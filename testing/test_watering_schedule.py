import unittest
from backend.timing.watering_schedule import set_watering_time, get_watering_datetime


class WateringScheduleTests(unittest.TestCase):

    def test_set_watering_time(self):
        schedule = {"watering_time": "08:00"}

        result = set_watering_time(schedule, "20:00")

        self.assertEqual(result, "Watering time updated successfully")
        self.assertEqual(schedule["watering_time"], "20:00")

    def test_invalid_watering_time(self):
        schedule = {"watering_time": "08:00"}

        result = set_watering_time(schedule, "25:70")

        self.assertEqual(result, "Invalid watering time")
        self.assertEqual(schedule["watering_time"], "08:00")

    def test_empty_watering_time(self):
        schedule = {"watering_time": "08:00"}

        result = set_watering_time(schedule, "")

        self.assertEqual(result, "Invalid watering time")
        self.assertEqual(schedule["watering_time"], "08:00")
    
    def test_before_dst(self):
        watering_time = get_watering_datetime(
            2026, 3, 7, 8, 0
        )

        self.assertEqual(watering_time.hour, 8)
        self.assertEqual(
            watering_time.utcoffset().total_seconds(),
            -21600
        )
    
    def test_after_dst(self):
        watering_time = get_watering_datetime(
            2026, 3, 8, 8, 0
        )

        self.assertEqual(watering_time.hour, 8)
        self.assertEqual(
            watering_time.utcoffset().total_seconds(),
            -18000
        )

    def test_dst_ends(self):
        watering_time = get_watering_datetime(2026, 11, 1, 8, 0)

        self.assertEqual(watering_time.hour, 8)
        self.assertEqual(
            watering_time.utcoffset().total_seconds(),
            -21600
            )
    
          