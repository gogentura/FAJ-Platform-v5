import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from app.config import Config
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.handlers.start import cmd_start
from app.handlers.predict import handle_predict
from app.handlers.journal import cmd_journal
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.load_passports import cmd_load_passports  # новый импорт
from app.handlers.keyboard import get_main_keyboard

logger = logging.getLogger(__name__)

async def run_bot(core, journal):
    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return

    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_journal, Command("journal"))
    dp.message.register(cmd_health, Command("health"))
    dp.message.register(cmd_load_passports, Command("load_passports"))  # новая команда

    dp.message.register(
        handle_predict,
        lambda msg: not msg.text.startswith("/") and len(msg.text.split()) >= 2
    )

    logger.info("Бот запущен (чистая установка + загрузка паспортов)")
    await dp.start_polling(bot)
