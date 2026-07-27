#!/usr/bin/env python3
# =====================================================
# FAJ Platform v7.0.1
# main.py
#
# Entry Point
#
# PostgreSQL
# FAJ Core
# Prediction Pipeline
# Journal
# Telegram Bot
# =====================================================


import asyncio
import logging

from dotenv import load_dotenv


# =====================================================
# ENV
# =====================================================

load_dotenv()



# =====================================================
# INTERNAL IMPORTS
# =====================================================

from app.database import init_db

from app.core.faj_core import FAJCore

from app.journal import Journal

from app.bot import run_bot



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
# VERSION
# =====================================================

FAJ_VERSION = "7.0.1"



# =====================================================
# MAIN
# =====================================================


async def main():


    logger.info(
        "🚀 Starting FAJ Platform %s",
        FAJ_VERSION
    )


    try:


        # =============================================
        # DATABASE
        # =============================================

        logger.info(
            "🔄 Initializing PostgreSQL..."
        )


        init_db()


        logger.info(
            "✅ Database ready"
        )



        # =============================================
        # CORE ENGINE
        # =============================================

        core = FAJCore()


        logger.info(
            "✅ FAJ Core loaded: %s",
            core.VERSION
        )



        # =============================================
        # JOURNAL
        # =============================================

        journal = Journal()


        logger.info(
            "✅ Journal loaded"
        )



        # =============================================
        # BOT
        # =============================================

        logger.info(
            "🤖 Starting Telegram Bot..."
        )


        await run_bot(

            core,

            journal

        )



    except Exception as e:


        logger.exception(

            "❌ FAJ startup failed: %s",

            e

        )


        raise



# =====================================================
# ENTRY
# =====================================================


if __name__ == "__main__":

    asyncio.run(
        main()
    )
