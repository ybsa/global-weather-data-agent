"""Unit tests for Universal Natural Disaster Data Collector."""
import unittest

from data_agent.models import LocationInfo, CurrentWeather, HydrologySnapshot, EarthquakeEvent
from data_agent.geocoder import slugify, UniversalGeocoder
from data_agent.seismic import haversine_distance_km
from data_agent.storage import StorageEngine


class TestUniversalDataAgent(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("New York"), "new_york")
        self.assertEqual(slugify("Kyōto (Japan)"), "kyoto_japan")
        self.assertEqual(slugify("Zurich-Altstetten"), "zurich_altstetten")

    def test_location_info_display(self):
        loc = LocationInfo(
            location_id="tokyo_jp",
            name="Tokyo",
            country="Japan",
            country_code="JP",
            admin1="Tokyo",
            admin2="",
            latitude=35.6762,
            longitude=139.6503,
            elevation_m=40.0,
            timezone="Asia/Tokyo",
        )
        self.assertIn("Tokyo", loc.display_name)
        self.assertIn("Japan", loc.display_name)

    def test_haversine_distance(self):
        # Tokyo (35.6762, 139.6503) to Sendai (38.2667, 140.8667) is approx 304 km
        dist = haversine_distance_km(35.6762, 139.6503, 38.2667, 140.8667)
        self.assertGreater(dist, 290.0)
        self.assertLess(dist, 320.0)

    def test_storage_secret_code_format(self):
        code = StorageEngine.generate_secret_code()
        self.assertTrue(code.startswith("NAT-"))
        self.assertEqual(len(code), 12)  # NAT- + 8 hex chars

    def test_geocoder_case_insensitivity(self):
        geocoder = UniversalGeocoder()
        # Mock opener to verify variants are passed properly
        calls = []
        def mock_opener(req, timeout=15):
            calls.append(req.full_url)
            class MockResp:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self):
                    # Return results only on title or lowercase to simulate case resilience
                    return b'{"results":[{"name":"Sendai","country":"Japan","country_code":"JP","latitude":38.26,"longitude":140.86}]}'
            return MockResp()

        geocoder.opener = mock_opener
        results = geocoder.search("sendai")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Sendai")
        self.assertEqual(results[0].country_code, "JP")

    def test_geocoder_comma_qualifier(self):
        geocoder = UniversalGeocoder()
        calls = []
        def mock_opener(req, timeout=15):
            calls.append(req.full_url)
            class MockResp:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self):
                    return b'{"results":[{"name":"Lahaina","country":"United States","country_code":"US","admin1":"Hawaii","latitude":20.87,"longitude":-156.67}]}'
            return MockResp()

        geocoder.opener = mock_opener
        results = geocoder.search("lahaina, hi")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Lahaina")
        # Ensure detected country code HI or name query lahaina was requested
        self.assertTrue(any("name=lahaina" in c or "name=Lahaina" in c for c in calls))


if __name__ == "__main__":
    unittest.main()
