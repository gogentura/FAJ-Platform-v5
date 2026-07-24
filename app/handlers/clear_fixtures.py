from aiogram import types

from app.database import get_db


async def cmd_clear_fixtures(
    message: types.Message
):

    conn = get_db()

    try:

        result = conn.execute(
            """
            DELETE FROM fixtures
            WHERE league = ?
            """,
            (
                "RPL",
            )
        )

        conn.commit()

        count = result.rowcount


        await message.answer(
            f"""
🗑 FAJ Fixtures очистка


🏆 Лига: RPL


Удалено матчей:
{count}


Теперь можно выполнить:

🔄 Синхронизировать календарь
"""
        )


    except Exception as e:

        conn.rollback()

        await message.answer(
            f"""
❌ Ошибка очистки fixtures

{str(e)}
"""
        )


    finally:

        conn.close()
