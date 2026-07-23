from aiogram import types
from app.database import get_db
from app.handlers.keyboard import get_main_keyboard


async def cmd_dbcheck(message: types.Message):

    conn = get_db()

    try:
        passports = conn.execute(
            "SELECT COUNT(*) FROM passports"
        ).fetchone()[0]

        teams = conn.execute(
            "SELECT team FROM passports LIMIT 10"
        ).fetchall()

        conn.close()

        text = "🗄 Проверка базы FAJ\n\n"
        text += f"Паспортов в БД: {passports}\n\n"

        if teams:
            text += "Команды:\n"
            for t in teams:
                text += f"• {t['team']}\n"
        else:
            text += "❌ Команд нет"

        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        await message.answer(
            f"Ошибка БД:\n{e}",
            reply_markup=get_main_keyboard()
        )
