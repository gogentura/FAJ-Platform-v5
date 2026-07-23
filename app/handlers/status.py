from aiogram import types

from app.database import get_db
from app.api_tracker import get_api_status
from app.handlers.keyboard import get_main_keyboard


async def cmd_status(message: types.Message):

    conn = get_db()


    passports = conn.execute(
        "SELECT COUNT(*) AS cnt FROM passports"
    ).fetchone()


    journal = conn.execute(
        "SELECT COUNT(*) AS cnt FROM journal"
    ).fetchone()


    fixtures = conn.execute(
        "SELECT COUNT(*) AS cnt FROM fixtures"
    ).fetchone()


    conn.close()


    api = get_api_status()


    text = f"""
⚽ *FAJ Platform v5.2*


🤖 Бот:
✅ Онлайн


☁️ Railway:
✅ Online


🌐 API Football:
{api['used']} / {api['limit']}


📁 Паспортов:
{passports['cnt']}


📝 Прогнозов:
{journal['cnt']}


📅 Матчей:
{fixtures['cnt']}


📌 Версия:
5.2


🧠 Модули:

✅ Team Passport

✅ xG Engine

✅ Prediction

✅ Journal

✅ Fixtures


🕒 Система работает
"""


    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
