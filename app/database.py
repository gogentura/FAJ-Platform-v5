# =====================================================
# FAJ Platform v6.9.2
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
        return self.connection.cursor(cursor_factory=RealDictCursor)

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params or ())
        return cur

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


# =====================================================
# CONNECTION
# =====================================================

def get_connection():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL missing")
    conn = psycopg2.connect(url)
    return FAJConnection(conn)

def get_db():
    return get_connection()


# =====================================================
# INIT DATABASE
# =====================================================

def init_database():
    conn = get_connection()
    cur = conn.cursor()

    # =================================================
    # MIGRATIONS
    # =================================================

    migrations = [
        # ---------- team_passports ----------
        """
        ALTER TABLE team_passports
        ADD COLUMN IF NOT EXISTS faj_rating REAL DEFAULT 0;
        """,
        # ---------- journal ----------
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS fixture_id INTEGER;
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
        ADD COLUMN IF NOT EXISTS league TEXT;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS winner TEXT;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS winner_probability REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS home_probability REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS draw_probability REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS away_probability REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS home_rating REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS away_rating REAL;
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
        ADD COLUMN IF NOT EXISTS grade_name TEXT;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS actual_score TEXT;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS winner_correct BOOLEAN;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS score_exact BOOLEAN;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS accuracy REAL;
        """,
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
        ADD COLUMN IF NOT EXISTS prediction TEXT;
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
        ADD COLUMN IF NOT EXISTS confidence REAL;
        """,
        """
        ALTER TABLE journal
        ADD COLUMN IF NOT EXISTS actual_winner TEXT;
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
        """,
        # ---------- predictions (новые колонки) ----------
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS home_team TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS away_team TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS league TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS season TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS winner TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS expected_score TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS home_rating REAL;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS away_rating REAL;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS home_probability REAL;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS draw_probability REAL;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS away_probability REAL;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS risk TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS category TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS factors JSONB;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS season_phase TEXT;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS passport_quality JSONB;
        """,
        """
        ALTER TABLE predictions
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
        """
    ]

    for migration in migrations:
        try:
            cur.execute(migration)
            conn.commit()
        except Exception as e:
            logger.warning(f"Migration skipped: {e}")
            conn.connection.rollback()

    # =================================================
    # CREATE TABLES
    # =================================================

    # ---------- team_passports ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_passports (
            id SERIAL PRIMARY KEY,
            team TEXT NOT NULL,
            league TEXT NOT NULL,
            season TEXT NOT NULL,
            attack REAL DEFAULT 70,
            defense REAL DEFAULT 70,
            control REAL DEFAULT 70,
            efficiency REAL DEFAULT 70,
            mentality REAL DEFAULT 70,
            discipline REAL DEFAULT 70,
            fitness REAL DEFAULT 70,
            predictability REAL DEFAULT 70,
            form REAL DEFAULT 70,
            xg_for REAL DEFAULT 1.30,
            xg_against REAL DEFAULT 1.30,
            transfer_index REAL DEFAULT 0,
            injury_index REAL DEFAULT 0,
            fatigue_index REAL DEFAULT 0,
            faj_rating REAL DEFAULT 0,
            updated TIMESTAMP DEFAULT NOW(),
            UNIQUE(team, league, season)
        );
    """)

    # ---------- fixtures ----------
    cur.execute("""
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
            result TEXT,
            winner TEXT,
            source TEXT,
            match_url TEXT,
            created TIMESTAMP DEFAULT NOW(),
            updated TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---------- journal ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER,
            date TIMESTAMP,
            match TEXT,
            home_team TEXT,
            away_team TEXT,
            league TEXT,
            prediction TEXT,
            winner TEXT,
            winner_probability REAL,
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
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
            grade_name TEXT,
            home_rating REAL,
            away_rating REAL,
            faj_rating JSONB,
            model_version TEXT,
            data_version TEXT,
            accuracy REAL,
            winner_correct BOOLEAN,
            score_exact BOOLEAN,
            error_type TEXT,
            notes TEXT,
            created TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---------- match_statistics ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_statistics (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER REFERENCES fixtures(id),
            xg_home REAL,
            xg_away REAL,
            shots_home INTEGER,
            shots_away INTEGER,
            shots_target_home INTEGER,
            shots_target_away INTEGER,
            possession_home REAL,
            possession_away REAL,
            corners_home INTEGER,
            corners_away INTEGER,
            cards_home INTEGER,
            cards_away INTEGER,
            source TEXT,
            updated TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---------- predictions (новая структура) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER REFERENCES fixtures(id),
            home_team TEXT,
            away_team TEXT,
            league TEXT,
            season TEXT,
            winner TEXT,
            expected_score TEXT,
            xg_home REAL,
            xg_away REAL,
            home_rating REAL,
            away_rating REAL,
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
            confidence REAL,
            risk TEXT,
            category TEXT,
            factors JSONB,
            season_phase TEXT,
            passport_quality JSONB,
            model_version TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # ---------- sources_monitor ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sources_monitor (
            id SERIAL PRIMARY KEY,
            source TEXT UNIQUE,
            url TEXT,
            status TEXT,
            last_check TIMESTAMP,
            last_update TIMESTAMP,
            errors TEXT
        );
    """)

    # ---------- calibration_log ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS calibration_log (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER,
            faj_score TEXT,
            fact_score TEXT,
            faj_winner TEXT,
            fact_winner TEXT,
            expert_score TEXT,
            expert_winner TEXT,
            error_type TEXT,
            rating_gap_error FLOAT DEFAULT 0,
            xg_error FLOAT DEFAULT 0,
            confidence_error FLOAT DEFAULT 0,
            conclusion TEXT,
            created TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

    logger.info("FAJ PostgreSQL database v6.9.2 initialized")


# =====================================================
# DATABASE CLASS
# =====================================================

class Database:
    def get_fixture(self, league, season, home_team, away_team):
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
            (league, season, home_team, away_team)
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
