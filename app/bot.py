import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from app.config import Config
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.handlers.start import cmd_start
from app.handlers.predict import handle_predict
from app.handlers.passport import cmd_passport
from app.handlers.update import cmd_update_rpl, cmd_update_team
from app.handlers.journal import cmd_journal
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)

async def run_bot(core, journal):
    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    ADMIN_ID = int(Config.ADMIN_CHAT_ID) if Config.ADMIN_CHAT_ID else None
    if not ADMIN_ID:
        logger.warning("ADMIN_CHAT_ID не задан — бот будет доступен всем!")

    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    # Регистрация команд
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_update_rpl, Command("update_rpl"))
    dp.message.register(cmd_update_team, Command("update_team"))
    dp.message.register(cmd_passport, Command("passport"))
    dp.message.register(cmd_journal, Command("journal"))
    dp.message.register(cmd_health, Command("health"))

    # Обработка простого текста (прогноз)
    dp.message.register(
        handle_predict,
        lambda msg: not msg.text.startswith("/") and len(msg.text.split()) >= 2
    )

    logger.info("Бот запущен (v5.1 Professional Architecture)")
    await dp.start_polling(bot)
