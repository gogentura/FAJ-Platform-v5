# =====================================================
# FAJ Platform v6.9.6
# app/handlers/database_check.py
# =====================================================

import logging

from aiogram.types import Message

from app.database import get_db


logger = logging.getLogger(__name__)


async def cmd_database_check(
    message: Message
):

    try:

        conn = get_db()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT column_name

            FROM information_schema.columns

            WHERE table_name='passports'

            ORDER BY ordinal_position
            """
        )


        columns = cur.fetchall()


        conn.close()


        text = "🗄 FAJ DATABASE CHECK\n\n"

        text += "Таблица passports:\n"


        for row in columns:

            try:

                text += f"• {row['column_name']}\n"

            except:

                text += f"• {row[0]}\n"



        await message.answer(
            text
        )


    except Exception as e:


        await message.answer(

            f"❌ Database error\n\n{e}"

        )
