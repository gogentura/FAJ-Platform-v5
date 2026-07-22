import json
from datetime import datetime
from app.database import get_db

def save_passport(team: str, passport: dict):
    conn = get_db()
    existing = conn.execute("SELECT version, created FROM passports WHERE team = ?", (team,)).fetchone()
    version = (existing["version"] + 1) if existing else 1
    created = existing["created"] if existing else datetime.now().isoformat()
    updated = datetime.now().isoformat()

    passport["version"] = version
    passport["created"] = created
    passport["updated"] = updated

    # Используем historical_xg для расчёта атаки (если есть)
    hist_xg_value = passport["xg"]["historical"]["value"]
    if hist_xg_value:
        attack_base = 70 + passport["avg_goals"]["value"] * 7 + hist_xg_value * 6
    else:
        attack_base = 70 + passport["avg_goals"]["value"] * 10
    passport["attack"] = min(100, attack_base)

    # Защита, контроль, форма — как раньше
    defense = 70 - passport["avg_goals_conceded"]["value"] * 8
    control = 70 + (passport["avg_possession"]["value"] - 50) * 0.4
    form = 70 + (passport["avg_goals"]["value"] - 1.2) * 20

    passport["defense"] = min(100, defense)
    passport["control"] = min(100, control)
    passport["form_index"] = min(100, form)

    # Сохраняем в БД
    conn.execute("""
        INSERT OR REPLACE INTO passports (
            team, attack, defense, control, form_index,
            historical_xg_value, historical_xg_source,
            avg_goals_value, avg_goals_source,
            avg_goals_conceded_value, avg_goals_conceded_source,
            avg_possession_value, avg_possession_source,
            version, created, updated, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        team,
        passport["attack"],
        passport["defense"],
        passport["control"],
        passport["form_index"],
        passport["xg"]["historical"]["value"],
        passport["xg"]["historical"]["source"],
        passport["goals"]["scored"]["value"],
        passport["goals"]["scored"]["source"],
        passport["goals"]["conceded"]["value"],
        passport["goals"]["conceded"]["source"],
        passport["possession"]["value"],
        passport["possession"]["source"],
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
