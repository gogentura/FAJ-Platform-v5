#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — FAJ DATA AUDIT v1.1
============================================================

НАЗНАЧЕНИЕ
-----------

Безопасный диагностический аудит FAJ перед созданием
полноценного Evolution Report.

ВАЖНО:
    - ТОЛЬКО READ-ONLY
    - НЕ INSERT
    - НЕ UPDATE
    - НЕ DELETE
    - НЕ ALTER
    - НЕ DROP
    - НЕ изменяет faj.db

Проверяет:

    1. Реальную схему SQLite
    2. Наличие критических таблиц
    3. Количество записей
    4. Колонки
    5. Прогнозы
    6. Факты
    7. xG
    8. prediction scores
    9. Learning Memory
   10. Model Parameters
   11. Match Snapshots
   12. Связи MATCH → PREDICTION → RESULT
   13. Возможность восстановления жизненного цикла матча
   14. Возможность построения League Trends
   15. Возможность Prediction Evolution
   16. Возможность Model Evolution

============================================================
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# PATH
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

DB_PATH = ROOT / "data" / "faj.db"


# ============================================================
# HELPERS
# ============================================================

def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "—") -> str:
    if value is None:
        return default

    value = str(value).strip()

    return value if value else default


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def subsection(title: str) -> None:
    print()
    print("-" * 70)
    print(title)
    print("-" * 70)


def status(ok: bool, yes: str = "OK", no: str = "MISSING") -> None:
    print(f"    {'✅' if ok else '❌'} {yes if ok else no}")


# ============================================================
# AUDIT
# ============================================================

