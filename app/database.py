#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Personal Prediction Database v1

Personal football prediction workspace.

The database stores:
    - teams
    - competitions
    - analysis sessions
    - analysis matches
    - data sources
    - historical matches
    - historical statistics
    - predictions
    - prediction history

The database DOES NOT perform:
    - learning
    - ETC
    - rating evolution
    - parameter optimization
    - prediction calculations
    - bookmaker integration
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


logger = logging.getLogger(__name__)


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "faj.db")

DB_SCHEMA_VERSION = "personal-v1"

os.makedirs(DATA_DIR, exist_ok=True)


# ============================================================
# CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(
        DB_FILE,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    return conn


@contextmanager
def transaction():
    conn = get_connection()

    try:
        yield conn
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None

    return dict(row)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database() -> None:

    with transaction() as conn:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # SCHEMA
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_info (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            INSERT INTO schema_info (id, version, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                version = excluded.version,
                updated_at = excluded.updated_at
        """, (DB_SCHEMA_VERSION, now()))

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                league TEXT,
                country TEXT,
                api_id INTEGER,
                logo_url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(name, league)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_teams_name
            ON teams(name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_teams_league
            ON teams(league)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_teams_api_id
            ON teams(api_id)
        """)

        # ----------------------------------------------------
        # MIGRATION: TEAMS
        # ----------------------------------------------------
        team_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(teams)"
            ).fetchall()
        }

        if "active" not in team_columns:
            cursor.execute("""
                ALTER TABLE teams
                ADD COLUMN active INTEGER NOT NULL DEFAULT 1
            """)
            logger.info("Добавлена колонка active в таблицу teams")

        if "country" not in team_columns:
            cursor.execute("""
                ALTER TABLE teams
                ADD COLUMN country TEXT
            """)
            logger.info("Добавлена колонка country в таблицу teams")

        if "api_id" not in team_columns:
            cursor.execute("""
                ALTER TABLE teams
                ADD COLUMN api_id INTEGER
            """)
            logger.info("Добавлена колонка api_id в таблицу teams")

        if "logo_url" not in team_columns:
            cursor.execute("""
                ALTER TABLE teams
                ADD COLUMN logo_url TEXT
            """)
            logger.info("Добавлена колонка logo_url в таблицу teams")

        if "created_at" not in team_columns:
            cursor.execute("""
                ALTER TABLE teams
                ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            """)
            logger.info("Добавлена колонка created_at в таблицу teams")

        # ----------------------------------------------------
        # COMPETITIONS
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                country TEXT,
                competition_type TEXT DEFAULT 'league',
                season TEXT,
                api_id INTEGER,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(name, season)
            )
        """)

        # ----------------------------------------------------
        # MIGRATION: COMPETITIONS
        # ----------------------------------------------------
        competition_columns = {
            row["name"]
            for row in cursor.execute(
                "PRAGMA table_info(competitions)"
            ).fetchall()
        }

        if "active" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN active INTEGER NOT NULL DEFAULT 1
            """)
            logger.info("Добавлена колонка active в таблицу competitions")

        if "country" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN country TEXT
            """)
            logger.info("Добавлена колонка country в таблицу competitions")

        if "competition_type" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN competition_type TEXT DEFAULT 'league'
            """)
            logger.info("Добавлена колонка competition_type в таблицу competitions")

        if "season" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN season TEXT
            """)
            logger.info("Добавлена колонка season в таблицу competitions")

        if "api_id" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN api_id INTEGER
            """)
            logger.info("Добавлена колонка api_id в таблицу competitions")

        if "created_at" not in competition_columns:
            cursor.execute("""
                ALTER TABLE competitions
                ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            """)
            logger.info("Добавлена колонка created_at в таблицу competitions")

        # ----------------------------------------------------
        # TEAM / COMPETITION
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_competitions (
                team_id INTEGER NOT NULL,
                competition_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                PRIMARY KEY(team_id, competition_id),

                FOREIGN KEY(team_id)
                    REFERENCES teams(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(competition_id)
                    REFERENCES competitions(id)
                    ON DELETE CASCADE
            )
        """)

        # ----------------------------------------------------
        # ANALYSIS SESSION
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                competition_id INTEGER,

                title TEXT,
                notes TEXT,

                status TEXT NOT NULL DEFAULT 'draft',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,

                FOREIGN KEY(competition_id)
                    REFERENCES competitions(id)
                    ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_sessions_date
            ON analysis_sessions(created_at)
        """)

        # ----------------------------------------------------
        # ANALYSIS MATCH
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                session_id INTEGER NOT NULL,

                home_team_id INTEGER NOT NULL,
                away_team_id INTEGER NOT NULL,

                match_date TEXT,

                status TEXT NOT NULL DEFAULT 'draft',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(session_id)
                    REFERENCES analysis_sessions(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(home_team_id)
                    REFERENCES teams(id),

                FOREIGN KEY(away_team_id)
                    REFERENCES teams(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_matches_session
            ON analysis_matches(session_id)
        """)

        # ----------------------------------------------------
        # SOURCES
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                analysis_match_id INTEGER NOT NULL,
                team_id INTEGER,

                source_type TEXT NOT NULL,
                source_name TEXT,

                source_url TEXT,
                external_id TEXT,

                parser_version TEXT,

                status TEXT NOT NULL DEFAULT 'pending',

                collected_at TEXT,

                raw_metadata TEXT DEFAULT '{}',

                FOREIGN KEY(analysis_match_id)
                    REFERENCES analysis_matches(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(team_id)
                    REFERENCES teams(id)
                    ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sources_analysis_match
            ON analysis_sources(analysis_match_id)
        """)

        # ----------------------------------------------------
        # HISTORICAL MATCHES
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                analysis_match_id INTEGER NOT NULL,

                team_id INTEGER NOT NULL,
                opponent_team_id INTEGER,

                source_id INTEGER,

                external_match_id TEXT,

                match_date TEXT,

                is_home INTEGER NOT NULL,

                goals_for INTEGER,
                goals_against INTEGER,

                result TEXT,

                raw_metadata TEXT DEFAULT '{}',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(analysis_match_id)
                    REFERENCES analysis_matches(id)
                    ON DELETE CASCADE,

                FOREIGN KEY(team_id)
                    REFERENCES teams(id),

                FOREIGN KEY(opponent_team_id)
                    REFERENCES teams(id),

                FOREIGN KEY(source_id)
                    REFERENCES analysis_sources(id)
                    ON DELETE SET NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historical_matches_analysis
            ON historical_matches(analysis_match_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historical_matches_team
            ON historical_matches(team_id)
        """)

        # ----------------------------------------------------
        # HISTORICAL STATISTICS
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                historical_match_id INTEGER NOT NULL,

                possession REAL,

                shots INTEGER,
                shots_on_target INTEGER,

                corners INTEGER,

                fouls INTEGER,

                yellow_cards INTEGER,
                red_cards INTEGER,

                xg REAL,

                big_chances INTEGER,

                saves INTEGER,

                passes INTEGER,
                accurate_passes INTEGER,
                pass_accuracy REAL,

                tackles INTEGER,

                offsides INTEGER,

                raw_metadata TEXT DEFAULT '{}',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(historical_match_id)
                    REFERENCES historical_matches(id)
                    ON DELETE CASCADE,

                UNIQUE(historical_match_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_historical_stats_match
            ON historical_stats(historical_match_id)
        """)

        # ----------------------------------------------------
        # PREDICTIONS
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                analysis_match_id INTEGER NOT NULL,

                model_version TEXT NOT NULL,

                home_xg REAL,
                away_xg REAL,

                home_goals_expected REAL,
                away_goals_expected REAL,

                home_win_probability REAL,
                draw_probability REAL,
                away_win_probability REAL,

                btts_probability REAL,

                over15_probability REAL,
                over25_probability REAL,
                over35_probability REAL,

                under15_probability REAL,
                under25_probability REAL,
                under35_probability REAL,

                first_half_home_xg REAL,
                first_half_away_xg REAL,

                first_half_over05_probability REAL,
                first_half_over15_probability REAL,

                corners_expected REAL,
                home_corners_expected REAL,
                away_corners_expected REAL,

                cards_expected REAL,
                home_cards_expected REAL,
                away_cards_expected REAL,

                most_likely_score TEXT,
                second_likely_score TEXT,
                third_likely_score TEXT,

                confidence REAL,
                risk TEXT,

                summary TEXT,

                analysis_json TEXT DEFAULT '{}',

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(analysis_match_id)
                    REFERENCES analysis_matches(id)
                    ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_match
            ON predictions(analysis_match_id)
        """)

        # ----------------------------------------------------
        # PREDICTION HISTORY
        # ----------------------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                prediction_id INTEGER NOT NULL,

                snapshot_json TEXT NOT NULL,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(prediction_id)
                    REFERENCES predictions(id)
                    ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_prediction_history_prediction
            ON prediction_history(prediction_id)
        """)


