"""Universal Natural Data Agent: Free, open-source global natural disaster data collector.
Collects live & historical atmospheric, seismic (USGS), river flood discharge, and soil moisture conditions.
Zero API keys required.
"""
from .models import (
    LocationInfo,
    CurrentWeather,
    HourlyForecast,
    EarthquakeEvent,
    HydrologySnapshot,
    NaturalLiveReport,
    CollectionRecord,
)
from .geocoder import UniversalGeocoder, GeocodingError, resolve_location, search_locations, resolve_coordinates
from .collector import (
    UniversalCollector,
    get_current_weather,
    get_hourly_forecast,
    get_natural_live_report,
)
from .seismic import SeismicCollector, get_recent_earthquakes
from .hydrology import HydrologyCollector, get_hydrology
from .archive import fetch_historical_series
from .storage import StorageEngine, get_storage
from .exporter import export_ml_dataset, export_from_queries

__version__ = "1.2.0"

__all__ = [
    "LocationInfo",
    "CurrentWeather",
    "HourlyForecast",
    "EarthquakeEvent",
    "HydrologySnapshot",
    "NaturalLiveReport",
    "CollectionRecord",
    "UniversalGeocoder",
    "GeocodingError",
    "resolve_location",
    "search_locations",
    "resolve_coordinates",
    "UniversalCollector",
    "get_current_weather",
    "get_hourly_forecast",
    "get_natural_live_report",
    "SeismicCollector",
    "get_recent_earthquakes",
    "HydrologyCollector",
    "get_hydrology",
    "fetch_historical_series",
    "StorageEngine",
    "get_storage",
    "export_ml_dataset",
    "export_from_queries",
]
