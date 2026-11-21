from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "change-this-to-a-random-string"  


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/user/<int:user_id>/profile")
def profile(user_id):
    user_profile = {
        "id": user_id,
        "username": "JohnDoe",
        "email": "johndoe@example.com",
    }
    return render_template("profile.html", profile=user_profile)


@app.route("/user/<int:user_id>/notifications", methods=["POST"])
def notifications(user_id):
    notification_data = request.form.get("notification", "")
    flash(f"Notification for user {user_id}: {notification_data}")
    return redirect(url_for("home"))


@app.route("/user/<int:user_id>/location")
def location(user_id):
    user_location = {
        "city": "New York",
        "country": "USA",
    }
    return render_template("location.html", location=user_location, user_id=user_id)

if __name__ == "__main__":
    app.run(debug=True)