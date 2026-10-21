"""Universal Data Agent Data Models.
Standardized location and multi-domain natural record structures for global use.
Covers atmospheric, seismic, hydrology/flood, and soil indicators.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class LocationInfo:
    location_id: str
    name: str
    country: str
    country_code: str
    admin1: str = ""  # State, Province, or Prefecture
    admin2: str = ""  # District, County, or Canton
    admin3: str = ""  # Municipality, Gaunpalika, or Ward
    latitude: float = 0.0
    longitude: float = 0.0
    elevation_m: float = 0.0
    timezone: str = "UTC"

    @property
    def display_name(self) -> str:
        parts = [self.name]
        if self.admin2 and self.admin2 != self.name:
            parts.append(self.admin2)
        if self.admin1 and self.admin1 not in (self.name, self.admin2):
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["display_name"] = self.display_name
        return d


@dataclass
class CurrentWeather:
    location: LocationInfo
    timestamp: str
    temperature_2m: float
    relative_humidity_2m: float
    precipitation_mm: float
    wind_speed_10m: float
    surface_pressure_hpa: float
    wind_gusts_10m: float = 0.0
    cloud_cover_pct: float = 0.0
    weather_code: int = 0
    is_day: int = 1
    source: str = "open-meteo"
    data_kind: str = "model-estimated"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["location"] = self.location.to_dict()
        return d


@dataclass
class HourlyForecast:
    location: LocationInfo
    times: list[str] = field(default_factory=list)
    temperatures: list[float] = field(default_factory=list)
    humidities: list[float] = field(default_factory=list)
    precipitations: list[float] = field(default_factory=list)
    wind_speeds: list[float] = field(default_factory=list)
    pressures: list[float] = field(default_factory=list)
    wind_gusts: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["location"] = self.location.to_dict()
        return d


@dataclass
class EarthquakeEvent:
    event_id: str
    magnitude: float
    place: str
    timestamp: str
    latitude: float
    longitude: float
    depth_km: float
    distance_km: float
    tsunami_alert: int = 0
    alert_level: str | None = None
    felt_reports: int = 0
    usgs_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HydrologySnapshot:
    river_discharge_m3s: float | None = None
    river_discharge_mean_7d: float | None = None
    river_discharge_max_7d: float | None = None
    soil_moisture_0_to_1cm: float | None = None
    soil_moisture_1_to_3cm: float | None = None
    soil_moisture_9_to_27cm: float | None = None
    soil_moisture_27_to_81cm: float | None = None
    surface_runoff_mm: float | None = None
    timestamp: str = ""
    source: str = "open-meteo-flood-and-land"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NaturalLiveReport:
    """Consolidated multi-domain live environmental snapshot for any village/city on Earth."""
    location: LocationInfo
    timestamp: str
    atmosphere: CurrentWeather
    hydrology: HydrologySnapshot
    recent_earthquakes: list[EarthquakeEvent] = field(default_factory=list)
    closest_earthquake_distance_km: float | None = None
    max_earthquake_magnitude_nearby: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "timestamp": self.timestamp,
            "atmosphere": self.atmosphere.to_dict(),
            "hydrology": self.hydrology.to_dict(),
            "recent_earthquakes": [eq.to_dict() for eq in self.recent_earthquakes],
            "closest_earthquake_distance_km": self.closest_earthquake_distance_km,
            "max_earthquake_magnitude_nearby": self.max_earthquake_magnitude_nearby,
        }


@dataclass
class CollectionRecord:
    collection_id: str
    secret_code: str
    title: str
    description: str
    locations: list[dict[str, Any]]
    created_at: str
    updated_at: str
    record_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
