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


from app.passport_manager import (
    load_passport
)


from app.services.prediction_pipeline import (
    prediction_pipeline
)



logger = logging.getLogger(__name__)




# =====================================================
# FORMAT PERCENT
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
# WINNER FORMAT
# =====================================================

def format_winner(
        winner,
        home_team,
        away_team
):

    if winner == "home":
        return home_team

    if winner == "away":
        return away_team

    if winner == "draw":
        return "Ничья"

    return winner or "-"





# =====================================================
# HANDLE PREDICT
# =====================================================

async def handle_predict(

        message: Message,

        core=None,

        journal=None

):


    logger.info(

        "PREDICT RECEIVED: %s",

        message.text

    )


    try:


        text = (

            message.text

            or ""

        ).strip()



        if not text:

            return




        text = (

            text.replace(
                "Прогноз",
                ""
            )

            .replace(
                "прогноз",
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

📊 xG Engine

🤖 FAJ Rating

🎲 Monte Carlo

⚠️ Risk Engine


Подождите...
"""

        )






        # =================================================
        # PASSPORTS
        # =================================================


        home_passport = load_passport(
            home_team
        )


        away_passport = load_passport(
            away_team
        )



        if not home_passport:


            await message.answer(

                f"❌ Паспорт {home_team} не найден"

            )

            return




        if not away_passport:


            await message.answer(

                f"❌ Паспорт {away_team} не найден"

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

            "FAJ prediction completed %s - %s",

            home_team,

            away_team

        )






        # =================================================
        # JOURNAL
        # =================================================


        if journal:


            try:

                journal.add_prediction(

                    result

                )


            except Exception:


                logger.warning(

                    "Journal skipped",

                    exc_info=True

                )







        # =================================================
        # DATA
        # =================================================


        winner = format_winner(

            result.get(
                "winner",
                result.get(
                    "winner_prediction",
                    "-"
                )
            ),

            home_team,

            away_team

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







        # =================================================
        # OUTPUT
        # =================================================


        answer = f"""

✅ FAJ PREDICTION READY


⚽ {home_team} — {away_team}


━━━━━━━━━━━━━━


🏆 Победитель:

{winner}



🎯 Ожидаемый счёт:

{expected_score}



━━━━━━━━━━━━━━


📊 xG


{home_team}:

{xg_home}


{away_team}:

{xg_away}



━━━━━━━━━━━━━━


🤖 FAJ Rating


{home_team}:

{home_passport.get(
    "faj_rating",
    "-"
)}


{away_team}:

{away_passport.get(
    "faj_rating",
    "-"
)}



━━━━━━━━━━━━━━


🔥 Уверенность:

{format_percent(
    result.get(
        "confidence",
        0
    )
)}



⚠️ Риск:

{result.get(
    "risk",
    "Средний"
)}



🏷 Категория:

{result.get(
    "grade",
    "C"
)}



"""




        top_scores = result.get(
            "top_scores"
        )


        if top_scores:


            answer += """

━━━━━━━━━━━━━━

🎲 Вероятные счета:

"""


            answer += str(
                top_scores
            )





        btts = result.get(
            "btts_probability"
        )


        if btts is not None:


            answer += f"""

━━━━━━━━━━━━━━

⚽ ОЗ:

{format_percent(btts)}

"""




        over25 = result.get(
            "over25_probability"
        )


        if over25 is not None:


            answer += f"""

📈 ТБ 2.5:

{format_percent(over25)}

"""





        answer += """

━━━━━━━━━━━━━━


🧠 FAJ Engine v7.0.3

🎲 Monte Carlo Simulation

"""




        await message.answer(

            answer

        )






    except Exception as e:


        logger.exception(

            "Prediction handler failed"

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
