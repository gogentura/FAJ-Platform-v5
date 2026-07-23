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
from app.handlers.passport import handle_passport

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
    # КОМАНДЫ С /
    # ==========================

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



    # ==========================
    # КНОПКИ МЕНЮ
    # ==========================


    @dp.message(
        lambda m: m.text == "📊 Статус"
    )
    async def button_status(message: Message):

        await cmd_status(message)



    @dp.message(
        lambda m: m.text == "📋 Журнал"
    )
    async def button_journal(message: Message):

        await cmd_journal(message)



    @dp.message(
        lambda m: m.text == "❤️ Проверка"
    )
    async def button_health(message: Message):

        await cmd_health(message)



    @dp.message(
        lambda m: m.text == "📥 Загрузить паспорта"
    )
    async def button_load(message: Message):

        await cmd_load_passports(message)



    @dp.message(
        lambda m: m.text == "📁 Паспорт"
    )
    async def button_passport(message: Message):

        await message.answer(
            "📁 Раздел паспортов\n\n"
            "Пример:\n\n"
            "Паспорт Зенит",
            reply_markup=get_main_keyboard()
        )



    # ==========================
    # ПОЛУЧЕНИЕ ПАСПОРТА
    # ==========================


    @dp.message(
        lambda m:
        m.text
        and m.text.lower().startswith("паспорт")
    )
    async def passport_request(message: Message):

        await handle_passport(message)



    # ==========================
    # ПРОГНОЗ
    # ==========================


    @dp.message(
        lambda m:
        m.text
        and not m.text.startswith("/")
        and not m.text.lower().startswith("паспорт")
        and len(m.text.split()) >= 2
    )
    async def predict_request(message: Message):

        text = message.text.strip()


        if text.lower().startswith("прогноз"):

            text = text.replace(
                "Прогноз",
                "",
                1
            ).strip()

            message.text = text


        logger.info(
            f"Запрос прогноза: {message.text}"
        )


        await handle_predict(
            message,
            core,
            journal
        )



    # ==========================
    # НЕИЗВЕСТНЫЕ СООБЩЕНИЯ
    # ==========================


    @dp.message()
    async def default_message(message: Message):

        await message.answer(
            "⚽ FAJ Platform v5.1\n\n"

            "Доступные команды:\n\n"

            "📊 Статус\n"
            "📁 Паспорт Зенит\n"
            "📈 Прогноз Зенит Спартак\n"
            "🏆 Таблица\n"
            "⚽ Команды\n"
            "🌍 Лиги\n"
            "📋 Журнал\n"
            "❤️ Проверка\n\n"

            "Примеры:\n\n"
            "Паспорт Зенит\n"
            "Зенит Спартак",

            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )


    await dp.start_polling(bot)
