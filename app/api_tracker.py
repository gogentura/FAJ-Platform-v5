from datetime import datetime
from app.database import get_db

def get_today_usage() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    row = conn.execute("SELECT used FROM api_usage WHERE date = ?", (today,)).fetchone()
    conn.close()
    return row["used"] if row else 0

def increment_usage():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("""
        INSERT INTO api_usage (date, used) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET used = used + 1
    """, (today,))
    conn.commit()
    conn.close()

def get_api_status():
    today = datetime.now().strftime("%Y-%m-%d")
    used = get_today_usage()
    # Используем новое имя столбца daily_limit
    conn = get_db()
    row = conn.execute("SELECT daily_limit FROM api_usage WHERE date = ?", (today,)).fetchone()
    daily_limit = row["daily_limit"] if row else 100
    conn.close()
    return {"used": used, "limit": daily_limit, "remaining": max(0, daily_limit - used)}
