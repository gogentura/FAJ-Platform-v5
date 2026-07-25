# =====================================================
# FAJ Platform v6.3.3
# app/passport_manager.py
#
# Team Passport Manager
# =====================================================


import logging


from app.database import get_connection


logger = logging.getLogger(__name__)



# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(value, default=0):

    try:

        if value is None:

            return default


        if isinstance(value, dict):

            return default


        return float(value)


    except Exception:

        return default



# =====================================================
# FAJ RATING CALCULATOR
# =====================================================


def calculate_faj_rating(passport):


    if not passport:

        return 0.0



    # если уже есть рейтинг
    if passport.get("faj_rating"):

        return round(

            safe_float(
                passport.get("faj_rating")
            ),

            1

        )



    rating = (

        safe_float(
            passport.get(
                "attack"
            )
        )

        * 0.25


        +

        safe_float(
            passport.get(
                "defense"
            )
        )

        * 0.25


        +

        safe_float(
            passport.get(
                "control"
            )
        )

        * 0.20


        +

        safe_float(
            passport.get(
                "form"
            )
        )

        * 0.20


        +

        safe_float(
            passport.get(
                "efficiency"
            )
        )

        * 0.10

    )


    return round(
        rating,
        1
    )



# =====================================================
# TEAM ALIASES
# =====================================================


TEAM_ALIASES = {


    "зенит":
        "Зенит",


    "зенит спб":
        "Зенит",


    "акрон":
        "Акрон",


    "динамо":
        "Динамо",


    "динамо москва":
        "Динамо",


    "крылья":
        "Крылья Советов",


    "крылья советов":
        "Крылья Советов",


    "спартак":
        "Спартак",


    "цска":
        "ЦСКА",


    "локомотив":
        "Локомотив",


    "краснодар":
        "Краснодар",


    "ростов":
        "Ростов",


    "рубина":
        "Рубин",


    "рубин":
        "Рубин"

}



# =====================================================
# GET TEAM BY ALIAS
# =====================================================


def get_team_by_alias(name):


    if not name:

        return None



    key = (

        name
        .lower()
        .strip()

    )



    return TEAM_ALIASES.get(
        key
    )



# =====================================================
# LOAD PASSPORT
# =====================================================


def load_passport(team):


    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """
            SELECT *
            FROM passports
            WHERE LOWER(team)=LOWER(%s)
            LIMIT 1
            """,

            (
                team,
            )

        )



        row = cur.fetchone()


        conn.close()



        if not row:


            logger.warning(

                "Passport not found: %s",

                team

            )


            return {}



        columns = [

            desc[0]

            for desc in cur.description

        ]



        passport = dict(

            zip(

                columns,

                row

            )

        )



        # =============================================
        # NORMALIZE
        # =============================================


        numeric_fields = [

            "attack",

            "defense",

            "control",

            "form",

            "efficiency",

            "mentality",

            "discipline",

            "fitness",

            "predictability",

            "transfer_index",

            "injury_index",

            "fatigue_index",

            "xg_for",

            "xg_against"

        ]



        for field in numeric_fields:


            passport[field] = safe_float(

                passport.get(
                    field,
                    0
                )

            )



        # =============================================
        # FAJ RATING
        # =============================================


        passport["faj_rating"] = calculate_faj_rating(

            passport

        )



        return passport



    except Exception as e:


        logger.error(

            "Passport load error: %s",

            e,

            exc_info=True

        )


        return {}



# =====================================================
# LOAD ALL PASSPORTS
# =====================================================


def load_all_passports():


    passports = []



    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """
            SELECT *
            FROM passports
            """

        )


        rows = cur.fetchall()



        columns = [

            desc[0]

            for desc in cur.description

        ]



        for row in rows:


            passport = dict(

                zip(

                    columns,

                    row

                )

            )


            passport["faj_rating"] = calculate_faj_rating(

                passport

            )


            passports.append(

                passport

            )



        conn.close()



    except Exception as e:


        logger.error(

            "Load all passports error: %s",

            e,

            exc_info=True

        )



    return passports
