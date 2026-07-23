from aiogram import types
from app.database import get_db
from app.handlers.keyboard import get_main_keyboard


def load_passport(team):
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM passports WHERE team = ?",
        (team,)
    ).fetchone()

    conn.close()

    return dict(row) if row else None



async def handle_passport(message: types.Message):

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer(
            "❌ Напиши:\n\n"
            "Паспорт Зенит",
            reply_markup=get_main_keyboard()
        )
        return


    team = " ".join(parts[1:])


    passport = load_passport(team)


    if not passport:
        await message.answer(
            f"❌ Паспорт команды {team} не найден.\n\n"
            "Проверь название команды.",
            reply_markup=get_main_keyboard()
        )
        return


    text = (
        f"📁 *Паспорт команды*\n\n"
        f"⚽ {passport['team']}\n"
        f"🏆 Лига: {passport.get('league','RPL')}\n\n"

        f"📊 Сила команды:\n"
        f"⚔️ Атака: {passport.get('attack',0)}\n"
        f"🛡 Защита: {passport.get('defense',0)}\n"
        f"🎯 Контроль: {passport.get('control',0)}\n"
        f"📈 Форма: {passport.get('form_index',0)}\n\n"

        f"📉 xG:\n"
        f"{passport.get('historical_xg_value',0)}\n\n"

        f"⚽ Средние голы:\n"
        f"Забито: {passport.get('avg_goals_value',0)}\n"
        f"Пропущено: {passport.get('avg_goals_conceded_value',0)}\n\n"

        f"🏟 Дом:\n"
        f"{passport.get('home_rating',0)}\n"

        f"✈️ Выезд:\n"
        f"{passport.get('away_rating',0)}\n\n"

        f"🤖 Версия FAJ: 5.1"
    )


    await message.answer(
        text,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
