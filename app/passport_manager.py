import json
from datetime import datetime

from app.database import get_db


# =====================================================
# ALIASES
# =====================================================

ALIASES = {

    "зенит": "Зенит",
    "зенит спб": "Зенит",

    "спартак": "Спартак",
    "спартак москва": "Спартак",

    "цска": "ЦСКА",

    "динамо": "Динамо М",

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

    "динамо махачкала": "Динамо Мх",

    "родина": "Родина"

}



# =====================================================
# SAVE PASSPORT
# =====================================================

def save_passport(team, passport):

    conn = get_db()


    now = datetime.now().isoformat()


    conn.execute(
    """
    INSERT INTO passports (

        team,

        league,


        attack,

        defense,

        control,

        form_index,


        efficiency,

        mentality,


        home_rating,

        away_rating,


        coach_factor,


        injury_index,

        fatigue_index,


        historical_xg_value,

        historical_xg_source,


        avg_goals_value,

        avg_goals_source,


        avg_goals_conceded_value,

        avg_goals_conceded_source,


        avg_possession_value,

        avg_possession_source,


        version,


        created,

        updated,


        data

    )

    VALUES (

        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?

    )


    ON CONFLICT(team)

    DO UPDATE SET


        league=excluded.league,

        attack=excluded.attack,

        defense=excluded.defense,

        control=excluded.control,

        form_index=excluded.form_index,


        efficiency=excluded.efficiency,

        mentality=excluded.mentality,


        home_rating=excluded.home_rating,

        away_rating=excluded.away_rating,


        coach_factor=excluded.coach_factor,


        injury_index=excluded.injury_index,

        fatigue_index=excluded.fatigue_index,


        historical_xg_value=excluded.historical_xg_value,

        historical_xg_source=excluded.historical_xg_source,


        avg_goals_value=excluded.avg_goals_value,

        avg_goals_source=excluded.avg_goals_source,


        avg_goals_conceded_value=excluded.avg_goals_conceded_value,

        avg_goals_conceded_source=excluded.avg_goals_conceded_source,


        avg_possession_value=excluded.avg_possession_value,

        avg_possession_source=excluded.avg_possession_source,


        version=excluded.version,

        updated=excluded.updated,


        data=excluded.data

    """,

    (

        team,


        passport.get(
            "league",
            "RPL"
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
            "form_index",
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
            "home_rating",
            70
        ),

        passport.get(
            "away_rating",
            70
        ),


        passport.get(
            "coach_factor",
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
            "historical_xg_value",
            1.3
        ),

        passport.get(
            "historical_xg_source",
            "manual"
        ),


        passport.get(
            "avg_goals_value",
            0
        ),

        passport.get(
            "avg_goals_source",
            "manual"
        ),


        passport.get(
            "avg_goals_conceded_value",
            0
        ),

        passport.get(
            "avg_goals_conceded_source",
            "manual"
        ),


        passport.get(
            "avg_possession_value",
            50
        ),

        passport.get(
            "avg_possession_source",
            "manual"
        ),


        passport.get(
            "version",
            1
        ),


        now,

        now,


        json.dumps(
            passport,
            ensure_ascii=False
        )

    )

    )


    conn.commit()

    conn.close()



# =====================================================
# LOAD PASSPORT
# =====================================================

def get_passport(team):

    team = get_team_by_alias(team)


    conn = get_db()


    row = conn.execute(
    """
    SELECT *
    FROM passports
    WHERE team = ?
    """,
    (
        team,
    )
    ).fetchone()


    conn.close()


    if row:

        return dict(row)


    return None




# =====================================================
# ALIAS SEARCH
# =====================================================

def get_team_by_alias(name):

    if not name:
        return None


    clean = name.lower().strip()


    if clean in ALIASES:

        return ALIASES[clean]


    return name



# =====================================================
# LOAD ALL
# =====================================================

def get_all_passports():

    conn = get_db()


    rows = conn.execute(
    """
    SELECT *
    FROM passports
    """
    ).fetchall()


    conn.close()


    return [
        dict(row)
        for row in rows
    ]
# =====================================================
# DEFAULT ALIASES INIT
# =====================================================

def init_default_aliases():

    conn = get_db()


    for alias, team in ALIASES.items():

        try:

            conn.execute(
            """
            INSERT INTO team_aliases
            (
                team,
                alias
            )

            VALUES
            (
                ?,
                ?
            )

            ON CONFLICT(alias)

            DO UPDATE SET

                team=excluded.team

            """,
            (
                team,
                alias
            )
            )


        except Exception:

            pass



    conn.commit()

    conn.close()
