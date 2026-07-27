# =====================================================
# FAJ Platform v7.0.2
# app/passport_manager.py
#
# PostgreSQL Passport Layer
# Compatible with existing passports table
# =====================================================


import logging

from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# ALIASES
# =====================================================


TEAM_ALIASES = {

    "зенит": "Зенит",
    "Зенит": "Зенит",

    "спартак": "Спартак",
    "Спартак": "Спартак",

    "цска": "ЦСКА",
    "ЦСКА": "ЦСКА",

    "краснодар": "Краснодар",
    "Краснодар": "Краснодар",

    "локомотив": "Локомотив",
    "Локомотив": "Локомотив",

    "динамо": "Динамо М",
    "Динамо": "Динамо М",

    "ростов": "Ростов",

    "рубін": "Рубин",
    "Рубин": "Рубин",

    "ахмат": "Ахмат",

    "балтика": "Балтика",

    "акрон": "Акрон",

    "оренбург": "Оренбург",

    "факел": "Факел",

    "крылья": "Крылья Советов",
    "Крылья": "Крылья Советов",

    "динамо мх": "Динамо Мх",

    "родина": "Родина"

}



def get_team_by_alias(team):

    if not team:
        return None

    return TEAM_ALIASES.get(
        team.strip(),
        team.strip()
    )



# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(value, default=0):

    try:

        if value is None:
            return default

        return float(value)

    except:

        return default



# =====================================================
# FAJ RATING
# =====================================================


def calculate_faj_rating(passport):

    if not passport:
        return 0


    rating = (

        safe_float(passport.get(
            "attack",
            70
        )) * 0.25

        +

        safe_float(passport.get(
            "defense",
            70
        )) * 0.25

        +

        safe_float(passport.get(
            "control",
            70
        )) * 0.20

        +

        safe_float(passport.get(
            "efficiency",
            70
        )) * 0.15

        +

        safe_float(passport.get(
            "form_index",
            70
        )) * 0.15

    )


    return round(
        rating,
        1
    )



# =====================================================
# LOAD PASSPORT
# =====================================================


def load_passport(team):


    real_team = get_team_by_alias(
        team
    )


    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """

        SELECT *

        FROM passports

        WHERE team=%s

        LIMIT 1

        """,

        (
            real_team,
        )
    )


    row = cur.fetchone()


    conn.close()



    if not row:

        logger.warning(
            "Passport not found: %s",
            real_team
        )

        return None



    passport = dict(row)



    passport["team"] = real_team


    passport["faj_rating"] = calculate_faj_rating(
        passport
    )



    return passport



# =====================================================
# GET PASSPORT
# =====================================================


def get_passport(team):

    return load_passport(team)



# =====================================================
# CHECK
# =====================================================


def passport_exists(team):

    return load_passport(team) is not None



# =====================================================
# LIST
# =====================================================


def list_teams(
    league="RPL"
):


    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """

        SELECT team

        FROM passports

        WHERE league=%s

        ORDER BY team

        """,

        (
            league,
        )

    )


    rows = cur.fetchall()


    conn.close()


    return [
        r["team"]
        for r in rows
    ]



# =====================================================
# COMPATIBILITY
# =====================================================


def init_default_aliases():

    return TEAM_ALIASES
