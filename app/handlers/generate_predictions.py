# =====================================================
# FAJ Platform v6.5
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions Handler
# =====================================================


import logging


from aiogram.types import Message


from app.services.tour_predictor import (
    predict_tour
)


from app.handlers.keyboard import (
    get_main_keyboard
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
# FORMAT %
# =====================================================


def format_percent(

    value

):


    try:


        value = float(value)



        if value <= 1:

            value *= 100



        return f"{value:.1f}%"



    except Exception:


        return "Нет данных"







# =====================================================
# CREATE TOUR
# =====================================================


async def cmd_generate_predictions(

    message: Message

):


    await message.answer(

        """
🚀 FAJ начинает анализ тура...


Проверяем:

📅 календарь матчей

📁 паспорта команд

📊 xG модель

🧠 FAJ Core

🎲 Monte Carlo 10000

⚠️ Risk Engine


Пожалуйста, подождите...
        """,

        reply_markup=get_main_keyboard()

    )



    try:



        predictions = predict_tour(

            league="RPL",

            season="2026/27"

        )



        if not predictions:



            await message.answer(

                """
⚠️ FAJ не нашёл матчей для анализа.


Проверь:

• календарь fixtures

• статус scheduled

• сезон 2026/27

• загрузку паспортов

                """,

                reply_markup=get_main_keyboard()

            )


            return





        text = """

🏆 *FAJ ПРОГНОЗЫ ТУРА*

🏟 Лига: RPL

🧠 FAJ Engine v6.5

🎲 Monte Carlo: 10000

━━━━━━━━━━━━━━

"""



        for prediction in predictions:



            home = prediction.get(

                "home_team",

                "?"

            )


            away = prediction.get(

                "away_team",

                "?"

            )



            winner = prediction.get(

                "winner",

                "Нет"

            )



            score = prediction.get(

                "expected_score",

                "-"

            )



            confidence = prediction.get(

                "confidence",

                0

            )



            risk = prediction.get(

                "risk",

                "Нет данных"

            )



            grade = prediction.get(

                "grade",

                "C"

            )



            home_rating = prediction.get(

                "home_rating",

                0

            )


            away_rating = prediction.get(

                "away_rating",

                0

            )



            xg_home = prediction.get(

                "xg_home",

                "-"

            )


            xg_away = prediction.get(

                "xg_away",

                "-"

            )



            text += f"""

⚽ *{home} — {away}*


🏆 Победа:
{winner}


🎯 Счёт:

{safe_value(score)}


📊 xG:

{xg_home} — {xg_away}


🎯 Уверенность:

{format_percent(confidence)}


🧠 FAJ Rating:

{home_rating} — {away_rating}


⚠️ Риск:

{risk}


🏷 Категория:

{grade}


──────────────

"""




        text += """

✅ Прогнозы сохранены в FAJ Journal


Теперь система сможет:

📊 сравнить факт с прогнозом

🧠 найти ошибки модели

📈 улучшать FAJ Core

"""



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=get_main_keyboard()

        )




    except Exception as e:



        logger.exception(

            "Generate predictions error"

        )


        await message.answer(

            f"""
❌ Ошибка создания прогнозов тура


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

""",

            reply_markup=get_main_keyboard()

        )
