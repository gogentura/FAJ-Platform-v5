# =====================================================
# FAJ Platform v6.3.1
# app/database.py
#
# PostgreSQL Database Layer
# =====================================================


import os
import logging

from datetime import datetime

import psycopg2

from psycopg2.extras import RealDictCursor


logger = logging.getLogger(__name__)



# =====================================================
# CONNECTION WRAPPER
# =====================================================


class FAJConnection:


    def __init__(self, connection):

        self.connection = connection



    def cursor(self):

        return self.connection.cursor(
            cursor_factory=RealDictCursor
        )



    def execute(
        self,
        query,
        params=None
    ):

        cur = self.cursor()

        cur.execute(
            query,
            params or ()
        )

        return cur



    def commit(self):

        self.connection.commit()



    def close(self):

        self.connection.close()



# =====================================================
# CONNECTION
# =====================================================


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



# compatibility

def get_db():

    return get_connection()



# =====================================================
# INIT DATABASE
# =====================================================


def init_database():


    conn = get_connection()

    cur = conn.cursor()



    # =================================================
    # JOURNAL MIGRATION
    # =================================================


    migrations = [


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS date TIMESTAMP;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS match TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS home_team TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS away_team TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS winner TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS winner_prob REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS home_prob REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS draw_prob REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS away_prob REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS xg_home REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS xg_away REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS expected_score TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS top_scores JSONB;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS btts REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS over25 REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS actual_score TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS actual_winner TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS confidence REAL;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS risk TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS grade TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS faj_rating JSONB;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS model_version TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS data_version TEXT;
        """,


        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS created TIMESTAMP DEFAULT NOW();
        """

    ]



    for migration in migrations:

        try:

            cur.execute(
                migration
            )

            conn.commit()


        except Exception as e:

            logger.warning(
                f"Journal migration skipped: {e}"
            )

            conn.connection.rollback()



    # =================================================
    # CREATE JOURNAL TABLE
    # =================================================


    cur.execute(
        """

        CREATE TABLE IF NOT EXISTS journal

        (

            id SERIAL PRIMARY KEY,


            fixture_id INTEGER,


            date TIMESTAMP,


            match TEXT,


            home_team TEXT,


            away_team TEXT,


            prediction TEXT,


            winner TEXT,


            winner_prob REAL,


            home_prob REAL,


            draw_prob REAL,


            away_prob REAL,


            xg_home REAL,


            xg_away REAL,


            expected_score TEXT,


            top_scores JSONB,


            btts REAL,


            over25 REAL,


            actual_score TEXT,


            actual_winner TEXT,


            confidence REAL,


            risk TEXT,


            grade TEXT,


            faj_rating JSONB,


            model_version TEXT,


            data_version TEXT,


            accuracy REAL,


            error_type TEXT,


            notes TEXT,


            created TIMESTAMP DEFAULT NOW()

        );


        """

    )



    conn.commit()



    cur.close()

    conn.close()



    logger.info(
        "FAJ PostgreSQL database v6.3.1 initialized"
    )



# =====================================================
# DATABASE CLASS
# =====================================================


class Database:



    def get_fixture(

        self,

        league,

        season,

        home_team,

        away_team

    ):


        conn = get_connection()


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
# COMPATIBILITY
# =====================================================


def init_db():

    return init_database()



# =====================================================
# AUTO START
# =====================================================


if __name__ == "__main__":

    init_database()
