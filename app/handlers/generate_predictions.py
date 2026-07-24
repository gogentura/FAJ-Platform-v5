# =====================================================
# FAJ Platform v6.0
# Generate Predictions Handler
# Admin FAJ Prediction Builder
# =====================================================


from aiogram import types


from app.managers.faj_prediction_generator import (
    generate_rpl_predictions
)


from app.keyboards.main import (
    main_keyboard
)




# =====================================================
# CREATE FAJ TOUR PREDICTIONS
# =====================================================


async def cmd_generate_predictions(
    message: types.Message
):


    await message.answer(

        """
⏳ FAJ создаёт прогнозы РПЛ 2026/27...


Запускаю:

• календарь
• паспорта команд
• FAJ модель
• xG расчёт
• вероятности
• точные счета


Подождите...
""",

        reply_markup=main_keyboard()

    )



    try:


        result = generate_rpl_predictions()



        generated = result.get(
            "generated",
            0
        )


        errors = result.get(
            "errors",
            []
        )


        error_text = ""



        if errors:


            error_text = "\n\nПодробности:\n"


            for error in errors:


                error_text += (

                    f"\n⚠️ {error.get('match')}\n"

                    f"{error.get('error')}\n"

                )



        await message.answer(

            f"""
✅ FAJ прогнозы созданы


🏆 Лига:
{result.get('league')}


📅 Сезон:
{result.get('season')}


⚽ Матчей обработано:
{generated}


❌ Ошибок:
{len(errors)}

{error_text}


Теперь доступно:

🤖 FAJ прогнозы

в основном меню.
""",

            reply_markup=main_keyboard()

        )



    except Exception as e:



        await message.answer(

            f"""
❌ Критическая ошибка FAJ


Тип:
{type(e).__name__}


Ошибка:
{str(e)}
""",

            reply_markup=main_keyboard()

        )
