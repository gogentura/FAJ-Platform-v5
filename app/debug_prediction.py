# =====================================================
# FAJ Platform v6.7
# app/debug_prediction.py
#
# Full Prediction Pipeline Debug
# =====================================================


import logging
import traceback


from aiogram import types


from app.services.prediction_pipeline import (
    predict_match_pipeline
)


logger = logging.getLogger(__name__)




# =====================================================
# DEBUG COMMAND
# =====================================================


async def cmd_debug_prediction(

    message: types.Message,

    core=None

):


    try:


        text = (

            message.text

            .replace(
                "/debug_prediction",
                ""
            )

            .strip()

        )



        parts = text.split()



        if len(parts) < 2:


            await message.answer(

                """
🧪 FAJ Debug Prediction


Пример:

/debug_prediction Акрон Зенит
"""

            )


            return




        home = parts[0]


        away = " ".join(

            parts[1:]

        )




        await message.answer(

            f"""
🧪 FAJ Pipeline Debug


Матч:

⚽ {home} — {away}


Проверяю:

✅ Team Passport

✅ FAJ Rating

✅ xG Engine

✅ Monte Carlo

✅ Risk Engine

✅ Expert Layer

"""

        )




        # =============================================
        # PIPELINE
        # =============================================


        prediction = predict_match_pipeline(

            home,

            away,

            "RPL",

            "2026/27"

        )



        if prediction is None:


            raise Exception(

                "Prediction pipeline вернул None"

            )




        # =============================================
        # OUTPUT
        # =============================================


        answer = f"""

✅ FAJ PIPELINE OK


⚽ {home} — {away}


━━━━━━━━━━━━━━


🏆 Победитель:

{prediction.get(
    "winner",
    "-"
)}


🎯 Счёт:

{prediction.get(
    "expected_score",
    "-"
)}


━━━━━━━━━━━━━━


📊 xG:

{prediction.get(
    "xg_home",
    0
)}

-

{prediction.get(
    "xg_away",
    0
)}



🧠 FAJ Rating:

{prediction.get(
    "home_rating",
    0
)}

-

{prediction.get(
    "away_rating",
    0
)}


━━━━━━━━━━━━━━


🔥 Уверенность:

{prediction.get(
    "confidence",
    0
)}%



⚠️ Риск:

{prediction.get(
    "risk",
    "-"
)}



🏷 Категория:

{prediction.get(
    "grade",
    "-"
)}


━━━━━━━━━━━━━━


🧠 Факторы:


{prediction.get(
    "factors",
    []
)}

"""


        await message.answer(

            answer

        )




    except Exception as e:


        logger.error(

            traceback.format_exc()

        )


        await message.answer(

            f"""
❌ DEBUG ERROR


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )
