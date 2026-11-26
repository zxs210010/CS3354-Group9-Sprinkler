import re

from flask import Flask, render_template, request, redirect, session, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-string"  

@app.route("/")
def home():
    return render_template("home.html")

from create_account import AccountError, create_user, verify_login

AUTH_PAGES = {
    "login": {"title": "Login", "button": "Sign In"},
    "register": {"title": "Register", "button": "Create Account"}
}


@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template("login", verify_login)

@app.route("/register", methods=["GET", "POST"])
def register():
    return render_template("register", create_user)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))

OPTIONS = ["Sprinkler", "Clock", "Weather", "Calendar", "Reports"]
DEFAULT_LAYOUT = {"c1": "#c5d4fb", "c2": "#177858", "panels": ["Sprinkler", "Clock", "Calendar", "Reports"]}

def decode_key(key):
    try:
        c1, c2, panels = key.split(";", 2)
    except ValueError:
        return DEFAULT_LAYOUT
    if not (re.fullmatch(r"[0-9a-fA-F]{6}", c1) and re.fullmatch(r"[0-9a-fA-F]{6}", c2)):
        return DEFAULT_LAYOUT
    panels = [p if p in OPTIONS else "" for p in panels.split(",")][:20]
    return {"c1": "#" + c1, "c2": "#" + c2, "panels": panels}

@app.route("/user/<string:user_id>/dashboard")
def dashboard(user_id):
    user_dashboard = {
        "id": user_id,
        "username": "JohnDoe",
        "email": "johndoe@example.com",
    }

    key = request.args.get("key")
    if key:
        session[f"layout_{user_id}"] = key
    layout = decode_key(session.get(f"layout_{user_id}", ""))

    return render_template("dashboard.html", dashboard=user_dashboard, layout=layout)

@app.route("/user/<string:user_id>/editDash")
def edit_dash(user_id):
    layout = decode_key(session.get(f"layout_{user_id}", ""))
    return render_template("editDash.html", dashboard={"id": user_id}, layout=layout)

@app.route("/user/<string:user_id>/profile")
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
    return redirect(url_for("home"))


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


