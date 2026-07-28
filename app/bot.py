# =====================================================
# FAJ Platform v7.0.1
# app/bot.py
#
# Telegram Bot Core
#
# Compatible:
# - FAJCore v7
# - PostgreSQL Database
# - Journal v7
# - Passport Manager v7
# =====================================================
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from app.config import Config
from app.core.faj_core import FAJCore
from app.journal import Journal, clear_journal

logger = logging.getLogger(__name__)

# =====================================================
# HANDLERS
# =====================================================
from app.handlers.start import cmd_start
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.journal import cmd_journal
from app.handlers.database_check import (
    database_check
)
from app.handlers.load_passports import (
    cmd_load_passports
)
from app.handlers.passport import (
    cmd_passport,
    button_passport
)
from app.handlers.show_fixtures import (
    cmd_show_fixtures
)
from app.handlers.load_fixtures import (
    cmd_load_fixtures
)
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
    cmd_faj_predictions,
    faj_match_callback
)
from app.handlers.expert_predictions import (
    cmd_expert_predictions
)
from app.handlers.generate_predictions import (
    cmd_generate_predictions
)
from app.handlers.debug_prediction import (
    cmd_debug_prediction
)
from app.handlers.debug_calendar import (
    cmd_debug_calendar
)
from app.handlers.debug_results import (
    cmd_debug_results
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
    logger.info(
        "FAJ Bot initializing..."
    )
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
        database_check,
        Command("база")
    )
    dp.message.register(
        database_check,
        Command("database_check")
    )
    dp.message.register(
        cmd_passport,
        Command("паспорт")
    )
    # =================================================
    # PASSPORT LOADING
    # =================================================
    dp.message.register(
        cmd_load_passports,
        Command("загрузить_паспорта")
    )
    # =================================================
    # FIXTURES
    # =================================================
    dp.message.register(
        cmd_load_fixtures,
        Command("загрузить_календарь")
    )
    dp.message.register(
        cmd_show_fixtures,
        Command("тур")
    )
    dp.message.register(
        cmd_show_fixtures,
        Command("fixtures")
    )
    dp.message.register(
        cmd_fixtures_check,
        Command("fixtures_check")
    )
    # =================================================
    # CALENDAR UPDATE
    # =================================================
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
    # =================================================
    # FAJ PREDICTIONS
    # =================================================
    @dp.message(
        Command("faj")
    )
    async def faj_command(
        message: Message
    ):
        await cmd_faj_predictions(
            message
        )
    @dp.message(
        Command("generate_tour")
    )
    async def generate_tour(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )
    @dp.message(
        Command("generate_predictions")
    )
    async def generate_predictions(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )
    # =================================================
    # DEBUG
    # =================================================
    @dp.message(
        Command("debug_prediction")
    )
    async def debug_prediction(
        message: Message
    ):
        await cmd_debug_prediction(
            message,
            core
        )
    dp.message.register(
        cmd_debug_calendar,
        Command("debug_calendar")
    )
    dp.message.register(
        cmd_debug_results,
        Command("debug_results")
    )
    # =================================================
    # CLEAR JOURNAL
    # =================================================
    @dp.message(
        Command("clear_journal")
    )
    async def clear_journal_handler(
        message: Message
    ):
        result = clear_journal()
        if result:
            await message.answer(
                "🗑 Журнал очищен."
            )
        else:
            await message.answer(
                "❌ Ошибка очистки журнала."
            )
    # =================================================
    # INLINE CALLBACKS
    # =================================================
    dp.callback_query.register(
        faj_match_callback
    )
    # =================================================
    # BUTTONS
    # =================================================
    @dp.message(
        lambda m:
        m.text == "📁 Паспорта"
    )
    async def passports_button(
        message: Message
    ):
        await button_passport(
            message
        )
    @dp.message(
        lambda m:
        m.text == "📊 Статус"
    )
    async def status_button(
        message: Message
    ):
        await cmd_status(
            message
        )
    @dp.message(
        lambda m:
        m.text == "📋 Журнал"
    )
    async def journal_button(
        message: Message
    ):
        await cmd_journal(
            message
        )
    @dp.message(
        lambda m:
        m.text == "❤️ Проверка"
    )
    async def health_button(
        message: Message
    ):
        await cmd_health(
            message
        )
    @dp.message(
        lambda m:
        m.text == "📅 Матчи"
    )
    async def matches_button(
        message: Message
    ):
        await cmd_show_fixtures(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🤖 FAJ прогнозы"
    )
    async def faj_button(
        message: Message
    ):
        await cmd_faj_predictions(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🧠 Мои прогнозы"
    )
    async def expert_button(
        message: Message
    ):
        await cmd_expert_predictions(
            message
        )
    # =================================================
    # ADMIN BUTTON
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
⚙️ FAJ Platform v7.0.1
Админ панель:
📥 Загрузить паспорта
🔄 Синхронизировать календарь
🔄 Обновить результаты
🔍 Проверить календарь
🗄 Проверка базы
🚀 Создать прогнозы тура
🗑 Очистить календарь
🗑 Очистить журнал
""",
            reply_markup=admin_keyboard()
        )
    @dp.message(
        lambda m:
        m.text == "📥 Загрузить паспорта"
    )
    async def load_passports_button(
        message: Message
    ):
        await cmd_load_passports(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🔄 Синхронизировать календарь"
    )
    async def update_calendar_button(
        message: Message
    ):
        await cmd_update_calendar(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🔄 Обновить результаты"
    )
    async def update_results_button(
        message: Message
    ):
        await cmd_update_results(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🔍 Проверить календарь"
    )
    async def fixtures_check_button(
        message: Message
    ):
        await cmd_fixtures_check(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🗄 Проверка базы"
    )
    async def database_button(
        message: Message
    ):
        await database_check(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🚀 Создать прогнозы тура"
    )
    async def create_predictions_button(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )
    @dp.message(
        lambda m:
        m.text == "🗑 Очистить календарь"
    )
    async def clear_calendar_button(
        message: Message
    ):
        await cmd_clear_fixtures(
            message
        )
    # =================================================
    # DEFAULT HANDLER
    # =================================================
    @dp.message()
    async def default_handler(
        message: Message
    ):
        await message.answer(
            """
⚽ FAJ Platform v7.0.1
📊 Статус        📈 Прогноз
📁 Паспорта      📅 Матчи
🤖 FAJ прогнозы  🧠 Мои прогнозы
🏆 Турниры       📋 Журнал
⚙️ Админ         ❤️ Проверка
FAJ анализирует:
• Team Passport
• FAJ Rating
• xG Engine
• Monte Carlo
• вероятности
• точные счета
• риск
• журнал обучения
""",
            reply_markup=main_keyboard()
        )
    # =================================================
    # START
    # =================================================
    logger.info(
        "🚀 FAJ Platform v7.0.1 started"
    )
    await dp.start_polling(
        bot
    )
