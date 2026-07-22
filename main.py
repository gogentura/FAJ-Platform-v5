import asyncio
import logging

from app.bot import run_bot
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.rpl_database import load_rpl_database


logging.basicConfig(
    level=logging.INFO
)


logger = logging.getLogger("FAJ")


async def main():

    logger.info("Запуск FAJ Platform v5.1")


    # Загрузка базы РПЛ и создание паспортов
    try:
        load_rpl_database()

        logger.info(
            "База РПЛ загружена"
        )

    except Exception as e:

        logger.error(
            f"Ошибка загрузки РПЛ базы: {e}"
        )



    # Создание ядра FAJ

    core = FAJCore()


    # Журнал аналитики

    journal = Journal()



    logger.info(
        f"FAJ Core версия: {core.version}"
    )


    # Запуск Telegram бота

    await run_bot(
        core,
        journal
    )



if __name__ == "__main__":

    asyncio.run(main())
