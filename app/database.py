import os
import sqlite3
from datetime import datetime


DATABASE_URL = os.getenv("DATABASE_URL")


# =====================================================
# CONNECTION
# =====================================================

def get_db():

    if DATABASE_URL:

        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            conn = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=RealDictCursor
            )

            return PostgresWrapper(conn)

        except Exception as e:
            print("POSTGRES ERROR:", e)


    conn = sqlite3.connect(
        "faj.db"
    )

    conn.row_factory = sqlite3.Row

    return conn



# =====================================================
# POSTGRES WRAPPER
# =====================================================

class PostgresWrapper:


    def __init__(self, conn):

        self.conn = conn



    def execute(self, query, params=()):

        query = query.replace(
            "?",
            "%s"
        )

        cursor = self.conn.cursor()

        cursor.execute(
            query,
            params
        )

        return cursor



    def commit(self):

        self.conn.commit()



    def close(self):

        self.conn.close()



# =====================================================
# INIT DATABASE
# =====================================================

def init_db():

    conn = get_db()



    # =================================================
    # PASSPORTS
    # =================================================

    conn.execute(
    """
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


        avg_goals_value REAL,

        avg_goals_conceded_value REAL,


        avg_possession_value REAL,


        version INTEGER,


        created TEXT,

        updated TEXT

    )
    """
    )



    # =================================================
    # JOURNAL
    # =================================================

    conn.execute(
    """
    CREATE TABLE IF NOT EXISTS journal (

        id SERIAL PRIMARY KEY,


        match TEXT,


        prediction TEXT,


        home_team TEXT,

        away_team TEXT,


        league TEXT,


        winner TEXT,


        winner_prob REAL,


        home_prob REAL,

        draw_prob REAL,

        away_prob REAL,


        expected_score TEXT,


        top_scores TEXT,


        btts REAL,


        over25 REAL,


        actual_winner TEXT,


        actual_score TEXT,


        data_version TEXT,


        date TEXT,


        created TEXT

    )
    """
    )



    # =================================================
    # MIGRATION JOURNAL
    # =================================================

    journal_columns = [

        "match TEXT",

        "prediction TEXT",

        "winner_prob REAL",

        "actual_winner TEXT",

        "actual_score TEXT",

        "data_version TEXT",

        "date TEXT",

        "top_scores TEXT",

        "btts REAL",

        "over25 REAL"

    ]


    for column in journal_columns:

        try:

            conn.execute(
                f"""
                ALTER TABLE journal
                ADD COLUMN {column}
                """
            )

        except Exception:

            pass



    # =================================================
    # ALIASES
    # =================================================

    conn.execute(
    """
    CREATE TABLE IF NOT EXISTS team_aliases (

        team TEXT NOT NULL,

        alias TEXT PRIMARY KEY

    )
    """
    )



    # =================================================
    # API
    # =================================================

    conn.execute(
    """
    CREATE TABLE IF NOT EXISTS api_usage (

        id SERIAL PRIMARY KEY,

        service TEXT,

        used INTEGER DEFAULT 0,

        limit_value INTEGER,

        updated TEXT

    )
    """
    )



    # =================================================
    # CONFIG
    # =================================================

    conn.execute(
    """
    CREATE TABLE IF NOT EXISTS model_config (

        key TEXT PRIMARY KEY,

        value TEXT

    )
    """
    )



    conn.commit()

    conn.close()



# =====================================================
# HELPERS
# =====================================================

def count_passports():

    conn = get_db()


    row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM passports
        """
    ).fetchone()


    conn.close()


    if row:

        return row["cnt"]


    return 0



def database_info():

    return {

        "database":
        "PostgreSQL"
        if DATABASE_URL
        else "SQLite",


        "time":
        datetime.now().isoformat()

    }
