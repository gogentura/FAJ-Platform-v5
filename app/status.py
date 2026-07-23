from datetime import datetime

from app.database import get_db

from app.api_tracker import get_api_status


def get_full_status():

    conn = get_db()


    passports_count = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM passports
        """
    ).fetchone()


    journal_count = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM journal
        """
    ).fetchone()


    fixtures_count = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM fixtures
        """
    ).fetchone()


    conn.close()



    api = get_api_status()



    lines = [

        "⚽ *FAJ Platform v5.2*",

        "",

        "🤖 *Бот*: ✅ Онлайн",

        "☁️ *Railway*: ✅ Online",

        "",

        f"🌐 *API Football*: {api['used']} / {api['limit']}",

        "",

        f"📁 *Паспортов*: {passports_count['cnt']}",

        f"📝 *Прогнозов*: {journal_count['cnt']}",

        f"📅 *Матчей в календаре*: {fixtures_count['cnt']}",

        "",

        "🧠 *Модули:*",

        "✅ Team Passport",

        "✅ xG Engine",

        "✅ Prediction",

        "✅ Journal",

        "✅ Fixtures",

        "",

        "📌 *Версия*: 5.2",

        "",

        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    ]


    return "\n".join(lines)
