#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv
from app.bot import run_bot
from app.core.faj_core import FAJCore
from app.journal import Journal
from app.database import init_db

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FAJ")

async def main():
    logger.info("Запуск FAJ Platform v5.1 (чистая установка)")
    init_db()
    core = FAJCore()
    journal = Journal()
    await run_bot(core, journal)

if __name__ == "__main__":
    asyncio.run(main())
