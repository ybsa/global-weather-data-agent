"""Universal Hydrology & Flood Indicator Collector.
Pulls real-time & forecast river discharge and multi-depth soil moisture data globally.
Powered by Open-Meteo Global Flood API and Land-Surface models.
No API keys required.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import HydrologySnapshot

FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_USER_AGENT = "Universal-Natural-Data-Agent/1.0"


class HydrologyCollector:
    """Collects river discharge and multi-strata soil moisture data."""

    def __init__(self, opener=urlopen):
        self.opener = opener

    def _request_json(self, url: str) -> dict:
        req = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with self.opener(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_hydrology(
        self,
        latitude: float,
        longitude: float,
    ) -> HydrologySnapshot:
        """Fetch real-time hydrology snapshot (river discharge and soil moisture) for any location."""
        # 1. Fetch river discharge from Flood API
        flood_params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "river_discharge,river_discharge_mean,river_discharge_max",
            "forecast_days": 3,
            "past_days": 3,
        }
        flood_url = f"{FLOOD_API_URL}?{urlencode(flood_params)}"

        river_cur = None
        river_mean = None
        river_max = None
        timestamp = ""

        try:
            flood_data = self._request_json(flood_url)
            daily = flood_data.get("daily", {})
            discharges = daily.get("river_discharge", [])
            means = daily.get("river_discharge_mean", [])
            maxs = daily.get("river_discharge_max", [])
            times = daily.get("time", [])

            if discharges:
                # Use today's index (past_days index is typically index 3)
                idx = min(3, len(discharges) - 1)
                river_cur = discharges[idx] if discharges[idx] is not None else (discharges[0] if discharges else None)
                if times and idx < len(times):
                    timestamp = times[idx]
            if means:
                valid_means = [x for x in means if x is not None]
                if valid_means:
                    river_mean = sum(valid_means) / len(valid_means)
            if maxs:
                valid_maxs = [x for x in maxs if x is not None]
                if valid_maxs:
                    river_max = max(valid_maxs)
        except Exception:
            pass

        # 2. Fetch multi-layer soil moisture from Land/Weather model
        soil_params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_9_to_27cm,soil_moisture_27_to_81cm",
            "forecast_days": 1,
        }
        soil_url = f"{WEATHER_API_URL}?{urlencode(soil_params)}"

        sm_0_1 = None
        sm_1_3 = None
        sm_9_27 = None
        sm_27_81 = None

        try:
            soil_data = self._request_json(soil_url)
            hourly = soil_data.get("hourly", {})
            sm0 = hourly.get("soil_moisture_0_to_1cm", [])
            sm1 = hourly.get("soil_moisture_1_to_3cm", [])
            sm9 = hourly.get("soil_moisture_9_to_27cm", [])
            sm27 = hourly.get("soil_moisture_27_to_81cm", [])

            if sm0 and len(sm0) > 0 and sm0[0] is not None:
                sm_0_1 = float(sm0[0])
            if sm1 and len(sm1) > 0 and sm1[0] is not None:
                sm_1_3 = float(sm1[0])
            if sm9 and len(sm9) > 0 and sm9[0] is not None:
                sm_9_27 = float(sm9[0])
            if sm27 and len(sm27) > 0 and sm27[0] is not None:
                sm_27_81 = float(sm27[0])
        except Exception:
            pass

        return HydrologySnapshot(
            river_discharge_m3s=round(float(river_cur), 2) if river_cur is not None else None,
            river_discharge_mean_7d=round(float(river_mean), 2) if river_mean is not None else None,
            river_discharge_max_7d=round(float(river_max), 2) if river_max is not None else None,
            soil_moisture_0_to_1cm=round(sm_0_1, 4) if sm_0_1 is not None else None,
            soil_moisture_1_to_3cm=round(sm_1_3, 4) if sm_1_3 is not None else None,
            soil_moisture_9_to_27cm=round(sm_9_27, 4) if sm_9_27 is not None else None,
            soil_moisture_27_to_81cm=round(sm_27_81, 4) if sm_27_81 is not None else None,
            timestamp=timestamp,
            source="open-meteo-flood-and-land",
        )


_default_hydrology = HydrologyCollector()


def get_hydrology(latitude: float, longitude: float) -> HydrologySnapshot:
    return _default_hydrology.fetch_hydrology(latitude, longitude)
