# =====================================================
# FAJ Platform v6.9.6
# app/handlers/database_check.py
#
# PostgreSQL Database Check
# Compatible:
# - cmd_database_check
# - cmd_dbcheck
# - database_check
# =====================================================


import logging

from aiogram.types import Message

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# DATABASE CHECK
# =====================================================

async def cmd_database_check(
    message: Message
):

    try:

        conn = get_db()

        cur = conn.cursor()


        text = (
            "🗄 FAJ DATABASE CHECK\n\n"
        )


        text += (
            "✅ PostgreSQL connection OK\n\n"
        )


        # =============================================
        # PASSPORTS
        # =============================================

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='passports'
            ORDER BY ordinal_position
            """
        )


        passports = cur.fetchall()


        text += (
            "📁 passports:\n"
        )


        if passports:

            for row in passports:

                try:
                    text += (
                        f"• {row['column_name']}\n"
                    )

                except:

                    text += (
                        f"• {row[0]}\n"
                    )

        else:

            text += (
                "❌ Таблица не найдена\n"
            )



        text += "\n"



        # =============================================
        # FIXTURES
        # =============================================

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='fixtures'
            ORDER BY ordinal_position
            """
        )


        fixtures = cur.fetchall()


        text += (
            "📅 fixtures:\n"
        )


        if fixtures:

            for row in fixtures:

                try:
                    text += (
                        f"• {row['column_name']}\n"
                    )

                except:

                    text += (
                        f"• {row[0]}\n"
                    )

        else:

            text += (
                "❌ Таблица не найдена\n"
            )



        text += "\n"



        # =============================================
        # PREDICTIONS
        # =============================================

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='predictions'
            ORDER BY ordinal_position
            """
        )


        predictions = cur.fetchall()


        text += (
            "🤖 predictions:\n"
        )


        if predictions:

            for row in predictions:

                try:

                    text += (
                        f"• {row['column_name']}\n"
                    )

                except:

                    text += (
                        f"• {row[0]}\n"
                    )

        else:

            text += (
                "❌ Таблица не найдена\n"
            )



        conn.close()


        await message.answer(
            text
        )


    except Exception as e:


        logger.exception(
            "FAJ database check error"
        )


        await message.answer(

            f"""
❌ FAJ DATABASE ERROR

{type(e).__name__}

{str(e)}
"""

        )



# =====================================================
# COMPATIBILITY ALIASES
# =====================================================

cmd_dbcheck = cmd_database_check

database_check = cmd_database_check



__all__ = [

    "cmd_database_check",

    "cmd_dbcheck",

    "database_check"

]
