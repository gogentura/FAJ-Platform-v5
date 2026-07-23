import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Config

from app.core.faj_core import FAJCore
from app.journal import Journal

from app.handlers.start import cmd_start
from app.handlers.status import cmd_status
from app.handlers.journal import cmd_journal
from app.handlers.health import cmd_health
from app.handlers.load_passports import cmd_load_passports
from app.handlers.predict import handle_predict

from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)


async def run_bot(core: FAJCore, journal: Journal):

    if not Config.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN отсутствует")
        return


    bot = Bot(
        token=Config.TELEGRAM_TOKEN
    )

    dp = Dispatcher()


    # =========================
    # Системные команды
    # =========================

    dp.message.register(
        cmd_start,
        Command("start")
    )


    dp.message.register(
        cmd_status,
        Command(
            commands=[
                "status",
                "статус"
            ]
        )
    )


    dp.message.register(
        cmd_journal,
        Command(
            commands=[
                "journal",
                "журнал"
            ]
        )
    )


    dp.message.register(
        cmd_health,
        Command(
            commands=[
                "health",
                "проверка"
            ]
        )
    )


    dp.message.register(
        cmd_load_passports,
        Command(
            commands=[
                "load_passports",
                "загрузить_паспорта"
            ]
        )
    )



    # =========================
    # Прогноз через текст
    # =========================

    @dp.message()
    async def all_messages(message: Message):

        if not message.text:
            return


        text = message.text.strip()


        logger.info(
            f"Получено сообщение: {text}"
        )


        # -------------------------
        # прогноз
        # -------------------------

        if not text.startswith("/"):

            words = text.split()


            # варианты:
            # Зенит Спартак
            # прогноз Зенит Спартак

            if words[0].lower() in [
                "прогноз",
                "анализ",
                "счёт"
            ]:
                words = words[1:]


            if len(words) >= 2:

                await handle_predict(
                    message,
                    core,
                    journal
                )

                return



        # -------------------------
        # помощь
        # -------------------------

        await message.answer(
            """
⚽ FAJ Platform v5.1

Команды:

📊 /статус
📋 /журнал
❤️ /проверка
📥 /загрузить_паспорта


Прогноз:

Зенит Спартак

или

прогноз Зенит Спартак


FAJ анализирует:
• xG
• силу команд
• паспорта
• вероятности
• возможные счета
            """,
            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Bot v5.1 запущен"
    )


    await dp.start_polling(bot)
