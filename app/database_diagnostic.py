#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Database Diagnostic
============================================================

НАЗНАЧЕНИЕ:
    Полная диагностика текущей SQLite базы FAJ.

ВАЖНО:
    Этот модуль НЕ изменяет БД.
    Только чтение.

Проверяет:
    - существование БД
    - schema version
    - таблицы
    - команды
    - сезоны
    - туры
    - паспорта
    - legacy passport layers
    - orphan records
    - основные prediction / learning таблицы
"""

from __future__ import annotations

import os
import sqlite3
import logging
from typing import Any

from app.database import FAJDatabase, DB_FILE


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

EXPECTED_LEAGUE = "РПЛ"
EXPECTED_SEASON = "2026-2027"
EXPECTED_TEAMS = 16
EXPECTED_ROUNDS = 30

REQUIRED_TABLES = [
    "teams",
    "seasons",
    "rounds",
    "matches",
    "team_base",
    "team_dynamic",
    "team_identity",
    "team_passports",
    "team_passport_meta",
    "tactical_matchup",
    "match_predictions",
    "predictions",
    "prediction_scores",
    "prediction_distributions",
    "prediction_validation",
    "match_results",
    "match_statistics",
    "standings",
    "gold_dataset",
    "learning_records",
    "learning_events",
    "audit_log",
    "expert_predictions",
    "journal",
    "model_parameters",
    "learning_memory",
    "xg_memory",
    "match_snapshots",
    "player_impact",
    "team_competition_profile",
    "team_events",
    "team_history",
    "match_events",
    "players",
    "player_events",
    "migrations",
    "schema_migrations",
]


PASSPORT_FIELDS = [
    "attack",
    "defense",
    "control",
    "tempo",
    "press",
    "transition",
    "finishing",
    "goalkeeper",
    "discipline",
    "squad_quality",
    "bench_quality",
    "coach_factor",
    "mental",
    "home_strength",
    "away_strength",
    "injury_factor",
    "key_player_loss",
    "league_adaptation",
    "form",
    "passport_confidence",
    "faj_rating",
]


LEGACY_TABLES = [
    "team_base",
    "team_identity",
    "team_dynamic",
    "team_passport_meta",
]


# ============================================================
# HELPER
# ============================================================

def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return dict(row)


def _safe_count(
    conn: sqlite3.Connection,
    table: str,
) -> int:
    try:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM {table}"
        ).fetchone()

        return int(row["cnt"]) if row else 0

    except Exception:
        return -1


def _table_exists(
    conn: sqlite3.Connection,
    table: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table,),
    ).fetchone()

    return row is not None


# ============================================================
# DIAGNOSTIC ENGINE
# ============================================================

class DatabaseDiagnostic:

    def __init__(self):
        self.db = FAJDatabase()

        self.result = {
            "status": "unknown",
            "database": {},
            "schema": {},
            "tables": {},
            "teams": {},
            "seasons": {},
            "rounds": {},
            "passports": {},
            "legacy": {},
            "integrity": {},
            "data_counts": {},
            "issues": [],
            "warnings": [],
        }

    # ========================================================
    # CONNECTION
    # ========================================================

    def _connection(self):
        """
        Используем официальный get_connection()
        FAJDatabase.

        Никаких прямых подключений через
        внутренние методы database.py.
        """

        return self.db.get_connection()

    # ========================================================
    # DATABASE
    # ========================================================

    def check_database(self):

        exists = os.path.exists(DB_FILE)

        self.result["database"] = {
            "exists": exists,
            "file": DB_FILE,
            "size_bytes": (
                os.path.getsize(DB_FILE)
                if exists
                else 0
            ),
        }

        if not exists:
            self.result["issues"].append(
                f"Database file does not exist: {DB_FILE}"
            )

            return

        try:

            conn = self._connection()

            conn.execute("SELECT 1").fetchone()

            journal_mode = conn.execute(
                "PRAGMA journal_mode"
            ).fetchone()[0]

            foreign_keys = conn.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]

            self.result["database"].update(
                {
                    "connection": "OK",
                    "journal_mode": journal_mode,
                    "foreign_keys": bool(foreign_keys),
                }
            )

            if not foreign_keys:
                self.result["warnings"].append(
                    "SQLite foreign_keys pragma is OFF"
                )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Database connection failed: {e}"
            )

    # ========================================================
    # SCHEMA
    # ========================================================

    def check_schema(self):

        try:

            conn = self._connection()

            tables = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                ORDER BY name
                """
            ).fetchall()

            table_names = [
                row["name"]
                for row in tables
            ]

            missing = [
                table
                for table in REQUIRED_TABLES
                if table not in table_names
            ]

            self.result["tables"] = {
                "total": len(table_names),
                "names": table_names,
                "missing_required": missing,
            }

            if missing:

                self.result["issues"].append(
                    "Missing required tables: "
                    + ", ".join(missing)
                )

            # schema_migrations
            if "schema_migrations" in table_names:

                rows = conn.execute(
                    """
                    SELECT *
                    FROM schema_migrations
                    ORDER BY id DESC
                    LIMIT 5
                    """
                ).fetchall()

                migrations = [
                    _row_to_dict(row)
                    for row in rows
                ]

                self.result["schema"][
                    "recent_migrations"
                ] = migrations

                latest = (
                    migrations[0]
                    if migrations
                    else None
                )

                if latest:

                    version = latest.get(
                        "version"
                    )

                    self.result["schema"][
                        "version"
                    ] = version

                    if str(version) != "12.1":

                        self.result["warnings"].append(
                            "Latest schema migration "
                            f"is {version}, expected 12.1"
                        )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Schema check failed: {e}"
            )

    # ========================================================
    # TEAMS
    # ========================================================

    def check_teams(self):

        try:

            conn = self._connection()

            rows = conn.execute(
                """
                SELECT
                    id,
                    name,
                    league,
                    country
                FROM teams
                WHERE league = ?
                ORDER BY name
                """,
                (EXPECTED_LEAGUE,),
            ).fetchall()

            teams = [
                _row_to_dict(row)
                for row in rows
            ]

            names = [
                team["name"]
                for team in teams
            ]

            duplicates = [
                name
                for name in set(names)
                if names.count(name) > 1
            ]

            self.result["teams"] = {
                "count": len(teams),
                "expected": EXPECTED_TEAMS,
                "teams": teams,
                "duplicates": duplicates,
            }

            if len(teams) != EXPECTED_TEAMS:

                self.result["issues"].append(
                    "RPL team count is "
                    f"{len(teams)}, expected "
                    f"{EXPECTED_TEAMS}"
                )

            if duplicates:

                self.result["issues"].append(
                    "Duplicate team names: "
                    + ", ".join(duplicates)
                )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Team check failed: {e}"
            )

    # ========================================================
    # SEASONS
    # ========================================================

    def check_seasons(self):

        try:

            conn = self._connection()

            rows = conn.execute(
                """
                SELECT *
                FROM seasons
                ORDER BY id
                """
            ).fetchall()

            seasons = [
                _row_to_dict(row)
                for row in rows
            ]

            expected = [
                season
                for season in seasons
                if season.get("league") == EXPECTED_LEAGUE
                and season.get("year") == EXPECTED_SEASON
            ]

            self.result["seasons"] = {
                "count": len(seasons),
                "all": seasons,
                "expected_matches": expected,
            }

            if not expected:

                self.result["issues"].append(
                    "Expected RPL season "
                    f"{EXPECTED_SEASON} not found"
                )

            if len(expected) > 1:

                self.result["issues"].append(
                    "Duplicate expected seasons found"
                )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Season check failed: {e}"
            )

    # ========================================================
    # ROUNDS
    # ========================================================

    def check_rounds(self):

        try:

            conn = self._connection()

            season_rows = conn.execute(
                """
                SELECT id
                FROM seasons
                WHERE league = ?
                  AND year = ?
                """,
                (
                    EXPECTED_LEAGUE,
                    EXPECTED_SEASON,
                ),
            ).fetchall()

            season_ids = [
                row["id"]
                for row in season_rows
            ]

            if not season_ids:

                self.result["rounds"] = {
                    "count": 0,
                    "expected": EXPECTED_ROUNDS,
                }

                return

            placeholders = ",".join(
                "?" for _ in season_ids
            )

            rows = conn.execute(
                f"""
                SELECT *
                FROM rounds
                WHERE season_id IN ({placeholders})
                ORDER BY round_number
                """,
                season_ids,
            ).fetchall()

            rounds = [
                _row_to_dict(row)
                for row in rows
            ]

            numbers = [
                row.get("round_number")
                for row in rounds
            ]

            missing = [
                number
                for number in range(
                    1,
                    EXPECTED_ROUNDS + 1
                )
                if number not in numbers
            ]

            duplicates = [
                number
                for number in set(numbers)
                if numbers.count(number) > 1
            ]

            self.result["rounds"] = {
                "count": len(rounds),
                "expected": EXPECTED_ROUNDS,
                "missing": missing,
                "duplicates": duplicates,
            }

            if missing:

                self.result["issues"].append(
                    "Missing rounds: "
                    + ", ".join(
                        map(str, missing)
                    )
                )

            if duplicates:

                self.result["issues"].append(
                    "Duplicate round numbers: "
                    + ", ".join(
                        map(str, duplicates)
                    )
                )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Round check failed: {e}"
            )

    # ========================================================
    # PASSPORTS
    # ========================================================

    def check_passports(self):

        try:

            conn = self._connection()

            rows = conn.execute(
                """
                SELECT
                    p.*,
                    t.name AS team_name,
                    s.year AS season_year,
                    s.league AS season_league
                FROM team_passports p
                LEFT JOIN teams t
                    ON t.id = p.team_id
                LEFT JOIN seasons s
                    ON s.id = p.season_id
                WHERE s.league = ?
                  AND s.year = ?
                ORDER BY t.name, p.id
                """,
                (
                    EXPECTED_LEAGUE,
                    EXPECTED_SEASON,
                ),
            ).fetchall()

            passports = [
                _row_to_dict(row)
                for row in rows
            ]

            team_ids = set()

            for passport in passports:

                team_id = passport.get(
                    "team_id"
                )

                if team_id is not None:
                    team_ids.add(team_id)

            teams = conn.execute(
                """
                SELECT id, name
                FROM teams
                WHERE league = ?
                """,
                (EXPECTED_LEAGUE,),
            ).fetchall()

            team_map = {
                row["id"]: row["name"]
                for row in teams
            }

            missing_passport_teams = [
                name
                for team_id, name
                in team_map.items()
                if team_id not in team_ids
            ]

            versions = {}

            for passport in passports:

                team_name = passport.get(
                    "team_name",
                    "UNKNOWN"
                )

                version = passport.get(
                    "version",
                    "UNKNOWN"
                )

                key = (
                    team_name,
                    version,
                )

                versions[key] = (
                    versions.get(key, 0) + 1
                )

            duplicate_versions = [
                {
                    "team": key[0],
                    "version": key[1],
                    "count": count,
                }
                for key, count
                in versions.items()
                if count > 1
            ]

            # Current passport = highest version per team
            current_by_team = {}

            for passport in passports:

                team_name = passport.get(
                    "team_name"
                )

                if not team_name:
                    continue

                current = current_by_team.get(
                    team_name
                )

                if current is None:
                    current_by_team[
                        team_name
                    ] = passport
                    continue

                if str(
                    passport.get("created_at", "")
                ) > str(
                    current.get("created_at", "")
                ):
                    current_by_team[
                        team_name
                    ] = passport

            missing_fields = []

            for passport in passports:

                for field in PASSPORT_FIELDS:

                    if field not in passport:

                        missing_fields.append(
                            {
                                "team": passport.get(
                                    "team_name"
                                ),
                                "field": field,
                            }
                        )

            self.result["passports"] = {
                "count": len(passports),
                "teams_with_passports": len(team_ids),
                "expected_teams": EXPECTED_TEAMS,
                "missing_teams": missing_passport_teams,
                "duplicate_versions":
                    duplicate_versions,
                "records": passports,
                "current_by_team":
                    current_by_team,
                "missing_fields":
                    missing_fields,
            }

            if len(team_ids) != EXPECTED_TEAMS:

                self.result["issues"].append(
                    "Not every RPL team has a passport"
                )

            if duplicate_versions:

                self.result["warnings"].append(
                    "Duplicate passport versions detected"
                )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Passport check failed: {e}"
            )

    # ========================================================
    # LEGACY TABLES
    # ========================================================

    def check_legacy(self):

        try:

            conn = self._connection()

            for table in LEGACY_TABLES:

                count = _safe_count(
                    conn,
                    table,
                )

                self.result["legacy"][
                    table
                ] = {
                    "count": count,
                    "expected_minimum":
                        EXPECTED_TEAMS,
                }

                if count < EXPECTED_TEAMS:

                    self.result["warnings"].append(
                        f"{table}: "
                        f"{count} records, "
                        f"expected at least "
                        f"{EXPECTED_TEAMS}"
                    )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Legacy layer check failed: {e}"
            )

    # ========================================================
    # ORPHAN / FK CHECK
    # ========================================================

    def check_integrity(self):

        try:

            conn = self._connection()

            fk_result = conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            foreign_key_errors = [
                tuple(row)
                for row in fk_result
            ]

            orphan_queries = {
                "team_base": """
                    SELECT COUNT(*)
                    FROM team_base tb
                    LEFT JOIN teams t
                        ON t.id = tb.team_id
                    WHERE t.id IS NULL
                """,

                "team_dynamic": """
                    SELECT COUNT(*)
                    FROM team_dynamic td
                    LEFT JOIN teams t
                        ON t.id = td.team_id
                    WHERE t.id IS NULL
                """,

                "team_identity": """
                    SELECT COUNT(*)
                    FROM team_identity ti
                    LEFT JOIN teams t
                        ON t.id = ti.team_id
                    WHERE t.id IS NULL
                """,

                "team_passports": """
                    SELECT COUNT(*)
                    FROM team_passports tp
                    LEFT JOIN teams t
                        ON t.id = tp.team_id
                    WHERE t.id IS NULL
                """,
            }

            orphan_counts = {}

            for name, query in orphan_queries.items():

                try:

                    row = conn.execute(
                        query
                    ).fetchone()

                    orphan_counts[name] = (
                        int(row[0])
                        if row
                        else 0
                    )

                except Exception as e:

                    orphan_counts[name] = (
                        f"ERROR: {e}"
                    )

            self.result["integrity"] = {
                "foreign_key_errors":
                    foreign_key_errors,
                "orphan_counts":
                    orphan_counts,
            }

            if foreign_key_errors:

                self.result["issues"].append(
                    "SQLite foreign_key_check "
                    "reported errors"
                )

            for table, count in orphan_counts.items():

                if isinstance(count, int) and count > 0:

                    self.result["issues"].append(
                        f"{table}: {count} orphan records"
                    )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Integrity check failed: {e}"
            )

    # ========================================================
    # DATA COUNTS
    # ========================================================

    def check_data_counts(self):

        tables = [
            "matches",
            "match_results",
            "match_statistics",
            "match_predictions",
            "predictions",
            "prediction_scores",
            "prediction_distributions",
            "prediction_validation",
            "expert_predictions",
            "gold_dataset",
            "learning_records",
            "learning_events",
            "audit_log",
            "learning_memory",
            "xg_memory",
            "match_snapshots",
            "players",
            "player_events",
        ]

        try:

            conn = self._connection()

            for table in tables:

                if _table_exists(
                    conn,
                    table
                ):

                    self.result["data_counts"][
                        table
                    ] = _safe_count(
                        conn,
                        table,
                    )

            conn.close()

        except Exception as e:

            self.result["issues"].append(
                f"Data count check failed: {e}"
            )

    # ========================================================
    # FINAL STATUS
    # ========================================================

    def finalize(self):

        issues = self.result["issues"]
        warnings = self.result["warnings"]

        if issues:

            self.result["status"] = "ERROR"

        elif warnings:

            self.result["status"] = "WARNING"

        else:

            self.result["status"] = "HEALTHY"

        return self.result

    # ========================================================
    # RUN
    # ========================================================

    def run(self):

        logger.info(
            "🔍 Starting FAJ database diagnostic..."
        )

        self.check_database()
        self.check_schema()
        self.check_teams()
        self.check_seasons()
        self.check_rounds()
        self.check_passports()
        self.check_legacy()
        self.check_integrity()
        self.check_data_counts()

        result = self.finalize()

        logger.info(
            "🔍 Database diagnostic completed: %s",
            result["status"],
        )

        return result


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def run_database_diagnostic() -> dict:
    """
    Публичная функция для Streamlit / других модулей.
    """

    diagnostic = DatabaseDiagnostic()

    return diagnostic.run()


# ============================================================
# DIRECT RUN
# ============================================================

if __name__ == "__main__":

    import json

    result = run_database_diagnostic()

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
