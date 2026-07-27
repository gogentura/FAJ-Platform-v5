# =====================================================
# FAJ Platform v6.9.4
# app/keyboards/faj_navigation.py
# =====================================================

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def faj_navigation_keyboard(index: int, total: int):

    keyboard = []

    buttons = []

    # Предыдущий
    if index > 0:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ Предыдущий матч",
                callback_data=f"faj_prev_{index}"
            )
        )

    # Следующий
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

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )
