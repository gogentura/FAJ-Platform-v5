from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_keyboard():

    buttons = [

        [
            KeyboardButton(text="📊 Статус"),
            KeyboardButton(text="⚽ Прогноз")
        ],

        [
            KeyboardButton(text="📚 Паспорт"),
            KeyboardButton(text="👥 Команды")
        ],

        [
            KeyboardButton(text="🏆 Таблица"),
            KeyboardButton(text="🌍 Лиги")
        ],

        [
            KeyboardButton(text="📋 Журнал"),
            KeyboardButton(text="❤️ Проверка")
        ]

    ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )
