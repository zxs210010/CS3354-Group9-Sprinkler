from werkzeug.security import check_password_hash
from backend.create_account import AccountError, change_password, execute, query


def update_user_password(user_id, current_password, new_password):
    change_password(user_id, current_password, new_password)


def delete_user_account(user_id, current_password):
    rows = query("SELECT password_hash FROM users WHERE id = ?", [user_id])
    if not rows:
        raise AccountError("Account not found.")
    if not check_password_hash(rows[0]["password_hash"], current_password or ""):
        raise AccountError("Current password is incorrect.")

    execute("DELETE FROM notification_settings WHERE user_id = ?", [user_id])
    execute("DELETE FROM watering_schedules WHERE user_id = ?", [user_id])
    execute("DELETE FROM users WHERE id = ?", [user_id])