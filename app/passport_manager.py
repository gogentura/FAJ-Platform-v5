# =====================================================
# FAJ Platform v7.0.2
# app/passport_manager.py
#
# PostgreSQL Passport Adapter
#
# Compatible with:
# - FAJCore
# - Prediction Pipeline
# - Learning Layer
#
# Database table:
# passports
# =====================================================


import logging

from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(value, default=0):

    try:

        if value is None:
            return default

        return float(value)

    except Exception:

        return default



# =====================================================
# TEAM ALIASES
# =====================================================


TEAM_ALIASES = {

    "Зенит": "Зенит",
    "зенит": "Зенит",

    "Спартак": "Спартак",
    "спартак": "Спартак",

    "ЦСКА": "ЦСКА",
    "цска": "ЦСКА",

    "Краснодар": "Краснодар",
    "краснодар": "Краснодар",

    "Локомотив": "Локомотив",
    "локомотив": "Локомотив",

    "Динамо": "Динамо М",
    "Динамо М": "Динамо М",

    "Ахмат": "Ахмат",

    "Рубин": "Рубин",

    "Ростов": "Ростов",

    "Балтика": "Балтика",

    "Акрон": "Акрон",

    "Оренбург": "Оренбург",

    "Факел": "Факел",

    "Крылья": "Крылья Советов",
    "Крылья Советов": "Крылья Советов",

    "Динамо Мх": "Динамо Мх",

    "Родина": "Родина"
}



# =====================================================
# ALIAS INIT
# =====================================================


def init_default_aliases():

    logger.info(
        "FAJ aliases initialized"
    )

    return TEAM_ALIASES



# =====================================================
# NORMALIZE
# =====================================================


def get_team_by_alias(team):

    if not team:

        return None


    clean = team.strip()


    return TEAM_ALIASES.get(
        clean,
        clean
    )



# =====================================================
# FAJ RATING
# =====================================================


def calculate_faj_rating(passport):

    if not passport:

        return 0.0


    rating = (

        safe_float(passport.get("attack"),70)
        *0.25

        +

        safe_float(passport.get("defense"),70)
        *0.25

        +

        safe_float(passport.get("control"),70)
        *0.20

        +

        safe_float(passport.get("form"),70)
        *0.15

        +

        safe_float(passport.get("efficiency"),70)
        *0.15

    )


    return round(
        rating,
        1
    )



# =====================================================
# NORMALIZE PASSPORT
# =====================================================


def normalize_passport(row):

    passport = dict(row)


    # Старые поля базы → FAJ Engine


    passport["form"] = safe_float(
        passport.get(
            "form_index",
            passport.get("form",70)
        ),
        70
    )


    passport["xg_for"] = safe_float(
        passport.get(
            "historical_xg_value",
            1.3
        ),
        1.3
    )


    passport["xg_against"] = safe_float(
        passport.get(
            "avg_goals_conceded_value",
            1.3
        ),
        1.3
    )


    numeric = [

        "attack",
        "defense",
        "control",
        "efficiency",
        "mentality",
        "discipline",
        "fitness",
        "predictability",
        "transfer_index",
        "injury_index",
        "fatigue_index"

    ]


    for field in numeric:

        passport[field] = safe_float(
            passport.get(field,0)
        )


    passport["faj_rating"] = calculate_faj_rating(
        passport
    )


    return passport



# =====================================================
# LOAD PASSPORT
# =====================================================


def load_passport(team):


    conn = get_db()

    cur = conn.cursor()


    real_team = get_team_by_alias(
        team
    )


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



    return normalize_passport(
        row
    )



# =====================================================
# GET ALL
# =====================================================


def load_all_passports(
    league="RPL"
):

    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT *
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

        normalize_passport(row)

        for row in rows

    ]



# =====================================================
# SAVE PASSPORT
# =====================================================


def save_passport(
    team,
    passport
):

    conn = get_db()

    cur = conn.cursor()


    real_team = get_team_by_alias(
        team
    )


    rating = calculate_faj_rating(
        passport
    )


    cur.execute(
        """
        UPDATE passports

        SET

        attack=%s,
        defense=%s,
        control=%s,
        form_index=%s,
        efficiency=%s,
        mentality=%s,
        discipline=%s,
        fitness=%s,
        predictability=%s,

        historical_xg_value=%s,

        avg_goals_conceded_value=%s,

        transfer_index=%s,

        injury_index=%s,

        fatigue_index=%s,

        updated=%s

        WHERE team=%s
        """,

        (

            passport.get("attack",70),

            passport.get("defense",70),

            passport.get("control",70),

            passport.get("form",70),

            passport.get("efficiency",70),

            passport.get("mentality",70),

            passport.get("discipline",70),

            passport.get("fitness",70),

            passport.get("predictability",70),

            passport.get("xg_for",1.3),

            passport.get("xg_against",1.3),

            passport.get("transfer_index",0),

            passport.get("injury_index",0),

            passport.get("fatigue_index",0),

            datetime.now(),

            real_team

        )

    )


    conn.commit()

    conn.close()


    logger.info(
        "Passport updated: %s rating=%s",
        real_team,
        rating
    )



# =====================================================
# COMPATIBILITY
# =====================================================


def get_passport(team):

    return load_passport(team)



def update_passport(team, passport):

    return save_passport(
        team,
        passport
    )



def passport_exists(team):

    return load_passport(team) is not None



def get_all_passports():

    return load_all_passports()



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
