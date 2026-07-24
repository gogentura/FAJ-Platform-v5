from aiogram import types

from app.keyboards.admin import admin_keyboard


async def cmd_admin_menu(
    message: types.Message
):

    await message.answer(

        "⚙️ Панель администратора",

        reply_markup=admin_keyboard()

    )
