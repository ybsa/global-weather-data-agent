"""Universal Real-Time Weather & Forecast Collector.
Pulls continuous real-time weather and forecast series for any location globally via Open-Meteo.
No API keys required.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import CurrentWeather, LocationInfo

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_USER_AGENT = "Universal-Data-Agent/1.0"


class UniversalCollector:
    """Universal live and forecast data fetcher."""

    def __init__(self, opener=urlopen):
        self.opener = opener

    def _request_json(self, url: str) -> dict:
        req = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with self.opener(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_current(self, location: LocationInfo) -> CurrentWeather:
        """Fetch current weather snapshot for any global location."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "elevation": location.elevation_m,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure,weather_code,is_day",
            "timezone": location.timezone or "auto",
        }
        url = f"{FORECAST_API_URL}?{urlencode(params)}"
        payload = self._request_json(url)

        curr = payload.get("current", {})
        return CurrentWeather(
            location=location,
            timestamp=curr.get("time", ""),
            temperature_2m=float(curr.get("temperature_2m", 0.0) or 0.0),
            relative_humidity_2m=float(curr.get("relative_humidity_2m", 0.0) or 0.0),
            precipitation_mm=float(curr.get("precipitation", 0.0) or 0.0),
            wind_speed_10m=float(curr.get("wind_speed_10m", 0.0) or 0.0),
            surface_pressure_hpa=float(curr.get("surface_pressure", 0.0) or 0.0),
            weather_code=int(curr.get("weather_code", 0) or 0),
            is_day=int(curr.get("is_day", 1) or 1),
            source="open-meteo",
            data_kind="model-estimated",
        )

    def fetch_hourly(self, location: LocationInfo, forecast_days: int = 3) -> HourlyForecast:
        """Fetch multi-day hourly forecast series for any global location."""
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "elevation": location.elevation_m,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure",
            "forecast_days": min(max(1, forecast_days), 16),
            "timezone": location.timezone or "auto",
        }
        url = f"{FORECAST_API_URL}?{urlencode(params)}"
        payload = self._request_json(url)

        hourly = payload.get("hourly", {})
        return HourlyForecast(
            location=location,
            times=hourly.get("time", []),
            temperatures=[float(x or 0.0) for x in hourly.get("temperature_2m", [])],
            humidities=[float(x or 0.0) for x in hourly.get("relative_humidity_2m", [])],
            precipitations=[float(x or 0.0) for x in hourly.get("precipitation", [])],
            wind_speeds=[float(x or 0.0) for x in hourly.get("wind_speed_10m", [])],
            pressures=[float(x or 0.0) for x in hourly.get("surface_pressure", [])],
        )


_default_collector = UniversalCollector()

def get_current_weather(location: LocationInfo) -> CurrentWeather:
    return _default_collector.fetch_current(location)

def get_hourly_forecast(location: LocationInfo, forecast_days: int = 3) -> HourlyForecast:
    return _default_collector.fetch_hourly(location, forecast_days=forecast_days)
