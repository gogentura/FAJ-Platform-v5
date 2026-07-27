# =====================================================
# FAJ Platform v7.0
# app/database.py
#
# PostgreSQL Database Layer
#
# Single source of truth:
# - team_passports
# - fixtures
# - predictions
# - journal
# - calibration_log
# =====================================================


import os
import logging

import psycopg2

from psycopg2.extras import RealDictCursor


logger = logging.getLogger(__name__)



# =====================================================
# CONNECTION
# =====================================================


class FAJConnection:


    def __init__(self, connection):

        self.connection = connection



    def cursor(self):

        return self.connection.cursor(
            cursor_factory=RealDictCursor
        )



    def commit(self):

        self.connection.commit()



    def close(self):

        self.connection.close()





def get_connection():


    url = os.getenv(
        "DATABASE_URL"
    )


    if not url:

        raise RuntimeError(
            "DATABASE_URL missing"
        )


    conn = psycopg2.connect(
        url
    )


    return FAJConnection(
        conn
    )





def get_db():

    return get_connection()





# =====================================================
# INIT DATABASE
# =====================================================


def init_database():


    conn = get_connection()

    cur = conn.cursor()



    # =================================================
    # TEAM PASSPORTS
    # =================================================


    cur.execute(
    """

    CREATE TABLE IF NOT EXISTS team_passports (

        id SERIAL PRIMARY KEY,


        team TEXT NOT NULL,

        league TEXT NOT NULL,

        season TEXT NOT NULL,


        attack REAL DEFAULT 70,

        defense REAL DEFAULT 70,

        control REAL DEFAULT 70,

        efficiency REAL DEFAULT 70,


        form REAL DEFAULT 70,


        mentality REAL DEFAULT 70,

        discipline REAL DEFAULT 70,

        fitness REAL DEFAULT 70,


        predictability REAL DEFAULT 70,


        xg_for REAL DEFAULT 1.30,

        xg_against REAL DEFAULT 1.30,


        transfer_index REAL DEFAULT 0,

        injury_index REAL DEFAULT 0,

        fatigue_index REAL DEFAULT 0,


        faj_rating REAL DEFAULT 0,


        updated TIMESTAMP DEFAULT NOW(),


        UNIQUE(
            team,
            league,
            season
        )

    );

    """
    )





    # =================================================
    # FIXTURES
    # =================================================


    cur.execute(
    """

    CREATE TABLE IF NOT EXISTS fixtures (


        id SERIAL PRIMARY KEY,


        league TEXT NOT NULL,

        season TEXT NOT NULL,


        round INTEGER,


        match_date DATE,

        match_time TEXT,


        home_team TEXT NOT NULL,

        away_team TEXT NOT NULL,


        status TEXT DEFAULT 'scheduled',



        home_score INTEGER,

        away_score INTEGER,


        winner TEXT,


        source TEXT,


        created TIMESTAMP DEFAULT NOW(),

        updated TIMESTAMP DEFAULT NOW()


    );

    """
    )





    # =================================================
    # PREDICTIONS
    # =================================================


    cur.execute(
    """

    CREATE TABLE IF NOT EXISTS predictions (


        id SERIAL PRIMARY KEY,


        fixture_id INTEGER,


        home_team TEXT,

        away_team TEXT,


        winner TEXT,


        expected_score TEXT,


        home_probability REAL,

        draw_probability REAL,

        away_probability REAL,


        winner_probability REAL,


        home_rating REAL,

        away_rating REAL,


        xg_home REAL,

        xg_away REAL,


        confidence REAL,


        risk TEXT,


        grade TEXT,


        grade_name TEXT,


        passport_quality JSONB,


        season_phase TEXT,


        volatility REAL,


        top_scores JSONB,


        model_version TEXT,


        created TIMESTAMP DEFAULT NOW()


    );

    """
    )





    # =================================================
    # JOURNAL
    # =================================================


    cur.execute(
    """

    CREATE TABLE IF NOT EXISTS journal (


        id SERIAL PRIMARY KEY,


        fixture_id INTEGER,


        home_team TEXT,

        away_team TEXT,


        prediction TEXT,


        expected_score TEXT,


        actual_score TEXT,


        winner TEXT,


        actual_winner TEXT,


        winner_correct BOOLEAN DEFAULT FALSE,


        score_exact BOOLEAN DEFAULT FALSE,


        confidence REAL,


        risk TEXT,


        grade TEXT,


        xg_home REAL,

        xg_away REAL,


        xg_error REAL DEFAULT 0,


        confidence_error REAL DEFAULT 0,


        rating_error REAL DEFAULT 0,


        conclusion TEXT,


        model_version TEXT,


        created TIMESTAMP DEFAULT NOW()


    );

    """
    )





    # =================================================
    # CALIBRATION LOG
    # =================================================


    cur.execute(
    """

    CREATE TABLE IF NOT EXISTS calibration_log (


        id SERIAL PRIMARY KEY,


        fixture_id INTEGER,


        faj_score TEXT,


        fact_score TEXT,


        faj_winner TEXT,


        fact_winner TEXT,


        error_type TEXT,


        xg_error REAL DEFAULT 0,


        confidence_error REAL DEFAULT 0,


        conclusion TEXT,


        created TIMESTAMP DEFAULT NOW()


    );

    """
    )





    conn.commit()


    cur.close()

    conn.close()



    logger.info(
        "FAJ Database v7.0 initialized"
    )





# =====================================================
# COMPATIBILITY
# =====================================================


def init_db():

    return init_database()





# =====================================================
# DATABASE SERVICE
# =====================================================


class Database:


    def get_fixture(
        self,
        league,
        season,
        home_team,
        away_team
    ):


        conn = get_db()

        cur = conn.cursor()



        cur.execute(
        """

        SELECT *

        FROM fixtures


        WHERE league=%s

        AND season=%s

        AND home_team=%s

        AND away_team=%s


        LIMIT 1

        """,

        (
            league,
            season,
            home_team,
            away_team
        )

        )


        row = cur.fetchone()


        conn.close()


        return row





# =====================================================
# AUTO START
# =====================================================


if __name__ == "__main__":

    init_database()
