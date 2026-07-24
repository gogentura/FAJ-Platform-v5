# =====================================================
# FAJ Platform v6.0
# Fixtures Keyboard
# =====================================================


from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton
)



def fixtures_keyboard():


    return ReplyKeyboardMarkup(

        keyboard=[

            [
                KeyboardButton(
                    text="🇷🇺 РПЛ"
                ),

                KeyboardButton(
                    text="🌍 Все турниры"
                )
            ],


            [
                KeyboardButton(
                    text="🔥 Ближайшие матчи"
                )
            ],


            [
                KeyboardButton(
                    text="📈 Прогноз матча"
                )
            ],


            [
                KeyboardButton(
                    text="⬅️ Главное меню"
                )
            ]

        ],

        resize_keyboard=True

    )
