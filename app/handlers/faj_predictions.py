# =====================================================
# FAJ Platform v6.9.3
# app/handlers/faj_predictions.py
#
# FAJ Predictions Viewer
#
# Compatible:
# - prediction_manager v6.9.3
# - tour_predictor v6.9.3
# - PostgreSQL
# =====================================================


import logging


from aiogram.types import Message


from app.managers.prediction_manager import (
    get_predictions
)


from app.keyboards.main import (
    main_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# CONFIDENCE
# =====================================================


def confidence_badge(value):

    try:

        value = float(value)


        if value <= 1:

            value *= 100



        if value >= 65:

            icon = "🟢"

        elif value >= 50:

            icon = "🟡"

        elif value >= 35:

            icon = "🟠"

        else:

            icon = "🔴"



        return f"{icon} {value:.1f}%"



    except:

        return "⚪ -"






# =====================================================
# WINNER FORMAT
# =====================================================


def winner_format(
    value
):


    mapping = {

        "home": "🏠 Хозяева",

        "away": "🚩 Гости",

        "draw": "🤝 Ничья"

    }


    return mapping.get(
        value,
        value or "-"
    )







# =====================================================
# TELEGRAM SPLIT
# =====================================================


async def send_long_message(
    message,
    text
):


    limit = 3800


    while len(text) > limit:


        part = text[:limit]


        cut = part.rfind("\n")


        if cut > 0:

            part = text[:cut]



        await message.answer(

            part,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )


        text = text[len(part):]



    if text:


        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )








# =====================================================
# MAIN HANDLER
# =====================================================


async def cmd_faj_predictions(
    message: Message
):


    try:


        predictions = get_predictions(
            limit=7
        )



        if not predictions:


            await message.answer(

"""
⚠️ FAJ прогнозов нет.

Создайте прогнозы:

🚀 /generate_tour

""",

reply_markup=main_keyboard()

)

            return





        text = """

🤖 *FAJ ПРОГНОЗЫ*

🧠 FAJ Engine v6.9.3

🎲 Monte Carlo 10000

━━━━━━━━━━━━━━

"""



        counter = 1



        for p in predictions:


            if not p:

                continue



            home = p.get(
                "home_team",
                "?"
            )


            away = p.get(
                "away_team",
                "?"
            )



            winner = winner_format(

                p.get(
                    "winner",
                    "-"
                )

            )



            score = p.get(

                "expected_score",

                p.get(
                    "score_prediction",
                    "-"
                )

            )



            xg_home = p.get(
                "xg_home",
                0
            )


            xg_away = p.get(
                "xg_away",
                0
            )


            confidence = p.get(
                "confidence",
                0
            )




            text += f"""

{counter}️⃣ ⚽ *{home} — {away}*

🏆 Победа:
{winner}

🎯 Счёт:
{score}

📊 xG:
{xg_home} — {xg_away}

🔥 Уверенность:
{confidence_badge(confidence)}

━━━━━━━━━━━━━━

"""


            counter += 1




        text += """

📈 *FAJ Learning Layer*

• Calibration
• Ошибки модели
• Улучшение Core

"""



        await send_long_message(
            message,
            text
        )



    except Exception as e:


        logger.exception(
            "FAJ predictions handler error"
        )


        await message.answer(

f"""
❌ FAJ ПРОГНОЗ ERROR

{type(e).__name__}

{str(e)}

""",

reply_markup=main_keyboard()

)
