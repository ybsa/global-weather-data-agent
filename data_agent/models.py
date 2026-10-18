"""Universal Data Agent Data Models.
Standardized location and weather record structures for global use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class CurrentWeather:
    location: LocationInfo
    timestamp: str
    temperature_2m: float
    relative_humidity_2m: float
    precipitation_mm: float
    wind_speed_10m: float
    surface_pressure_hpa: float
    weather_code: int = 0
    is_day: int = 1
    source: str = "open-meteo"
    data_kind: str = "model-estimated"


@dataclass
class HourlyForecast:
    location: LocationInfo
    times: list[str] = field(default_factory=list)
    temperatures: list[float] = field(default_factory=list)
    humidities: list[float] = field(default_factory=list)
    precipitations: list[float] = field(default_factory=list)
    wind_speeds: list[float] = field(default_factory=list)
    pressures: list[float] = field(default_factory=list)
