"""Global place-name resolver backed by the Open-Meteo geocoding API."""
from __future__ import annotations

import json
import re
import sqlite3
from urllib.parse import quote_plus
from urllib.request import urlopen

from .models import Location

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

def slugify(text: str) -> str:
    """Normalize place name to safe ID."""
    clean = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "_", clean)


def find_local_location(con: sqlite3.Connection, query: str) -> Location | None:
    """Search for location in the local SQLite database first."""
    query_norm = query.strip().lower()
    
    # 1. Exact match on location_id or name
    row = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m
           FROM locations
           WHERE lower(location_id) = ? OR lower(name) = ?
           LIMIT 1""",
        (query_norm, query_norm),
    ).fetchone()
    
    if row:
        return Location(
            location_id=row["location_id"],
            name=row["name"],
            province=row["province"] or "Unknown",
            district=row["district"] or "Unknown",
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            elevation_m=float(row["elevation_m"] or 0.0),
        )

    # 2. Substring match
    row = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m
           FROM locations
           WHERE lower(name) LIKE ? OR lower(location_id) LIKE ?
           ORDER BY length(name) ASC
           LIMIT 1""",
        (f"%{query_norm}%", f"%{query_norm}%"),
    ).fetchone()

    if row:
        return Location(
            location_id=row["location_id"],
            name=row["name"],
            province=row["province"] or "Unknown",
            district=row["district"] or "Unknown",
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            elevation_m=float(row["elevation_m"] or 0.0),
        )

    return None


def search_local_locations(con: sqlite3.Connection, query: str, limit: int = 5) -> list[Location]:
    """Search for multiple matching locations in local SQLite database."""
    query_norm = query.strip().lower()
    rows = con.execute(
        """SELECT location_id, name, province, district, latitude, longitude, elevation_m
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

    res = results[0]
    name = res.get("name", query.strip().title())
    admin1 = res.get("admin1", "Unknown")
    admin2 = res.get("admin2", res.get("admin3", "Unknown"))
    country = res.get("country_code", res.get("country", "Unknown"))
    elevation = float(res.get("elevation", 0.0) or 0.0)
    loc_id = slugify(f"{name}_{admin2}_{country}")

    return Location(
        location_id=loc_id,
        name=name,
        province=admin1,
        district=admin2,
        latitude=float(res.get("latitude", 0)),
        longitude=float(res.get("longitude", 0)),
        elevation_m=elevation,
    )


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
