from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "America/Chicago"

def get_watering_datetime(year, month, day, hour, minute, tz_name=None):
    try:
        timezone = ZoneInfo(tz_name or DEFAULT_TZ)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(DEFAULT_TZ)
    return datetime(year, month, day, hour, minute, tzinfo=tz)

def set_watering_time(schedule, new_time):
    try:
        datetime.strptime(new_time, "%H:%M")
    except ValueError:
        return "Invalid watering time"

    schedule["watering_time"] = new_time
    return "Watering time updated successfully"

