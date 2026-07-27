# =====================================================
# FAJ Platform v6.9.4
# app/keyboards/faj_navigation.py
#
# FAJ Match Navigation Keyboard
#
# Compatible:
# - faj_predictions.py v6.9.4
# - aiogram 3.x
# =====================================================


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton





# =====================================================
# NAVIGATION KEYBOARD
# =====================================================


def faj_navigation_keyboard(
    index,
    total
):


    buttons = []



    # =============================================
    # PREVIOUS
    # =============================================

    if index > 0:

        buttons.append(

            InlineKeyboardButton(

                text="⬅️ Предыдущий матч",

                callback_data=f"faj_prev:{index}"

            )

        )



    # =============================================
    # NEXT
    # =============================================

    if index < total - 1:

        buttons.append(

            InlineKeyboardButton(

                text="Следующий матч ➡️",

                callback_data=f"faj_next:{index}"

            )

        )




    keyboard = []



    if buttons:

        keyboard.append(
            buttons
        )




    # =============================================
    # COUNTER
    # =============================================


    keyboard.append(

        [

            InlineKeyboardButton(

                text=f"⚽ {index+1}/{total}",

                callback_data="faj_noop"

            )

        ]

    )



    return InlineKeyboardMarkup(

        inline_keyboard=keyboard

    )






# =====================================================
# END
# =====================================================
