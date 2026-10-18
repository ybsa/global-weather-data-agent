"""Unit tests for Universal Data Agent."""
import unittest

from data_agent.models import LocationInfo, CurrentWeather
from data_agent.geocoder import slugify, UniversalGeocoder


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


if __name__ == "__main__":
    unittest.main()
