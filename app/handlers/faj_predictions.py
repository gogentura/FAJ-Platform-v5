# =====================================================
# FAJ Platform v6.9.4
# app/handlers/faj_predictions.py
#
# FAJ Match Viewer
#
# One message = one match
#
# Compatible:
# - prediction_manager v6.9.3
# - PostgreSQL
# - Telegram callbacks
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
# FORMATTERS
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






def winner_format(value):

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
# SINGLE MATCH FORMAT
# =====================================================


def format_match(
    prediction,
    index,
    total
):


    if not prediction:

        return ""



    home = prediction.get(
        "home_team",
        "?"
    )


    away = prediction.get(
        "away_team",
        "?"
    )


    winner = winner_format(
        prediction.get(
            "winner",
            "-"
        )
    )


    score = prediction.get(
        "expected_score",
        prediction.get(
            "score_prediction",
            "-"
        )
    )


    xg_home = prediction.get(
        "xg_home",
        0
    )


    xg_away = prediction.get(
        "xg_away",
        0
    )


    confidence = prediction.get(
        "confidence",
        0
    )



    return f"""
🤖 *FAJ MATCH ANALYSIS*

🧠 FAJ Engine v6.9.4

⚽ Матч {index}/{total}

━━━━━━━━━━━━━━


⚽ *{home} — {away}*


🏆 Победа:

{winner}


🎯 Счёт:

{score}


📊 xG:

{xg_home} — {xg_away}


🔥 Уверенность:

{confidence_badge(confidence)}


━━━━━━━━━━━━━━


📈 FAJ Learning Layer

• Calibration
• Ошибки модели
• Улучшение Core

"""








# =====================================================
# MAIN COMMAND
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

Создайте:

/generate_tour

"""

            )

            return




        # Пока показываем первый матч.
        # Навигацию добавим следующим файлом.

        text = format_match(

            predictions[0],

            1,

            len(predictions)

        )



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )



    except Exception as e:


        logger.exception(

            "FAJ Match Viewer error"

        )


        await message.answer(

f"""
❌ FAJ ПРОГНОЗ ERROR

{type(e).__name__}

{str(e)}

""",

reply_markup=main_keyboard()

)
