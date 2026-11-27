import os, re, sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from backend.uicustom.dashboard_layout import get_layout_key, save_layout_key
from backend.create_account import (get_user_by_id, AccountError, create_user,
                                    verify_login, query, execute)
from backend.timing.watering_schedule import get_watering_datetime, set_watering_time
from backend.timing.daily_settings import get_daily_settings, set_daily_setting, DAYS

from flask import Flask, render_template, request, redirect, session, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-string"

SCHEDULE_TZ = "America/Chicago"  # matches get_watering_datetime in watering_schedule.py


# Admin Route
@app.route("/")
def admin():
    return render_template("admin.html")


# Login Requirement
def login_required(view):
    @wraps(view)
    def wrapped(user_id, *args, **kwargs):
        if str(session.get("user_id")) != str(user_id):
            flash("You must be logged in to access this page.")
            return redirect(url_for("login"))
        return view(user_id, *args, **kwargs)
    return wrapped


# Login and Registration Pages
AUTH_PAGES = {
    "login": {"title": "Login", "button": "Sign In",
              "autocomplete": "current-password", "minlength": 1},
    "register": {"title": "Register", "button": "Create Account",
                 "autocomplete": "new-password", "minlength": 8},
}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = verify_login(request.form.get("email"), request.form.get("password"))
        if user:
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard", user_id=user["id"]))
        flash("Invalid email or password.")
    return render_template("auth.html", page=AUTH_PAGES["login"], name="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            user = create_user(request.form.get("email"), request.form.get("password"))
        except AccountError as exc:
            flash(str(exc))
        else:
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard", user_id=user["id"]))
    return render_template("auth.html", page=AUTH_PAGES["register"], name="register")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


# Customize UI Key
OPTIONS = ["Sprinkler", "Clock", "Weather", "Schedule", "Reports"]
DEFAULT_LAYOUT = {"c1": "#c5d4fb", "c2": "#177858",
                  "panels": ["Sprinkler", "Clock", "Calendar", "Reports"]}


def parse_key(key):
    """Return the layout dict if the key is valid, else None."""
    try:
        c1, c2, panels = (key or "").split(";", 2)
    except ValueError:
        return None
    if not (re.fullmatch(r"[0-9a-fA-F]{6}", c1) and re.fullmatch(r"[0-9a-fA-F]{6}", c2)):
        return None
    panels = [p if p in OPTIONS else "" for p in panels.split(",")][:20]
    return {"c1": "#" + c1, "c2": "#" + c2, "panels": panels}


def decode_key(key):
    return parse_key(key) or DEFAULT_LAYOUT


# Watering schedule helpers (use watering_schedule.py and daily_settings.py as-is)
def load_schedule(uid):
    rows = query(
        "SELECT watering_time, is_enabled FROM watering_schedules WHERE user_id = ?",
        [uid],
    )
    return rows[0] if rows else None


def store_schedule(uid, watering_time, is_enabled):
    execute(
        """
        INSERT INTO watering_schedules (user_id, watering_time, timezone, is_enabled)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            watering_time = excluded.watering_time,
            timezone = excluded.timezone,
            is_enabled = excluded.is_enabled,
            updated_at = datetime('now')
        """,
        [uid, watering_time, SCHEDULE_TZ, 1 if is_enabled else 0],
    )

def get_schedule_tz():
    try:
        return ZoneInfo(SCHEDULE_TZ)
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo

def next_watering(uid):
    """Return {'label', 'timezone'} for the next run, or None if nothing is scheduled."""
    sched = load_schedule(uid)
    if not sched or not sched["is_enabled"]:
        return None

    hh, mm = map(int, sched["watering_time"].split(":"))
    now = datetime.now(get_schedule_tz())
    settings = get_daily_settings(uid)

    for offset in range(8):
        d = now + timedelta(days=offset)
        run = get_watering_datetime(d.year, d.month, d.day, hh, mm)
        if run <= now:
            continue
        day = settings.get(DAYS[run.weekday()])
        if day and day["max_water_gallons"] == 0 and day["max_duration_min"] == 0:
            continue  # this weekday is turned off

        when = "Today" if offset == 0 else "Tomorrow" if offset == 1 else run.strftime("%A")
        time_str = run.strftime("%I:%M %p").lstrip("0")
        return {"label": f"{when} at {time_str}", "timezone": SCHEDULE_TZ}
    return {"label": f"{when} at {time_str}", "timezone": SCHEDULE_TZ,
        "time": f"{hh:02d}:{mm:02d}"}


def to_int(value, default=0, maximum=10000):
    try:
        return max(0, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


# Dashboards
@app.route("/user/<string:user_id>/dashboard")
@login_required
def dashboard(user_id):
    uid = session["user_id"]

    key = request.args.get("key")
    if key and parse_key(key):
        save_layout_key(uid, key)
        return redirect(url_for("dashboard", user_id=uid))

    layout = decode_key(get_layout_key(uid))
    user_dashboard = get_user_by_id(uid)
    return render_template("dashboard.html", dashboard=user_dashboard, layout=layout,
                           next_run=next_watering(uid))


@app.route("/user/<string:user_id>/editDash")
@login_required
def edit_dash(user_id):
    uid = session["user_id"]
    layout = decode_key(get_layout_key(uid))
    return render_template("editDash.html", dashboard={"id": user_id}, layout=layout,
                           next_run=next_watering(uid))


# Watering Schedule page
@app.route("/user/<string:user_id>/schedule", methods=["GET", "POST"])
@login_required
def schedule(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        draft = {}
        result = set_watering_time(draft, request.form.get("watering_time", ""))
        if result != "Watering time updated successfully":
            flash(result)
            return redirect(url_for("schedule", user_id=uid))

        store_schedule(uid, draft["watering_time"], request.form.get("is_enabled") == "on")

        for day in DAYS:
            if request.form.get(f"{day}_enabled") == "on":
                gallons = to_int(request.form.get(f"{day}_gallons"))
                minutes = to_int(request.form.get(f"{day}_minutes"))
            else:
                gallons = minutes = 0
            set_daily_setting(uid, day, gallons, minutes)

        flash("Schedule updated successfully.")
        return redirect(url_for("dashboard", user_id=uid))

    sched = load_schedule(uid) or {"watering_time": "06:00", "is_enabled": 1}
    saved = get_daily_settings(uid)
    days = []
    for name in DAYS:
        s = saved.get(name)
        on = s is None or bool(s["max_water_gallons"] or s["max_duration_min"])
        days.append({
            "name": name,
            "enabled": on,
            "gallons": s["max_water_gallons"] if s and on else 100,
            "minutes": s["max_duration_min"] if s and on else 15,
        })

    return render_template("schedule.html", dashboard={"id": uid}, sched=sched,
                           days=days, timezone=SCHEDULE_TZ, next_run=next_watering(uid))

@app.route("/user/<string:user_id>/schedule/time", methods=["POST"])
@login_required
def update_time(user_id):
    uid = session["user_id"]
    draft = {}
    result = set_watering_time(draft, request.form.get("watering_time", ""))
    if result != "Watering time updated successfully":
        flash(result)
        return redirect(url_for("schedule", user_id=uid))

    current = load_schedule(uid)
    enabled = bool(current["is_enabled"]) if current else True
    store_schedule(uid, draft["watering_time"], enabled)
    return redirect(url_for("dashboard", user_id=uid))

@app.route("/user/<string:user_id>/profile")
@login_required
def profile(user_id):
    uid = session["user_id"]
    user = get_user_by_id(uid)
    layout = decode_key(get_layout_key(uid))
    return render_template("profile.html", profile=user, layout=layout)

@app.route("/user/<string:user_id>/profile/account")
@login_required
def account_settings(user_id):
    return "In Development"

@app.route("/user/<string:user_id>/notifications", methods=["POST"])
@login_required
def notifications(user_id):
    notification_data = request.form.get("notification", "")
    flash(f"Notification for user {user_id}: {notification_data}")
    return redirect(url_for("admin"))


@app.route("/user/<string:user_id>/location")
@login_required
def location(user_id):
    user_location = {
        "city": "New York",
        "country": "USA",
    }
    return render_template("location.html", location=user_location, user_id=user_id)


if __name__ == "__main__":
    app.run(debug=True)