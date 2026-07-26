# =====================================================
# FAJ Platform v6.7
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions Handler
#
# FAJ Pipeline + Journal + Calibration Ready
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
# SAFE
# =====================================================


def safe_value(
    value,
    default="-"
):

    if value is None:

        return default


    return str(value)





def format_percent(value):

    try:

        value=float(value or 0)


        if value <= 1:

            value*=100


        return f"{value:.1f}%"



    except Exception:

        return "0%"






# =====================================================
# GENERATE TOUR
# =====================================================


async def cmd_generate_predictions(

    message: Message

):


    await message.answer(

        """
🚀 FAJ запускает прогноз тура


Версия:

🧠 FAJ Engine v6.7


Модули:

📁 Team Passport

📊 xG Engine

🎲 Monte Carlo 10000

🧠 Expert Layer

⚠️ Risk Engine

📈 Calibration Ready


Ожидайте...
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
⚠️ Нет прогнозов


Проверь:

• fixtures

• сезон

• паспорта команд

• статус матчей

""",

                reply_markup=main_keyboard()

            )


            return




        text = """

🏆 *FAJ ПРОГНОЗЫ ТУРА*

🏟 Лига: RPL

🧠 FAJ Engine v6.7

🎲 Monte Carlo: 10000

━━━━━━━━━━━━━━

"""



        for prediction in predictions:


            if not prediction:

                continue



            home=safe_value(

                prediction.get(
                    "home_team"
                )

            )


            away=safe_value(

                prediction.get(
                    "away_team"
                )

            )


            winner=safe_value(

                prediction.get(
                    "winner"
                )

            )


            score=safe_value(

                prediction.get(
                    "expected_score"
                )

            )


            confidence=format_percent(

                prediction.get(
                    "confidence"
                )

            )


            risk=safe_value(

                prediction.get(
                    "risk",
                    "Средний"

                )

            )


            grade=safe_value(

                prediction.get(
                    "grade",
                    "C"

                )

            )


            xg_home=safe_value(

                prediction.get(
                    "xg_home",
                    0

                )

            )


            xg_away=safe_value(

                prediction.get(
                    "xg_away",
                    0

                )

            )


            rating_home=safe_value(

                prediction.get(
                    "home_rating",
                    0

                )

            )


            rating_away=safe_value(

                prediction.get(
                    "away_rating",
                    0

                )

            )


            factors=prediction.get(

                "factors",

                []

            )



            factor_text=""


            if factors:


                factor_text="\n".join(

                    [

                        f"• {str(x)}"

                        for x in factors[:3]

                        if x is not None

                    ]

                )




            text += f"""

⚽ *{home} — {away}*


🏆 Победа:

{winner}


🎯 Счёт:

{score}


📊 xG:

{xg_home} — {xg_away}


🔥 Уверенность:

{confidence}


🧠 FAJ Rating:

{rating_home} — {rating_away}


⚠️ Риск:

{risk}


🏷 Категория:

{grade}


🧠 Факторы:

{factor_text}


──────────────

"""




        text += """

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


        logger.exception(e)



        await message.answer(

            f"""
❌ Ошибка генерации тура FAJ


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

""",

            reply_markup=main_keyboard()

        )
