import json
from datetime import datetime, timedelta
from app.database import get_db

# --- Основные функции паспортов ---

def save_passport(team: str, passport: dict):
    conn = get_db()
    existing = conn.execute("SELECT version, created FROM passports WHERE team = ?", (team,)).fetchone()
    version = (existing["version"] + 1) if existing else 1
    created = existing["created"] if existing else datetime.now().isoformat()
    updated = datetime.now().isoformat()

    # Извлекаем данные с защитой от отсутствия ключей
    hist_xg = passport.get("xg", {}).get("historical", {}).get("value")
    avg_goals = passport.get("avg_goals", {}).get("value", 0.0)
    avg_goals_conceded = passport.get("avg_goals_conceded", {}).get("value", 0.0)
    avg_possession = passport.get("avg_possession", {}).get("value", 50)

    # Вычисляем основные рейтинги (если не заданы явно)
    attack = passport.get("attack")
    if attack is None:
        attack = 70 + avg_goals * 7 + (hist_xg * 6 if hist_xg else 0)
    defense = passport.get("defense")
    if defense is None:
        defense = 70 - avg_goals_conceded * 8
    control = passport.get("control")
    if control is None:
        control = 70 + (avg_possession - 50) * 0.4
    form_index = passport.get("form_index")
    if form_index is None:
        form_index = 70 + (avg_goals - 1.2) * 20

    attack = min(100, max(0, int(attack)))
    defense = min(100, max(0, int(defense)))
    control = min(100, max(0, int(control)))
    form_index = min(100, max(0, int(form_index)))

    efficiency = passport.get("efficiency", 50)
    mentality = passport.get("mentality", 50)
    home_rating = passport.get("home_rating", 50)
    away_rating = passport.get("away_rating", 50)
    coach_factor = passport.get("coach_factor", 0)
    injury_index = passport.get("injury_index", 0)
    fatigue_index = passport.get("fatigue_index", 0)
    league = passport.get("league", "RPL")

    conn.execute("""
        INSERT OR REPLACE INTO passports (
            team, league, attack, defense, control, form_index,
            efficiency, mentality, home_rating, away_rating,
            coach_factor, injury_index, fatigue_index,
            historical_xg_value, historical_xg_source,
            avg_goals_value, avg_goals_source,
            avg_goals_conceded_value, avg_goals_conceded_source,
            avg_possession_value, avg_possession_source,
            version, created, updated, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
        passport.get("xg", {}).get("historical", {}).get("value"),
        passport.get("xg", {}).get("historical", {}).get("source"),
        passport.get("avg_goals", {}).get("value"),
        passport.get("avg_goals", {}).get("source"),
        passport.get("avg_goals_conceded", {}).get("value"),
        passport.get("avg_goals_conceded", {}).get("source"),
        passport.get("avg_possession", {}).get("value"),
        passport.get("avg_possession", {}).get("source"),
        version,
        created,
        updated,
        json.dumps(passport)
    ))
    conn.commit()
    conn.close()
    return version

def load_passport(team: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM passports WHERE team = ?", (team,)).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

def is_passport_fresh(team: str, days: int = 7) -> bool:
    passport = load_passport(team)
    if not passport:
        return False
    updated = datetime.fromisoformat(passport["updated"])
    return (datetime.now() - updated) < timedelta(days=days)

def is_updated_today(team: str) -> bool:
    passport = load_passport(team)
    if not passport:
        return False
    updated = datetime.fromisoformat(passport["updated"])
    return updated.strftime("%Y-%m-%d") == datetime.now().strftime("%Y-%m-%d")

# --- Функции для работы с алиасами ---

def save_alias(team: str, alias: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO team_aliases (team, alias) VALUES (?, ?)", (team, alias))
    conn.commit()
    conn.close()

def get_team_by_alias(alias: str) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT team FROM team_aliases WHERE alias = ?", (alias,)).fetchone()
    conn.close()
    if row:
        return row["team"]
    if load_passport(alias):
        return alias
    return None

def get_all_aliases(team: str) -> list:
    conn = get_db()
    rows = conn.execute("SELECT alias FROM team_aliases WHERE team = ?", (team,)).fetchall()
    conn.close()
    return [row["alias"] for row in rows]

def init_default_aliases():
    default_aliases = {
        "Зенит": ["Зенит", "Zenit", "Зенит СПб"],
        "Спартак": ["Спартак", "Spartak", "Спартак М"],
        "ЦСКА": ["ЦСКА", "CSKA", "ПФК ЦСКА"],
        "Динамо М": ["Динамо М", "Dinamo", "Динамо Москва"],
        "Локомотив": ["Локомотив", "Lokomotiv", "Локомотив М"],
        "Краснодар": ["Краснодар", "Krasnodar"],
        "Ростов": ["Ростов", "Rostov"],
        "Ахмат": ["Ахмат", "Akhmat", "Терек"],
        "Рубин": ["Рубин", "Rubin"],
        "Крылья Советов": ["Крылья Советов", "Крылья", "KS Samara"],
        "Факел": ["Факел", "Fakel"],
        "Оренбург": ["Оренбург", "Orenburg"],
        "Балтика": ["Балтика", "Baltika"],
        "Акрон": ["Акрон", "Akron"],
        "Динамо Мх": ["Динамо Мх", "Динамо Махачкала"],
        "Родина": ["Родина", "Rodina"]
    }
    for team, aliases in default_aliases.items():
        for alias in aliases:
            save_alias(team, alias)
