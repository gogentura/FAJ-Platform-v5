from aiogram.types import Message
from app.passport_manager import load_passport, get_team_by_alias, get_all_aliases
from app.handlers.keyboard import get_main_keyboard

async def cmd_passport(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите команду:\n/passport Название команды",
            reply_markup=get_main_keyboard()
        )
        return

    raw_team = args[1]
    team = get_team_by_alias(raw_team)
    if not team:
        await message.answer(
            f"❌ Команда '{raw_team}' не найдена. Проверьте название.",
            reply_markup=get_main_keyboard()
        )
        return

    passport = load_passport(team)
    if passport is None:
        await message.answer(
            f"❌ Паспорт команды '{team}' не найден. Обновите: /update_team {team}",
            reply_markup=get_main_keyboard()
        )
        return

    aliases = get_all_aliases(team)
    aliases_text = ", ".join(aliases) if aliases else "нет"

    text = f"""
📘 **PASSPORT FAJ v5.2**

🏟 **Команда:** {team}
🏆 **Лига:** {passport.get("league", "RPL")}

━━━━━━━━━━━━━━━━━━

⚔️ **Attack:** {passport.get("attack")}
🛡 **Defense:** {passport.get("defense")}
🎯 **Control:** {passport.get("control")}
📈 **Form:** {passport.get("form_index")}

━━━━━━━━━━━━━━━━━━

⚡ **Efficiency:** {passport.get("efficiency", "-")}
🧠 **Mentality:** {passport.get("mentality", "-")}
🏠 **Home:** {passport.get("home_rating", "-")}
✈ **Away:** {passport.get("away_rating", "-")}

⚽ **Historical xG:** {passport.get("historical_xg_value", "-")}
👨‍🏫 **Coach:** {passport.get("coach_factor", "-")}
🏥 **Injury:** {passport.get("injury_index", "-")}
🔋 **Fatigue:** {passport.get("fatigue_index", "-")}

━━━━━━━━━━━━━━━━━━

🧠 **Version:** {passport.get("version")}
📅 **Updated:** {passport.get("updated")}

🔗 **Синонимы:** {aliases_text}
"""
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
