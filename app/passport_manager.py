# =====================================================
# FAJ Platform v6.3.3
# app/passport_manager.py
#
# Team Passport Manager (PostgreSQL)
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
    if passport.get("faj_rating"):
        return round(safe_float(passport.get("faj_rating")), 1)
    rating = (
        safe_float(passport.get("attack")) * 0.25 +
        safe_float(passport.get("defense")) * 0.25 +
        safe_float(passport.get("control")) * 0.20 +
        safe_float(passport.get("form")) * 0.20 +
        safe_float(passport.get("efficiency")) * 0.10
    )
    return round(rating, 1)

# =====================================================
# TEAM ALIASES (твой старый список)
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
    logger.info("FAJ aliases initialized")
    return TEAM_ALIASES

# =====================================================
# GET REAL TEAM NAME
# =====================================================
def get_team_by_alias(team):
    if not team:
        return None
    return TEAM_ALIASES.get(team.strip(), team.strip())

# =====================================================
# SAVE PASSPORT (с вычислением faj_rating)
# =====================================================
def save_passport(team, passport):
    conn = get_db()
    cur = conn.cursor()

    real_team = get_team_by_alias(team)

    # вычисляем рейтинг
    rating = calculate_faj_rating(passport)

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
        faj_rating,
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
        %s,
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
        faj_rating = EXCLUDED.faj_rating,
        updated = EXCLUDED.updated
    """

    cur.execute(
        query,
        (
            real_team,
            passport.get("league", "RPL"),
            passport.get("season", "2026/27"),
            passport.get("attack", 70),
            passport.get("defense", 70),
            passport.get("control", 70),
            passport.get("efficiency", 70),
            passport.get("mentality", 70),
            passport.get("discipline", 70),
            passport.get("fitness", 70),
            passport.get("predictability", 70),
            passport.get("xg_for", 1.3),
            passport.get("xg_against", 1.3),
            passport.get("form", 70),
            passport.get("injury_index", 0),
            passport.get("fatigue_index", 0),
            passport.get("transfer_index", 0),
            rating,
            datetime.now()
        )
    )

    conn.commit()
    conn.close()
    logger.info(f"Passport saved: {real_team}")

# =====================================================
# LOAD PASSPORT (с вычислением рейтинга)
# =====================================================
def load_passport(team):
    conn = get_db()
    cur = conn.cursor()

    real_team = get_team_by_alias(team)
    if not real_team:
        real_team = team

    cur.execute(
        """
        SELECT *
        FROM team_passports
        WHERE team = %s
        LIMIT 1
        """,
        (real_team,)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        passport = dict(row)
        # нормализуем числовые поля
        for field in ["attack", "defense", "control", "form", "efficiency",
                      "mentality", "discipline", "fitness", "predictability",
                      "transfer_index", "injury_index", "fatigue_index",
                      "xg_for", "xg_against"]:
            passport[field] = safe_float(passport.get(field, 0))
        passport["faj_rating"] = calculate_faj_rating(passport)
        return passport
    return None

# =====================================================
# LOAD ALL PASSPORTS
# =====================================================
def load_all_passports(league="RPL"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM team_passports
        WHERE league = %s
        ORDER BY team
        """,
        (league,)
    )
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        passport = dict(row)
        # нормализуем
        for field in ["attack", "defense", "control", "form", "efficiency",
                      "mentality", "discipline", "fitness", "predictability",
                      "transfer_index", "injury_index", "fatigue_index",
                      "xg_for", "xg_against"]:
            passport[field] = safe_float(passport.get(field, 0))
        passport["faj_rating"] = calculate_faj_rating(passport)
        result.append(passport)
    return result

# =====================================================
# DELETE PASSPORTS
# =====================================================
def clear_passports(league="RPL"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM team_passports
        WHERE league = %s
        """,
        (league,)
    )
    conn.commit()
    conn.close()
    logger.info(f"Passports cleared: {league}")

# =====================================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ
# =====================================================
def get_passport(team):
    return load_passport(team)

def update_passport(team, passport):
    save_passport(team, passport)

def passport_exists(team):
    return load_passport(team) is not None

def delete_passport(team):
    # удаляем конкретную команду
    conn = get_db()
    cur = conn.cursor()
    real_team = get_team_by_alias(team)
    if not real_team:
        real_team = team
    cur.execute(
        """
        DELETE FROM team_passports
        WHERE team = %s
        """,
        (real_team,)
    )
    conn.commit()
    conn.close()
    logger.info(f"Passport deleted: {real_team}")

def get_all_passports():
    return load_all_passports()

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
