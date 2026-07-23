from aiogram import types

from app.database import get_db
from app.config import Config



def get_passport_count():

    try:

        conn = get_db()

        row = conn.execute(
            "SELECT COUNT(*) as count FROM passports"
        ).fetchone()

        conn.close()

        if row:
            return row["count"]

        return 0


    except Exception:

        return 0



def get_prediction_count():

    try:

        conn = get_db()

        row = conn.execute(
            "SELECT COUNT(*) as count FROM journal"
        ).fetchone()

        conn.close()

        if row:
            return row["count"]

        return 0


    except Exception:

        return 0



def get_api_usage():

    try:

        conn = get_db()

        row = conn.execute(
            """
            SELECT used, daily_limit
            FROM api_usage
            ORDER BY date DESC
            LIMIT 1
            """
        ).fetchone()

        conn.close()


        if row:

            return (
                row["used"],
                row["daily_limit"]
            )


        return (
            0,
            100
        )


    except Exception:

        return (
            0,
            100
        )



async def cmd_status(
    message: types.Message
):


    passports = get_passport_count()

    predictions = get_prediction_count()

    api_used, api_limit = get_api_usage()



    text = f"""
⚽ FAJ Platform v5.1


🤖 Бот:
✅ Онлайн


☁️ Railway:
✅ Online


🌐 API Football:
{api_used} / {api_limit}


📁 Паспортов:
{passports}


📝 Прогнозов:
{predictions}


📌 Версия:
5.1


🕒 Система работает
"""


    await message.answer(
        text
    )
