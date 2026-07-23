# =====================================================
# FAJ Platform v5.2
# Load Fixtures Handler
# =====================================================


from aiogram import types

from app.loaders.rpl_loader import load_rpl_calendar

from app.handlers.keyboard import get_main_keyboard



# =====================================================
# LOAD FIXTURES COMMAND
# =====================================================


async def cmd_load_fixtures(
    message: types.Message
):

    await message.answer(
        """
⏳ Загружаю календарь РПЛ 2026/27...

Пожалуйста, подождите.
""",
        reply_markup=get_main_keyboard()
    )


    try:


        result = load_rpl_calendar()



        errors = result.get(
            "errors",
            []
        )



        await message.answer(
            f"""
✅ Календарь загружен


🏆 Лига:
{result.get('league','RPL')}


📅 Сезон:
{result.get('season','2026/27')}


⚽ Загружено матчей:
{result.get('loaded',0)}


❌ Ошибок:
{len(errors)}


Теперь доступно:

📅 Матчи

и

📈 Прогнозы по календарю
""",
            reply_markup=get_main_keyboard()
        )



    except Exception as e:


        await message.answer(
            f"""
❌ Ошибка загрузки календаря


Тип:
{type(e).__name__}


Ошибка:
{str(e)}
""",
            reply_markup=get_main_keyboard()
        )
