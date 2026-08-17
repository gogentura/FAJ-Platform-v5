#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Learning Engine

Пакетное обучение на завершённых матчах.

ВАЖНО:
- результаты матчей только читаются;
- DELETE отсутствует;
- календарь не изменяется;
- прогнозы не создаются;
- обучение атомарно;
- повторный запуск того же массива без force
  не создаёт новый цикл обучения;
- force=True разрешает сознательный повторный цикл.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


ENGINE_VERSION = "12.1"
ENGINE_NAME = "FAJ Learning Engine"

# app/learning_engine.py -> корень проекта
ROOT_DIR = Path(__file__).resolve().parents[1]

DEFAULT_DB_PATH = ROOT_DIR / "data" / "faj.db"

MIN_MATCHES_FOR_LEARNING = 8
MIN_PATTERN_OCCURRENCES = 2

MAX_PARAMETER_STEP = 0.03

PATTERN_WEIGHT = 1.0


DEFAULT_PARAMETERS: Dict[str, float] = {
    "attack": 0.18,
    "defense": 0.18,
    "control": 0.15,
    "efficiency": 0.12,
    "mentality": 0.10,
    "tempo": 0.07,
    "press": 0.05,
    "transition": 0.05,
    "flexibility": 0.05,
    "coach": 0.05,
}


def _now() -> str:
    return datetime.now().isoformat()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:

    return max(
        minimum,
        min(maximum, value),
    )


def _pattern_strength(
    difference: float,
) -> float:

    return _clamp(
        abs(_safe_float(difference)),
        0.0,
        1.0,
    )


