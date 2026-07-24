# =====================================================
# FAJ Platform v6.0
# Fixtures Debug Handler
# Проверка загруженного календаря
# =====================================================


from aiogram import types

from app.database import get_db



# =====================================================
# SHOW FIXTURES FROM DATABASE
# =====================================================


async def cmd_fixtures_check(
    message: types.Message
):

    conn = get_db()


    try:


        rows = conn.execute(
            """

            SELECT

                id,

                league,

                season,

                round,

                match_date,

                home_team,

                away_team,

                status


            FROM fixtures


            WHERE league = ?


            ORDER BY

                round ASC,

                id ASC


            """,

            (
                "RPL",
            )

        ).fetchall()



        if not rows:


            await message.answer(

                """
❌ Таблица fixtures пуста


Сначала:

⚙️ Админ

↓

📥 Загрузить календарь

"""

            )

            return




        text = """

📅 FAJ Fixtures Check

🏆 Лига: RPL

"""


        current_round = None



        for row in rows:


            item = dict(row)



            if current_round != item["round"]:


                current_round = item["round"]


                text += (

                    "\n"

                    "━━━━━━━━━━━━━━\n"

                    f"📅 Тур {current_round}\n"

                    "━━━━━━━━━━━━━━\n"

                )



            text += (

                f"\n"

                f"⚽ {item['home_team']} — "
                f"{item['away_team']}\n"

                f"📆 {item['match_date']}\n"

                f"📌 Статус: {item['status']}\n"

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


    finally:


        conn.close()
