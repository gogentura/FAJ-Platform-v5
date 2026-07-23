from aiogram import types
from app.status import get_full_status
from app.handlers.keyboard import get_main_keyboard

async def cmd_status(message: types.Message):
    text = get_full_status()
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
