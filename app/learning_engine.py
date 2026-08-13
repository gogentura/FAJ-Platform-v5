#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
Learning Engine
===========================================================

НАЗНАЧЕНИЕ
    Пакетное обучение FAJ на накопленных завершённых матчах.

ПРИНЦИП
    Факты предыдущих матчей
            ↓
    пакетный анализ
            ↓
    поиск повторяющихся закономерностей
            ↓
    сравнение FAJ-прогнозов с фактами
            ↓
    осторожная корректировка параметров
            ↓
    learning_memory
            +
    model_parameters
            ↓
    следующий прогноз

ВАЖНО
    - обучение НЕ выполняется после каждого матча;
    - анализируются только завершённые матчи;
    - повторяющиеся закономерности имеют больший вес;
    - единичные аномалии не должны резко менять модель;
    - DELETE отсутствует;
    - исторические результаты не удаляются;
    - календарь не изменяется;
    - прогнозы нового тура здесь НЕ создаются;
    - Learning Engine работает как отдельный слой.

ПЕРВЫЙ ОБУЧАЮЩИЙ МАССИВ
    24 исторических результата РПЛ, туры 1-3.

===========================================================
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

ENGINE_VERSION = "12.1"
ENGINE_NAME = "FAJ Learning Engine"

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "faj.db"
)

MIN_MATCHES_FOR_LEARNING = 8
MIN_PATTERN_OCCURRENCES = 2

# Максимальное изменение параметра за один пакет обучения.
MAX_PARAMETER_STEP = 0.03

# Единичные аномалии практически не влияют.
ANOMALY_WEIGHT = 0.20

# Повторяющаяся закономерность.
PATTERN_WEIGHT = 1.00


# ============================================================
# DEFAULT PARAMETERS
# ============================================================

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


# ============================================================
# UTILS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
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
    return max(minimum, min(maximum, value))


# ============================================================
# LEARNING ENGINE
# ============================================================