class FAJDataAudit:

    def __init__(self, db_path: Path = DB_PATH):

        self.db_path = Path(db_path)

        self.conn: Optional[sqlite3.Connection] = None

        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "database": str(self.db_path),
            "tables": {},
            "capabilities": {},
            "links": {},
            "sample_matches": [],
            "issues": [],
        }

    # ========================================================
    # CONNECTION
    # ========================================================

    def connect(self) -> None:

        if not self.db_path.exists():

            raise FileNotFoundError(
                f"SQLite database not found: {self.db_path}"
            )

        self.conn = sqlite3.connect(
            str(self.db_path)
        )

        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:

        if self.conn:
            self.conn.close()

            self.conn = None

    # ========================================================
    # BASIC SQL
    # ========================================================

    def execute(
        self,
        sql: str,
        params: tuple = (),
    ):

        if not self.conn:
            raise RuntimeError("Database is not connected")

        return self.conn.execute(sql, params)

    # ========================================================
    # TABLES
    # ========================================================

    def get_tables(self) -> List[str]:

        rows = self.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        return [row["name"] for row in rows]

    def table_exists(self, table: str) -> bool:

        return table in self.get_tables()

    def get_columns(self, table: str) -> List[str]:

        if not self.table_exists(table):
            return []

        rows = self.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        return [row["name"] for row in rows]

    def count(self, table: str) -> int:

        if not self.table_exists(table):
            return 0

        row = self.execute(
            f"SELECT COUNT(*) AS n FROM {table}"
        ).fetchone()

        return safe_int(row["n"])

    # ========================================================
    # 1. SCHEMA
    # ========================================================

    def audit_schema(self) -> None:

        section("1. REAL SQLITE SCHEMA")

        tables = self.get_tables()

        print(f"\nDatabase: {self.db_path}")
        print(f"Tables:   {len(tables)}")

        for table in tables:

            columns = self.get_columns(table)
            rows = self.count(table)

            self.results["tables"][table] = {
                "rows": rows,
                "columns": columns,
            }

            print(
                f"\n  📦 {table}"
                f"\n     rows={rows}"
                f"\n     columns={len(columns)}"
            )

            print(
                "     "
                + ", ".join(columns)
            )

    # ========================================================
    # 2. CRITICAL TABLES
    # ========================================================

    def audit_critical_tables(self) -> None:

        section("2. CRITICAL FAJ TABLES")

        critical = [
            "teams",
            "seasons",
            "rounds",
            "matches",
            "match_results",
            "predictions",
            "prediction_scores",
            "learning_memory",
            "model_parameters",
            "match_snapshots",
            "team_passports",
            "team_history",
        ]

        for table in critical:

            exists = self.table_exists(table)

            rows = self.count(table) if exists else 0

            print(
                f"  {'✅' if exists else '❌'} "
                f"{table}: "
                f"{rows} rows"
            )

    # ========================================================
    # 3. PREDICTIONS
    # ========================================================

    def audit_predictions(self) -> None:

        section("3. PREDICTION DATA")

        if not self.table_exists("predictions"):

            print("  ❌ predictions does not exist")

            self.results["capabilities"]["prediction"] = False

            return

        columns = self.get_columns("predictions")
        rows = self.count("predictions")

        print(f"  Rows: {rows}")

        useful = [
            "id",
            "match_id",
            "model_version",
            "created_at",
            "home_xg",
            "away_xg",
            "home_win",
            "draw",
            "away_win",
            "predicted_home_goals",
            "predicted_away_goals",
        ]

        found = []

        for column in useful:

            if column in columns:

                found.append(column)

                print(f"  ✅ {column}")

            else:

                print(f"  ⚪ {column}")

        enough = (
            "match_id" in columns
            and rows > 0
        )

        self.results["capabilities"]["prediction"] = enough

        if enough:

            print("\n  ✅ Prediction history exists")

        else:

            print("\n  ❌ Prediction history insufficient")

    # ========================================================
    # 4. PREDICTION SCORES
    # ========================================================

    def audit_prediction_scores(self) -> None:

        section("4. PREDICTION SCORES")

        if not self.table_exists("prediction_scores"):

            print("  ❌ prediction_scores does not exist")

            self.results["capabilities"]["prediction_scores"] = False

            return

        columns = self.get_columns("prediction_scores")
        rows = self.count("prediction_scores")

        print(f"  Rows: {rows}")

        for column in [
            "prediction_id",
            "score",
            "probability",
            "rank",
        ]:

            print(
                f"  {'✅' if column in columns else '⚪'} "
                f"{column}"
            )

        self.results["capabilities"]["prediction_scores"] = (
            rows > 0
            and "prediction_id" in columns
        )

    # ========================================================
    # 5. MATCH RESULTS
    # ========================================================

    def audit_results(self) -> None:

        section("5. MATCH RESULTS")

        if not self.table_exists("match_results"):

            print("  ❌ match_results does not exist")

            self.results["capabilities"]["facts"] = False

            return

        columns = self.get_columns("match_results")
        rows = self.count("match_results")

        print(f"  Rows: {rows}")

        for column in [
            "match_id",
            "home_goals",
            "away_goals",
            "home_xg",
            "away_xg",
        ]:

            print(
                f"  {'✅' if column in columns else '⚪'} "
                f"{column}"
            )

        enough = (
            rows > 0
            and "match_id" in columns
            and "home_goals" in columns
            and "away_goals" in columns
        )

        self.results["capabilities"]["facts"] = enough

        # xG
        has_xg = (
            "home_xg" in columns
            and "away_xg" in columns
        )

        self.results["capabilities"]["result_xg"] = has_xg

        if has_xg:

            row = self.execute(
                """
                SELECT COUNT(*) AS n
                FROM match_results
                WHERE home_xg IS NOT NULL
                  AND away_xg IS NOT NULL
                """
            ).fetchone()

            xg_rows = safe_int(row["n"])

            print(f"\n  xG populated rows: {xg_rows}")

    # ========================================================
    # 6. LEARNING MEMORY
    # ========================================================

    def audit_learning_memory(self) -> None:

        section("6. LEARNING MEMORY")

        if not self.table_exists("learning_memory"):

            print("  ❌ learning_memory does not exist")

            self.results["capabilities"]["learning_memory"] = False

            return

        columns = self.get_columns("learning_memory")
        rows = self.count("learning_memory")

        print(f"  Rows: {rows}")

        for column in [
            "id",
            "event_type",
            "reference_id",
            "feature",
            "before_value",
            "after_value",
            "delta",
            "created_at",
        ]:

            print(
                f"  {'✅' if column in columns else '⚪'} "
                f"{column}"
            )

        if "event_type" in columns:

            rows_by_type = self.execute(
                """
                SELECT event_type, COUNT(*) AS n
                FROM learning_memory
                GROUP BY event_type
                ORDER BY n DESC
                """
            ).fetchall()

            print("\n  Event types:")

            for row in rows_by_type:

                print(
                    f"    • "
                    f"{safe_str(row['event_type'])}: "
                    f"{row['n']}"
                )

        self.results["capabilities"]["learning_memory"] = (
            rows > 0
        )

    # ========================================================
    # 7. MODEL PARAMETERS
    # ========================================================

    def audit_model_parameters(self) -> None:

        section("7. MODEL PARAMETERS")

        if not self.table_exists("model_parameters"):

            print("  ❌ model_parameters does not exist")

            self.results["capabilities"]["model_history"] = False

            return

        columns = self.get_columns("model_parameters")
        rows = self.count("model_parameters")

        print(f"  Rows: {rows}")

        for column in [
            "id",
            "version",
            "parameters",
            "created_at",
        ]:

            print(
                f"  {'✅' if column in columns else '⚪'} "
                f"{column}"
            )

        versions = 0

        if "version" in columns:

            row = self.execute(
                """
                SELECT COUNT(DISTINCT version) AS n
                FROM model_parameters
                """
            ).fetchone()

            versions = safe_int(row["n"])

        print(f"\n  Model versions: {versions}")

        self.results["capabilities"]["model_history"] = (
            versions >= 2
        )

    # ========================================================
    # 8. SNAPSHOTS
    # ========================================================

    def audit_snapshots(self) -> None:

        section("8. MATCH SNAPSHOTS")

        if not self.table_exists("match_snapshots"):

            print("  ❌ match_snapshots does not exist")

            self.results["capabilities"]["snapshots"] = False

            return

        rows = self.count("match_snapshots")

        columns = self.get_columns("match_snapshots")

        print(f"  Rows: {rows}")

        for column in [
            "match_id",
            "snapshot_type",
            "data",
            "created_at",
        ]:

            print(
                f"  {'✅' if column in columns else '⚪'} "
                f"{column}"
            )

        self.results["capabilities"]["snapshots"] = (
            rows > 0
        )

    # ========================================================
    # 9. MATCH → PREDICTION → RESULT
    # ========================================================

    def audit_match_lifecycle(self) -> None:

        section("9. MATCH LIFECYCLE")

        if not (
            self.table_exists("matches")
            and self.table_exists("predictions")
            and self.table_exists("match_results")
        ):

            print("  ❌ Required tables are missing")

            self.results["capabilities"]["match_lifecycle"] = False

            return

        mc = self.get_columns("matches")
        pc = self.get_columns("predictions")
        rc = self.get_columns("match_results")

        if (
            "id" not in mc
            or "match_id" not in pc
            or "match_id" not in rc
        ):

            print("  ❌ Required ID fields are missing")

            self.results["capabilities"]["match_lifecycle"] = False

            return

        total_matches = self.count("matches")

        predictions = self.count("predictions")

        results = self.count("match_results")

        linked_predictions = self.execute(
            """
            SELECT COUNT(DISTINCT m.id) AS n
            FROM matches m
            JOIN predictions p
              ON p.match_id = m.id
            """
        ).fetchone()["n"]

        linked_results = self.execute(
            """
            SELECT COUNT(DISTINCT m.id) AS n
            FROM matches m
            JOIN match_results r
              ON r.match_id = m.id
            """
        ).fetchone()["n"]

        fully_linked = self.execute(
            """
            SELECT COUNT(DISTINCT m.id) AS n
            FROM matches m
            JOIN predictions p
              ON p.match_id = m.id
            JOIN match_results r
              ON r.match_id = m.id
            """
        ).fetchone()["n"]

        print(f"  Matches:              {total_matches}")
        print(f"  Predictions:          {predictions}")
        print(f"  Results:              {results}")
        print(f"  Matches + prediction: {linked_predictions}")
        print(f"  Matches + result:     {linked_results}")
        print(f"  FULL LIFECYCLE:       {fully_linked}")

        self.results["links"]["matches_predictions"] = safe_int(
            linked_predictions
        )

        self.results["links"]["matches_results"] = safe_int(
            linked_results
        )

        self.results["links"]["full_lifecycle"] = safe_int(
            fully_linked
        )

        self.results["capabilities"]["match_lifecycle"] = (
            fully_linked > 0
        )

    # ========================================================
    # 10. SAMPLE MATCHES
    # ========================================================

    def audit_sample_matches(self) -> None:

        section("10. REAL MATCH SAMPLE")

        if not (
            self.table_exists("matches")
            and self.table_exists("predictions")
            and self.table_exists("match_results")
        ):

            print("  ❌ Cannot build sample")

            return

        mc = self.get_columns("matches")

        home_field = (
            "home_team_id"
            if "home_team_id" in mc
            else None
        )

        away_field = (
            "away_team_id"
            if "away_team_id" in mc
            else None
        )

        if not home_field or not away_field:

            print(
                "  ⚠️ Team ID fields not found in matches"
            )

            return

        rows = self.execute(
            f"""
            SELECT
                m.id AS match_id,
                m.{home_field} AS home_team_id,
                m.{away_field} AS away_team_id,
                p.id AS prediction_id,
                r.home_goals,
                r.away_goals
            FROM matches m

            LEFT JOIN predictions p
              ON p.match_id = m.id

            LEFT JOIN match_results r
              ON r.match_id = m.id

            WHERE r.home_goals IS NOT NULL
              AND r.away_goals IS NOT NULL

            ORDER BY m.id DESC

            LIMIT 10
            """
        ).fetchall()

        if not rows:

            print("  ❌ No completed matches with lifecycle")

            return

        for row in rows:

            item = {
                "match_id": row["match_id"],
                "home_team_id": row["home_team_id"],
                "away_team_id": row["away_team_id"],
                "prediction_id": row["prediction_id"],
                "actual_score": (
                    f"{row['home_goals']}:"
                    f"{row['away_goals']}"
                ),
            }

            self.results["sample_matches"].append(item)

            print(
                f"  MATCH {row['match_id']}: "
                f"{row['home_team_id']} - "
                f"{row['away_team_id']} | "
                f"prediction={row['prediction_id']} | "
                f"actual={item['actual_score']}"
            )

    # ========================================================
    # 11. LEAGUE TRENDS
    # ========================================================

    def audit_league_trends(self) -> None:

        section("11. LEAGUE TRENDS CAPABILITY")

        if not self.table_exists("match_results"):

            print("  ❌ No match_results")

            self.results["capabilities"]["league_trends"] = False

            return

        columns = self.get_columns("match_results")

        required = [
            "home_goals",
            "away_goals",
        ]

        if not all(
            field in columns
            for field in required
        ):

            print("  ❌ Goal data insufficient")

            self.results["capabilities"]["league_trends"] = False

            return

        row = self.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN away_goals >= 1 THEN 1 ELSE 0 END) AS away_1plus,
                SUM(CASE WHEN away_goals >= 2 THEN 1 ELSE 0 END) AS away_2plus,
                SUM(CASE WHEN away_goals >= 3 THEN 1 ELSE 0 END) AS away_3plus,
                SUM(CASE WHEN away_goals = 0 THEN 1 ELSE 0 END) AS away_zero,
                SUM(CASE WHEN home_goals >= 2 THEN 1 ELSE 0 END) AS home_2plus
            FROM match_results
            WHERE home_goals IS NOT NULL
              AND away_goals IS NOT NULL
            """
        ).fetchone()

        total = safe_int(row["total"])

        print(f"  Completed matches: {total}")

        if total:

            metrics = {
                "away_1plus": row["away_1plus"],
                "away_2plus": row["away_2plus"],
                "away_3plus": row["away_3plus"],
                "away_zero": row["away_zero"],
                "home_2plus": row["home_2plus"],
            }

            for name, value in metrics.items():

                rate = safe_int(value) / total

                print(
                    f"  • {name}: "
                    f"{safe_int(value)}/{total} "
                    f"({rate:.1%})"
                )

            self.results["capabilities"]["league_trends"] = True

        else:

            self.results["capabilities"]["league_trends"] = False

    # ========================================================
    # 12. EVOLUTION CAPABILITY
    # ========================================================

    def audit_evolution_capabilities(self) -> None:

        section("12. EVOLUTION REPORT CAPABILITIES")

        capabilities = {

            "League Trends":
                self.results["capabilities"].get(
                    "league_trends", False
                ),

            "Prediction History":
                self.results["capabilities"].get(
                    "prediction", False
                ),

            "Prediction Scores":
                self.results["capabilities"].get(
                    "prediction_scores", False
                ),

            "Actual Facts":
                self.results["capabilities"].get(
                    "facts", False
                ),

            "Result xG":
                self.results["capabilities"].get(
                    "result_xg", False
                ),

            "Learning Memory":
                self.results["capabilities"].get(
                    "learning_memory", False
                ),

            "Model History":
                self.results["capabilities"].get(
                    "model_history", False
                ),

            "Match Snapshots":
                self.results["capabilities"].get(
                    "snapshots", False
                ),

            "Full Match Lifecycle":
                self.results["capabilities"].get(
                    "match_lifecycle", False
                ),
        }

        for name, value in capabilities.items():

            print(
                f"  {'✅' if value else '❌'} "
                f"{name}"
            )

        missing = [
            name
            for name, value in capabilities.items()
            if not value
        ]

        self.results["missing_capabilities"] = missing

    # ========================================================
    # 13. FINAL
    # ========================================================

    def summary(self) -> None:

        section("13. FINAL AUDIT")

        missing = self.results.get(
            "missing_capabilities",
            []
        )

        if not missing:

            print(
                "  ✅ FAJ имеет необходимые данные "
                "для построения Evolution Report."
            )

        else:

            print(
                "  ⚠️ Evolution Report пока "
                "нельзя строить полностью."
            )

            print("\n  Не хватает:")

            for item in missing:

                print(f"    • {item}")

        print("\n  ВАЖНО:")

        print(
            "    Этот аудит НЕ изменяет базу данных."
        )

        print(
            "    Следующий этап — анализ конкретных "
            "недостающих данных."
        )

    # ========================================================
    # RUN
    # ========================================================

    def run(self) -> Dict[str, Any]:

        try:

            self.connect()

            print()
            print("=" * 78)
            print("FAJ PLATFORM v12.1")
            print("ETC — DATA AUDIT v1.1")
            print("=" * 78)

            print(
                f"\nDatabase: {self.db_path}"
            )

            self.audit_schema()
            self.audit_critical_tables()
            self.audit_predictions()
            self.audit_prediction_scores()
            self.audit_results()
            self.audit_learning_memory()
            self.audit_model_parameters()
            self.audit_snapshots()
            self.audit_match_lifecycle()
            self.audit_sample_matches()
            self.audit_league_trends()
            self.audit_evolution_capabilities()
            self.summary()

            return self.results

        finally:

            self.close()


# ============================================================
# MAIN
# ============================================================

def main():

    audit = FAJDataAudit()

    try:

        result = audit.run()

        print("\n" + "=" * 78)
        print("AUDIT FINISHED")
        print("=" * 78)

        print(
            "\nJSON SUMMARY:"
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    except Exception as exc:

        print(
            f"\n❌ AUDIT ERROR: {exc}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
