from aiogram import types

from app.passport_manager import (
    get_team_by_alias,
    load_passport
)

from app.handlers.keyboard import get_main_keyboard



async def cmd_passport(
    message: types.Message
):

    # Получаем название после слова "Паспорт"

    text = message.text.strip()

    team_name = (
        text
        .replace("Паспорт", "")
        .replace("паспорт", "")
        .strip()
    )


    if not team_name:

        await message.answer(
            "📁 Раздел паспортов\n\n"
            "Пример:\n"
            "Паспорт Зенит",
            reply_markup=get_main_keyboard()
        )

        return



    # Проверяем алиасы

    team = get_team_by_alias(
        team_name
    )


    if not team:

        await message.answer(
            f"❌ Паспорт команды {team_name} не найден.\n\n"
            "Проверь название команды.",
            reply_markup=get_main_keyboard()
        )

        return



    # Загружаем паспорт

    passport = load_passport(
        team
    )


    if not passport:

        await message.answer(
            f"❌ Паспорт {team} отсутствует в базе.",
            reply_markup=get_main_keyboard()
        )

        return



    # Формируем вывод


    answer = f"""
📁 Паспорт команды
⚽ {team}

🏆 Лига:
{passport.get('league','RPL')}

──────────────

⚔️ Атака:
{passport.get('attack',0)}

🛡 Защита:
{passport.get('defense',0)}

🎯 Контроль:
{passport.get('control',0)}

📈 Форма:
{passport.get('form_index',0)}

──────────────

⚽ Исторический xG:
{passport.get('historical_xg_value',0)}

🥅 Средние голы:
{passport.get('avg_goals_value',0)}

🛡 Пропущенные:
{passport.get('avg_goals_conceded_value',0)}

🎯 Владение:
{passport.get('avg_possession_value',0)}%

──────────────

👔 Тренерский фактор:
{passport.get('coach_factor',0)}

🏠 Домашний рейтинг:
{passport.get('home_rating',0)}

✈️ Выездной рейтинг:
{passport.get('away_rating',0)}

──────────────

📌 Версия паспорта:
{passport.get('version',1)}

🕒 Обновлён:
{passport.get('updated','-')}
"""


    await message.answer(
        answer,
        reply_markup=get_main_keyboard()
    )
