import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

from app.config import Config
from app.core.faj_core import FAJCore
from app.journal import Journal

from app.handlers.predict import handle_predict
from app.handlers.status import cmd_status
from app.handlers.journal import cmd_journal
from app.handlers.health import cmd_health
from app.handlers.load_passports import cmd_load_passports


logger = logging.getLogger(__name__)


async def run_bot(core: FAJCore, journal: Journal):

    bot = Bot(token=Config.TELEGRAM_TOKEN)
    dp = Dispatcher()


    # ------------------------
    # /start
    # ------------------------

    @dp.message(Command("start"))
    async def start(message: Message):

        await message.answer(
            """
⚽ FAJ Platform v5.1

Команды:

📊 Статус
📁 Паспорт команда
📈 Прогноз команда команда
🏆 Таблица
⚽ Команды
🌍 Лиги
📋 Журнал
❤️ Проверка


Пример:

Прогноз Зенит Спартак

или просто:

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
        )


    # ------------------------
    # Старые команды
    # ------------------------

    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_journal, Command("journal"))
    dp.message.register(cmd_health, Command("health"))
    dp.message.register(cmd_load_passports, Command("load_passports"))



    # ------------------------
    # Русские команды
    # ------------------------

    @dp.message()
    async def text_handler(message: Message):

        text = message.text.strip()

        lower = text.lower()


        # статус

        if lower in [
            "статус",
            "📊 статус"
        ]:

            await cmd_status(message)
            return



        # журнал

        if lower == "журнал":

            await cmd_journal(message)
            return



        # проверка

        if lower in [
            "проверка",
            "здоровье"
        ]:

            await cmd_health(message)
            return



        # загрузка паспортов

        if lower in [
            "загрузить паспорта",
            "паспорта загрузить"
        ]:

            await cmd_load_passports(message)
            return



        # прогноз

        if lower.startswith("прогноз"):

            parts = text.split()

            if len(parts) >= 3:

                message.text = (
                    parts[1]
                    +
                    " "
                    +
                    parts[2]
                )

                await handle_predict(
                    message,
                    core,
                    journal
                )

                return



        # просто две команды

        words = text.split()

        if len(words) == 2:

            await handle_predict(
                message,
                core,
                journal
            )

            return



        # паспорт

        if lower.startswith("паспорт"):

            await message.answer(
                "📁 Модуль паспортов подключаем следующим этапом."
            )

            return



        # таблица

        if lower == "таблица":

            await message.answer(
                "🏆 Турнирная таблица будет подключена после календаря РПЛ."
            )

            return



        # команды

        if lower == "команды":

            await message.answer(
                "⚽ Доступные команды:\n\n"
                "Зенит\n"
                "Спартак\n"
                "ЦСКА\n"
                "Краснодар\n"
                "Локомотив\n"
                "Динамо М\n"
            )

            return



        # лиги

        if lower == "лиги":

            await message.answer(
                "🌍 Активные лиги:\n\n"
                "🇷🇺 РПЛ\n"
                "🏆 Лига чемпионов\n\n"
                "Другие лиги будут подключаться позже."
            )

            return



        await message.answer(
            "Не понял команду.\n\n"
            "Напиши:\n"
            "Прогноз Зенит Спартак\n"
            "или\n"
            "Статус"
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен. Русский интерфейс активен."
    )


    await dp.start_polling(bot)
