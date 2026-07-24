# =====================================================
# FAJ Platform v6.0
# Debug Handler
# Database Diagnostics
# =====================================================


from aiogram import types


from app.database import get_db




# =====================================================
# CHECK FIXTURES
# =====================================================


async def cmd_fixtures_check(
    message: types.Message
):


    try:


        conn = get_db()



        rows = conn.execute(

            """
            SELECT

                id,

                league,

                season,

                round,

                date,

                home_team,

                away_team


            FROM fixtures


            WHERE league = ?

            AND season = ?


            ORDER BY id

            """,

            (

                "RPL",

                "2026/27"

            )

        ).fetchall()



        conn.close()



        if not rows:


            await message.answer(

                """
🔎 Проверка календаря FAJ


Матчи не найдены.

Проверьте загрузку календаря.
"""

            )

            return




        text = """

🔎 Проверка календаря FAJ

🏆 РПЛ 2026/27


"""



        for row in rows:


            text += (

                "━━━━━━━━━━━━━━\n"

                f"🆔 ID: {row['id']}\n"

                f"📅 {row['date']}\n"

                f"🔹 Тур: {row['round']}\n"

                f"⚽ {row['home_team']} — "
                f"{row['away_team']}\n\n"

            )



        await message.answer(

            text

        )



    except Exception as e:



        await message.answer(

            f"""
❌ Ошибка проверки календаря


Тип:
{type(e).__name__}


Ошибка:
{str(e)}
"""

        )
