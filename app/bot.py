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

from app.handlers.passport import cmd_passport


from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)



async def run_bot(core: FAJCore, journal: Journal):


    if not Config.TELEGRAM_TOKEN:

        logger.error(
            "TELEGRAM_TOKEN отсутствует"
        )

        return



    bot = Bot(
        token=Config.TELEGRAM_TOKEN
    )


    dp = Dispatcher()



    # =================================
    # КОМАНДЫ С /
    # =================================


    dp.message.register(
        cmd_start,
        Command("start")
    )


    dp.message.register(
        cmd_status,
        Command("status")
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




    # =================================
    # КНОПКИ МЕНЮ БЕЗ /
    # =================================



    # -------- СТАТУС --------

    @dp.message(
        lambda m:
        m.text
        and m.text.lower()
        .replace("📊","")
        .strip()
        == "статус"
    )
    async def status_button(message: Message):

        await cmd_status(message)




    # -------- ЖУРНАЛ --------

    @dp.message(
        lambda m:
        m.text
        and "журнал" in m.text.lower()
    )
    async def journal_button(message: Message):

        await cmd_journal(message)




    # -------- ПРОВЕРКА --------

    @dp.message(
        lambda m:
        m.text
        and "проверка" in m.text.lower()
    )
    async def health_button(message: Message):

        await cmd_health(message)




    # -------- ЗАГРУЗКА ПАСПОРТОВ --------

    @dp.message(
        lambda m:
        m.text
        and (
            "загрузить паспорта" in m.text.lower()
            or
            "загрузить_паспорта" in m.text.lower()
        )
    )
    async def load_button(message: Message):

        await cmd_load_passports(message)




    # -------- ПАСПОРТ КОМАНДЫ --------

    @dp.message(
        lambda m:
        m.text
        and m.text.lower().startswith("паспорт")
    )
    async def passport_button(message: Message):

        await cmd_passport(message)




    # =================================
    # ПРОГНОЗ
    # =================================


    @dp.message(
        lambda m:
        m.text
        and not m.text.startswith("/")
        and len(m.text.split()) >= 2
        and not m.text.lower().startswith(
            (
                "паспорт",
                "статус",
                "журнал",
                "проверка",
                "загрузить"
            )
        )
    )
    async def prediction_handler(message: Message):

        logger.info(
            f"Запрос прогноза: {message.text}"
        )


        await handle_predict(
            message,
            core,
            journal
        )




    # =================================
    # ВСЕ ОСТАЛЬНОЕ
    # =================================


    @dp.message()
    async def default_message(message: Message):


        text = """

⚽ FAJ Platform v5.1


Доступные команды:


📊 Статус

📁 Паспорт Зенит

📈 Прогноз Зенит Спартак

🏆 Таблица

⚽ Команды

🌍 Лиги

📋 Журнал

❤️ Проверка


Примеры:


Паспорт Зенит


Зенит Спартак


FAJ анализирует:

• паспорта команд
• xG
• форму
• силу атаки
• защиту
• вероятности
• точные счета

"""


        await message.answer(
            text,
            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )



    await dp.start_polling(bot)
