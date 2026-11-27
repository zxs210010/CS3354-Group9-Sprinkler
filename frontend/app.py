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
from backend.notification_settings import (
    get_notification_settings,
    save_notification_settings,
)
from backend.account_settings import delete_user_account, update_user_password

from flask import Flask, render_template, request, redirect, session, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-string"

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


# Watering schedule helpers 
TZ_NAME = re.compile(r"^([A-Za-z0-9_+\-]+/[A-Za-z0-9_+\-]+){0,2}$")

def clean_tz(value):
    """Keep a timezone name as text. Empty means 'use the viewer's own timezone'."""
    value = (value or "").strip()
    return value if value and len(value) <= 64 and TZ_NAME.match(value) else ""

def load_schedule(uid):
    rows = query(
        "SELECT watering_time, timezone, is_enabled FROM watering_schedules WHERE user_id = ?",
        [uid],
    )
    return rows[0] if rows else None


def store_schedule(uid, watering_time, tz, is_enabled):
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
        [uid, watering_time, tz, 1 if is_enabled else 0],
    )

def schedule_data(uid):
    """Plain data handed to the browser so it ran work out the next run itself"""
    sched = load_schedule(uid)
    if not sched:
        return None
    settings = get_daily_settings(uid)
    off_days = []
    for i, name in enumerate(DAYS):
        s = settings.get(name)
        if  s and not s["max_water_gallons"] and not s["max_duration_min"]:
            off_days.append(i)
        return {
            "enabled": bool(sched["is_enabled"]),
            "time": sched["watering_time"],
            "timezone": sched["timezone"],
            "offDays": off_days,

        }

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
                           sched_data=schedule_data(uid))


@app.route("/user/<string:user_id>/editDash")
@login_required
def edit_dash(user_id):
    uid = session["user_id"]
    layout = decode_key(get_layout_key(uid))
    return render_template("editDash.html", dashboard={"id": user_id}, layout=layout,
                           next_run=schedule_data(uid))


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

        store_schedule(uid, draft["watering_time"], clean_tz(request.form.get("timezone")),
                        request.form.get("is_enabled") == "on")

        for day in DAYS:
            if request.form.get(f"{day}_enabled") == "on":
                gallons = to_int(request.form.get(f"{day}_gallons"))
                minutes = to_int(request.form.get(f"{day}_minutes"))
            else:
                gallons = minutes = 0
            set_daily_setting(uid, day, gallons, minutes)

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
                           days=days, sched_data=schedule_data(uid))

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
    zone = current["timezone"] if current else ""
    store_schedule(uid, draft["watering_time"], zone, enabled)
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


@app.route("/user/<string:user_id>/location")
@login_required
def location(user_id):
    user_location = {
        "city": "New York",
        "country": "USA",
    }
    return render_template("location.html", location=user_location, user_id=user_id)
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
