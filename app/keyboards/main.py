from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)


def main_keyboard():

    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="📈 Прогноз")
            ],

            [
                KeyboardButton(text="📁 Паспорта"),
                KeyboardButton(text="📅 Матчи")
            ],

            [
                KeyboardButton(text="🏆 Турниры"),
                KeyboardButton(text="📋 Журнал")
            ],

            [
                KeyboardButton(text="⚙️ Админ"),
                KeyboardButton(text="❤️ Проверка")
            ]

        ],

        resize_keyboard=True

    )
