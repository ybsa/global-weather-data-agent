"""Universal Geocoder & Location Resolver.
Resolves any city, district, village, or landmark globally using Open-Meteo's free geocoding API,
and reverse-geocodes exact GPS coordinates down to any 2km patch on Earth.
No API keys required.
"""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.error import HTTPError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .models import LocationInfo

OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
REVERSE_GEOCODE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"
DEFAULT_USER_AGENT = "Universal-Natural-Data-Agent/1.0"


def slugify(text: str) -> str:
    """Normalize text into safe ASCII identifier (e.g. 'Kyōto' -> 'kyoto', 'Namche' -> 'namche')."""
    ascii_norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^\w\s-]", "", ascii_norm.strip().lower())
    return re.sub(r"[-\s]+", "_", clean)


class GeocodingError(RuntimeError):
    """Raised when the geocoding service cannot be reached (as opposed to 'no match found')."""


# Common informal country abbreviations that are not valid ISO 3166-1 alpha-2 codes
_COUNTRY_CODE_ALIASES = {"UK": "GB"}

GEOCODE_TIMEOUT_S = 8
_CACHE_MAX_ENTRIES = 256


class UniversalGeocoder:
    """Universal geocoder querying Open-Meteo's free global geocoding API."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, opener=urlopen):
        self.user_agent = user_agent
        self.opener = opener
        self._search_cache: dict[tuple, list[LocationInfo]] = {}

    def _request_json(self, url: str, timeout: float = 15) -> dict:
        req = Request(url, headers={"User-Agent": self.user_agent})
        with self.opener(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_open_meteo_raw(
        self,
        name: str,
        count: int = 5,
        country_code: str | None = None,
        language: str = "en",
    ) -> list[dict]:
        """Query Open-Meteo. Returns [] when there is no match.
        Raises GeocodingError when the service is unreachable or returns an invalid response.
        """
        params = [
            f"name={quote_plus(name.strip())}",
            f"count={max(1, min(count, 50))}",
            f"language={language}",
        ]
        if country_code:
            params.append(f"country_code={quote_plus(country_code.upper())}")

        url = f"{OPEN_METEO_GEOCODE_URL}?{'&'.join(params)}"
        try:
            payload = self._request_json(url, timeout=GEOCODE_TIMEOUT_S)
        except HTTPError as exc:
            if 400 <= exc.code < 500:
                return []  # e.g. invalid country_code filter: no match, not an outage
            raise GeocodingError(f"Geocoding service error (HTTP {exc.code})") from exc
        except Exception as exc:
            raise GeocodingError(f"Geocoding service unreachable: {exc}") from exc
        return payload.get("results") or []

    def search(
        self,
        query: str,
        count: int = 5,
        country_code: str | None = None,
        language: str = "en",
    ) -> list[LocationInfo]:
        """Search for one or more matching locations globally.
        Case-insensitive, and supports 'City, Country' or 'City, State' qualifiers
        (e.g. 'london, uk', 'lahaina, hi').

        Returns [] if nothing matches. Raises GeocodingError if the service is unreachable.
        """
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        cache_key = (clean_query.lower(), count, (country_code or "").upper(), language)
        if cache_key in self._search_cache:
            return list(self._search_cache[cache_key])

        locations = self._search_uncached(clean_query, count, country_code, language)

        if len(self._search_cache) >= _CACHE_MAX_ENTRIES:
            self._search_cache.pop(next(iter(self._search_cache)))
        self._search_cache[cache_key] = locations
        return list(locations)

    def _search_uncached(
        self,
        clean_query: str,
        count: int,
        country_code: str | None,
        language: str,
    ) -> list[LocationInfo]:

        # Check if user entered coordinates directly like "27.8033, 86.7144" or "35.68, 139.76"
        coord_match = re.match(r"^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$", clean_query)
        if coord_match:
            parts = [float(p.strip()) for p in clean_query.split(",")]
            loc = self.resolve_coordinates(parts[0], parts[1])
            return [loc]

        # Check for comma-separated qualifiers (e.g. "lahaina, hi", "london, uk", "delhi, india")
        detected_ccode = country_code.upper() if country_code else None
        name_part = clean_query
        qualifier = ""
        if "," in clean_query:
            comma_parts = [p.strip() for p in clean_query.split(",") if p.strip()]
            if comma_parts:
                name_part = comma_parts[0]
                if len(comma_parts) > 1:
                    qualifier = comma_parts[1]
                    if not detected_ccode and len(qualifier) == 2 and qualifier.isalpha():
                        detected_ccode = qualifier.upper()
        if detected_ccode:
            detected_ccode = _COUNTRY_CODE_ALIASES.get(detected_ccode, detected_ccode)

        # Open-Meteo matching is already case-insensitive, so no casing variants are needed.
        # Attempts, in priority order (deduplicated):
        #   1. Place name filtered by country code (explicit, or a 2-letter qualifier like 'uk')
        #   2. Full 'City, Country' string (Open-Meteo understands exact qualifiers natively)
        #   3. Bare place name, unfiltered
        attempts: list[tuple[str, str | None]] = []
        if detected_ccode:
            attempts.append((name_part, detected_ccode))
        if clean_query != name_part:
            attempts.append((clean_query, None))
        attempts.append((name_part, None))

        results: list[dict] = []
        last_error: GeocodingError | None = None
        for variant, ccode in dict.fromkeys(attempts):
            try:
                results = self._fetch_open_meteo_raw(variant, count=max(count, 5), country_code=ccode, language=language)
            except GeocodingError as exc:
                last_error = exc
                continue
            if results:
                break

        # A network failure may have hidden a real match: report it instead of "not found"
        if not results and last_error is not None:
            raise last_error

        # If qualifier (country/state name) was provided, prioritize matching items
        if qualifier and len(results) > 1:
            q_lower = qualifier.lower()
            def sort_key(item: dict) -> int:
                cntry = (item.get("country") or "").lower()
                a1 = (item.get("admin1") or "").lower()
                a2 = (item.get("admin2") or "").lower()
                cc = (item.get("country_code") or "").lower()
                if q_lower in (cntry, a1, a2, cc):
                    return 0
                if q_lower in cntry or q_lower in a1 or q_lower in a2:
                    return 1
                return 2
            results.sort(key=sort_key)

        results = results[:count]
        locations: list[LocationInfo] = []

        for item in results:
            name = item.get("name") or name_part.title()
            country = item.get("country", "")
            ccode = item.get("country_code", "")
            admin1 = item.get("admin1", "")
            admin2 = item.get("admin2", "")
            admin3 = item.get("admin3", "")
            lat = float(item.get("latitude", 0.0))
            lon = float(item.get("longitude", 0.0))
            elevation = float(item.get("elevation", 0.0) or 0.0)
            tz = item.get("timezone", "UTC")

            slug_parts = [slugify(name)]
            if admin2:
                slug_parts.append(slugify(admin2))
            if ccode:
                slug_parts.append(ccode.lower())
            loc_id = "_".join(slug_parts)

            locations.append(
                LocationInfo(
                    location_id=loc_id,
                    name=name,
                    country=country,
                    country_code=ccode,
                    admin1=admin1,
                    admin2=admin2,
                    admin3=admin3,
                    latitude=lat,
                    longitude=lon,
                    elevation_m=elevation,
                    timezone=tz,
                )
            )

        return locations

    def resolve(
        self,
        query: str,
        country_code: str | None = None,
    ) -> LocationInfo | None:
        """Resolve a query to the single best matching location globally."""
        candidates = self.search(query, count=1, country_code=country_code)
        return candidates[0] if candidates else None

    def resolve_coordinates(self, latitude: float, longitude: float) -> LocationInfo:
        """Reverse geocode exact GPS coordinates for any spot / 2km grid cell on Earth."""
        lat = round(latitude, 4)
        lon = round(longitude, 4)

        place_name = f"Zone ({lat:.4f}°, {lon:.4f}°)"
        country = ""
        country_code = ""
        admin1 = ""
        admin2 = ""
        elevation = 0.0

        # 1. Reverse geocoding lookup
        try:
            rev_url = f"{REVERSE_GEOCODE_URL}?latitude={lat}&longitude={lon}&localityLanguage=en"
            rev_data = self._request_json(rev_url)
            locality = rev_data.get("locality") or rev_data.get("city") or ""
            admin_sub = rev_data.get("principalSubdivision") or ""
            cntry = rev_data.get("countryName") or ""
            ccode = rev_data.get("countryCode") or ""

            if locality:
                place_name = locality
            elif admin_sub:
                place_name = f"{admin_sub} Area"
            elif cntry:
                place_name = f"{cntry} Region"

            country = cntry
            country_code = ccode
            admin1 = admin_sub
        except Exception:
            pass

        # 2. Elevation lookup
        try:
            elev_url = f"{OPEN_METEO_ELEVATION_URL}?latitude={lat}&longitude={lon}"
            elev_data = self._request_json(elev_url)
            elevs = elev_data.get("elevation", [])
            if elevs and elevs[0] is not None:
                elevation = float(elevs[0])
        except Exception:
            pass

        slug_parts = ["loc", f"{lat:.4f}".replace(".", "p").replace("-", "m"), f"{lon:.4f}".replace(".", "p").replace("-", "m")]
        loc_id = "_".join(slug_parts)

        return LocationInfo(
            location_id=loc_id,
            name=place_name,
            country=country,
            country_code=country_code,
            admin1=admin1,
            admin2=admin2,
            latitude=lat,
            longitude=lon,
            elevation_m=elevation,
            timezone="auto",
        )


_default_geocoder = UniversalGeocoder()

def resolve_location(query: str, country_code: str | None = None) -> LocationInfo | None:
    return _default_geocoder.resolve(query, country_code=country_code)

def search_locations(query: str, count: int = 5, country_code: str | None = None) -> list[LocationInfo]:
    return _default_geocoder.search(query, count=count, country_code=country_code)

def resolve_coordinates(latitude: float, longitude: float) -> LocationInfo:
    return _default_geocoder.resolve_coordinates(latitude, longitude)