class LearningEngine:

    def __init__(
        self,
        db_path: Optional[str] = None,
    ) -> None:

        self.db_path = (
            Path(db_path)
            if db_path
            else DEFAULT_DB_PATH
        )

        self.run_id = (
            f"learning-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

    # ========================================================
    # PUBLIC
    # ========================================================

    def run(
        self,
        force: bool = False,
    ) -> Dict[str, Any]:

        result = {
            "success": False,
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "run_id": self.run_id,
            "started_at": _now(),
            "finished_at": None,
            "matches_analyzed": 0,
            "teams_analyzed": 0,
            "patterns_found": 0,
            "predictions_analyzed": 0,
            "parameters_changed": 0,
            "patterns": [],
            "parameter_changes": [],
            "errors": [],
            "skipped": False,
            "skip_reason": None,
        }

        if not self.db_path.exists():

            result["errors"].append(
                f"База данных не найдена: "
                f"{self.db_path}"
            )

            return result

        conn = sqlite3.connect(
            str(self.db_path)
        )

        conn.row_factory = sqlite3.Row

        try:

            matches = self._get_finished_matches(
                conn
            )

            result["matches_analyzed"] = len(
                matches
            )

            if (
                len(matches) < MIN_MATCHES_FOR_LEARNING
                and not force
            ):

                result["errors"].append(
                    "Недостаточно завершённых матчей "
                    f"для обучения: "
                    f"{len(matches)}/"
                    f"{MIN_MATCHES_FOR_LEARNING}"
                )

                return result

            # ------------------------------------------------
            # Защита от повторного обучения того же массива.
            # ------------------------------------------------

            if not force:

                fingerprint = self._dataset_fingerprint(
                    matches
                )

                if self._was_dataset_already_learned(
                    conn,
                    fingerprint,
                ):

                    result["success"] = True
                    result["skipped"] = True
                    result["skip_reason"] = (
                        "Этот набор завершённых матчей "
                        "уже использовался для обучения."
                    )
                    result["finished_at"] = _now()

                    return result

            # ------------------------------------------------
            # TEAM STATS
            # ------------------------------------------------

            team_stats = self._build_team_statistics(
                matches
            )

            result["teams_analyzed"] = len(
                team_stats
            )

            # ------------------------------------------------
            # PATTERNS
            # ------------------------------------------------

            patterns = self._find_patterns(
                matches,
                team_stats,
            )

            # ------------------------------------------------
            # PREDICTIONS
            # ------------------------------------------------

            predictions = self._get_prediction_accuracy(
                conn
            )

            result["predictions_analyzed"] = len(
                predictions
            )

            prediction_patterns = (
                self._analyze_prediction_errors(
                    predictions
                )
            )

            patterns.extend(
                prediction_patterns
            )

            result["patterns"] = patterns
            result["patterns_found"] = len(
                patterns
            )

            # ------------------------------------------------
            # PARAMETERS
            # ------------------------------------------------

            parameters = self._load_parameters(
                conn
            )

            new_parameters, changes = (
                self._adjust_parameters(
                    parameters,
                    patterns,
                )
            )

            result["parameter_changes"] = changes
            result["parameters_changed"] = len(
                changes
            )

            # ------------------------------------------------
            # SAVE
            # ------------------------------------------------

            fingerprint = self._dataset_fingerprint(
                matches
            )

            self._save_learning_memory(
                conn,
                matches,
                patterns,
                changes,
                fingerprint,
            )

            self._save_model_parameters(
                conn,
                new_parameters,
            )

            conn.commit()

            result["success"] = True
            result["finished_at"] = _now()

            logger.info(
                "FAJ Learning completed: "
                "matches=%s patterns=%s changes=%s",
                len(matches),
                len(patterns),
                len(changes),
            )

            return result

        except Exception as exc:

            conn.rollback()

            logger.exception(
                "FAJ Learning Engine error"
            )

            result["errors"].append(
                str(exc)
            )

            result["finished_at"] = _now()

            return result

        finally:
            conn.close()

    # ========================================================
    # DATASET FINGERPRINT
    # ========================================================

    @staticmethod
    def _dataset_fingerprint(
        matches: List[Dict[str, Any]],
    ) -> str:

        rows = []

        for match in matches:

            rows.append({
                "id": match.get("id"),
                "home": match.get("home_team_id"),
                "away": match.get("away_team_id"),
                "hg": match.get("result_home_goals"),
                "ag": match.get("result_away_goals"),
            })

        encoded = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
        )

        import hashlib

        return hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest()

    def _was_dataset_already_learned(
        self,
        conn: sqlite3.Connection,
        fingerprint: str,
    ) -> bool:

        if "learning_memory" not in self._tables(
            conn
        ):
            return False

        columns = self._columns(
            conn,
            "learning_memory",
        )

        # Ищем fingerprint в content/data.
        search_columns = [
            column
            for column in ("content", "data")
            if column in columns
        ]

        if not search_columns:
            return False

        cursor = conn.cursor()

        for column in search_columns:

            cursor.execute(
                f"""
                SELECT 1
                FROM learning_memory
                WHERE {column} LIKE ?
                LIMIT 1
                """,
                (f"%{fingerprint}%",),
            )

            if cursor.fetchone():
                return True

        return False

    # ========================================================
    # FINISHED MATCHES
    # ========================================================

    def _get_finished_matches(
        self,
        conn: sqlite3.Connection,
    ) -> List[Dict[str, Any]]:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                m.*,

                ht.name AS home_team,
                at.name AS away_team,

                mr.home_goals AS result_home_goals,
                mr.away_goals AS result_away_goals

            FROM matches m

            LEFT JOIN teams ht
                ON ht.id = m.home_team_id

            LEFT JOIN teams at
                ON at.id = m.away_team_id

            INNER JOIN match_results mr
                ON mr.match_id = m.id

            WHERE
                mr.home_goals IS NOT NULL
                AND mr.away_goals IS NOT NULL

            ORDER BY
                datetime(m.date) ASC,
                m.id ASC
            """
        )

        return [
            dict(row)
            for row in cursor.fetchall()
        ]

    # ========================================================
    # TEAM STATS
    # ========================================================

    def _build_team_statistics(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:

        stats = {}

        for match in matches:

            home = match.get("home_team")
            away = match.get("away_team")

            if not home or not away:
                continue

            hg = _safe_int(
                match.get("result_home_goals")
            )

            ag = _safe_int(
                match.get("result_away_goals")
            )

            if home not in stats:
                stats[home] = self._empty_team_stats(
                    home
                )

            if away not in stats:
                stats[away] = self._empty_team_stats(
                    away
                )

            h = stats[home]
            a = stats[away]

            h["matches"] += 1
            a["matches"] += 1

            h["goals_for"] += hg
            h["goals_against"] += ag

            a["goals_for"] += ag
            a["goals_against"] += hg

            if hg > ag:

                h["wins"] += 1
                a["losses"] += 1

            elif hg < ag:

                h["losses"] += 1
                a["wins"] += 1

            else:

                h["draws"] += 1
                a["draws"] += 1

            if hg == 0:
                a["clean_sheets"] += 1

            if ag == 0:
                h["clean_sheets"] += 1

            h["points"] += (
                3 if hg > ag
                else 1 if hg == ag
                else 0
            )

            a["points"] += (
                3 if ag > hg
                else 1 if ag == hg
                else 0
            )

            total = hg + ag

            h["total_goals_in_matches"] += total
            a["total_goals_in_matches"] += total

        for data in stats.values():

            games = max(
                1,
                data["matches"],
            )

            data["goals_for_avg"] = (
                data["goals_for"] / games
            )

            data["goals_against_avg"] = (
                data["goals_against"] / games
            )

            data["win_rate"] = (
                data["wins"] / games
            )

            data["draw_rate"] = (
                data["draws"] / games
            )

            data["loss_rate"] = (
                data["losses"] / games
            )

            data["clean_sheet_rate"] = (
                data["clean_sheets"] / games
            )

            data["avg_total_goals"] = (
                data["total_goals_in_matches"]
                / games
            )

        return stats

    @staticmethod
    def _empty_team_stats(
        team: str,
    ) -> Dict[str, Any]:

        return {
            "team": team,
            "matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "clean_sheets": 0,
            "total_goals_in_matches": 0,
        }

    # ========================================================
    # PATTERNS
    # ========================================================

    def _find_patterns(
        self,
        matches,
        team_stats,
    ):

        patterns = []

        if not matches:
            return patterns

        total_goals = sum(
            _safe_int(
                m.get("result_home_goals")
            )
            +
            _safe_int(
                m.get("result_away_goals")
            )
            for m in matches
        )

        avg_goals = (
            total_goals / len(matches)
        )

        if avg_goals < 2.20:

            patterns.append({
                "type": "league_low_scoring",
                "strength": _pattern_strength(
                    2.20 - avg_goals
                ),
                "occurrences": len(matches),
                "description":
                    "Пониженная результативность РПЛ.",
                "evidence": {
                    "average_goals":
                        round(avg_goals, 3),
                },
            })

        elif avg_goals > 2.80:

            patterns.append({
                "type": "league_high_scoring",
                "strength": _pattern_strength(
                    avg_goals - 2.80
                ),
                "occurrences": len(matches),
                "description":
                    "Повышенная результативность РПЛ.",
                "evidence": {
                    "average_goals":
                        round(avg_goals, 3),
                },
            })

        btts = sum(
            1
            for m in matches
            if _safe_int(
                m.get("result_home_goals")
            ) > 0
            and
            _safe_int(
                m.get("result_away_goals")
            ) > 0
        )

        btts_rate = btts / len(matches)

        if btts_rate >= 0.65:

            patterns.append({
                "type": "high_btts",
                "strength": _pattern_strength(
                    btts_rate - 0.50
                ),
                "occurrences": btts,
                "description":
                    "Повышенная частота BTTS.",
                "evidence": {
                    "btts_rate":
                        round(btts_rate, 3),
                },
            })

        elif btts_rate <= 0.35:

            patterns.append({
                "type": "low_btts",
                "strength": _pattern_strength(
                    0.50 - btts_rate
                ),
                "occurrences":
                    len(matches) - btts,
                "description":
                    "Пониженная частота BTTS.",
                "evidence": {
                    "btts_rate":
                        round(btts_rate, 3),
                },
            })

        home_wins = 0
        draws = 0
        away_wins = 0

        for m in matches:

            hg = _safe_int(
                m.get("result_home_goals")
            )

            ag = _safe_int(
                m.get("result_away_goals")
            )

            if hg > ag:
                home_wins += 1
            elif hg < ag:
                away_wins += 1
            else:
                draws += 1

        home_rate = home_wins / len(matches)
        draw_rate = draws / len(matches)

        if home_rate >= 0.50:

            patterns.append({
                "type": "home_advantage_strong",
                "strength": _pattern_strength(
                    home_rate - 0.33
                ),
                "occurrences": home_wins,
                "description":
                    "Повышенная доля домашних побед.",
                "evidence": {
                    "home_win_rate":
                        round(home_rate, 3),
                    "draw_rate":
                        round(draw_rate, 3),
                    "away_win_rate":
                        round(
                            away_wins / len(matches),
                            3,
                        ),
                },
            })

        if draw_rate >= 0.40:

            patterns.append({
                "type": "high_draw_rate",
                "strength": _pattern_strength(
                    draw_rate - 0.33
                ),
                "occurrences": draws,
                "description":
                    "Повышенная доля ничьих.",
                "evidence": {
                    "draw_rate":
                        round(draw_rate, 3),
                },
            })

        for team, stats in team_stats.items():

            if stats["matches"] < 2:
                continue

            if (
                stats["win_rate"] >= 0.75
                and
                stats["goals_for_avg"] >= 2.0
            ):

                patterns.append({
                    "type":
                        "team_attack_strength",
                    "team": team,
                    "strength":
                        _pattern_strength(
                            stats["win_rate"]
                        ),
                    "occurrences":
                        stats["matches"],
                    "description":
                        f"{team}: сильная "
                        "результативная форма.",
                })

            if (
                stats["clean_sheet_rate"] >= 0.50
                and
                stats["goals_against_avg"] <= 0.75
            ):

                patterns.append({
                    "type":
                        "team_defense_strength",
                    "team": team,
                    "strength":
                        _pattern_strength(
                            stats["clean_sheet_rate"]
                        ),
                    "occurrences":
                        stats["matches"],
                    "description":
                        f"{team}: сильная "
                        "оборонительная форма.",
                })

        return patterns

    # ========================================================
    # PREDICTIONS
    # ========================================================

    def _get_prediction_accuracy(
        self,
        conn,
    ) -> List[Dict[str, Any]]:

        if "predictions" not in self._tables(conn):
            return []

        columns = self._columns(
            conn,
            "predictions",
        )

        match_column = self._first_existing(
            columns,
            [
                "match_id",
                "fixture_id",
            ],
        )

        if not match_column:
            return []

        home_column = self._first_existing(
            columns,
            [
                "predicted_home",
                "predicted_home_goals",
                "home_score",
                "predicted_score_home",
            ],
        )

        away_column = self._first_existing(
            columns,
            [
                "predicted_away",
                "predicted_away_goals",
                "away_score",
                "predicted_score_away",
            ],
        )

        if not home_column or not away_column:
            return []

        cursor = conn.cursor()

        # КЛЮЧЕВАЯ ПРАВКА:
        # predictions -> matches -> match_results
        cursor.execute(
            f"""
            SELECT
                p.*,

                m.id AS linked_match_id,

                mr.home_goals AS actual_home,
                mr.away_goals AS actual_away

            FROM predictions p

            INNER JOIN matches m
                ON m.id = p.{match_column}

            INNER JOIN match_results mr
                ON mr.match_id = m.id

            WHERE
                p.{match_column} IS NOT NULL

                AND mr.home_goals IS NOT NULL
                AND mr.away_goals IS NOT NULL
            """
        )

        rows = []

        for row in cursor.fetchall():

            item = dict(row)

            item["_predicted_home"] = (
                item.get(home_column)
            )

            item["_predicted_away"] = (
                item.get(away_column)
            )

            rows.append(item)

        return rows

    def _analyze_prediction_errors(
        self,
        predictions,
    ):

        errors = []

        for prediction in predictions:

            ph = prediction.get(
                "_predicted_home"
            )

            pa = prediction.get(
                "_predicted_away"
            )

            ah = prediction.get(
                "actual_home"
            )

            aa = prediction.get(
                "actual_away"
            )

            if None in (ph, pa, ah, aa):
                continue

            try:
                ph = int(ph)
                pa = int(pa)
                ah = int(ah)
                aa = int(aa)
            except (TypeError, ValueError):
                continue

            errors.append(
                abs(ph - ah)
                +
                abs(pa - aa)
            )

        if not errors:
            return []

        avg_error = mean(errors)

        if avg_error < 1.50:
            return []

        return [{
            "type":
                "prediction_score_error_high",
            "strength":
                _pattern_strength(
                    avg_error - 1.0
                ),
            "occurrences":
                len(errors),
            "description":
                "Средняя ошибка точного счёта "
                "выше допустимого уровня.",
            "evidence": {
                "average_score_error":
                    round(avg_error, 3),
            },
        }]

    # ========================================================
    # PARAMETERS
    # ========================================================

    def _load_parameters(
        self,
        conn,
    ):

        if "model_parameters" not in self._tables(
            conn
        ):
            return dict(DEFAULT_PARAMETERS)

        columns = self._columns(
            conn,
            "model_parameters",
        )

        json_column = self._first_existing(
            columns,
            [
                "parameters",
                "parameters_json",
                "value",
                "config",
                "data",
            ],
        )

        if not json_column:
            return dict(DEFAULT_PARAMETERS)

        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT {json_column}
            FROM model_parameters
            ORDER BY rowid DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if not row:
            return dict(DEFAULT_PARAMETERS)

        try:

            parsed = json.loads(row[0])

            parameters = dict(
                DEFAULT_PARAMETERS
            )

            if isinstance(parsed, dict):

                for key in parameters:

                    if key in parsed:
                        parameters[key] = _safe_float(
                            parsed[key],
                            parameters[key],
                        )

            return parameters

        except Exception:
            return dict(DEFAULT_PARAMETERS)

    def _adjust_parameters(
        self,
        parameters,
        patterns,
    ):

        new_parameters = dict(parameters)
        changes = []

        for pattern in patterns:

            occurrences = _safe_int(
                pattern.get("occurrences")
            )

            if occurrences < MIN_PATTERN_OCCURRENCES:
                continue

            strength = _safe_float(
                pattern.get("strength")
            )

            step = _clamp(
                strength * 0.01 * PATTERN_WEIGHT,
                0.0,
                MAX_PARAMETER_STEP,
            )

            pattern_type = pattern.get("type")

            parameter = None
            direction = 0

            if pattern_type == "league_low_scoring":
                parameter = "defense"
                direction = 1

            elif pattern_type == "league_high_scoring":
                parameter = "attack"
                direction = 1

            elif pattern_type == "high_btts":
                parameter = "attack"
                direction = 1

            elif pattern_type == "low_btts":
                parameter = "defense"
                direction = 1

            elif pattern_type == "home_advantage_strong":
                parameter = "mentality"
                direction = 1

            elif pattern_type == "xg_overperformance":
                parameter = "efficiency"
                direction = 1

            elif pattern_type == "xg_underperformance":
                parameter = "efficiency"
                direction = -1

            elif pattern_type == "prediction_score_error_high":
                parameter = "form"
                direction = 1

                # form нет в текущем наборе весов.
                parameter = None

            elif pattern_type == "team_attack_strength":
                parameter = "attack"
                direction = 1

            elif pattern_type == "team_defense_strength":
                parameter = "defense"
                direction = 1

            if (
                parameter is None
                or parameter not in new_parameters
                or direction == 0
            ):
                continue

            old_value = new_parameters[
                parameter
            ]

            new_value = _clamp(
                old_value + step * direction,
                0.01,
                0.50,
            )

            if abs(
                new_value - old_value
            ) < 0.000001:
                continue

            new_parameters[
                parameter
            ] = new_value

            changes.append({
                "parameter": parameter,
                "old_value": round(
                    old_value,
                    6,
                ),
                "new_value": round(
                    new_value,
                    6,
                ),
                "delta": round(
                    new_value - old_value,
                    6,
                ),
                "reason": pattern_type,
                "occurrences": occurrences,
                "strength": round(
                    strength,
                    4,
                ),
            })

        # Нормализация.
        total = sum(
            new_parameters.values()
        )

        if total > 0:

            for key in new_parameters:
                new_parameters[key] = (
                    new_parameters[key] / total
                )

        return new_parameters, changes

    # ========================================================
    # SAVE MEMORY
    # ========================================================

    def _save_learning_memory(
        self,
        conn,
        matches,
        patterns,
        changes,
        fingerprint,
    ):

        if "learning_memory" not in self._tables(
            conn
        ):
            return

        columns = self._columns(
            conn,
            "learning_memory",
        )

        payload = {
            "created_at": _now(),
            "updated_at": _now(),
            "run_id": self.run_id,
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "memory_type": "batch_learning",
            "type": "batch_learning",
            "title":
                "FAJ пакетное обучение",
            "description":
                f"Проанализировано "
                f"{len(matches)} завершённых матчей.",
            "content": json.dumps(
                {
                    "dataset_fingerprint":
                        fingerprint,
                    "matches_analyzed":
                        len(matches),
                    "patterns":
                        patterns,
                    "parameter_changes":
                        changes,
                },
                ensure_ascii=False,
            ),
            "data": json.dumps(
                {
                    "dataset_fingerprint":
                        fingerprint,
                    "patterns":
                        patterns,
                    "parameter_changes":
                        changes,
                },
                ensure_ascii=False,
            ),
            "importance":
                "high"
                if len(patterns) >= 3
                else "normal",
            "status": "active",
        }

        self._insert_compatible(
            conn,
            "learning_memory",
            columns,
            payload,
        )

    # ========================================================
    # SAVE PARAMETERS (ИСПРАВЛЕНО)
    # ========================================================

    def _save_model_parameters(
        self,
        conn,
        parameters,
    ):
        """
        Сохраняет параметры обучения в model_parameters.
        Перед вставкой удаляет старую запись для данной пары (model_version, parameter_name),
        чтобы избежать UNIQUE constraint.
        """
        if "model_parameters" not in self._tables(conn):
            logger.warning("Таблица model_parameters отсутствует")
            return

        columns = self._columns(conn, "model_parameters")
        has_parameter_name = "parameter_name" in columns
        has_parameter_value = "parameter_value" in columns
        has_model_version = "model_version" in columns
        has_updated_at = "updated_at" in columns

        if not has_parameter_name:
            logger.error("model_parameters не содержит parameter_name")
            return

        now = _now()
        cursor = conn.cursor()
        saved_count = 0

        for param_name, param_value in parameters.items():
            # Удаляем старую запись, если она существует
            if has_model_version:
                cursor.execute(
                    "DELETE FROM model_parameters WHERE model_version = ? AND parameter_name = ?",
                    (ENGINE_VERSION, param_name)
                )
            else:
                cursor.execute(
                    "DELETE FROM model_parameters WHERE parameter_name = ?",
                    (param_name,)
                )

            # Формируем payload для вставки
            payload = {
                "parameter_name": param_name,
                "parameter_value": float(param_value),
            }
            if has_model_version:
                payload["model_version"] = ENGINE_VERSION
            if has_updated_at:
                payload["updated_at"] = now

            # Вставляем только те поля, которые есть в таблице
            usable = {k: v for k, v in payload.items() if k in columns}
            if not usable:
                continue

            names = list(usable.keys())
            placeholders = ", ".join("?" for _ in names)
            sql = f"INSERT INTO model_parameters ({', '.join(names)}) VALUES ({placeholders})"
            cursor.execute(sql, [usable[name] for name in names])
            saved_count += 1

        conn.commit()
        logger.info(f"Сохранено {saved_count} параметров в model_parameters")

    # ========================================================
    # SQLITE
    # ========================================================

    @staticmethod
    def _tables(conn):

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        return {
            row[0]
            for row in cursor.fetchall()
        }

    @staticmethod
    def _columns(
        conn,
        table,
    ):

        cursor = conn.cursor()

        cursor.execute(
            f'PRAGMA table_info("{table}")'
        )

        return {
            row[1]
            for row in cursor.fetchall()
        }

    @staticmethod
    def _first_existing(
        columns,
        candidates,
    ):

        for candidate in candidates:

            if candidate in columns:
                return candidate

        return None

    @staticmethod
    def _insert_compatible(
        conn,
        table,
        columns,
        payload,
    ):

        usable = {
            key: value
            for key, value in payload.items()
            if key in columns
        }

        if not usable:
            return

        names = list(usable.keys())

        placeholders = ", ".join(
            "?" for _ in names
        )

        cursor = conn.cursor()

        cursor.execute(
            f"""
            INSERT INTO {table}
            ({", ".join(names)})
            VALUES ({placeholders})
            """,
            [
                usable[name]
                for name in names
            ],
        )


def run_learning(
    db_path: Optional[str] = None,
    force: bool = False,
):

    return LearningEngine(
        db_path=db_path
    ).run(
        force=force
    )


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    result = run_learning()

    print("=" * 70)
    print("FAJ LEARNING ENGINE v12.1")
    print("=" * 70)

    print(
        f"Успех: {result['success']}"
    )

    print(
        f"Матчей: "
        f"{result['matches_analyzed']}"
    )

    print(
        f"Команд: "
        f"{result['teams_analyzed']}"
    )

    print(
        f"Закономерностей: "
        f"{result['patterns_found']}"
    )

    print(
        f"Прогнозов: "
        f"{result['predictions_analyzed']}"
    )

    print(
        f"Изменений параметров: "
        f"{result['parameters_changed']}"
    )

    if result["skipped"]:
        print(
            f"Пропуск: "
            f"{result['skip_reason']}"
        )

    for error in result["errors"]:
        print(f"❌ {error}")

    print("=" * 70)
