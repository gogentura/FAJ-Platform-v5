import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command

from app.config import Config

from app.handlers.start import cmd_start
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.update import cmd_update_rpl, cmd_update_team
from app.handlers.passport import cmd_passport
from app.handlers.journal import cmd_journal
from app.handlers.predict import handle_predict


logger = logging.getLogger(__name__)


async def run_bot(core, journal):

    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан!")
        return


    bot = Bot(
        token=Config.TELEGRAM_TOKEN
    )

    dp = Dispatcher()


    # Команды

    dp.message.register(
        cmd_start,
        Command("start")
    )

    dp.message.register(
        cmd_status,
        Command("status")
    )

    dp.message.register(
        cmd_health,
        Command("health")
    )

    dp.message.register(
        cmd_update_rpl,
        Command("update_rpl")
    )

    dp.message.register(
        cmd_update_team,
        Command("update_team")
    )

    dp.message.register(
        cmd_passport,
        Command("passport")
    )

    dp.message.register(
        cmd_journal,
        Command("journal")
    )


    # Прогноз
    # Новый predict.py принимает только message

    async def predict_handler(message):

        await handle_predict(
            message
        )


    dp.message.register(
        predict_handler,
        F.text
    )


    logger.info(
        "⚽ FAJ Platform v5.1 started"
    )


    await dp.start_polling(bot)
