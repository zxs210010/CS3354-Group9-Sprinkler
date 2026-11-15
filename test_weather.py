"""Offline tests for AquaThink's weather module."""
import unittest
from unittest.mock import patch
from weather_service import WeatherServiceError, get_location, get_watering_data


class WeatherServiceTests(unittest.TestCase):
    @patch("weather_service._fetch_json")
    def test_location(self, fetch):
        fetch.return_value = {"results": [{"name": "Dallas", "admin1": "Texas", "country": "United States", "latitude": 32.78, "longitude": -96.80}]}
        location = get_location("Dallas", "US")
        self.assertEqual(location["state"], "Texas")
        self.assertEqual(location["latitude"], 32.78)

    def test_blank_city(self):
        with self.assertRaises(WeatherServiceError):
            get_location("  ")

    @patch("weather_service._fetch_json")
    def test_partner_output(self, fetch):
        fetch.side_effect = [
            {"results": [{"name": "Dallas", "country": "United States", "latitude": 32.78, "longitude": -96.80}]},
            {"current": {"time": "2026-11-14T12:00", "temperature_2m": 25, "relative_humidity_2m": 60, "precipitation": 0, "soil_moisture_0_to_1cm": None},
             "daily": {"time": ["2026-11-14"], "precipitation_sum": [2.5], "precipitation_probability_max": [40], "et0_fao_evapotranspiration": [3.1], "temperature_2m_max": [27], "temperature_2m_min": [18]}}
        ]
        data = get_watering_data("Dallas")
        self.assertEqual(data["weather"]["forecast"][0]["precipitation_sum"], 2.5)
        self.assertIsNone(data["weather"]["soil_moisture_fraction"])


if __name__ == "__main__":
    unittest.main()
