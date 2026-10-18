from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
  location_id TEXT PRIMARY KEY, name TEXT NOT NULL, province TEXT, district TEXT,
  latitude REAL NOT NULL, longitude REAL NOT NULL, elevation_m REAL,
  country_code TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS weather_records (
  id INTEGER PRIMARY KEY, location_id TEXT NOT NULL REFERENCES locations(location_id),
  data_kind TEXT NOT NULL CHECK(data_kind IN ('observed','forecast','model_estimated','derived')),
  source TEXT NOT NULL, product TEXT NOT NULL, valid_at TEXT NOT NULL, received_at TEXT NOT NULL,
  temperature_c REAL, humidity_pct REAL, precipitation_mm REAL,
  precipitation_probability_pct REAL, wind_speed_kmh REAL, weather_code INTEGER,
  raw_payload TEXT NOT NULL,
  UNIQUE(location_id, source, product, valid_at, received_at)
);
CREATE INDEX IF NOT EXISTS idx_weather_lookup ON weather_records(location_id, valid_at DESC);
"""


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save_location(con, loc) -> None:
    country_code = getattr(loc, "country_code", "")
    con.execute("""INSERT INTO locations
      (location_id, name, province, district, latitude, longitude, elevation_m, country_code)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(location_id) DO UPDATE SET name=excluded.name, province=excluded.province,
      district=excluded.district, latitude=excluded.latitude, longitude=excluded.longitude,
      elevation_m=excluded.elevation_m, country_code=excluded.country_code""",
      (loc.location_id, loc.name, loc.province, loc.district, loc.latitude,
       loc.longitude, loc.elevation_m, country_code))


def save_records(con, records: list[dict]) -> int:
    fields = list(records[0]) if records else []
    if not fields:
        return 0
    placeholders = ",".join("?" for _ in fields)
    before = con.total_changes
    con.executemany(f"INSERT OR IGNORE INTO weather_records ({','.join(fields)}) VALUES ({placeholders})",
                    [tuple(record[field] for field in fields) for record in records])
    return con.total_changes - before

