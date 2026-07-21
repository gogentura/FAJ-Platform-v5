#!/usr/bin/env python3
import os
import asyncio
import logging
from dotenv import load_dotenv
from app.bot import run_bot
from app.core import FAJCore
from app.journal import Journal
from app.scheduler import schedule_notifications

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FAJ")

async def main():
    core = FAJCore()
    journal = Journal()
    logger.info("Запуск FAJ Platform v5.0")
    
    # Запускаем бота
    bot_task = asyncio.create_task(run_bot(core, journal))
    
    # Запускаем планировщик уведомлений
    chat_id = os.getenv("ADMIN_CHAT_ID")
    if chat_id:
        # Импортируем bot из bot.py (для доступа к объекту Bot)
        from app.bot import run_bot as run_bot_func
        # Временно создаём заглушку для бота, так как bot_instance не экспортируется
        # Для простоты пока пропустим уведомления до завтра
        logger.warning("Уведомления пока отключены, чтобы не сломать бота. Завтра настроим.")
    else:
        logger.warning("ADMIN_CHAT_ID не задан, уведомления не будут отправляться.")
    
    await bot_task

if __name__ == "__main__":
    asyncio.run(main())
