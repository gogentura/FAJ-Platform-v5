from aiogram import types
from app.update_manager import UpdateManager
from app.handlers.keyboard import get_main_keyboard

update_manager = UpdateManager()

async def cmd_update_rpl(message: types.Message):
    await message.answer("⏳ Обновляю РПЛ... (16 команд, ~5 секунд)", reply_markup=get_main_keyboard())
    result = await update_manager.update_rpl()
    updated = sum(1 for r in result["results"] if r["status"] == "ok")
    skipped = sum(1 for r in result["results"] if r["status"] == "skipped")
    await message.answer(f"✅ Обновлено: {updated}, пропущено (уже сегодня): {skipped}", reply_markup=get_main_keyboard())

async def cmd_update_team(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи команду: /update_team Спартак", reply_markup=get_main_keyboard())
        return
    team = args[1]
    await message.answer(f"⏳ Обновляю {team}...", reply_markup=get_main_keyboard())
    result = await update_manager.update_team(team)
    if result["status"] == "ok":
        await message.answer(f"✅ {team} обновлён (версия паспорта: {result['version']})", reply_markup=get_main_keyboard())
    else:
        await message.answer(f"❌ {result['message']}", reply_markup=get_main_keyboard())
