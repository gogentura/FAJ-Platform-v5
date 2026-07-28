# =====================================================
# FAJ Platform v7.0.3
# app/handlers/predict.py
#
# Single Match Prediction Handler
#
# Flow:
#
# Telegram
#    |
#    v
# Team names
#    |
#    v
# Passport Manager
#    |
#    v
# Prediction Pipeline
#    |
#    v
# FAJ Core
#    |
#    v
# Journal
#
# =====================================================


import logging


from aiogram.types import Message


from app.services.prediction_pipeline import (
    prediction_pipeline
)


from app.passport_manager import (
    load_passport
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

        return "Нет данных"






# =====================================================
# HANDLE PREDICT
# =====================================================


async def handle_predict(

        message: Message,

        core=None,

        journal=None

):


    try:


        text = (

            message.text

            or ""

        )


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

Формат:

Зенит Спартак

или:

Прогноз Зенит Спартак
"""

            )

            return






        home = parts[0]


        away = " ".join(
            parts[1:]
        )





        await message.answer(

            f"""
🧠 FAJ анализ матча


⚽ {home} — {away}


Проверяю:

📁 Team Passport

📊 xG модель

🧠 FAJ Rating

🎲 Monte Carlo

⚠️ Risk Engine


Подождите...
"""

        )







        # =================================================
        # LOAD PASSPORTS
        # =================================================


        home_passport = load_passport(
            home
        )


        away_passport = load_passport(
            away
        )



        if not home_passport:


            await message.answer(

                f"❌ Паспорт {home} не найден"

            )

            return




        if not away_passport:


            await message.answer(

                f"❌ Паспорт {away} не найден"

            )

            return







        # =================================================
        # FIXTURE
        # =================================================


        fixture = {


            "home_team":
                home,


            "away_team":
                away,


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







        # =================================================
        # JOURNAL
        # =================================================


        if journal:


            try:


                fixture_id = (

                    fixture.get(
                        "fixture_id",
                        None
                    )

                )


                journal.save(

                    fixture,

                    result,

                    fixture_id

                )


            except Exception:


                logger.warning(

                    "Journal save skipped",

                    exc_info=True

                )









        # =================================================
        # OUTPUT DATA
        # =================================================


        winner = result.get(

            "winner",

            "-"

        )


        expected_score = result.get(

            "expected_score",

            "-"

        )


        xg_home = result.get(

            "xg_home",

            0

        )


        xg_away = result.get(

            "xg_away",

            0

        )



        confidence = result.get(

            "confidence",

            0

        )



        risk = result.get(

            "risk",

            "Средний"

        )



        grade = result.get(

            "grade",

            "C"

        )





        answer = f"""

✅ FAJ PIPELINE OK


⚽ {home} — {away}


━━━━━━━━━━━━━━


🏆 Победитель:

{winner}



🎯 Ожидаемый счёт:

{expected_score}



━━━━━━━━━━━━━━


📊 xG:


{home}

{xg_home}


-

{away}

{xg_away}



━━━━━━━━━━━━━━


🧠 FAJ Rating:


{home}:

{home_passport.get('faj_rating', '-')}


{away}:

{away_passport.get('faj_rating', '-')}



━━━━━━━━━━━━━━


🔥 Уверенность:

{format_percent(
    confidence
)}



⚠️ Риск:

{risk}



🏷 Категория:

{grade}



━━━━━━━━━━━━━━


🤖 Модель:

FAJ v7.0.3

🎲 Simulation:

Monte Carlo


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
