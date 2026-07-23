import sqlite3
from pathlib import Path
from datetime import datetime


# ==========================
# ПУТЬ К БАЗЕ
# ==========================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(
    exist_ok=True
)


DB_PATH = DATA_DIR / "faj.db"



# ==========================
# ПОДКЛЮЧЕНИЕ
# ==========================

def get_db():

    conn = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn



# ==========================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ==========================

def init_db():

    conn = get_db()



    # ----------------------
    # ПАСПОРТА
    # ----------------------

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



    # ----------------------
    # ЖУРНАЛ ПРОГНОЗОВ
    # ----------------------

    conn.execute("""
    CREATE TABLE IF NOT EXISTS journal (

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        date TEXT,


        match TEXT,


        home_team TEXT,
        away_team TEXT,


        prediction TEXT,


        winner TEXT,

        winner_probability REAL,


        xg_home REAL,
        xg_away REAL,


        expected_score TEXT,


        actual_score TEXT,


        accuracy TEXT

    )
    """)



    # ----------------------
    # API FOOTBALL
    # ----------------------

    conn.execute("""
    CREATE TABLE IF NOT EXISTS api_usage (

        date TEXT PRIMARY KEY,


        used INTEGER DEFAULT 0,


        daily_limit INTEGER DEFAULT 100

    )
    """)



    # ----------------------
    # АЛИАСЫ КОМАНД
    # ----------------------

    conn.execute("""
    CREATE TABLE IF NOT EXISTS team_aliases (

        team TEXT NOT NULL,


        alias TEXT PRIMARY KEY

    )
    """)



    # ----------------------
    # МАТЧИ / КАЛЕНДАРЬ
    # ----------------------

    conn.execute("""
    CREATE TABLE IF NOT EXISTS matches (

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        league TEXT,


        round TEXT,


        date TEXT,


        home_team TEXT,


        away_team TEXT,


        status TEXT DEFAULT 'scheduled',


        prediction TEXT,


        actual_score TEXT

    )
    """)



    conn.commit()

    conn.close()



# ==========================
# ПРОВЕРКА СТАТУСА
# ==========================

def get_database_stats():

    conn = get_db()


    passports = conn.execute(
        "SELECT COUNT(*) FROM passports"
    ).fetchone()[0]


    predictions = conn.execute(
        "SELECT COUNT(*) FROM journal"
    ).fetchone()[0]


    matches = conn.execute(
        "SELECT COUNT(*) FROM matches"
    ).fetchone()[0]


    conn.close()


    return {

        "passports": passports,

        "predictions": predictions,

        "matches": matches

    }
