"""Universal Chart & Time-Series Data Aggregator.
Fetches continuous multi-day hourly and daily series for atmospheric,
hydrology (river discharge), soil moisture strata, and seismic activity.
Formats clean payloads ready for Chart.js and prediction dashboards.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .cache import chart_cache
from .models import LocationInfo
from .seismic import get_recent_earthquakes

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
DEFAULT_USER_AGENT = "Universal-Natural-Data-Agent/1.0"


def fetch_chart_data(
    latitude: float,
    longitude: float,
    days: int = 7,
    opener=urlopen,
    use_cache: bool = True,
) -> dict:
    """Fetch complete multi-category time-series for dynamic charting with 5-minute TTL caching."""
    safe_days = min(max(1, days), 14)
    cache_key = (round(latitude, 3), round(longitude, 3), safe_days)

    if use_cache:
        cached = chart_cache.get(cache_key)
        if cached is not None:
            return cached

    data = _fetch_chart_data_uncached(latitude, longitude, safe_days, opener=opener)
    if use_cache and data:
        chart_cache.set(cache_key, data, ttl_seconds=300.0)
    return data


def _fetch_chart_data_uncached(
    latitude: float,
    longitude: float,
    safe_days: int,
    opener=urlopen,
) -> dict:

    # 1. Open-Meteo Hourly (Atmosphere + Soil Moisture)
    weather_params = {
        "latitude": latitude,
        "longitude": longitude,
        "past_days": safe_days,
        "forecast_days": safe_days,
        "hourly": (
            "temperature_2m,relative_humidity_2m,precipitation,"
            "wind_speed_10m,wind_gusts_10m,surface_pressure,"
            "soil_moisture_0_to_1cm,soil_moisture_27_to_81cm"
        ),
    }
    w_url = f"{FORECAST_API_URL}?{urlencode(weather_params)}"
    req_w = Request(w_url, headers={"User-Agent": DEFAULT_USER_AGENT})

    hourly = {}
    try:
        with opener(req_w, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            hourly = payload.get("hourly", {})
    except Exception:
        pass

    # 2. Open-Meteo Flood API (Daily River Discharge)
    flood_params = {
        "latitude": latitude,
        "longitude": longitude,
        "past_days": safe_days,
        "forecast_days": safe_days,
        "daily": "river_discharge,river_discharge_mean,river_discharge_max",
    }
    f_url = f"{FLOOD_API_URL}?{urlencode(flood_params)}"
    req_f = Request(f_url, headers={"User-Agent": DEFAULT_USER_AGENT})

    flood_daily = {}
    try:
        with opener(req_f, timeout=20) as resp:
            f_payload = json.loads(resp.read().decode("utf-8"))
            flood_daily = f_payload.get("daily", {})
    except Exception:
        pass

    # 3. USGS Recent Earthquakes within 300km
    eqs = get_recent_earthquakes(latitude, longitude, radius_km=300.0, min_magnitude=1.0, limit=40)
    seismic_series = [
        {
            "timestamp": eq.timestamp,
            "magnitude": eq.magnitude,
            "place": eq.place,
            "distance_km": eq.distance_km,
            "depth_km": eq.depth_km,
        }
        for eq in reversed(eqs)
    ]

    return {
        "latitude": latitude,
        "longitude": longitude,
        "days": safe_days,
        "hourly": {
            "times": hourly.get("time", []),
            "surface_pressure_hpa": hourly.get("surface_pressure", []),
            "temperature_2m": hourly.get("temperature_2m", []),
            "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
            "precipitation_mm": hourly.get("precipitation", []),
            "wind_speed_10m": hourly.get("wind_speed_10m", []),
            "wind_gusts_10m": hourly.get("wind_gusts_10m", []),
            "soil_moisture_0_to_1cm": hourly.get("soil_moisture_0_to_1cm", []),
            "soil_moisture_27_to_81cm": hourly.get("soil_moisture_27_to_81cm", []),
        },
        "river": {
            "times": flood_daily.get("time", []),
            "discharge_m3s": flood_daily.get("river_discharge", []),
            "discharge_mean": flood_daily.get("river_discharge_mean", []),
            "discharge_max": flood_daily.get("river_discharge_max", []),
        },
        "seismic": seismic_series,
    }
