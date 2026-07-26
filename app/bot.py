# =====================================================
# FAJ Platform v6.3
# app/bot.py
# =====================================================

import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Config

from app.core.faj_core import FAJCore
from app.journal import Journal, clear_journal

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

# ===== ЗАМЕНА: используем show_fixtures вместо fixtures =====
from app.handlers.show_fixtures import cmd_show_fixtures

from app.handlers.load_fixtures import cmd_load_fixtures

from app.handlers.fixtures_check import (
    cmd_fixtures_check
)

from app.handlers.update_calendar import (
    cmd_update_calendar
)

from app.handlers.update_results import (
    cmd_update_results
)

from app.handlers.clear_fixtures import (
    cmd_clear_fixtures
)

from app.handlers.faj_predictions import (
    cmd_faj_predictions
)

from app.handlers.expert_predictions import (
    cmd_expert_predictions
)

# ===== НОВЫЙ ИМПОРТ =====
from app.handlers.calibration import cmd_calibration

# ===== ВАЖНО: импорт генератора прогнозов =====
from app.handlers.generate_predictions import (
    cmd_generate_predictions
)

from app.handlers.debug_calendar import (
    cmd_debug_calendar
)

from app.handlers.debug_rpl_source import (
    cmd_debug_rpl_source
)

from app.handlers.debug_soccer365 import (
    cmd_debug_soccer365
)

# ===== НОВЫЙ ИМПОРТ (debug_results) =====
from app.handlers.debug_results import (
    cmd_debug_results
)

