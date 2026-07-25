# =====================================================
# FAJ Platform v6.4
# app/handlers/generate_predictions.py
#
# Generate Tour Predictions Handler
# =====================================================


import logging


from aiogram.types import Message


from app.services.tour_predictor import (
    predict_tour
)



logger = logging.getLogger(__name__)



# =====================================================
# CREATE TOUR PREDICTIONS
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

🎯 вероятности счёта

📈 рейтинг команд


Пожалуйста, подождите...
        """

    )



    try:



        predictions = predict_tour()



        if not predictions:


            await message.answer(

                """
⚠️ FAJ не нашёл матчей для анализа.


Проверь:

• календарь fixtures

• статус матчей

• сезон

• загрузку паспортов
                """

            )


            return



        text = """

🏆 FAJ ПРОГНОЗЫ ТУРА

🏟 Лига: RPL

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

                "нет"

            )



            score = prediction.get(

                "expected_score",

                "-"

            )



            confidence = prediction.get(

                "confidence"

            )


            if confidence is None:

                confidence_text = "Нет данных"

            else:

                confidence_text = (
                    f"{float(confidence):.1f}%"
                )



            risk = prediction.get(

                "risk",

                "Нет данных"

            )


            grade = prediction.get(

                "grade",

                "Нет данных"

            )



            home_rating = prediction.get(

                "home_rating"

            )


            away_rating = prediction.get(

                "away_rating"

            )



            if home_rating is None:

                rating_text = "Нет данных"

            else:

                rating_text = (

                    f"{home_rating:.1f}"
                    " — "
                    f"{away_rating:.1f}"

                )



            text += f"""

⚽ {home} — {away}


🏆 Победа: {winner}


🎯 Счёт:
{score}


🎯 Уверенность:
{confidence_text}


🧠 FAJ Rating:
{rating_text}


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

            text

        )



    except Exception as e:



        logger.exception(e)



        await message.answer(

            f"""

❌ Ошибка создания прогнозов тура


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )
