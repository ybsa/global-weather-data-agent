"""Global place-name resolver backed by the Open-Meteo geocoding API."""
from __future__ import annotations

import json
import re
import sqlite3
from urllib.parse import quote_plus
from urllib.request import urlopen

from .models import Location

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class AmbiguousLocationError(ValueError):
    """Raised when a place name matches multiple locations."""


def slugify(text: str) -> str:
    """Normalize place name to safe ID."""
    clean = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "_", clean)


def find_local_location(con: sqlite3.Connection, query: str) -> Location | None:
    """Search for location in the local SQLite database first."""
    query_norm = query.strip().lower()
    place_query = query.split(",", 1)[0].strip().lower()
    country_code = _country_qualifier(query)
    
    # 1. Exact match on location_id or name
    rows = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m, country_code
           FROM locations
           WHERE lower(location_id) = ? OR lower(name) = ?
           ORDER BY length(name) ASC LIMIT 20""",
        (query_norm, place_query),
    ).fetchall()

    exact_id = [row for row in rows if row["location_id"].lower() == query_norm]
    exact_name = [
        row for row in rows
        if row["name"].lower() == place_query
        and (not country_code or (row["country_code"] or "").upper() == country_code)
    ]
    matches = exact_id or exact_name
    places = {
        ((row["country_code"] or "").upper(), row["province"] or "", row["district"] or "")
        for row in matches
    }
    if len(places) > 1:
        choices = "; ".join(
            f"{row['name']}, {row['district'] or row['province']}, {row['country_code']}"
            for row in matches[:5]
        )
        qualifier_hint = (
            f"Add a region to '{place_query}, {country_code}'."
            if country_code else f"Add a country or region, such as '{place_query}, {matches[0]['country_code']}'."
        )
        raise AmbiguousLocationError(
            f"'{query}' matches multiple saved locations. {qualifier_hint} Matches: {choices}"
        )
    row = matches[0] if matches else None
    
    if row:
        return Location(
            location_id=row["location_id"],
            name=row["name"],
            province=row["province"] or "Unknown",
            district=row["district"] or "Unknown",
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            elevation_m=float(row["elevation_m"] or 0.0),
            country_code=row["country_code"] or "",
        )

    # 2. Substring match
    if "," in query and not country_code:
        return None

    rows = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m, country_code
           FROM locations
           WHERE lower(name) LIKE ? OR lower(location_id) LIKE ?
           ORDER BY length(name) ASC LIMIT 20""",
        (f"%{place_query}%", f"%{place_query}%"),
    ).fetchall()
    if country_code:
        rows = [row for row in rows if (row["country_code"] or "").upper() == country_code]
    if len({(row["country_code"] or "").upper() for row in rows if row["country_code"]}) > 1:
        choices = "; ".join(
            f"{row['name']}, {row['district'] or row['province']}, {row['country_code']}"
            for row in rows[:5]
        )
        raise AmbiguousLocationError(
            f"'{query}' matches multiple saved locations. Add a country code to choose one. "
            f"Matches: {choices}"
        )
    row = rows[0] if rows else None

    if row:
        return Location(
            location_id=row["location_id"],
            name=row["name"],
            province=row["province"] or "Unknown",
            district=row["district"] or "Unknown",
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            elevation_m=float(row["elevation_m"] or 0.0),
            country_code=row["country_code"] or "",
        )

    return None


def search_local_locations(con: sqlite3.Connection, query: str, limit: int = 5) -> list[Location]:
    """Search for multiple matching locations in local SQLite database."""
    query_norm = query.strip().lower()
    rows = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m, country_code
           FROM locations
           WHERE lower(name) LIKE ? OR lower(location_id) LIKE ? OR lower(district) LIKE ?
           ORDER BY length(name) ASC
           LIMIT ?""",
        (f"%{query_norm}%", f"%{query_norm}%", f"%{query_norm}%", limit),
    ).fetchall()

    return [
        Location(
            location_id=row["location_id"],
            name=row["name"],
            province=row["province"] or "Unknown",
            district=row["district"] or "Unknown",
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            elevation_m=float(row["elevation_m"] or 0.0),
            country_code=row["country_code"] or "",
        )
        for row in rows
    ]


def geocode_global_location(query: str, opener=urlopen) -> Location | None:
    """Geocode a city, town, village, or named place anywhere in the world."""
    params = f"?name={quote_plus(query)}&count=10&language=en"
    url = f"{GEOCODING_URL}{params}"

    try:
        with opener(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    results = data.get("results", [])
    if not results:
        return None

    # The API uses a trailing country/admin qualifier in name (e.g. "London, UK").
    # If the unqualified name matches multiple countries, require that context.
    if "," not in query:
        normalized_query = query.strip().casefold()
        exact_results = [
            result for result in results
            if str(result.get("name", "")).strip().casefold() == normalized_query
        ]
        ambiguity_candidates = exact_results or results
        places = {
            (
                str(result.get("country_code", "")).upper(),
                str(result.get("admin1", "")),
                str(result.get("admin2", result.get("admin3", ""))),
            )
            for result in exact_results
        }
        countries = {place[0] for place in places if place[0]}
        if len(countries) > 1 or (len(exact_results) > 1 and len(places) > 1):
            suggestions = []
            for result in ambiguity_candidates:
                label = ", ".join(
                    part for part in (
                        result.get("name"), result.get("admin1"),
                        result.get("country"), result.get("country_code"),
                    ) if part
                )
                if label and label not in suggestions:
                    suggestions.append(label)
            choices = "; ".join(suggestions[:5])
            first_country = results[0].get("country", results[0].get("country_code", ""))
            first_region = results[0].get("admin1")
            qualifier = first_region if len(countries) <= 1 and first_region else first_country
            raise AmbiguousLocationError(
                f"'{query}' matches multiple places. Add a country or region, "
                f"for example '{query}, {qualifier}'. "
                f"Matches: {choices}"
            )

    res = results[0]
    name = res.get("name", query.strip().title())
    admin1 = res.get("admin1", "Unknown")
    admin2 = res.get("admin2", res.get("admin3", "Unknown"))
    country = res.get("country_code", res.get("country", "Unknown"))
    elevation = float(res.get("elevation", 0.0) or 0.0)
    country_code = str(res.get("country_code", "")).upper()
    loc_id = slugify(f"{name}_{admin2}_{country_code or country}")

    return Location(
        location_id=loc_id,
        name=name,
        province=admin1,
        district=admin2,
        latitude=float(res.get("latitude", 0)),
        longitude=float(res.get("longitude", 0)),
        elevation_m=elevation,
        country_code=country_code,
    )


def _country_qualifier(query: str) -> str:
    """Return a country-code qualifier when the query uses an unambiguous ISO code."""
    if "," not in query:
        return ""
    qualifier = query.rsplit(",", 1)[-1].strip()
    return qualifier.upper() if len(qualifier) == 2 and qualifier.isalpha() else ""


def resolve_location(con: sqlite3.Connection, query: str) -> Location | None:
    """Resolve location: checks local DB first, falls back to dynamic geocoding and auto-saves."""
    local = find_local_location(con, query)
    if local:
        return local

    # Try dynamic geocoding for locations not already in the local cache.
    geocoded = geocode_global_location(query)
    if geocoded:
        # Import save_location to dynamically register the discovered village
        from .storage import save_location
        save_location(con, geocoded)
        con.commit()
        return geocoded

    return None
