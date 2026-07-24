# =====================================================
# FAJ Platform v6.0
# Predictions Keyboards
# =====================================================


from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)



# =====================================================
# PREDICTIONS MENU
# =====================================================


def predictions_keyboard():

    buttons = [

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
                text="🏆 Прогноз тура"
            )

        ],

        [

            KeyboardButton(
                text="⬅️ Главное меню"
            )

        ]

    ]


    return ReplyKeyboardMarkup(

        keyboard=buttons,

        resize_keyboard=True

    )
