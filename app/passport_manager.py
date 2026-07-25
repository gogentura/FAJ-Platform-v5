# =====================================================
# FAJ Platform v6.3
# app/passport_manager.py
#
# Team Passport Manager
# PostgreSQL version
# =====================================================

import json
import logging
from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# TEAM ALIASES
# =====================================================

ALIASES = {

    "зенит": "Зенит",
    "спартак": "Спартак",
    "цска": "ЦСКА",

    "динамо": "Динамо М",
    "динамо м": "Динамо М",

    "локомотив": "Локомотив",
    "краснодар": "Краснодар",

    "ростов": "Ростов",
    "ахмат": "Ахмат",

    "рубин": "Рубин",

    "крылья": "Крылья Советов",
    "крылья советов": "Крылья Советов",

    "факел": "Факел",
    "оренбург": "Оренбург",

    "балтика": "Балтика",

    "акрон": "Акрон",

    "динамо мх": "Динамо Мх",

    "родина": "Родина"

}


# =====================================================
# ALIAS
# =====================================================

def get_team_by_alias(name):

    if not name:
        return None

    clean = name.lower().strip()

    return ALIASES.get(
        clean,
        name
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


    now = datetime.now()


    xg_value = passport.get(
        "xg",
        {}
    )


    if isinstance(xg_value, dict):

        xg_for = (
            xg_value
            .get("historical", {})
            .get("value", 1.3)
        )

    else:

        xg_for = 1.3



    avg_goals = passport.get(
        "avg_goals",
        {}
    )


    avg_conceded = passport.get(
        "avg_goals_conceded",
        {}
    )


    possession = passport.get(
        "avg_possession",
        {}
    )



    cur.execute(
        """

        INSERT INTO team_passports
        (

            league,
            season,
            team,

            attack,
            defense,
            control,

            efficiency,
            mentality,

            form,

            xg_for,
            xg_against,

            injury_index,
            fatigue_index,
            transfer_index,

            updated

        )

        VALUES

        (

            %s,
            %s,
            %s,

            %s,
            %s,
            %s,

            %s,
            %s,

            %s,

            %s,
            %s,

            %s,
            %s,
            %s,

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

            form = EXCLUDED.form,

            xg_for = EXCLUDED.xg_for,
            xg_against = EXCLUDED.xg_against,

            injury_index = EXCLUDED.injury_index,
            fatigue_index = EXCLUDED.fatigue_index,
            transfer_index = EXCLUDED.transfer_index,

            updated = EXCLUDED.updated


        """,

        (

            passport.get(
                "league",
                "RPL"
            ),

            passport.get(
                "season",
                "2026/27"
            ),

            team,


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
                "form_index",
                70
            ),


            xg_for,


            avg_conceded.get(
                "value",
                1.3
            )
            if isinstance(
                avg_conceded,
                dict
            )
            else 1.3,


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


            now

        )

    )


    conn.commit()

    conn.close()


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



# Совместимость
def get_passport(team):

    return load_passport(team)



# =====================================================
# INIT ALIASES
# =====================================================

def init_default_aliases():

    logger.info(
        "Aliases loaded"
    )

    return True



# =====================================================
# ALL PASSPORTS
# =====================================================

def get_all_passports():

    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """

        SELECT *

        FROM team_passports

        ORDER BY team

        """
    )


    rows = cur.fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]
