# =====================================================
# FAJ Platform v6.0
# Expert Predictions Handler
# =====================================================


from aiogram import types


from app.managers.expert_manager import (
    get_expert_predictions
)


from app.keyboards.main import (
    main_keyboard
)



# =====================================================
# SHOW EXPERT PREDICTIONS
# =====================================================


async def cmd_expert_predictions(
    message: types.Message
):


    try:


        predictions = get_expert_predictions(

            league="RPL",

            season="2026/27"

        )



        if not predictions:


            await message.answer(

                """
🧠 Мои прогнозы


Экспертные прогнозы пока не добавлены.


Добавьте прогноз через:

⚙️ Админ
↓
🧠 Создать мой прогноз


Они будут идти отдельно от FAJ модели.


Не влияют на обучение модели.
""",

                reply_markup=main_keyboard()

            )


            return




        text = """

🧠 Мои прогнозы

🏆 РПЛ 2026/27


"""



        for item in predictions[:10]:


            text += (

                "──────────────\n"

                f"⚽ {item.get('home_team','-')} — "
                f"{item.get('away_team','-')}\n\n"

                f"🎯 Мой счёт: "
                f"{item.get('score_prediction','-')}\n\n"

                f"🏁 Исход: "
                f"{item.get('winner_prediction','-')}\n\n"

                f"🔥 Уверенность: "
                f"{item.get('confidence','-')}/10\n\n"

                f"💬 Комментарий:\n"
                f"{item.get('comment','-')}\n\n"

            )



        await message.answer(

            text,

            reply_markup=main_keyboard()

        )



    except Exception as e:



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
