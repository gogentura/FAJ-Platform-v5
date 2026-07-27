# =====================================================
# FAJ Platform v6.9.4
# app/handlers/faj_predictions.py
#
# FAJ Match Analysis Viewer
#
# One match = one Telegram message
#
# Compatible:
# - prediction_manager v6.9.3
# - tour_predictor v6.9.3
# - PostgreSQL
# - aiogram 3.x
# =====================================================


import logging


from aiogram import Router

from aiogram.types import (
    Message,
    CallbackQuery
)


from app.managers.prediction_manager import (
    get_predictions
)


from app.keyboards.main import (
    main_keyboard
)


from app.keyboards.faj_navigation import (
    faj_navigation_keyboard
)



logger = logging.getLogger(__name__)


router = Router()



# =====================================================
# CACHE
# =====================================================


FAJ_CACHE = {
    "predictions": []
}





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

        return "⚪ Нет данных"






# =====================================================
# WINNER FORMAT
# =====================================================


def winner_format(value):

    if value == "home":

        return "🏠 Хозяева"


    if value == "away":

        return "🚩 Гости"


    if value == "draw":

        return "🤝 Ничья"


    return "-"






# =====================================================
# BUILD MESSAGE
# =====================================================


def build_match_message(
    prediction,
    index,
    total
):


    home = prediction.get(
        "home_team",
        "?"
    )


    away = prediction.get(
        "away_team",
        "?"
    )


    score = prediction.get(
        "score_prediction",
        prediction.get(
            "expected_score",
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


    winner = prediction.get(
        "winner",
        "-"
    )



    return f"""
🤖 *FAJ MATCH ANALYSIS*

🧠 FAJ Engine v6.9.4

⚽ Матч {index + 1}/{total}

━━━━━━━━━━━━━━


⚽ *{home} — {away}*


🏆 Победа:

{winner_format(winner)}


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
# SHOW MATCH
# =====================================================


async def show_match(
    message,
    index
):


    predictions = FAJ_CACHE.get(
        "predictions",
        []
    )


    if not predictions:


        await message.answer(
            "⚠️ FAJ прогнозов нет",
            reply_markup=main_keyboard()
        )

        return



    if index < 0:

        index = 0



    if index >= len(predictions):

        index = len(predictions)-1




    text = build_match_message(
        predictions[index],
        index,
        len(predictions)
    )



    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=faj_navigation_keyboard(
            index,
            len(predictions)
        )
    )






# =====================================================
# COMMAND
# =====================================================


@router.message(
    lambda message:
    message.text == "/faj_predictions"
)
async def cmd_faj_predictions(
    message: Message
):


    try:


        predictions = get_predictions(
            limit=20
        )



        if not predictions:


            await message.answer(
                """
⚠️ FAJ прогнозов пока нет.

Создайте прогнозы:

🚀 Создать прогнозы тура

или

/generate_tour
""",
                reply_markup=main_keyboard()
            )

            return




        FAJ_CACHE["predictions"] = predictions



        await show_match(
            message,
            0
        )



    except Exception as e:


        logger.exception(
            "FAJ prediction handler error"
        )


        await message.answer(
            f"""
❌ FAJ ПРОГНОЗ ERROR

{type(e).__name__}

{str(e)}
""",
            reply_markup=main_keyboard()
        )








# =====================================================
# NEXT BUTTON
# =====================================================


@router.callback_query(
    lambda c:
    c.data.startswith(
        "faj_next:"
    )
)
async def faj_next(
    callback: CallbackQuery
):


    try:


        index = int(
            callback.data.split(":")[1]
        )


        predictions = FAJ_CACHE.get(
            "predictions",
            []
        )


        new_index = index + 1



        if new_index >= len(predictions):

            new_index = len(predictions)-1



        text = build_match_message(
            predictions[new_index],
            new_index,
            len(predictions)
        )



        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=faj_navigation_keyboard(
                new_index,
                len(predictions)
            )
        )



        await callback.answer()



    except Exception as e:


        logger.exception(
            "FAJ next error"
        )


        await callback.answer(
            "Ошибка"
        )







# =====================================================
# PREVIOUS BUTTON
# =====================================================


@router.callback_query(
    lambda c:
    c.data.startswith(
        "faj_prev:"
    )
)
async def faj_prev(
    callback: CallbackQuery
):


    try:


        index = int(
            callback.data.split(":")[1]
        )



        predictions = FAJ_CACHE.get(
            "predictions",
            []
        )



        new_index = index - 1



        if new_index < 0:

            new_index = 0




        text = build_match_message(
            predictions[new_index],
            new_index,
            len(predictions)
        )



        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=faj_navigation_keyboard(
                new_index,
                len(predictions)
            )
        )



        await callback.answer()



    except Exception as e:


        logger.exception(
            "FAJ prev error"
        )


        await callback.answer(
            "Ошибка"
        )



# =====================================================
# END
# =====================================================
