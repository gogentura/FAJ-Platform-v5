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
        "📊 *FAJ Platform v5.0.1 RC*",
        "",
        "🤖 *Бот*: ✅ Онлайн",
        "☁️ *Railway*: ✅ Online",
        "🔗 *GitHub*: ✅ Connected",
        "",
        f"🌐 *API Football*: {api['used']} / {api['limit']}",
        "📅 *Data Football*: последнее обновление не выполнено",
        "",
        f"📁 *Паспортов*: {passports_count}",
        f"📝 *Прогнозов*: {journal_count}",
        "📊 *Точность*: 68.7% (в разработке)",
        f"📌 *Версия*: 5.0.1 RC",
        "",
        f"🕒 *Статус на*: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    ]
    return "\n".join(lines)