# ===== НОВЫЙ ИМПОРТ =====
from app.debug_prediction import cmd_debug_prediction


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
    "🧠 Анализ ошибок FAJ",

    "🏆 Турниры",
    "📋 Журнал",

    "⚙️ Админ",
    "❤️ Проверка",

    "📥 Загрузить паспорта",

    "🔄 Синхронизировать календарь",

    "🔄 Обновить результаты",

    "🔍 Проверить календарь",

    "🗑 Очистить календарь",

    "🚀 Создать прогнозы тура",

    "🗄 Проверка базы",

    "⬅️ Главное меню",

    "🗑 Очистить журнал"
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


    dp.message.register(
        cmd_load_fixtures,
        Command("загрузить_календарь")
    )


    dp.message.register(
        cmd_fixtures_check,
        Command("fixtures_check")
    )


    dp.message.register(
        cmd_update_calendar,
        Command("update_calendar")
    )


    dp.message.register(
        cmd_update_results,
        Command("update_results")
    )


    dp.message.register(
        cmd_clear_fixtures,
        Command("clear_fixtures")
    )


    dp.message.register(
        cmd_debug_calendar,
        Command("debug_calendar")
    )

    dp.message.register(
        cmd_debug_rpl_source,
        Command("debug_rpl")
    )

    dp.message.register(
        cmd_debug_soccer365,
        Command("debug_soccer365")
    )

    # ===== DEBUG PREDICTION =====
    async def debug_prediction_handler(
        message: Message
    ):
        await cmd_debug_prediction(
            message,
            core
        )

    dp.message.register(
        debug_prediction_handler,
        Command("debug_prediction")
    )

    # ===== НОВАЯ КОМАНДА DEBUG RESULTS =====
    dp.message.register(
        cmd_debug_results,
        Command("debug_results")
    )

    # ===== НОВЫЕ КОМАНДЫ =====
    dp.message.register(
        cmd_show_fixtures,
        Command("тур")
    )
    dp.message.register(
        cmd_show_fixtures,
        Command("fixtures")
    )

    @dp.message(
        Command("clear_journal")
    )
    async def clear_journal_handler(
        message: Message
    ):
        ok = clear_journal()
        if ok:
            await message.answer(
                "🗑 Журнал прогнозов очищен."
            )
        else:
            await message.answer(
                "❌ Ошибка очистки журнала."
            )

    # ===== КОМАНДА ДЛЯ ГЕНЕРАЦИИ ТУРА =====
    @dp.message(
        Command("generate_tour")
    )
    async def generate_tour_command(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )

    # ===== НОВАЯ КОМАНДА КАЛИБРОВКИ =====
    dp.message.register(
        cmd_calibration,
        Command("calibration")
    )


    # =================================================
    # MAIN MENU
    # =================================================


    @dp.message(
        lambda m:
        m.text == "📊 Статус"
    )
    async def status_button(message: Message):

        await cmd_status(message)



    @dp.message(
        lambda m:
        m.text == "📋 Журнал"
    )
    async def journal_button(message: Message):

        await cmd_journal(message)



    @dp.message(
        lambda m:
        m.text == "❤️ Проверка"
    )
    async def health_button(message: Message):

        await cmd_health(message)



    @dp.message(
        lambda m:
        m.text == "📁 Паспорта"
    )
    async def passport_button_handler(message: Message):

        await button_passport(message)



    # ===== ЗАМЕНА: теперь используем cmd_show_fixtures =====
    @dp.message(
        lambda m:
        m.text == "📅 Матчи"
    )
    async def fixtures_button(message: Message):

        await cmd_show_fixtures(message)



    # =================================================
    # FAJ PREDICTIONS
    # =================================================


    @dp.message(
        lambda m:
        m.text == "🤖 FAJ прогнозы"
    )
    async def faj_predictions_button(message: Message):

        await cmd_faj_predictions(message)



    @dp.message(
        lambda m:
        m.text == "🧠 Мои прогнозы"
    )
    async def expert_predictions_button(message: Message):

        await cmd_expert_predictions(message)



    # ===== ОБРАБОТЧИК КНОПКИ "🧠 Анализ ошибок FAJ" =====
    @dp.message(
        lambda m:
        m.text == "🧠 Анализ ошибок FAJ"
    )
    async def calibration_button(
        message: Message
    ):
        await cmd_calibration(message)


    # =================================================
    # ADMIN
    # =================================================


    @dp.message(
        lambda m:
        m.text == "⚙️ Админ"
    )
    async def admin_button(message: Message):

        await message.answer(

            """
⚙️ Админ панель FAJ v6.3

📥 Загрузить паспорта

🔄 Синхронизировать календарь

🔄 Обновить результаты

🔍 Проверить календарь

🗑 Очистить календарь

🚀 Создать прогнозы тура

🧠 Анализ ошибок FAJ

🗄 Проверка базы

🗑 Очистить журнал
""",

            reply_markup=admin_keyboard()

        )


    # ===== ОБРАБОТЧИК КНОПКИ "🚀 Создать прогнозы тура" =====
    @dp.message(
        lambda m:
        m.text == "🚀 Создать прогнозы тура"
    )
    async def generate_tour_button(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )


    @dp.message(
        lambda m:
        m.text == "🗑 Очистить календарь"
    )
    async def clear_calendar_button(message: Message):

        await cmd_clear_fixtures(message)



    @dp.message(
        lambda m:
        m.text == "🔄 Синхронизировать календарь"
    )
    async def update_calendar_button(message: Message):

        await cmd_update_calendar(message)



    @dp.message(
        lambda m:
        m.text == "🔄 Обновить результаты"
    )
    async def update_results_button(message: Message):

        await cmd_update_results(message)



    @dp.message(
        lambda m:
        m.text == "🔍 Проверить календарь"
    )
    async def check_calendar_button(message: Message):

        await cmd_fixtures_check(message)



    @dp.message(
        lambda m:
        m.text == "📥 Загрузить паспорта"
    )
    async def passports_button(message: Message):

        await cmd_load_passports(message)



    @dp.message(
        lambda m:
        m.text == "🗄 Проверка базы"
    )
    async def db_check_button(message: Message):

        await cmd_dbcheck(message)



    @dp.message(
        lambda m:
        m.text == "🗑 Очистить журнал"
    )
    async def clear_journal_button(
        message: Message
    ):
        ok = clear_journal()
        if ok:
            await message.answer(
                "🗑 Журнал очищен."
            )
        else:
            await message.answer(
                "❌ Не удалось очистить журнал."
            )


    # =================================================
    # PASSPORT TEXT
    # =================================================


    @dp.message(
        lambda m:
        m.text
        and
        m.text.lower().startswith("паспорт")
    )
    async def passport_text(message: Message):

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
            len(m.text.split()) >= 2
        )

    )
    async def predict_handler(message: Message):

        await handle_predict(
            message,
            core,
            journal
        )



    # =================================================
    # DEFAULT
    # =================================================


    @dp.message()
    async def default_handler(message: Message):

        await message.answer(

            """
⚽ FAJ Platform v6.3


📊 Статус        📈 Прогноз

📁 Паспорта      📅 Матчи

🤖 FAJ прогнозы  🧠 Мои прогнозы

🧠 Анализ ошибок FAJ

🏆 Турниры       📋 Журнал

⚙️ Админ         ❤️ Проверка


FAJ анализирует:

• Team Passport
• xG модель
• форму
• атаку
• защиту
• вероятности
• точные счета
• календарь турниров
""",

            reply_markup=main_keyboard()

        )


    logger.info(
        "FAJ Platform v6.3 started"
    )


    await dp.start_polling(bot)