# ============================================================
# DATABASE CLASS
# ============================================================

class FAJDatabase:

    def __init__(self):
        init_database()

    def get_connection(self):
        return get_connection()

    # ========================================================
    # TEAMS
    # ========================================================

    def get_teams(self, league: Optional[str] = None) -> List[Dict[str, Any]]:

        with self.get_connection() as conn:

            if league:
                rows = conn.execute("""
                    SELECT *
                    FROM teams
                    WHERE active = 1
                      AND league = ?
                    ORDER BY name
                """, (league,)).fetchall()

            else:
                rows = conn.execute("""
                    SELECT *
                    FROM teams
                    WHERE active = 1
                    ORDER BY name
                """).fetchall()

            return rows_to_dicts(rows)

    def get_team(self, team_id: int):

        with self.get_connection() as conn:

            row = conn.execute("""
                SELECT *
                FROM teams
                WHERE id = ?
            """, (team_id,)).fetchone()

            return row_to_dict(row)

    # ========================================================
    # COMPETITIONS
    # ========================================================

    def get_competitions(self) -> List[Dict[str, Any]]:

        with self.get_connection() as conn:

            rows = conn.execute("""
                SELECT *
                FROM competitions
                WHERE active = 1
                ORDER BY name
            """).fetchall()

            return rows_to_dicts(rows)

    # ========================================================
    # ANALYSIS SESSIONS
    # ========================================================

    def create_analysis_session(
        self,
        competition_id: Optional[int] = None,
        title: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO analysis_sessions (
                    competition_id,
                    title,
                    notes,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, 'draft', ?)
            """, (
                competition_id,
                title,
                notes,
                now(),
            ))

            return cursor.lastrowid

    def get_analysis_session(self, session_id: int):

        with self.get_connection() as conn:

            row = conn.execute("""
                SELECT
                    s.*,
                    c.name AS competition_name
                FROM analysis_sessions s
                LEFT JOIN competitions c
                    ON c.id = s.competition_id
                WHERE s.id = ?
            """, (session_id,)).fetchone()

            return row_to_dict(row)

    # ========================================================
    # ANALYSIS MATCHES
    # ========================================================

    def add_analysis_match(
        self,
        session_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[str] = None,
    ) -> int:

        if home_team_id == away_team_id:
            raise ValueError("Home and away teams must be different.")

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO analysis_matches (
                    session_id,
                    home_team_id,
                    away_team_id,
                    match_date,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'draft', ?)
            """, (
                session_id,
                home_team_id,
                away_team_id,
                match_date,
                now(),
            ))

            return cursor.lastrowid

    def get_analysis_matches(
        self,
        session_id: int,
    ) -> List[Dict[str, Any]]:

        with self.get_connection() as conn:

            rows = conn.execute("""
                SELECT
                    am.*,
                    ht.name AS home_team,
                    at.name AS away_team
                FROM analysis_matches am

                JOIN teams ht
                    ON ht.id = am.home_team_id

                JOIN teams at
                    ON at.id = am.away_team_id

                WHERE am.session_id = ?

                ORDER BY am.id
            """, (session_id,)).fetchall()

            return rows_to_dicts(rows)

    # ========================================================
    # SOURCES
    # ========================================================

    def add_source(
        self,
        analysis_match_id: int,
        source_type: str,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        team_id: Optional[int] = None,
        external_id: Optional[str] = None,
        parser_version: Optional[str] = None,
    ) -> int:

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO analysis_sources (
                    analysis_match_id,
                    team_id,
                    source_type,
                    source_name,
                    source_url,
                    external_id,
                    parser_version,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                analysis_match_id,
                team_id,
                source_type,
                source_name,
                source_url,
                external_id,
                parser_version,
            ))

            return cursor.lastrowid

    # ========================================================
    # HISTORICAL MATCH
    # ========================================================

    def save_historical_match(
        self,
        analysis_match_id: int,
        team_id: int,
        opponent_team_id: Optional[int],
        source_id: Optional[int],
        match_date: Optional[str],
        is_home: bool,
        goals_for: Optional[int],
        goals_against: Optional[int],
        result: Optional[str],
        external_match_id: Optional[str] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
    ) -> int:

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO historical_matches (
                    analysis_match_id,
                    team_id,
                    opponent_team_id,
                    source_id,
                    external_match_id,
                    match_date,
                    is_home,
                    goals_for,
                    goals_against,
                    result,
                    raw_metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_match_id,
                team_id,
                opponent_team_id,
                source_id,
                external_match_id,
                match_date,
                int(is_home),
                goals_for,
                goals_against,
                result,
                json.dumps(raw_metadata or {}, ensure_ascii=False),
            ))

            return cursor.lastrowid

    # ========================================================
    # HISTORICAL STATISTICS
    # ========================================================

    def save_historical_stats(
        self,
        historical_match_id: int,
        stats: Dict[str, Any],
    ) -> int:

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO historical_stats (
                    historical_match_id,
                    possession,
                    shots,
                    shots_on_target,
                    corners,
                    fouls,
                    yellow_cards,
                    red_cards,
                    xg,
                    big_chances,
                    saves,
                    passes,
                    accurate_passes,
                    pass_accuracy,
                    tackles,
                    offsides,
                    raw_metadata
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                historical_match_id,
                stats.get("possession"),
                stats.get("shots"),
                stats.get("shots_on_target"),
                stats.get("corners"),
                stats.get("fouls"),
                stats.get("yellow_cards"),
                stats.get("red_cards"),
                stats.get("xg"),
                stats.get("big_chances"),
                stats.get("saves"),
                stats.get("passes"),
                stats.get("accurate_passes"),
                stats.get("pass_accuracy"),
                stats.get("tackles"),
                stats.get("offsides"),
                json.dumps(
                    stats.get("raw_metadata", {}),
                    ensure_ascii=False,
                ),
            ))

            return cursor.lastrowid

    # ========================================================
    # RECENT HISTORICAL MATCHES
    # ========================================================

    def get_recent_historical_matches(
        self,
        team_id: int,
        before_date: Optional[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает последние завершённые исторические матчи
        конкретной команды перед датой прогнозируемого матча.

        Правило FAJ:
            team
                ↓
            before forecast date
                ↓
            match_date DESC
                ↓
            LIMIT 5

        Важно:
            будущие матчи и сам прогнозируемый матч
            в историю не попадают.
        """
        if not team_id:
            return []

        try:
            limit = max(
                1,
                min(int(limit), 20),
            )
        except (TypeError, ValueError):
            limit = 5

        with self.get_connection() as conn:
            if before_date:
                rows = conn.execute(
                    """
                    SELECT
                        hm.*,
                        t.name AS team_name,
                        ot.name AS opponent_name
                    FROM historical_matches hm
                    JOIN teams t
                        ON t.id = hm.team_id
                    LEFT JOIN teams ot
                        ON ot.id = hm.opponent_team_id
                    WHERE hm.team_id = ?
                      AND hm.match_date IS NOT NULL
                      AND date(hm.match_date) < date(?)
                    ORDER BY
                        date(hm.match_date) DESC,
                        hm.id DESC
                    LIMIT ?
                    """,
                    (
                        team_id,
                        before_date,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT
                        hm.*,
                        t.name AS team_name,
                        ot.name AS opponent_name
                    FROM historical_matches hm
                    JOIN teams t
                        ON t.id = hm.team_id
                    LEFT JOIN teams ot
                        ON ot.id = hm.opponent_team_id
                    WHERE hm.team_id = ?
                      AND hm.match_date IS NOT NULL
                    ORDER BY
                        date(hm.match_date) DESC,
                        hm.id DESC
                    LIMIT ?
                    """,
                    (
                        team_id,
                        limit,
                    ),
                ).fetchall()

            return rows_to_dicts(rows)

    # ========================================================
    # PREDICTIONS
    # ========================================================

    def save_prediction(
        self,
        analysis_match_id: int,
        prediction: Dict[str, Any],
        model_version: str,
    ) -> int:

        with transaction() as conn:

            cursor = conn.execute("""
                INSERT INTO predictions (
                    analysis_match_id,
                    model_version,

                    home_xg,
                    away_xg,

                    home_goals_expected,
                    away_goals_expected,

                    home_win_probability,
                    draw_probability,
                    away_win_probability,

                    btts_probability,

                    over15_probability,
                    over25_probability,
                    over35_probability,

                    under15_probability,
                    under25_probability,
                    under35_probability,

                    first_half_home_xg,
                    first_half_away_xg,

                    first_half_over05_probability,
                    first_half_over15_probability,

                    corners_expected,
                    home_corners_expected,
                    away_corners_expected,

                    cards_expected,
                    home_cards_expected,
                    away_cards_expected,

                    most_likely_score,
                    second_likely_score,
                    third_likely_score,

                    confidence,
                    risk,

                    summary,
                    analysis_json
                )
                VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?
                )
            """, (
                analysis_match_id,
                model_version,

                prediction.get("home_xg"),
                prediction.get("away_xg"),

                prediction.get("home_goals_expected"),
                prediction.get("away_goals_expected"),

                prediction.get("home_win_probability"),
                prediction.get("draw_probability"),
                prediction.get("away_win_probability"),

                prediction.get("btts_probability"),

                prediction.get("over15_probability"),
                prediction.get("over25_probability"),
                prediction.get("over35_probability"),

                prediction.get("under15_probability"),
                prediction.get("under25_probability"),
                prediction.get("under35_probability"),

                prediction.get("first_half_home_xg"),
                prediction.get("first_half_away_xg"),

                prediction.get("first_half_over05_probability"),
                prediction.get("first_half_over15_probability"),

                prediction.get("corners_expected"),
                prediction.get("home_corners_expected"),
                prediction.get("away_corners_expected"),

                prediction.get("cards_expected"),
                prediction.get("home_cards_expected"),
                prediction.get("away_cards_expected"),

                prediction.get("most_likely_score"),
                prediction.get("second_likely_score"),
                prediction.get("third_likely_score"),

                prediction.get("confidence"),
                prediction.get("risk"),

                prediction.get("summary"),

                json.dumps(
                    prediction.get("analysis_json", {}),
                    ensure_ascii=False,
                ),
            ))

            prediction_id = cursor.lastrowid

            # Immutable personal snapshot.
            conn.execute("""
                INSERT INTO prediction_history (
                    prediction_id,
                    snapshot_json,
                    created_at
                )
                VALUES (?, ?, ?)
            """, (
                prediction_id,
                json.dumps(
                    prediction,
                    ensure_ascii=False,
                ),
                now(),
            ))

            return prediction_id

    def get_prediction(
        self,
        prediction_id: int,
    ) -> Optional[Dict[str, Any]]:

        with self.get_connection() as conn:

            row = conn.execute("""
                SELECT
                    p.*,
                    am.session_id,
                    am.match_date,

                    ht.name AS home_team,
                    at.name AS away_team

                FROM predictions p

                JOIN analysis_matches am
                    ON am.id = p.analysis_match_id

                JOIN teams ht
                    ON ht.id = am.home_team_id

                JOIN teams at
                    ON at.id = am.away_team_id

                WHERE p.id = ?
            """, (prediction_id,)).fetchone()

            result = row_to_dict(row)

            if result and result.get("analysis_json"):
                try:
                    result["analysis_json"] = json.loads(
                        result["analysis_json"]
                    )
                except (TypeError, json.JSONDecodeError):
                    result["analysis_json"] = {}

            return result

    # ========================================================
    # HISTORY
    # ========================================================

    def get_prediction_history(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:

        with self.get_connection() as conn:

            rows = conn.execute("""
                SELECT
                    p.id,
                    p.created_at,
                    p.model_version,

                    p.home_xg,
                    p.away_xg,

                    p.home_win_probability,
                    p.draw_probability,
                    p.away_win_probability,

                    p.btts_probability,

                    p.most_likely_score,
                    p.confidence,
                    p.risk,

                    ht.name AS home_team,
                    at.name AS away_team

                FROM predictions p

                JOIN analysis_matches am
                    ON am.id = p.analysis_match_id

                JOIN teams ht
                    ON ht.id = am.home_team_id

                JOIN teams at
                    ON at.id = am.away_team_id

                ORDER BY p.id DESC

                LIMIT ?
            """, (limit,)).fetchall()

            return rows_to_dicts(rows)

    # ========================================================
    # CLEANUP
    # ========================================================

    def delete_analysis_session(
        self,
        session_id: int,
    ) -> None:

        with transaction() as conn:

            conn.execute("""
                DELETE FROM analysis_sessions
                WHERE id = ?
            """, (session_id,))

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self) -> Dict[str, Any]:

        with self.get_connection() as conn:

            tables = conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """).fetchall()

            return {
                "status": "online",
                "database": DB_FILE,
                "schema_version": DB_SCHEMA_VERSION,
                "tables": [
                    row["name"]
                    for row in tables
                ],
            }


# ============================================================
# MODULE INITIALIZATION
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    init_database()

    db = FAJDatabase()

    logger.info(
        "FAJ Personal Prediction Database initialized: %s",
        db.get_status(),
    )
