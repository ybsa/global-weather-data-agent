import json
import sqlite3
import unittest

from weather_agent.models import Location
from weather_agent.storage import connect, save_location
from weather_agent.tools import execute_tool


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.con = connect(":memory:")
        loc = Location("jumla", "Jumla", "Karnali", "Jumla", 29.274, 82.1838, 2300.0)
        save_location(self.con, loc)
        self.con.commit()

    def tearDown(self):
        self.con.close()

    def test_search_locations_tool(self):
        result_str = execute_tool(self.con, "search_locations", {"query": "Jumla"})
        data = json.loads(result_str)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["location_id"], "jumla")
        self.assertEqual(data[0]["province"], "Karnali")

    def test_unknown_tool_returns_error(self):
        result_str = execute_tool(self.con, "invalid_tool", {})
        data = json.loads(result_str)
        self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
