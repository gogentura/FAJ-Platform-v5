import logging

from aiogram import types

from app.passport_manager import load_passport, get_team_by_alias
from app.handlers.keyboard import get_main_keyboard


logger = logging.getLogger(__name__)


async def cmd_passport(message: types.Message):

    text = message.text.strip()

    parts = text.split(maxsplit=1)


    if len(parts) < 2:

        await message.answer(
            "📁 Паспорт команды\n\n"
            "Пример:\n"
            "Паспорт Зенит",
            reply_markup=get_main_keyboard()
        )

        return



    team_input = parts[1].strip()


    team = get_team_by_alias(team_input)


    if not team:

        team = team_input



    passport = load_passport(team)



    if not passport:

        await message.answer(
            f"❌ Паспорт команды {team_input} не найден.\n\n"
            "Проверь название команды.",
            reply_markup=get_main_keyboard()
        )

        return



    answer = f"""
⚽ Паспорт: {passport['team']}

🏆 Лига: {passport['league']}

──────────────

📊 Сила команды

⚔️ Атака:
{passport['attack']}

🛡 Защита:
{passport['defense']}

🎯 Контроль:
{passport['control']}

📈 Форма:
{passport['form_index']}

──────────────

📊 Исторические данные

xG:
{passport['historical_xg_value']}

Голы:
{passport['avg_goals_value']}

Пропущено:
{passport['avg_goals_conceded_value']}

Владение:
{passport['avg_possession_value']}%

──────────────

🧠 Дополнительно

Тренер:
{passport['coach_factor']}

Дом:
{passport['home_rating']}

Выезд:
{passport['away_rating']}

Травмы:
{passport['injury_index']}

Усталость:
{passport['fatigue_index']}

──────────────

📌 Версия паспорта:
{passport['version']}

Обновлён:
{passport['updated']}
"""


    await message.answer(
        answer,
        reply_markup=get_main_keyboard()
    )



async def button_passport(message: types.Message):

    await message.answer(
        "📁 Раздел паспортов\n\n"
        "Пример:\n\n"
        "Паспорт Зенит\n\n"
        "Доступны паспорта команд РПЛ.",
        reply_markup=get_main_keyboard()
    )
