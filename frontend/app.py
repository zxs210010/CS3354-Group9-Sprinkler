import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from dashboard_layout import get_layout_key, save_layout_key
from create_account import get_user_by_id, AccountError, create_user, verify_login

from flask import Flask, render_template, request, redirect, session, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-string"  

@app.route("/")
def admin():
    return render_template("admin.html")

from functools import wraps

def login_required(view):
    @wraps(view)
    def wrapped(user_id, *args, **kwargs):
        if str(session.get("user_id")) != str(user_id):
            flash("You must be logged in to access this page.")
            return redirect(url_for("login"))
        return view(user_id,*args, **kwargs)
    return wrapped

AUTH_PAGES = {
    "login": {"title": "Login", "button": "Sign In",
              "autocomplete": "current-password", "minlength": 1},
    "register": {"title": "Register", "button": "Create Account",
                 "autocomplete": "new-password", "minlength": 8}
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

OPTIONS = ["Sprinkler", "Clock", "Weather", "Calendar", "Reports"]
DEFAULT_LAYOUT = {"c1": "#c5d4fb", "c2": "#177858", "panels": ["Sprinkler", "Clock", "Calendar", "Reports"]}

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
    return render_template("dashboard.html", dashboard=user_dashboard, layout=layout)

@app.route("/user/<string:user_id>/editDash")
@login_required
def edit_dash(user_id):
    layout = decode_key(session.get(f"layout_{user_id}", ""))
    return render_template("editDash.html", dashboard={"id": user_id}, layout=layout)

@app.route("/user/<string:user_id>/profile")
@login_required
def profile(user_id):
    user_profile = {
        "id": user_id,
        "username": "JohnDoe",
        "email": "johndoe@example.com",
    }
    return render_template("profile.html", profile=user_profile)


@app.route("/user/<string:user_id>/notifications", methods=["POST"])
def notifications(user_id):
    notification_data = request.form.get("notification", "")
    flash(f"Notification for user {user_id}: {notification_data}")
    return redirect(url_for("admin"))


@app.route("/user/<string:user_id>/location")
def location(user_id):
    user_location = {
        "city": "New York",
        "country": "USA",
    }
    return render_template("location.html", location=user_location, user_id=user_id)

@app.route("/admin")
def admin_panel():       
    return render_template("admin.html")





if __name__ == "__main__":
    app.run(debug=True)


