"""Universal Data Agent: Free, modular, open-source global weather scraper and ML dataset exporter.
No API keys required.
"""
from .models import LocationInfo, CurrentWeather, HourlyForecast
from .geocoder import UniversalGeocoder, resolve_location, search_locations
from .collector import UniversalCollector, get_current_weather, get_hourly_forecast
from .archive import fetch_historical_series
from .exporter import export_ml_dataset, export_from_queries

__version__ = "1.0.0"

__all__ = [
    "LocationInfo",
    "CurrentWeather",
    "HourlyForecast",
    "UniversalGeocoder",
    "resolve_location",
    "search_locations",
    "UniversalCollector",
    "get_current_weather",
    "get_hourly_forecast",
    "fetch_historical_series",
    "export_ml_dataset",
    "export_from_queries",
]
