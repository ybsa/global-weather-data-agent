"""Historical Weather Exporter for Google TimesFM.
Fetches continuous hourly historical weather series for configured locations
and formats them directly into TimesFM training format (unique_id, timestamp, target).
Uses Open-Meteo Historical Archive API (free, no API key required).
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from weather_agent.models import Location
from weather_agent.storage import connect

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORICAL_FIELDS = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,surface_pressure"


def fetch_historical_series(
    location: Location,
    start_date: str = "2023-01-01",
    end_date: str = "2024-01-01",
    opener=urlopen,
) -> list[dict]:
    """Fetch continuous hourly historical series for a configured location."""
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "elevation": location.elevation_m,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HISTORICAL_FIELDS,
        "timezone": "auto",
    }
    url = f"{ARCHIVE_API_URL}?{urlencode(params)}"
    with opener(url, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    records = []

    for idx, t in enumerate(times):
        records.append({
            "unique_id": location.location_id,
            "name": location.name,
            "district": location.district,
            "province": location.province,
            "elevation_m": location.elevation_m,
            "timestamp": t,
            "temperature_2m": hourly.get("temperature_2m", [])[idx] if idx < len(hourly.get("temperature_2m", [])) else None,
            "relative_humidity_2m": hourly.get("relative_humidity_2m", [])[idx] if idx < len(hourly.get("relative_humidity_2m", [])) else None,
            "precipitation_mm": hourly.get("precipitation", [])[idx] if idx < len(hourly.get("precipitation", [])) else 0.0,
            "wind_speed_10m": hourly.get("wind_speed_10m", [])[idx] if idx < len(hourly.get("wind_speed_10m", [])) else None,
            "surface_pressure_hpa": hourly.get("surface_pressure", [])[idx] if idx < len(hourly.get("surface_pressure", [])) else None,
        })

    return records


def export_timesfm_dataset(
    locations: list[Location],
    output_path: str,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
) -> int:
    """Export multi-location dataset formatted for Google TimesFM fine-tuning.
    Generates CSV with columns: unique_id, timestamp, temperature_2m, precipitation_mm, relative_humidity_2m, wind_speed_10m, surface_pressure_hpa
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    all_rows = []

    print(f"Exporting TimesFM historical dataset for {len(locations)} locations ({start_date} to {end_date})...")
    for loc in locations:
        try:
            print(f"  Fetching historical data for {loc.name} ({loc.district}, {loc.province}, {loc.elevation_m}m)...")
            rows = fetch_historical_series(loc, start_date=start_date, end_date=end_date)
            all_rows.extend(rows)
            print(f"    -> {len(rows)} hourly records.")
        except Exception as exc:
            print(f"    FAILED for {loc.name}: {exc}")

    if not all_rows:
        print("No records retrieved.")
        return 0

    fieldnames = list(all_rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} total time-series steps to: {output_path}")
    return len(all_rows)
