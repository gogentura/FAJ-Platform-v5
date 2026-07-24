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


    except:


        return 0




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


После этого здесь появятся:

• вероятности
• xG
• точные счета
• Confidence
• версия модели
""",

                reply_markup=main_keyboard()

            )


            return




        text = (

            "🤖 *FAJ прогнозы РПЛ 2026/27*\n\n"

            "🧠 Модель: FAJ v6.0\n"

        )



        for item in predictions[:8]:


            text += (

                "\n━━━━━━━━━━━━━━\n"

                f"⚽ *{item.get('home_team')} — "
                f"{item.get('away_team')}*\n\n"

            )



            text += (

                f"📅 Тур: {item.get('round','-')}\n"

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

                f"🔥 Confidence: "

                f"{item.get('confidence','-')}%\n\n"

            )



            text += (

                f"⚽ ОЗ: "

                f"{format_probability(item.get('btts_probability'))}%\n"

            )



            text += (

                f"⚽ Тотал 2.5: "

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
