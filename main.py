#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FAJ")

async def main():
    from app.bot import run_bot
    from app.core import FAJCore
    from app.journal import Journal
    core = FAJCore()
    journal = Journal()
    logger.info("Запуск FAJ Platform v5.0")
    await run_bot(core, journal)

if __name__ == "__main__":
    asyncio.run(main())
