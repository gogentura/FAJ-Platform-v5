from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)


def admin_keyboard():

    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(text="📥 Загрузить календарь")
            ],

            [
                KeyboardButton(text="📥 Обновить паспорта")
            ],

            [
                KeyboardButton(text="🌐 API Football")
            ],

            [
                KeyboardButton(text="🗄 База данных")
            ],

            [
                KeyboardButton(text="⬅️ Главное меню")
            ]

        ],

        resize_keyboard=True

    )
