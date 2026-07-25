# =====================================================
# FAJ Platform v6.3
# app/passport_manager.py
#
# Team Passport Manager
# PostgreSQL version
# =====================================================


import logging
from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# DEFAULT ALIASES
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
# GET REAL TEAM NAME
# =====================================================

def get_team_by_alias(team):

    if not team:
        return None


    return TEAM_ALIASES.get(

        team.strip(),

        team.strip()

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


    real_team = get_team_by_alias(team)



    query = """

    INSERT INTO team_passports
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


        xg_for,

        xg_against,


        form,


        injury_index,

        fatigue_index,

        transfer_index,


        updated

    )


    VALUES

    (

        %s,%s,%s,

        %s,%s,%s,

        %s,%s,%s,%s,%s,

        %s,%s,

        %s,

        %s,%s,%s,

        %s

    )


    ON CONFLICT

    (

        league,

        season,

        team

    )


    DO UPDATE SET


        attack = EXCLUDED.attack,

        defense = EXCLUDED.defense,

        control = EXCLUDED.control,


        efficiency = EXCLUDED.efficiency,

        mentality = EXCLUDED.mentality,

        discipline = EXCLUDED.discipline,

        fitness = EXCLUDED.fitness,

        predictability = EXCLUDED.predictability,


        xg_for = EXCLUDED.xg_for,

        xg_against = EXCLUDED.xg_against,


        form = EXCLUDED.form,


        injury_index = EXCLUDED.injury_index,

        fatigue_index = EXCLUDED.fatigue_index,

        transfer_index = EXCLUDED.transfer_index,


        updated = EXCLUDED.updated

    """



    cur.execute(

        query,

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
                "xg_for",
                1.3
            ),


            passport.get(
                "xg_against",
                1.3
            ),



            passport.get(
                "form",
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



            datetime.now()

        )

    )


    conn.commit()

    conn.close()


    logger.info(

        f"Passport saved: {real_team}"

    )



# =====================================================
# LOAD PASSPORT
# =====================================================

def load_passport(team):

    conn = get_db()

    cur = conn.cursor()



    real_team = get_team_by_alias(team)



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



    if row:

        return dict(row)


    return None



# =====================================================
# LOAD ALL PASSPORTS
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
# DELETE PASSPORTS
# =====================================================

def clear_passports(
    league="RPL"
):

    conn = get_db()

    cur = conn.cursor()


    cur.execute(

        """

        DELETE FROM team_passports

        WHERE league=%s

        """,

        (

            league,

        )

    )


    conn.commit()

    conn.close()


    logger.info(

        f"Passports cleared: {league}"

    )
