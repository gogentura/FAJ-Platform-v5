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
    # КОМАНДЫ
    # =========================


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



    # =========================
    # КНОПКИ
    # =========================


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
    async def button_passports(message: Message):
        await cmd_load_passports(message)



    # =========================
    # ПАСПОРТ
    # =========================


    @dp.message(
        lambda m:
        m.text
        and (
            m.text.lower().startswith("паспорт")
            or m.text.startswith("📁")
        )
    )
    async def passport_command(message: Message):

        await message.answer(
            "📁 Раздел паспортов\n\n"
            "Пример:\n"
            "Паспорт Зенит\n\n"
            "Сейчас доступна загрузка и анализ паспортов РПЛ.",
            reply_markup=get_main_keyboard()
        )



    # =========================
    # ПРОГНОЗ
    # =========================


    @dp.message(
        lambda m:
        m.text
        and not m.text.startswith("/")
        and (
            m.text.lower().startswith("прогноз")
            or len(m.text.split()) == 2
        )
    )
    async def predict_handler(message: Message):

        text = message.text.strip()

        logger.info(
            f"Запрос прогноза: {text}"
        )

        await handle_predict(
            message,
            core,
            journal
        )



    # =========================
    # ТАБЛИЦА / ЛИГИ / КОМАНДЫ
    # =========================


    @dp.message(
        lambda m:
        m.text in [
            "🏆 Таблица",
            "⚽ Команды",
            "🌍 Лиги"
        ]
    )
    async def info_handler(message: Message):

        await message.answer(
            "🚧 Раздел находится в разработке.\n\n"
            "Следующий этап FAJ:\n"
            "• календарь туров\n"
            "• список матчей\n"
            "• автоматический прогноз тура\n"
            "• паспорта команд",
            reply_markup=get_main_keyboard()
        )



    # =========================
    # ОСТАЛЬНОЕ
    # =========================


    @dp.message()
    async def default_message(message: Message):

        await message.answer(
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
            "или:\n"
            "Зенит Спартак",
            
            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )


    await dp.start_polling(bot)
