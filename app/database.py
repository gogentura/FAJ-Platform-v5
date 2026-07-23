import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(
    exist_ok=True
)


DB_PATH = DATA_DIR / "faj.db"


def get_db():

    logger.info(
        f"FAJ DATABASE: {DB_PATH}"
    )

    conn = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn



def init_db():

    conn = get_db()


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



    conn.execute("""
    CREATE TABLE IF NOT EXISTS journal (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        date TEXT,
        match TEXT,

        home_team TEXT,
        away_team TEXT,

        prediction TEXT,

        xg_home REAL,
        xg_away REAL,

        expected_score TEXT,

        actual_score TEXT,

        accuracy TEXT
    )
    """)


    conn.execute("""
    CREATE TABLE IF NOT EXISTS api_usage (

        date TEXT PRIMARY KEY,

        used INTEGER DEFAULT 0,

        daily_limit INTEGER DEFAULT 100
    )
    """)



    conn.execute("""
    CREATE TABLE IF NOT EXISTS team_aliases (

        team TEXT,
        alias TEXT PRIMARY KEY
    )
    """)



    conn.commit()


    # Проверка количества данных

    try:

        row = conn.execute(
            "SELECT COUNT(*) as c FROM passports"
        ).fetchone()


        logger.info(
            f"PASSPORTS IN DATABASE: {row['c']}"
        )


    except Exception as e:

        logger.error(e)



    conn.close()
