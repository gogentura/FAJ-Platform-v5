#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM MODEL v1.0
============================================================

НАЗНАЧЕНИЕ
----------

FormModel v1 НЕ ПРОГНОЗИРУЕТ.

Он измеряет текущее состояние команды на основании
истории последних матчей, переданной FormContext.

Архитектура:

    MatchRecord
        ↓
    FormContext v1.4
        ↓
    PatternState
        ↓
    FormModel v1
        ↓
    FormModelResult

FormModel НЕ:

    - прогнозирует исход;
    - рассчитывает вероятности;
    - рассчитывает GoalModel;
    - изменяет xG;
    - изменяет FAJ Rating;
    - обучает модель;
    - пишет в SQLite;
    - использует bookmaker odds;
    - определяет силу соперника;
    - создаёт composite Form Score;
    - применяет EffectSignal как multiplier.

------------------------------------------------------------
МАТЕМАТИЧЕСКИЙ ПРИНЦИП
------------------------------------------------------------

FormModel измеряет четыре независимых состояния:

    RESULT
    PERFORMANCE
    DYNAMICS
    VENUE

и отдельно предоставляет:

    PATTERN / EFFECT EVIDENCE

Никакие каналы не смешиваются в один score.

------------------------------------------------------------
VERSION
------------------------------------------------------------

FORM_MODEL_VERSION = "1.0"

------------------------------------------------------------
ВАЖНЫЕ ПРАВИЛА
------------------------------------------------------------

1. None никогда не превращается в 0.

2. Отсутствующие значения исключаются только
   из соответствующего среднего.

3. История xG сохраняется полностью.

4. xG и goals — независимые каналы.

5. Difficulty не является силой соперника.

6. Difficulty используется только для описания
   фактической результативности команды в bucket.

7. ResultStrength = RecentPointsRate.

8. FormScore в v1 не определён.

9. Strength в v1 не определён без baseline.

10. Trend — OLS slope без искусственной нормализации.

11. Trend label отделён от numerical slope.

12. Effect signals не изменяют GoalModel.

13. Dark Horse / Lukaku / Kepa / Haaland
    требуют baseline и поэтому в v1 не активируются.

14. Temporal weights 1..6 являются
    RESEARCH_PARAMETER.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================
# VERSION / PARAMETERS
# ============================================================

FORM_MODEL_VERSION = "1.0"

# Research parameter.
# История передаётся от старого к новому:
#
# M1 -> M2 -> ... -> M6
#
# Поэтому последний матч получает максимальный вес.
TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)

TREND_THRESHOLD: Optional[float] = None

GLADIATOR_MIN_WINS = 5
FORTRESS_MIN_HOME_MATCHES = 5
FORTRESS_MIN_HOME_UNBEATEN = 4
LEICESTER_MIN_AWAY_MATCHES = 5
LEICESTER_MIN_AWAY_WINS = 4
GOD_KISS_MIN_AWAY_STREAK = 3


# ============================================================
# ENUM-LIKE CONSTANTS
# ============================================================

RESULT_POINTS = {
    "W": 3.0,
    "D": 1.0,
    "L": 0.0,
}

RESULT_TREND_VALUE = {
    "W": 1.0,
    "D": 0.0,
    "L": -1.0,
}


