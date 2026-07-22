import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command

from app.config import Config

from app.handlers.start import cmd_start
from app.handlers.predict import handle_predict
from app.handlers.passport import cmd_passport
from app.handlers.update import cmd_update_rpl, cmd_update_team
from app.handlers.journal import cmd_journal
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health


logger = logging.getLogger(__name__)


async def run_bot(core, journal):

    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не задан")
        return


    bot = Bot(
        token=Config.TELEGRAM_TOKEN
    )

    dp = Dispatcher()


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


    async def predict_wrapper(message):

        await handle_predict(
            message,
            core,
            journal
        )


    dp.message.register(
        predict_wrapper,
        lambda msg:
        msg.text
        and not msg.text.startswith("/")
        and len(msg.text.split()) >= 2
    )


    logger.info(
        "FAJ Platform v5.1 started"
    )


    await dp.start_polling(bot)
