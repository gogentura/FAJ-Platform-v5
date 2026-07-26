# =====================================================
# FAJ Platform v6.6
# app/keyboards/admin.py
#
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
                text="🔄 Обновить результаты"
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
                text="🤖 FAJ прогнозы"
            ),
        ],



        [
            KeyboardButton(
                text="🧠 Анализ ошибок FAJ"
            ),
        ],



        [
            KeyboardButton(
                text="🗄 Проверка базы"
            ),
        ],



        [
            KeyboardButton(
                text="🗑 Очистить журнал"
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
