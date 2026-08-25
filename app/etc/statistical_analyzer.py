#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Statistical Analyzer v2.0
============================================================

app/etc/statistical_analyzer.py

НАЗНАЧЕНИЕ
-----------

Statistical Analyzer является чистым аналитическим слоем ETC.

Он получает УЖЕ ВЫБРАННЫЕ BatchController матчи и превращает
фактические данные в объективные статистические наблюдения.

АРХИТЕКТУРА:

    match_results
          +
    match_statistics
          ↓
    StatisticalAnalyzer
          ↓
    objective observations
          ↓
    ETCLearningEngine
          ↓
    LearningMemory
          ↓
    ETC

ВАЖНО
-----

МОДУЛЬ НЕ:

    - обучает модель;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет календарь;
    - удаляет данные;
    - записывает learning_memory;
    - запускает prediction pipeline;
    - самостоятельно принимает решения об изменении модели.

МОДУЛЬ ТОЛЬКО:

    - читает факты;
    - рассчитывает производные статистические показатели;
    - сравнивает голы и observed xG;
    - агрегирует показатели команд;
    - агрегирует показатели batch;
    - возвращает результат ETC.

ИСТОЧНИКИ:

    Счёт:
        match_results

    Фактическая статистика:
        match_statistics

    Календарь:
        matches

ЕДИНЫЙ ИСТОЧНИК СХЕМЫ:

    app.database.FAJDatabase

============================================================

ETC PRINCIPLE:

    FACTS
      ↓
    ANALYZER
      ↓
    OBSERVATIONS
      ↓
    LEARNING ENGINE
      ↓
    MEMORY

============================================================

ИСПРАВЛЕНИЯ v2.0
============================================================

1. analyze_match() теперь возвращает СТАБИЛЬНЫЙ КОНТРАКТ:

   УСПЕХ:
       {
           "success": True,
           "status": "analyzed",
           "match_id": match_id,
           "observations": [...],      # обязательное поле
           "memory_events": [...],     # optional, может быть пустым
           "prediction": {...},        # optional
           "fact": {...},             # optional
           "xg": {...},               # optional
           "summary": {...},          # обязательное поле
           "created_at": "..."
       }

   ОШИБКА:
       {
           "success": False,
           "status": "analysis_failed",
           "match_id": match_id,
           "observations": [],
           "memory_events": [],
           "prediction": None,
           "fact": None,
           "xg": None,
           "errors": [...],
           "error": "...",
           "created_at": "..."
       }

2. memory_events теперь OPTIONAL:

   memory_events НЕ является обязательным результатом
   StatisticalAnalyzer.

   ETCLearningEngine сам строит memory_events из:
       - observations
       - prediction + fact
       - xg
       - analysis_completed fallback

3. observations стал ОБЯЗАТЕЛЬНЫМ полем.

4. Добавлен параметр prediction, fact, xg в analyze_match()
   для передачи внешних данных.

============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase

logger = logging.getLogger(__name__)

ANALYZER_VERSION = "2.0"
ANALYZER_NAME = "FAJ ETC Statistical Analyzer"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """Текущее время в ISO формате."""
    return datetime.now().isoformat()


def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование в float.
    """

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
    """
    Безопасное преобразование в int.

    ВАЖНО:

    Для голов используется default=-1,
    чтобы отличить None от 0.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):

        return default


def _average(
    values: List[float],
) -> Optional[float]:
    """
    Среднее значение.
    """

    if not values:
        return None

    return sum(values) / len(values)


def _round(
    value: Optional[float],
    digits: int = 4,
) -> Optional[float]:
    """
    Безопасное округление.
    """

    if value is None:
        return None

    return round(value, digits)


# ============================================================
# MAIN CLASS
# ============================================================