# ============================================================
# SAFE CONVERSION
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    None / empty / invalid -> None.

    Missing data NEVER becomes zero.
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

        return float(text)

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """
    Safe integer conversion.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)

    except (TypeError, ValueError):
        return None


def _get_value(record: Any, *keys: str) -> Any:
    """
    Unified access for:

        dict
        sqlite3.Row
        dataclass/object
    """

    if record is None:
        return None

    for key in keys:

        if isinstance(record, dict):

            if key in record:
                return record[key]

        try:

            keys_method = record.keys

            if key in keys_method():
                return record[key]

        except (AttributeError, TypeError):
            pass

        try:
            return getattr(record, key)

        except AttributeError:
            pass

    return None


# ============================================================
# RESULT HELPERS
# ============================================================

def _result_to_points(result: Optional[str]) -> Optional[float]:
    """
    W = 3
    D = 1
    L = 0
    """

    if result not in RESULT_POINTS:
        return None

    return RESULT_POINTS[result]


def _result_to_trend_value(
    result: Optional[str],
) -> Optional[float]:

    if result not in RESULT_TREND_VALUE:
        return None

    return RESULT_TREND_VALUE[result]


# ============================================================
# GENERIC MEAN
# ============================================================

def _mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:
    """
    Arithmetic mean.

    None values are excluded.

    Empty collection -> None.
    """

    valid = [
        float(value)
        for value in values
        if value is not None
    ]

    if not valid:
        return None

    return sum(valid) / len(valid)


# ============================================================
# WEIGHTED MEAN
# ============================================================

def _weighted_mean(
    values: Iterable[Optional[float]],
    weights: Iterable[float],
) -> Optional[float]:
    """
    Weighted mean.

    None observations are excluded together
    with their corresponding weights.
    """

    pairs = [
        (float(value), float(weight))
        for value, weight in zip(values, weights)
        if value is not None
    ]

    if not pairs:
        return None

    numerator = sum(
        value * weight
        for value, weight in pairs
    )

    denominator = sum(
        weight
        for _, weight in pairs
    )

    if denominator == 0:
        return None

    return numerator / denominator


# ============================================================
# OLS SLOPE
# ============================================================

def _ols_slope(
    values: Iterable[Optional[float]],
) -> Optional[float]:
    """
    Ordinary Least Squares slope.

    Для наблюдений:

        y1 ... yN

    используются последовательные временные индексы:

        x = 0 ... N-1

    None observations исключаются.

    ВАЖНО:

        slope НЕ нормализуется.

    Возвращается реальный OLS slope
    в единицах исходного показателя за один шаг времени.
    """

    observations = [
        float(value)
        for value in values
        if value is not None
    ]

    n = len(observations)

    if n < 2:
        return None

    x_values = list(
        range(n)
    )

    x_mean = sum(x_values) / n
    y_mean = sum(observations) / n

    numerator = sum(
        (
            x - x_mean
        ) * (
            y - y_mean
        )
        for x, y in zip(
            x_values,
            observations,
        )
    )

    denominator = sum(
        (
            x - x_mean
        ) ** 2
        for x in x_values
    )

    if denominator == 0:
        return None

    return numerator / denominator


# ============================================================
# POPULATION STANDARD DEVIATION
# ============================================================

def _population_std(
    values: Iterable[Optional[float]],
) -> Optional[float]:
    """
    Population standard deviation.

    sigma =
        sqrt(
            1/N *
            sum((x - mean)^2)
        )
    """

    valid = [
        float(value)
        for value in values
        if value is not None
    ]

    if not valid:
        return None

    mean = sum(valid) / len(valid)

    variance = sum(
        (
            value - mean
        ) ** 2
        for value in valid
    ) / len(valid)

    return sqrt(variance)


# ============================================================
# TREND LABEL
# ============================================================

def _trend_label(
    slope: Optional[float],
    threshold: Optional[float],
) -> Optional[str]:
    """
    Converts numerical trend slope into label.

    threshold is intentionally optional.

    Without calibrated/research threshold:

        no label is produced.

    This prevents arbitrary numerical thresholds
    from becoming hidden model logic.
    """

    if slope is None:
        return None

    if threshold is None:
        return None

    if abs(slope) <= threshold:
        return "stable"

    if slope > threshold:
        return "improving"

    if slope < -threshold:
        return "declining"

    return "stable"


# ============================================================
# DIFFICULTY STATE
# ============================================================

@dataclass
class DifficultyState:

    matches: int = 0
    points: float = 0.0
    points_rate: Optional[float] = None

    adjustment: Optional[float] = None

    recent_points_rate: Optional[float] = None


# ============================================================
# EFFECT SIGNAL
# ============================================================

@dataclass
class EffectSignal:

    name: str

    detected: Optional[bool]

    signal: Optional[float]

    confidence: Optional[float]

    evidence: Dict[str, Any]

    status: str = "DESCRIPTIVE_ONLY"


# ============================================================
# FORM MODEL RESULT
# ============================================================

@dataclass
class FormModelResult:

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    version: str

    team: Optional[str]

    matches_count: int

    # --------------------------------------------------------
    # RESULT STATE
    # --------------------------------------------------------

    raw_points: Optional[float]

    points_rate: Optional[float]

    recent_points_rate: Optional[float]

    result_strength: Optional[float]

    # --------------------------------------------------------
    # DIFFICULTY STATE
    # --------------------------------------------------------

    hard_points_rate: Optional[float]

    medium_points_rate: Optional[float]

    easy_points_rate: Optional[float]

    hard_adjustment: Optional[float]

    medium_adjustment: Optional[float]

    easy_adjustment: Optional[float]

    hard_recent_points_rate: Optional[float]

    medium_recent_points_rate: Optional[float]

    easy_recent_points_rate: Optional[float]

    # --------------------------------------------------------
    # PERFORMANCE STATE — GOALS
    # --------------------------------------------------------

    goals_for_avg: Optional[float]

    goals_against_avg: Optional[float]

    # --------------------------------------------------------
    # PERFORMANCE STATE — xG
    # --------------------------------------------------------

    xg_avg: Optional[float]

    xga_avg: Optional[float]

    xg_history: Tuple[Optional[float], ...]

    xga_history: Tuple[Optional[float], ...]

    xg_recent: Optional[float]

    xga_recent: Optional[float]

    xg_trend: Optional[float]

    xga_trend: Optional[float]

    # --------------------------------------------------------
    # REALIZATION
    # --------------------------------------------------------

    finishing_delta: Optional[float]

    finishing_ratio: Optional[float]

    defensive_delta: Optional[float]

    # --------------------------------------------------------
    # DYNAMICS
    # --------------------------------------------------------

    trend_score: Optional[float]

    trend: Optional[str]

    consistency: Optional[float]

    # --------------------------------------------------------
    # VENUE
    # --------------------------------------------------------

    home_points_rate: Optional[float]

    home_coverage: Optional[float]

    away_points_rate: Optional[float]

    away_coverage: Optional[float]

    # --------------------------------------------------------
    # FORM SCORE
    # --------------------------------------------------------

    form_score: Optional[float]

    form_score_status: str

    # --------------------------------------------------------
    # STRENGTH
    # --------------------------------------------------------

    attack_strength: Optional[float]

    defense_strength: Optional[float]

    goal_strength: Optional[float]

    xg_strength: Optional[float]

    realization_strength: Optional[float]

    defensive_xg_strength: Optional[float]

    # --------------------------------------------------------
    # EFFECTS
    # --------------------------------------------------------

    effects: Tuple[EffectSignal, ...]


# ============================================================
# FORM MODEL
# ============================================================

class FormModel:
    """
    FormModel v1.

    Главный принцип:

        MEASURE STATE.
        DO NOT PREDICT.

    Input:

        FormContext v1.4 dictionary/object.

    Output:

        FormModelResult.
    """

    def __init__(
        self,
        temporal_weights: Tuple[
            float, ...
        ] = TEMPORAL_WEIGHTS,
        trend_threshold: Optional[
            float
        ] = TREND_THRESHOLD,
    ) -> None:

        self.temporal_weights = tuple(
            temporal_weights
        )

        self.trend_threshold = (
            trend_threshold
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def analyze(
        self,
        form_context: Any,
        next_venue: Optional[str] = None,
    ) -> FormModelResult:
        """
        Analyze FormContext.

        next_venue is optional contextual input.

        FormModel itself does not query DB.
        """

        team = _get_value(
            form_context,
            "team",
            "team_name",
        )

        matches = self._extract_matches(
            form_context
        )

        results = self._extract_results(
            form_context,
            matches,
        )

        goals_for = self._extract_history(
            form_context,
            matches,
            (
                "goals_for",
                "team_goals",
            ),
        )

        goals_against = self._extract_history(
            form_context,
            matches,
            (
                "goals_against",
                "opponent_goals",
            ),
        )

        xg_history = self._extract_xg_history(
            form_context,
            matches,
            "recent_xg",
            "team_xg",
        )

        xga_history = self._extract_xg_history(
            form_context,
            matches,
            "recent_xga",
            "opponent_xg",
        )

        venues = self._extract_history(
            form_context,
            matches,
            (
                "venue",
                "home_away",
            ),
        )

        difficulties = self._extract_history(
            form_context,
            matches,
            (
                "difficulty",
            ),
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        result_points = [
            _result_to_points(result)
            for result in results
        ]

        raw_points = (
            sum(
                value
                for value in result_points
                if value is not None
            )
            if any(
                value is not None
                for value in result_points
            )
            else None
        )

        valid_result_count = sum(
            1
            for value in result_points
            if value is not None
        )

        points_rate = (
            raw_points
            / (
                3.0
                * valid_result_count
            )
            if raw_points is not None
            and valid_result_count > 0
            else None
        )

        normalized_points = [
            (
                value / 3.0
                if value is not None
                else None
            )
            for value in result_points
        ]

        recent_points_rate = (
            _weighted_mean(
                normalized_points,
                self._weights_for(
                    len(normalized_points)
                ),
            )
        )

        result_strength = (
            recent_points_rate
        )

        # ----------------------------------------------------
        # DIFFICULTY
        # ----------------------------------------------------

        hard = self._difficulty_state(
            difficulties,
            result_points,
            "hard",
            points_rate,
        )

        medium = self._difficulty_state(
            difficulties,
            result_points,
            "medium",
            points_rate,
        )

        easy = self._difficulty_state(
            difficulties,
            result_points,
            "easy",
            points_rate,
        )

        # ----------------------------------------------------
        # GOALS
        # ----------------------------------------------------

        goals_for_avg = _mean(
            goals_for
        )

        goals_against_avg = _mean(
            goals_against
        )

        # ----------------------------------------------------
        # xG
        # ----------------------------------------------------

        xg_avg = _mean(
            xg_history
        )

        xga_avg = _mean(
            xga_history
        )

        # "recent" v1 intentionally remains
        # the diagnostic mean of the six-match window.
        xg_recent = xg_avg
        xga_recent = xga_avg

        xg_trend = _ols_slope(
            xg_history
        )

        xga_trend = _ols_slope(
            xga_history
        )

        # ----------------------------------------------------
        # REALIZATION
        # ----------------------------------------------------

        finishing_delta = (
            goals_for_avg - xg_avg
            if goals_for_avg is not None
            and xg_avg is not None
            else None
        )

        finishing_ratio = (
            goals_for_avg / xg_avg
            if goals_for_avg is not None
            and xg_avg is not None
            and xg_avg > 0
            else None
        )

        defensive_delta = (
            goals_against_avg - xga_avg
            if goals_against_avg is not None
            and xga_avg is not None
            else None
        )

        # ----------------------------------------------------
        # RESULT TREND
        # ----------------------------------------------------

        result_trend_values = [
            _result_to_trend_value(result)
            for result in results
        ]

        trend_score = _ols_slope(
            result_trend_values
        )

        trend = _trend_label(
            trend_score,
            self.trend_threshold,
        )

        # ----------------------------------------------------
        # CONSISTENCY
        # ----------------------------------------------------

        result_std = _population_std(
            result_trend_values
        )

        consistency = (
            1.0 - result_std
            if result_std is not None
            else None
        )

        if consistency is not None:

            consistency = max(
                0.0,
                min(
                    1.0,
                    consistency,
                ),
            )

        # ----------------------------------------------------
        # VENUE
        # ----------------------------------------------------

        home_points_rate = (
            self._venue_points_rate(
                venues,
                result_points,
                "дома",
            )
        )

        away_points_rate = (
            self._venue_points_rate(
                venues,
                result_points,
                "гости",
            )
        )

        home_matches = sum(
            1
            for venue in venues
            if self._normalize_venue(
                venue
            ) == "дома"
        )

        away_matches = sum(
            1
            for venue in venues
            if self._normalize_venue(
                venue
            ) == "гости"
        )

        total_window = len(
            results
        )

        home_coverage = (
            home_matches / total_window
            if total_window > 0
            else None
        )

        away_coverage = (
            away_matches / total_window
            if total_window > 0
            else None
        )

        # ----------------------------------------------------
        # EFFECTS
        # ----------------------------------------------------

        effects = self._detect_effects(
            results=results,
            venues=venues,
            next_venue=next_venue,
            difficulties=difficulties,
            result_points=result_points,
            goals_for_avg=goals_for_avg,
            goals_against_avg=goals_against_avg,
            xg_avg=xg_avg,
            xga_avg=xga_avg,
            finishing_delta=finishing_delta,
            finishing_ratio=finishing_ratio,
            defensive_delta=defensive_delta,
        )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        return FormModelResult(

            version=FORM_MODEL_VERSION,

            team=(
                str(team)
                if team is not None
                else None
            ),

            matches_count=len(results),

            # RESULT
            raw_points=raw_points,
            points_rate=points_rate,
            recent_points_rate=recent_points_rate,
            result_strength=result_strength,

            # DIFFICULTY
            hard_points_rate=hard.points_rate,
            medium_points_rate=medium.points_rate,
            easy_points_rate=easy.points_rate,

            hard_adjustment=hard.adjustment,
            medium_adjustment=medium.adjustment,
            easy_adjustment=easy.adjustment,

            hard_recent_points_rate=(
                hard.recent_points_rate
            ),

            medium_recent_points_rate=(
                medium.recent_points_rate
            ),

            easy_recent_points_rate=(
                easy.recent_points_rate
            ),

            # GOALS
            goals_for_avg=goals_for_avg,
            goals_against_avg=goals_against_avg,

            # xG
            xg_avg=xg_avg,
            xga_avg=xga_avg,

            xg_history=tuple(
                xg_history
            ),

            xga_history=tuple(
                xga_history
            ),

            xg_recent=xg_recent,
            xga_recent=xga_recent,

            xg_trend=xg_trend,
            xga_trend=xga_trend,

            # REALIZATION
            finishing_delta=finishing_delta,
            finishing_ratio=finishing_ratio,
            defensive_delta=defensive_delta,

            # DYNAMICS
            trend_score=trend_score,
            trend=trend,
            consistency=consistency,

            # VENUE
            home_points_rate=home_points_rate,
            home_coverage=home_coverage,
            away_points_rate=away_points_rate,
            away_coverage=away_coverage,

            # FORM SCORE
            form_score=None,
            form_score_status=(
                "UNDEFINED_PENDING_CALIBRATION"
            ),

            # STRENGTH
            attack_strength=None,
            defense_strength=None,
            goal_strength=None,
            xg_strength=None,
            realization_strength=None,
            defensive_xg_strength=None,

            # EFFECTS
            effects=tuple(
                effects
            ),
        )

    # ========================================================
    # EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_matches(
        form_context: Any,
    ) -> List[Any]:

        matches = _get_value(
            form_context,
            "matches",
        )

        if matches is None:
            return []

        try:
            return list(matches)

        except TypeError:
            return []

    @staticmethod
    def _extract_history(
        form_context: Any,
        matches: List[Any],
        context_keys: Tuple[str, ...],
    ) -> List[Any]:
        """
        Prefer explicit history from FormContext.

        Fallback to match-level records.
        """

        for key in context_keys:

            value = _get_value(
                form_context,
                key,
            )

            if value is not None:

                try:

                    return list(value)

                except TypeError:

                    pass

        values = []

        for match in matches:

            values.append(
                _get_value(
                    match,
                    *context_keys,
                )
            )

        return values

    @staticmethod
    def _extract_results(
        form_context: Any,
        matches: List[Any],
    ) -> List[Optional[str]]:

        direct = _get_value(
            form_context,
            "results",
        )

        if direct is not None:

            try:

                return [
                    (
                        str(value)
                        if value is not None
                        else None
                    )
                    for value in list(direct)
                ]

            except TypeError:
                pass

        return [
            _get_value(
                match,
                "result",
            )
            for match in matches
        ]

    @staticmethod
    def _extract_xg_history(
        form_context: Any,
        matches: List[Any],
        history_key: str,
        match_key: str,
    ) -> List[Optional[float]]:
        """
        Explicit FormContext v1.4 history has priority.

        IMPORTANT:

            recent_xg / recent_xga contain the complete
            history and are NOT reconstructed from averages.
        """

        direct = _get_value(
            form_context,
            history_key,
        )

        if direct is not None:

            try:

                return [
                    _safe_float(value)
                    for value in list(direct)
                ]

            except TypeError:
                pass

        values = []

        for match in matches:

            values.append(
                _safe_float(
                    _get_value(
                        match,
                        match_key,
                    )
                )
            )

        return values

    # ========================================================
    # WEIGHTS
    # ========================================================

    def _weights_for(
        self,
        count: int,
    ) -> Tuple[float, ...]:
        """
        Generates temporal weights.

        Research baseline:

            1,2,3,4,5,6

        For fewer observations the latest observation
        receives the largest weight.

        For the normal six-match FormContext:

            1,2,3,4,5,6
        """

        if count <= 0:
            return ()

        if count <= len(
            self.temporal_weights
        ):

            return self.temporal_weights[
                -count:
            ]

        start = (
            len(
                self.temporal_weights
            )
            + 1
        )

        return tuple(
            float(value)
            for value in range(
                start,
                start + count,
            )
        )

    # ========================================================
    # DIFFICULTY
    # ========================================================

    def _difficulty_state(
        self,
        difficulties: List[Any],
        result_points: List[
            Optional[float]
        ],
        bucket: str,
        overall_points_rate: Optional[float],
    ) -> DifficultyState:
        """
        Calculates descriptive statistics for one
        difficulty bucket.

        Difficulty is NOT opponent strength.

        No arbitrary difficulty weight is applied.
        """

        normalized = [
            self._normalize_difficulty(
                difficulty
            )
            for difficulty in difficulties
        ]

        indexes = [
            index
            for index, value
            in enumerate(normalized)
            if value == bucket
        ]

        points = [
            result_points[index]
            for index in indexes
            if index < len(
                result_points
            )
            and result_points[index]
            is not None
        ]

        matches = len(points)

        total_points = (
            sum(points)
            if points
            else None
        )

        points_rate = (
            total_points
            / (
                3.0
                * matches
            )
            if matches > 0
            and total_points is not None
            else None
        )

        adjustment = (
            points_rate
            - overall_points_rate
            if points_rate is not None
            and overall_points_rate is not None
            else None
        )

        bucket_values = [
            (
                point / 3.0
                if point is not None
                else None
            )
            for point in points
        ]

        bucket_weights = self._weights_for(
            len(
                result_points
            )
        )

        bucket_recent_values = [
            result_points[index] / 3.0
            for index in indexes
            if index < len(
                result_points
            )
            and result_points[index]
            is not None
        ]

        bucket_recent_weights = [
            bucket_weights[index]
            for index in indexes
            if index < len(
                result_points
            )
            and result_points[index]
            is not None
        ]

        recent_points_rate = (
            _weighted_mean(
                bucket_recent_values,
                bucket_recent_weights,
            )
            if bucket_recent_values
            else None
        )

        return DifficultyState(
            matches=matches,
            points=(
                total_points
                if total_points is not None
                else 0.0
            ),
            points_rate=points_rate,
            adjustment=adjustment,
            recent_points_rate=(
                recent_points_rate
            ),
        )

    # ========================================================
    # VENUE
    # ========================================================

    @staticmethod
    def _normalize_venue(
        venue: Any,
    ) -> Optional[str]:

        if venue is None:
            return None

        value = str(
            venue
        ).strip().lower()

        if value in (
            "home",
            "дома",
            "h",
        ):
            return "дома"

        if value in (
            "away",
            "гости",
            "гостях",
            "a",
        ):
            return "гости"

        return None

    @staticmethod
    def _venue_points_rate(
        venues: List[Any],
        result_points: List[
            Optional[float]
        ],
        target: str,
    ) -> Optional[float]:

        points = []

        for venue, point in zip(
            venues,
            result_points,
        ):

            if (
                FormModel._normalize_venue(
                    venue
                )
                == target
                and point is not None
            ):
                points.append(
                    point
                )

        if not points:
            return None

        return sum(points) / (
            3.0 * len(points)
        )

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_difficulty(
        difficulty: Any,
    ) -> Optional[str]:

        if difficulty is None:
            return None

        value = str(
            difficulty
        ).strip().lower()

        aliases = {
            "easy": "easy",
            "лёгкий": "easy",
            "легкий": "easy",

            "medium": "medium",
            "средний": "medium",

            "hard": "hard",
            "тяжёлый": "hard",
            "тяжелый": "hard",

            "very_hard": "hard",
            "очень тяжёлый": "hard",
            "очень тяжелый": "hard",
        }

        return aliases.get(
            value
        )

    # ========================================================
    # EFFECT DETECTORS
    # ========================================================

    def _detect_effects(
        self,
        results: List[Optional[str]],
        venues: List[Any],
        next_venue: Optional[str],
        difficulties: List[Any],
        result_points: List[
            Optional[float]
        ],
        goals_for_avg: Optional[float],
        goals_against_avg: Optional[float],
        xg_avg: Optional[float],
        xga_avg: Optional[float],
        finishing_delta: Optional[float],
        finishing_ratio: Optional[float],
        defensive_delta: Optional[float],
    ) -> List[EffectSignal]:

        effects: List[
            EffectSignal
        ] = []

        # ----------------------------------------------------
        # GLADIATOR
        # ----------------------------------------------------

        consecutive_wins = (
            self._leading_streak(
                results,
                "W",
            )
        )

        gladiator_detected = (
            consecutive_wins
            >= GLADIATOR_MIN_WINS
        )

        effects.append(
            EffectSignal(
                name="Gladiator",
                detected=(
                    gladiator_detected
                    if results
                    else None
                ),
                signal=(
                    1.0
                    if gladiator_detected
                    else 0.0
                )
                if results
                else None,
                confidence=None,
                evidence={
                    "streak_length":
                        consecutive_wins,
                    "threshold":
                        GLADIATOR_MIN_WINS,
                },
            )
        )

        # ----------------------------------------------------
        # FORTRESS
        # ----------------------------------------------------

        home_results = [
            result
            for venue, result
            in zip(
                venues,
                results,
            )
            if self._normalize_venue(
                venue
            ) == "дома"
        ]

        home_unbeaten = sum(
            1
            for result
            in home_results
            if result in ("W", "D")
        )

        home_matches = len(
            home_results
        )

        fortress_detected = (
            home_matches
            >= FORTRESS_MIN_HOME_MATCHES
            and home_unbeaten
            >= FORTRESS_MIN_HOME_UNBEATEN
        )

        effects.append(
            EffectSignal(
                name="Fortress",
                detected=(
                    fortress_detected
                    if home_matches
                    else None
                ),
                signal=(
                    1.0
                    if fortress_detected
                    else 0.0
                )
                if home_matches
                else None,
                confidence=None,
                evidence={
                    "home_matches":
                        home_matches,
                    "home_unbeaten":
                        home_unbeaten,
                    "threshold_matches":
                        FORTRESS_MIN_HOME_MATCHES,
                    "threshold_unbeaten":
                        FORTRESS_MIN_HOME_UNBEATEN,
                },
            )
        )

        # ----------------------------------------------------
        # LEICESTER
        # ----------------------------------------------------

        away_results = [
            result
            for venue, result
            in zip(
                venues,
                results,
            )
            if self._normalize_venue(
                venue
            ) == "гости"
        ]

        away_matches = len(
            away_results
        )

        away_wins = sum(
            1
            for result in away_results
            if result == "W"
        )

        leicester_detected = (
            away_matches
            >= LEICESTER_MIN_AWAY_MATCHES
            and away_wins
            >= LEICESTER_MIN_AWAY_WINS
        )

        effects.append(
            EffectSignal(
                name="Leicester",
                detected=(
                    leicester_detected
                    if away_matches
                    else None
                ),
                signal=(
                    1.0
                    if leicester_detected
                    else 0.0
                )
                if away_matches
                else None,
                confidence=None,
                evidence={
                    "away_matches":
                        away_matches,
                    "away_wins":
                        away_wins,
                    "away_win_rate": (
                        away_wins
                        / away_matches
                        if away_matches > 0
                        else None
                    ),
                    "threshold_matches":
                        LEICESTER_MIN_AWAY_MATCHES,
                    "threshold_wins":
                        LEICESTER_MIN_AWAY_WINS,
                },
            )
        )

        # ----------------------------------------------------
        # GOD KISS
        # ----------------------------------------------------

        consecutive_away = (
            self._leading_streak(
                [
                    (
                        "A"
                        if self._normalize_venue(
                            venue
                        ) == "гости"
                        else "H"
                    )
                    for venue in venues
                ],
                "A",
            )
        )

        normalized_next_venue = (
            self._normalize_venue(
                next_venue
            )
        )

        god_kiss_detected = (
            consecutive_away
            >= GOD_KISS_MIN_AWAY_STREAK
            and normalized_next_venue
            == "дома"
        )

        effects.append(
            EffectSignal(
                name="God Kiss",
                detected=(
                    god_kiss_detected
                    if consecutive_away > 0
                    and normalized_next_venue
                    is not None
                    else None
                ),
                signal=(
                    1.0
                    if god_kiss_detected
                    else 0.0
                )
                if consecutive_away > 0
                and normalized_next_venue
                is not None
                else None,
                confidence=None,
                evidence={
                    "consecutive_away_matches":
                        consecutive_away,
                    "next_venue":
                        normalized_next_venue,
                    "threshold":
                        GOD_KISS_MIN_AWAY_STREAK,
                },
            )
        )

        # ----------------------------------------------------
        # DARK HORSE
        # ----------------------------------------------------
        #
        # Requires league baseline.
        #

        effects.append(
            EffectSignal(
                name="Dark Horse",
                detected=None,
                signal=None,
                confidence=None,
                evidence={
                    "goals_for_avg":
                        goals_for_avg,
                    "xg_avg":
                        xg_avg,
                    "finishing_delta":
                        finishing_delta,
                    "finishing_ratio":
                        finishing_ratio,
                    "status":
                        "BASELINE_REQUIRED",
                },
            )
        )

        # ----------------------------------------------------
        # LUKAKU
        # ----------------------------------------------------

        effects.append(
            EffectSignal(
                name="Lukaku",
                detected=None,
                signal=None,
                confidence=None,
                evidence={
                    "goals_for_avg":
                        goals_for_avg,
                    "xg_avg":
                        xg_avg,
                    "finishing_delta":
                        finishing_delta,
                    "finishing_ratio":
                        finishing_ratio,
                    "status":
                        "BASELINE_REQUIRED",
                },
            )
        )

        # ----------------------------------------------------
        # HAALAND
        # ----------------------------------------------------

        effects.append(
            EffectSignal(
                name="Haaland",
                detected=None,
                signal=None,
                confidence=None,
                evidence={
                    "goals_for_avg":
                        goals_for_avg,
                    "xg_avg":
                        xg_avg,
                    "finishing_delta":
                        finishing_delta,
                    "finishing_ratio":
                        finishing_ratio,
                    "status":
                        "BASELINE_REQUIRED",
                },
            )
        )

        # ----------------------------------------------------
        # KEPA
        # ----------------------------------------------------

        effects.append(
            EffectSignal(
                name="Kepa",
                detected=None,
                signal=None,
                confidence=None,
                evidence={
                    "goals_against_avg":
                        goals_against_avg,
                    "xga_avg":
                        xga_avg,
                    "defensive_delta":
                        defensive_delta,
                    "status":
                        "BASELINE_REQUIRED",
                },
            )
        )

        return effects

    # ========================================================
    # STREAK
    # ========================================================

    @staticmethod
    def _leading_streak(
        values: List[Any],
        target: Any,
    ) -> int:
        """
        Counts consecutive target values
        starting from the newest observation.

        FormContext must therefore be ordered:

            newest -> oldest

        This function does not reorder history.
        """

        count = 0

        for value in values:

            if value == target:
                count += 1

            else:
                break

        return count


# ============================================================
# SERIALIZATION
# ============================================================

def form_model_result_to_dict(
    result: FormModelResult,
) -> Dict[str, Any]:
    """
    Convert FormModelResult into plain dictionary.

    EffectSignal dataclasses are also converted.
    """

    data = asdict(
        result
    )

    return data


# ============================================================
# PUBLIC HELPER
# ============================================================

def build_form_model(
    form_context: Any,
    next_venue: Optional[str] = None,
    temporal_weights: Tuple[
        float, ...
    ] = TEMPORAL_WEIGHTS,
    trend_threshold: Optional[
        float
    ] = TREND_THRESHOLD,
) -> Dict[str, Any]:
    """
    Convenience API.

    Returns a serializable dictionary.
    """

    model = FormModel(
        temporal_weights=temporal_weights,
        trend_threshold=trend_threshold,
    )

    result = model.analyze(
        form_context=form_context,
        next_venue=next_venue,
    )

    return form_model_result_to_dict(
        result
    )


# ============================================================
# DEBUG
# ============================================================

if __name__ == "__main__":

    sample_context = {

        "team": "Зенит",

        # IMPORTANT:
        # For FormModel calculations history is expected
        # from oldest -> newest.

        "results": (
            "L",
            "L",
            "D",
            "W",
            "W",
            "W",
        ),

        "goals_for": (
            0,
            1,
            1,
            2,
            2,
            3,
        ),

        "goals_against": (
            2,
            1,
            1,
            0,
            1,
            0,
        ),

        "recent_xg": (
            0.70,
            1.10,
            1.20,
            1.50,
            1.70,
            2.00,
        ),

        "recent_xga": (
            1.80,
            1.40,
            1.20,
            0.90,
            1.10,
            0.70,
        ),

        "venue": (
            "гости",
            "дома",
            "гости",
            "дома",
            "гости",
            "дома",
        ),

        "difficulty": (
            "тяжёлый",
            "тяжёлый",
            "средний",
            "средний",
            "лёгкий",
            "лёгкий",
        ),
    }

    result = FormModel(
        trend_threshold=None,
    ).analyze(
        sample_context,
        next_venue="дома",
    )

    print(
        form_model_result_to_dict(
            result
        )
    )
