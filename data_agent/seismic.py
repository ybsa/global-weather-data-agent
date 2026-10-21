"""Universal Seismic Data Collector.
Pulls real-time and historical earthquake event feeds from USGS (United States Geological Survey).
No API keys required. Works for any coordinate / village / city worldwide.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import EarthquakeEvent

USGS_QUERY_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
DEFAULT_USER_AGENT = "Universal-Natural-Data-Agent/1.0"


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points on Earth in kilometers."""
    r = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class SeismicCollector:
    """Collects real-time and historical seismic events from USGS."""

    def __init__(self, opener=urlopen):
        self.opener = opener

    def _request_json(self, url: str) -> dict:
        req = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with self.opener(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_recent_earthquakes(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 300.0,
        min_magnitude: float = 1.0,
        limit: int = 25,
    ) -> list[EarthquakeEvent]:
        """Fetch recent earthquake events within radius of a target location.
        
        Args:
            latitude: Center point latitude.
            longitude: Center point longitude.
            radius_km: Search circle radius in km (default 300km).
            min_magnitude: Minimum magnitude threshold (default 1.0).
            limit: Maximum events to return (default 25).
        """
        params = {
            "format": "geojson",
            "latitude": latitude,
            "longitude": longitude,
            "maxradiuskm": min(max(10, radius_km), 20000),
            "minmagnitude": min_magnitude,
            "limit": limit,
            "orderby": "time",
        }
        url = f"{USGS_QUERY_API}?{urlencode(params)}"
        try:
            payload = self._request_json(url)
        except Exception:
            return []

        features = payload.get("features", [])
        events: list[EarthquakeEvent] = []

        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0, 0.0])
            eq_lon = coords[0] if len(coords) > 0 else 0.0
            eq_lat = coords[1] if len(coords) > 1 else 0.0
            eq_depth = coords[2] if len(coords) > 2 else 0.0

            time_ms = props.get("time") or 0
            time_iso = (
                datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).isoformat()
                if time_ms
                else ""
            )

            dist_km = haversine_distance_km(latitude, longitude, eq_lat, eq_lon)

            events.append(
                EarthquakeEvent(
                    event_id=str(feat.get("id", "")),
                    magnitude=float(props.get("mag") or 0.0),
                    place=str(props.get("place") or "Unknown location"),
                    timestamp=time_iso,
                    latitude=eq_lat,
                    longitude=eq_lon,
                    depth_km=float(eq_depth or 0.0),
                    distance_km=round(dist_km, 2),
                    tsunami_alert=int(props.get("tsunami") or 0),
                    alert_level=props.get("alert"),
                    felt_reports=int(props.get("felt") or 0),
                    usgs_url=str(props.get("url") or ""),
                )
            )

        # Sort by proximity or time
        events.sort(key=lambda x: x.distance_km)
        return events

    def fetch_historical_earthquakes(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        radius_km: float = 500.0,
        min_magnitude: float = 2.5,
        limit: int = 200,
    ) -> list[EarthquakeEvent]:
        """Fetch historical earthquake events for ML model training and baseline analysis."""
        params = {
            "format": "geojson",
            "latitude": latitude,
            "longitude": longitude,
            "maxradiuskm": min(max(10, radius_km), 20000),
            "starttime": start_date,
            "endtime": end_date,
            "minmagnitude": min_magnitude,
            "limit": limit,
            "orderby": "time",
        }
        url = f"{USGS_QUERY_API}?{urlencode(params)}"
        try:
            payload = self._request_json(url)
        except Exception:
            return []

        features = payload.get("features", [])
        events: list[EarthquakeEvent] = []

        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0, 0.0])
            eq_lon = coords[0] if len(coords) > 0 else 0.0
            eq_lat = coords[1] if len(coords) > 1 else 0.0
            eq_depth = coords[2] if len(coords) > 2 else 0.0

            time_ms = props.get("time") or 0
            time_iso = (
                datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).isoformat()
                if time_ms
                else ""
            )

            dist_km = haversine_distance_km(latitude, longitude, eq_lat, eq_lon)

            events.append(
                EarthquakeEvent(
                    event_id=str(feat.get("id", "")),
                    magnitude=float(props.get("mag") or 0.0),
                    place=str(props.get("place") or "Unknown location"),
                    timestamp=time_iso,
                    latitude=eq_lat,
                    longitude=eq_lon,
                    depth_km=float(eq_depth or 0.0),
                    distance_km=round(dist_km, 2),
                    tsunami_alert=int(props.get("tsunami") or 0),
                    alert_level=props.get("alert"),
                    felt_reports=int(props.get("felt") or 0),
                    usgs_url=str(props.get("url") or ""),
                )
            )

        return events


_default_seismic = SeismicCollector()


def get_recent_earthquakes(
    latitude: float,
    longitude: float,
    radius_km: float = 300.0,
    min_magnitude: float = 1.0,
    limit: int = 25,
) -> list[EarthquakeEvent]:
    return _default_seismic.fetch_recent_earthquakes(
        latitude, longitude, radius_km=radius_km, min_magnitude=min_magnitude, limit=limit
    )
