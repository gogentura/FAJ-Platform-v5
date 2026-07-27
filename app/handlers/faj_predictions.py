# =====================================================
# FAJ Platform v6.9.5
# app/handlers/faj_predictions.py
#
# Telegram Match Viewer
# =====================================================


import logging


from aiogram.types import (
    Message,
    CallbackQuery
)


from app.managers.prediction_manager import (
    get_predictions
)


from app.keyboards.faj_navigation import (
    faj_navigation_keyboard,
    faj_tour_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# CONFIDENCE BADGE
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



    except Exception:

        return "⚪"





# =====================================================
# WINNER ICON
# =====================================================

def winner_icon(value):


    if value == "home":

        return "🏠 Хозяева"



    if value == "away":

        return "🚩 Гости"



    if value == "draw":

        return "🤝 Ничья"



    return "—"






# =====================================================
# MATCH CARD
# =====================================================

def format_match(
        prediction,
        index,
        total
):


    return f"""
🤖 *FAJ MATCH ANALYSIS*

🧠 FAJ Engine v6.9.5

⚽ Матч {index+1}/{total}

━━━━━━━━━━━━━━

⚽ *{prediction.get('home_team','?')} — {prediction.get('away_team','?')}*

🏆 Прогноз:

{winner_icon(
    prediction.get('winner')
)}

🎯 Основной счёт:

{prediction.get(
    'expected_score',
    '-'
)}

📊 Ожидаемый xG:

{prediction.get(
    'xg_home',
    0
)}
 —
{prediction.get(
    'xg_away',
    0
)}


━━━━━━━━━━━━━━


🔥 Уверенность:

{confidence_badge(
    prediction.get(
        'confidence',
        0
    )
)}


━━━━━━━━━━━━━━


⚙️ Model:

FAJ Core

🎲 Simulation:

Monte Carlo 10000


━━━━━━━━━━━━━━


📈 FAJ Learning Layer

• Calibration
• Ошибки модели
• Улучшение Core

"""






# =====================================================
# SHOW TOUR LIST
# =====================================================

async def show_predictions_list(
        target
):


    predictions = get_predictions(
        limit=100
    )



    if not predictions:


        text = """
⚠️ FAJ прогнозов нет.

Сначала выполните:

🚀 Создать прогнозы тура
"""



        if isinstance(
            target,
            Message
        ):

            await target.answer(
                text
            )

        else:

            await target.message.edit_text(
                text
            )


        return





    text = """
🤖 *FAJ ПРОГНОЗЫ*

🧠 FAJ Engine v6.9.5

━━━━━━━━━━━━━━

Выберите матч:
"""



    keyboard = faj_tour_keyboard(
        predictions
    )




    if isinstance(
        target,
        Message
    ):


        await target.answer(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


    else:


        await target.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )








# =====================================================
# SHOW ONE MATCH
# =====================================================

async def show_prediction(
        target,
        index: int
):


    predictions = get_predictions(
        limit=100
    )



    if not predictions:


        text = """
⚠️ FAJ прогнозов нет.

Сначала выполните:

🚀 Создать прогнозы тура
"""



        if isinstance(
            target,
            Message
        ):


            await target.answer(
                text
            )


        else:


            await target.message.edit_text(
                text
            )


        return





    total = len(
        predictions
    )



    if index < 0:

        index = 0



    if index >= total:

        index = total - 1





    prediction = predictions[index]



    text = format_match(
        prediction,
        index,
        total
    )



    keyboard = faj_navigation_keyboard(
        index,
        total
    )




    if isinstance(
        target,
        Message
    ):


        await target.answer(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )



    else:


        await target.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )







# =====================================================
# FIRST OPEN
# =====================================================

async def cmd_faj_predictions(
        message: Message
):


    await show_prediction(
        message,
        0
    )







# =====================================================
# CALLBACKS
# =====================================================

async def faj_match_callback(
        callback: CallbackQuery
):


    try:


        data = callback.data or ""



        if not data.startswith(
            "faj_"
        ):

            return






        # =============================================
        # OPEN MATCH
        # =============================================

        if data.startswith(
            "faj_open_"
        ):


            index = int(
                data.split("_")[2]
            )


            await show_prediction(
                callback,
                index
            )


            await callback.answer()

            return






        # =============================================
        # BACK TO TOUR
        # =============================================

        if data == "faj_all_matches":


            await show_predictions_list(
                callback
            )


            await callback.answer()

            return






        # =============================================
        # EMPTY BUTTON
        # =============================================

        if data == "faj_noop":

            await callback.answer()

            return







        predictions = get_predictions(
            limit=100
        )



        if not predictions:


            await callback.answer(
                "Нет прогнозов",
                show_alert=True
            )

            return





        total = len(
            predictions
        )



        parts = data.split("_")



        action = parts[1]

        index = int(
            parts[2]
        )



        if action == "next":

            index += 1



        elif action == "prev":

            index -= 1





        if index < 0:

            index = 0



        if index >= total:

            index = total - 1





        await show_prediction(
            callback,
            index
        )



        await callback.answer()





    except Exception as e:


        logger.exception(
            "FAJ callback error"
        )


        await callback.answer(
            str(e),
            show_alert=True
        )



# =====================================================
# END
# =====================================================
