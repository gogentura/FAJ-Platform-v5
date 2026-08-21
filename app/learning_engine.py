#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ LEARNING ENGINE v2.3
MEMORY HARDENED
============================================================

Назначение:
    Пакетное обучение FAJ на завершённых матчах.

ЦЕПОЧКА:

    MATCH RESULTS
          ↓
    LEARNING ENGINE
          ↓
    FINISHED MATCHES
          ↓
    TEAM STATISTICS
          ↓
    PATTERN DETECTION
          ↓
    PREDICTION ACCURACY
          ↓
    PARAMETER ADJUSTMENT
          ↓
    LEARNING MEMORY
          ↓
    MODEL PARAMETERS
          ↓
    NEXT CYCLE

ПРИНЦИПЫ:

    SQLite only
    database.py — единый источник схемы
    Основная память — только через FAJDatabase
    learning_memory — допустимый прямой SQL
    Никакого DELETE
    Никакого DROP
    Никакого изменения исторических фактов
    Никакого изменения календаря
    Параметры сохраняются через versioning API
    Повторное обучение одного набора матчей блокируется
    sqlite3.Row никогда не изменяется напрямую

============================================================
V2.3 — SQLITE ROW HARDENING
============================================================

ИСПРАВЛЕНО:

    sqlite3.Row object does not support item assignment

Причина:

    FAJDatabase возвращает sqlite3.Row.

    Старый код делал:

        match["result_home_goals"] = ...

    sqlite3.Row является read-only.

Решение:

    Каждый Row преобразуется:

        dict(row)

    после чего Learning Engine работает
    только с обычными Python dict.

Также защищены:

    matches
    match results
    teams
    predictions

