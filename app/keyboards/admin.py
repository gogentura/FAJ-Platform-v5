# =====================================================
# FAJ Platform v6.1
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
        ],

        [
            KeyboardButton(
                text="🔄 Синхронизировать календарь"
            ),
        ],

        [
            KeyboardButton(
                text="🔍 Проверить календарь"
            ),
        ],

        [
            KeyboardButton(
                text="🚀 Создать прогнозы тура"
            ),
        ],

        [
            KeyboardButton(
                text="🗄 Проверка базы"
            ),
        ],

        [
            KeyboardButton(
                text="⬅️ Главное меню"
            ),
        ]

    ]


    return ReplyKeyboardMarkup(

        keyboard=buttons,

        resize_keyboard=True

    )
