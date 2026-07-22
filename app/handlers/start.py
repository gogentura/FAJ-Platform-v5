from aiogram import types
from aiogram.filters import Command
from app.handlers.keyboard import get_main_keyboard

async def cmd_start(message: types.Message):
    await message.answer(
        "⚽ *FAJ Platform v5.1*\n\n"
        "Просто напиши две команды: Зенит Спартак\n"
        "Используй кнопки ниже 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
