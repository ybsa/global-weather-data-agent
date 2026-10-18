import json
import unittest

from weather_agent.models import Location
from weather_agent.geocoding import geocode_global_location
from weather_agent.providers import fetch_open_meteo


class Response:
    def __init__(self, payload): self.payload = payload
    def read(self): return json.dumps(self.payload).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False


class ProviderTests(unittest.TestCase):
    def test_labels_current_as_model_estimated_and_hourly_as_forecast(self):
        payload = {"current": {"time": "2026-10-18T10:00", "temperature_2m": 20},
          "hourly": {"time": ["2026-10-18T11:00"], "temperature_2m": [21], "precipitation": [0]}}
        location = Location("test", "Test", "Bagmati", "Test", 27, 85, 1000)
        records = fetch_open_meteo(location, opener=lambda *args, **kwargs: Response(payload))
        self.assertEqual([r["data_kind"] for r in records], ["model_estimated", "forecast"])
        self.assertEqual(records[1]["temperature_c"], 21)

    def test_global_geocoder_accepts_places_outside_nepal(self):
        payload = {"results": [{
            "name": "London", "country_code": "GB", "admin1": "England",
            "admin2": "Greater London", "latitude": 51.5072, "longitude": -0.1276,
            "elevation": 25,
        }]}
        location = geocode_global_location("London, UK", opener=lambda *args, **kwargs: Response(payload))
        self.assertIsNotNone(location)
        self.assertEqual(location.name, "London")
        self.assertEqual(location.location_id, "london_greater_london_gb")

