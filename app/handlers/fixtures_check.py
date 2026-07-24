# =====================================================
# FAJ Platform v6.3
# app/handlers/fixtures_check.py
#
# Calendar Check Handler
# =====================================================


from aiogram.types import Message

from app.database import get_connection



async def cmd_fixtures_check(
    message: Message
):


    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(
            """
            SELECT
                id,
                home_team,
                away_team,
                match_date,
                match_time,
                status

            FROM fixtures

            WHERE league=%s
            AND season=%s

            ORDER BY
                match_date,
                match_time
            """,
            (
                "RPL",
                "2026/27"
            )
        )



        fixtures = cur.fetchall()


        conn.close()



        if not fixtures:


            await message.answer(

                """
❌ Календарь пуст

Матчи РПЛ не найдены
"""

            )

            return




        text = """

🔍 Проверка календаря FAJ


🏆 РПЛ 2026/27


━━━━━━━━━━━━━━


"""


        for f in fixtures[:20]:


            text += f"""

⚽ {f['home_team']} — {f['away_team']}

📆 {f['match_date']} {f['match_time']}

📌 {f['status']}


"""


        text += """

━━━━━━━━━━━━━━

✅ Проверка завершена

"""



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

{repr(e)}
"""

        )
