# =====================================================
# FAJ Platform v6.7
# app/handlers/predict.py
#
# Single Match Prediction Handler
# =====================================================


import logging


from aiogram.types import Message


from app.services.prediction_pipeline import (
    prediction_pipeline
)


from app.journal import Journal


logger = logging.getLogger(__name__)





# =====================================================
# FORMAT %
# =====================================================


def format_percent(value):

    try:

        value = float(value)

        if value <= 1:
            value *= 100

        return f"{value:.1f}%"

    except Exception:

        return "Нет данных"






# =====================================================
# HANDLE PREDICT
# =====================================================


async def handle_predict(

    message: Message,

    core=None,

    journal=None

):


    try:


        text = (

            message.text

            .replace(
                "прогноз",
                ""
            )

            .replace(
                "Прогноз",
                ""
            )

            .strip()

        )



        parts = text.split()



        if len(parts) < 2:


            await message.answer(

                """
⚽ FAJ Прогноз

Формат:

Акрон Зенит

или:

прогноз Акрон Зенит
"""

            )

            return





        home = parts[0]

        away = " ".join(parts[1:])



        await message.answer(

            f"""
🧠 FAJ анализ матча

⚽ {home} — {away}

Проверяю:

📁 Team Passport
📊 xG модель
🧠 FAJ Rating
🎲 Monte Carlo 10000
⚠️ Risk Engine

Подождите...
"""

        )





        # =================================================
        # PIPELINE
        # =================================================


        result = prediction_pipeline.predict_match(

            home,

            away,

            "RPL",

            "2026/27"

        )



        if not result:


            await message.answer(

                "❌ FAJ Pipeline вернул пустой результат"

            )

            return





        decision = result.get(

            "decision",

            {}

        )



        xg = result.get(

            "xg",

            {}

        ).get(

            "predicted",

            {}

        )



        simulation = result.get(

            "simulation",

            {}

        )





        # =================================================
        # JOURNAL
        # =================================================


        if journal:


            try:

                journal.add_prediction(

                    result

                )


            except Exception:


                logger.warning(

                    "Journal save skipped",

                    exc_info=True

                )







        # =================================================
        # OUTPUT
        # =================================================


        answer = f"""

✅ FAJ PIPELINE OK


⚽ {home} — {away}


━━━━━━━━━━━━━━


🏆 Победитель:

{decision.get('winner_name','Нет данных')}


🎯 Счёт:

{decision.get('expected_score','-')}


━━━━━━━━━━━━━━


📊 xG:

{xg.get('home',0)}

-

{xg.get('away',0)}



🧠 FAJ Rating:

{decision.get('home_rating','-')}

-

{decision.get('away_rating','-')}



━━━━━━━━━━━━━━


🔥 Уверенность:

{format_percent(

    decision.get(
        'confidence',
        0
    )

)}


⚠️ Риск:

{decision.get(

    'risk',

    'Средний'

)}


🏷 Категория:

{decision.get(

    'grade',

    'C'

)}



━━━━━━━━━━━━━━


🧠 Факторы:

"""



        factors = decision.get(

            "factors",

            []

        )



        if factors:


            for factor in factors:

                answer += f"\n• {factor}"


        else:


            answer += "\n• Анализ факторов доступен в FAJ Core"





        await message.answer(

            answer

        )






    except Exception as e:


        logger.error(

            "Prediction handler error",

            exc_info=True

        )


        await message.answer(

            f"""
❌ FAJ ERROR


Тип:

{type(e).__name__}


Ошибка:

{str(e)}
"""

        )