class StatisticalAnalyzer:
    """
    Чистый статистический анализатор ETC.

    Получает факты и возвращает объективные наблюдения.

    Никаких изменений модели здесь не производится.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC — BATCH
    # ========================================================

    def analyze_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Анализирует конкретный batch матчей.

        ВАЖНО:

        Список matches должен приходить от BatchController
        либо быть явно передан ETC.

        Метод НЕ выбирает самостоятельно новые матчи.

        ВОЗВРАЩАЕТ:
            {
                "success": bool,
                "matches_analyzed": int,
                "match_results": [...],
                "team_statistics": [...],
                "league_statistics": {...},
                "observations": [...],
                "errors": [...]
            }
        """

        result: Dict[str, Any] = {
            "success": False,

            "version": ANALYZER_VERSION,
            "engine": ANALYZER_NAME,

            "matches_requested": len(matches or []),
            "matches_analyzed": 0,

            "teams_analyzed": 0,

            "league_statistics": {},

            "team_statistics": [],

            "match_results": [],

            "observations": [],

            "errors": [],
        }

        if not matches:

            result["errors"].append(
                "Нет матчей для статистического анализа."
            )

            return result

        try:

            team_data: Dict[int, Dict[str, Any]] = {}

            analyzed_matches: List[Dict[str, Any]] = []

            # ------------------------------------------------
            # ANALYZE EACH MATCH
            # ------------------------------------------------

            for match in matches:

                if not isinstance(match, dict):

                    result["errors"].append(
                        "Пропущена некорректная запись матча."
                    )

                    continue

                analyzed = self._analyze_match_data(
                    match
                )

                if analyzed is None:

                    match_id = _safe_int(
                        match.get("id")
                    )

                    result["errors"].append(
                        f"Матч {match_id}: "
                        f"недостаточно фактических данных."
                    )

                    continue

                analyzed_matches.append(
                    analyzed
                )

                self._add_match_to_team_statistics(
                    team_data=team_data,
                    analyzed=analyzed,
                    home=True,
                )

                self._add_match_to_team_statistics(
                    team_data=team_data,
                    analyzed=analyzed,
                    home=False,
                )

            # ------------------------------------------------
            # MATCH COUNT
            # ------------------------------------------------

            result["matches_analyzed"] = len(
                analyzed_matches
            )

            result["match_results"] = (
                analyzed_matches
            )

            # ------------------------------------------------
            # LEAGUE STATISTICS
            # ------------------------------------------------

            result["league_statistics"] = (
                self._build_league_statistics(
                    analyzed_matches
                )
            )

            # ------------------------------------------------
            # TEAM STATISTICS
            # ------------------------------------------------

            result["team_statistics"] = (
                self._finalize_team_statistics(
                    team_data
                )
            )

            result["teams_analyzed"] = len(
                result["team_statistics"]
            )

            # ------------------------------------------------
            # OBJECTIVE OBSERVATIONS
            # ------------------------------------------------

            result["observations"] = (
                self._build_observations(
                    analyzed_matches=analyzed_matches,
                    team_statistics=result[
                        "team_statistics"
                    ],
                    league_statistics=result[
                        "league_statistics"
                    ],
                )
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if analyzed_matches:

                result["success"] = True

            else:

                result["success"] = False

                if not result["errors"]:

                    result["errors"].append(
                        "Не удалось проанализировать ни одного матча."
                    )

            logger.info(
                "ETC Statistical Analyzer: "
                "requested=%s analyzed=%s teams=%s",
                len(matches),
                result["matches_analyzed"],
                result["teams_analyzed"],
            )

            return result

        except Exception as exc:

            logger.exception(
                "ETC Statistical Analyzer failed"
            )

            result["errors"].append(
                str(exc)
            )

            return result

    # ========================================================
    # PUBLIC — SINGLE MATCH (НОВЫЙ КОНТРАКТ v2.0)
    # ========================================================

    def analyze_match(
        self,
        match_id: int,
        prediction: Optional[Dict[str, Any]] = None,
        fact: Optional[Dict[str, Any]] = None,
        xg: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует один конкретный матч.

        НОВЫЙ КОНТРАКТ v2.0:

            memory_events — OPTIONAL
            observations — OBLIGATORY

        ВОЗВРАЩАЕТ СТАБИЛЬНЫЙ DICT:

            УСПЕХ:
                {
                    "success": True,
                    "status": "analyzed",
                    "match_id": match_id,
                    "observations": [...],
                    "memory_events": [...],
                    "prediction": {...} or None,
                    "fact": {...} or None,
                    "xg": {...} or None,
                    "summary": {...},
                    "created_at": "..."
                }

            ОШИБКА:
                {
                    "success": False,
                    "status": "analysis_failed",
                    "match_id": match_id,
                    "observations": [],
                    "memory_events": [],
                    "prediction": None,
                    "fact": None,
                    "xg": None,
                    "errors": [...],
                    "error": "...",
                    "created_at": "..."
                }
        """

        # ----------------------------------------------------
        # БАЗОВЫЙ РЕЗУЛЬТАТ
        # ----------------------------------------------------

        result: Dict[str, Any] = {
            "success": False,

            "status": "analysis_failed",

            "version": ANALYZER_VERSION,
            "engine": ANALYZER_NAME,

            "match_id": match_id,

            "observations": [],

            "memory_events": [],

            "prediction": None,

            "fact": None,

            "xg": None,

            "summary": {},

            "errors": [],

            "error": None,

            "created_at": _now(),
        }

        try:

            # ----------------------------------------------------
            # 1. ПОЛУЧАЕМ ДАННЫЕ ИЗ БД
            # ----------------------------------------------------

            matches = self.db.get_matches()

            match = next(
                (
                    item
                    for item in matches
                    if _safe_int(
                        item.get("id")
                    ) == _safe_int(match_id)
                ),
                None,
            )

            if not match:

                result["errors"].append(
                    f"Матч {match_id} не найден."
                )

                result["error"] = (
                    f"Матч {match_id} не найден."
                )

                return result

            # ----------------------------------------------------
            # 2. АНАЛИЗИРУЕМ МАТЧ
            # ----------------------------------------------------

            analyzed = self._analyze_match_data(
                match
            )

            if analyzed is None:

                result["errors"].append(
                    f"Матч {match_id}: "
                    f"недостаточно фактической статистики."
                )

                result["error"] = (
                    f"Матч {match_id}: "
                    f"недостаточно фактической статистики."
                )

                return result

            # ----------------------------------------------------
            # 3. СТРОИМ НАБЛЮДЕНИЯ (ОБЯЗАТЕЛЬНО)
            # ----------------------------------------------------

            observations = (
                self._build_match_observations(
                    analyzed
                )
            )

            # ----------------------------------------------------
            # 4. ФОРМИРУЕМ СТАБИЛЬНЫЙ ОТВЕТ
            # ----------------------------------------------------

            result["success"] = True

            result["status"] = "analyzed"

            # observations — ОБЯЗАТЕЛЬНОЕ поле
            result["observations"] = observations

            # memory_events — OPTIONAL, может быть пустым
            result["memory_events"] = []

            # prediction, fact, xg — если переданы
            if prediction:
                result["prediction"] = prediction

            if fact:
                result["fact"] = fact

            if xg:
                result["xg"] = xg

            # summary — ОБЯЗАТЕЛЬНОЕ поле
            result["summary"] = {
                "match_id": match_id,
                "home_goals": analyzed.get("home_goals"),
                "away_goals": analyzed.get("away_goals"),
                "total_goals": analyzed.get("total_goals"),
                "btts": analyzed.get("btts"),
                "over_25": analyzed.get("over_25"),
                "over_35": analyzed.get("over_35"),
                "home_has_xg": analyzed.get("home", {}).get("available", False),
                "away_has_xg": analyzed.get("away", {}).get("available", False),
                "observations_count": len(observations),
            }

            return result

        except Exception as exc:

            logger.exception(
                "ETC analysis failed for match=%s",
                match_id,
            )

            result["errors"].append(
                str(exc)
            )

            result["error"] = str(exc)

            return result

    # ========================================================
    # MATCH ANALYSIS
    # ========================================================

    def _analyze_match_data(
        self,
        match: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Собирает объективные факты одного матча.

        ВАЖНОЕ ИСПРАВЛЕНИЕ v1.3/v2.0:

        Голы проверяются строго:

            home_goals = _safe_int(home_goals_raw, default=-1)
            away_goals = _safe_int(away_goals_raw, default=-1)

            if home_goals < 0: return None
            if away_goals < 0: return None

        Это отличает:

            0 — валидный результат
            -1 — отсутствие факта
        """

        match_id = _safe_int(
            match.get("id")
        )

        if match_id <= 0:
            return None

        home_team_id = _safe_int(
            match.get("home_team_id")
        )

        away_team_id = _safe_int(
            match.get("away_team_id")
        )

        if home_team_id <= 0:
            return None

        if away_team_id <= 0:
            return None

        # ----------------------------------------------------
        # FACT RESULT
        # ----------------------------------------------------

        match_result = self.db.get_match_result(
            match_id
        )

        if not match_result:
            return None

        home_goals_raw = match_result.get(
            "home_goals"
        )

        away_goals_raw = match_result.get(
            "away_goals"
        )

        # ✅ ИСПРАВЛЕНО v1.3
        # default=-1 чтобы отличить None от 0
        home_goals = _safe_int(
            home_goals_raw,
            default=-1,
        )

        away_goals = _safe_int(
            away_goals_raw,
            default=-1,
        )

        # 0 — валидный результат
        # -1 — отсутствие факта
        if home_goals < 0:
            return None

        if away_goals < 0:
            return None

        # ----------------------------------------------------
        # FACT STATISTICS
        # ----------------------------------------------------

        home_stats = (
            self._get_team_match_statistics(
                match_id=match_id,
                team_id=home_team_id,
            )
        )

        away_stats = (
            self._get_team_match_statistics(
                match_id=match_id,
                team_id=away_team_id,
            )
        )

        # ✅ ОСТАВЛЕНО v1.3
        # Частичная статистика разрешена.
        # Если статистика есть хотя бы у одной команды,
        # матч принимается.
        if not home_stats and not away_stats:
            return None

        home_metrics = (
            self._calculate_team_match_metrics(
                stats=home_stats,
                goals=home_goals,
            )
        )

        away_metrics = (
            self._calculate_team_match_metrics(
                stats=away_stats,
                goals=away_goals,
            )
        )

        return {
            "match_id": match_id,

            "season_id": match.get(
                "season_id"
            ),

            "round_id": match.get(
                "round_id"
            ),

            "match_date": (
                match.get("match_date")
                or match.get("date")
            ),

            "league": (
                match.get("league")
                or match.get("competition")
                or match.get("competition_name")
                or match.get("league_name")
            ),

            "home_team_id": home_team_id,
            "away_team_id": away_team_id,

            "home_goals": home_goals,
            "away_goals": away_goals,

            "home_result": self._result(
                home_goals,
                away_goals,
            ),

            "away_result": self._result(
                away_goals,
                home_goals,
            ),

            "total_goals": (
                home_goals + away_goals
            ),

            "btts": (
                home_goals > 0
                and away_goals > 0
            ),

            "over_25": (
                home_goals + away_goals > 2
            ),

            "over_35": (
                home_goals + away_goals > 3
            ),

            "home": home_metrics,

            "away": away_metrics,
        }

    # ========================================================
    # RAW MATCH STATISTICS
    # ========================================================

    def _get_team_match_statistics(
        self,
        match_id: int,
        team_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает фактическую статистику команды
        конкретного матча.

        Только SELECT.

        Никаких изменений БД.
        """

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM match_statistics
                WHERE match_id = ?
                  AND team_id = ?
                LIMIT 1
                """,
                (
                    match_id,
                    team_id,
                ),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return dict(row)

        finally:

            conn.close()

    # ========================================================
    # MATCH METRICS
    # ========================================================

    def _calculate_team_match_metrics(
        self,
        stats: Optional[Dict[str, Any]],
        goals: int,
    ) -> Dict[str, Any]:
        """
        Производные показатели команды в одном матче.

        ВАЖНО:

        Это не модель и не обучение.

        Это только математическое описание факта.
        """

        if not stats:

            return {
                "available": False,

                "xg": None,
                "goals": goals,

                "possession": None,

                "shots": None,
                "shots_on_target": None,

                "corners": None,

                "fouls": None,
                "yellow_cards": None,
                "red_cards": None,

                "big_chances": None,
                "saves": None,

                "passes": None,
                "pass_accuracy": None,

                "xg_conversion": None,
                "shot_conversion": None,
                "shot_on_target_conversion": None,

                "finishing_overperformance": None,
            }

        # ✅ ИСПРАВЛЕНО v1.3
        # _safe_int с default=-1 для статистики
        # Чтобы отличить отсутствие данных от 0
        xg = _safe_float(
            stats.get("xg")
        )

        shots = _safe_int(
            stats.get("shots"),
            default=-1,
        )

        shots_on_target = _safe_int(
            stats.get("shots_on_target"),
            default=-1,
        )

        possession = _safe_float(
            stats.get("possession")
        )

        corners = _safe_int(
            stats.get("corners"),
            default=-1,
        )

        fouls = _safe_int(
            stats.get("fouls"),
            default=-1,
        )

        yellow_cards = _safe_int(
            stats.get("yellow_cards"),
            default=-1,
        )

        red_cards = _safe_int(
            stats.get("red_cards"),
            default=-1,
        )

        big_chances = _safe_int(
            stats.get("big_chances"),
            default=-1,
        )

        saves = _safe_int(
            stats.get("saves"),
            default=-1,
        )

        passes = _safe_int(
            stats.get("passes"),
            default=-1,
        )

        pass_accuracy = _safe_float(
            stats.get("pass_accuracy")
        )

        # ----------------------------------------------------
        # xG conversion
        # ----------------------------------------------------

        if xg is not None and xg > 0:

            xg_conversion = (
                goals / xg
            )

        else:

            xg_conversion = None

        # ----------------------------------------------------
        # Shot conversion
        # ----------------------------------------------------

        if shots > 0:

            shot_conversion = (
                goals / shots
            )

        else:

            shot_conversion = None

        # ----------------------------------------------------
        # Shot on target conversion
        # ----------------------------------------------------

        if shots_on_target > 0:

            shot_on_target_conversion = (
                goals / shots_on_target
            )

        else:

            shot_on_target_conversion = None

        # ----------------------------------------------------
        # Finishing overperformance
        # ----------------------------------------------------

        if xg is not None:

            finishing_overperformance = (
                goals - xg
            )

        else:

            finishing_overperformance = None

        return {
            "available": True,

            "xg": _round(
                xg
            ),

            "goals": goals,

            "possession": _round(
                possession,
                2,
            ),

            "shots": shots if shots >= 0 else None,

            "shots_on_target": shots_on_target if shots_on_target >= 0 else None,

            "corners": corners if corners >= 0 else None,

            "fouls": fouls if fouls >= 0 else None,

            "yellow_cards": yellow_cards if yellow_cards >= 0 else None,

            "red_cards": red_cards if red_cards >= 0 else None,

            "big_chances": big_chances if big_chances >= 0 else None,

            "saves": saves if saves >= 0 else None,

            "passes": passes if passes >= 0 else None,

            "pass_accuracy": _round(
                pass_accuracy,
                2,
            ),

            "xg_conversion": _round(
                xg_conversion
            ),

            "shot_conversion": _round(
                shot_conversion
            ),

            "shot_on_target_conversion": _round(
                shot_on_target_conversion
            ),

            "finishing_overperformance": _round(
                finishing_overperformance
            ),
        }

    # ========================================================
    # TEAM AGGREGATION
    # ========================================================

    def _add_match_to_team_statistics(
        self,
        team_data: Dict[int, Dict[str, Any]],
        analyzed: Dict[str, Any],
        home: bool,
    ) -> None:
        """
        Добавляет факт одного матча в агрегированную
        статистику команды.
        """

        if home:

            team_id = analyzed[
                "home_team_id"
            ]

            metrics = analyzed[
                "home"
            ]

            opponent_goals = analyzed[
                "away_goals"
            ]

        else:

            team_id = analyzed[
                "away_team_id"
            ]

            metrics = analyzed[
                "away"
            ]

            opponent_goals = analyzed[
                "home_goals"
            ]

        if not metrics.get(
            "available",
            False,
        ):
            return

        if team_id not in team_data:

            team_data[team_id] = {
                "team_id": team_id,

                "matches": 0,

                "wins": 0,
                "draws": 0,
                "losses": 0,

                "goals_for": [],
                "goals_against": [],

                "xg": [],
                "possession": [],

                "shots": [],
                "shots_on_target": [],

                "corners": [],

                "fouls": [],

                "yellow_cards": [],
                "red_cards": [],

                "big_chances": [],
                "saves": [],

                "passes": [],
                "pass_accuracy": [],

                "xg_conversion": [],
                "shot_conversion": [],
                "shot_on_target_conversion": [],

                "finishing_overperformance": [],
            }

        data = team_data[
            team_id
        ]

        data["matches"] += 1

        goals = _safe_int(
            metrics.get("goals")
        )

        data["goals_for"].append(
            goals
        )

        data["goals_against"].append(
            opponent_goals
        )

        if goals > opponent_goals:

            data["wins"] += 1

        elif goals < opponent_goals:

            data["losses"] += 1

        else:

            data["draws"] += 1

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        for field in (
            "xg",
            "possession",
            "shots",
            "shots_on_target",
            "corners",
            "fouls",
            "yellow_cards",
            "red_cards",
            "big_chances",
            "saves",
            "passes",
            "pass_accuracy",
            "xg_conversion",
            "shot_conversion",
            "shot_on_target_conversion",
            "finishing_overperformance",
        ):

            self._append_if_number(
                data[field],
                metrics.get(field),
            )

    @staticmethod
    def _append_if_number(
        target: List[float],
        value: Any,
    ) -> None:
        """
        Добавляет только корректное числовое значение.
        """

        numeric = _safe_float(
            value
        )

        if numeric is not None:

            target.append(
                numeric
            )

    # ========================================================
    # FINAL TEAM STATISTICS
    # ========================================================

    def _finalize_team_statistics(
        self,
        team_data: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Формирует итоговую статистику команд batch.
        """

        result: List[Dict[str, Any]] = []

        for team_id, data in team_data.items():

            matches = max(
                1,
                data["matches"],
            )

            points = (
                data["wins"] * 3
                + data["draws"]
            )

            result.append(
                {
                    "team_id": team_id,

                    "matches": data[
                        "matches"
                    ],

                    "wins": data[
                        "wins"
                    ],

                    "draws": data[
                        "draws"
                    ],

                    "losses": data[
                        "losses"
                    ],

                    "points": points,

                    "points_per_match": round(
                        points / matches,
                        4,
                    ),

                    "win_rate": round(
                        data["wins"] / matches,
                        4,
                    ),

                    "draw_rate": round(
                        data["draws"] / matches,
                        4,
                    ),

                    "loss_rate": round(
                        data["losses"] / matches,
                        4,
                    ),

                    "goals_for_avg": round(
                        sum(
                            data["goals_for"]
                        ) / matches,
                        4,
                    ),

                    "goals_against_avg": round(
                        sum(
                            data["goals_against"]
                        ) / matches,
                        4,
                    ),

                    "goal_difference_avg": round(
                        (
                            sum(
                                data["goals_for"]
                            )
                            -
                            sum(
                                data["goals_against"]
                            )
                        )
                        / matches,
                        4,
                    ),

                    "xg_avg": _round(
                        _average(
                            data["xg"]
                        )
                    ),

                    "possession_avg": _round(
                        _average(
                            data["possession"]
                        ),
                        2,
                    ),

                    "shots_avg": _round(
                        _average(
                            data["shots"]
                        )
                    ),

                    "shots_on_target_avg": _round(
                        _average(
                            data["shots_on_target"]
                        )
                    ),

                    "corners_avg": _round(
                        _average(
                            data["corners"]
                        )
                    ),

                    "fouls_avg": _round(
                        _average(
                            data["fouls"]
                        )
                    ),

                    "yellow_cards_avg": _round(
                        _average(
                            data["yellow_cards"]
                        )
                    ),

                    "red_cards_avg": _round(
                        _average(
                            data["red_cards"]
                        )
                    ),

                    "big_chances_avg": _round(
                        _average(
                            data["big_chances"]
                        )
                    ),

                    "saves_avg": _round(
                        _average(
                            data["saves"]
                        )
                    ),

                    "passes_avg": _round(
                        _average(
                            data["passes"]
                        )
                    ),

                    "pass_accuracy_avg": _round(
                        _average(
                            data["pass_accuracy"]
                        ),
                        2,
                    ),

                    "xg_conversion_avg": _round(
                        _average(
                            data["xg_conversion"]
                        )
                    ),

                    "shot_conversion_avg": _round(
                        _average(
                            data["shot_conversion"]
                        )
                    ),

                    "shot_on_target_conversion_avg": _round(
                        _average(
                            data[
                                "shot_on_target_conversion"
                            ]
                        )
                    ),

                    "finishing_overperformance_avg": _round(
                        _average(
                            data[
                                "finishing_overperformance"
                            ]
                        )
                    ),
                }
            )

        result.sort(
            key=lambda item: (
                item["points"],
                item["goal_difference_avg"],
                item["goals_for_avg"],
            ),
            reverse=True,
        )

        return result

    # ========================================================
    # LEAGUE STATISTICS
    # ========================================================

    def _build_league_statistics(
        self,
        analyzed_matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Агрегированная статистика конкретного batch.

        В отличие от старой версии метод больше не делает
        повторные запросы к match_results и statistics.

        Он работает уже с проверенными фактами.
        """

        if not analyzed_matches:

            return {}

        total_matches = len(
            analyzed_matches
        )

        total_goals = sum(
            _safe_int(
                match.get("total_goals")
            )
            for match in analyzed_matches
        )

        home_wins = sum(
            1
            for match in analyzed_matches
            if match.get("home_result") == "W"
        )

        draws = sum(
            1
            for match in analyzed_matches
            if match.get("home_result") == "D"
        )

        away_wins = sum(
            1
            for match in analyzed_matches
            if match.get("away_result") == "W"
        )

        btts_count = sum(
            1
            for match in analyzed_matches
            if match.get("btts")
        )

        over25_count = sum(
            1
            for match in analyzed_matches
            if match.get("over_25")
        )

        over35_count = sum(
            1
            for match in analyzed_matches
            if match.get("over_35")
        )

        # ----------------------------------------------------
        # TEAM-LEVEL OBSERVATIONS
        # ----------------------------------------------------

        xg_values: List[float] = []

        shots_values: List[float] = []

        shots_on_target_values: List[float] = []

        possession_values: List[float] = []

        corners_values: List[float] = []

        for match in analyzed_matches:

            for side in (
                "home",
                "away",
            ):

                stats = match.get(
                    side,
                    {},
                )

                if not stats.get(
                    "available",
                    False,
                ):
                    continue

                self._append_if_number(
                    xg_values,
                    stats.get("xg"),
                )

                self._append_if_number(
                    shots_values,
                    stats.get("shots"),
                )

                self._append_if_number(
                    shots_on_target_values,
                    stats.get(
                        "shots_on_target"
                    ),
                )

                self._append_if_number(
                    possession_values,
                    stats.get(
                        "possession"
                    ),
                )

                self._append_if_number(
                    corners_values,
                    stats.get(
                        "corners"
                    ),
                )

        return {
            "matches": total_matches,

            "goals_total": total_goals,

            "goals_per_match": round(
                total_goals
                / total_matches,
                4,
            ),

            "home_win_rate": round(
                home_wins
                / total_matches,
                4,
            ),

            "draw_rate": round(
                draws
                / total_matches,
                4,
            ),

            "away_win_rate": round(
                away_wins
                / total_matches,
                4,
            ),

            "btts_rate": round(
                btts_count
                / total_matches,
                4,
            ),

            "over25_rate": round(
                over25_count
                / total_matches,
                4,
            ),

            "over35_rate": round(
                over35_count
                / total_matches,
                4,
            ),

            "observed_xg_per_team_avg": _round(
                _average(
                    xg_values
                )
            ),

            "shots_per_team_avg": _round(
                _average(
                    shots_values
                )
            ),

            "shots_on_target_per_team_avg": _round(
                _average(
                    shots_on_target_values
                )
            ),

            "possession_per_team_avg": _round(
                _average(
                    possession_values
                ),
                2,
            ),

            "corners_per_team_avg": _round(
                _average(
                    corners_values
                )
            ),
        }

    # ========================================================
    # OBSERVATIONS
    # ========================================================

    def _build_observations(
        self,
        analyzed_matches: List[Dict[str, Any]],
        team_statistics: List[Dict[str, Any]],
        league_statistics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Формирует объективные наблюдения для ETC.

        ВАЖНО v2.0:

        Это НЕ learning_memory.

        Это только аналитические сигналы.

        ETCLearningEngine сам решает, какие из них
        превращать в записи памяти.

        memory_events здесь НЕ создаются.
        """

        observations: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # LEAGUE OBSERVATION
        # ----------------------------------------------------

        if league_statistics:

            observations.append(
                {
                    "type": "league_batch_observation",

                    "feature": "goals_per_match",

                    "value": league_statistics.get(
                        "goals_per_match"
                    ),

                    "sample_size": league_statistics.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "league_batch_observation",

                    "feature": "observed_xg_per_team",

                    "value": league_statistics.get(
                        "observed_xg_per_team_avg"
                    ),

                    "sample_size": league_statistics.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "league_batch_observation",

                    "feature": "btts_rate",

                    "value": league_statistics.get(
                        "btts_rate"
                    ),

                    "sample_size": league_statistics.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "league_batch_observation",

                    "feature": "over25_rate",

                    "value": league_statistics.get(
                        "over25_rate"
                    ),

                    "sample_size": league_statistics.get(
                        "matches",
                        0,
                    ),
                }
            )

        # ----------------------------------------------------
        # TEAM OBSERVATIONS
        # ----------------------------------------------------

        for team in team_statistics:

            team_id = team.get(
                "team_id"
            )

            observations.append(
                {
                    "type": "team_batch_observation",

                    "team_id": team_id,

                    "feature": "goals_for_avg",

                    "value": team.get(
                        "goals_for_avg"
                    ),

                    "sample_size": team.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "team_batch_observation",

                    "team_id": team_id,

                    "feature": "goals_against_avg",

                    "value": team.get(
                        "goals_against_avg"
                    ),

                    "sample_size": team.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "team_batch_observation",

                    "team_id": team_id,

                    "feature": "xg_avg",

                    "value": team.get(
                        "xg_avg"
                    ),

                    "sample_size": team.get(
                        "matches",
                        0,
                    ),
                }
            )

            observations.append(
                {
                    "type": "team_batch_observation",

                    "team_id": team_id,

                    "feature": "finishing_overperformance_avg",

                    "value": team.get(
                        "finishing_overperformance_avg"
                    ),

                    "sample_size": team.get(
                        "matches",
                        0,
                    ),
                }
            )

        return observations

    # ========================================================
    # SINGLE MATCH OBSERVATIONS
    # ========================================================

    def _build_match_observations(
        self,
        analyzed: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Объективные наблюдения одного матча.

        Не записываются в memory напрямую.
        """

        observations: List[
            Dict[str, Any]
        ] = []

        match_id = analyzed.get(
            "match_id"
        )

        for side in (
            "home",
            "away",
        ):

            stats = analyzed.get(
                side,
                {},
            )

            if not stats.get(
                "available",
                False,
            ):
                continue

            team_id = analyzed.get(
                f"{side}_team_id"
            )

            observations.append(
                {
                    "type": "match_observation",

                    "match_id": match_id,

                    "team_id": team_id,

                    "side": side,

                    "feature": "finishing_overperformance",

                    "value": stats.get(
                        "finishing_overperformance"
                    ),
                }
            )

            observations.append(
                {
                    "type": "match_observation",

                    "match_id": match_id,

                    "team_id": team_id,

                    "side": side,

                    "feature": "xg",

                    "value": stats.get(
                        "xg"
                    ),
                }
            )

            observations.append(
                {
                    "type": "match_observation",

                    "match_id": match_id,

                    "team_id": team_id,

                    "side": side,

                    "feature": "goals",

                    "value": stats.get(
                        "goals"
                    ),
                }
            )

        return observations

    # ========================================================
    # RESULT
    # ========================================================

    @staticmethod
    def _result(
        goals_for: int,
        goals_against: int,
    ) -> str:
        """
        W / D / L.
        """

        if goals_for > goals_against:

            return "W"

        if goals_for < goals_against:

            return "L"

        return "D"


# ============================================================
# PUBLIC API
# ============================================================

def analyze_statistics(
    matches: List[Dict[str, Any]],
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API пакетного анализа.
    """

    analyzer = StatisticalAnalyzer(
        db=db
    )

    return analyzer.analyze_matches(
        matches
    )


def analyze_match_statistics(
    match_id: int,
    prediction: Optional[Dict[str, Any]] = None,
    fact: Optional[Dict[str, Any]] = None,
    xg: Optional[Dict[str, Any]] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API анализа одного матча с новым контрактом v2.0.
    """

    analyzer = StatisticalAnalyzer(
        db=db
    )

    return analyzer.analyze_match(
        match_id=match_id,
        prediction=prediction,
        fact=fact,
        xg=xg,
    )


# ============================================================
# STATUS
# ============================================================

def get_analyzer_status() -> Dict[str, Any]:
    """
    Технический статус анализатора.
    """

    return {
        "module": ANALYZER_NAME,
        "version": ANALYZER_VERSION,

        "role": "FACT_ANALYSIS",

        "writes_database": False,

        "writes_learning_memory": False,

        "changes_model": False,

        "changes_rating": False,

        "changes_parameters": False,

        "deletes_data": False,

        "source_results": "match_results",

        "source_statistics": "match_statistics",

        "database_layer": "FAJDatabase",

        "memory_events": "OPTIONAL (не создаются здесь)",
    }


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

    print("=" * 70)

    print(
        "FAJ ETC — STATISTICAL ANALYZER"
    )

    print(
        f"Version: {ANALYZER_VERSION}"
    )

    print("=" * 70)

    status = get_analyzer_status()

    for key, value in status.items():

        print(
            f"{key}: {value}"
        )

    print("=" * 70)

    print(
        "Statistical Analyzer готов."
    )

    print(
        "Модуль только читает FACTS "
        "и формирует objective observations."
    )

    print(
        "LearningMemory здесь НЕ вызывается."
    )

    print(
        "memory_events — OPTIONAL, создаются в ETCLearningEngine."
    )

    print("=" * 70)
