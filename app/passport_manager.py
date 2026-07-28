# =====================================================
# FAJ Platform v7.0.3
# app/passport_manager.py
#
# PostgreSQL Passport Manager
#
# Compatible:
# - FAJCore
# - passport.py
# - load_passports.py
# - PostgreSQL passports table
# =====================================================


import logging

from app.database import get_db


logger = logging.getLogger(__name__)



MODEL_VERSION = "FAJ v7.0.3"



# =====================================================
# TEAM ALIASES
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
    "Динамо М": "Динамо М",

    "ростов": "Ростов",
    "Ростов": "Ростов",

    "рубин": "Рубин",
    "Рубин": "Рубин",

    "ахмат": "Ахмат",
    "Ахмат": "Ахмат",

    "балтика": "Балтика",
    "Балтика": "Балтика",

    "акрон": "Акрон",
    "Акрон": "Акрон",

    "оренбург": "Оренбург",
    "Оренбург": "Оренбург",

    "факел": "Факел",
    "Факел": "Факел",

    "крылья": "Крылья Советов",
    "Крылья Советов": "Крылья Советов",

    "динамо мх": "Динамо Мх",
    "Динамо Мх": "Динамо Мх",

    "родина": "Родина",
    "Родина": "Родина"

}



# =====================================================
# NORMALIZE TEAM
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

    except:

        return default



# =====================================================
# FAJ RATING
# =====================================================


def calculate_faj_rating(
        passport
):

    if not passport:

        return 0



    rating = (

        safe_float(
            passport.get(
                "attack",
                70
            )
        ) * 0.25


        +

        safe_float(
            passport.get(
                "defense",
                70
            )
        ) * 0.25


        +

        safe_float(
            passport.get(
                "control",
                70
            )
        ) * 0.20


        +

        safe_float(
            passport.get(
                "efficiency",
                70
            )
        ) * 0.15


        +

        safe_float(
            passport.get(
                "form_index",
                passport.get(
                    "form",
                    70
                )
            )
        ) * 0.15

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

        INSERT INTO passports
        (

            team,
            league,
            season,

            attack,
            defense,
            control,

            efficiency,

            mentality,
            discipline,
            fitness,
            predictability,

            injury_index,
            fatigue_index,
            transfer_index,

            historical_xg_value,

            home_rating,
            away_rating,

            version,

            updated

        )

        VALUES

        (

            %s,%s,%s,

            %s,%s,%s,

            %s,

            %s,%s,%s,%s,

            %s,%s,%s,

            %s,

            %s,%s,

            %s,

            NOW()

        )


        ON CONFLICT (team)

        DO UPDATE SET


            attack = EXCLUDED.attack,

            defense = EXCLUDED.defense,

            control = EXCLUDED.control,

            efficiency = EXCLUDED.efficiency,

            mentality = EXCLUDED.mentality,

            discipline = EXCLUDED.discipline,

            fitness = EXCLUDED.fitness,

            predictability = EXCLUDED.predictability,

            injury_index = EXCLUDED.injury_index,

            fatigue_index = EXCLUDED.fatigue_index,

            transfer_index = EXCLUDED.transfer_index,

            historical_xg_value =
                EXCLUDED.historical_xg_value,

            home_rating =
                EXCLUDED.home_rating,

            away_rating =
                EXCLUDED.away_rating,

            version =
                EXCLUDED.version,

            updated =
                NOW()

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
                "injury_index",
                0
            ),

            passport.get(
                "fatigue_index",
                0
            ),

            passport.get(
                "transfer_index",
                0
            ),


            passport.get(
                "historical_xg_value",
                1.3
            ),


            rating,

            rating,


            MODEL_VERSION

        )

    )


    conn.commit()

    cur.close()

    conn.close()



    logger.info(
        "Passport saved: %s",
        real_team
    )



# =====================================================
# LOAD ONE
# =====================================================


def load_passport(
        team
):


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

        return None



    passport = dict(row)



    # FIX VERSION

    if (

        not passport.get("version")

        or str(
            passport.get("version")
        ).isdigit()

    ):

        passport["version"] = MODEL_VERSION



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

        dict(row)

        for row in rows

    ]



# =====================================================
# COMPATIBILITY
# =====================================================


def get_passport(team):

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



def passport_exists(
        team
):

    return load_passport(
        team
    ) is not None



def list_teams(
        league="RPL"
):

    passports = load_all_passports(
        league
    )


    return [

        p["team"]

        for p in passports

    ]



# =====================================================
# BOT COMPATIBILITY
# =====================================================


def init_default_aliases():

    return TEAM_ALIASES