class LearningEngine:
    """
    Пакетный Learning Engine FAJ.

    Не обучается после каждого отдельного матча.

    Основной вызов:

        engine.run()

    или:

        engine.run(force=True)

    """

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
    # PUBLIC API
    # ========================================================

    def run(
        self,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Полный пакетный цикл обучения.

        force=True позволяет запустить обучение повторно
        вручную, даже если накоплено недостаточно новых данных.
        """

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
        }

        if not self.db_path.exists():
            result["errors"].append(
                f"База данных не найдена: {self.db_path}"
            )
            return result

        conn = sqlite3.connect(
            str(self.db_path)
        )
        conn.row_factory = sqlite3.Row

        try:
            # ------------------------------------------------
            # 1. Получаем завершённые матчи
            # ------------------------------------------------

            matches = self._get_finished_matches(conn)

            result["matches_analyzed"] = len(matches)

            if (
                len(matches) < MIN_MATCHES_FOR_LEARNING
                and not force
            ):
                result["errors"].append(
                    "Недостаточно завершённых матчей "
                    f"для пакетного обучения: "
                    f"{len(matches)}/{MIN_MATCHES_FOR_LEARNING}"
                )
                return result

            # ------------------------------------------------
            # 2. Анализируем команды
            # ------------------------------------------------

            team_stats = self._build_team_statistics(
                matches
            )

            result["teams_analyzed"] = len(team_stats)

            # ------------------------------------------------
            # 3. Ищем устойчивые закономерности
            # ------------------------------------------------

            patterns = self._find_patterns(
                matches,
                team_stats,
            )

            result["patterns"] = patterns
            result["patterns_found"] = len(patterns)

            # ------------------------------------------------
            # 4. Сравнение прогнозов с фактами
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

            for pattern in prediction_patterns:
                patterns.append(pattern)

            result["patterns_found"] = len(patterns)

            # ------------------------------------------------
            # 5. Получаем текущие параметры
            # ------------------------------------------------

            parameters = self._load_parameters(
                conn
            )

            # ------------------------------------------------
            # 6. Корректируем параметры
            # ------------------------------------------------

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
            # 7. Сохраняем память обучения
            # ------------------------------------------------

            self._save_learning_memory(
                conn,
                matches,
                patterns,
                changes,
            )

            # ------------------------------------------------
            # 8. Сохраняем параметры
            # ------------------------------------------------

            self._save_model_parameters(
                conn,
                new_parameters,
            )

            conn.commit()

            result["success"] = True
            result["finished_at"] = _now()

            logger.info(
                "FAJ Learning Engine completed: "
                "%s matches, %s patterns, %s parameter changes",
                len(matches),
                len(patterns),
                len(changes),
            )

            return result

        except Exception as exc:

            conn.rollback()

            logger.exception(
                "Learning Engine error"
            )

            result["errors"].append(
                str(exc)
            )

            result["finished_at"] = _now()

            return result

        finally:
            conn.close()

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

            LEFT JOIN match_results mr
                ON mr.match_id = m.id

            WHERE
                (
                    m.status = 'finished'
                    OR
                    mr.match_id IS NOT NULL
                )

                AND
                (
                    mr.home_goals IS NOT NULL
                    AND
                    mr.away_goals IS NOT NULL
                )

            ORDER BY
                datetime(m.date) ASC,
                m.id ASC
            """
        )

        rows = cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # TEAM STATISTICS
    # ========================================================

    def _build_team_statistics(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:

        stats: Dict[str, Dict[str, Any]] = {}

        for match in matches:

            home = match.get("home_team")
            away = match.get("away_team")

            if not home or not away:
                continue

            home_goals = _safe_int(
                match.get("result_home_goals")
            )

            away_goals = _safe_int(
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

            h["goals_for"] += home_goals
            h["goals_against"] += away_goals

            a["goals_for"] += away_goals
            a["goals_against"] += home_goals

            h["home_matches"] += 1
            a["away_matches"] += 1

            if home_goals > away_goals:

                h["wins"] += 1
                a["losses"] += 1

            elif home_goals < away_goals:

                h["losses"] += 1
                a["wins"] += 1

            else:

                h["draws"] += 1
                a["draws"] += 1

            if home_goals == 0:
                h["clean_sheets_against"] += 1

            if away_goals == 0:
                a["clean_sheets_against"] += 1

            if home_goals == 0:
                a["clean_sheets"] += 1

            if away_goals == 0:
                h["clean_sheets"] += 1

            h["points"] += (
                3
                if home_goals > away_goals
                else 1
                if home_goals == away_goals
                else 0
            )

            a["points"] += (
                3
                if away_goals > home_goals
                else 1
                if away_goals == home_goals
                else 0
            )

            total_goals = (
                home_goals + away_goals
            )

            h["total_goals_in_matches"] += (
                total_goals
            )

            a["total_goals_in_matches"] += (
                total_goals
            )

        for team, data in stats.items():

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

            data["points_avg"] = (
                data["points"] / games
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
            "home_matches": 0,
            "away_matches": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "clean_sheets": 0,
            "clean_sheets_against": 0,
            "total_goals_in_matches": 0,
        }

    # ========================================================
    # PATTERN DETECTION
    # ========================================================

    def _find_patterns(
        self,
        matches: List[Dict[str, Any]],
        team_stats: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        patterns: List[Dict[str, Any]] = []

        if not matches:
            return patterns

        # ----------------------------------------------------
        # Pattern 1:
        # Низкая результативность
        # ----------------------------------------------------

        total_goals = 0

        for match in matches:

            total_goals += (
                _safe_int(
                    match.get("result_home_goals")
                )
                +
                _safe_int(
                    match.get("result_away_goals")
                )
            )

        avg_goals = (
            total_goals / len(matches)
        )

        if avg_goals < 2.20:

            patterns.append({
                "type": "league_low_scoring",
                "strength": _pattern_strength(
                    abs(2.20 - avg_goals)
                ),
                "occurrences": len(matches),
                "description": (
                    "РПЛ показывает пониженную "
                    "результативность."
                ),
                "evidence": {
                    "matches": len(matches),
                    "average_goals": round(
                        avg_goals,
                        3,
                    ),
                },
            })

        # ----------------------------------------------------
        # Pattern 2:
        # Высокая результативность
        # ----------------------------------------------------

        elif avg_goals > 2.80:

            patterns.append({
                "type": "league_high_scoring",
                "strength": _pattern_strength(
                    avg_goals - 2.80
                ),
                "occurrences": len(matches),
                "description": (
                    "РПЛ показывает повышенную "
                    "результативность."
                ),
                "evidence": {
                    "matches": len(matches),
                    "average_goals": round(
                        avg_goals,
                        3,
                    ),
                },
            })

        # ----------------------------------------------------
        # Pattern 3:
        # BTTS
        # ----------------------------------------------------

        btts_count = 0

        for match in matches:

            hg = _safe_int(
                match.get("result_home_goals")
            )

            ag = _safe_int(
                match.get("result_away_goals")
            )

            if hg > 0 and ag > 0:
                btts_count += 1

        btts_rate = (
            btts_count / len(matches)
        )

        if btts_rate >= 0.65:

            patterns.append({
                "type": "high_btts",
                "strength": _pattern_strength(
                    btts_rate - 0.50
                ),
                "occurrences": btts_count,
                "description": (
                    "Повышенная частота матчей "
                    "с голами обеих команд."
                ),
                "evidence": {
                    "btts_rate": round(
                        btts_rate,
                        3,
                    ),
                },
            })

        elif btts_rate <= 0.35:

            patterns.append({
                "type": "low_btts",
                "strength": _pattern_strength(
                    0.50 - btts_rate
                ),
                "occurrences": (
                    len(matches) - btts_count
                ),
                "description": (
                    "Повышенная частота матчей "
                    "без голов одной из команд."
                ),
                "evidence": {
                    "btts_rate": round(
                        btts_rate,
                        3,
                    ),
                },
            })

        # ----------------------------------------------------
        # Pattern 4:
        # Домашнее преимущество
        # ----------------------------------------------------

        home_wins = 0
        away_wins = 0
        draws = 0

        for match in matches:

            hg = _safe_int(
                match.get("result_home_goals")
            )

            ag = _safe_int(
                match.get("result_away_goals")
            )

            if hg > ag:
                home_wins += 1
            elif hg < ag:
                away_wins += 1
            else:
                draws += 1

        home_rate = (
            home_wins / len(matches)
        )

        away_rate = (
            away_wins / len(matches)
        )

        draw_rate = (
            draws / len(matches)
        )

        if home_rate >= 0.50:

            patterns.append({
                "type": "home_advantage_strong",
                "strength": _pattern_strength(
                    home_rate - 0.33
                ),
                "occurrences": home_wins,
                "description": (
                    "Домашняя команда выигрывает "
                    "чаще обычного."
                ),
                "evidence": {
                    "home_win_rate": round(
                        home_rate,
                        3,
                    ),
                    "away_win_rate": round(
                        away_rate,
                        3,
                    ),
                    "draw_rate": round(
                        draw_rate,
                        3,
                    ),
                },
            })

        # ----------------------------------------------------
        # Pattern 5:
        # Большое количество ничьих
        # ----------------------------------------------------

        if draw_rate >= 0.40:

            patterns.append({
                "type": "high_draw_rate",
                "strength": _pattern_strength(
                    draw_rate - 0.33
                ),
                "occurrences": draws,
                "description": (
                    "Повышенная доля ничейных "
                    "результатов."
                ),
                "evidence": {
                    "draw_rate": round(
                        draw_rate,
                        3,
                    ),
                },
            })

        # ----------------------------------------------------
        # Pattern 6:
        # Команды с аномальным xG/результатом
        # ----------------------------------------------------

        xg_patterns = self._find_xg_patterns(
            matches
        )

        patterns.extend(
            xg_patterns
        )

        # ----------------------------------------------------
        # Pattern 7:
        # Устойчивые команды
        # ----------------------------------------------------

        for team, stats in team_stats.items():

            if stats["matches"] < 2:
                continue

            if (
                stats["win_rate"] >= 0.75
                and stats["goals_for_avg"] >= 2.0
            ):

                patterns.append({
                    "type": "team_attack_strength",
                    "team": team,
                    "strength": _pattern_strength(
                        stats["win_rate"]
                    ),
                    "occurrences": stats["matches"],
                    "description": (
                        f"{team}: устойчивая "
                        "результативная форма."
                    ),
                    "evidence": {
                        "matches": stats["matches"],
                        "goals_for_avg": round(
                            stats["goals_for_avg"],
                            3,
                        ),
                        "win_rate": round(
                            stats["win_rate"],
                            3,
                        ),
                    },
                })

            if (
                stats["clean_sheet_rate"] >= 0.50
                and stats["goals_against_avg"] <= 0.75
            ):

                patterns.append({
                    "type": "team_defense_strength",
                    "team": team,
                    "strength": _pattern_strength(
                        stats["clean_sheet_rate"]
                    ),
                    "occurrences": stats["matches"],
                    "description": (
                        f"{team}: устойчивая "
                        "оборонительная форма."
                    ),
                    "evidence": {
                        "matches": stats["matches"],
                        "goals_against_avg": round(
                            stats["goals_against_avg"],
                            3,
                        ),
                        "clean_sheet_rate": round(
                            stats["clean_sheet_rate"],
                            3,
                        ),
                    },
                })

        return patterns

    # ========================================================
    # XG PATTERNS
    # ========================================================

    def _find_xg_patterns(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        patterns = []

        xg_available = []

        for match in matches:

            hxg = match.get("home_xg")
            axg = match.get("away_xg")

            if hxg is None or axg is None:
                continue

            xg_available.append(match)

        if len(xg_available) < 4:
            return patterns

        overperformance = []

        underperformance = []

        for match in xg_available:

            hxg = _safe_float(
                match.get("home_xg")
            )

            axg = _safe_float(
                match.get("away_xg")
            )

            hg = _safe_int(
                match.get("result_home_goals")
            )

            ag = _safe_int(
                match.get("result_away_goals")
            )

            overperformance.append(
                (hg - hxg) + (ag - axg)
            )

            underperformance.append(
                (hxg - hg) + (axg - ag)
            )

        avg_over = mean(
            overperformance
        )

        avg_under = mean(
            underperformance
        )

        if avg_over > 0.40:

            patterns.append({
                "type": "xg_overperformance",
                "strength": _pattern_strength(
                    avg_over
                ),
                "occurrences": len(
                    xg_available
                ),
                "description": (
                    "Фактические голы в среднем "
                    "выше ожидаемых xG."
                ),
                "evidence": {
                    "average_difference": round(
                        avg_over,
                        3,
                    ),
                },
            })

        if avg_under > 0.40:

            patterns.append({
                "type": "xg_underperformance",
                "strength": _pattern_strength(
                    avg_under
                ),
                "occurrences": len(
                    xg_available
                ),
                "description": (
                    "Фактические голы в среднем "
                    "ниже ожидаемых xG."
                ),
                "evidence": {
                    "average_difference": round(
                        avg_under,
                        3,
                    ),
                },
            })

        return patterns

    # ========================================================
    # PREDICTION ANALYSIS
    # ========================================================

    def _get_prediction_accuracy(
        self,
        conn: sqlite3.Connection,
    ) -> List[Dict[str, Any]]:

        tables = self._tables(conn)

        if "predictions" not in tables:
            return []

        columns = self._columns(
            conn,
            "predictions",
        )

        # Ищем наиболее вероятные поля.
        match_column = self._first_existing(
            columns,
            [
                "match_id",
                "fixture_id",
            ],
        )

        home_score_column = self._first_existing(
            columns,
            [
                "predicted_home",
                "predicted_home_goals",
                "home_goals",
                "home_score",
            ],
        )

        away_score_column = self._first_existing(
            columns,
            [
                "predicted_away",
                "predicted_away_goals",
                "away_goals",
                "away_score",
            ],
        )

        if not match_column:
            return []

        query = f"""
            SELECT *
            FROM predictions
            WHERE {match_column} IS NOT NULL
        """

        cursor = conn.cursor()
        cursor.execute(query)

        rows = [
            dict(row)
            for row in cursor.fetchall()
        ]

        # Если точного счёта нет, всё равно возвращаем
        # записи для дальнейшего анализа вероятностей.
        for row in rows:

            row["_match_id"] = row.get(
                match_column
            )

            row["_predicted_home"] = (
                row.get(home_score_column)
                if home_score_column
                else None
            )

            row["_predicted_away"] = (
                row.get(away_score_column)
                if away_score_column
                else None
            )

        return rows

    def _analyze_prediction_errors(
        self,
        predictions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        if not predictions:
            return []

        exact_hits = 0
        score_errors = []

        for prediction in predictions:

            ph = prediction.get(
                "_predicted_home"
            )

            pa = prediction.get(
                "_predicted_away"
            )

            if ph is None or pa is None:
                continue

            try:
                ph = int(ph)
                pa = int(pa)
            except (TypeError, ValueError):
                continue

            # Факт может отсутствовать непосредственно
            # в prediction.
            actual_home = prediction.get(
                "actual_home"
            )

            actual_away = prediction.get(
                "actual_away"
            )

            if (
                actual_home is None
                or actual_away is None
            ):
                continue

            ah = int(actual_home)
            aa = int(actual_away)

            if ph == ah and pa == aa:
                exact_hits += 1

            score_errors.append(
                abs(ph - ah)
                +
                abs(pa - aa)
            )

        if not score_errors:
            return []

        avg_error = mean(
            score_errors
        )

        patterns = []

        if avg_error >= 1.50:

            patterns.append({
                "type": "prediction_score_error_high",
                "strength": _pattern_strength(
                    avg_error - 1.0
                ),
                "occurrences": len(
                    score_errors
                ),
                "description": (
                    "Средняя ошибка точного счёта "
                    "выше допустимого уровня."
                ),
                "evidence": {
                    "average_score_error": round(
                        avg_error,
                        3,
                    ),
                    "exact_hits": exact_hits,
                },
            })

        return patterns

    # ========================================================
    # PARAMETERS
    # ========================================================

    def _load_parameters(
        self,
        conn: sqlite3.Connection,
    ) -> Dict[str, float]:

        tables = self._tables(conn)

        if "model_parameters" not in tables:
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

        value = row[0]

        try:

            if isinstance(
                value,
                str,
            ):

                parsed = json.loads(
                    value
                )

            elif isinstance(
                value,
                dict,
            ):

                parsed = value

            else:

                parsed = {}

            parameters = dict(
                DEFAULT_PARAMETERS
            )

            for key in parameters:

                if key in parsed:

                    parameters[key] = _safe_float(
                        parsed[key],
                        parameters[key],
                    )

            return parameters

        except Exception:

            return dict(
                DEFAULT_PARAMETERS
            )

    def _adjust_parameters(
        self,
        parameters: Dict[str, float],
        patterns: List[Dict[str, Any]],
    ) -> Tuple[
        Dict[str, float],
        List[Dict[str, Any]],
    ]:

        new_parameters = dict(
            parameters
        )

        changes = []

        for pattern in patterns:

            pattern_type = pattern.get(
                "type"
            )

            strength = _safe_float(
                pattern.get(
                    "strength"
                )
            )

            occurrences = _safe_int(
                pattern.get(
                    "occurrences"
                )
            )

            if (
                occurrences
                < MIN_PATTERN_OCCURRENCES
            ):
                continue

            # Повторяющаяся закономерность имеет
            # нормальный вес. Единичная — сильно
            # ослабленный.
            weight = (
                PATTERN_WEIGHT
                if occurrences >= 2
                else ANOMALY_WEIGHT
            )

            step = _clamp(
                strength
                * 0.01
                * weight,
                0.0,
                MAX_PARAMETER_STEP,
            )

            parameter = None
            direction = 0

            # --------------------------------------------
            # Результативность
            # --------------------------------------------

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

            elif pattern_type == "high_draw_rate":

                parameter = "predictability"
                direction = 1

                # Если такого параметра нет,
                # не создаём его искусственно.
                if parameter not in new_parameters:
                    parameter = None

            elif pattern_type == "xg_overperformance":

                parameter = "efficiency"
                direction = 1

            elif pattern_type == "xg_underperformance":

                parameter = "efficiency"
                direction = -1

            elif pattern_type == "prediction_score_error_high":

                parameter = "form"
                direction = 1

                if parameter not in new_parameters:
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
                old_value
                + (
                    step
                    * direction
                ),
                0.01,
                0.50,
            )

            # Изменяем только действительно отличающиеся
            # значения.
            if abs(
                new_value - old_value
            ) < 0.0001:
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

        # ----------------------------------------------------
        # Нормализация весов.
        # ----------------------------------------------------

        total = sum(
            new_parameters.values()
        )

        if total > 0:

            for key in new_parameters:

                new_parameters[key] = (
                    new_parameters[key]
                    / total
                )

        return new_parameters, changes

    # ========================================================
    # SAVE LEARNING MEMORY
    # ========================================================

    def _save_learning_memory(
        self,
        conn: sqlite3.Connection,
        matches: List[Dict[str, Any]],
        patterns: List[Dict[str, Any]],
        changes: List[Dict[str, Any]],
    ) -> None:

        if "learning_memory" not in self._tables(
            conn
        ):
            logger.warning(
                "Таблица learning_memory отсутствует."
            )
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
            "title": (
                "FAJ пакетное обучение "
                f"{datetime.now().strftime('%Y-%m-%d')}"
            ),
            "description": (
                f"Проанализировано {len(matches)} "
                f"завершённых матчей."
            ),
            "content": json.dumps(
                {
                    "matches_analyzed": len(
                        matches
                    ),
                    "patterns": patterns,
                    "parameter_changes": changes,
                },
                ensure_ascii=False,
            ),
            "data": json.dumps(
                {
                    "patterns": patterns,
                    "parameter_changes": changes,
                },
                ensure_ascii=False,
            ),
            "importance": (
                "high"
                if len(patterns) >= 3
                else "normal"
            ),
            "status": "active",
        }

        self._insert_compatible(
            conn,
            "learning_memory",
            columns,
            payload,
        )

    # ========================================================
    # SAVE MODEL PARAMETERS
    # ========================================================

    def _save_model_parameters(
        self,
        conn: sqlite3.Connection,
        parameters: Dict[str, float],
    ) -> None:

        if "model_parameters" not in self._tables(
            conn
        ):
            logger.warning(
                "Таблица model_parameters отсутствует."
            )
            return

        columns = self._columns(
            conn,
            "model_parameters",
        )

        encoded = json.dumps(
            parameters,
            ensure_ascii=False,
        )

        payload = {
            "created_at": _now(),
            "updated_at": _now(),
            "run_id": self.run_id,
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "parameter_type": "learning",
            "name": "FAJ learned parameters",
            "parameters": encoded,
            "parameters_json": encoded,
            "value": encoded,
            "config": encoded,
            "data": encoded,
            "status": "active",
        }

        self._insert_compatible(
            conn,
            "model_parameters",
            columns,
            payload,
        )

    # ========================================================
    # SQLITE SCHEMA HELPERS
    # ========================================================

    @staticmethod
    def _tables(
        conn: sqlite3.Connection,
    ) -> set:

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
        conn: sqlite3.Connection,
        table: str,
    ) -> set:

        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info({table})"
        )

        return {
            row[1]
            for row in cursor.fetchall()
        }

    @staticmethod
    def _first_existing(
        columns: set,
        candidates: List[str],
    ) -> Optional[str]:

        for candidate in candidates:

            if candidate in columns:
                return candidate

        return None

    @staticmethod
    def _insert_compatible(
        conn: sqlite3.Connection,
        table: str,
        columns: set,
        payload: Dict[str, Any],
    ) -> None:

        usable = {
            key: value
            for key, value in payload.items()
            if key in columns
        }

        if not usable:
            logger.warning(
                "Нет совместимых колонок для %s",
                table,
            )
            return

        names = list(
            usable.keys()
        )

        placeholders = ", ".join(
            ["?"] * len(names)
        )

        sql = f"""
            INSERT INTO {table}
            ({", ".join(names)})
            VALUES ({placeholders})
        """

        cursor = conn.cursor()

        cursor.execute(
            sql,
            [
                usable[name]
                for name in names
            ],
        )


# ============================================================
# HELPERS
# ============================================================

def _pattern_strength(
    difference: float,
) -> float:

    """
    Преобразует силу закономерности в диапазон 0..1.

    Мы специально не используем линейное агрессивное
    изменение модели.
    """

    difference = abs(
        _safe_float(
            difference
        )
    )

    return _clamp(
        difference,
        0.0,
        1.0,
    )


# ============================================================
# CONVENIENCE API
# ============================================================

def run_learning(
    db_path: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:

    engine = LearningEngine(
        db_path=db_path
    )

    return engine.run(
        force=force
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    print()
    print("=" * 70)
    print("FAJ LEARNING ENGINE v12.1")
    print("=" * 70)

    result = run_learning()

    print()
    print(
        f"Успех: {result['success']}"
    )

    print(
        f"Матчей проанализировано: "
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
        f"Прогнозов проанализировано: "
        f"{result['predictions_analyzed']}"
    )

    print(
        f"Изменений параметров: "
        f"{result['parameters_changed']}"
    )

    if result["patterns"]:

        print()
        print("НАЙДЕННЫЕ ЗАКОНОМЕРНОСТИ:")

        for pattern in result["patterns"]:

            print(
                f"  • "
                f"{pattern.get('description', pattern.get('type'))} "
                f"(повторений: "
                f"{pattern.get('occurrences', 0)})"
            )

    if result["parameter_changes"]:

        print()
        print("ИЗМЕНЕНИЯ ПАРАМЕТРОВ:")

        for change in result[
            "parameter_changes"
        ]:

            print(
                f"  • "
                f"{change['parameter']}: "
                f"{change['old_value']:.4f} → "
                f"{change['new_value']:.4f} "
                f"({change['delta']:+.4f})"
            )

    if result["errors"]:

        print()
        print("ОШИБКИ:")

        for error in result["errors"]:

            print(
                f"  ❌ {error}"
            )

    print("=" * 70)
