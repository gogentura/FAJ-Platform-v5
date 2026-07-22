from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="📋 Журнал")],
        [KeyboardButton(text="🔄 Обновить РПЛ"), KeyboardButton(text="📁 Паспорт")],
        [KeyboardButton(text="⚙️ Здоровье"), KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
