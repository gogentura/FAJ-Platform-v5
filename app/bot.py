# app/bot.py

import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Config

from app.core.faj_core import FAJCore
from app.journal import Journal


# handlers

from app.handlers.start import cmd_start
from app.handlers.predict import handle_predict
from app.handlers.journal import cmd_journal
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.load_passports import cmd_load_passports
from app.handlers.database_check import cmd_dbcheck
from app.handlers.result import cmd_result


from app.handlers.passport import (
    cmd_passport,
    button_passport
)


from app.handlers.keyboard import get_main_keyboard



logger = logging.getLogger(__name__)




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



    # =====================================================
    # COMMANDS /
    # =====================================================


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
        cmd_load_passports,
        Command("загрузить_паспорта")
    )


    dp.message.register(
        cmd_dbcheck,
        Command("база")
    )


    dp.message.register(
        cmd_result,
        Command("результат")
    )




    # =====================================================
    # TEXT COMMANDS
    # =====================================================


    dp.message.register(
        cmd_status,
        lambda message:
        message.text
        and message.text.lower()
        == "статус"
    )



    dp.message.register(
        cmd_journal,
        lambda message:
        message.text
        and message.text.lower()
        == "журнал"
    )



    dp.message.register(
        cmd_health,
        lambda message:
        message.text
        and message.text.lower()
        == "проверка"
    )



    dp.message.register(
        cmd_load_passports,
        lambda message:
        message.text
        and "загрузить" in message.text.lower()
    )



    dp.message.register(
        cmd_result,
        lambda message:
        message.text
        and message.text.lower().startswith(
            "результат"
        )
    )



    dp.message.register(
        cmd_passport,
        lambda message:
        message.text
        and message.text.lower().startswith(
            "паспорт"
        )
    )



    # =====================================================
    # BUTTONS
    # =====================================================


    @dp.message(
        lambda message:
        message.text == "📊 Статус"
    )
    async def button_status(
        message: Message
    ):

        await cmd_status(
            message
        )



    @dp.message(
        lambda message:
        message.text == "📋 Журнал"
    )
    async def button_journal(
        message: Message
    ):

        await cmd_journal(
            message
        )



    @dp.message(
        lambda message:
        message.text == "❤️ Проверка"
    )
    async def button_health(
        message: Message
    ):

        await cmd_health(
            message
        )



    @dp.message(
        lambda message:
        message.text == "⚽ Результат"
    )
    async def button_result(
        message: Message
    ):

        await message.answer(

            """
⚽ Введите результат:

Пример:

Зенит Спартак 2:1

или

Результат Зенит Спартак 2:1
            """,

            reply_markup=get_main_keyboard()

        )



    @dp.message(
        lambda message:
        message.text == "📁 Паспорт"
    )
    async def button_pass(
        message: Message
    ):

        await button_passport(
            message
        )




    # =====================================================
    # PREDICTION
    # =====================================================


    @dp.message(
        lambda msg:
        msg.text
        and not msg.text.startswith("/")
        and len(msg.text.split()) >= 2
        and not msg.text.lower().startswith(
            "результат"
        )
    )
    async def predict_text(
        message: Message
    ):


        logger.info(
            f"Запрос прогноза: {message.text}"
        )


        await handle_predict(
            message,
            core,
            journal
        )




    # =====================================================
    # DEFAULT
    # =====================================================


    @dp.message()
    async def default_message(
        message: Message
    ):


        await message.answer(

            """
⚽ FAJ Platform v5.1


Доступно:


📊 Статус

📁 Паспорт Зенит

📈 Прогноз Зенит Спартак

⚽ Результат Зенит Спартак 2:1

📋 Журнал

❤️ Проверка



FAJ анализирует:

• паспорта команд
• xG
• форму
• атаку
• защиту
• вероятности
• точные счета
• точность прогнозов
            """,

            reply_markup=get_main_keyboard()

        )




    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )


    await dp.start_polling(
        bot
    )
