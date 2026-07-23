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
    # Команды через /
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
    # Основной обработчик
    # Русский режим
    # =========================

    @dp.message()
    async def all_messages(message: Message):

        if not message.text:
            return


        text = message.text.strip()

        logger.info(
            f"Сообщение пользователя: {text}"
        )


        command = text.lower()



        # -------------------------
        # Статус
        # -------------------------

        if command in [
            "статус",
            "📊 статус"
        ]:

            await cmd_status(message)
            return



        # -------------------------
        # Журнал
        # -------------------------

        if command in [
            "журнал",
            "📋 журнал"
        ]:

            await cmd_journal(message)
            return



        # -------------------------
        # Проверка системы
        # -------------------------

        if command in [
            "проверка",
            "❤️ проверка"
        ]:

            await cmd_health(message)
            return



        # -------------------------
        # Загрузка паспортов
        # -------------------------

        if command in [
            "загрузить паспорта",
            "📥 загрузить паспорта"
        ]:

            await cmd_load_passports(message)
            return



        # -------------------------
        # Прогноз
        # -------------------------

        words = text.split()


        if words[0].lower() in [
            "прогноз",
            "анализ",
            "счёт"
        ]:

            await handle_predict(
                message,
                core,
                journal
            )

            return



        # Например:
        # Зенит Спартак

        if len(words) >= 2 and not text.startswith("/"):

            await handle_predict(
                message,
                core,
                journal
            )

            return



        # -------------------------
        # Помощь
        # -------------------------

        await message.answer(
            """
⚽ FAJ Platform v5.1

Доступные функции:

📊 Статус
📋 Журнал
❤️ Проверка

⚽ Прогноз матча:

Пример:

Зенит Спартак

или

Прогноз Зенит Спартак


Система анализирует:

• паспорта команд
• xG
• форму
• вероятности
• возможные счета
            """,
            reply_markup=get_main_keyboard()
        )



    logger.info(
        "FAJ Platform v5.1 бот запущен"
    )


    await dp.start_polling(bot)
