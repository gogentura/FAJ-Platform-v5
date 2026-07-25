# =====================================================
# FAJ Platform v6.3.3
# app/handlers/clear_journal.py
# =====================================================

from aiogram.types import Message

from app.journal import clear_journal


async def cmd_clear_journal(message: Message):

    try:

        clear_journal()

        await message.answer(

            "🗑 Журнал FAJ успешно очищен.\n\n"
            "📋 История прогнозов начинается заново.\n"
            "Версия журнала: FAJ Platform v6.3.3"

        )

    except Exception as e:

        await message.answer(

            "❌ Не удалось очистить журнал.\n\n"
            f"Ошибка:\n{e}"

        )
