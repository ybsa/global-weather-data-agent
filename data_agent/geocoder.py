"""Universal Geocoder & Location Resolver.
Resolves any city, district, village, or landmark globally using Open-Meteo's free geocoding API.
No API keys required.
"""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .models import LocationInfo

OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_USER_AGENT = "Universal-Data-Agent/1.0 (Open-Source Weather Intelligence)"


def slugify(text: str) -> str:
    """Normalize text into safe ASCII identifier (e.g. 'Kyōto' -> 'kyoto', 'Namche' -> 'namche')."""
    # Decompose unicode characters into ASCII base + combining mark
    ascii_norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^\w\s-]", "", ascii_norm.strip().lower())
    return re.sub(r"[-\s]+", "_", clean)


class UniversalGeocoder:
    """Universal geocoder querying Open-Meteo's free global geocoding API."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, opener=urlopen):
        self.user_agent = user_agent
        self.opener = opener

    def _request_json(self, url: str) -> dict:
        req = Request(url, headers={"User-Agent": self.user_agent})
        with self.opener(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search(
        self,
        query: str,
        count: int = 5,
        country_code: str | None = None,
        language: str = "en",
    ) -> list[LocationInfo]:
        """Search for one or more matching locations globally.
        
        Args:
            query: Name of city, village, mountain, or district.
            count: Max number of candidates (default 5).
            country_code: Optional ISO 2-letter country code (e.g. 'NP', 'US', 'JP').
            language: Preferred response language (default 'en').
        """
        if not query or not query.strip():
            return []

        params = [
            f"name={quote_plus(query.strip())}",
            f"count={max(1, min(count, 50))}",
            f"language={language}",
        ]
        if country_code:
            params.append(f"country_code={quote_plus(country_code.upper())}")

        url = f"{OPEN_METEO_GEOCODE_URL}?{'&'.join(params)}"

        try:
            payload = self._request_json(url)
        except Exception:
            return []

        results = payload.get("results", [])
        locations: list[LocationInfo] = []

        for item in results:
            name = item.get("name", query.strip().title())
            country = item.get("country", "")
            ccode = item.get("country_code", "")
            admin1 = item.get("admin1", "")
            admin2 = item.get("admin2", "")
            admin3 = item.get("admin3", "")
            lat = float(item.get("latitude", 0.0))
            lon = float(item.get("longitude", 0.0))
            elevation = float(item.get("elevation", 0.0) or 0.0)
            tz = item.get("timezone", "UTC")

            # Generate unique slug: e.g. 'namche_bazar_np' or 'tokyo_jp'
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


# Convenience function
_default_geocoder = UniversalGeocoder()

def resolve_location(query: str, country_code: str | None = None) -> LocationInfo | None:
    return _default_geocoder.resolve(query, country_code=country_code)

def search_locations(query: str, count: int = 5, country_code: str | None = None) -> list[LocationInfo]:
    return _default_geocoder.search(query, count=count, country_code=country_code)
