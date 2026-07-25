from aiogram import types

from app.database import get_db
from app.handlers.keyboard import get_main_keyboard


async def cmd_dbcheck(message: types.Message):

    conn = get_db()

    try:

        passports = conn.execute(
            "SELECT COUNT(*) FROM passports"
        ).fetchone()[0]

        fixtures = conn.execute(
            "SELECT COUNT(*) FROM fixtures"
        ).fetchone()[0]

        teams = conn.execute(
            """
            SELECT team
            FROM passports
            LIMIT 5
            """
        ).fetchall()

        matches = conn.execute(
            """
            SELECT *
            FROM fixtures
            LIMIT 5
            """
        ).fetchall()

        text = "🗄 Проверка базы FAJ\n\n"

        text += f"Паспортов: {passports}\n"
        text += f"Матчей: {fixtures}\n\n"

        text += "Команды:\n"

        for t in teams:
            text += f"• {t['team']}\n"

        text += "\n──────────────\n"

        text += "Fixtures:\n\n"

        for m in matches:

            text += (
                f"{dict(m)}\n\n"
            )

        conn.close()

        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )

    except Exception as e:

        await message.answer(
            f"Ошибка БД:\n\n{e}",
            reply_markup=get_main_keyboard()
        )
