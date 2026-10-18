"""Standardized Machine-Learning Dataset Exporter.
Exports continuous multi-location weather time-series into standardized CSV format
compatible with Google TimesFM, Chronos, Nixtla, or custom deep-learning architectures.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from .archive import fetch_historical_series
from .geocoder import resolve_location
from .models import LocationInfo


def export_ml_dataset(
    locations: Sequence[LocationInfo],
    output_path: str,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    verbose: bool = True,
) -> int:
    """Export time-series for a sequence of LocationInfo objects to a CSV file.
    
    Standard Columns:
      unique_id, name, country, country_code, latitude, longitude, elevation_m,
      timestamp, temperature_2m, precipitation_mm, relative_humidity_2m,
      wind_speed_10m, surface_pressure_hpa
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []

    if verbose:
        print(f"[Data Agent] Exporting dataset for {len(locations)} location(s) from {start_date} to {end_date}...")

    for loc in locations:
        try:
            if verbose:
                print(f"  • Fetching historical series for: {loc.display_name} (elevation: {loc.elevation_m}m)...")
            rows = fetch_historical_series(loc, start_date=start_date, end_date=end_date)
            all_rows.extend(rows)
            if verbose:
                print(f"    -> {len(rows)} hourly steps collected.")
        except Exception as exc:
            if verbose:
                print(f"    FAILED for {loc.name}: {exc}")

    if not all_rows:
        if verbose:
            print("[Data Agent] Warning: No records retrieved.")
        return 0

    fieldnames = list(all_rows[0].keys())
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    if verbose:
        print(f"[Data Agent] Successfully exported {len(all_rows)} rows to: {out_file.resolve()}")
    return len(all_rows)


def export_from_queries(
    queries: Sequence[str],
    output_path: str,
    start_date: str = "2023-01-01",
    end_date: str = "2023-12-31",
    country_code: str | None = None,
    verbose: bool = True,
) -> int:
    """Resolve a list of location name strings and export their historical data to CSV."""
    locations: list[LocationInfo] = []
    for q in queries:
        loc = resolve_location(q, country_code=country_code)
        if loc:
            locations.append(loc)
        elif verbose:
            print(f"[Data Agent] Could not resolve location: '{q}'")

    if not locations:
        if verbose:
            print("[Data Agent] Error: Zero valid locations resolved.")
        return 0

    return export_ml_dataset(
        locations,
        output_path=output_path,
        start_date=start_date,
        end_date=end_date,
        verbose=verbose,
    )
