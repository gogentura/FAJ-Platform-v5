# =====================================================
# FAJ Platform v6.3
# app/handlers/passports.py
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

from app.handlers.keyboard import (
    get_main_keyboard
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

            reply_markup=get_main_keyboard()

        )

        return



    team_input = parts[1].strip()



    # -----------------------------
    # ALIAS
    # -----------------------------

    team = get_team_by_alias(
        team_input
    )


    if not team:

        team = team_input



    # -----------------------------
    # LOAD
    # -----------------------------

    passport = load_passport(
        team
    )



    if not passport:


        await message.answer(

            f"❌ Паспорт {team_input} не найден.\n\n"
            "Доступные команды: РПЛ",

            reply_markup=get_main_keyboard()

        )

        return



    # -----------------------------
    # SAFE VALUES
    # -----------------------------

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

📊 *Командная модель FAJ*

⚔️ Атака:
{val('attack')}

🛡 Защита:
{val('defense')}

🎯 Контроль:
{val('control')}


📈 Форма:
{val('form')}


━━━━━━━━━━━━━━

📊 *xG модель*

Создано:
{val('xg_for')}

Пропущено:
{val('xg_against')}


━━━━━━━━━━━━━━

🧠 *Индексы*

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

Версия FAJ:
v6.3
"""


    await message.answer(

        answer,

        parse_mode="Markdown",

        reply_markup=get_main_keyboard()

    )




# =====================================================
# BUTTON
# =====================================================

async def button_passport(
    message: types.Message
):

    await message.answer(

        "📁 Раздел паспортов\n\n"
        "Пример:\n\n"
        "Паспорт Зенит\n\n"
        "Доступны паспорта команд РПЛ.",

        reply_markup=get_main_keyboard()

    )
