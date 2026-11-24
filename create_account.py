"""
create_account.py — account creation and login, backed by Cloudflare D1.
Requires: CF_API_TOKEN (D1:Edit), flask, werkzeug
"""

import json
import os
import re
import urllib.request

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

ACCOUNT_ID = "0a1f0d7a2efde9dc6f7f86b125bfa23b"
DATABASE_ID = "1a23b01a-fa14-4dae-b1f5-89523e281414"
TOKEN = os.environ["cfut_87IvkDKgZK5z4wtpHbsr5JKhF8b6ZMHOep2zO8pL8068f46d"]

URL = (
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
    f"/d1/database/{DATABASE_ID}/query"
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


# --------------------------------------------------------------------------
# Low-level D1 transport
# --------------------------------------------------------------------------

def _post(sql, params=None):
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
    return _post(sql, params).get("results", [])


def execute(sql, params=None):
    return _post(sql, params).get("meta", {})


# --------------------------------------------------------------------------
# Account logic
# --------------------------------------------------------------------------

class AccountError(Exception):
    """Raised when an account operation fails for a user-facing reason."""


def get_user_by_email(email):
    rows = query(
        "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
        [email.strip().lower()],
    )
    return rows[0] if rows else None


def get_user_by_id(user_id):
    rows = query(
        "SELECT id, email, created_at FROM users WHERE id = ?",
        [user_id],
    )
    return rows[0] if rows else None


def create_user(email, password):
    """Create an account and return the new user row."""
    email = (email or "").strip().lower()
    password = password or ""

    if not EMAIL_RE.match(email):
        raise AccountError("Enter a valid email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    if get_user_by_email(email):
        raise AccountError("An account with that email already exists.")

    password_hash = generate_password_hash(password)

    try:
        meta = execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            [email, password_hash],
        )
    except RuntimeError as exc:
        # UNIQUE on users.email is the real guard against simultaneous signups
        if "UNIQUE" in str(exc):
            raise AccountError("An account with that email already exists.") from exc
        raise

    return {"id": meta.get("last_row_id"), "email": email}


def verify_login(email, password):
    """Return the user row if the credentials are valid, else None."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    return {"id": user["id"], "email": user["email"]}


def change_password(user_id, current_password, new_password):
    rows = query("SELECT password_hash FROM users WHERE id = ?", [user_id])
    if not rows:
        raise AccountError("Account not found.")
    if not check_password_hash(rows[0]["password_hash"], current_password or ""):
        raise AccountError("Current password is incorrect.")
    if len(new_password or "") < MIN_PASSWORD_LENGTH:
        raise AccountError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    execute(
        "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
        [generate_password_hash(new_password), user_id],
    )


# --------------------------------------------------------------------------
# Flask routes
# --------------------------------------------------------------------------

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.post("/create_account")
def create_account_route():
    data = request.get_json(silent=True) or request.form
    try:
        user = create_user(data.get("email"), data.get("password"))
    except AccountError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "user": user}), 201


@accounts_bp.post("/login")
def login_route():
    data = request.get_json(silent=True) or request.form
    user = verify_login(data.get("email"), data.get("password"))
    if not user:
        return jsonify({"success": False, "error": "Invalid email or password."}), 401
    return jsonify({"success": True, "user": user}), 200


if __name__ == "__main__":
    import sys

    email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "changeme123"

    try:
        print("Created:", create_user(email, password))
    except AccountError as exc:
        print("Not created:", exc)

    print("Login ok:", verify_login(email, password))
    print("Login bad:", verify_login(email, "wrong-password"))
