from aiogram import types

from app.keyboards.main import main_keyboard


async def cmd_main_menu(
    message: types.Message
):

    await message.answer(

        "🏠 Главное меню",

        reply_markup=main_keyboard()

    )
