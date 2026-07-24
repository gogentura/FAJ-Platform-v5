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




        text = """

🤖 FAJ прогнозы

🏆 РПЛ 2026/27


"""



        for item in predictions[:10]:


            text += (

                "──────────────\n"

                f"⚽ {item.get('home_team')} — "
                f"{item.get('away_team')}\n\n"

                f"🎯 Счёт: "
                f"{item.get('expected_score','-')}\n\n"

                "📊 Вероятности:\n"

                f"П1: {item.get('home_probability',0)}%\n"

                f"X: {item.get('draw_probability',0)}%\n"

                f"П2: {item.get('away_probability',0)}%\n\n"

                f"📈 xG: "
                f"{item.get('xg_home','-')} - "
                f"{item.get('xg_away','-')}\n\n"

                f"🔥 Confidence: "
                f"{item.get('confidence','-')}%\n\n"

            )



        await message.answer(

            text,

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
