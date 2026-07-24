# =====================================================
# FAJ Platform v6.2
# app/handlers/show_fixtures.py
#
# Fixtures Viewer
#
# PostgreSQL -> Telegram
# =====================================================


import logging


from aiogram.types import Message


from app.database import (
    get_connection
)



logger = logging.getLogger(__name__)



# =====================================================
# GET FIXTURES
# =====================================================


def get_rpl_fixtures():


    conn = get_connection()


    cur = conn.cursor()



    cur.execute(

        """
        SELECT

            id,

            league,

            season,

            match_date,

            match_time,

            home_team,

            away_team,

            status


        FROM fixtures


        WHERE

            league = %s

        AND

            season = %s


        ORDER BY

            match_date,

            match_time

        LIMIT 20

        """,

        (

            "RPL",

            "2026/27"

        )

    )



    fixtures = cur.fetchall()



    conn.close()



    return fixtures



# =====================================================
# TELEGRAM HANDLER
# =====================================================


async def cmd_show_fixtures(

    message: Message

):


    try:


        fixtures = get_rpl_fixtures()



        if not fixtures:


            await message.answer(

                """
📅 Матчи


❌ Календарь пуст


Сначала:

⚙️ Админ

↓

🔄 Синхронизировать календарь

"""

            )

            return



        text = """

📅 FAJ Fixtures


🏆 Лига:
RPL


📅 Сезон:
2026/27


━━━━━━━━━━━━━━

"""



        for fixture in fixtures:



            status = (

                fixture["status"]

                or

                "scheduled"

            )



            date = (

                fixture["match_date"]

                or

                "-"

            )



            time = (

                fixture["match_time"]

                or

                ""

            )



            text += f"""

⚽ {fixture['home_team']} — {fixture['away_team']}

📆 {date} {time}

📌 {status}

"""



        text += """

━━━━━━━━━━━━━━

FAJ готовит:

📊 статистику
🧠 прогнозы
📈 анализ формы

"""



        await message.answer(

            text

        )



    except Exception as e:


        logger.exception(e)



        await message.answer(

            f"""

❌ Ошибка загрузки календаря


{type(e).__name__}


{str(e)}

"""

        )
