# =====================================================
# FAJ Platform v7.0.3
# app/handlers/predict.py
#
# Single Match Prediction Handler
# Passport -> Pipeline -> Journal
# =====================================================


import logging


from aiogram.types import Message


from app.services.prediction_pipeline import (
    prediction_pipeline
)


from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


from app.journal import Journal



logger = logging.getLogger(__name__)



journal_service = Journal()



# =====================================================
# FORMAT %
# =====================================================

def format_percent(value):

    try:

        value = float(value)

        if value <= 1:
            value *= 100

        return f"{value:.1f}%"

    except:

        return "0%"



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
            text
            .replace(
                "прогноз",
                ""
            )
            .replace(
                "Прогноз",
                ""
            )
            .replace(
                "—",
                " "
            )
            .replace(
                "-",
                " "
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

или

Прогноз Зенит Спартак
"""

            )

            return




        home_input = parts[0]


        away_input = " ".join(
            parts[1:]
        )



        home = get_team_by_alias(
            home_input
        )


        away = get_team_by_alias(
            away_input
        )



        await message.answer(

f"""
🧠 FAJ анализ матча

⚽ {home} — {away}

Проверяю:

📁 Team Passport
📊 xG модель
🤖 FAJ Rating
🎲 Monte Carlo
⚠️ Risk Engine

Подождите...
"""

        )



        # =============================================
        # LOAD PASSPORTS
        # =============================================


        home_passport = load_passport(
            home
        )


        away_passport = load_passport(
            away
        )



        if not home_passport:


            await message.answer(
                f"❌ Нет паспорта {home}"
            )

            return



        if not away_passport:


            await message.answer(
                f"❌ Нет паспорта {away}"
            )

            return




        # =============================================
        # FIXTURE OBJECT
        # =============================================


        fixture = {

            "home_team": home,

            "away_team": away,

            "league": "RPL",

            "season": "2026/27"

        }





        # =============================================
        # PIPELINE
        # =============================================


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




        # =============================================
        # JOURNAL
        # =============================================


        try:

            journal_service.save(

                fixture,

                result,

                fixture_id=None

            )


        except Exception:


            logger.warning(

                "Journal save skipped",

                exc_info=True

            )





        # =============================================
        # OUTPUT
        # =============================================


        answer=f"""

🤖 FAJ PREDICTION v7.0.3


⚽ {home} — {away}


━━━━━━━━━━━━━━


🏆 Победитель:

{result.get(
    "winner",
    "-"
)}


🎯 Счёт:

{result.get(
    "expected_score",
    "-"
)}


━━━━━━━━━━━━━━


📊 xG

{result.get(
    "xg_home",
    0
)}

-

{result.get(
    "xg_away",
    0
)}



🤖 FAJ Rating

{home}:

{home_passport.get(
    "faj_rating",
    "-"
)}


{away}:

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
    "-"
)}



🏷 Категория:

{result.get(
    "grade",
    "-"
)}


━━━━━━━━━━━━━━


🧠 Model:

FAJ v7.0.3

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
