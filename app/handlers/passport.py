# =====================================================
# FAJ Platform v7.0.3
# app/handlers/passport.py
#
# Team Passport Viewer
#
# PostgreSQL compatible
#
# =====================================================


import logging

from aiogram import types

from app.passport_manager import (
    load_passport,
    get_team_by_alias
)

from app.keyboards.main import main_keyboard


logger = logging.getLogger(__name__)



# =====================================================
# SAFE VALUE
# =====================================================

def val(
    passport,
    key,
    default=0
):

    value = passport.get(
        key,
        default
    )

    if value is None:
        return default

    return value



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

            """
📁 Паспорт команды FAJ

Пример:

Паспорт Зенит

Доступны команды РПЛ.
""",

            reply_markup=main_keyboard()

        )


        return



    team_input = parts[1].strip()



    team = get_team_by_alias(
        team_input
    )



    if not team:

        team = team_input



    passport = load_passport(
        team
    )



    if not passport:


        await message.answer(

            f"""
❌ Паспорт не найден

Команда:
{team_input}

Проверьте название.
""",

            reply_markup=main_keyboard()

        )


        return



    # =================================================
    # DATA
    # =================================================


    form = val(

        passport,

        "form_index",

        val(
            passport,
            "form",
            0
        )

    )


    xg_for = val(

        passport,

        "historical_xg_value",

        val(
            passport,
            "xg_for",
            0
        )

    )


    xg_against = val(

        passport,

        "historical_xg_against_value",

        val(
            passport,
            "xg_against",
            0
        )

    )


    possession = val(

        passport,

        "avg_possession_value",

        0

    )


    coach = val(

        passport,

        "coach_factor",

        0

    )



    rating = val(

        passport,

        "faj_rating",

        0

    )



    answer = f"""
⚽ *Паспорт: {val(passport,'team','')}*

🏆 Лига:
{val(passport,'league','')}

📅 Сезон:
{val(passport,'season','')}


━━━━━━━━━━━━━━

📊 *FAJ Team Profile*

⚔️ Атака:
{val(passport,'attack')}

🛡 Защита:
{val(passport,'defense')}

🎯 Контроль:
{val(passport,'control')}

📈 Форма:
{form}


━━━━━━━━━━━━━━

📊 *Advanced Metrics*

⚽ xG создано:
{xg_for}

🛡 xG пропущено:
{xg_against}

🔵 Владение:
{possession}


━━━━━━━━━━━━━━

🧠 *Командные индексы*

⚙️ Эффективность:
{val(passport,'efficiency')}

🔥 Ментальность:
{val(passport,'mentality')}

📋 Дисциплина:
{val(passport,'discipline')}

🏃 Физика:
{val(passport,'fitness')}

🔮 Предсказуемость:
{val(passport,'predictability')}


━━━━━━━━━━━━━━

👔 Тренерский фактор:
{coach}


━━━━━━━━━━━━━━

🔄 Трансферы:
{val(passport,'transfer_index')}

🏥 Травмы:
{val(passport,'injury_index')}

😴 Усталость:
{val(passport,'fatigue_index')}


━━━━━━━━━━━━━━

🤖 *FAJ Rating*

{rating}


━━━━━━━━━━━━━━

Версия:
{val(passport,'version','FAJ v7.0.3')}
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

        """
📁 Раздел паспортов FAJ


Введите:

Паспорт Зенит


Доступны паспорта команд РПЛ.
""",

        reply_markup=main_keyboard()

    )
