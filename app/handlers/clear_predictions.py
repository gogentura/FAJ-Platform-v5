# =====================================================
# FAJ Platform v6.0
# Clear Predictions
# =====================================================

from aiogram import types

from app.database import get_db


async def cmd_clear_predictions(
    message: types.Message
):

    conn = get_db()

    try:

        conn.execute(
            """
            DELETE FROM predictions
            """
        )

        conn.commit()


        await message.answer(
            """
🗑 Старые прогнозы удалены


Теперь:

⚙️ Админ

↓

🚀 Создать прогнозы тура


FAJ создаст новые прогнозы
по текущему календарю fixtures.
"""
        )


    except Exception as e:

        conn.rollback()

        await message.answer(
            f"❌ Ошибка очистки:\n{e}"
        )


    finally:

        conn.close()
