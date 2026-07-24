#!/usr/bin/env python3
# =====================================================
# FAJ Platform v6.2
# main.py
# =====================================================

import asyncio
import logging

from dotenv import load_dotenv


from app.bot import run_bot

from app.core.faj_core import FAJCore

from app.journal import Journal

from app.database import init_db



# =====================================================
# ENV
# =====================================================

load_dotenv()



# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(

    level=logging.INFO,

    format=
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

)


logger = logging.getLogger(
    "FAJ"
)



# =====================================================
# MAIN
# =====================================================


async def main():


    logger.info(
        "🚀 Запуск FAJ Platform v6.2"
    )


    try:


        # PostgreSQL + migrations

        init_db()


        logger.info(
            "✅ Database initialized"
        )



        core = FAJCore()


        journal = Journal()



        logger.info(
            "✅ FAJ Core loaded"
        )



        await run_bot(

            core,

            journal

        )



    except Exception as e:


        logger.exception(

            f"FAJ startup error: {e}"

        )


        raise



# =====================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
