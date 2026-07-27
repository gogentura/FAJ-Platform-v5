# =====================================================
# FAJ Platform v6.9.4
# app/keyboards/faj_navigation.py
#
# FAJ Prediction Navigation Keyboard
#
# Buttons:
# - Previous match
# - Next match
# =====================================================


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton





# =====================================================
# MAIN NAVIGATION
# =====================================================


def faj_navigation_keyboard(
    index,
    total
):

    buttons = []



    # ===============================
    # PREVIOUS
    # ===============================

    if index > 0:

        buttons.append(

            InlineKeyboardButton(

                text="⬅️ Назад",

                callback_data=f"faj_prev:{index}"

            )

        )



    # ===============================
    # NEXT
    # ===============================

    if index < total - 1:

        buttons.append(

            InlineKeyboardButton(

                text="Следующий ➡️",

                callback_data=f"faj_next:{index}"

            )

        )



    # ===============================
    # ROWS
    # ===============================


    keyboard = []


    if buttons:

        keyboard.append(
            buttons
        )



    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )
