from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.notifier import Notifier

scheduler = AsyncIOScheduler()

async def schedule_notifications(bot, chat_id):
    notifier = Notifier(bot)
    # Отправляем сразу для проверки
    await notifier.send_top_matches(chat_id)
    # Планируем на понедельник и четверг в 10:00
    scheduler.add_job(
        notifier.send_top_matches,
        "cron",
        day_of_week="mon,thu",
        hour=10,
        minute=0,
        args=[chat_id]
    )
    scheduler.start()
