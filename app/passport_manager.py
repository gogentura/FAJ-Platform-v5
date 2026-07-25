# =====================================================
# FAJ Platform v6.3
# Passport Manager
# PostgreSQL Edition
# =====================================================
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
    "динамо москва": "Динамо М",
    "динамо м": "Динамо М",
    "локомотив": "Локомотив",
    "локомотив москва": "Локомотив",
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
    "динамо мх": "Динамо Мх",
    "родина": "Родина"
}

# =====================================================
# NORMALIZE TEAM
# =====================================================
def get_team_by_alias(name):
    if not name:
        return None
    clean = name.lower().strip()
    return ALIASES.get(clean, name)

# =====================================================
# LOAD PASSPORT
# =====================================================
def load_passport(team):
    team = get_team_by_alias(team)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM team_passports
        WHERE team = %s
        LIMIT 1
        """,
        (team,)
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
# SAVE PASSPORT
# =====================================================
def save_passport(team, passport):
    team = get_team_by_alias(team)
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now()

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

            %s,%s,%s,%s,%s,%s,%s,%s,

            %s,%s,

            %s,

            %s,%s,%s,

            %s
        )
        ON CONFLICT (league, season, team)
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
        """,
        (
            passport.get("league", "RPL"),
            passport.get("season", "2026/27"),
            team,

            passport.get("attack", 70),
            passport.get("defense", 70),
            passport.get("control", 70),
            passport.get("efficiency", 70),
            passport.get("mentality", 70),
            passport.get("discipline", 70),
            passport.get("fitness", 70),
            passport.get("predictability", 70),

            passport.get("xg_for", 1.30),
            passport.get("xg_against", 1.30),

            passport.get("form", 70),

            passport.get("injury_index", 0),
            passport.get("fatigue_index", 0),
            passport.get("transfer_index", 0),

            now
        )
    )

    conn.commit()
    conn.close()

# =====================================================
# UPDATE PASSPORT
# =====================================================
def update_passport(team, passport):
    save_passport(team, passport)

# =====================================================
# EXISTS
# =====================================================
def passport_exists(team):
    team = get_team_by_alias(team)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id
        FROM team_passports
        WHERE team = %s
        LIMIT 1
        """,
        (team,)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None

# =====================================================
# DELETE PASSPORT
# =====================================================
def delete_passport(team):
    team = get_team_by_alias(team)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE
        FROM team_passports
        WHERE team = %s
        """,
        (team,)
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
        FROM team_passports
        ORDER BY league, team
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(x) for x in rows]

# =====================================================
# LIST TEAMS
# =====================================================
def list_teams(league=None):
    conn = get_db()
    cur = conn.cursor()
    if league:
        cur.execute(
            """
            SELECT team
            FROM team_passports
            WHERE league = %s
            ORDER BY team
            """,
            (league,)
        )
    else:
        cur.execute(
            """
            SELECT team
            FROM team_passports
            ORDER BY team
            """
        )
    rows = cur.fetchall()
    conn.close()
    return [r["team"] for r in rows]

# =====================================================
# DEFAULT ALIASES
# =====================================================
def init_default_aliases():
    logger.info("FAJ aliases loaded")
    return True

# =====================================================
# EXPORT
# =====================================================
__all__ = [
    "ALIASES",
    "get_team_by_alias",
    "load_passport",
    "get_passport",
    "save_passport",
    "update_passport",
    "delete_passport",
    "passport_exists",
    "get_all_passports",
    "list_teams",
    "init_default_aliases"
]
