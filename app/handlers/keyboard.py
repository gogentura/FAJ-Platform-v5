# =====================================================
# FAJ Platform v5.2
# Main Telegram Keyboard
# =====================================================


from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)



def get_main_keyboard():


    buttons = [

        [
            KeyboardButton(
                text="📊 Статус"
            ),

            KeyboardButton(
                text="📁 Паспорт"
            )
        ],


        [
            KeyboardButton(
                text="📈 Прогноз"
            ),

            KeyboardButton(
                text="📅 Матчи"
            )
        ],


        [
            KeyboardButton(
                text="📋 Журнал"
            ),

            KeyboardButton(
                text="❤️ Проверка"
            )
        ]

    ]


    return ReplyKeyboardMarkup(

        keyboard=buttons,

        resize_keyboard=True

    )
