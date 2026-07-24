from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():

    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="📁 Паспорт")
            ],

            [
                KeyboardButton(text="📈 Прогноз"),
                KeyboardButton(text="📅 Матчи")
            ],

            [
                KeyboardButton(text="📋 Журнал"),
                KeyboardButton(text="❤️ Проверка")
            ],

            [
                KeyboardButton(text="📥 Загрузить календарь")
            ]

        ],

        resize_keyboard=True

    )
