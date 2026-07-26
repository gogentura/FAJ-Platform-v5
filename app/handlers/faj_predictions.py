# =====================================================
# FAJ Platform v6.5
# app/handlers/faj_predictions.py
#
# FAJ Predictions Viewer
# PostgreSQL version
# =====================================================


import logging


from aiogram import types


from app.managers.prediction_manager import (
    get_predictions
)


from app.managers.passport_analysis import (
    format_passport_block
)


from app.keyboards.main import (
    main_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# FORMAT %
# =====================================================


def format_probability(value):

    try:

        value = float(value)


        if value <= 1:

            value *= 100


        return round(
            value,
            1
        )


    except Exception:

        return 0





# =====================================================
# CONFIDENCE
# =====================================================


def confidence_label(value):

    try:

        value = float(value)


        if value >= 75:

            return "🟢 Высокая"


        elif value >= 60:

            return "🟡 Средняя"


        else:

            return "🔴 Низкая"


    except Exception:

        return "⚪ Нет данных"






# =====================================================
# SAFE GET
# =====================================================


def safe_get(

    item,

    key,

    default="-"

):


    value = item.get(

        key

    )


    if value is None:

        return default


    return value





# =====================================================
# FAJ PREDICTIONS
# =====================================================


async def cmd_faj_predictions(

    message: types.Message

):


    try:



        predictions = get_predictions(

            league="RPL",

            season="2026/27"

        )



        if not predictions:


            await message.answer(

                """
🤖 FAJ ПРОГНОЗЫ


Прогнозы пока отсутствуют.


Запусти:

⚙️ Админ панель

↓

🚀 Создать прогнозы тура


После этого появятся:

• xG анализ

• FAJ Rating

• вероятности

• точный счёт

• риск

• категория

""",

                reply_markup=main_keyboard()

            )


            return





        text = """

🏆 *FAJ ПРОГНОЗЫ РПЛ*

🧠 FAJ Engine v6.5

🎲 Monte Carlo: 10000

📊 xG + Team Passport

━━━━━━━━━━━━━━

"""



        for item in predictions[:10]:


            home = safe_get(

                item,

                "home_team"

            )


            away = safe_get(

                item,

                "away_team"

            )



            text += f"""

⚽ *{home} — {away}*

"""



            # паспорт

            try:


                text += format_passport_block(

                    home,

                    away

                )


                text += "\n"


            except Exception:


                pass




            text += f"""

📊 Вероятности:


🏠 П1:
{format_probability(
    safe_get(item,"home_probability",0)
)}%


🤝 X:
{format_probability(
    safe_get(item,"draw_probability",0)
)}%


🚩 П2:
{format_probability(
    safe_get(item,"away_probability",0)
)}%



📈 xG:

{safe_get(item,"xg_home")} -
{safe_get(item,"xg_away")}



🎯 Ожидаемый счёт:

*{safe_get(
    item,
    "expected_score"
)}*



🔥 Уверенность:

{format_probability(
    safe_get(item,"confidence",0)
)}%

{confidence_label(
    safe_get(item,"confidence",0)
)}



⚠️ Риск:

{safe_get(
    item,
    "risk",
    "Нет данных"
)}



🏷 Категория:

{safe_get(
    item,
    "grade",
    "C"
)}



━━━━━━━━━━━━━━

"""





        text += """

✅ FAJ Journal обновлён


После завершения матчей система сможет:


📊 сравнить прогноз и факт

🧠 найти ошибки

📈 откалибровать FAJ Core


"""



        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )





    except Exception as e:



        logger.exception(

            "FAJ predictions handler error"

        )


        await message.answer(

            f"""
❌ Ошибка FAJ прогнозов


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

""",

            reply_markup=main_keyboard()

        )
