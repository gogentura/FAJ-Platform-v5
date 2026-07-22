import json
from datetime import datetime
from app.database import get_db

def save_passport(team: str, passport: dict):
    conn = get_db()
    existing = conn.execute("SELECT version FROM passports WHERE team = ?", (team,)).fetchone()
    version = (existing["version"] + 1) if existing else 1

    passport["version"] = version
    passport["last_updated"] = datetime.now().isoformat()

    # Сохраняем все поля, включая вложенные структуры
    conn.execute("""
        INSERT OR REPLACE INTO passports (
            team, attack, defense, control, form_index,
            historical_xg_value, historical_xg_source,
            predicted_xg_value, predicted_xg_source,
            avg_goals_value, avg_goals_source,
            avg_goals_conceded_value, avg_goals_conceded_source,
            avg_possession_value, avg_possession_source,
            version, last_updated, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        team,
        passport["attack"],
        passport["defense"],
        passport["control"],
        passport["form_index"],
        passport["historical_xg"]["value"],
        passport["historical_xg"]["source"],
        passport["predicted_xg"]["value"],
        passport["predicted_xg"]["source"],
        passport["avg_goals"]["value"],
        passport["avg_goals"]["source"],
        passport["avg_goals_conceded"]["value"],
        passport["avg_goals_conceded"]["source"],
        passport["avg_possession"]["value"],
        passport["avg_possession"]["source"],
        version,
        passport["last_updated"],
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
