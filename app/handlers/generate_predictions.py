# =====================================================
# FAJ Platform v6.9.2
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions Handler
#
# Compatible:
# - FAJCore v6.8+
# - prediction_pipeline v6.9.2
# - tour_predictor v6.9.2
# - PostgreSQL
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
# CONFIDENCE BADGE
# =====================================================


def confidence_badge(

    value

):

    try:

        value = float(value)



        if value <= 1:

            value *= 100



        if value >= 70:

            icon = "🟢"


        elif value >= 50:

            icon = "🟡"


        elif value >= 35:

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


def quality_format(

    value

):

    try:

        value=float(value)



        # если уже проценты

        if value > 1:

            percent=value

        else:

            percent=value*100



        if percent >= 80:

            return f"🟢 {percent:.0f}%"


        elif percent >= 50:

            return f"🟡 {percent:.0f}%"


        else:

            return f"🔴 {percent:.0f}%"



    except Exception:

        return "🔴 0%"







# =====================================================
# WINNER NORMALIZER
# =====================================================


def normalize_winner(

    prediction

):


    winner = prediction.get(

        "winner_name"

    )



    if winner:

        return winner



    code = prediction.get(

        "winner",

        "-"

    )



    if code == "home":

        return "Хозяева"



    if code == "away":

        return "Гости"



    if code == "draw":

        return "Ничья"



    return "-"








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

🧠 FAJ Core v6.9.2

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
⚠️ Нет прогнозов


Проверить:

• fixtures

• сезон

• паспорта команд

• статус матчей


/debug_fixtures

/debug_prediction команда1 команда2

""",

reply_markup=main_keyboard()

)


            return





        text = """

🏆 *FAJ ПРОГНОЗЫ ТУРА*

🏟 RPL

🧠 FAJ Engine v6.9.2

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



            winner = normalize_winner(

                prediction

            )



            score = prediction.get(

                "expected_score",

                prediction.get(

                    "score",

                    "-"

                )

            )



            confidence = prediction.get(

                "confidence",

                0

            )



            rating_home = prediction.get(

                "home_rating",

                0

            )


            rating_away = prediction.get(

                "away_rating",

                0

            )



            xg_home = prediction.get(

                "xg_home",

                0

            )


            xg_away = prediction.get(

                "xg_away",

                0

            )



            quality = prediction.get(

                "passport_quality",

                prediction.get(

                    "data_quality",

                    {

                        "home":0,

                        "away":0

                    }

                )

            )



            factors = prediction.get(

                "factors",

                []

            )



            category = prediction.get(

                "grade",

                prediction.get(

                    "category",

                    "C"

                )

            )





            text += f"""

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

{prediction.get(
    "season_phase",
    "start"
)}


📁 Качество данных:

🏠 {quality_format(
    quality.get(
        "home",
        0
    )
)}

🚩 {quality_format(
    quality.get(
        "away",
        0
    )
)}


⚠️ Риск:

{prediction.get(
    "risk",
    "Высокий"
)}


🏷 Категория:

{category}



"""



            if factors:


                text += "\n🧠 Факторы:\n"


                for factor in factors:


                    text += (

                        f"\n• {factor}"

                    )



            text += (

                "\n\n──────────────\n"

            )







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


        logger.exception(

            "Generate predictions error"

        )


        await message.answer(

f"""
❌ Ошибка FAJ генерации


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

""",

reply_markup=main_keyboard()

)
