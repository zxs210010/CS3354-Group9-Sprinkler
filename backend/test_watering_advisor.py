import unittest
from backend.watering_advisor import recommend_watering


class WateringAdvisorTests(unittest.TestCase):
    def test_soil_is_moist(self):
        result = recommend_watering(0.35, 0, 0.1)
        self.assertEqual(result, "don't water")
    def test_heavy_rain_predicted(self):
        result = recommend_watering(0.2, 8, 0.3)
        self.assertEqual(result, "don't water")
    def test_high_rain_probability(self):
        result = recommend_watering(0.2, 2, 0.8)
        self.assertEqual(result, "don't water")
    def test_water_when_soil_is_dry_and_no_heavy_rain(self):
        result = recommend_watering(0.2, 2, 0.3)
        self.assertEqual(result, "water")
    def test_missing_soil_moisture(self):
        result = recommend_watering(None, 2, 0.3)
        self.assertEqual(result, "insufficient soil moisture data")
    def test_missing_forecast_rain(self):
        result = recommend_watering(0.2, None, 0.3)
        self.assertEqual(result, "insufficient forecast rain data")
    def test_missing_rain_probability(self):
        result = recommend_watering(0.2, 2, None)
        self.assertEqual(result, "insufficient rain probability data")