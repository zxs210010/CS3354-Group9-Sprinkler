# ============================================================
# AQUATHINK - MAIN FLASK APPLICATION
# ============================================================

# -------------------- Standard Imports ----------------------

import os, re, sys
from functools import wraps
from pathlib import Path

# -------------------- Flask Imports -------------------------

from flask import Flask, render_template, request, redirect, session, url_for, flash

# -------------------- Project Path --------------------------

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ============================================================
# BACKEND IMPORTS
# ============================================================

# Account and database
from backend.create_account import get_user_by_id, AccountError, create_user, verify_login, query, execute
from backend.account_settings import delete_user_account, update_user_password

# Dashboard customization
from backend.uicustom.dashboard_layout import get_layout_key, save_layout_key

# Watering schedule
from backend.timing.watering_schedule import set_watering_time
from backend.timing.daily_settings import DAYS

# Notifications
from backend.notifications.notification_settings import get_notification_settings, save_notification_settings

# Location and sprinkler
from backend.location.location import get_location as get_saved_location, save_location, PLACEHOLDER_SPRINKLERS, LocationError

# Weather
from backend.advice.weather_service import get_weather, recommend_watering, WeatherServiceError

# Database Browsing
from backend.db_browser import ALLOWED_TABLES, fetch_table_rows

# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-key")

# ============================================================
# DEBUGGING
# ============================================================

print("APP ROOT:", app.root_path)
print("TEMPLATE FOLDERS:", app.jinja_loader.searchpath)
print("LOCATION TEMPLATE:", app.jinja_env.get_template("location.html").filename)

# ============================================================
# AUTHENTICATION
# ============================================================

AUTH_PAGES = {
    "login": {"title": "Login", "button": "Sign In", "autocomplete": "current-password", "minlength": 1},
    "register": {"title": "Register", "button": "Create Account", "autocomplete": "new-password", "minlength": 8},
}


def login_required(view):
    """Require the logged-in user to own the requested page."""

    @wraps(view)
    def wrapped(user_id, *args, **kwargs):
        if str(session.get("user_id")) != str(user_id):
            flash("You must be logged in to access this page.")
            return redirect(url_for("login"))
        return view(user_id, *args, **kwargs)

    return wrapped


# ============================================================
# DASHBOARD CUSTOMIZATION
# ============================================================

OPTIONS = ["Sprinkler", "Clock", "Weather", "Schedule"]

DEFAULT_LAYOUT = {
    "c1": "#c5d4fb", "c2": "#177858",
    "panels": ["Sprinkler", "Clock", "Schedule", "Weather"],
}


def parse_key(key):
    """Return the layout dictionary if the key is valid."""

    try:
        c1, c2, panels = (key or "").split(";", 2)
    except ValueError:
        return None

    if not (re.fullmatch(r"[0-9a-fA-F]{6}", c1) and re.fullmatch(r"[0-9a-fA-F]{6}", c2)):
        return None

    panels = [p if p in OPTIONS else "" for p in panels.split(",")][:20]
    return {"c1": "#" + c1, "c2": "#" + c2, "panels": panels}


def decode_key(key):
    """Load saved layout or return default layout."""
    return parse_key(key) or DEFAULT_LAYOUT


# ============================================================
# WATERING SCHEDULE HELPERS
# ============================================================

TIME_OK = "Watering time updated successfully"
DEFAULT_DAY = {"on": True, "time": "06:00", "gallons": 100, "minutes": 15}


def get_user_timezone(uid):
    """Get the timezone saved with the user's location."""

    rows = query("SELECT timezone FROM locations WHERE user_id = ?", [uid])
    return rows[0]["timezone"] if rows and rows[0]["timezone"] else ""


def load_days(uid):
    """Load all saved daily watering settings."""

    rows = query("""
        SELECT day_of_week, watering_time, is_enabled, max_water_gallons, max_duration_min
        FROM daily_settings WHERE user_id = ?
    """, [uid])

    return {row["day_of_week"]: row for row in rows}


def save_week(uid, rows):
    """Save all seven days in one database request."""

    placeholders = ", ".join(["(?, ?, ?, ?, ?, ?)"] * len(rows))
    params = []

    for day, time_str, on, gallons, minutes in rows:
        params += [uid, day, time_str, 1 if on else 0, gallons, minutes]

    execute(f"""
        INSERT INTO daily_settings
            (user_id, day_of_week, watering_time, is_enabled, max_water_gallons, max_duration_min)
        VALUES {placeholders}
        ON CONFLICT(user_id, day_of_week) DO UPDATE SET
            watering_time = excluded.watering_time,
            is_enabled = excluded.is_enabled,
            max_water_gallons = excluded.max_water_gallons,
            max_duration_min = excluded.max_duration_min
    """, params)


