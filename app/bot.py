import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Config
from app.core.faj_core import FAJCore
from app.journal import Journal

from app.handlers.start import cmd_start
from app.handlers.predict import handle_predict
from app.handlers.journal import cmd_journal
from app.handlers.status import cmd_status
from app.handlers.health import cmd_health
from app.handlers.load_passports import cmd_load_passports
from app.handlers.database_check import cmd_dbcheck

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


    # ==========================
    # КОМАНДЫ БОТА
    # ==========================

    dp.message.register(
        cmd_start,
        Command(
            "start"
        )
    )


    dp.message.register(
        cmd_status,
        Command(
            "статус"
        )
    )


    dp.message.register(
        cmd_journal,
        Command(
            "журнал"
        )
    )


    dp.message.register(
        cmd_health,
        Command(
            "проверка"
        )
    )


    dp.message.register(
        cmd_load_passports,
        Command(
            "загрузить_паспорта"
        )
    )


    dp.message.register(
        cmd_dbcheck,
        Command(
            "база"
        )
    )


    # ==========================
    # КНОПКИ МЕНЮ
    # ==========================


    @dp.message(
        lambda message:
        message.text == "📊 Статус"
    )
    async def button_status(message: Message):

        await cmd_status(message)



    @dp.message(
        lambda message:
        message.text == "📋 Журнал"
    )
    async def button_journal(message: Message):

        await cmd_journal(message)



    @dp.message(
        lambda message:
        message.text == "❤️ Проверка"
    )
    async def button_health(message: Message):

        await cmd_health(message)



    @dp.message(
        lambda message:
        message.text == "📥 Загрузить паспорта"
    )
    async def button_load(message: Message):

        await cmd_load_passports(message)



    # ==========================
    # ПРОГНОЗ
    # ==========================

    @dp.message(
        lambda msg:
        msg.text
        and not msg.text.startswith("/")
        and len(msg.text.split()) >= 2
    )
    async def predict_text(message: Message):

        logger.info(
            f"Запрос прогноза: {message.text}"
        )

        await handle_predict(
            message,
            core,
            journal
        )



    # ==========================
    # СПРАВКА
    # ==========================

    @dp.message()
    async def default_message(message: Message):

        text = (
            "⚽ FAJ Platform v5.1\n\n"

            "Команды:\n\n"

            "📊 Статус\n"
            "📁 Паспорт команда\n"
            "📈 Прогноз команда команда\n"
            "🏆 Таблица\n"
            "⚽ Команды\n"
            "🌍 Лиги\n"
            "📋 Журнал\n"
            "❤️ Проверка\n\n"

            "Пример:\n"
            "Прогноз Зенит Спартак\n\n"

            "или просто:\n"
            "Зенит Спартак\n\n"

            "FAJ анализирует:\n"
            "• паспорта команд\n"
            "• xG\n"
            "• форму\n"
            "• атаку\n"
            "• защиту\n"
            "• вероятности\n"
            "• точные счета"
        )


        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )


    await dp.start_polling(bot)
