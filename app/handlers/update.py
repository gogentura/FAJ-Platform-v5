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


    sync = SyncManager()

    result = await sync.update_team(
        team,
        league
    )


    if result.get("status") == "ok":

        await message.answer(
            f"✅ Паспорт {team} создан\n"
            f"🏆 Лига: {league}\n"
            f"📊 Источник: {result.get('source')}"
        )

    else:

        await message.answer(
            f"❌ Ошибка:\n{result.get('message')}"
        )



async def cmd_update_rpl(message: Message):

    await message.answer(
        "⏳ Обновляю паспорта РПЛ..."
    )

    sync = SyncManager()

    result = await sync.update_rpl()

    await message.answer(
        f"✅ Завершено.\nКоманд обработано: {len(result.get('results', []))}"
    )
