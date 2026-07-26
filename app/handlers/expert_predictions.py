# =====================================================
# FAJ Platform v6.5
# app/handlers/expert_predictions.py
#
# Expert Prediction Layer
# =====================================================


import logging


from aiogram import types


from app.database import get_db


from app.keyboards.main import (
    main_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# EXPERT BASELINE
#
# Эксперт Марк
# FAJ Expert Layer v1
# =====================================================


EXPERT_PREDICTIONS = {


    "ЦСКА - Балтика":

    {
        "score": "1-0",
        "winner": "ЦСКА"
    },


    "Динамо М - Крылья Советов":

    {
        "score": "3-1",
        "winner": "Динамо М"
    },


    "Акрон - Зенит":

    {
        "score": "0-2",
        "winner": "Зенит"
    },


    "Факел - Динамо Мх":

    {
        "score": "1-0",
        "winner": "Факел"
    },


    "Спартак - Родина":

    {
        "score": "3-0",
        "winner": "Спартак"
    },


    "Оренбург - Ростов":

    {
        "score": "2-1",
        "winner": "Оренбург"
    },


    "Локомотив - Ахмат":

    {
        "score": "2-1",
        "winner": "Локомотив"
    },


    "Рубин - Краснодар":

    {
        "score": "1-2",
        "winner": "Краснодар"
    }


}






# =====================================================
# SAVE EXPERT PREDICTION
# =====================================================


def save_expert_prediction(

    match,

    prediction,

    league="RPL",

    season="2026/27"

):


    try:


        conn = get_db()

        cur = conn.cursor()



        cur.execute(

            """

            INSERT INTO expert_predictions

            (

            match,

            league,

            season,

            predicted_score,

            predicted_winner

            )


            VALUES

            (%s,%s,%s,%s,%s)


            ON CONFLICT (match,season)

            DO UPDATE SET


            predicted_score =
            EXCLUDED.predicted_score,


            predicted_winner =
            EXCLUDED.predicted_winner

            """,

            (

                match,

                league,

                season,

                prediction["score"],

                prediction["winner"]

            )

        )



        conn.commit()


        cur.close()

        conn.close()



        return True



    except Exception as e:


        logger.error(

            "Expert save error: %s",

            e,

            exc_info=True

        )


        return False







# =====================================================
# GENERATE EXPERT PREDICTIONS
# =====================================================


async def cmd_expert_predictions(

    message: types.Message

):


    try:



        saved = 0



        for match, prediction in EXPERT_PREDICTIONS.items():


            if save_expert_prediction(

                match,

                prediction

            ):

                saved += 1





        text = """

🧠 *FAJ EXPERT LAYER*


Экспертские прогнозы сохранены.


Версия:

FAJ Expert Baseline v1


━━━━━━━━━━━━━━


"""



        for match, prediction in EXPERT_PREDICTIONS.items():


            text += f"""

⚽ {match}


🎯 Счёт:

{prediction["score"]}


🏆 Победа:

{prediction["winner"]}


──────────────

"""



        text += f"""

✅ Сохранено:

{saved}

матчей


Теперь FAJ сможет:


📊 сравнить модель и эксперта

🧠 определить сильные стороны

📈 обучить калибровку модели

"""



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )




    except Exception as e:


        logger.exception(

            "Expert handler error"

        )


        await message.answer(

            f"""

❌ Ошибка экспертских прогнозов


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

""",

            reply_markup=main_keyboard()

        )
