from aiogram import types
from app.passport_manager import load_passport
from app.handlers.keyboard import get_main_keyboard

async def cmd_passport(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи команду: /passport Спартак", reply_markup=get_main_keyboard())
        return
    team = args[1]
    passport = load_passport(team)
    if not passport:
        await message.answer(f"❌ Паспорт {team} не найден. Обнови: /update_team {team}", reply_markup=get_main_keyboard())
        return
    text = (
        f"📋 *{team}*\n"
        f"Passport v{passport['version']}\n"
        f"🔄 {passport['last_updated']}\n"
        f"⚔️ Атака: {passport['attack']}\n"
        f"🛡️ Защита: {passport['defense']}\n"
        f"🎮 Контроль: {passport['control']}\n"
        f"📈 Форма: {passport['form_index']}\n"
        f"📊 xG: {passport['avg_xg']:.2f}"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
