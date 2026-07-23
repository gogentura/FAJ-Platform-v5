from datetime import datetime
from app.database import get_db
from app.api_tracker import get_api_status

def get_full_status():
    conn = get_db()
    passports_count = conn.execute("SELECT COUNT(*) FROM passports").fetchone()[0]
    journal_count = conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
    conn.close()

    api = get_api_status()

    lines = [
        "📊 *FAJ Platform v5.1*",
        "",
        "🤖 *Бот*: ✅ Онлайн",
        "☁️ *Railway*: ✅ Online",
        "",
        f"🌐 *API Football*: {api['used']} / {api['limit']}",
        f"📁 *Паспортов*: {passports_count}",
        f"📝 *Прогнозов*: {journal_count}",
        f"📌 *Версия*: 5.1",
        "",
        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ]
    return "\n".join(lines)
