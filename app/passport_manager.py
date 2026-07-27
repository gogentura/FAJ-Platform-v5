# =====================================================
# FAJ Platform v7.0
# app/passport_manager.py
#
# Team Passport Manager
#
# PostgreSQL ONLY
#
# Single format for:
# - FAJCore
# - Prediction Pipeline
# - Learning Layer
# =====================================================


import logging

from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)





# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(
    value,
    default=0
):

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


    "Зенит":
        "Зенит",


    "зенит":
        "Зенит",


    "Спартак":
        "Спартак",


    "спартак":
        "Спартак",


    "ЦСКА":
        "ЦСКА",


    "цска":
        "ЦСКА",


    "Краснодар":
        "Краснодар",


    "краснодар":
        "Краснодар",


    "Локомотив":
        "Локомотив",


    "локомотив":
        "Локомотив",


    "Динамо":
        "Динамо М",


    "Динамо М":
        "Динамо М",


    "Ахмат":
        "Ахмат",


    "Рубин":
        "Рубин",


    "Ростов":
        "Ростов",


    "Балтика":
        "Балтика",


    "Акрон":
        "Акрон",


    "Оренбург":
        "Оренбург",


    "Факел":
        "Факел",


    "Крылья":
        "Крылья Советов",


    "Крылья Советов":
        "Крылья Советов",


    "Динамо Мх":
        "Динамо Мх",


    "Родина":
        "Родина"

}





# =====================================================
# NORMALIZE TEAM
# =====================================================


def get_team_by_alias(
    team
):

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


def calculate_faj_rating(
    passport
):


    if not passport:

        return 0.0



    rating = (

        safe_float(
            passport.get(
                "attack",
                70
            )
        )
        *
        0.25


        +

        safe_float(
            passport.get(
                "defense",
                70
            )
        )
        *
        0.25


        +

        safe_float(
            passport.get(
                "control",
                70
            )
        )
        *
        0.20


        +

        safe_float(
            passport.get(
                "form",
                70
            )
        )
        *
        0.15


        +

        safe_float(
            passport.get(
                "efficiency",
                70
            )
        )
        *
        0.15

    )


    return round(
        rating,
        1
    )





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


    passport["team"] = real_team



    rating = calculate_faj_rating(
        passport
    )



    cur.execute(
    """

    INSERT INTO team_passports

    (

        team,

        league,

        season,


        attack,

        defense,

        control,

        efficiency,


        form,

        mentality,

        discipline,

        fitness,

        predictability,


        xg_for,

        xg_against,


        transfer_index,

        injury_index,

        fatigue_index,


        faj_rating,

        updated

    )


    VALUES

    (

        %s,%s,%s,

        %s,%s,%s,%s,

        %s,%s,%s,%s,%s,

        %s,%s,

        %s,%s,%s,

        %s,

        %s

    )


    ON CONFLICT
    (
        team,
        league,
        season
    )

    DO UPDATE SET


        attack = EXCLUDED.attack,

        defense = EXCLUDED.defense,

        control = EXCLUDED.control,

        efficiency = EXCLUDED.efficiency,


        form = EXCLUDED.form,

        mentality = EXCLUDED.mentality,

        discipline = EXCLUDED.discipline,

        fitness = EXCLUDED.fitness,

        predictability = EXCLUDED.predictability,


        xg_for = EXCLUDED.xg_for,

        xg_against = EXCLUDED.xg_against,


        transfer_index = EXCLUDED.transfer_index,

        injury_index = EXCLUDED.injury_index,

        fatigue_index = EXCLUDED.fatigue_index,


        faj_rating = EXCLUDED.faj_rating,


        updated = EXCLUDED.updated

    """,

    (

        real_team,


        passport.get(
            "league",
            "RPL"
        ),


        passport.get(
            "season",
            "2026/27"
        ),


        passport.get(
            "attack",
            70
        ),


        passport.get(
            "defense",
            70
        ),


        passport.get(
            "control",
            70
        ),


        passport.get(
            "efficiency",
            70
        ),


        passport.get(
            "form",
            70
        ),


        passport.get(
            "mentality",
            70
        ),


        passport.get(
            "discipline",
            70
        ),


        passport.get(
            "fitness",
            70
        ),


        passport.get(
            "predictability",
            70
        ),


        passport.get(
            "xg_for",
            1.3
        ),


        passport.get(
            "xg_against",
            1.3
        ),


        passport.get(
            "transfer_index",
            0
        ),


        passport.get(
            "injury_index",
            0
        ),


        passport.get(
            "fatigue_index",
            0
        ),


        rating,


        datetime.now()

    )


    conn.commit()

    conn.close()


    logger.info(
        "Passport saved: %s",
        real_team
    )





# =====================================================
# LOAD PASSPORT
# =====================================================


def load_passport(
    team
):


    conn = get_db()

    cur = conn.cursor()



    real_team = get_team_by_alias(
        team
    )



    cur.execute(
    """

    SELECT *

    FROM team_passports

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
            "PASSPORT NOT FOUND: %s",
            real_team
        )

        return None




    passport = dict(row)



    numeric_fields = [

        "attack",

        "defense",

        "control",

        "efficiency",

        "form",

        "mentality",

        "discipline",

        "fitness",

        "predictability",

        "xg_for",

        "xg_against",

        "transfer_index",

        "injury_index",

        "fatigue_index"

    ]



    for field in numeric_fields:


        passport[field] = safe_float(
            passport.get(field)
        )



    passport["faj_rating"] = calculate_faj_rating(
        passport
    )


    return passport





# =====================================================
# LOAD ALL
# =====================================================


def load_all_passports(
    league="RPL"
):


    conn = get_db()

    cur = conn.cursor()


    cur.execute(
    """

    SELECT *

    FROM team_passports

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

        dict(row)

        for row in rows

    ]





# =====================================================
# CHECK
# =====================================================


def passport_exists(
    team
):

    return load_passport(
        team
    ) is not None





def get_passport(
    team
):

    return load_passport(
        team
    )





def update_passport(
    team,
    passport
):

    return save_passport(
        team,
        passport
    )





def list_teams(
    league="RPL"
):


    conn = get_db()

    cur = conn.cursor()


    cur.execute(
    """

    SELECT team

    FROM team_passports

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
