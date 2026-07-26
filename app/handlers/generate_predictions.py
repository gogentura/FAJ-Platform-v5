# =====================================================
# FAJ Platform v6.8
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





# =====================================================
# SAFE VALUE
# =====================================================


def safe_value(
    value,
    default="-"
):

    if value is None:
        return default

    return value






# =====================================================
# CONFIDENCE FORMAT
# =====================================================


def confidence_badge(value):

    try:

        value = float(value)


        if value <= 1:

            value *= 100



        if value >= 65:

            icon = "🟢"


        elif value >=45:

            icon = "🟡"


        elif value >=30:

            icon = "🟠"


        else:

            icon = "🔴"



        return (
            f"{icon} {value:.1f}%"
        )


    except Exception:

        return "⚪ Нет данных"








# =====================================================
# QUALITY FORMAT
# =====================================================


def quality_format(value):


    try:

        value=float(value)


        percent=value*100



        if percent>=80:

            return f"🟢 {percent:.0f}%"


        elif percent>=50:

            return f"🟡 {percent:.0f}%"


        else:

            return f"🔴 {percent:.0f}%"



    except:

        return "Нет данных"







# =====================================================
# MAIN COMMAND
# =====================================================


async def cmd_generate_predictions(

    message: Message

):


    await message.answer(

"""
🚀 FAJ создаёт прогнозы тура...


Проверяем:

📅 Fixtures

📁 Team Passport

📊 xG Engine

🧠 FAJ Core v6.7.1

🎲 Monte Carlo 10000

⚠️ Risk Engine


Подождите...
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
⚠️ FAJ не получил прогнозы.


Проверить:

• fixtures
• сезон
• паспорта
• статус scheduled

/debug_fixtures

/debug_prediction команда1 команда2

""",

reply_markup=main_keyboard()

)

            return





        text=f"""
🏆 *FAJ ПРОГНОЗЫ ТУРА*

🏟 RPL

🧠 FAJ Engine v6.8

🎲 Monte Carlo: 10000

━━━━━━━━━━━━━━

"""




        for p in predictions:



            home=p.get(
                "home_team",
                "?"
            )


            away=p.get(
                "away_team",
                "?"
            )


            decision=p.get(
                "decision",
                {}
            )



            winner=decision.get(
                "winner_name",
                "-"
            )


            score=decision.get(
                "expected_score",
                "-"
            )



            confidence=decision.get(
                "confidence",
                p.get(
                    "confidence",
                    0
                )
            )



            rating_home=p.get(
                "home_rating",
                decision.get(
                    "home_rating",
                    "-"
                )
            )


            rating_away=p.get(
                "away_rating",
                decision.get(
                    "away_rating",
                    "-"
                )
            )



            xg_home=p.get(
                "xg_home",
                "-"
            )


            xg_away=p.get(
                "xg_away",
                "-"
            )



            phase=p.get(
                "season_phase",
                "-"
            )



            quality=p.get(
                "passport_quality",
                {}
            )



            factors=p.get(
                "factors",
                []
            )



            text+=f"""

⚽ *{home} — {away}*


🏆 Победа:

{winner}


🎯 Счёт:

{score}


📊 xG:

{xg_home} — {xg_away}


🎯 Уверенность:

{confidence_badge(confidence)}


🧠 FAJ Rating:

{rating_home} — {rating_away}


📅 Фаза сезона:

{phase}


📁 Качество данных:

🏠 {quality_format(
quality.get("home",0)
)}

🚩 {quality_format(
quality.get("away",0)
)}


⚠️ Риск:

{p.get(
"risk",
"Средний"
)}


🏷 Категория:

{p.get(
"grade",
"C"
)}


"""



            if factors:


                text+="\n🧠 Факторы:\n"


                for f in factors:

                    text+=f"\n• {f}"



            text+="\n\n──────────────\n"





        text+="""

✅ Прогнозы сохранены


FAJ Learning Layer:

📊 сравнение факт/прогноз

🧠 поиск ошибок

📈 Calibration Layer

🚀 улучшение FAJ Core

"""



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )




    except Exception as e:


        logger.exception(

            "Generate tour error"

        )


        await message.answer(

f"""
❌ Ошибка FAJ генерации


{type(e).__name__}


{str(e)}

""",

reply_markup=main_keyboard()

)
