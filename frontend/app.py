import os, re, sys
from functools import wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from backend.uicustom.dashboard_layout import get_layout_key, save_layout_key
from backend.create_account import (get_user_by_id, AccountError, create_user,
                                    verify_login, query, execute)
from backend.timing.watering_schedule import set_watering_time
from backend.timing.daily_settings import get_daily_settings, set_daily_setting, DAYS
from backend.notifications.notification_settings import (
    get_notification_settings,
    save_notification_settings,
)
from backend.location.location import get_location as get_saved_location
from backend.account_settings import delete_user_account, update_user_password
from backend.advice.weather_service import get_watering_data, recommend_watering, WeatherServiceError
from flask import Flask, render_template, request, redirect, session, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")

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
OPTIONS = ["Sprinkler", "Clock", "Weather", "Schedule"]
DEFAULT_LAYOUT = {"c1": "#c5d4fb", "c2": "#177858",
                  "panels": ["Sprinkler", "Clock", "Schedule", "Reports"]}


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

# Watering schedule helpers
# Every weekday has its own start time, on/off switch and limits (table daily_settings).
# The server never works with timezones: it hands the browser the timezone saved with the
# user's location (as text) and the browser works out "now" and "next run" itself.
TIME_OK = "Watering time updated successfully"
DEFAULT_DAY = {"on": True, "time": "06:00", "gallons": 100, "minutes": 15}


def get_user_timezone(uid):
    """Timezone name saved with the user's location ('' if none: the browser's own is used)."""
    rows = query("SELECT timezone FROM locations WHERE user_id = ?", [uid])
    return rows[0]["timezone"] if rows and rows[0]["timezone"] else ""


def load_days(uid):
    """Return {weekday name: row} for the days this user has saved."""
    rows = query(
        """
        SELECT day_of_week, watering_time, is_enabled, max_water_gallons, max_duration_min
        FROM daily_settings WHERE user_id = ?
        """,
        [uid],
    )
    return {r["day_of_week"]: r for r in rows}


def save_week(uid, rows):
    """Save all seven days in ONE request. rows = [(day, time, on, gallons, minutes), ...]"""
    placeholders = ", ".join(["(?, ?, ?, ?, ?, ?)"] * len(rows))
    params = []
    for day, time_str, on, gallons, minutes in rows:
        params += [uid, day, time_str, 1 if on else 0, gallons, minutes]
    execute(
        f"""
        INSERT INTO daily_settings
            (user_id, day_of_week, watering_time, is_enabled, max_water_gallons, max_duration_min)
        VALUES {placeholders}
        ON CONFLICT(user_id, day_of_week) DO UPDATE SET
            watering_time = excluded.watering_time,
            is_enabled = excluded.is_enabled,
            max_water_gallons = excluded.max_water_gallons,
            max_duration_min = excluded.max_duration_min
        """,
        params,
    )


def day_forms(uid):
    """The seven days as the schedule page shows them (saved values, else defaults)."""
    saved = load_days(uid)
    out = []
    for name in DAYS:
        r = saved.get(name)
        out.append({
            "name": name,
            "on": bool(r["is_enabled"]) if r else DEFAULT_DAY["on"],
            "time": r["watering_time"] if r else DEFAULT_DAY["time"],
            "gallons": r["max_water_gallons"] if r else DEFAULT_DAY["gallons"],
            "minutes": r["max_duration_min"] if r else DEFAULT_DAY["minutes"],
        })
    return out

def schedule_data(uid):
    """Send schedule and sprinkler run duration to the dashboard."""
    saved = load_days(uid)

    if not saved:
        return None

    days = []
    for name in DAYS:
        r = saved.get(name)
        days.append({
            "on": bool(r and r["is_enabled"]),
            "time": r["watering_time"] if r else DEFAULT_DAY["time"]
        })

    # Get run_minutes from sprinkler_settings
    settings = query(
        "SELECT run_minutes FROM sprinkler_settings WHERE user_id = ?",
        [uid]
    )

    run_minutes = settings[0]["run_minutes"] if settings else 0

    return {
        "timezone": get_user_timezone(uid),
        "days": days,
        "runMinutes": run_minutes
    }
def to_int(value, default=0, maximum=10000):
    try:
        return max(0, min(int(value), maximum))
    except (TypeError, ValueError):
        return default
    
def store_run_minutes(uid, minutes):
    """Save the run length into sprinkler_settings.run_minutes (one row per user)."""
    if query("SELECT user_id FROM sprinkler_settings WHERE user_id = ?", [uid]):
        execute("UPDATE sprinkler_settings SET run_minutes = ?, updated_at = datetime('now') "
                "WHERE user_id = ?", [minutes, uid])
    else:
        execute("INSERT INTO sprinkler_settings (user_id, run_minutes) VALUES (?, ?)",
                [uid, minutes])

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
                           sched_data=schedule_data(uid))


@app.route("/user/<string:user_id>/editDash")
@login_required
def edit_dash(user_id):
    uid = session["user_id"]
    layout = decode_key(get_layout_key(uid))
    return render_template("editDash.html", dashboard={"id": user_id}, layout=layout,
                           sched_data=schedule_data(uid))


