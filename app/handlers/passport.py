from aiogram.types import Message

from app.passport_manager import load_passport


async def cmd_passport(message: Message):

    args = message.text.split(maxsplit=1)

    if len(args) < 2:

        await message.answer(
            "Использование:\n/passport Название команды"
        )

        return


    team = args[1]

    passport = load_passport(team)

    if passport is None:

        await message.answer(
            f"❌ Паспорт команды '{team}' не найден."
        )

        return


    text = f"""
📘 PASSPORT FAJ v5.2

🏟 Команда:
{passport.get("team")}

🏆 Лига:
{passport.get("league")}

━━━━━━━━━━━━━━━━━━

⚔️ Attack:
{passport.get("attack")}

🛡 Defense:
{passport.get("defense")}

🎯 Control:
{passport.get("control")}

📈 Form:
{passport.get("form_index")}

━━━━━━━━━━━━━━━━━━

⚡ Efficiency:
{passport.get("efficiency", "-")}

🧠 Mentality:
{passport.get("mentality", "-")}

🏠 Home:
{passport.get("home_rating", "-")}

✈ Away:
{passport.get("away_rating", "-")}

⚽ Historical xG:
{passport.get("historical_xg_value")}

👨‍🏫 Coach:
{passport.get("coach_factor", "-")}

🏥 Injury:
{passport.get("injury_index", "-")}

🔋 Fatigue:
{passport.get("fatigue_index", "-")}

━━━━━━━━━━━━━━━━━━

🧠 Version:
{passport.get("version")}

📅 Updated:
{passport.get("last_updated")}
"""

    await message.answer(text)