def day_forms(uid):
    """Prepare saved watering settings for the schedule page."""

    saved = load_days(uid)
    out = []

    for name in DAYS:
        row = saved.get(name)
        out.append({
            "name": name,
            "on": bool(row["is_enabled"]) if row else DEFAULT_DAY["on"],
            "time": row["watering_time"] if row else DEFAULT_DAY["time"],
            "gallons": row["max_water_gallons"] if row else DEFAULT_DAY["gallons"],
            "minutes": row["max_duration_min"] if row else DEFAULT_DAY["minutes"],
        })

    return out


def schedule_data(uid):
    """Send schedule and sprinkler duration to dashboard cards."""

    saved = load_days(uid)
    if not saved:
        return None

    days = []

    for name in DAYS:
        row = saved.get(name)
        days.append({
            "on": bool(row and row["is_enabled"]),
            "time": row["watering_time"] if row else DEFAULT_DAY["time"],
        })

    settings = query("SELECT run_minutes FROM sprinkler_settings WHERE user_id = ?", [uid])
    run_minutes = settings[0]["run_minutes"] if settings else 0

    return {"timezone": get_user_timezone(uid), "days": days, "runMinutes": run_minutes}


def to_int(value, default=0, maximum=10000):
    """Safely convert form input to an integer."""

    try:
        return max(0, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def store_run_minutes(uid, minutes):
    """Save sprinkler duration in sprinkler_settings."""

    existing = query("SELECT user_id FROM sprinkler_settings WHERE user_id = ?", [uid])

    if existing:
        execute("UPDATE sprinkler_settings SET run_minutes = ?, updated_at = datetime('now') WHERE user_id = ?", [minutes, uid])
    else:
        execute("INSERT INTO sprinkler_settings (user_id, run_minutes) VALUES (?, ?)", [uid, minutes])


# ============================================================
# WEATHER CARD
# ============================================================

def build_weather_card(uid):
    """Build weather information using the user's saved D1 location."""

    try:
        location = get_saved_location(uid)
        if not location:
            return None

        latitude, longitude = location.get("latitude"), location.get("longitude")
        if latitude is None or longitude is None:
            return None

        weather = get_weather(latitude, longitude)

        current = {
            "temperature_c": weather["temperature_c"],
            "humidity_percent": weather["humidity_percent"],
            "precipitation_mm": weather["current_precipitation_mm"],
            "soil_moisture": weather["soil_moisture_fraction"],
            "observed_at": weather["observed_at"],
        }

        forecast = weather["forecast"]
        if not forecast:
            return None

        today = forecast[0]
        soil, rain = current["soil_moisture"], today["precipitation_sum"]
        probability_percent = today["precipitation_probability_max"]
        probability = probability_percent / 100 if probability_percent is not None else None

        recommendation = recommend_watering(soil, rain, probability)

        forecast_display = [{
            "date": day["date"],
            "rain_mm": day["precipitation_sum"],
            "rain_probability": day["precipitation_probability_max"],
            "high": day["temperature_2m_max"],
        } for day in forecast]

        return {
            "city": location.get("city", "Saved Location"),
            "current": current,
            "today": today,
            "forecast": forecast_display,
            "recommendation": recommendation,
        }

    except WeatherServiceError as exc:
        print("Weather card error:", exc)
        return None


# ============================================================
# PUBLIC PAGES
# ============================================================

@app.route("/")
def admin():
    return render_template("admin.html")


# ============================================================
# LOGIN AND REGISTRATION
# ============================================================

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
            return redirect(url_for("location", user_id=user["id"]))

    return render_template("auth.html", page=AUTH_PAGES["register"], name="register")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


# ============================================================
# DASHBOARD ROUTES
# ============================================================

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

    return render_template(
        "dashboard.html",
        dashboard=user_dashboard,
        layout=layout,
        sched_data=schedule_data(uid),
        weather_card=build_weather_card(uid),
    )


@app.route("/user/<string:user_id>/editDash")
@login_required
def edit_dash(user_id):
    uid = session["user_id"]
    layout = decode_key(get_layout_key(uid))

    return render_template("editDash.html", dashboard={"id": uid}, layout=layout, sched_data=schedule_data(uid))


# ============================================================
# WATERING SCHEDULE PAGE
# ============================================================

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

            rows.append((
                day,
                time_str,
                request.form.get(f"{day}_enabled") == "on",
                to_int(request.form.get(f"{day}_gallons")),
                to_int(request.form.get(f"{day}_minutes")),
            ))

        save_week(uid, rows)

        run_minutes = max((minutes for day, time_str, on, gallons, minutes in rows if on), default=0)
        store_run_minutes(uid, run_minutes)

        return redirect(url_for("dashboard", user_id=uid))

    return render_template("schedule.html", dashboard={"id": uid}, days=day_forms(uid), sched_data=schedule_data(uid))


# ============================================================
# QUICK SCHEDULE TIME UPDATE
# ============================================================

@app.route("/user/<string:user_id>/schedule/time", methods=["POST"])
@login_required
def update_time(user_id):
    uid = session["user_id"]
    day, time_str = request.form.get("day", ""), request.form.get("watering_time", "")

    if day not in DAYS or set_watering_time({}, time_str) != TIME_OK:
        flash("Invalid watering time.")
        return redirect(url_for("schedule", user_id=uid))

    execute("UPDATE daily_settings SET watering_time = ? WHERE user_id = ? AND day_of_week = ?", [time_str, uid, day])
    return redirect(url_for("dashboard", user_id=uid))


# ============================================================
# LOCATION AND SPRINKLER PAGE
# ============================================================

@app.route("/user/<string:user_id>/location", methods=["GET", "POST"])
@login_required
def location(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        try:
            place = save_location(uid, request.form.get("city"), request.form.get("state"), request.form.get("country"), request.form.get("sprinkler_id"))

        except (LocationError, AccountError) as exc:
            flash(str(exc), "error")
            typed = {
                "city": request.form.get("city", ""),
                "state": request.form.get("state", ""),
                "country": request.form.get("country", ""),
                "sprinkler_id": request.form.get("sprinkler_id", ""),
            }

            return render_template("location.html", place=typed, user_id=uid, sprinklers=PLACEHOLDER_SPRINKLERS)

        if place and place.get("timezone"):
            execute("UPDATE watering_schedules SET timezone = ? WHERE user_id = ?", [place["timezone"], uid])

        flash("Location saved successfully.")
        return redirect(url_for("dashboard", user_id=uid))

    place = get_saved_location(uid)
    html = render_template(
    "location.html",
    place=place,
    user_id=uid,
    sprinklers=PLACEHOLDER_SPRINKLERS
    )
    print("\n========== LOCATION PAGE DEBUG ==========")
    print("TEMPLATE:", app.jinja_env.get_template("location.html").filename)
    print("HTML OUTPUT:")
    print(html[:500])
    print("=========================================\n")

    return html

# ============================================================
# PROFILE PAGE
# ============================================================

@app.route("/user/<string:user_id>/profile")
@login_required
def profile(user_id):
    uid = session["user_id"]
    user = get_user_by_id(uid)
    layout = decode_key(get_layout_key(uid))

    return render_template("profile.html", profile=user, layout=layout)


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/user/<string:user_id>/notifications", methods=["POST"])
@login_required
def notifications(user_id):
    notification_data = request.form.get("notification", "")
    flash(f"Notification for user {user_id}: {notification_data}")
    return redirect(url_for("admin"))


# ============================================================
# ACCOUNT SETTINGS
# ============================================================

@app.route("/user/<string:user_id>/account", methods=["GET", "POST"])
@login_required
def account_settings(user_id):
    uid = session["user_id"]

    if request.method == "POST":
        action = request.form.get("action")

        try:
            if action == "notifications":
                save_notification_settings(uid, request.form.get("notification_enabled") == "on", request.form.get("notification_time", ""))
                flash("Notification settings updated.")

            elif action == "change_password":
                update_user_password(uid, request.form.get("current_password", ""), request.form.get("new_password", ""))
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

    return render_template("account_settings.html", profile=user, layout=layout, notif=notif)

# ============================================================
# DATABASE BROWSING
# ============================================================
@app.route("/db_browser")
def db_browser():
    selected = request.args.get("table", "").strip()
    result = None

    if selected:
        try:
            result = fetch_table_rows(selected)
        except AccountError as exc:
            flash(str(exc))
            selected = None

    return render_template(
        "db_browser.html",
        profile=None,
        layout=DEFAULT_LAYOUT,
        tables=ALLOWED_TABLES,
        selected=selected,
        result=result,
        standalone_db=True,
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
