# =====================================================
# FAJ Platform v6.0
# Admin Keyboard
# =====================================================


from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)




def admin_keyboard():



    buttons = [


        [

            KeyboardButton(
                text="📥 Загрузить паспорта"
            ),

            KeyboardButton(
                text="📥 Загрузить календарь"
            )

        ],


        [

            KeyboardButton(
                text="🚀 Создать прогнозы тура"
            )

        ],


        [

            KeyboardButton(
                text="🗄 Проверка базы"
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
