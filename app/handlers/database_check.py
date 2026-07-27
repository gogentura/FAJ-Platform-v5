# =====================================================
# FAJ Platform v6.9.6
# app/handlers/database_check.py
#
# PostgreSQL Database Diagnostic
#
# Проверяет:
# - наличие подключения
# - таблицу passports
# - таблицу fixtures
# - таблицу predictions
# =====================================================


import logging

from aiogram.types import Message

from app.database import get_db


logger = logging.getLogger(__name__)



# =====================================================
# SAFE ROW VALUE
# =====================================================


def get_value(row, key, index=0):

    try:

        return row[key]

    except Exception:

        try:
            return row[index]

        except Exception:

            return "-"




# =====================================================
# TABLE CHECK
# =====================================================


def check_table(
    cur,
    table_name
):

    cur.execute(
        """
        SELECT column_name

        FROM information_schema.columns

        WHERE table_name=%s

        ORDER BY ordinal_position
        """,
        (
            table_name,
        )
    )


    rows = cur.fetchall()


    columns = []


    for row in rows:

        columns.append(
            get_value(
                row,
                "column_name"
            )
        )


    return columns




# =====================================================
# DATABASE CHECK COMMAND
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



        # ===============================
        # CONNECTION
        # ===============================


        text += (
            "✅ PostgreSQL connection OK\n\n"
        )



        # ===============================
        # PASSPORTS
        # ===============================


        passports = check_table(
            cur,
            "passports"
        )


        text += (
            "📁 passports:\n"
        )


        if passports:

            for column in passports:

                text += (
                    f"• {column}\n"
                )

        else:

            text += (
                "❌ Таблица отсутствует\n"
            )



        text += "\n"



        # ===============================
        # FIXTURES
        # ===============================


        fixtures = check_table(
            cur,
            "fixtures"
        )


        text += (
            "📅 fixtures:\n"
        )


        if fixtures:

            for column in fixtures:

                text += (
                    f"• {column}\n"
                )

        else:

            text += (
                "❌ Таблица отсутствует\n"
            )



        text += "\n"



        # ===============================
        # PREDICTIONS
        # ===============================


        predictions = check_table(
            cur,
            "predictions"
        )


        text += (
            "🤖 predictions:\n"
        )


        if predictions:

            for column in predictions:

                text += (
                    f"• {column}\n"
                )

        else:

            text += (
                "❌ Таблица отсутствует\n"
            )



        conn.close()



        await message.answer(
            text
        )



    except Exception as e:


        logger.exception(
            "Database check error"
        )


        await message.answer(

            f"""
❌ FAJ DATABASE ERROR

{type(e).__name__}

{str(e)}
"""

        )



# =====================================================
# ALIASES
# =====================================================

# для совместимости со старыми версиями bot.py

cmd_dbcheck = cmd_database_check


__all__ = [
    "cmd_database_check",
    "cmd_dbcheck"
]
