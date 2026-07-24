# =====================================================
# FAJ Platform v6.0
# FAJ Predictions Handler
# =====================================================


from aiogram import types


from app.managers.prediction_manager import (
    get_predictions
)


from app.keyboards.main import (
    main_keyboard
)




# =====================================================
# FORMAT PROBABILITY
# =====================================================


def format_probability(value):

    try:

        value = float(value)


        if value <= 1:

            value *= 100


        return round(value, 1)


    except Exception:

        return 0




# =====================================================
# CONFIDENCE LABEL
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
# SHOW FAJ PREDICTIONS
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
🤖 FAJ прогнозы


Прогнозы модели пока не созданы.


Сначала:

⚙️ Админ
↓
🚀 Создать прогнозы тура


После этого появятся:

• вероятности
• xG
• точные счета
• надёжность прогноза
• версия модели
""",

                reply_markup=main_keyboard()

            )


            return




        text = (

            "🤖 *FAJ прогнозы РПЛ 2026/27*\n\n"

            "🧠 Модель: FAJ Engine v6.0\n"

            "🎲 Симуляция: Monte Carlo 10000\n"

            "📊 Метод: xG + Team Passport\n\n"

        )



        for item in predictions[:8]:


            confidence = item.get(
                "confidence",
                0
            )



            text += (

                "\n━━━━━━━━━━━━━━\n"

                f"⚽ *{item.get('home_team')} — "
                f"{item.get('away_team')}*\n\n"

                f"📅 Тур: {item.get('round','-')}\n\n"

            )



            text += (

                "📊 Вероятности:\n"

                f"🏠 П1: "
                f"{format_probability(item.get('home_probability'))}%\n"

                f"🤝 X: "
                f"{format_probability(item.get('draw_probability'))}%\n"

                f"🚩 П2: "
                f"{format_probability(item.get('away_probability'))}%\n\n"

            )



            text += (

                f"📈 xG: "

                f"{item.get('xg_home','-')} - "

                f"{item.get('xg_away','-')}\n\n"

            )



            text += (

                f"🎯 Ожидаемый счёт: "

                f"*{item.get('expected_score','-')}*\n\n"

            )



            text += (

                f"🔥 Надёжность прогноза: "

                f"{confidence}%\n"

                f"{confidence_label(confidence)}\n\n"

            )



            text += (

                f"⚽ Обе забьют: "

                f"{format_probability(item.get('btts_probability'))}%\n"

            )



            text += (

                f"⚽ Тотал больше 2.5: "

                f"{format_probability(item.get('over25_probability'))}%\n"

            )





        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )




    except Exception as e:



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
