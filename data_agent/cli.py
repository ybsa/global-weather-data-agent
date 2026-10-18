"""Universal Data Agent CLI.
Command-line interface for global geocoding, live weather scraping, and ML dataset exporting.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure Windows terminal doesn't crash on international unicode characters (e.g. Kyoto -> Kyōto)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

from .archive import fetch_historical_series
from .collector import get_current_weather, get_hourly_forecast
from .exporter import export_from_queries, export_ml_dataset
from .geocoder import resolve_location, search_locations
from .models import LocationInfo


def cmd_search(args):
    """Search for locations matching query."""
    results = search_locations(args.query, count=args.count, country_code=args.country)
    if not results:
        print(f"No locations found for '{args.query}'")
        return 1

    print(f"\nFound {len(results)} location(s) for '{args.query}':")
    print("-" * 75)
    for i, loc in enumerate(results, 1):
        print(f"[{i}] {loc.display_name}")
        print(f"    Coordinates : {loc.latitude:.4f} N, {loc.longitude:.4f} E")
        print(f"    Elevation   : {loc.elevation_m} meters")
        print(f"    Timezone    : {loc.timezone}")
        print(f"    ID (slug)   : {loc.location_id}")
        print("-" * 75)
    return 0


def cmd_live(args):
    """Fetch live weather snapshot for any location on Earth."""
    loc = resolve_location(args.location, country_code=args.country)
    if not loc:
        print(f"Error: Could not resolve location '{args.location}'")
        return 1

    weather = get_current_weather(loc)
    print("\n" + "=" * 55)
    print(f"  WEATHER SNAPSHOT: {loc.display_name.upper()}")
    print("=" * 55)
    print(f"  * Observed/Model Time : {weather.timestamp}")
    print(f"  * Temperature         : {weather.temperature_2m:.1f} C")
    print(f"  * Relative Humidity   : {weather.relative_humidity_2m:.0f} %")
    print(f"  * Precipitation       : {weather.precipitation_mm:.2f} mm")
    print(f"  * Wind Speed (10m)    : {weather.wind_speed_10m:.1f} km/h")
    print(f"  * Surface Pressure    : {weather.surface_pressure_hpa:.1f} hPa")
    print(f"  * Elevation           : {loc.elevation_m} m")
    print(f"  * Source              : {weather.source} ({weather.data_kind})")
    print("=" * 55 + "\n")
    return 0


def cmd_forecast(args):
    """Fetch multi-day hourly forecast summary."""
    loc = resolve_location(args.location, country_code=args.country)
    if not loc:
        print(f"Error: Could not resolve location '{args.location}'")
        return 1

    fc = get_hourly_forecast(loc, forecast_days=args.days)
    print(f"\n{args.days}-Day Forecast for {loc.display_name} ({len(fc.times)} hourly steps):")
    print(f"{'Timestamp':<18} | {'Temp (C)':<9} | {'Rain (mm)':<9} | {'Humidity':<8} | {'Wind (km/h)':<10}")
    print("-" * 65)

    # Show sample every 6 hours
    step = 6
    for i in range(0, len(fc.times), step):
        t = fc.times[i]
        temp = fc.temperatures[i]
        rain = fc.precipitations[i]
        hum = fc.humidities[i]
        wind = fc.wind_speeds[i]
        print(f"{t:<18} | {temp:9.1f} | {rain:9.2f} | {hum:7.0f}% | {wind:10.1f}")
    print("-" * 65 + "\n")
    return 0


def cmd_export(args):
    """Export historical data for Google TimesFM or ML models."""
    count = export_from_queries(
        queries=args.locations,
        output_path=args.output,
        start_date=args.start,
        end_date=args.end,
        country_code=args.country,
        verbose=True,
    )
    return 0 if count > 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="data_agent",
        description="Universal Data Agent: Free, open-source global weather scraper and ML dataset generator.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search subparser
    p_search = subparsers.add_parser("search", help="Search any city or village globally")
    p_search.add_argument("query", help="Location name or landmark")
    p_search.add_argument("--count", type=int, default=5, help="Max candidates (default: 5)")
    p_search.add_argument("--country", default=None, help="Filter by ISO 2-letter country code (e.g. NP, US)")
    p_search.set_defaults(func=cmd_search)

    # Live subparser
    p_live = subparsers.add_parser("live", help="Instant real-time weather snapshot")
    p_live.add_argument("location", help="Location name")
    p_live.add_argument("--country", default=None, help="Filter by country code")
    p_live.set_defaults(func=cmd_live)

    # Forecast subparser
    p_fc = subparsers.add_parser("forecast", help="Multi-day hourly forecast series")
    p_fc.add_argument("location", help="Location name")
    p_fc.add_argument("--days", type=int, default=3, help="Forecast horizon in days (default: 3)")
    p_fc.add_argument("--country", default=None, help="Filter by country code")
    p_fc.set_defaults(func=cmd_forecast)

    # Export subparser
    p_exp = subparsers.add_parser("export", help="Export historical weather formatted for Google TimesFM")
    p_exp.add_argument("locations", nargs="+", help="One or more location names")
    p_exp.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    p_exp.add_argument("--end", default="2023-12-31", help="End date YYYY-MM-DD")
    p_exp.add_argument("--output", default="data/exported_weather.csv", help="Output CSV path")
    p_exp.add_argument("--country", default=None, help="Filter by country code")
    p_exp.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
