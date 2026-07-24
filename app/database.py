# =====================================================
# FAJ Platform v6.2
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
# CONNECTION
# =====================================================

def get_connection():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


# =====================================================
# COMPATIBILITY LAYER (for old modules)
# =====================================================

def get_db():
    """Совместимость со старыми monitoring modules"""
    return get_connection()


# =====================================================
# INIT DATABASE
# =====================================================

def init_database():
    conn = get_connection()
    cur = conn.cursor()

    # ================================================
    # FIXTURES
    # ================================================
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
            result TEXT,
            winner TEXT,
            source TEXT,
            created TIMESTAMP DEFAULT NOW(),
            updated TIMESTAMP DEFAULT NOW()
        );
        """
    )

    # ================================================
    # TEAM PASSPORTS
    # ================================================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS team_passports (
            id SERIAL PRIMARY KEY,
            league TEXT,
            season TEXT,
            team TEXT,
            attack REAL,
            defense REAL,
            control REAL,
            efficiency REAL,
            mentality REAL,
            discipline REAL,
            fitness REAL,
            predictability REAL,
            xg_for REAL,
            xg_against REAL,
            form REAL,
            injury_index REAL DEFAULT 0,
            fatigue_index REAL DEFAULT 0,
            transfer_index REAL DEFAULT 0,
            updated TIMESTAMP DEFAULT NOW(),
            UNIQUE(league, season, team)
        );
        """
    )

    # ================================================
    # MATCH STATISTICS
    # ================================================
    cur.execute(
        """
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
        """
    )

    # ================================================
    # PREDICTIONS
    # ================================================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER REFERENCES fixtures(id),
            home_win REAL,
            draw REAL,
            away_win REAL,
            xg_home REAL,
            xg_away REAL,
            score_prediction TEXT,
            confidence REAL,
            model_version TEXT,
            created TIMESTAMP DEFAULT NOW()
        );
        """
    )

    # ================================================
    # JOURNAL
    # ================================================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id SERIAL PRIMARY KEY,
            fixture_id INTEGER,
            prediction TEXT,
            actual_result TEXT,
            accuracy REAL,
            error_type TEXT,
            notes TEXT,
            created TIMESTAMP DEFAULT NOW()
        );
        """
    )

    # ================================================
    # SOURCES MONITOR
    # ================================================
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sources_monitor (
            id SERIAL PRIMARY KEY,
            source TEXT UNIQUE,
            url TEXT,
            status TEXT,
            last_check TIMESTAMP,
            last_update TIMESTAMP,
            errors TEXT
        );
        """
    )

    conn.commit()
    cur.close()
    conn.close()

    logger.info("FAJ database initialized")


# =====================================================
# FIXTURES METHODS
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

    def insert_fixture(self, data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO fixtures
            (league, season, match_date, match_time, home_team, away_team, status, source)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                data["league"],
                data["season"],
                data["date"],
                data["time"],
                data["home_team"],
                data["away_team"],
                data["status"],
                "soccer365"
            )
        )
        conn.commit()
        conn.close()

    def update_fixture(self, fixture_id, data):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE fixtures
            SET match_date=%s,
                match_time=%s,
                status=%s,
                updated=%s
            WHERE id=%s
            """,
            (
                data["date"],
                data["time"],
                data["status"],
                datetime.now(),
                fixture_id
            )
        )
        conn.commit()
        conn.close()


# =====================================================
# COMPATIBILITY ALIAS (for main.py, bot.py, handlers)
# =====================================================

def init_db():
    """Совместимость со старыми вызовами (main.py, bot.py, handlers)"""
    return init_database()


# =====================================================
# AUTO INIT
# =====================================================

if __name__ == "__main__":
    init_database()
