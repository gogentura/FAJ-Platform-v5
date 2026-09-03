#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
CORNERS MODEL v1.0
============================================================

Назначение
----------

CornersModel анализирует фактическую историю угловых команды.

Модель НЕ:
    - изменяет xG;
    - изменяет вероятность;
    - изменяет счёт;
    - применяет bookmaker odds;
    - создаёт искусственные коэффициенты;
    - интерпретирует 6+ угловых как автоматический гол;
    - штрафует/бонусит команду за результат;
    - изменяет FormContext.

Архитектура:

    FormContext
         │
         ▼
    CornersModel
         │
         ▼
    CornerState

История является первичной информацией.
Средние, recent и trend являются производными.

Важно:

    None != 0

Отсутствующее значение не превращается в ноль.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional
import math


CORNERS_MODEL_VERSION = "1.0"

MAX_HISTORY_MATCHES = 6


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Безопасное преобразование значения в float.

    None и пустые значения сохраняются как None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        text = str(value).strip()

        if not text:
            return None

        text = text.replace(",", ".")

        result = float(text)

        if not math.isfinite(result):
            return None

        return result

    except (TypeError, ValueError):
        return None


def _get_value(
    record: Any,
    *keys: str,
) -> Any:
    """
    Получение значения из dict / sqlite3.Row / объекта.
    """

    if record is None:
        return None

    for key in keys:

        if isinstance(record, dict):
            if key in record:
                return record[key]

        try:
            if key in record.keys():
                return record[key]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(record, key)
        except AttributeError:
            pass

    return None


def _numeric_values(
    values: Iterable[Any],
) -> List[float]:
    """
    Оставляет только реальные числовые наблюдения.
    """

    result: List[float] = []

    for value in values:

        number = _safe_float(value)

        if number is not None:
            result.append(number)

    return result


def _average(
    values: Iterable[Any],
) -> Optional[float]:
    """
    Arithmetic mean.

    None не считается нулём.
    """

    numeric = _numeric_values(values)

    if not numeric:
        return None

    return sum(numeric) / len(numeric)


def _chronological_history(
    values: Iterable[Any],
) -> List[Optional[float]]:
    """
    Приводит историю к единому порядку:

        старый → новый

    FormContext текущей версии может хранить
    recent history как:

        новый → старый

    Поэтому для моделей входная последовательность
    нормализуется здесь.

    Если история уже задана старый → новый,
    этот helper предполагает, что вызывающая сторона
    передала chronological=True через отдельную функцию.

    Для FormContext по умолчанию используется reverse.
    """

    result = [
        _safe_float(value)
        for value in values
    ]

    return list(reversed(result))


def _recent_mean(
    chronological_values: Iterable[Any],
) -> Optional[float]:
    """
    Среднее последних доступных наблюдений.

    Без дополнительных весов.

    Последний доступный период определяется
    по хронологическому порядку.
    """

    values = [
        _safe_float(value)
        for value in chronological_values
    ]

    available = [
        value
        for value in values
        if value is not None
    ]

    if not available:
        return None

    return sum(available) / len(available)


def _ols_slope(
    values: Iterable[Any],
) -> Optional[float]:
    """
    OLS slope.

    x = 1..N

    None-наблюдения исключаются.

    Важно:
    порядок должен быть старый → новый.
    """

    points = []

    for index, value in enumerate(values, start=1):

        number = _safe_float(value)

        if number is not None:
            points.append(
                (float(index), number)
            )

    if len(points) < 2:
        return None

    n = float(len(points))

    sum_x = sum(
        x for x, _ in points
    )

    sum_y = sum(
        y for _, y in points
    )

    sum_xy = sum(
        x * y
        for x, y in points
    )

    sum_x2 = sum(
        x * x
        for x, _ in points
    )

    denominator = (
        n * sum_x2
        - sum_x * sum_x
    )

    if denominator == 0:
        return None

    numerator = (
        n * sum_xy
        - sum_x * sum_y
    )

    return numerator / denominator


def _points_rate(
    results: Iterable[Any],
) -> Optional[float]:
    """
    PointsRate:

        W = 3
        D = 1
        L = 0

    PointsRate = points / (3N)

    None results are excluded from N.
    """

    points = 0
    count = 0

    for result in results:

        if result is None:
            continue

        normalized = str(result).strip().upper()

        if normalized == "W":
            points += 3
            count += 1

        elif normalized == "D":
            points += 1
            count += 1

        elif normalized == "L":
            points += 0
            count += 1

    if count == 0:
        return None

    return points / (3.0 * count)


