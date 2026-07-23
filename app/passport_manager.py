import json
from datetime import datetime

from app.database import get_db


# =====================================================
# TEAM ALIASES
# =====================================================

ALIASES = {
    "зенит": "Зенит",
    "спартак": "Спартак",
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
    "динамо мх": "Динамо Мх",
    "родина": "Родина"
}


# =====================================================
# ALIAS FIND
# =====================================================

def get_team_by_alias(name):
    if not name:
        return None
    clean = name.lower().strip()
    return ALIASES.get(clean, name)


# =====================================================
# SAVE PASSPORT
# =====================================================

def save_passport(team, passport):
    conn = get_db()
    now = datetime.now().isoformat()

    conn.execute(
    """
    INSERT INTO passports
    (
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
    VALUES
    (
        ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
    )
    ON CONFLICT(team)
    DO UPDATE SET
        league = EXCLUDED.league,
        attack = EXCLUDED.attack,
        defense = EXCLUDED.defense,
        control = EXCLUDED.control,
        form_index = EXCLUDED.form_index,
        efficiency = EXCLUDED.efficiency,
        mentality = EXCLUDED.mentality,
        home_rating = EXCLUDED.home_rating,
        away_rating = EXCLUDED.away_rating,
        coach_factor = EXCLUDED.coach_factor,
        injury_index = EXCLUDED.injury_index,
        fatigue_index = EXCLUDED.fatigue_index,
        historical_xg_value = EXCLUDED.historical_xg_value,
        historical_xg_source = EXCLUDED.historical_xg_source,
        avg_goals_value = EXCLUDED.avg_goals_value,
        avg_goals_source = EXCLUDED.avg_goals_source,
        avg_goals_conceded_value = EXCLUDED.avg_goals_conceded_value,
        avg_goals_conceded_source = EXCLUDED.avg_goals_conceded_source,
        avg_possession_value = EXCLUDED.avg_possession_value,
        avg_possession_source = EXCLUDED.avg_possession_source,
        version = EXCLUDED.version,
        created = EXCLUDED.created,
        updated = EXCLUDED.updated,
        data = EXCLUDED.data
    """,
    (
        team,
        passport.get("league", "RPL"),
        passport.get("attack", 70),
        passport.get("defense", 70),
        passport.get("control", 70),
        passport.get("form_index", 70),
        passport.get("efficiency", 70),
        passport.get("mentality", 70),
        passport.get("home_rating", 70),
        passport.get("away_rating", 70),
        passport.get("coach_factor", 70),
        passport.get("injury_index", 0),
        passport.get("fatigue_index", 0),
        passport.get("historical_xg_value", 1.3),
        passport.get("historical_xg_source", "manual"),
        passport.get("avg_goals_value", 0),
        passport.get("avg_goals_source", "manual"),
        passport.get("avg_goals_conceded_value", 0),
        passport.get("avg_goals_conceded_source", "manual"),
        passport.get("avg_possession_value", 50),
        passport.get("avg_possession_source", "manual"),
        passport.get("version", 1),
        now,
        now,
        json.dumps(passport, ensure_ascii=False)
    )
    )

    conn.commit()
    conn.close()


# =====================================================
# LOAD PASSPORT
# =====================================================

def load_passport(team):
    real_team = get_team_by_alias(team)
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM passports WHERE team = ?",
        (real_team,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# совместимое имя
def get_passport(team):
    return load_passport(team)


# =====================================================
# ALIASES INIT
# =====================================================

def init_default_aliases():
    conn = get_db()
    for alias, team in ALIASES.items():
        try:
            conn.execute(
                """
                INSERT INTO team_aliases (team, alias)
                VALUES (?, ?)
                ON CONFLICT(alias)
                DO UPDATE SET team = EXCLUDED.team
                """,
                (team, alias)
            )
        except Exception:
            pass
    conn.commit()
    conn.close()


# =====================================================
# ALL PASSPORTS
# =====================================================

def get_all_passports():
    conn = get_db()
    rows = conn.execute("SELECT * FROM passports").fetchall()
    conn.close()
    return [dict(row) for row in rows]
