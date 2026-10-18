"""Universal Historical Weather Scraper.
Fetches continuous historical time-series back to 1940 for any location on Earth.
Uses Open-Meteo Historical Archive API (free, zero API keys required).
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import LocationInfo

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_USER_AGENT = "Universal-Data-Agent/1.0"
HISTORICAL_FIELDS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure"


def fetch_historical_series(
    location: LocationInfo,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    variables: str = HISTORICAL_FIELDS,
    opener=urlopen,
) -> list[dict]:
    """Fetch continuous hourly historical series for any global location.
    
    Returns clean dictionaries ready for ML dataframe / CSV conversion.
    """
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "elevation": location.elevation_m,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": variables,
        "timezone": location.timezone or "UTC",
    }
    url = f"{ARCHIVE_API_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})

    with opener(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    records = []

    temps = hourly.get("temperature_2m", [])
    humids = hourly.get("relative_humidity_2m", [])
    precips = hourly.get("precipitation", [])
    winds = hourly.get("wind_speed_10m", [])
    pressures = hourly.get("surface_pressure", [])

    for idx, t in enumerate(times):
        records.append({
            "unique_id": location.location_id,
            "name": location.name,
            "country": location.country,
            "country_code": location.country_code,
            "admin1": location.admin1,
            "admin2": location.admin2,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "elevation_m": location.elevation_m,
            "timestamp": t,
            "temperature_2m": temps[idx] if idx < len(temps) else None,
            "relative_humidity_2m": humids[idx] if idx < len(humids) else None,
            "precipitation_mm": precips[idx] if idx < len(precips) else 0.0,
            "wind_speed_10m": winds[idx] if idx < len(winds) else None,
            "surface_pressure_hpa": pressures[idx] if idx < len(pressures) else None,
        })

    return records
