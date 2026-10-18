"""External feeds. Provider outputs must declare what the values mean."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

from .models import Location

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
HOURLY_FIELDS = "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code"


def fetch_open_meteo(location: Location, opener=urlopen) -> list[dict]:
    """Return normalized records. Current values are model estimates, not station observations."""
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "elevation": location.elevation_m,
        "current": CURRENT_FIELDS,
        "hourly": HOURLY_FIELDS,
        "forecast_days": 3,
        "timezone": "auto",
    }
    url = f"{OPEN_METEO_URL}?{urlencode(params)}"
    with opener(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    received_at = datetime.now(timezone.utc).isoformat()
    records = []
    current = payload.get("current", {})
    if current.get("time"):
        records.append(_record(location, "model_estimated", "open-meteo", "current", current["time"], current, received_at, payload))
    hourly = payload.get("hourly", {})
    for index, valid_at in enumerate(hourly.get("time", [])):
        values = {key: series[index] for key, series in hourly.items() if key != "time" and index < len(series)}
        records.append(_record(location, "forecast", "open-meteo", "hourly", valid_at, values, received_at, payload))
    return records


def _record(location, data_kind, source, product, valid_at, values, received_at, raw_payload):
    return {
        "location_id": location.location_id,
        "data_kind": data_kind,
        "source": source,
        "product": product,
        "valid_at": valid_at,
        "received_at": received_at,
        "temperature_c": values.get("temperature_2m"),
        "humidity_pct": values.get("relative_humidity_2m"),
        "precipitation_mm": values.get("precipitation"),
        "precipitation_probability_pct": values.get("precipitation_probability"),
        "wind_speed_kmh": values.get("wind_speed_10m"),
        "weather_code": values.get("weather_code"),
        "raw_payload": json.dumps(raw_payload, separators=(",", ":")),
    }

