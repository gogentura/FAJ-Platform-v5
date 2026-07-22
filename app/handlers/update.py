from aiogram.types import Message
from app.sync_manager import SyncManager


async def cmd_update_team(message: Message):

    text = message.text.split()

    if len(text) < 2:
        await message.answer(
            "Используй:\n/update_team Команда Лига\n\nПример:\n/update_team Real LaLiga"
        )
        return


    team = text[1]

    league = "RPL"

    if len(text) >= 3:
        league = text[2]


    await message.answer(
        f"⏳ Обновляю {team} ({league})..."
    )


    try:

        sync = SyncManager()

        result = await sync.update_team(
            team,
            league
        )


        if not result:

            await message.answer(
                "❌ SyncManager вернул пустой ответ"
            )
            return


        if result.get("status") == "ok":

            await message.answer(
                f"✅ Паспорт {team} создан\n"
                f"🏆 Лига: {league}\n"
                f"📊 Источник: {result.get('source', 'нет данных')}"
            )

        else:

            await message.answer(
                "❌ Ошибка обновления:\n"
                f"{result}"
            )


    except Exception as e:

        await message.answer(
            "❌ Исключение:\n"
            f"{type(e).__name__}: {e}"
        )



async def cmd_update_rpl(message: Message):

    await message.answer(
        "⏳ Обновляю паспорта РПЛ..."
    )


    try:

        sync = SyncManager()

        result = await sync.update_rpl()


        await message.answer(
            f"✅ Завершено.\n"
            f"Команд обработано: {len(result.get('results', []))}"
        )


    except Exception as e:

        await message.answer(
            "❌ Ошибка РПЛ:\n"
            f"{type(e).__name__}: {e}"
        )
