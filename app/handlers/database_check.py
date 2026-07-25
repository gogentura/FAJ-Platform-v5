from aiogram import types

from app.database import get_db
from app.handlers.keyboard import get_main_keyboard


async def cmd_dbcheck(message: types.Message):

    try:

        conn = get_db()

        text = "🗄 Проверка PostgreSQL\n\n"

        try:
            passports = conn.execute(
                "SELECT COUNT(*) FROM passports"
            ).fetchone()[0]

            text += f"✅ passports: {passports}\n"

        except Exception as e:
            text += f"❌ passports: {repr(e)}\n"

        try:
            fixtures = conn.execute(
                "SELECT COUNT(*) FROM fixtures"
            ).fetchone()[0]

            text += f"✅ fixtures: {fixtures}\n"

        except Exception as e:
            text += f"❌ fixtures: {repr(e)}\n"

        try:

            rows = conn.execute(

                "SELECT * FROM fixtures LIMIT 3"

            ).fetchall()

            text += "\nПервые записи fixtures:\n"

            for row in rows:

                text += f"{dict(row)}\n\n"

        except Exception as e:

            text += f"\n❌ SELECT * fixtures:\n{repr(e)}"

        conn.close()

        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )

    except Exception as e:

        await message.answer(
            f"Общая ошибка:\n\n{repr(e)}",
            reply_markup=get_main_keyboard()
        )