def _recent_points_rate(
    results_chronological: Iterable[Any],
) -> Optional[float]:
    """
    RecentPointsRate.

    Веса:

        1, 2, ..., N

    где N — самый свежий матч.

    Формула:

        Σ(i * points_i)
        ----------------
        3 * Σi
    """

    results = list(results_chronological)

    weighted_points = 0.0
    weight_sum = 0.0

    for index, result in enumerate(results, start=1):

        if result is None:
            continue

        normalized = str(result).strip().upper()

        if normalized == "W":
            points = 3.0

        elif normalized == "D":
            points = 1.0

        elif normalized == "L":
            points = 0.0

        else:
            continue

        weighted_points += index * points
        weight_sum += index

    if weight_sum == 0:
        return None

    return weighted_points / (3.0 * weight_sum)


# ============================================================
# RESULT
# ============================================================

@dataclass
class CornersModelResult:

    version: str
    team: Optional[str]

    matches_available: int

    corners_for_history: List[Optional[float]]
    corners_against_history: List[Optional[float]]

    corners_for_avg: Optional[float]
    corners_against_avg: Optional[float]

    corners_for_recent: Optional[float]
    corners_against_recent: Optional[float]

    corners_for_trend: Optional[float]
    corners_against_trend: Optional[float]

    points_rate: Optional[float]
    recent_points_rate: Optional[float]

    home_corners_expected: Optional[float]
    away_corners_expected: Optional[float]

    total_expected_corners: Optional[float]

    data_coverage: Optional[float]

    formula_status: str

    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# CORNERS MODEL
# ============================================================

