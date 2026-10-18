"""CLI tool to export historical weather data for downstream model training."""
from __future__ import annotations

import argparse
from weather_agent.cli import load_locations
from project1_data_agent.timesfm_exporter import export_timesfm_dataset


def main():
    parser = argparse.ArgumentParser(description="Export historical weather for TimesFM training")
    parser.add_argument("--locations", default="config/locations.csv", help="Path to locations CSV")
    parser.add_argument("--output", default="exports/weather_timeseries.csv", help="Output CSV path")
    parser.add_argument("--start", default="2023-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2023-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of locations to export (default 10)")

    args = parser.parse_args()

    locs = list(load_locations(args.locations))
    if args.limit:
        locs = locs[:args.limit]

    print(f"Selected {len(locs)} locations for TimesFM dataset generation.")
    export_timesfm_dataset(locs, output_path=args.output, start_date=args.start, end_date=args.end)


if __name__ == "__main__":
    main()
