"""Universal Natural Disaster Data Collector - Model Context Protocol (MCP) Server.
Allows external AI models, prediction pipelines, and dashboards to seamlessly
plug in and retrieve live or historical natural data for any village or city worldwide.
"""
from __future__ import annotations

import json
from typing import Any
from mcp.server.fastmcp import FastMCP

from .archive import fetch_historical_series
from .collector import get_natural_live_report
from .geocoder import resolve_location, search_locations
from .hydrology import get_hydrology
from .seismic import get_recent_earthquakes
from .storage import get_storage

# Initialize FastMCP Server
mcp = FastMCP("Universal Natural Data Collector")


@mcp.tool()
def search_global_locations(query: str, country_code: str = "") -> str:
    """Search for any city, town, village, mountain, or district anywhere on Earth.
    
    Args:
        query: Name of the village, city, district, or landmark (e.g. 'Kathmandu', 'Gorkha', 'Valparaíso', 'Lahaina').
        country_code: Optional ISO 2-letter country code (e.g. 'NP', 'US', 'JP', 'CL').
    """
    results = search_locations(query, count=5, country_code=country_code if country_code else None)
    if not results:
        return f"No location found matching '{query}'"
    return json.dumps([loc.to_dict() for loc in results], indent=2)


@mcp.tool()
def get_live_natural_indicators(location_name: str, country_code: str = "") -> str:
    """Fetch live multi-domain natural data for any village or city in the world.
    
    Returns real-time atmospheric readings (pressure, wind gusts, rain, temp),
    hydrology & soil moisture levels, and nearby USGS earthquake tremors with distance.
    
    Args:
        location_name: Name of village, town, or city.
        country_code: Optional ISO 2-letter country code.
    """
    loc = resolve_location(location_name, country_code=country_code if country_code else None)
    if not loc:
        return json.dumps({"error": f"Could not geocode location '{location_name}'"})

    report = get_natural_live_report(loc, seismic_radius_km=300.0)
    return json.dumps(report.to_dict(), indent=2)


@mcp.tool()
def get_past_natural_time_series(
    location_name: str,
    start_date: str,
    end_date: str,
    country_code: str = "",
) -> str:
    """Fetch historical hourly time-series (temperature, precipitation, wind gusts, pressure, soil moisture).
    Ideal for machine learning prediction model training and anomaly baseline estimation.
    
    Args:
        location_name: Village or city name.
        start_date: Start date in YYYY-MM-DD format (e.g. '2023-01-01').
        end_date: End date in YYYY-MM-DD format (e.g. '2023-01-10').
        country_code: Optional 2-letter country code.
    """
    loc = resolve_location(location_name, country_code=country_code if country_code else None)
    if not loc:
        return json.dumps({"error": f"Could not geocode location '{location_name}'"})

    records = fetch_historical_series(loc, start_date=start_date, end_date=end_date)
    return json.dumps({
        "location": loc.to_dict(),
        "total_records": len(records),
        "sample_records": records[:100],  # Return first 100 samples in tool output
    }, indent=2)


@mcp.tool()
def get_nearby_earthquakes(
    location_name: str,
    radius_km: float = 300.0,
    min_magnitude: float = 1.0,
    country_code: str = "",
) -> str:
    """Fetch real-time USGS earthquake events within radius of any village or city.
    
    Args:
        location_name: Name of village, town, or city.
        radius_km: Search radius in km (default 300km).
        min_magnitude: Minimum magnitude threshold (default 1.0).
        country_code: Optional 2-letter country code.
    """
    loc = resolve_location(location_name, country_code=country_code if country_code else None)
    if not loc:
        return json.dumps({"error": f"Could not geocode location '{location_name}'"})

    events = get_recent_earthquakes(
        loc.latitude, loc.longitude, radius_km=radius_km, min_magnitude=min_magnitude, limit=20
    )
    return json.dumps({
        "location": loc.to_dict(),
        "search_radius_km": radius_km,
        "count": len(events),
        "earthquakes": [e.to_dict() for e in events],
    }, indent=2)


@mcp.tool()
def get_river_and_soil_data(location_name: str, country_code: str = "") -> str:
    """Fetch river discharge rate (m3/s) and multi-layer soil moisture for flood & landslide indicators.
    
    Args:
        location_name: Name of village, town, or city.
        country_code: Optional 2-letter country code.
    """
    loc = resolve_location(location_name, country_code=country_code if country_code else None)
    if not loc:
        return json.dumps({"error": f"Could not geocode location '{location_name}'"})

    hydro = get_hydrology(loc.latitude, loc.longitude)
    return json.dumps({
        "location": loc.to_dict(),
        "hydrology": hydro.to_dict(),
    }, indent=2)


@mcp.tool()
def create_monitored_collection(
    collection_name: str,
    location_names: list[str],
    description: str = "",
) -> str:
    """Create a persistent collection of locations to monitor and generate a secret share code.
    
    Args:
        collection_name: Title of the dataset collection (e.g. 'Pacific Rim Coastal Watch').
        location_names: List of city or village names to track.
        description: Optional notes or description.
    """
    resolved_locations = []
    storage = get_storage()

    for name in location_names:
        loc = resolve_location(name)
        if loc:
            resolved_locations.append(loc)

    if not resolved_locations:
        return json.dumps({"error": "None of the specified locations could be geocoded."})

    record = storage.create_collection(
        title=collection_name,
        locations=resolved_locations,
        description=description,
    )

    # Immediately collect an initial snapshot for all locations
    saved_count = 0
    for loc in resolved_locations:
        report = get_natural_live_report(loc)
        storage.save_live_report(record.secret_code, report)
        saved_count += 1

    return json.dumps({
        "status": "created",
        "secret_code": record.secret_code,
        "collection_id": record.collection_id,
        "title": record.title,
        "locations_count": len(resolved_locations),
        "snapshots_saved": saved_count,
        "share_instructions": f"Share secret_code '{record.secret_code}' or query /api/share/{record.secret_code}",
    }, indent=2)


@mcp.tool()
def get_shared_collection_data(secret_code: str) -> str:
    """Retrieve saved observations and latest natural indicators using a secret share code.
    
    Args:
        secret_code: Secret share code (e.g. 'NAT-8F29A4').
    """
    storage = get_storage()
    coll = storage.get_collection_by_secret(secret_code)
    if not coll:
        return json.dumps({"error": f"No collection found matching secret code: {secret_code}"})

    obs = storage.get_observations(secret_code, limit=50)
    return json.dumps({
        "collection": coll.to_dict(),
        "total_saved_snapshots": coll.record_count,
        "recent_observations": obs,
    }, indent=2)


def main():
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
