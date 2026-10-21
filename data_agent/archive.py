"""Universal Historical Natural Indicators Scraper.
Fetches continuous historical time-series back to 1940 for any location on Earth.
Pulls atmospheric, wind, rain, pressure, and soil moisture conditions.
Uses Open-Meteo Historical Archive API (free, zero API keys required).
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import LocationInfo

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_USER_AGENT = "Universal-Natural-Data-Agent/1.0"
NATURAL_HISTORICAL_FIELDS = (
    "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_gusts_10m,"
    "surface_pressure,soil_temperature_0_to_7cm,soil_moisture_0_to_7cm,soil_moisture_7_to_28cm"
)


def fetch_historical_series(
    location: LocationInfo,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    variables: str = NATURAL_HISTORICAL_FIELDS,
    opener=urlopen,
) -> list[dict]:
    """Fetch continuous hourly historical series for any global location.
    
    Returns clean dictionaries ready for ML dataframe / CSV / Parquet conversion.
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
    gusts = hourly.get("wind_gusts_10m", [])
    pressures = hourly.get("surface_pressure", [])
    soil_temps = hourly.get("soil_temperature_0_to_7cm", [])
    soil_moist1 = hourly.get("soil_moisture_0_to_7cm", [])
    soil_moist2 = hourly.get("soil_moisture_7_to_28cm", [])

    for idx, t in enumerate(times):
        records.append({
            "location_id": location.location_id,
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
            "wind_gusts_10m": gusts[idx] if idx < len(gusts) else None,
            "surface_pressure_hpa": pressures[idx] if idx < len(pressures) else None,
            "soil_temperature_0_to_7cm": soil_temps[idx] if idx < len(soil_temps) else None,
            "soil_moisture_0_to_7cm": soil_moist1[idx] if idx < len(soil_moist1) else None,
            "soil_moisture_7_to_28cm": soil_moist2[idx] if idx < len(soil_moist2) else None,
        })

    return records
