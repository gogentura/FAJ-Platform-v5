import os
from datetime import datetime


DATABASE_URL = os.getenv("DATABASE_URL")


# =====================================================
# CONNECTION
# =====================================================

def get_db():

    if not DATABASE_URL:

        raise Exception(
            "DATABASE_URL не найден в Railway Variables"
        )


    try:

        import psycopg2

        from psycopg2.extras import RealDictCursor


        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )


        print(
            "✅ PostgreSQL connected"
        )


        return PostgresWrapper(conn)



    except Exception as e:


        print(
            "❌ POSTGRES ERROR:",
            e
        )


        raise e



# =====================================================
# POSTGRES WRAPPER
# =====================================================

class PostgresWrapper:


    def __init__(self, conn):

        self.conn = conn



    def execute(
        self,
        query,
        params=()
    ):


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

        historical_xg_source TEXT,


        avg_goals_value REAL,

        avg_goals_source TEXT,


        avg_goals_conceded_value REAL,

        avg_goals_conceded_source TEXT,


        avg_possession_value REAL,

        avg_possession_source TEXT,


        version INTEGER,


        created TEXT,

        updated TEXT,


        data TEXT

    )
    """
    )



    # =================================================
    # PASSPORT MIGRATION
    # =================================================


    passport_columns = [

        "historical_xg_source TEXT",

        "avg_goals_source TEXT",

        "avg_goals_conceded_source TEXT",

        "avg_possession_source TEXT",

        "data TEXT"

    ]


    for column in passport_columns:


        try:

            conn.execute(
                f"""
                ALTER TABLE passports
                ADD COLUMN {column}
                """
            )


        except Exception:

            pass



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
    # API USAGE
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
    # MODEL CONFIG
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


    return row["cnt"] if row else 0




def database_info():


    return {


        "database":
        "PostgreSQL Railway",


        "time":
        datetime.now().isoformat()


    }
