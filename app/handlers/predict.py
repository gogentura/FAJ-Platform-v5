# =====================================================
# FAJ Platform v7.0.3
# app/handlers/predict.py
#
# Single Match Prediction Handler
#
# Input:
#   Зенит Спартак
#
# Flow:
#   Passport Manager
#        |
#        v
#   Prediction Pipeline
#        |
#        v
#   FAJ Core
#        |
#        v
#   Journal
#
# =====================================================


import logging


from aiogram.types import Message


from app.passport_manager import (
    load_passport
)


from app.services.prediction_pipeline import (
    prediction_pipeline
)



logger = logging.getLogger(__name__)




# =====================================================
# FORMAT %
# =====================================================


def format_percent(value):

    try:

        value = float(value)

        if value <= 1:

            value *= 100


        return f"{value:.1f}%"



    except Exception:

        return "0%"






# =====================================================
# MAIN HANDLER
# =====================================================


async def handle_predict(

        message: Message,

        core=None,

        journal=None

):


    logger.info(
        "PREDICT HANDLER RECEIVED: %s",
        message.text
    )


    try:


        text = (

            message.text

            or ""

        ).strip()



        if not text:


            return





        # убираем слово прогноз

        text = (

            text.replace(
                "прогноз",
                ""
            )

            .replace(
                "Прогноз",
                ""
            )

            .strip()

        )





        parts = text.split()



        if len(parts) < 2:


            await message.answer(

                """
⚽ FAJ Прогноз


Введите:

Зенит Спартак


или:

Прогноз Зенит Спартак
"""

            )

            return





        home_team = parts[0]


        away_team = " ".join(
            parts[1:]
        )





        await message.answer(

            f"""
🧠 FAJ анализ матча


⚽ {home_team} — {away_team}


Проверяю:

📁 Team Passport

📊 xG модель

🤖 FAJ Rating

🎲 Monte Carlo

⚠️ Risk Engine


Подождите...
"""

        )







        # =================================================
        # LOAD PASSPORTS
        # =================================================


        home_passport = load_passport(
            home_team
        )


        away_passport = load_passport(
            away_team
        )





        if not home_passport:


            await message.answer(

                f"❌ Не найден паспорт {home_team}"

            )

            return





        if not away_passport:


            await message.answer(

                f"❌ Не найден паспорт {away_team}"

            )

            return







        # =================================================
        # FIXTURE
        # =================================================


        fixture = {


            "home_team":
                home_team,


            "away_team":
                away_team,


            "league":
                "RPL",


            "season":
                "2026/27"

        }







        # =================================================
        # PIPELINE
        # =================================================


        result = prediction_pipeline.predict_match(

            fixture,

            home_passport,

            away_passport

        )






        if not result:


            await message.answer(

                "❌ FAJ Pipeline вернул пустой результат"

            )

            return







        logger.info(

            "Prediction completed: %s - %s",

            home_team,

            away_team

        )







        # =================================================
        # JOURNAL
        # =================================================


        if journal:


            try:

                journal.save(

                    fixture,

                    result

                )


            except Exception:


                logger.warning(

                    "Journal save skipped",

                    exc_info=True

                )









        # =================================================
        # OUTPUT
        # =================================================


        answer = f"""

✅ FAJ PREDICTION READY


⚽ {home_team} — {away_team}


━━━━━━━━━━━━━━


🏆 Победитель:

{result.get(
    'winner',
    '-'
)}



🎯 Ожидаемый счёт:

{result.get(
    'expected_score',
    '-'
)}



━━━━━━━━━━━━━━


📊 xG


{home_team}:

{result.get(
    'xg_home',
    0
)}


{away_team}:

{result.get(
    'xg_away',
    0
)}



━━━━━━━━━━━━━━


🤖 FAJ Rating


{home_team}:

{home_passport.get(
    'faj_rating',
    '-'
)}


{away_team}:

{away_passport.get(
    'faj_rating',
    '-'
)}



━━━━━━━━━━━━━━


🔥 Уверенность:

{format_percent(
    result.get(
        'confidence',
        0
    )
)}



⚠️ Риск:

{result.get(
    'risk',
    '-'
)}



🏷 Категория:

{result.get(
    'grade',
    '-'
)}



━━━━━━━━━━━━━━


🧠 FAJ Engine v7.0.3

🎲 Monte Carlo Simulation

"""



        await message.answer(

            answer

        )






    except Exception as e:


        logger.exception(

            "Prediction handler error"

        )


        await message.answer(

            f"""
❌ FAJ ERROR


Тип:

{type(e).__name__}


Ошибка:

{str(e)}
"""

        )



# =====================================================
# END
# =====================================================
