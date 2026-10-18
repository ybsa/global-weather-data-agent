"""Agent Tools Registry & Dispatcher.
Defines standard OpenAI-compatible function schemas and maps them to Python executables.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .geocoding import search_local_locations
from .service import check_weather_risk, get_current_weather, get_forecast

# Standard OpenAI / universal function calling schemas
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Fetch current live weather conditions for a city, town, village, or named place worldwide. Checks local cache first and automatically fetches live data if missing or stale.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "A place name, preferably including a country when it could be ambiguous (for example, 'London, UK').",
                    },
                    "force_live": {
                        "type": "boolean",
                        "description": "If true, bypasses the local SQLite cache and forces a fresh live API fetch.",
                        "default": False,
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Get a 24 to 72 hour hourly forecast, expected rainfall, temperature ranges, and wind conditions for any location worldwide.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "A place name, preferably including a country when it could be ambiguous.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of forecast days (1 to 3). Default is 3.",
                        "default": 3,
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_weather_risk",
            "description": "Analyze broad weather-risk indicators for a location, including heavy rain, freezing temperatures, and high winds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "A place name, preferably including a country when it could be ambiguous.",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_locations",
            "description": "Search the local cached locations database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Partial name of a previously cached place or administrative area.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def execute_tool(con: sqlite3.Connection, tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool by name and return a JSON string result."""
    try:
        if tool_name == "get_current_weather":
            location = arguments.get("location", "")
            force_live = bool(arguments.get("force_live", False))
            result = get_current_weather(con, query=location, force_live=force_live)
            return json.dumps(result, indent=2)

        elif tool_name == "get_forecast":
            location = arguments.get("location", "")
            days = int(arguments.get("days", 3))
            result = get_forecast(con, query=location, days=days)
            return json.dumps(result, indent=2)

        elif tool_name == "check_weather_risk":
            location = arguments.get("location", "")
            result = check_weather_risk(con, query=location)
            return json.dumps(result, indent=2)

        elif tool_name == "search_locations":
            query = arguments.get("query", "")
            matches = search_local_locations(con, query=query)
            res = [
                {
                    "name": loc.name,
                    "district": loc.district,
                    "province": loc.province,
                    "elevation_m": loc.elevation_m,
                    "location_id": loc.location_id,
                }
                for loc in matches
            ]
            return json.dumps(res, indent=2)

        else:
            return json.dumps({"error": f"Unknown tool '{tool_name}'"})

    except Exception as exc:
        return json.dumps({"error": f"Tool execution failed for '{tool_name}': {str(exc)}"})
