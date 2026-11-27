import re
from backend.create_account import AccountError, execute, query

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def normalize_notification_time(raw_time):
    val = (raw_time or "").strip()
    if not val:
        return None
    if not TIME_RE.match(val):
        raise AccountError("Notification time must be valid 24-hour HH:MM.")
    return val


def get_notification_settings(user_id):
    rows = query(
        "SELECT is_enabled, notification_time FROM notification_settings WHERE user_id = ?",
        [user_id],
    )
    if not rows:
        return {"is_enabled": False, "notification_time": None}
    row = rows[0]
    return {
        "is_enabled": bool(row.get("is_enabled")),
        "notification_time": row.get("notification_time"),
    }


def save_notification_settings(user_id, enabled, raw_time):
    notif_time = normalize_notification_time(raw_time)
    is_enabled = 1 if enabled else 0
    if is_enabled and not notif_time:
        raise AccountError("Please set a notification time (HH:MM) before enabling notifications.")

    execute(
        """
        INSERT INTO notification_settings (user_id, is_enabled, notification_time)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            is_enabled = excluded.is_enabled,
            notification_time = excluded.notification_time,
            updated_at = datetime('now')
        """,
        [user_id, is_enabled, notif_time],
    )