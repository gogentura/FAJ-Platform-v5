# =====================================================
# FAJ Platform v7.0.3
# app/handlers/passport.py
#
# Team Passport Viewer
#
# PostgreSQL compatible
#
# Compatible:
# - bot.py
# - passport_manager.py
# - PostgreSQL passports table
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
# SAFE VALUE
# =====================================================


def get_value(
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
# COMMAND:
#
# Паспорт Зенит
#
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
    # COMPATIBILITY FIELDS
    # =================================================


    form = get_value(

        passport,

        "form_index",

        get_value(
            passport,
            "form",
            0
        )

    )



    xg_for = get_value(

        passport,

        "historical_xg_value",

        get_value(
            passport,
            "xg_for",
            0
        )

    )



    xg_against = get_value(

        passport,

        "historical_xg_against_value",

        get_value(
            passport,
            "xg_against",
            0
        )

    )



    possession = get_value(

        passport,

        "avg_possession_value",

        0

    )



    coach = get_value(

        passport,

        "coach_factor",

        0

    )



    rating = get_value(

        passport,

        "faj_rating",

        0

    )



    # =================================================
    # MESSAGE
    # =================================================


    answer = f"""
⚽ *Паспорт: {get_value(passport,'team','')}*


🏆 Лига:
{get_value(passport,'league','')}


📅 Сезон:
{get_value(passport,'season','')}


━━━━━━━━━━━━━━


📊 *FAJ Team Profile*


⚔️ Атака:
{get_value(passport,'attack')}


🛡 Защита:
{get_value(passport,'defense')}


🎯 Контроль:
{get_value(passport,'control')}


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
{get_value(passport,'efficiency')}


🔥 Ментальность:
{get_value(passport,'mentality')}


📋 Дисциплина:
{get_value(passport,'discipline')}


🏃 Физика:
{get_value(passport,'fitness')}


🔮 Предсказуемость:
{get_value(passport,'predictability')}



━━━━━━━━━━━━━━


👔 Тренерский фактор:
{coach}



━━━━━━━━━━━━━━


🔄 Трансферы:
{get_value(passport,'transfer_index')}


🏥 Травмы:
{get_value(passport,'injury_index')}


😴 Усталость:
{get_value(passport,'fatigue_index')}



━━━━━━━━━━━━━━


🤖 *FAJ Rating*

{rating}



━━━━━━━━━━━━━━


Версия:

{get_value(passport,'version','FAJ v7.0.3')}
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



# =====================================================
# TEXT COMPATIBILITY
# =====================================================
#
# Старые версии bot.py используют:
#
# passport_text_handler
#
# =====================================================


async def passport_text_handler(
    message: types.Message
):


    text = (

        message.text

        or ""

    ).strip()



    if not text.lower().startswith(
        "паспорт"
    ):

        return



    await cmd_passport(
        message
    )



# =====================================================
# EXPORTS
# =====================================================


__all__ = [

    "cmd_passport",

    "button_passport",

    "passport_text_handler"

]
