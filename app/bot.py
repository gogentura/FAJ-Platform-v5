# =====================================================
# FAJ Platform v6.1
# app/bot.py
# =====================================================


import logging


from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


from app.config import Config


from app.core.faj_core import FAJCore


from app.journal import Journal



# =====================================================
# HANDLERS
# =====================================================


from app.handlers.start import cmd_start

from app.handlers.predict import handle_predict

from app.handlers.journal import cmd_journal

from app.handlers.status import cmd_status

from app.handlers.health import cmd_health

from app.handlers.load_passports import cmd_load_passports

from app.handlers.database_check import cmd_dbcheck


from app.handlers.passport import (
    cmd_passport,
    button_passport
)


from app.handlers.fixtures import cmd_fixtures


from app.handlers.load_fixtures import (
    cmd_load_fixtures
)


from app.handlers.fixtures_check import (
    cmd_fixtures_check
)


from app.handlers.update_calendar import (
    cmd_update_calendar
)


from app.handlers.faj_predictions import (
    cmd_faj_predictions
)


from app.handlers.expert_predictions import (
    cmd_expert_predictions
)


from app.handlers.generate_predictions import (
    cmd_generate_predictions
)



# =====================================================
# KEYBOARDS
# =====================================================


from app.keyboards.main import (
    main_keyboard
)


from app.keyboards.admin import (
    admin_keyboard
)



logger = logging.getLogger(__name__)




# =====================================================
# SERVICE BUTTONS
# =====================================================


SERVICE_BUTTONS = {


    "📊 Статус",

    "📈 Прогноз",

    "📁 Паспорта",

    "📅 Матчи",

    "🤖 FAJ прогнозы",

    "🧠 Мои прогнозы",

    "🏆 Турниры",

    "📋 Журнал",

    "⚙️ Админ",

    "❤️ Проверка",


    "📥 Загрузить паспорта",

    "📥 Загрузить календарь",

    "🔄 Синхронизировать календарь",

    "🔍 Проверить календарь",

    "🚀 Создать прогнозы тура",

    "🗄 Проверка базы",

    "⬅️ Главное меню"

}




# =====================================================
# RUN BOT
# =====================================================


async def run_bot(
    core: FAJCore,
    journal: Journal
):


    if not Config.TELEGRAM_TOKEN:


        logger.error(
            "TELEGRAM_TOKEN отсутствует"
        )

        return




    bot = Bot(
        token=Config.TELEGRAM_TOKEN
    )



    dp = Dispatcher()




    # =================================================
    # COMMANDS
    # =================================================


    dp.message.register(
        cmd_start,
        Command("start")
    )


    dp.message.register(
        cmd_status,
        Command("статус")
    )


    dp.message.register(
        cmd_journal,
        Command("журнал")
    )


    dp.message.register(
        cmd_health,
        Command("проверка")
    )


    dp.message.register(
        cmd_dbcheck,
        Command("база")
    )


    dp.message.register(
        cmd_load_passports,
        Command("загрузить_паспорта")
    )


    # резервная загрузка
    dp.message.register(
        cmd_load_fixtures,
        Command("загрузить_календарь")
    )


    # проверка базы fixtures
    dp.message.register(
        cmd_fixtures_check,
        Command("fixtures_check")
    )


    # синхронизация календаря
    dp.message.register(
        cmd_update_calendar,
        Command("update_calendar")
    )




    # =================================================
    # MAIN MENU
    # =================================================


    @dp.message(
        lambda m:
        m.text == "📊 Статус"
    )
    async def status_button(
        message: Message
    ):

        await cmd_status(message)



    @dp.message(
        lambda m:
        m.text == "📋 Журнал"
    )
    async def journal_button(
        message: Message
    ):

        await cmd_journal(message)



    @dp.message(
        lambda m:
        m.text == "❤️ Проверка"
    )
    async def health_button(
        message: Message
    ):

        await cmd_health(message)




    @dp.message(
        lambda m:
        m.text == "📁 Паспорта"
    )
    async def passport_button(
        message: Message
    ):

        await button_passport(message)




    @dp.message(
        lambda m:
        m.text == "📅 Матчи"
    )
    async def fixtures_button(
        message: Message
    ):

        await cmd_fixtures(message)




    # =================================================
    # PREDICTIONS
    # =================================================


    @dp.message(
        lambda m:
        m.text == "🤖 FAJ прогнозы"
    )
    async def faj_predictions_button(
        message: Message
    ):

        await cmd_faj_predictions(message)




    @dp.message(
        lambda m:
        m.text == "🧠 Мои прогнозы"
    )
    async def expert_predictions_button(
        message: Message
    ):

        await cmd_expert_predictions(message)




    # =================================================
    # ADMIN
    # =================================================


    @dp.message(
        lambda m:
        m.text == "⚙️ Админ"
    )
    async def admin_button(
        message: Message
    ):


        await message.answer(

            """
⚙️ Админ FAJ v6.1


Выберите действие:


📥 Загрузить паспорта

🔄 Синхронизировать календарь

🔍 Проверить календарь

🚀 Создать прогнозы тура

🗄 Проверка базы
""",

            reply_markup=admin_keyboard()

        )




    @dp.message(
        lambda m:
        m.text == "🔄 Синхронизировать календарь"
    )
    async def sync_calendar_button(
        message: Message
    ):

        await cmd_update_calendar(message)




    @dp.message(
        lambda m:
        m.text == "🔍 Проверить календарь"
    )
    async def check_calendar_button(
        message: Message
    ):

        await cmd_fixtures_check(message)




    @dp.message(
        lambda m:
        m.text == "🚀 Создать прогнозы тура"
    )
    async def generate_predictions_button(
        message: Message
    ):

        await cmd_generate_predictions(message)




    @dp.message(
        lambda m:
        m.text == "📥 Загрузить календарь"
    )
    async def old_calendar_loader(
        message: Message
    ):

        await cmd_load_fixtures(message)




    @dp.message(
        lambda m:
        m.text == "📥 Загрузить паспорта"
    )
    async def passport_loader(
        message: Message
    ):

        await cmd_load_passports(message)




    # =================================================
    # PASSPORT TEXT
    # =================================================


    @dp.message(
        lambda m:
        m.text
        and
        m.text.lower().startswith("паспорт")
    )
    async def passport_text(
        message: Message
    ):

        await cmd_passport(message)




    # =================================================
    # MATCH PREDICT
    # =================================================


    @dp.message(
        lambda m:

        m.text

        and

        not m.text.startswith("/")

        and

        m.text not in SERVICE_BUTTONS

        and

        (
            m.text.lower().startswith("прогноз")

            or

            len(m.text.split()) == 2

        )
    )
    async def predict_handler(
        message: Message
    ):


        await handle_predict(

            message,

            core,

            journal

        )




    # =================================================
    # DEFAULT
    # =================================================


    @dp.message()
    async def default_handler(
        message: Message
    ):


        await message.answer(

            """
⚽ FAJ Platform v6.1


📊 Статус
📈 Прогноз
📁 Паспорта
📅 Матчи
🤖 FAJ прогнозы
🧠 Мои прогнозы
🏆 Турниры
📋 Журнал
⚙️ Админ


FAJ:

• Team Passport
• xG Engine
• Monte Carlo 10000
• Calendar Monitor
• Prediction Engine
""",

            reply_markup=main_keyboard()

        )



    logger.info(
        "FAJ Platform v6.1 started"
    )



    await dp.start_polling(bot)
