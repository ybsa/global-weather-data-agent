"""Weather Intelligence Service Layer.
Implements cache-first retrieval with dynamic live fallback and risk assessment.
"""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from .geocoding import resolve_location, search_local_locations
from .models import Location
from .providers import fetch_open_meteo
from .storage import save_records

# WMO Weather interpretation codes
WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def weather_code_to_text(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return WMO_DESCRIPTIONS.get(int(code), f"Code {code}")


def is_record_fresh(received_at_iso: str, max_age_minutes: int = 60) -> bool:
    """Check if a record was received within the allowable age in minutes."""
    try:
        dt = datetime.fromisoformat(received_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now - dt).total_seconds()
        return age_seconds <= (max_age_minutes * 60)
    except Exception:
        return False


def get_current_weather(
    con: sqlite3.Connection,
    query: str,
    force_live: bool = False,
    max_age_minutes: int = 60,
) -> dict:
    """Get current weather for any location worldwide.
    Checks SQLite cache first; fetches live and saves if missing or stale.
    """
    loc = resolve_location(con, query)
    if not loc:
        return {"error": f"Could not find or geocode location '{query}'."}

    # 1. Check local cached current weather
    cached = None
    if not force_live:
        row = con.execute(
            """SELECT w.*, l.name, l.province, l.district, l.latitude, l.longitude, l.elevation_m
               FROM weather_records w
               JOIN locations l USING(location_id)
               WHERE w.location_id = ? AND w.product = 'current'
               ORDER BY w.received_at DESC LIMIT 1""",
            (loc.location_id,),
        ).fetchone()

        if row and is_record_fresh(row["received_at"], max_age_minutes=max_age_minutes):
            cached = dict(row)

    if cached:
        return {
            "status": "cached",
            "location_id": loc.location_id,
            "name": loc.name,
            "province": loc.province,
            "district": loc.district,
            "coordinates": {"latitude": loc.latitude, "longitude": loc.longitude},
            "elevation_m": loc.elevation_m,
            "condition": weather_code_to_text(cached.get("weather_code")),
            "temperature_c": cached.get("temperature_c"),
            "humidity_pct": cached.get("humidity_pct"),
            "precipitation_mm": cached.get("precipitation_mm"),
            "wind_speed_kmh": cached.get("wind_speed_kmh"),
            "weather_code": cached.get("weather_code"),
            "data_kind": cached.get("data_kind"),
            "source": cached.get("source"),
            "valid_at": cached.get("valid_at"),
            "received_at": cached.get("received_at"),
            "is_fresh": True,
        }

    # 2. Live fetch fallback
    try:
        records = fetch_open_meteo(loc)
        save_records(con, records)
        con.commit()

        # Extract current record from newly fetched set
        current_rec = next((r for r in records if r["product"] == "current"), None)
        if not current_rec and records:
            current_rec = records[0]

        return {
            "status": "live_fetched",
            "location_id": loc.location_id,
            "name": loc.name,
            "province": loc.province,
            "district": loc.district,
            "coordinates": {"latitude": loc.latitude, "longitude": loc.longitude},
            "elevation_m": loc.elevation_m,
            "condition": weather_code_to_text(current_rec.get("weather_code") if current_rec else None),
            "temperature_c": current_rec.get("temperature_c") if current_rec else None,
            "humidity_pct": current_rec.get("humidity_pct") if current_rec else None,
            "precipitation_mm": current_rec.get("precipitation_mm") if current_rec else None,
            "wind_speed_kmh": current_rec.get("wind_speed_kmh") if current_rec else None,
            "weather_code": current_rec.get("weather_code") if current_rec else None,
            "data_kind": current_rec.get("data_kind") if current_rec else "model_estimated",
            "source": current_rec.get("source") if current_rec else "open-meteo",
            "valid_at": current_rec.get("valid_at") if current_rec else None,
            "received_at": current_rec.get("received_at") if current_rec else None,
            "is_fresh": True,
        }
    except Exception as exc:
        return {"error": f"Failed to fetch live weather for '{loc.name}': {exc}"}


def get_forecast(
    con: sqlite3.Connection,
    query: str,
    days: int = 3,
    force_live: bool = False,
) -> dict:
    """Get hourly and daily summarized forecast for any location worldwide."""
    loc = resolve_location(con, query)
    if not loc:
        return {"error": f"Could not find or geocode location '{query}'."}

    # Always ensure we have fresh data for forecasts
    if force_live:
        try:
            records = fetch_open_meteo(loc)
            save_records(con, records)
            con.commit()
        except Exception as exc:
            return {"error": f"Live fetch failed: {exc}"}

    # Query latest hourly forecasts from DB
    hours_limit = max(1, min(days * 24, 72))
    rows = con.execute(
        """SELECT valid_at, temperature_c, humidity_pct, precipitation_mm,
                  precipitation_probability_pct, wind_speed_kmh, weather_code
           FROM weather_records
           WHERE location_id = ? AND product = 'hourly'
           ORDER BY received_at DESC, valid_at ASC
           LIMIT ?""",
        (loc.location_id, hours_limit),
    ).fetchall()

    if not rows:
        # Fetch if no hourly records present
        try:
            records = fetch_open_meteo(loc)
            save_records(con, records)
            con.commit()
            rows = con.execute(
                """SELECT valid_at, temperature_c, humidity_pct, precipitation_mm,
                          precipitation_probability_pct, wind_speed_kmh, weather_code
                   FROM weather_records
                   WHERE location_id = ? AND product = 'hourly'
                   ORDER BY received_at DESC, valid_at ASC
                   LIMIT ?""",
                (loc.location_id, hours_limit),
            ).fetchall()
        except Exception as exc:
            return {"error": f"Failed to retrieve forecast: {exc}"}

    hourly_list = []
    total_rain = 0.0
    temps = []

    for r in rows:
        t = r["temperature_c"]
        p = r["precipitation_mm"] or 0.0
        if t is not None:
            temps.append(t)
        total_rain += p
        hourly_list.append({
            "time": r["valid_at"],
            "temp_c": t,
            "rain_mm": p,
            "rain_prob_pct": r["precipitation_probability_pct"],
            "wind_kmh": r["wind_speed_kmh"],
            "condition": weather_code_to_text(r["weather_code"]),
        })

    return {
        "location": loc.name,
        "district": loc.district,
        "province": loc.province,
        "elevation_m": loc.elevation_m,
        "forecast_hours_count": len(hourly_list),
        "summary": {
            "max_temp_c": max(temps) if temps else None,
            "min_temp_c": min(temps) if temps else None,
            "total_precipitation_expected_mm": round(total_rain, 1),
        },
        "hourly_preview": hourly_list[:12],  # first 12 hours preview
    }


def check_weather_risk(con: sqlite3.Connection, query: str) -> dict:
    """Analyze broad weather-risk indicators for the requested location."""
    current = get_current_weather(con, query)
    if "error" in current:
        return current

    forecast = get_forecast(con, query, days=1)
    
    warnings = []
    temp = current.get("temperature_c") or 20.0
    precip = current.get("precipitation_mm") or 0.0
    wind = current.get("wind_speed_kmh") or 0.0
    elevation = current.get("elevation_m") or 0.0
    expected_rain_24h = forecast.get("summary", {}).get("total_precipitation_expected_mm", 0.0)

    # 1. Heavy rainfall & landslide/flash flood risk
    if precip >= 20.0 or expected_rain_24h >= 60.0:
        warnings.append({
            "level": "DANGER",
            "type": "Flash Flood / Landslide Watch",
            "message": f"Intense rainfall expected ({expected_rain_24h} mm in 24h). Check local flood and landslide alerts.",
        })
    elif precip >= 10.0 or expected_rain_24h >= 30.0:
        warnings.append({
            "level": "WARNING",
            "type": "Moderate Rain",
            "message": f"Substantial rainfall ({expected_rain_24h} mm in 24h). Monitor local flood and travel alerts.",
        })

    # 2. Extreme mountain cold / Frost risk
    if temp <= 0.0:
        warnings.append({
            "level": "WARNING",
            "type": "Freezing / Frost Hazard",
            "message": f"Sub-zero temperature ({temp}°C) at {elevation}m elevation. High risk of frost, ice on passes, and hypothermia.",
        })

    # 3. High winds
    if wind >= 50.0:
        warnings.append({
            "level": "DANGER",
            "type": "Severe Gale",
            "message": f"Wind speeds reaching {wind} km/h. Avoid exposed areas and follow local transport advisories.",
        })
    elif wind >= 30.0:
        warnings.append({
            "level": "CAUTION",
            "type": "Gusty Winds",
            "message": f"Brisk winds ({wind} km/h). They may affect local transport and exposed areas.",
        })

    return {
        "location": current.get("name"),
        "district": current.get("district"),
        "province": current.get("province"),
        "elevation_m": elevation,
        "overall_risk": "HIGH" if any(w["level"] == "DANGER" for w in warnings) else ("MEDIUM" if warnings else "LOW"),
        "active_warnings": warnings,
        "disclaimer": "Informational only. Follow your local meteorological and emergency-management authority for official warnings.",
    }
