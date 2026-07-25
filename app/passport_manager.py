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
# ALIAS SEARCH
# =====================================================

def get_team_by_alias(name):

    if not name:
        return None

    clean = str(name).lower().strip()

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

    now = datetime.now()


    data_json = json.dumps(
        passport,
        ensure_ascii=False
    )


    cur = conn.cursor()


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

            form_index,

            efficiency,
            mentality,

            discipline,
            fitness,
            predictability,

            historical_xg_value,
            historical_xg_source,

            avg_goals_value,
            avg_goals_source,

            avg_goals_conceded_value,
            avg_goals_conceded_source,

            avg_possession_value,
            avg_possession_source,

            transfer_index,
            injury_index,
            fatigue_index,

            version,

            created,
            updated,

            data
        )

        VALUES

        (
            %s,%s,%s,

            %s,%s,%s,

            %s,

            %s,%s,

            %s,%s,%s,

            %s,%s,

            %s,%s,

            %s,%s,

            %s,%s,

            %s,%s,%s,

            %s,

            %s,%s,

            %s
        )


        ON CONFLICT(team)

        DO UPDATE SET


            league = EXCLUDED.league,
            season = EXCLUDED.season,


            attack = EXCLUDED.attack,
            defense = EXCLUDED.defense,
            control = EXCLUDED.control,


            form_index = EXCLUDED.form_index,


            efficiency = EXCLUDED.efficiency,
            mentality = EXCLUDED.mentality,


            discipline = EXCLUDED.discipline,
            fitness = EXCLUDED.fitness,
            predictability = EXCLUDED.predictability,


            historical_xg_value =
                EXCLUDED.historical_xg_value,

            historical_xg_source =
                EXCLUDED.historical_xg_source,


            avg_goals_value =
                EXCLUDED.avg_goals_value,

            avg_goals_conceded_value =
                EXCLUDED.avg_goals_conceded_value,


            avg_possession_value =
                EXCLUDED.avg_possession_value,


            transfer_index =
                EXCLUDED.transfer_index,

            injury_index =
                EXCLUDED.injury_index,

            fatigue_index =
                EXCLUDED.fatigue_index,


            version =
                EXCLUDED.version,


            updated =
                EXCLUDED.updated,


            data =
                EXCLUDED.data

        """,

        (

            team,

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
                "form",
                passport.get(
                    "form_index",
                    70
                )
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

            "expert",


            passport.get(
                "avg_goals",
                0
            ),

            "expert",


            passport.get(
                "avg_goals_conceded",
                0
            ),

            "expert",


            passport.get(
                "avg_possession",
                50
            ),

            "expert",


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


            1,


            now,

            now,


            data_json

        )

    )


    conn.commit()

    conn.close()


    logger.info(
        f"Passport saved: {team}"
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


    if row:

        return dict(row)


    return None



# =====================================================
# COMPATIBILITY
# =====================================================

def get_passport(team):

    return load_passport(team)



# =====================================================
# INIT ALIASES
# =====================================================

def init_default_aliases():

    conn = get_db()

    cur = conn.cursor()


    for alias, team in ALIASES.items():

        try:

            cur.execute(
                """
                INSERT INTO team_aliases
                (
                    team,
                    alias
                )

                VALUES
                (
                    %s,
                    %s
                )

                ON CONFLICT(alias)

                DO UPDATE SET

                    team =
                    EXCLUDED.team

                """,

                (
                    team,
                    alias
                )

            )

        except Exception as e:

            logger.warning(
                f"Alias skipped {alias}: {e}"
            )


    conn.commit()

    conn.close()



# =====================================================
# ALL PASSPORTS
# =====================================================

def get_all_passports():

    conn = get_db()

    cur = conn.cursor()


    cur.execute(
        """
        SELECT *

        FROM passports

        ORDER BY team
        """
    )


    rows = cur.fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]
