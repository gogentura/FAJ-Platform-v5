import sqlite3
from pathlib import Path

DB_PATH = Path("data/faj.db")

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Таблица паспортов (с новыми полями)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS passports (
            team TEXT PRIMARY KEY,
            league TEXT,
            attack INTEGER,
            defense INTEGER,
            control INTEGER,
            form_index INTEGER,
            efficiency INTEGER,
            mentality INTEGER,
            home_rating INTEGER,
            away_rating INTEGER,
            coach_factor INTEGER,
            injury_index INTEGER,
            fatigue_index INTEGER,
            historical_xg_value REAL,
            historical_xg_source TEXT,
            avg_goals_value REAL,
            avg_goals_source TEXT,
            avg_goals_conceded_value REAL,
            avg_goals_conceded_source TEXT,
            avg_possession_value REAL,
            avg_possession_source TEXT,
            version INTEGER DEFAULT 1,
            created TEXT,
            updated TEXT,
            data TEXT
        )
    """)
    # Добавим недостающие столбцы, если таблица уже существует (безопасно)
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(passports)").fetchall()]
    new_columns = {
        "league": "TEXT",
        "efficiency": "INTEGER",
        "mentality": "INTEGER",
        "home_rating": "INTEGER",
        "away_rating": "INTEGER",
        "coach_factor": "INTEGER",
        "injury_index": "INTEGER",
        "fatigue_index": "INTEGER"
    }
    for col, col_type in new_columns.items():
        if col not in existing_columns:
            conn.execute(f"ALTER TABLE passports ADD COLUMN {col} {col_type}")

    # Таблица статистики API
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            date TEXT PRIMARY KEY,
            used INTEGER DEFAULT 0,
            limit INTEGER DEFAULT 100
        )
    """)
    # Журнал прогнозов
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            match TEXT,
            home_team TEXT,
            away_team TEXT,
            prediction TEXT,
            winner_prob REAL,
            xg_home REAL,
            xg_away REAL,
            expected_score TEXT,
            actual_score TEXT,
            actual_winner TEXT,
            confidence INTEGER,
            model_version TEXT,
            data_version TEXT,
            accuracy TEXT
        )
    """)
    # Таблица алиасов (синонимов)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_aliases (
            team TEXT NOT NULL,
            alias TEXT PRIMARY KEY,
            FOREIGN KEY(team) REFERENCES passports(team) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
