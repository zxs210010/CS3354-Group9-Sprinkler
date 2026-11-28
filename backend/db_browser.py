from backend.create_account import AccountError, query

ALLOWED_TABLES = [
    "users",
    "sqlite_sequence",
    "watering_schedules",
    "daily_settings",
    "notification_settings",
    "weather_snapshots",
    "weather_forecasts",
    "watering_recommendations",
    "watering_events",
    "dashboard_layouts",
    "locations",
    "sprinkler_settings",
]

_ALLOWED_SET = set(ALLOWED_TABLES)


def fetch_table_rows(table_name):
    name = (table_name or "").strip()
    if name not in _ALLOWED_SET:
        raise AccountError(f"Unknown or disallowed table: {name}")

    # Safe because `name` is strictly verified against `_ALLOWED_SET`.
    rows = query(f"SELECT * FROM {name}")
    columns = list(rows[0].keys()) if rows else []
    return {
        "table": name,
        "columns": columns,
        "rows": rows,
    }