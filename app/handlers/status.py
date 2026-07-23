import logging
from datetime import datetime

from aiogram import types

from app.database import get_db
from app.config import Config
from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)


def count_passports():

    try:
        conn = get_db()

        row = conn.execute(
            "SELECT COUNT(*) as count FROM passports"
        ).fetchone()

        conn.close()

        if row:
            return row["count"]

        return 0

    except Exception as e:

        logger.error(
            f"Ошибка подсчета паспортов: {e}"
        )

        return 0



def count_predictions():

    try:
        conn = get_db()

        row = conn.execute(
            "SELECT COUNT(*) as count FROM journal"
        ).fetchone()

        conn.close()

        if row:
            return row["count"]

        return 0

    except Exception as e:

        logger.error(
            f"Ошибка подсчета прогнозов: {e}"
        )

        return 0



async def cmd_status(message: types.Message):


    passports = count_passports()

    predictions = count_predictions()


    text = f"""
⚽ FAJ Platform v5.1


🤖 Бот:
✅ Онлайн


☁️ Railway:
✅ Online


🌐 API Football:
0 / 100


📁 Паспортов:
{passports}


📝 Прогнозов:
{predictions}


📌 Версия:
{Config.MODEL_VERSION if hasattr(Config, 'MODEL_VERSION') else '5.1'}


🕒 Система работает
"""


    await message.answer(
        text,
        reply_markup=get_main_keyboard()
    )
