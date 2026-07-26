# =====================================================
# FAJ Platform v6.5
# app/debug_fixtures.py
#
# Fixtures Debug Handler
#
# PostgreSQL fixtures inspection
# =====================================================


import logging
import traceback


from aiogram.types import Message


from app.database import get_db



logger = logging.getLogger(__name__)





# =====================================================
# LOAD FIXTURES
# =====================================================


def load_fixtures_debug(

    league="RPL",

    season="2026/27"

):


    try:


        conn = get_db()

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
                status,
                round


            FROM fixtures


            WHERE league=%s

            AND season=%s


            ORDER BY match_date, match_time

            LIMIT 50

            """,

            (

                league,

                season

            )

        )



        rows = cur.fetchall()



        cur.close()

        conn.close()



        fixtures = []



        for row in rows:


            try:

                fixtures.append(

                    dict(row)

                )


            except Exception:


                fixtures.append(

                    {

                        "id": row[0],

                        "league": row[1],

                        "season": row[2],

                        "match_date": row[3],

                        "match_time": row[4],

                        "home_team": row[5],

                        "away_team": row[6],

                        "status": row[7],

                        "round": row[8]

                    }

                )



        return fixtures



    except Exception as e:


        logger.error(

            traceback.format_exc()

        )


        return {

            "error": str(e)

        }





# =====================================================
# DEBUG HANDLER
# =====================================================


async def debug_fixtures(

    message: Message

):


    try:


        await message.answer(

            """
🧪 FAJ FIXTURES DEBUG


Проверяю:

🏆 Лига:
RPL


📅 Сезон:
2026/27


База:
PostgreSQL fixtures

Подождите...
"""

        )



        data = load_fixtures_debug()



        if isinstance(data, dict) and "error" in data:


            await message.answer(

                f"""
❌ Ошибка базы fixtures


Тип:

Database Error


Ошибка:

{data['error']}
"""

            )


            return




        if not data:


            await message.answer(

                """
⚠️ Fixtures не найдены


Проверь:

• таблица fixtures

• league = RPL

• season = 2026/27

• загрузку календаря Soccer365

• миграции PostgreSQL

"""

            )


            return




        # статистика


        total = len(data)



        scheduled = len(

            [

                x for x in data

                if x.get("status") == "scheduled"

            ]

        )



        finished = len(

            [

                x for x in data

                if x.get("status") == "finished"

            ]

        )




        text = f"""

🧪 FAJ FIXTURES DEBUG


🏆 Лига:

RPL


📅 Сезон:

2026/27


━━━━━━━━━━━━━━


Всего матчей:

{total}


⏳ Scheduled:

{scheduled}


✅ Finished:

{finished}


━━━━━━━━━━━━━━


"""



        for fixture in data[:15]:


            text += f"""

⚽ {fixture.get('home_team')}

-

{fixture.get('away_team')}


📅 {fixture.get('match_date')}

⏰ {fixture.get('match_time')}


Статус:

{fixture.get('status')}


Раунд:

{fixture.get('round')}


──────────────

"""



        await message.answer(

            text

        )



    except Exception as e:


        logger.error(

            traceback.format_exc()

        )


        await message.answer(

            f"""

❌ DEBUG FIXTURES ERROR


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )





# =====================================================
# COMPATIBILITY NAME
# =====================================================


async def cmd_debug_fixtures(

    message: Message

):


    await debug_fixtures(

        message

    )
