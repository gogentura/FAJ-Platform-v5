# =====================================================
# FAJ Platform v7.0.1
# app/handlers/passport.py
#
# Team Passport Viewer
# PostgreSQL compatible
# =====================================================


import logging

from aiogram import types

from app.passport_manager import (
    load_passport,
    get_team_by_alias
)

from app.keyboards.main import (
    main_keyboard
)


logger = logging.getLogger(__name__)


# =====================================================
# PASSPORT COMMAND
# =====================================================

async def cmd_passport(
    message: types.Message
):

    text = (
        message.text
        or ""
    ).strip()


    parts = text.split(
        maxsplit=1
    )


    if len(parts) < 2:

        await message.answer(
            "📁 Паспорт команды\n\n"
            "Пример:\n"
            "Паспорт Зенит",
            reply_markup=main_keyboard()
        )

        return



    team_input = parts[1].strip()


    team = get_team_by_alias(
        team_input
    )


    passport = load_passport(
        team
    )


    if not passport:

        await message.answer(

            f"❌ Паспорт {team_input} не найден.\n\n"
            "Проверь загрузку паспортов.",

            reply_markup=main_keyboard()

        )

        return



    def val(
        key,
        default=0
    ):

        return passport.get(
            key,
            default
        )


    answer = f"""
⚽ *Паспорт: {val('team','')}*

🏆 Лига:
{val('league','')}

📅 Сезон:
{val('season','')}

━━━━━━━━━━━━━━

📊 *FAJ Team Profile*

⚔️ Атака:
{val('attack')}

🛡 Защита:
{val('defense')}

🎯 Контроль:
{val('control')}

📈 Форма:
{val('form')}


━━━━━━━━━━━━━━

📊 *xG показатели*

Создано:
{val('xg_for')}

Пропущено:
{val('xg_against')}


━━━━━━━━━━━━━━

🧠 *Командные индексы*

Эффективность:
{val('efficiency')}

Ментальность:
{val('mentality')}

Дисциплина:
{val('discipline')}

Физика:
{val('fitness')}

Предсказуемость:
{val('predictability')}


━━━━━━━━━━━━━━

🔄 Трансферы:
{val('transfer_index')}

🏥 Травмы:
{val('injury_index')}

😴 Усталость:
{val('fatigue_index')}


━━━━━━━━━━━━━━

🤖 FAJ Rating:
{val('faj_rating')}

Версия:
FAJ v7.0.1
"""


    await message.answer(

        answer,

        parse_mode="Markdown",

        reply_markup=main_keyboard()

    )


# =====================================================
# BUTTON
# =====================================================

async def button_passport(
    message: types.Message
):

    await message.answer(

        "📁 Раздел паспортов\n\n"
        "Введите:\n\n"
        "Паспорт Зенит\n\n"
        "Доступны команды РПЛ.",

        reply_markup=main_keyboard()

    )


# =====================================================
# TEXT ROUTER
# =====================================================

async def passport_text_handler(
    message: types.Message
):

    if not message.text:
        return


    if message.text.lower().startswith(
        "паспорт"
    ):

        await cmd_passport(
            message
        )