============================================================
"""

from __future__ import annotations

import hashlib
import json
import logging

from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple


from app.database import FAJDatabase


logger = logging.getLogger(__name__)


# ============================================================
# ENGINE CONFIG
# ============================================================

ENGINE_VERSION = "2.3"
ENGINE_NAME = "FAJ Learning Engine v2.3"

MIN_MATCHES_FOR_LEARNING = 8
MIN_PATTERN_OCCURRENCES = 2

MAX_PARAMETER_STEP = 0.03
PATTERN_WEIGHT = 1.0


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
# SAFE HELPERS
# ============================================================

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


def _row_to_dict(
    value: Any,
) -> Dict[str, Any]:

    """
    Безопасное преобразование результата SQLite
    в обычный dict.

    Поддерживает:

        dict
        sqlite3.Row
        другие mapping-like объекты
    """

    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    try:
        return dict(value)

    except (TypeError, ValueError):

        pass

    if hasattr(value, "__dict__"):

        try:
            return dict(value.__dict__)

        except Exception:
            pass

    return {}


# ============================================================
# LEARNING ENGINE
# ============================================================

class LearningEngine:
    """
    FAJ Learning Engine v2.3.

    Пакетное обучение на завершённых матчах.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

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

        result: Dict[str, Any] = {

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

        try:

            # =================================================
            # 1. FINISHED MATCHES
            # =================================================

            matches = self._get_finished_matches()

            result["matches_analyzed"] = len(matches)

            logger.info(
                "FAJ Learning: finished matches=%s",
                len(matches),
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

                result["finished_at"] = _now()

                return result

            # =================================================
            # 2. REPEATED DATASET PROTECTION
            # =================================================

            fingerprint = (
                self._dataset_fingerprint(matches)
            )

            if (
                not force
                and self._was_dataset_already_learned(
                    fingerprint
                )
            ):

                result["success"] = True
                result["skipped"] = True

                result["skip_reason"] = (
                    "Этот набор завершённых матчей "
                    "уже использовался для обучения."
                )

                result["finished_at"] = _now()

                logger.info(
                    "FAJ Learning skipped: "
                    "dataset already learned"
                )

                return result

            # =================================================
            # 3. TEAM STATISTICS
            # =================================================

            team_stats = (
                self._build_team_statistics(
                    matches
                )
            )

            result["teams_analyzed"] = len(
                team_stats
            )

            # =================================================
            # 4. PATTERNS
            # =================================================

            patterns = self._find_patterns(
                matches,
                team_stats,
            )

            # =================================================
            # 5. PREDICTIONS
            # =================================================

            predictions = (
                self._get_prediction_accuracy()
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

            # =================================================
            # 6. PARAMETERS
            # =================================================

            parameters = (
                self._load_parameters()
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

            # =================================================
            # 7. SAVE LEARNING MEMORY
            # =================================================

            self._save_learning_memory(
                matches=matches,
                patterns=patterns,
                changes=changes,
                fingerprint=fingerprint,
            )

            # =================================================
            # 8. SAVE PARAMETERS
            # =================================================

            self._save_model_parameters(
                parameters=new_parameters,
                changes=changes,
            )

            # =================================================
            # SUCCESS
            # =================================================

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

            logger.exception(
                "FAJ Learning Engine error"
            )

            result["errors"].append(
                str(exc)
            )

            result["finished_at"] = _now()

            return result

    # ========================================================
    # FINISHED MATCHES
    # ========================================================

    def _get_finished_matches(
        self,
    ) -> List[Dict[str, Any]]:

        """
        Получает завершённые матчи.

        КРИТИЧЕСКИ ВАЖНО:

        FAJDatabase может возвращать sqlite3.Row.

        sqlite3.Row нельзя изменять:

            row["field"] = value

        Поэтому каждый объект сначала
        преобразуется в обычный dict.
        """

        all_matches = self.db.get_matches()

        finished: List[Dict[str, Any]] = []

        for raw_match in all_matches or []:

            # ------------------------------------------------
            # ROW -> DICT
            # ------------------------------------------------

            match = _row_to_dict(
                raw_match
            )

            if not match:
                continue

            match_id = match.get("id")

            if match_id is None:
                continue

            # ------------------------------------------------
            # MATCH RESULT
            # ------------------------------------------------

            raw_result = (
                self.db.get_match_result(
                    match_id
                )
            )

            if not raw_result:
                continue

            result = _row_to_dict(
                raw_result
            )

            if not result:
                continue

            home_goals = result.get(
                "home_goals"
            )

            away_goals = result.get(
                "away_goals"
            )

            # ------------------------------------------------
            # MATCH MUST HAVE COMPLETE SCORE
            # ------------------------------------------------

            if (
                home_goals is None
                or away_goals is None
            ):
                continue

            # ------------------------------------------------
            # ADD FACTS
            # ------------------------------------------------

            match[
                "result_home_goals"
            ] = home_goals

            match[
                "result_away_goals"
            ] = away_goals

            # ------------------------------------------------
            # HOME TEAM
            # ------------------------------------------------

            home_team_id = match.get(
                "home_team_id"
            )

            home = None

            if home_team_id is not None:

                try:

                    home = self.db.get_team(
                        home_team_id
                    )

                except Exception as exc:

                    logger.warning(
                        "Ошибка получения "
                        "home team %s: %s",
                        home_team_id,
                        exc,
                    )

            home = _row_to_dict(home)

            # ------------------------------------------------
            # AWAY TEAM
            # ------------------------------------------------

            away_team_id = match.get(
                "away_team_id"
            )

            away = None

            if away_team_id is not None:

                try:

                    away = self.db.get_team(
                        away_team_id
                    )

                except Exception as exc:

                    logger.warning(
                        "Ошибка получения "
                        "away team %s: %s",
                        away_team_id,
                        exc,
                    )

            away = _row_to_dict(away)

            # ------------------------------------------------
            # TEAM NAMES
            # ------------------------------------------------

            match["home_team"] = (
                home.get("name")
                if home
                else None
            )

            match["away_team"] = (
                away.get("name")
                if away
                else None
            )

            finished.append(
                match
            )

        logger.info(
            "FAJ Learning: найдено "
            "завершённых матчей: %s",
            len(finished),
        )

        return finished

    # ========================================================
    # DATASET FINGERPRINT
    # ========================================================

    @staticmethod
    def _dataset_fingerprint(
        matches: List[Dict[str, Any]],
    ) -> str:

        rows = []

        for match in matches:

            rows.append(
                {
                    "id": match.get("id"),
                    "home": match.get(
                        "home_team_id"
                    ),
                    "away": match.get(
                        "away_team_id"
                    ),
                    "hg": match.get(
                        "result_home_goals"
                    ),
                    "ag": match.get(
                        "result_away_goals"
                    ),
                }
            )

        encoded = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
        )

        return hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest()

    # ========================================================
    # LEARNING MEMORY CHECK
    # ========================================================

    def _was_dataset_already_learned(
        self,
        fingerprint: str,
    ) -> bool:

        """
        Проверяет повторное обучение.

        learning_memory — единственное место,
        где используется прямой SQL.
        """

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 1
                FROM learning_memory
                WHERE content LIKE ?
                   OR data LIKE ?
                LIMIT 1
                """,
                (
                    f"%{fingerprint}%",
                    f"%{fingerprint}%",
                ),
            )

            return (
                cursor.fetchone()
                is not None
            )

        finally:

            conn.close()

    # ========================================================
    # TEAM STATISTICS
    # ========================================================

    def _build_team_statistics(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:

        stats: Dict[
            str,
            Dict[str, Any]
        ] = {}

        for match in matches:

            home = match.get(
                "home_team"
            )

            away = match.get(
                "away_team"
            )

            if not home or not away:
                continue

            hg = _safe_int(
                match.get(
                    "result_home_goals"
                )
            )

            ag = _safe_int(
                match.get(
                    "result_away_goals"
                )
            )

            if home not in stats:

                stats[home] = (
                    self._empty_team_stats(
                        home
                    )
                )

            if away not in stats:

                stats[away] = (
                    self._empty_team_stats(
                        away
                    )
                )

            h = stats[home]
            a = stats[away]

            # ------------------------------------------------
            # MATCHES
            # ------------------------------------------------

            h["matches"] += 1
            a["matches"] += 1

            # ------------------------------------------------
            # GOALS
            # ------------------------------------------------

            h["goals_for"] += hg
            h["goals_against"] += ag

            a["goals_for"] += ag
            a["goals_against"] += hg

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            if hg > ag:

                h["wins"] += 1
                a["losses"] += 1

            elif hg < ag:

                h["losses"] += 1
                a["wins"] += 1

            else:

                h["draws"] += 1
                a["draws"] += 1

            # ------------------------------------------------
            # CLEAN SHEETS
            # ------------------------------------------------

            if hg == 0:
                a["clean_sheets"] += 1

            if ag == 0:
                h["clean_sheets"] += 1

            # ------------------------------------------------
            # POINTS
            # ------------------------------------------------

            h["points"] += (
                3
                if hg > ag
                else 1
                if hg == ag
                else 0
            )

            a["points"] += (
                3
                if ag > hg
                else 1
                if ag == hg
                else 0
            )

            # ------------------------------------------------
            # TOTAL GOALS
            # ------------------------------------------------

            total = hg + ag

            h[
                "total_goals_in_matches"
            ] += total

            a[
                "total_goals_in_matches"
            ] += total

        # ----------------------------------------------------
        # AVERAGES
        # ----------------------------------------------------

        for data in stats.values():

            games = max(
                1,
                data["matches"],
            )

            data["goals_for_avg"] = (
                data["goals_for"]
                / games
            )

            data["goals_against_avg"] = (
                data["goals_against"]
                / games
            )

            data["win_rate"] = (
                data["wins"]
                / games
            )

            data["draw_rate"] = (
                data["draws"]
                / games
            )

            data["loss_rate"] = (
                data["losses"]
                / games
            )

            data["clean_sheet_rate"] = (
                data["clean_sheets"]
                / games
            )

            data["avg_total_goals"] = (
                data[
                    "total_goals_in_matches"
                ]
                / games
            )

        return stats

    # ========================================================
    # EMPTY TEAM STATS
    # ========================================================

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
        matches: List[Dict[str, Any]],
        team_stats: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        patterns: List[
            Dict[str, Any]
        ] = []

        if not matches:
            return patterns

        # ----------------------------------------------------
        # TOTAL GOALS
        # ----------------------------------------------------

        total_goals = sum(
            _safe_int(
                m.get(
                    "result_home_goals"
                )
            )
            +
            _safe_int(
                m.get(
                    "result_away_goals"
                )
            )
            for m in matches
        )

        avg_goals = (
            total_goals
            / len(matches)
        )

        if avg_goals < 2.20:

            patterns.append(
                {
                    "type":
                        "league_low_scoring",

                    "strength":
                        _pattern_strength(
                            2.20
                            - avg_goals
                        ),

                    "occurrences":
                        len(matches),

                    "description":
                        "Пониженная "
                        "результативность РПЛ.",

                    "evidence":
                        {
                            "average_goals":
                                round(
                                    avg_goals,
                                    3,
                                )
                        },
                }
            )

        elif avg_goals > 2.80:

            patterns.append(
                {
                    "type":
                        "league_high_scoring",

                    "strength":
                        _pattern_strength(
                            avg_goals
                            - 2.80
                        ),

                    "occurrences":
                        len(matches),

                    "description":
                        "Повышенная "
                        "результативность РПЛ.",

                    "evidence":
                        {
                            "average_goals":
                                round(
                                    avg_goals,
                                    3,
                                )
                        },
                }
            )

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        btts = sum(
            1
            for m in matches
            if (
                _safe_int(
                    m.get(
                        "result_home_goals"
                    )
                ) > 0
                and
                _safe_int(
                    m.get(
                        "result_away_goals"
                    )
                ) > 0
            )
        )

        btts_rate = (
            btts
            / len(matches)
        )

        if btts_rate >= 0.65:

            patterns.append(
                {
                    "type": "high_btts",

                    "strength":
                        _pattern_strength(
                            btts_rate
                            - 0.50
                        ),

                    "occurrences": btts,

                    "description":
                        "Повышенная "
                        "частота BTTS.",

                    "evidence":
                        {
                            "btts_rate":
                                round(
                                    btts_rate,
                                    3,
                                )
                        },
                }
            )

        elif btts_rate <= 0.35:

            patterns.append(
                {
                    "type": "low_btts",

                    "strength":
                        _pattern_strength(
                            0.50
                            - btts_rate
                        ),

                    "occurrences":
                        len(matches)
                        - btts,

                    "description":
                        "Пониженная "
                        "частота BTTS.",

                    "evidence":
                        {
                            "btts_rate":
                                round(
                                    btts_rate,
                                    3,
                                )
                        },
                }
            )

        # ----------------------------------------------------
        # HOME / DRAW / AWAY
        # ----------------------------------------------------

        home_wins = 0
        draws = 0
        away_wins = 0

        for m in matches:

            hg = _safe_int(
                m.get(
                    "result_home_goals"
                )
            )

            ag = _safe_int(
                m.get(
                    "result_away_goals"
                )
            )

            if hg > ag:
                home_wins += 1

            elif hg < ag:
                away_wins += 1

            else:
                draws += 1

        home_rate = (
            home_wins
            / len(matches)
        )

        draw_rate = (
            draws
            / len(matches)
        )

        if home_rate >= 0.50:

            patterns.append(
                {
                    "type":
                        "home_advantage_strong",

                    "strength":
                        _pattern_strength(
                            home_rate
                            - 0.33
                        ),

                    "occurrences":
                        home_wins,

                    "description":
                        "Повышенная доля "
                        "домашних побед.",

                    "evidence":
                        {
                            "home_win_rate":
                                round(
                                    home_rate,
                                    3,
                                ),

                            "draw_rate":
                                round(
                                    draw_rate,
                                    3,
                                ),

                            "away_win_rate":
                                round(
                                    away_wins
                                    / len(matches),
                                    3,
                                ),
                        },
                }
            )

        if draw_rate >= 0.40:

            patterns.append(
                {
                    "type":
                        "high_draw_rate",

                    "strength":
                        _pattern_strength(
                            draw_rate
                            - 0.33
                        ),

                    "occurrences":
                        draws,

                    "description":
                        "Повышенная доля "
                        "ничьих.",

                    "evidence":
                        {
                            "draw_rate":
                                round(
                                    draw_rate,
                                    3,
                                )
                        },
                }
            )

        # ----------------------------------------------------
        # TEAM PATTERNS
        # ----------------------------------------------------

        for team, stats in team_stats.items():

            if stats["matches"] < 2:
                continue

            # ATTACK

            if (
                stats["win_rate"] >= 0.75
                and
                stats["goals_for_avg"] >= 2.0
            ):

                patterns.append(
                    {
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
                            f"{team}: "
                            "сильная "
                            "результативная форма.",
                    }
                )

            # DEFENSE

            if (
                stats[
                    "clean_sheet_rate"
                ] >= 0.50
                and
                stats[
                    "goals_against_avg"
                ] <= 0.75
            ):

                patterns.append(
                    {
                        "type":
                            "team_defense_strength",

                        "team": team,

                        "strength":
                            _pattern_strength(
                                stats[
                                    "clean_sheet_rate"
                                ]
                            ),

                        "occurrences":
                            stats["matches"],

                        "description":
                            f"{team}: "
                            "сильная "
                            "оборонительная форма.",
                    }
                )

        return patterns

    # ========================================================
    # PREDICTIONS
    # ========================================================

    def _get_prediction_accuracy(
        self,
    ) -> List[Dict[str, Any]]:

        """
        Получает прогнозы FAJ для завершённых матчей.

        sqlite3.Row всегда преобразуется в dict.
        """

        finished = (
            self._get_finished_matches()
        )

        predictions: List[
            Dict[str, Any]
        ] = []

        for match in finished:

            match_id = match.get("id")

            if match_id is None:
                continue

            try:

                raw_preds = (
                    self.db.get_predictions_by_match(
                        match_id
                    )
                )

            except Exception as exc:

                logger.warning(
                    "Ошибка получения "
                    "прогнозов для матча %s: %s",
                    match_id,
                    exc,
                )

                continue

            for raw_pred in (
                raw_preds or []
            ):

                pred = _row_to_dict(
                    raw_pred
                )

                if not pred:
                    continue

                status = pred.get(
                    "prediction_status"
                )

                # Если статус существует,
                # анализируем только active.
                if (
                    status is not None
                    and status != "active"
                ):
                    continue

                predictions.append(
                    {
                        "match_id":
                            match_id,

                        "predicted_home":
                            pred.get(
                                "predicted_home"
                            ),

                        "predicted_away":
                            pred.get(
                                "predicted_away"
                            ),

                        "actual_home":
                            match.get(
                                "result_home_goals"
                            ),

                        "actual_away":
                            match.get(
                                "result_away_goals"
                            ),
                    }
                )

        logger.info(
            "FAJ Learning: найдено "
            "прогнозов для анализа: %s",
            len(predictions),
        )

        return predictions

    # ========================================================
    # PREDICTION ERROR ANALYSIS
    # ========================================================

    def _analyze_prediction_errors(
        self,
        predictions: List[
            Dict[str, Any]
        ],
    ) -> List[Dict[str, Any]]:

        errors: List[int] = []

        for pred in predictions:

            ph = pred.get(
                "predicted_home"
            )

            pa = pred.get(
                "predicted_away"
            )

            ah = pred.get(
                "actual_home"
            )

            aa = pred.get(
                "actual_away"
            )

            if None in (
                ph,
                pa,
                ah,
                aa,
            ):

                continue

            try:

                ph = int(ph)
                pa = int(pa)

                ah = int(ah)
                aa = int(aa)

            except (
                TypeError,
                ValueError,
            ):

                continue

            errors.append(
                abs(ph - ah)
                +
                abs(pa - aa)
            )

        if not errors:
            return []

        avg_error = mean(
            errors
        )

        if avg_error < 1.50:
            return []

        return [
            {
                "type":
                    "prediction_score_error_high",

                "strength":
                    _pattern_strength(
                        avg_error - 1.0
                    ),

                "occurrences":
                    len(errors),

                "description":
                    "Средняя ошибка "
                    "точного счёта выше "
                    "допустимого уровня.",

                "evidence":
                    {
                        "average_score_error":
                            round(
                                avg_error,
                                3,
                            )
                    },
            }
        ]

    # ========================================================
    # PARAMETERS
    # ========================================================

    def _load_parameters(
        self,
    ) -> Dict[str, float]:

        """
        Загружает текущие параметры FAJ.

        Если параметр отсутствует,
        используется DEFAULT_PARAMETERS.
        """

        params = dict(
            DEFAULT_PARAMETERS
        )

        for param_name in params.keys():

            try:

                value = (
                    self.db.get_parameter(
                        "learning",
                        param_name,
                    )
                )

            except Exception as exc:

                logger.warning(
                    "Ошибка загрузки "
                    "параметра %s: %s",
                    param_name,
                    exc,
                )

                continue

            if value is not None:

                params[param_name] = (
                    _safe_float(
                        value,
                        params[param_name],
                    )
                )

        return params

    # ========================================================
    # PARAMETER ADJUSTMENT
    # ========================================================

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

        changes: List[
            Dict[str, Any]
        ] = []

        for pattern in patterns:

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

            strength = _safe_float(
                pattern.get(
                    "strength"
                )
            )

            step = _clamp(
                strength
                * 0.01
                * PATTERN_WEIGHT,

                0.0,
                MAX_PARAMETER_STEP,
            )

            pattern_type = pattern.get(
                "type"
            )

            parameter = None
            direction = 0

            # ------------------------------------------------
            # PATTERN -> PARAMETER
            # ------------------------------------------------

            if (
                pattern_type
                == "league_low_scoring"
            ):

                parameter = "defense"
                direction = 1

            elif (
                pattern_type
                == "league_high_scoring"
            ):

                parameter = "attack"
                direction = 1

            elif (
                pattern_type
                == "high_btts"
            ):

                parameter = "attack"
                direction = 1

            elif (
                pattern_type
                == "low_btts"
            ):

                parameter = "defense"
                direction = 1

            elif (
                pattern_type
                == "home_advantage_strong"
            ):

                parameter = "mentality"
                direction = 1

            elif (
                pattern_type
                == "team_attack_strength"
            ):

                parameter = "attack"
                direction = 1

            elif (
                pattern_type
                == "team_defense_strength"
            ):

                parameter = "defense"
                direction = 1

            elif (
                pattern_type
                == "prediction_score_error_high"
            ):

                # Пока не меняем параметр
                # автоматически.
                continue

            # ------------------------------------------------
            # VALIDATION
            # ------------------------------------------------

            if (
                parameter is None
                or
                parameter
                not in new_parameters
                or
                direction == 0
            ):

                continue

            old_value = (
                new_parameters[
                    parameter
                ]
            )

            new_value = _clamp(
                old_value
                + step * direction,

                0.01,
                0.50,
            )

            if abs(
                new_value
                - old_value
            ) < 0.000001:

                continue

            new_parameters[
                parameter
            ] = new_value

            changes.append(
                {
                    "parameter":
                        parameter,

                    "old_value":
                        round(
                            old_value,
                            6,
                        ),

                    "new_value":
                        round(
                            new_value,
                            6,
                        ),

                    "delta":
                        round(
                            new_value
                            - old_value,
                            6,
                        ),

                    "reason":
                        pattern_type,

                    "occurrences":
                        occurrences,

                    "strength":
                        round(
                            strength,
                            4,
                        ),
                }
            )

        # ----------------------------------------------------
        # NORMALIZE
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

        return (
            new_parameters,
            changes,
        )

    # ========================================================
    # SAVE LEARNING MEMORY
    # ========================================================

    def _save_learning_memory(
        self,
        matches: List[Dict[str, Any]],
        patterns: List[Dict[str, Any]],
        changes: List[Dict[str, Any]],
        fingerprint: str,
    ) -> None:

        """
        Сохраняет запись обучения.

        learning_memory — единственное место,
        где используется прямой SQL.

        Никаких DELETE.
        """

        payload = {

            "run_id":
                self.run_id,

            "engine":
                ENGINE_NAME,

            "engine_version":
                ENGINE_VERSION,

            "memory_type":
                "batch_learning",

            "title":
                "FAJ пакетное обучение",

            "description":
                (
                    "Проанализировано "
                    f"{len(matches)} "
                    "завершённых матчей."
                ),

            "content":
                json.dumps(
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

            "data":
                json.dumps(
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
                (
                    "high"
                    if len(patterns) >= 3
                    else "normal"
                ),

            "status":
                "active",

            "created_at":
                _now(),
        }

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO learning_memory (
                    run_id,
                    engine,
                    engine_version,
                    memory_type,
                    title,
                    description,
                    content,
                    data,
                    importance,
                    status,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    payload["run_id"],
                    payload["engine"],
                    payload["engine_version"],
                    payload["memory_type"],
                    payload["title"],
                    payload["description"],
                    payload["content"],
                    payload["data"],
                    payload["importance"],
                    payload["status"],
                    payload["created_at"],
                ),
            )

            conn.commit()

        finally:

            conn.close()

    # ========================================================
    # SAVE MODEL PARAMETERS
    # ========================================================

    def _save_model_parameters(
        self,
        parameters: Dict[str, float],
        changes: List[Dict[str, Any]],
    ) -> None:

        """
        Сохраняет параметры через FAJDatabase.

        Используется versioning API.
        """

        for (
            param_name,
            param_value,
        ) in parameters.items():

            old_value = (
                self.db.get_parameter(
                    "learning",
                    param_name,
                )
            )

            self.db.set_model_parameter(
                model_version=ENGINE_VERSION,

                category="learning",

                parameter=param_name,

                value=param_value,

                description=(
                    "Learning adjustment: "
                    f"{self.run_id}"
                ),

                group_name="learning",
            )

            if (
                old_value is not None
                and
                abs(
                    old_value
                    - param_value
                )
                > 0.000001
            ):

                self.db.record_parameter_history(
                    parameter_name=param_name,

                    group_name="learning",

                    model_version=ENGINE_VERSION,

                    old_value=old_value,

                    new_value=param_value,

                    delta=(
                        param_value
                        - old_value
                    ),

                    reason="batch_learning",

                    confidence=0.8,
                )

        logger.info(
            "Сохранено %s параметров "
            "через set_model_parameter()",
            len(parameters),
        )


# ============================================================
# PUBLIC API
# ============================================================

def run_learning(
    force: bool = False,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:

    """
    Главная точка входа Learning Engine.
    """

    return LearningEngine(
        db=db
    ).run(
        force=force
    )


# ============================================================
# DIRECT EXECUTION
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

    result = run_learning()

    print("=" * 70)
    print(
        "FAJ LEARNING ENGINE v2.3 "
        "— MEMORY HARDENED"
    )
    print("=" * 70)

    print(
        f"Успех: "
        f"{result['success']}"
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

        print(
            f"❌ {error}"
        )

    print("=" * 70)
