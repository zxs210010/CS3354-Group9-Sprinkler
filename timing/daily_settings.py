"""
daily_settings.py — per-day watering caps, backed by Cloudflare D1.
Requires: CF_API_TOKEN environment variable (D1:Edit permission)
"""

import json
import os
import urllib.request

ACCOUNT_ID = "0a1f0d7a2efde9dc6f7f86b125bfa23b"
DATABASE_ID = "1a23b01a-fa14-4dae-b1f5-89523e281414"
TOKEN = os.environ["cfut_87IvkDKgZK5z4wtpHbsr5JKhF8b6ZMHOep2zO8pL8068f46d"]

URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
    f"/d1/database/{DATABASE_ID}/query"
)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --------------------------------------------------------------------------
# Low-level D1 transport
# --------------------------------------------------------------------------

def _post(sql, params=None):
    """Send one statement to D1 and return the first result object."""
    payload = json.dumps({"sql": sql, "params": params or []}).encode()
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    if not body.get("success"):
        raise RuntimeError(f"D1 error: {body.get('errors')}")

    return body["result"][0]


def query(sql, params=None):
    """Run a SELECT and return the rows as a list of dicts."""
    return _post(sql, params).get("results", [])


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and return the meta object."""
    return _post(sql, params).get("meta", {})


# --------------------------------------------------------------------------
# Daily settings
# --------------------------------------------------------------------------

def get_daily_settings(user_id):
    """Return {day_of_week: {max_water_gallons, max_duration_min}} for a user."""
    rows = query(
        """
        SELECT day_of_week, max_water_gallons, max_duration_min
        FROM daily_settings
        WHERE user_id = ?
        """,
        [user_id],
    )
    return {
        row["day_of_week"]: {
            "max_water_gallons": row["max_water_gallons"],
            "max_duration_min": row["max_duration_min"],
        }
        for row in rows
    }


def get_day_setting(user_id, day_of_week):
    """Return one day's limits, or None if that day has no row."""
    rows = query(
        """
        SELECT max_water_gallons, max_duration_min
        FROM daily_settings
        WHERE user_id = ? AND day_of_week = ?
        """,
        [user_id, day_of_week],
    )
    if not rows:
        return None
    return {
        "max_water_gallons": rows[0]["max_water_gallons"],
        "max_duration_min": rows[0]["max_duration_min"],
    }


def set_daily_setting(user_id, day_of_week, max_water_gallons, max_duration_min):
    """Insert or update one day's limits (single statement, no delete-then-insert)."""
    if day_of_week not in DAYS:
        raise ValueError(f"day_of_week must be one of {DAYS}, got {day_of_week!r}")

    execute(
        """
        INSERT INTO daily_settings (user_id, day_of_week, max_water_gallons, max_duration_min)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, day_of_week) DO UPDATE SET
            max_water_gallons = excluded.max_water_gallons,
            max_duration_min  = excluded.max_duration_min
        """,
        [user_id, day_of_week, max_water_gallons, max_duration_min],
    )
    return get_day_setting(user_id, day_of_week)


def set_all_days(user_id, max_water_gallons, max_duration_min):
    """Apply the same limits to every day of the week."""
    for day in DAYS:
        set_daily_setting(user_id, day, max_water_gallons, max_duration_min)
    return get_daily_settings(user_id)


def delete_daily_setting(user_id, day_of_week):
    execute(
        "DELETE FROM daily_settings WHERE user_id = ? AND day_of_week = ?",
        [user_id, day_of_week],
    )


def reset_daily_settings(user_id):
    execute("DELETE FROM daily_settings WHERE user_id = ?", [user_id])


if __name__ == "__main__":
    USER_ID = 1
    print("Before:", get_daily_settings(USER_ID))
    set_daily_setting(USER_ID, "Monday", 120, 15)
    set_daily_setting(USER_ID, "Tuesday", 90, 10)
    print("After: ", get_daily_settings(USER_ID))
