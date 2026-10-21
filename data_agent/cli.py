"""Universal Natural Data Agent CLI.
Command-line interface for global geocoding, live natural data collection,
seismic feeds, river discharge, ML exports, FastAPI server, and MCP protocol.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure Windows terminal prints international names (e.g. 'Valparaíso') instead of crashing or showing '�'
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .archive import fetch_historical_series
from .collector import get_current_weather, get_hourly_forecast, get_natural_live_report
from .exporter import export_from_queries, export_ml_dataset
from .geocoder import GeocodingError, resolve_location, search_locations
from .hydrology import get_hydrology
from .models import LocationInfo
from .seismic import get_recent_earthquakes
from .storage import get_storage


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
    """Fetch live natural indicators report for any location on Earth."""
    loc = resolve_location(args.location, country_code=args.country)
    if not loc:
        print(f"Error: Could not resolve location '{args.location}'")
        return 1

    report = get_natural_live_report(loc, seismic_radius_km=args.radius)
    atmo = report.atmosphere
    hydro = report.hydrology
    eqs = report.recent_earthquakes

    print("\n" + "=" * 65)
    print(f"  LIVE NATURAL DATA REPORT: {loc.display_name.upper()}")
    print("=" * 65)
    print(f"  * Observation Time      : {atmo.timestamp}")
    print(f"  * Coordinates           : {loc.latitude:.4f}°, {loc.longitude:.4f}° (Elev: {loc.elevation_m}m)")
    print("-" * 65)
    print("  [ATMOSPHERE & WEATHER]")
    print(f"  * Temperature           : {atmo.temperature_2m:.1f} °C")
    print(f"  * Relative Humidity     : {atmo.relative_humidity_2m:.0f} %")
    print(f"  * Precipitation         : {atmo.precipitation_mm:.2f} mm")
    print(f"  * Wind Speed (10m)      : {atmo.wind_speed_10m:.1f} km/h (Gusts: {atmo.wind_gusts_10m:.1f} km/h)")
    print(f"  * Surface Pressure      : {atmo.surface_pressure_hpa:.1f} hPa")
    print("-" * 65)
    print("  [HYDROLOGY & SOIL MOISTURE]")
    if hydro.river_discharge_m3s is not None:
        print(f"  * River Discharge       : {hydro.river_discharge_m3s:.2f} m³/s (7-day max: {hydro.river_discharge_max_7d} m³/s)")
    else:
        print("  * River Discharge       : N/A (no major river basin in cell)")
    if hydro.soil_moisture_0_to_1cm is not None:
        print(f"  * Surface Soil Moisture : {hydro.soil_moisture_0_to_1cm:.4f} m³/m³")
        print(f"  * Root Zone (27-81cm)   : {hydro.soil_moisture_27_to_81cm:.4f} m³/m³")
    print("-" * 65)
    print(f"  [SEISMIC ACTIVITY (USGS within {args.radius} km)]")
    if eqs:
        print(f"  * Detected Events       : {len(eqs)}")
        print(f"  * Closest Tremor        : M {eqs[0].magnitude:.1f} at {eqs[0].distance_km} km ({eqs[0].place})")
        print(f"  * Max Magnitude         : M {max([e.magnitude for e in eqs]):.1f}")
    else:
        print(f"  * Seismic Status        : Quiet (no M1.0+ events recorded)")
    print("=" * 65 + "\n")
    return 0


def cmd_seismic(args):
    """Fetch USGS earthquake events around a location."""
    loc = resolve_location(args.location, country_code=args.country)
    if not loc:
        print(f"Error: Location '{args.location}' not found")
        return 1

    events = get_recent_earthquakes(loc.latitude, loc.longitude, radius_km=args.radius, min_magnitude=args.min_mag)
    print(f"\nUSGS Seismic Feed for {loc.display_name} (Radius: {args.radius} km, Min M{args.min_mag}):")
    print("-" * 75)
    if not events:
        print("No earthquake events found.")
        return 0

    for i, e in enumerate(events[:args.limit], 1):
        print(f"[{i}] M {e.magnitude:.1f} | {e.distance_km:.1f} km away | Depth: {e.depth_km} km | {e.place}")
        print(f"    Time: {e.timestamp} | USGS: {e.usgs_url}")
    print("-" * 75)
    return 0


def cmd_collect(args):
    """Create a persistent collection with a secret share code."""
    storage = get_storage()
    resolved = []
    for q in args.locations:
        loc = resolve_location(q)
        if loc:
            resolved.append(loc)
            print(f"✓ Resolved: {loc.display_name}")
        else:
            print(f"✗ Failed to resolve: {q}")

    if not resolved:
        print("Error: No locations resolved.")
        return 1

    rec = storage.create_collection(
        title=args.name,
        locations=resolved,
        description=args.desc or "",
    )

    # Save initial snapshot
    for loc in resolved:
        rep = get_natural_live_report(loc)
        storage.save_live_report(rec.secret_code, rep)

    print("\n" + "=" * 60)
    print(f"  COLLECTION CREATED: {rec.title}")
    print("=" * 60)
    print(f"  Secret Share Code : {rec.secret_code}")
    print(f"  Monitored Places  : {len(resolved)}")
    print(f"  Shareable API     : /api/share/{rec.secret_code}")
    print(f"  CSV Download URL  : /api/share/{rec.secret_code}/download?format=csv")
    print("=" * 60 + "\n")
    return 0


def cmd_serve(args):
    """Start the FastAPI REST server and web dashboard."""
    import uvicorn
    print(f"\n🚀 Launching Natural Disaster Data Collector Server on http://{args.host}:{args.port}")
    print(f"👉 Web Dashboard : http://localhost:{args.port}/")
    print(f"👉 API Swagger   : http://localhost:{args.port}/docs")
    print(f"👉 Health Check  : http://localhost:{args.port}/api/health\n")
    uvicorn.run("data_agent.api:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_mcp(args):
    """Start the Model Context Protocol (MCP) server over stdio."""
    from .mcp_server import main as run_mcp
    run_mcp()
    return 0


def cmd_export(args):
    """Export historical ML dataset for one or more locations."""
    output_path = Path(args.output)
    print(f"\nResolving {len(args.locations)} location(s)...")
    res = export_from_queries(
        args.locations,
        start_date=args.start,
        end_date=args.end,
        output_file=output_path,
        country_code=args.country,
    )
    if "error" in res:
        print(f"Error: {res['error']}")
        return 1

    print("\n" + "=" * 60)
    print("  HISTORICAL DATASET EXPORT COMPLETE")
    print("=" * 60)
    print(f"  * Total Records  : {res['total_records']}")
    print(f"  * Output CSV     : {res['output_file']}")
    print(f"  * Start Date     : {args.start}")
    print(f"  * End Date       : {args.end}")
    print("=" * 60 + "\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="data-agent",
        description="Universal Natural Disaster Data Collector & ML Exporter (Zero API Keys)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Search
    p_search = subparsers.add_parser("search", help="Search for any village or city globally")
    p_search.add_argument("query", help="Name of location")
    p_search.add_argument("--count", type=int, default=5, help="Max candidates")
    p_search.add_argument("--country", default=None, help="2-letter ISO country code")
    p_search.set_defaults(func=cmd_search)

    # Live
    p_live = subparsers.add_parser("live", help="Fetch live natural vitals (atmosphere, river, soil, seismic)")
    p_live.add_argument("location", help="Name of location")
    p_live.add_argument("--country", default=None, help="2-letter ISO country code")
    p_live.add_argument("--radius", type=float, default=300.0, help="Seismic radius in km")
    p_live.set_defaults(func=cmd_live)

    # Seismic
    p_seismic = subparsers.add_parser("seismic", help="Fetch USGS earthquakes around a location")
    p_seismic.add_argument("location", help="Location name")
    p_seismic.add_argument("--country", default=None, help="2-letter country code")
    p_seismic.add_argument("--radius", type=float, default=300.0, help="Radius in km")
    p_seismic.add_argument("--min-mag", type=float, default=1.0, help="Min magnitude")
    p_seismic.add_argument("--limit", type=int, default=15, help="Max items")
    p_seismic.set_defaults(func=cmd_seismic)

    # Collect
    p_collect = subparsers.add_parser("collect", help="Create a persistent collection with a secret share code")
    p_collect.add_argument("locations", nargs="+", help="One or more locations")
    p_collect.add_argument("--name", default="Natural Indicators Collection", help="Collection title")
    p_collect.add_argument("--desc", default="", help="Description")
    p_collect.set_defaults(func=cmd_collect)

    # Export
    p_export = subparsers.add_parser("export", help="Export historical dataset for machine learning")
    p_export.add_argument("locations", nargs="+", help="One or more locations")
    p_export.add_argument("--start", default="2023-01-01", help="Start date YYYY-MM-DD")
    p_export.add_argument("--end", default="2023-12-31", help="End date YYYY-MM-DD")
    p_export.add_argument("--output", default="datasets/natural_history.csv", help="Output CSV path")
    p_export.add_argument("--country", default=None, help="2-letter ISO country code")
    p_export.set_defaults(func=cmd_export)

    # Serve
    p_serve = subparsers.add_parser("serve", help="Run FastAPI server and interactive web dashboard")
    p_serve.add_argument("--host", default="0.0.0.0", help="Host address")
    p_serve.add_argument("--port", type=int, default=8000, help="Port number")
    p_serve.set_defaults(func=cmd_serve)

    # MCP
    p_mcp = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) server")
    p_mcp.set_defaults(func=cmd_mcp)

    args = parser.parse_args()
    try:
        return args.func(args)
    except GeocodingError as exc:
        print(f"Error: could not reach the geocoding service ({exc}). Check your connection and try again.")
        return 2


if __name__ == "__main__":
    sys.exit(main() or 0)
