from aiogram.types import Message

from app.passport_manager import load_passport


async def cmd_passport(message: Message):

    args = message.text.split(maxsplit=1)


    if len(args) < 2:
        await message.answer(
            "Использование:\n/passport Название команды"
        )
        return


    team_name = args[1]


    passport = load_passport(team_name)


    if not passport:

        await message.answer(
            f"❌ Паспорт {team_name} не найден\n"
            f"Обновите: /update_team {team_name}"
        )

        return



    text = f"""
📘 PASSPORT FAJ v5.1

🏟 Команда: {passport.get('team', team_name)}

🏆 Лига: {passport.get('league', 'Не указана')}

⚔️ Attack:
{passport.get('attack', 70)}

🛡 Defense:
{passport.get('defense', 70)}

🎯 Control:
{passport.get('control', 70)}

📈 Form:
{passport.get('form_index', 70)}

⚽ Historical xG:
{passport.get('historical_xg_value', 1.35)}

🧠 FAJ Version:
{passport.get('version', '5.1')}

📅 Updated:
{passport.get('last_updated', 'unknown')}
"""


    await message.answer(text)
