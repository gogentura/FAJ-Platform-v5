from aiogram import types
from app.sync_manager import SyncManager
from app.handlers.keyboard import get_main_keyboard

sync_manager = SyncManager()

async def cmd_update_rpl(message: types.Message):
    await message.answer("⏳ Обновляю РПЛ... (16 команд, ~5 секунд)", reply_markup=get_main_keyboard())
    result = await sync_manager.update_rpl()
    updated = sum(1 for r in result["results"] if r["status"] == "ok")
    skipped = sum(1 for r in result["results"] if r["status"] == "skipped")
    await message.answer(f"✅ Обновлено: {updated}, пропущено (уже сегодня): {skipped}", reply_markup=get_main_keyboard())

async def cmd_update_team(message: types.Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("❌ Укажи команду: /update_team Спартак", reply_markup=get_main_keyboard())
        return
    team = args[1]
    league = args[2].upper() if len(args) > 2 and args[2].upper() in ["RPL", "EPL", "UCL"] else "RPL"
    await message.answer(f"⏳ Обновляю {team} ({league})...", reply_markup=get_main_keyboard())
    result = await sync_manager.update_team(team, league)
    if result["status"] == "ok":
        await message.answer(
            f"✅ {team} обновлён\nИсточник: {result['source']}\nПаспорт: v{result['version']}",
            reply_markup=get_main_keyboard()
        )
    elif result["status"] == "cached":
        await message.answer(
            f"📦 {team} — {result['message']}\nПаспорт: v{result['passport']['version']}",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(f"❌ {result['message']}", reply_markup=get_main_keyboard())
