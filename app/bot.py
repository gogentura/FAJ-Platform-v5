# =====================================================
# FAJ Platform v7.0.3
# app/bot.py
#
# Telegram Bot Core
#
# Stable aiogram 3 routing
# PostgreSQL
# Passport Manager
# FAJ Prediction Engine
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
# HANDLERS IMPORTS
# =====================================================
from app.handlers.start import cmd_start
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.journal import cmd_journal
from app.handlers.database_check import database_check
from app.handlers.load_passports import cmd_load_passports
from app.handlers.passport import (
    cmd_passport,
    button_passport,
    passport_text_handler
)
from app.handlers.show_fixtures import cmd_show_fixtures
from app.handlers.load_fixtures import cmd_load_fixtures
from app.handlers.fixtures_check import cmd_fixtures_check
from app.handlers.update_calendar import cmd_update_calendar
from app.handlers.update_results import cmd_update_results
from app.handlers.clear_fixtures import cmd_clear_fixtures
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
from app.handlers.predict import (
    handle_predict
)

# =====================================================
# KEYBOARDS
# =====================================================
from app.keyboards.main import main_keyboard
from app.keyboards.admin import admin_keyboard

# =====================================================
# BOT START
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
    dp.message.register(
        cmd_load_passports,
        Command("загрузить_паспорта")
    )
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
    # FAJ COMMANDS
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
    # CALLBACKS
    # =================================================
    dp.callback_query.register(
        faj_match_callback
    )

    # =================================================
    # MAIN USER BUTTONS
    # =================================================
    @dp.message(
        lambda m: m.text == "📁 Паспорта"
    )
    async def passports_button(
        message: Message
    ):
        await button_passport(
            message
        )

    @dp.message(
        lambda m: m.text == "📊 Статус"
    )
    async def status_button(
        message: Message
    ):
        await cmd_status(
            message
        )

    @dp.message(
        lambda m: m.text == "📋 Журнал"
    )
    async def journal_button(
        message: Message
    ):
        await cmd_journal(
            message
        )

    @dp.message(
        lambda m: m.text == "❤️ Проверка"
    )
    async def health_button(
        message: Message
    ):
        await cmd_health(
            message
        )

    @dp.message(
        lambda m: m.text == "📅 Матчи"
    )
    async def matches_button(
        message: Message
    ):
        await cmd_show_fixtures(
            message
        )

    @dp.message(
        lambda m: m.text == "🤖 FAJ прогнозы"
    )
    async def faj_button(
        message: Message
    ):
        await cmd_faj_predictions(
            message
        )

    @dp.message(
        lambda m: m.text == "🧠 Мои прогнозы"
    )
    async def expert_button(
        message: Message
    ):
        await cmd_expert_predictions(
            message
        )

    # =================================================
    # ADMIN BUTTONS
    # =================================================
    @dp.message(
        lambda m: m.text == "⚙️ Админ"
    )
    async def admin_button(
        message: Message
    ):
        logger.info(
            "ADMIN BUTTON PRESSED"
        )
        await message.answer(
"""
⚙️ FAJ Platform v7.0.3
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
        lambda m: m.text == "📥 Загрузить паспорта"
    )
    async def load_passports_button(
        message: Message
    ):
        await cmd_load_passports(
            message
        )

    @dp.message(
        lambda m: m.text == "🔄 Синхронизировать календарь"
    )
    async def update_calendar_button(
        message: Message
    ):
        await cmd_update_calendar(
            message
        )

    @dp.message(
        lambda m: m.text == "🔄 Обновить результаты"
    )
    async def update_results_button(
        message: Message
    ):
        await cmd_update_results(
            message
        )

    @dp.message(
        lambda m: m.text == "🔍 Проверить календарь"
    )
    async def fixtures_check_button(
        message: Message
    ):
        await cmd_fixtures_check(
            message
        )

    @dp.message(
        lambda m: m.text == "🗄 Проверка базы"
    )
    async def database_button(
        message: Message
    ):
        await database_check(
            message
        )

    @dp.message(
        lambda m: m.text == "🚀 Создать прогнозы тура"
    )
    async def create_predictions_button(
        message: Message
    ):
        await cmd_generate_predictions(
            message
        )

    @dp.message(
        lambda m: m.text == "🗑 Очистить календарь"
    )
    async def clear_calendar_button(
        message: Message
    ):
        await cmd_clear_fixtures(
            message
        )

    # =================================================
    # MATCH PREDICTION FILTER
    # =================================================
    def is_match_prediction(
        message: Message
    ):
        if not message.text:
            return False
        text = message.text.strip()
        if text.startswith("/"):
            return False
        blocked = [
            "📁 Паспорта",
            "📊 Статус",
            "📋 Журнал",
            "❤️ Проверка",
            "📅 Матчи",
            "🤖 FAJ прогнозы",
            "🧠 Мои прогнозы",
            "⚙️ Админ",
            "📥 Загрузить паспорта",
            "🔄 Синхронизировать календарь",
            "🔄 Обновить результаты",
            "🔍 Проверить календарь",
            "🗄 Проверка базы",
            "🚀 Создать прогнозы тура",
            "🗑 Очистить календарь"
        ]
        if text in blocked:
            return False
        words = text.split()
        # прогноз только две команды
        if len(words) < 2:
            return False
        return True

    dp.message.register(
        handle_predict,
        is_match_prediction
    )

    # =================================================
    # PASSPORT TEXT
    # ТОЛЬКО ОДНО СЛОВО
    # =================================================
    def is_passport_text(
        message: Message
    ):
        if not message.text:
            return False
        text = message.text.strip()
        if text.startswith("/"):
            return False
        # кнопки не трогаем
        buttons = [
            "📁 Паспорта",
            "📊 Статус",
            "📋 Журнал",
            "❤️ Проверка",
            "📅 Матчи",
            "🤖 FAJ прогнозы",
            "🧠 Мои прогнозы",
            "⚙️ Админ"
        ]
        if text in buttons:
            return False
        # паспорт команды = одно слово
        if len(text.split()) != 1:
            return False
        return True

    dp.message.register(
        passport_text_handler,
        is_passport_text
    )

    # =================================================
    # DEFAULT HANDLER
    # =================================================
    @dp.message()
    async def default_handler(
        message: Message
    ):
        logger.info(
            "DEFAULT HANDLER: %s",
            message.text
        )
        await message.answer(
"""
⚽ FAJ Platform v7.0.3
📊 Статус
📁 Паспорта
📅 Матчи
🤖 FAJ прогнозы
🧠 Мои прогнозы
⚙️ Админ
FAJ Engine:
• Team Passport
• FAJ Rating
• xG Engine
• Monte Carlo
• Risk Engine
• Journal Learning
""",
            reply_markup=main_keyboard()
        )

    # =================================================
    # START
    # =================================================
    logger.info(
        "Handlers registered successfully"
    )
    logger.info(
        "🚀 FAJ Platform v7.0.3 started"
    )
    await dp.start_polling(
        bot
    )