def build_weather_card(uid):
    """Build weather card using the user's saved D1 coordinates."""

    try:
        # Retrieve saved location from D1
        location = get_saved_location(uid)

        if not location:
            return None

        latitude = location.get("latitude")
        longitude = location.get("longitude")

        if latitude is None or longitude is None:
            return None

        # Retrieve weather using saved coordinates
        weather = get_weather(latitude, longitude)

        current = {
            "temperature_c": weather["temperature_c"],
            "humidity_percent": weather["humidity_percent"],
            "precipitation_mm": weather["current_precipitation_mm"],
            "soil_moisture": weather["soil_moisture_fraction"],
            "observed_at": weather["observed_at"]
        }

        # Get today's forecast
        forecast = weather["forecast"]

        if not forecast:
            return None

        today = forecast[0]

        soil = current["soil_moisture"]
        rain = today["precipitation_sum"]

        # API probability is 0-100; recommendation expects 0-1
        probability_percent = today["precipitation_probability_max"]

        probability = (
            probability_percent / 100
            if probability_percent is not None
            else None
        )

        # Generate recommendation
        recommendation = recommend_watering(
            soil,
            rain,
            probability
        )

        # Format three-day forecast for HTML
        forecast_display = [
            {
                "date": day["date"],
                "rain_mm": day["precipitation_sum"],
                "rain_probability": day["precipitation_probability_max"],
                "high": day["temperature_2m_max"]
            }
            for day in forecast
        ]

        return {
            "city": location.get("city", "Saved Location"),
            "current": current,
            "today": today,
            "forecast": forecast_display,
            "recommendation": recommendation
        }

    except WeatherServiceError as exc:
        print("Weather card error:", exc)
        return None
    
# Watering Schedule page
@app.route("/user/<string:user_id>/schedule", methods=["GET", "POST"])
@login_required
def schedule(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        rows = []
        for day in DAYS:
            time_str = request.form.get(f"{day}_time", "")
            if set_watering_time({}, time_str) != TIME_OK:
                flash(f"Invalid watering time for {day}.")
                return redirect(url_for("schedule", user_id=uid))
            rows.append((day, time_str,
                         request.form.get(f"{day}_enabled") == "on",
                         to_int(request.form.get(f"{day}_gallons")),
                         to_int(request.form.get(f"{day}_minutes"))))
        save_week(uid, rows)
        run_minutes = max(
            (minutes for day, time_str, on, gallons, minutes in rows if on),
            default=0
        )
        store_run_minutes(uid, run_minutes)
        return redirect(url_for("dashboard", user_id=uid))

    return render_template("schedule.html", dashboard={"id": uid},
                           days=day_forms(uid), sched_data=schedule_data(uid))

# Quick edit of one day's start time (used by the Next Activation card on the dashboard)
@app.route("/user/<string:user_id>/schedule/time", methods=["POST"])
@login_required
def update_time(user_id):
    uid = session["user_id"]
    day = request.form.get("day", "")
    time_str = request.form.get("watering_time", "")
    if day not in DAYS or set_watering_time({}, time_str) != TIME_OK:
        flash("Invalid watering time.")
        return redirect(url_for("schedule", user_id=uid))

    execute(
        "UPDATE daily_settings SET watering_time = ? WHERE user_id = ? AND day_of_week = ?",
        [time_str, uid, day],
    )
    return redirect(url_for("dashboard", user_id=uid))

@app.route("/user/<string:user_id>/profile")
@login_required
def profile(user_id):
    uid = session["user_id"]
    user = get_user_by_id(uid)
    layout = decode_key(get_layout_key(uid))
    return render_template("profile.html", profile=user, layout=layout)


@app.route("/user/<string:user_id>/notifications", methods=["POST"])
@login_required
def notifications(user_id):
    notification_data = request.form.get("notification", "")
    flash(f"Notification for user {user_id}: {notification_data}")
    return redirect(url_for("admin"))

from backend.location.location import save_location, get_location, PLACEHOLDER_SPRINKLERS

@app.route("/user/<string:user_id>/location", methods=["GET", "POST"])
@login_required
def location(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        try:
            place = save_location(uid, request.form.get("city"),
                                  request.form.get("state"), request.form.get("country"),
                                  request.form.get("sprinkler_id"))
        except AccountError as exc:
            flash(str(exc), "error")
            typed = {"city": request.form.get("city", ""),
                     "state": request.form.get("state", ""),
                     "country": request.form.get("country", ""),
                     "sprinkler_id": request.form.get("sprinkler_id", "")}
            return render_template("location.html", place=typed, user_id=uid,
                                   sprinklers=PLACEHOLDER_SPRINKLERS)

        if place.get("timezone"):
            execute("UPDATE watering_schedules SET timezone = ? WHERE user_id = ?",
                    [place["timezone"], uid])

        flash("Location saved.")
        return redirect(url_for("dashboard", user_id=uid))

    return render_template("location.html", location=get_location(uid), user_id=uid,
                           sprinklers=PLACEHOLDER_SPRINKLERS)


@app.route("/user/<string:user_id>/account", methods=["GET", "POST"])
@login_required
def account_settings(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "notifications":
                save_notification_settings(
                    uid,
                    request.form.get("notification_enabled") == "on",
                    request.form.get("notification_time", ""),
                )
                flash("Notification settings updated.")
            elif action == "change_password":
                update_user_password(
                    uid,
                    request.form.get("current_password", ""),
                    request.form.get("new_password", ""),
                )
                flash("Password updated successfully.")
            elif action == "delete_account":
                delete_user_account(uid, request.form.get("current_password", ""))
                session.pop("user_id", None)
                flash("Account deleted.")
                return redirect(url_for("register"))
        except AccountError as exc:
            flash(str(exc))

        return redirect(url_for("account_settings", user_id=uid))

    user = get_user_by_id(uid)
    layout = decode_key(get_layout_key(uid))
    notif = get_notification_settings(uid)
    return render_template(
        "account_settings.html",
        profile=user,
        layout=layout,
        notif=notif,
    )


if __name__ == "__main__":
    app.run(debug=True)