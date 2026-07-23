from aiogram import types
from app.passport_manager import load_passport
from app.handlers.keyboard import get_main_keyboard


async def cmd_passport(message: types.Message):

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "Пример:\n\nПаспорт Зенит",
            reply_markup=get_main_keyboard()
        )
        return


    team = " ".join(parts[1:])


    passport = load_passport(team)


    if not passport:
        await message.answer(
            f"❌ Паспорт команды {team} не найден",
            reply_markup=get_main_keyboard()
        )
        return


    text = (
        f"📁 *Паспорт: {passport['team']}*\n\n"

        f"🏆 Лига: {passport.get('league','')}\n\n"

        f"⚔ Атака: {passport.get('attack')}\n"
        f"🛡 Защита: {passport.get('defense')}\n"
        f"🎯 Контроль: {passport.get('control')}\n"
        f"📈 Форма: {passport.get('form_index')}\n\n"

        f"⚽ xG:\n"
        f"{passport.get('historical_xg_value')}\n\n"

        f"🥅 Средние голы:\n"
        f"{passport.get('avg_goals_value')}\n\n"

        f"🧤 Пропущено:\n"
        f"{passport.get('avg_goals_conceded_value')}\n\n"

        f"👔 Тренерский фактор:\n"
        f"{passport.get('coach_factor')}\n\n"

        f"🔄 Версия: {passport.get('version')}\n"
        f"🕒 Обновлено:\n{passport.get('updated')}"
    )


    await message.answer(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
