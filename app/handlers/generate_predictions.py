# =====================================================
# FAJ Platform v6.9.3
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions Handler
# =====================================================

import logging

from aiogram.types import Message

from app.services.tour_predictor import (
    predict_tour
)

from app.keyboards.main import (
    main_keyboard
)


logger = logging.getLogger(__name__)





def confidence_badge(value):

    try:

        value=float(value)

        if value <= 1:
            value*=100


        if value >=65:
            icon="🟢"

        elif value >=50:
            icon="🟡"

        elif value >=35:
            icon="🟠"

        else:
            icon="🔴"


        return f"{icon} {value:.1f}%"

    except:

        return "⚪ -"





# =====================================================
# COMMAND
# =====================================================


async def cmd_generate_predictions(
    message: Message
):

    await message.answer(
        """
🚀 FAJ создаёт прогнозы тура...

🧠 FAJ Engine v6.9.3

🎲 Monte Carlo 10000

⏳ Подождите...
""",
        reply_markup=main_keyboard()
    )



    try:


        predictions = predict_tour(

            league="RPL",

            season="2026/27"

        )



        if not predictions:


            await message.answer(
                """
⚠️ FAJ прогнозов нет.

Проверьте:

• fixtures
• scheduled статус
• паспорта команд
• pipeline
"""
            )

            return




        # Telegram limit protection

        chunks=[]

        text="""

🤖 *FAJ ПРОГНОЗЫ*

🧠 FAJ Engine v6.9.3

🎲 Monte Carlo 10000

━━━━━━━━━━━━━━

"""



        for p in predictions:



            home=p.get(
                "home_team",
                "-"
            )


            away=p.get(
                "away_team",
                "-"
            )


            winner=p.get(
                "winner",
                "-"
            )


            score=p.get(
                "expected_score",
                "-"
            )


            xgh=p.get(
                "xg_home",
                0
            )


            xga=p.get(
                "xg_away",
                0
            )


            confidence=p.get(
                "confidence",
                0
            )



            block=f"""

⚽ *{home} — {away}*

🏆 Победа:
{winner}

🎯 Счёт:
{score}

📊 xG:
{xgh} — {xga}

🔥 Уверенность:
{confidence_badge(confidence)}

━━━━━━━━━━━━━━

"""



            if len(text)+len(block)>3500:

                chunks.append(text)

                text=block

            else:

                text+=block



        if text:

            chunks.append(text)



        for chunk in chunks:

            await message.answer(

                chunk,

                parse_mode="Markdown",

                reply_markup=main_keyboard()

            )



    except Exception as e:


        logger.exception(
            "Generate tour error"
        )


        await message.answer(

f"""
❌ FAJ ПРОГНОЗ ERROR

{type(e).__name__}

{str(e)}

"""
        )
