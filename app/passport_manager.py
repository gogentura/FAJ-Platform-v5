import json
from datetime import datetime
from app.database import get_db

def save_passport(team: str, passport: dict):
    conn = get_db()
    existing = conn.execute("SELECT version FROM passports WHERE team = ?", (team,)).fetchone()
    version = (existing["version"] + 1) if existing else 1
    conn.execute("""
        INSERT OR REPLACE INTO passports (
            team, attack, defense, control, form_index,
            avg_goals, avg_goals_conceded, avg_possession, avg_xg,
            version, last_updated, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        team,
        passport["attack"],
        passport["defense"],
        passport["control"],
        passport["form_index"],
        passport["avg_goals"],
        passport["avg_goals_conceded"],
        passport["avg_possession"],
        passport["avg_xg"],
        version,
        datetime.now().isoformat(),
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

def list_passports():
    conn = get_db()
    rows = conn.execute("SELECT team FROM passports").fetchall()
    conn.close()
    return [r["team"] for r in rows]

def is_updated_today(team: str) -> bool:
    conn = get_db()
    row = conn.execute("SELECT last_updated FROM passports WHERE team = ?", (team,)).fetchone()
    conn.close()
    if not row:
        return False
    return row["last_updated"].startswith(datetime.now().strftime("%Y-%m-%d"))
