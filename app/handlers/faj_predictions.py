# =====================================================
# FAJ Platform v6.9.2
# app/handlers/faj_predictions.py
#
# FAJ Predictions Viewer
# Fixed Telegram length limit
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

        return "⚪ Нет данных"





def safe_json_list(value):

    if isinstance(value, list):
        return value

    return []





def quality_format(value):

    try:

        value=float(value)

        if value <= 1:
            value*=100


        if value >=80:
            return "🟢"

        elif value >=50:
            return "🟡"

        return "🔴"


    except:

        return "🔴"






# =====================================================
# SPLIT TELEGRAM MESSAGE
# =====================================================


async def send_long_message(
    message,
    text
):

    limit = 3800


    chunks=[]


    while len(text)>limit:

        part=text[:limit]

        index=part.rfind("\n")


        if index!=-1:
            part=text[:index]


        chunks.append(part)

        text=text[len(part):]



    chunks.append(text)



    for chunk in chunks:

        await message.answer(
            chunk,
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
            limit=10
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





        text="""

🤖 *FAJ ПРОГНОЗЫ*

🧠 FAJ Engine v6.9.2

🎲 Monte Carlo 10000

━━━━━━━━━━━━━━

"""





        for p in predictions:


            if p is None:
                continue



            home=p.get(
                "home_team",
                "?"
            )


            away=p.get(
                "away_team",
                "?"
            )



            score=p.get(
                "score_prediction",
                p.get(
                    "expected_score",
                    "-"
                )
            )



            xg_home=p.get(
                "xg_home",
                0
            )


            xg_away=p.get(
                "xg_away",
                0
            )



            confidence=p.get(
                "confidence",
                0
            )



            winner=p.get(
                "winner",
                "-"
            )



            text+=f"""

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

"""



        text += """

📈 FAJ Learning Layer

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
