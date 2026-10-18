from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
import sys

from .agent import WeatherAgent, direct_weather_fallback
from .models import Location
from .providers import fetch_open_meteo
from .service import check_weather_risk, get_current_weather
from .storage import connect, save_location, save_records


def load_locations(path):
    with open(path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            yield Location(
                row["location_id"],
                row["name"],
                row["province"],
                row["district"],
                float(row["latitude"]),
                float(row["longitude"]),
                float(row["elevation_m"]),
            )


def collect(args):
    con = connect(args.database)
    totals = {"locations": 0, "records": 0, "failed": 0}
    for loc in load_locations(args.locations):
        save_location(con, loc)
        try:
            records = fetch_open_meteo(loc)
            totals["records"] += save_records(con, records)
            totals["locations"] += 1
        except Exception as exc:  # continue collecting other locations; errors are visible
            totals["failed"] += 1
            print(f"FAILED {loc.location_id}: {exc}")
    con.commit()
    print(f"Collected {totals['records']} records for {totals['locations']} locations; failures: {totals['failed']}")


def latest(args):
    con = connect(args.database)
    rows = con.execute(
        """SELECT l.name, w.data_kind, w.source, w.product, w.valid_at, w.received_at,
           w.temperature_c, w.humidity_pct, w.precipitation_mm, w.precipitation_probability_pct, w.wind_speed_kmh
           FROM weather_records w JOIN locations l USING(location_id)
           WHERE w.location_id = ? ORDER BY w.received_at DESC, w.valid_at ASC LIMIT ?""",
        (args.location, args.limit),
    ).fetchall()
    for row in rows:
        print(dict(row))


def coverage(args):
    con = connect(args.database)
    now = datetime.now(timezone.utc)
    rows = con.execute(
        """SELECT l.province, COUNT(DISTINCT l.location_id) AS configured_locations,
           COUNT(w.id) AS records, MAX(w.received_at) AS newest_received_at
           FROM locations l LEFT JOIN weather_records w USING(location_id)
           GROUP BY l.province ORDER BY l.province"""
    ).fetchall()
    for row in rows:
        item = dict(row)
        item["checked_at_utc"] = now.isoformat()
        print(item)


def live(args):
    """Fetch current live or cached weather for any place worldwide."""
    con = connect(args.database)
    res = get_current_weather(con, query=args.location, force_live=args.force)
    if "error" in res:
        print(f"Error: {res['error']}")
        sys.exit(1)

    print(json.dumps(res, indent=2))


def risk(args):
    """Assess weather hazard risk for a location."""
    con = connect(args.database)
    res = check_weather_risk(con, query=args.location)
    print(json.dumps(res, indent=2))


def ask(args):
    """Run universal model-agnostic AI agent with autonomous tool calling."""
    con = connect(args.database)
    
    agent = WeatherAgent(
        con=con,
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
    )

    print(f"WeatherAgent running with model: {agent.model} (endpoint: {agent.base_url})")
    print(f"User Query: {args.prompt}\n")

    try:
        response = agent.run(args.prompt, verbose=True)
        print("\n" + response)
    except ConnectionError as err:
        print(f"\n[Notice] {err}")
        print("\n[Falling back to direct tool-based answer without LLM]:\n")
        print(direct_weather_fallback(con, query=args.prompt))


def main():
    parser = argparse.ArgumentParser(description="Global Weather Data Agent — live weather and forecast collection")
    parser.add_argument("--database", default="data/weather.sqlite3")
    sub = parser.add_subparsers(required=True)

    # Ingestion & Database commands
    c = sub.add_parser("collect", help="Batch collect configured locations into SQLite")
    c.add_argument("--locations", default="config/locations.csv")
    c.set_defaults(func=collect)

    l = sub.add_parser("latest", help="Show latest records for a known location_id")
    l.add_argument("--location", required=True)
    l.add_argument("--limit", type=int, default=6)
    l.set_defaults(func=latest)

    cov = sub.add_parser("coverage", help="Check database freshness and regional coverage")
    cov.set_defaults(func=coverage)

    # Village & Live lookup commands
    liv = sub.add_parser("live", help="Instant live or cached weather for any place worldwide")
    liv.add_argument("location", help="Place name; include a country for ambiguous names (e.g. 'London, UK')")
    liv.add_argument("--force", action="store_true", help="Force live API fetch instead of cache")
    liv.set_defaults(func=live)

    r = sub.add_parser("risk", help="Check weather hazard/flood/cold risks for a location")
    r.add_argument("location", help="Location name")
    r.set_defaults(func=risk)

    # Autonomous AI Agent command
    a = sub.add_parser("ask", help="Ask the AI agent any weather question (autonomous tool calling)")
    a.add_argument("prompt", help="Question in English or Nepali")
    a.add_argument("--model", help="AI Model name (e.g. llama3.2, gemini-1.5-flash, gpt-4o-mini)")
    a.add_argument("--base-url", help="OpenAI-compatible base URL (e.g. http://localhost:11434/v1)")
    a.add_argument("--api-key", help="API Key for cloud LLMs (Groq, Gemini, OpenAI)")
    a.set_defaults(func=ask)

    args = parser.parse_args()
    args.func(args)
