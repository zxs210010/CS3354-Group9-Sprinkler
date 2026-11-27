from backend.create_account import query, execute

def get_layout_key(user_id):
    rows = query(
        "SELECT layout_key FROM dashboard_layouts WHERE user_id = ?",
        [user_id],
    )
    return rows[0]["layout_key"] if rows else None
def save_layout_key(user_id, layout_key):
    execute(
        "INSERT INTO dashboard_layouts (user_id, layout_key) " \
        "VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET " \
        "layout_key = excluded.layout_key, " \
        "updated_at = datetime('now')",
        [user_id, layout_key],
    )