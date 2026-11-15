from datetime import datetime
from zoneinfo import ZoneInfo

def get_watering_datetime(year, month, day, hour, minute):
    timezone = ZoneInfo("America/Chicago")

    watering_datetime = datetime(
        year, month, day, hour, minute,
        tzinfo=timezone
    )

    return watering_datetime

def set_watering_time(schedule, new_time):
    try:
        datetime.strptime(new_time, "%H:%M")
    except ValueError:
        return "Invalid watering time"

    schedule["watering_time"] = new_time
    return "Watering time updated successfully"