class CornersModel:
    """
    Чистая математическая модель угловых.

    Основная baseline formula:

        HomeBaseCorners =
            (
                HomeCornersForAvg
                +
                AwayCornersAgainstAvg
            ) / 2

        AwayBaseCorners =
            (
                AwayCornersForAvg
                +
                HomeCornersAgainstAvg
            ) / 2

    """

    VERSION = CORNERS_MODEL_VERSION

    def __init__(
        self,
        max_history: int = MAX_HISTORY_MATCHES,
    ) -> None:

        self.max_history = max(
            1,
            int(max_history),
        )

    # ========================================================
    # EXTRACT HISTORY
    # ========================================================

    def _extract_history(
        self,
        context: Dict[str, Any],
    ) -> tuple[
        List[Optional[float]],
        List[Optional[float]],
    ]:

        corners_for = context.get(
            "corners_for_history",
            [],
        )

        corners_against = context.get(
            "corners_against_history",
            [],
        )

        corners_for = list(corners_for or [])
        corners_against = list(corners_against or [])

        corners_for = corners_for[
            : self.max_history
        ]

        corners_against = corners_against[
            : self.max_history
        ]

        return (
            [
                _safe_float(value)
                for value in corners_for
            ],
            [
                _safe_float(value)
                for value in corners_against
            ],
        )

    # ========================================================
    # SINGLE TEAM ANALYSIS
    # ========================================================

    def analyze(
        self,
        context: Dict[str, Any],
    ) -> CornersModelResult:

        team = context.get("team")

        corners_for_raw, corners_against_raw = (
            self._extract_history(context)
        )

        # ----------------------------------------------------
        # FormContext history is newest → oldest.
        #
        # Models work internally:
        # oldest → newest
        # ----------------------------------------------------

        corners_for_chronological = (
            _chronological_history(
                corners_for_raw
            )
        )

        corners_against_chronological = (
            _chronological_history(
                corners_against_raw
            )
        )

        results_raw = context.get(
            "results",
            [],
        )

        results_raw = list(
            results_raw or []
        )[
            : self.max_history
        ]

        results_chronological = list(
            reversed(results_raw)
        )

        # ----------------------------------------------------
        # Average
        # ----------------------------------------------------

        corners_for_avg = _average(
            corners_for_chronological
        )

        corners_against_avg = _average(
            corners_against_chronological
        )

        # ----------------------------------------------------
        # Recent
        # ----------------------------------------------------

        corners_for_recent = _recent_mean(
            corners_for_chronological
        )

        corners_against_recent = _recent_mean(
            corners_against_chronological
        )

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------

        corners_for_trend = _ols_slope(
            corners_for_chronological
        )

        corners_against_trend = _ols_slope(
            corners_against_chronological
        )

        # ----------------------------------------------------
        # Result context
        # ----------------------------------------------------

        points_rate = _points_rate(
            results_chronological
        )

        recent_points_rate = _recent_points_rate(
            results_chronological
        )

        # ----------------------------------------------------
        # Coverage
        #
        # History length is the denominator.
        # Missing values are NOT zero.
        # ----------------------------------------------------

        history_length = max(
            len(corners_for_raw),
            len(corners_against_raw),
            len(results_raw),
        )

        available_corner_values = sum(
            1
            for value in corners_for_raw
            if value is not None
        )

        if history_length > 0:

            data_coverage = (
                available_corner_values
                / history_length
            )

        else:
            data_coverage = None

        diagnostics = {
            "history_order_input": (
                "newest_to_oldest"
            ),
            "history_order_internal": (
                "oldest_to_newest"
            ),
            "max_history": self.max_history,
            "corners_for_available": len(
                _numeric_values(
                    corners_for_raw
                )
            ),
            "corners_against_available": len(
                _numeric_values(
                    corners_against_raw
                )
            ),
            "formula": (
                "(team_corners_for_avg + "
                "opponent_corners_against_avg) / 2"
            ),
            "result_context_used": True,
            "result_context_changes_corners": False,
        }

        return CornersModelResult(
            version=self.VERSION,
            team=team,
            matches_available=history_length,
            corners_for_history=corners_for_raw,
            corners_against_history=corners_against_raw,
            corners_for_avg=corners_for_avg,
            corners_against_avg=corners_against_avg,
            corners_for_recent=corners_for_recent,
            corners_against_recent=corners_against_recent,
            corners_for_trend=corners_for_trend,
            corners_against_trend=corners_against_trend,
            points_rate=points_rate,
            recent_points_rate=recent_points_rate,
            home_corners_expected=None,
            away_corners_expected=None,
            total_expected_corners=None,
            data_coverage=data_coverage,
            formula_status="BASELINE_OBSERVATIONAL",
            diagnostics=diagnostics,
        )

    # ========================================================
    # MATCH SYNTHESIS
    # ========================================================

    def synthesize_match(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ) -> Dict[str, Any]:

        home = self.analyze(
            home_context
        )

        away = self.analyze(
            away_context
        )

        home_expected = None
        away_expected = None

        # ----------------------------------------------------
        # Home:
        #
        # Home CF average
        # +
        # Away CA average
        # ----------------
        # 2
        # ----------------------------------------------------

        if (
            home.corners_for_avg is not None
            and away.corners_against_avg is not None
        ):

            home_expected = (
                home.corners_for_avg
                + away.corners_against_avg
            ) / 2.0

        # ----------------------------------------------------
        # Away:
        #
        # Away CF average
        # +
        # Home CA average
        # ----------------
        # 2
        # ----------------------------------------------------

        if (
            away.corners_for_avg is not None
            and home.corners_against_avg is not None
        ):

            away_expected = (
                away.corners_for_avg
                + home.corners_against_avg
            ) / 2.0

        total_expected = None

        if (
            home_expected is not None
            and away_expected is not None
        ):

            total_expected = (
                home_expected
                + away_expected
            )

        return {
            "version": self.VERSION,

            "home": {
                **home.to_dict(),
                "home_corners_expected": (
                    home_expected
                ),
                "formula_status": (
                    "BASELINE_SYNTHESIS"
                    if home_expected is not None
                    else "UNDEFINED_WITHOUT_BASELINE"
                ),
            },

            "away": {
                **away.to_dict(),
                "away_corners_expected": (
                    away_expected
                ),
                "formula_status": (
                    "BASELINE_SYNTHESIS"
                    if away_expected is not None
                    else "UNDEFINED_WITHOUT_BASELINE"
                ),
            },

            "home_corners_expected": (
                home_expected
            ),

            "away_corners_expected": (
                away_expected
            ),

            "total_expected_corners": (
                total_expected
            ),

            "formula_status": (
                "BASELINE_SYNTHESIS"
                if total_expected is not None
                else "UNDEFINED_WITHOUT_BASELINE"
            ),

            "affects_goal_model": False,
            "affects_probability_model": False,
            "affects_score_model": False,
        }


# ============================================================
# PUBLIC HELPERS
# ============================================================

def analyze_corners(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Удобная функция для анализа одной команды.
    """

    return CornersModel().analyze(
        context
    ).to_dict()


def synthesize_corners_match(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Удобная функция для baseline synthesis матча.
    """

    return CornersModel().synthesize_match(
        home_context,
        away_context,
    )
