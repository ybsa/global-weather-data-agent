"""Universal Persistent Storage & Secret Sharing Engine.
Stores monitored locations, periodic environmental snapshots, and generates secure share codes.
Uses SQLite for instant zero-dependency portability and speed.
"""
from __future__ import annotations

import csv
import io
import json
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import CollectionRecord, LocationInfo, NaturalLiveReport

DEFAULT_DB_PATH = Path(os.environ.get("NATURAL_DATA_DB", Path(__file__).resolve().parent.parent / "natural_data.db"))


class StorageEngine:
    """Manages SQLite storage for natural data collections and snapshots."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return closing(conn)

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS collections (
                    collection_id TEXT PRIMARY KEY,
                    secret_code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    locations_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_id TEXT NOT NULL,
                    secret_code TEXT NOT NULL,
                    location_id TEXT NOT NULL,
                    location_name TEXT NOT NULL,
                    country_code TEXT,
                    latitude REAL,
                    longitude REAL,
                    elevation_m REAL,
                    timestamp TEXT NOT NULL,
                    temperature_2m REAL,
                    relative_humidity_2m REAL,
                    precipitation_mm REAL,
                    wind_speed_10m REAL,
                    wind_gusts_10m REAL,
                    surface_pressure_hpa REAL,
                    river_discharge_m3s REAL,
                    soil_moisture_surface REAL,
                    closest_earthquake_distance_km REAL,
                    max_earthquake_mag REAL,
                    raw_json TEXT NOT NULL,
                    FOREIGN KEY (collection_id) REFERENCES collections(collection_id)
                );

                CREATE INDEX IF NOT EXISTS idx_obs_secret ON observations(secret_code);
                CREATE INDEX IF NOT EXISTS idx_obs_loc_time ON observations(location_id, timestamp);
            """)

    @staticmethod
    def generate_secret_code(prefix: str = "NAT") -> str:
        """Generate a user-friendly, high-entropy secret code (e.g. 'NAT-8F29A4')."""
        token = secrets.token_hex(4).upper()
        return f"{prefix}-{token}"

    def create_collection(
        self,
        title: str,
        locations: list[dict[str, Any] | LocationInfo],
        description: str = "",
        custom_secret_code: str | None = None,
    ) -> CollectionRecord:
        """Create a new dataset collection with a shareable secret code."""
        coll_id = f"col_{secrets.token_hex(6)}"
        secret_code = custom_secret_code.strip() if custom_secret_code else self.generate_secret_code()
        now = datetime.now(timezone.utc).isoformat()

        serialized_locations = []
        for loc in locations:
            if isinstance(loc, LocationInfo):
                serialized_locations.append(loc.to_dict())
            elif isinstance(loc, dict):
                serialized_locations.append(loc)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO collections (collection_id, secret_code, title, description, locations_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coll_id,
                    secret_code,
                    title.strip() or "Untitled Natural Data Collection",
                    description.strip(),
                    json.dumps(serialized_locations),
                    now,
                    now,
                ),
            )

        return CollectionRecord(
            collection_id=coll_id,
            secret_code=secret_code,
            title=title,
            description=description,
            locations=serialized_locations,
            created_at=now,
            updated_at=now,
            record_count=0,
        )

    def get_collection_by_secret(self, secret_code: str) -> CollectionRecord | None:
        """Find collection record by secret share code or collection_id."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM collections WHERE secret_code = ? OR collection_id = ?",
                (secret_code, secret_code),
            ).fetchone()
            if not row:
                return None

            count_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM observations WHERE collection_id = ?",
                (row["collection_id"],),
            ).fetchone()

            locations = json.loads(row["locations_json"])
            return CollectionRecord(
                collection_id=row["collection_id"],
                secret_code=row["secret_code"],
                title=row["title"],
                description=row["description"],
                locations=locations,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                record_count=count_row["cnt"] if count_row else 0,
            )

    def list_collections(self, limit: int = 50) -> list[CollectionRecord]:
        """List active data collections."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.*, (SELECT COUNT(*) FROM observations o WHERE o.collection_id = c.collection_id) as cnt
                FROM collections c
                ORDER BY c.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            records = []
            for row in rows:
                records.append(
                    CollectionRecord(
                        collection_id=row["collection_id"],
                        secret_code=row["secret_code"],
                        title=row["title"],
                        description=row["description"],
                        locations=json.loads(row["locations_json"]),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        record_count=row["cnt"],
                    )
                )
            return records

    def add_location_to_collection(self, secret_code_or_id: str, location: LocationInfo) -> bool:
        """Add a location to a collection's monitored list if not already present.
        Returns True if added, False if it was already tracked.
        """
        coll = self.get_collection_by_secret(secret_code_or_id)
        if not coll:
            raise ValueError(f"Collection not found for code: {secret_code_or_id}")

        for existing in coll.locations:
            same_id = existing.get("location_id") == location.location_id
            same_spot = (
                abs(float(existing.get("latitude", 999.0)) - location.latitude) < 1e-4
                and abs(float(existing.get("longitude", 999.0)) - location.longitude) < 1e-4
            )
            if same_id or same_spot:
                return False

        new_locations = list(coll.locations) + [location.to_dict()]
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE collections SET locations_json = ?, updated_at = ? WHERE collection_id = ?",
                (json.dumps(new_locations), now, coll.collection_id),
            )
        return True

    def save_live_report(
        self,
        secret_code_or_id: str,
        report: NaturalLiveReport | dict[str, Any],
    ) -> int:
        """Save a live natural report snapshot into the collection."""
        coll = self.get_collection_by_secret(secret_code_or_id)
        if not coll:
            raise ValueError(f"Collection not found for code: {secret_code_or_id}")

        if isinstance(report, NaturalLiveReport):
            r_dict = report.to_dict()
        else:
            r_dict = report

        loc = r_dict.get("location", {})
        atmo = r_dict.get("atmosphere", {})
        hydro = r_dict.get("hydrology", {})

        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO observations (
                    collection_id, secret_code, location_id, location_name, country_code,
                    latitude, longitude, elevation_m, timestamp,
                    temperature_2m, relative_humidity_2m, precipitation_mm,
                    wind_speed_10m, wind_gusts_10m, surface_pressure_hpa,
                    river_discharge_m3s, soil_moisture_surface,
                    closest_earthquake_distance_km, max_earthquake_mag, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    coll.collection_id,
                    coll.secret_code,
                    loc.get("location_id", ""),
                    loc.get("name", "Unknown"),
                    loc.get("country_code", ""),
                    float(loc.get("latitude", 0.0)),
                    float(loc.get("longitude", 0.0)),
                    float(loc.get("elevation_m", 0.0)),
                    r_dict.get("timestamp") or now,
                    atmo.get("temperature_2m"),
                    atmo.get("relative_humidity_2m"),
                    atmo.get("precipitation_mm"),
                    atmo.get("wind_speed_10m"),
                    atmo.get("wind_gusts_10m"),
                    atmo.get("surface_pressure_hpa"),
                    hydro.get("river_discharge_m3s"),
                    hydro.get("soil_moisture_0_to_1cm"),
                    r_dict.get("closest_earthquake_distance_km"),
                    r_dict.get("max_earthquake_magnitude_nearby"),
                    json.dumps(r_dict),
                ),
            )
            # update updated_at
            conn.execute(
                "UPDATE collections SET updated_at = ? WHERE collection_id = ?",
                (now, coll.collection_id),
            )
            return cur.lastrowid

    def get_observations(
        self,
        secret_code: str,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Retrieve recent saved observations for a collection."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM observations
                WHERE secret_code = ? OR collection_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (secret_code, secret_code, limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def export_csv(self, secret_code: str) -> str:
        """Export collection observations as CSV formatted string."""
        obs = self.get_observations(secret_code, limit=5000)
        if not obs:
            return ""

        output = io.StringIO()
        fieldnames = [
            "id", "collection_id", "location_name", "country_code",
            "latitude", "longitude", "elevation_m", "timestamp",
            "temperature_2m", "relative_humidity_2m", "precipitation_mm",
            "wind_speed_10m", "wind_gusts_10m", "surface_pressure_hpa",
            "river_discharge_m3s", "soil_moisture_surface",
            "closest_earthquake_distance_km", "max_earthquake_mag"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in reversed(obs):
            writer.writerow(row)
        return output.getvalue()


_default_storage = StorageEngine()

def get_storage() -> StorageEngine:
    return _default_storage
