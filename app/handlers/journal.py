from aiogram import types
from app.journal import Journal
from app.handlers.keyboard import get_main_keyboard

journal = Journal()

async def cmd_journal(message: types.Message):
    entries = journal.get_all(limit=5)
    if not entries:
        await message.answer("📭 Журнал пуст", reply_markup=get_main_keyboard())
        return
    text = "📋 *Последние прогнозы:*\n"
    for e in entries:
        text += f"• {e['match']}: {e['prediction']} (факт: {e.get('actual_score', '?')})\n"
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
