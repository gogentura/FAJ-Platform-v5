# =====================================================
# FAJ Platform v6.9.5
# app/keyboards/faj_navigation.py
# =====================================================

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def faj_navigation_keyboard(index: int, total: int):

    keyboard = []

    buttons = []


    # Предыдущий матч
    if index > 0:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущий матч",
                callback_data=f"faj_prev_{index}"
            )
        )


    # Следующий матч
    if index < total - 1:
        buttons.append(
            InlineKeyboardButton(
                text="Следующий матч ➡️",
                callback_data=f"faj_next_{index}"
            )
        )


    if buttons:
        keyboard.append(buttons)


    keyboard.append(
        [
            InlineKeyboardButton(
                text=f"⚽ {index + 1}/{total}",
                callback_data="faj_noop"
            )
        ]
    )


    keyboard.append(
        [
            InlineKeyboardButton(
                text="📋 Весь тур",
                callback_data="faj_all_matches"
            )
        ]
    )


    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )



# =====================================================
# TOUR LIST KEYBOARD
# =====================================================

def faj_tour_keyboard(predictions):

    keyboard = []


    for index, prediction in enumerate(predictions):

        home = prediction.get(
            "home_team",
            "?"
        )

        away = prediction.get(
            "away_team",
            "?"
        )


        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{index+1}. ⚽ {home} — {away}",
                    callback_data=f"faj_open_{index}"
                )
            ]
        )


    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )
