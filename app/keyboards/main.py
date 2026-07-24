# =====================================================
# FAJ Platform v6.0
# Main Keyboard
# =====================================================


from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)



# =====================================================
# MAIN MENU
# =====================================================


def main_keyboard():

    buttons = [

        [

            KeyboardButton(
                text="📊 Статус"
            ),

            KeyboardButton(
                text="📈 Прогноз"
            )

        ],


        [

            KeyboardButton(
                text="📁 Паспорта"
            ),

            KeyboardButton(
                text="📅 Матчи"
            )

        ],


        [

            KeyboardButton(
                text="🤖 FAJ прогнозы"
            ),

            KeyboardButton(
                text="🧠 Мои прогнозы"
            )

        ],


        [

            KeyboardButton(
                text="🏆 Турниры"
            ),

            KeyboardButton(
                text="📋 Журнал"
            )

        ],


        [

            KeyboardButton(
                text="⚙️ Админ"
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
