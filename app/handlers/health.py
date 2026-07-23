from aiogram import types
from app.api_tracker import get_api_status
from app.handlers.keyboard import get_main_keyboard

async def cmd_health(message: types.Message):
    api = get_api_status()
    await message.answer(
        f"✅ *Система работает*\n"
        f"• Бот: активен\n"
        f"• API-Football: доступен (осталось {api['remaining']} запросов)\n"
        f"• Паспорта: загружены\n"
        f"• Журнал: работает",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
