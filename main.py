#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv
from app.bot import run_bot
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.database import init_db
from app.passport_manager import init_default_aliases

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FAJ")

async def main():
    init_db()
    init_default_aliases()   # загружаем синонимы
    logger.info("База данных инициализирована")
    core = FAJCore()
    journal = Journal()
    logger.info("Запуск FAJ Platform v5.1")
    await run_bot(core, journal)

if __name__ == "__main__":
    asyncio.run(main())
