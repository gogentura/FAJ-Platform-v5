#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PLATFORM v12.1
FORM ANOMALY v2.0

Independent diagnostic mathematical organ.

Role:
    FormContext -> FormAnomaly -> FAJBrain

Main principle:
    FACTS -> STATE/EVIDENCE

FormAnomaly:
    - detects unusual change in recent form;
    - separates xG, xGA and result evidence;
    - detects directional trend;
    - detects recent spike;
    - detects reversal;
    - reports data quality.

FormAnomaly DOES NOT:
    - predict match result;
    - modify xG;
    - modify GoalModel;
    - modify FormWin;
    - modify Defence;
    - modify Control;
    - calculate probabilities;
    - calculate score distribution;
    - calculate confidence;
    - calculate risk;
    - use bookmaker odds;
    - use future result;
    - access database;
    - perform learning;
    - apply arbitrary predictive multipliers.

History order:
    M1 -> M2 -> ... -> M6
    oldest -> newest

Missing values:
    None != 0

Temporal weights:
    1, 2, 3, 4, 5, 6
    oldest -> newest
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt, tanh
from statistics import median
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


# ============================================================
# VERSION / CONTRACT
# ============================================================

FORM_ANOMALY_VERSION = "2.0"
FORMULA_STATUS = "DIAGNOSTIC_EVIDENCE"

CONTRACT_CONSTANT = "CONTRACT_CONSTANT"
RESEARCH_PARAMETER = "RESEARCH_PARAMETER"
CALIBRATED_PARAMETER = "CALIBRATED_PARAMETER"

HISTORY_SIZE = 6
MIN_HISTORY_FOR_SIGNAL = 3

EPSILON = 1e-9

# Contract-level temporal weights.
# For N observations, the first N weights are used.
TEMPORAL_WEIGHTS = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)

# A spike requires a sufficiently large standardized deviation.
# This is a diagnostic threshold, NOT a prediction coefficient.
SPIKE_THRESHOLD = 2.0

# Reversal requires at least four valid observations.
REVERSAL_MIN_OBSERVATIONS = 4


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class AnomalyResult:
    """
    Output State of FormAnomaly.

    anomaly_signal:
        Robust descriptive aggregate of available anomaly evidence.
        It is NOT a probability and MUST NOT directly modify xG,
        winner probability or any GoalModel output.

        Positive:
            recent state is directionally improved.

        Negative:
            recent state is directionally worsened.

        Near zero:
            no meaningful directional anomaly.

    anomaly_type:
        "positive", "negative", or "none".

    anomaly_strength:
        Absolute magnitude of anomaly_signal.

    evidence_quality:
        Data coverage of the three primary evidence sources.
        It is a data-quality metric, NOT confidence.
    """

    anomaly_signal: Optional[float]
    anomaly_type: str
    anomaly_strength: Optional[float]
    evidence_quality: Optional[float]

    xg_anomaly: Optional[float]
    xga_anomaly: Optional[float]
    trend_signal: Optional[float]
    result_signal: Optional[float]

    process_result_gap: Optional[float]

    spike_detected: bool
    reversal_detected: bool

    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Convert a value to finite float.

    Missing / invalid values remain None.
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None

        number = float(text)

        if not isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[Any]) -> Optional[float]:
    numbers = [
        _safe_float(value)
        for value in values
    ]

    numbers = [
        value
        for value in numbers
        if value is not None
    ]

    if not numbers:
        return None

    return sum(numbers) / len(numbers)


def _weighted_mean(
    values: Sequence[Any],
    weights: Sequence[float],
) -> Optional[float]:
    """
    Weighted mean with missing-value omission.

    The weight belongs to the original chronological position.
    Missing observations do not receive another observation's weight.
    """

    pairs = []

    for value, weight in zip(values, weights):
        number = _safe_float(value)

        if number is None:
            continue

        if weight <= 0:
            continue

        pairs.append((number, float(weight)))

    if not pairs:
        return None

    denominator = sum(
        weight
        for _, weight in pairs
    )

    if denominator <= EPSILON:
        return None

    return (
        sum(
            value * weight
            for value, weight in pairs
        )
        / denominator
    )


def _weighted_mean_history(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Contract weighted mean.

    For N observations:
        weights = 1..N

    Example:
        M1 M2 M3 M4 M5 M6
         1  2  3  4  5  6
    """

    values = tuple(values)[:HISTORY_SIZE]

    if not values:
        return None

    weights = TEMPORAL_WEIGHTS[:len(values)]

    return _weighted_mean(
        values,
        weights,
    )


def _clamp(
    value: Optional[float],
    lo: float = -1.0,
    hi: float = 1.0,
) -> Optional[float]:
    if value is None:
        return None

    return max(
        lo,
        min(hi, float(value)),
    )


def _sign(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None

    if value > EPSILON:
        return 1

    if value < -EPSILON:
        return -1

    return 0


def _valid_numbers(
    values: Sequence[Any],
) -> Tuple[float, ...]:
    result = []

    for value in values:
        number = _safe_float(value)

        if number is not None:
            result.append(number)

    return tuple(result)


def _std(
    values: Sequence[Any],
) -> Optional[float]:
    numbers = _valid_numbers(values)

    if not numbers:
        return None

    mean = sum(numbers) / len(numbers)

    variance = (
        sum(
            (value - mean) ** 2
            for value in numbers
        )
        / len(numbers)
    )

    return sqrt(
        max(
            variance,
            0.0,
        )
    )


def _mad(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Median absolute deviation.
    """

    numbers = _valid_numbers(values)

    if not numbers:
        return None

    center = median(numbers)

    deviations = [
        abs(value - center)
        for value in numbers
    ]

    return median(deviations)


def _robust_scale(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Robust scale.

    MAD is preferred.
    If MAD is zero, standard deviation is used.
    """

    numbers = _valid_numbers(values)

    if not numbers:
        return None

    mad = _mad(numbers)

    if mad is not None and mad > EPSILON:
        return mad

    std = _std(numbers)

    if std is not None and std > EPSILON:
        return std

    return None


def _median_center(
    values: Sequence[Any],
) -> Optional[float]:
    numbers = _valid_numbers(values)

    if not numbers:
        return None

    return median(numbers)


def _extract_field(
    context: Any,
    *names: str,
) -> Any:
    """
    Supports:
        dict
        mapping-like objects
        dataclass/object attributes
    """

    if context is None:
        return None

    for name in names:

        if isinstance(context, dict):
            if name in context:
                return context[name]

        try:
            if name in context.keys():
                return context[name]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(context, name)
        except AttributeError:
            pass

    return None


def _as_sequence(
    value: Any,
) -> Tuple[Any, ...]:

    if value is None:
        return ()

    if isinstance(value, (str, bytes)):
        return (value,)

    try:
        return tuple(value)

    except TypeError:
        return (value,)


def _history(
    values: Any,
) -> Tuple[Any, ...]:
    """
    Input is already oldest -> newest.

    Never reverse history here.
    """

    return _as_sequence(values)[:HISTORY_SIZE]


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def _result_value(
    result: Any,
) -> Optional[float]:
    """
    Result state:

        W = +1
        D =  0
        L = -1

    No other result is interpreted.
    """

    if result is None:
        return None

    text = str(result).strip().upper()

    if text in {
        "W",
        "WIN",
        "В",
        "ПОБЕДА",
    }:
        return 1.0

    if text in {
        "D",
        "DRAW",
        "Н",
        "НИЧЬЯ",
    }:
        return 0.0

    if text in {
        "L",
        "LOSS",
        "П",
        "ПОРАЖЕНИЕ",
    }:
        return -1.0

    return None


def _result_history(
    values: Sequence[Any],
) -> Tuple[Optional[float], ...]:

    return tuple(
        _result_value(value)
        for value in tuple(values)[:HISTORY_SIZE]
    )


# ============================================================
# RECENCY / BASELINE
# ============================================================

def _recent_weighted_value(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Weighted state over the complete available history.

    This follows the common FAJ State contract:
        N <= 6
        oldest -> newest
        weights 1..N
    """

    return _weighted_mean_history(values)


def _previous_weighted_value(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Weighted value before the latest observation.

    Used only for diagnostic spike comparison.
    """

    values = tuple(values)[:HISTORY_SIZE]

    if len(values) < 2:
        return None

    previous = values[:-1]

    return _weighted_mean_history(previous)


# ============================================================
# ANOMALY SIGNAL
# ============================================================

def _calculate_relative_anomaly(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Detects whether the newest observation is unusual relative
    to the preceding observations.

    Direction:
        positive = value increased
        negative = value decreased

    This is a descriptive anomaly signal.

    It does NOT claim that an increase is always good.
    For xGA the direction is inverted by the caller.
    """

    values = tuple(values)[:HISTORY_SIZE]

    if len(_valid_numbers(values)) < MIN_HISTORY_FOR_SIGNAL:
        return None

    latest = _safe_float(values[-1])

    if latest is None:
        return None

    previous = values[:-1]

    previous_numbers = _valid_numbers(previous)

    if len(previous_numbers) < 2:
        return None

    center = median(previous_numbers)

    scale = _robust_scale(previous_numbers)

    if scale is None or scale <= EPSILON:
        # A flat valid history followed by the same value is
        # a neutral state, not missing data.
        if abs(latest - center) <= EPSILON:
            return 0.0

        return None

    standardized_delta = (
        latest - center
    ) / scale

    return _clamp(
        tanh(standardized_delta)
    )


def _calculate_xg_anomaly(
    values: Sequence[Any],
) -> Optional[float]:
    """
    xG increase -> positive anomaly.
    xG decrease -> negative anomaly.
    """

    return _calculate_relative_anomaly(values)


def _calculate_xga_anomaly(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Defensive interpretation:

        xGA decrease -> positive anomaly
        xGA increase -> negative anomaly
    """

    signal = _calculate_relative_anomaly(values)

    if signal is None:
        return None

    return _clamp(-signal)


# ============================================================
# TREND
# ============================================================

def _ols_slope(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Ordinary least squares slope using chronological positions.

    Missing values are skipped together with their position.
    """

    points = []

    for index, value in enumerate(
        tuple(values)[:HISTORY_SIZE]
    ):
        number = _safe_float(value)

        if number is None:
            continue

        points.append(
            (float(index), number)
        )

    if len(points) < 2:
        return None

    x_mean = sum(
        x
        for x, _
        in points
    ) / len(points)

    y_mean = sum(
        y
        for _, y
        in points
    ) / len(points)

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in points
    )

    denominator = sum(
        (x - x_mean) ** 2
        for x, _
        in points
    )

    if denominator <= EPSILON:
        return None

    return numerator / denominator


def _calculate_trend_signal(
    values: Sequence[Any],
    invert: bool = False,
) -> Optional[float]:
    """
    Trend evidence.

    The raw slope is normalized by robust historical scale.

    No fixed multiplier is used.

    If invert=True:
        decreasing raw value becomes positive signal.

    This is useful for xGA.
    """

    values = tuple(values)[:HISTORY_SIZE]

    numbers = _valid_numbers(values)

    if len(numbers) < MIN_HISTORY_FOR_SIGNAL:
        return None

    slope = _ols_slope(values)

    if slope is None:
        return None

    scale = _robust_scale(numbers)

    if scale is None or scale <= EPSILON:
        if abs(slope) <= EPSILON:
            return 0.0

        return None

    normalized = slope / scale

    signal = tanh(normalized)

    if invert:
        signal = -signal

    return _clamp(signal)


# ============================================================
# RESULT TREND
# ============================================================

def _calculate_result_signal(
    results: Sequence[Any],
) -> Optional[float]:
    """
    Result trend:

        W = +1
        D =  0
        L = -1

    Uses the same independent State principle:
    no goals/xG fallback.
    """

    values = _result_history(results)

    valid = [
        value
        for value in values
        if value is not None
    ]

    if len(valid) < MIN_HISTORY_FOR_SIGNAL:
        return None

    slope = _ols_slope(values)

    if slope is None:
        return None

    scale = _robust_scale(valid)

    if scale is None or scale <= EPSILON:
        if abs(slope) <= EPSILON:
            return 0.0

        return None

    return _clamp(
        tanh(slope / scale)
    )


# ============================================================
# PROCESS / RESULT GAP
# ============================================================

def _calculate_process_signal(
    xg_anomaly: Optional[float],
    xga_anomaly: Optional[float],
) -> Optional[float]:
    """
    Process evidence without arbitrary weights.

    If both xG and xGA exist:
        median(xG anomaly, xGA anomaly)

    If only one exists:
        that evidence is used.

    No fixed coefficient is introduced.
    """

    values = [
        value
        for value in (
            xg_anomaly,
            xga_anomaly,
        )
        if value is not None
    ]

    if not values:
        return None

    return _clamp(
        median(values)
    )


def _calculate_gap(
    process_signal: Optional[float],
    result_signal: Optional[float],
) -> Optional[float]:
    """
    Diagnostic process/result divergence.

        positive:
            process evidence is better than result trend.

        negative:
            result trend is better than process evidence.

    It is diagnostic only.
    """

    if process_signal is None or result_signal is None:
        return None

    return _clamp(
        process_signal - result_signal
    )


# ============================================================
# SPIKE
# ============================================================

def _detect_spike(
    values: Sequence[Any],
) -> bool:
    """
    Detects whether the newest valid observation is an unusual
    deviation from the previous observations.

    Returns False when there is insufficient evidence.
    """

    values = tuple(values)[:HISTORY_SIZE]

    latest = _safe_float(
        values[-1]
    ) if values else None

    if latest is None:
        return False

    previous = _valid_numbers(
        values[:-1]
    )

    if len(previous) < MIN_HISTORY_FOR_SIGNAL - 1:
        return False

    center = median(previous)

    scale = _robust_scale(previous)

    if scale is None or scale <= EPSILON:
        return False

    z_like = abs(
        latest - center
    ) / scale

    return z_like >= SPIKE_THRESHOLD


# ============================================================
# REVERSAL
# ============================================================

def _detect_reversal(
    values: Sequence[Any],
) -> bool:
    """
    Detects a directional reversal in the latest part of the
    chronological series.

    Example:
        increasing -> increasing -> decreasing

    or:
        decreasing -> decreasing -> increasing

    This is descriptive only.
    """

    values = tuple(values)[:HISTORY_SIZE]

    points = [
        _safe_float(value)
        for value in values
    ]

    # Preserve chronological positions while allowing missing data
    valid = [
        value
        for value in points
        if value is not None
    ]

    if len(valid) < REVERSAL_MIN_OBSERVATIONS:
        return False

    tail = valid[-4:]

    deltas = [
        tail[index] - tail[index - 1]
        for index in range(1, len(tail))
    ]

    directions = [
        _sign(delta)
        for delta in deltas
    ]

    if any(
        direction is None or direction == 0
        for direction in directions
    ):
        return False

    return (
        directions[0] == directions[1]
        and directions[2] != directions[1]
    )


# ============================================================
# EVIDENCE AGGREGATION
# ============================================================

def _median_signal(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Robust symmetric aggregation.

    IMPORTANT:
        This is not a predictive weighting system.

    Median is used so that no evidence source receives an
    arbitrary fixed coefficient.
    """

    available = [
        float(value)
        for value in values
        if value is not None
    ]

    if not available:
        return None

    return _clamp(
        median(available)
    )


def _classify(
    signal: Optional[float],
) -> Tuple[str, Optional[float]]:
    if signal is None:
        return "none", None

    strength = abs(signal)

    if signal > EPSILON:
        return "positive", strength

    if signal < -EPSILON:
        return "negative", strength

    return "none", 0.0


# ============================================================
# DATA QUALITY
# ============================================================

def _quality(
    values: Sequence[Any],
) -> float:
    """
    Fraction of valid observations.

    This is coverage, not confidence.
    """

    values = tuple(values)[:HISTORY_SIZE]

    if not values:
        return 0.0

    available = sum(
        _safe_float(value) is not None
        for value in values
    )

    return available / len(values)


def _calculate_evidence_quality(
    xg: Sequence[Any],
    xga: Sequence[Any],
    results: Sequence[Any],
) -> Optional[float]:
    """
    Equal-source evidence coverage.

    No arbitrary source weighting.

    Returns None only when all three sources are completely absent.
    """

    qualities = [
        _quality(xg),
        _quality(xga),
        _quality(results),
    ]

    if all(
        quality <= 0.0
        for quality in qualities
    ):
        return None

    return sum(qualities) / len(qualities)


def _evidence_status(
    value: Optional[float],
) -> str:

    if value is None:
        return "INSUFFICIENT"

    if value >= 0.80:
        return "HIGH"

    if value >= 0.50:
        return "MEDIUM"

    if value > 0.0:
        return "LOW"

    return "INSUFFICIENT"


# ============================================================
# HISTORY EXTRACTION
# ============================================================

def _extract_histories(
    context: Any,
) -> Tuple[
    Tuple[Any, ...],
    Tuple[Any, ...],
    Tuple[Any, ...],
]:
    """
    Canonical FormContext names first.

    xG:
        team_xg_history
        recent_xg
        xg_history

    xGA:
        opponent_xg_history
        recent_xga
        xga_history

    Results:
        results_history
        results
        result_history
    """

    xg = _extract_field(
        context,
        "team_xg_history",
        "recent_xg",
        "xg_history",
    )

    xga = _extract_field(
        context,
        "opponent_xg_history",
        "recent_xga",
        "xga_history",
    )

    results = _extract_field(
        context,
        "results_history",
        "results",
        "result_history",
    )

    return (
        _history(xg),
        _history(xga),
        _history(results),
    )


# ============================================================
# MAIN ORGAN
# ============================================================

class FormAnomaly:
    """
    Deterministic FormAnomaly evidence organ.

    It measures abnormality / directional change in the supplied
    historical facts.

    It does not forecast.
    """

    def analyze(
        self,
        context: Any,
    ) -> AnomalyResult:

        xg_history, xga_history, results_history = (
            _extract_histories(context)
        )

        # ----------------------------------------------------
        # Independent evidence
        # ----------------------------------------------------

        xg_anomaly = _calculate_xg_anomaly(
            xg_history
        )

        xga_anomaly = _calculate_xga_anomaly(
            xga_history
        )

        # xG trend is preferred as process trend.
        # If unavailable, xGA trend is used as an independent
        # defensive trend signal.
        trend_signal = _calculate_trend_signal(
            xg_history,
            invert=False,
        )

        trend_source = "xg"

        if trend_signal is None:
            trend_signal = _calculate_trend_signal(
                xga_history,
                invert=True,
            )
            trend_source = (
                "xga"
                if trend_signal is not None
                else None
            )

        result_signal = _calculate_result_signal(
            results_history
        )

        # ----------------------------------------------------
        # Process/result divergence
        # ----------------------------------------------------

        process_signal = _calculate_process_signal(
            xg_anomaly,
            xga_anomaly,
        )

        process_result_gap = _calculate_gap(
            process_signal,
            result_signal,
        )

        # ----------------------------------------------------
        # No fixed weights.
        #
        # Median keeps evidence symmetric and prevents one
        # source from becoming a hidden predictor coefficient.
        # ----------------------------------------------------

        anomaly_signal = _median_signal(
            (
                xg_anomaly,
                xga_anomaly,
                trend_signal,
                result_signal,
            )
        )

        anomaly_type, anomaly_strength = _classify(
            anomaly_signal
        )

        # ----------------------------------------------------
        # Data quality
        # ----------------------------------------------------

        evidence_quality = _calculate_evidence_quality(
            xg_history,
            xga_history,
            results_history,
        )

        # ----------------------------------------------------
        # Event diagnostics
        # ----------------------------------------------------

        xg_spike = _detect_spike(
            xg_history
        )

        xga_spike = _detect_spike(
            xga_history
        )

        xg_reversal = _detect_reversal(
            xg_history
        )

        xga_reversal = _detect_reversal(
            xga_history
        )

        spike_detected = (
            xg_spike
            or xga_spike
        )

        reversal_detected = (
            xg_reversal
            or xga_reversal
        )

        # ----------------------------------------------------
        # Recency diagnostics
        # ----------------------------------------------------

        xg_recent_weighted = _recent_weighted_value(
            xg_history
        )

        xga_recent_weighted = _recent_weighted_value(
            xga_history
        )

        result_recent_weighted = _recent_weighted_value(
            _result_history(results_history)
        )

        xg_previous_weighted = _previous_weighted_value(
            xg_history
        )

        xga_previous_weighted = _previous_weighted_value(
            xga_history
        )

        # ----------------------------------------------------
        # Valid sample counts
        # ----------------------------------------------------

        xg_valid_count = len(
            _valid_numbers(xg_history)
        )

        xga_valid_count = len(
            _valid_numbers(xga_history)
        )

        result_valid_count = sum(
            value is not None
            for value in _result_history(results_history)
        )

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        diagnostics: Dict[str, Any] = {
            "version": FORM_ANOMALY_VERSION,
            "formula_status": FORMULA_STATUS,

            "model_role": "diagnostic_evidence",

            "history_order": "M1->M6",
            "history_max_size": HISTORY_SIZE,

            "temporal_weights": list(
                TEMPORAL_WEIGHTS
            ),

            "min_history_for_signal": (
                MIN_HISTORY_FOR_SIGNAL
            ),

            "missing_is_zero": False,

            "future_result_used": False,
            "known_result_as_prediction_input": False,

            "goal_model_modified": False,
            "form_win_modified": False,
            "defence_modified": False,
            "control_modified": False,

            "probability_generated": False,
            "score_generated": False,
            "winner_generated": False,

            "confidence_generated": False,
            "risk_generated": False,

            "corners_used": False,
            "cards_used": False,

            "prediction_impact": "none",

            # ----------------------------------------------
            # Signal semantics
            # ----------------------------------------------

            "positive_signal_meaning": (
                "directional improvement in the measured "
                "evidence source"
            ),

            "negative_signal_meaning": (
                "directional deterioration in the measured "
                "evidence source"
            ),

            "xg_anomaly_semantics": (
                "higher recent xG relative to preceding history"
            ),

            "xga_anomaly_semantics": (
                "lower recent xGA relative to preceding history"
            ),

            "result_signal_semantics": (
                "improving W/D/L sequence represented as "
                "W=+1, D=0, L=-1"
            ),

            # ----------------------------------------------
            # Aggregation
            # ----------------------------------------------

            "aggregation_method": "median_of_available_evidence",

            "fixed_predictive_weights": False,

            "arbitrary_multiplier_used": False,

            "anomaly_signal_is_probability": False,

            "anomaly_signal_is_winner_probability": False,

            "anomaly_signal_changes_xg": False,

            # ----------------------------------------------
            # Trend
            # ----------------------------------------------

            "trend_source": trend_source,

            "trend_method": (
                "OLS slope normalized by robust historical scale"
            ),

            # ----------------------------------------------
            # Spike
            # ----------------------------------------------

            "spike_threshold": SPIKE_THRESHOLD,

            "spike_is_diagnostic_only": True,

            # ----------------------------------------------
            # Reversal
            # ----------------------------------------------

            "reversal_min_observations": (
                REVERSAL_MIN_OBSERVATIONS
            ),

            "reversal_is_diagnostic_only": True,

            # ----------------------------------------------
            # Quality
            # ----------------------------------------------

            "evidence_quality_is_confidence": False,

            "evidence_quality_method": (
                "equal-source valid-observation coverage"
            ),

            "evidence_status": _evidence_status(
                evidence_quality
            ),

            # ----------------------------------------------
            # Coverage
            # ----------------------------------------------

            "xg_valid_count": xg_valid_count,
            "xga_valid_count": xga_valid_count,
            "result_valid_count": result_valid_count,

            "xg_quality": _quality(
                xg_history
            ),

            "xga_quality": _quality(
                xga_history
            ),

            "result_quality": _quality(
                results_history
            ),

            # ----------------------------------------------
            # Recency
            # ----------------------------------------------

            "xg_recent_weighted": xg_recent_weighted,
            "xga_recent_weighted": xga_recent_weighted,
            "result_recent_weighted": result_recent_weighted,

            "xg_previous_weighted": xg_previous_weighted,
            "xga_previous_weighted": xga_previous_weighted,

            # ----------------------------------------------
            # Event diagnostics
            # ----------------------------------------------

            "xg_spike": xg_spike,
            "xga_spike": xga_spike,

            "xg_reversal": xg_reversal,
            "xga_reversal": xga_reversal,

            # ----------------------------------------------
            # Process/result divergence
            # ----------------------------------------------

            "process_signal": process_signal,

            "process_result_gap_semantics": (
                "process evidence minus result trend; "
                "diagnostic only"
            ),

            # ----------------------------------------------
            # Contract
            # ----------------------------------------------

            "contract": "MATHEMATICAL_CONTRACT_V1",

            "state_changes_other_state": False,

            "winner_override": False,

            "low_score_correction": False,

            "learning_performed": False,
        }

        return AnomalyResult(
            anomaly_signal=anomaly_signal,
            anomaly_type=anomaly_type,
            anomaly_strength=anomaly_strength,
            evidence_quality=evidence_quality,

            xg_anomaly=xg_anomaly,
            xga_anomaly=xga_anomaly,
            trend_signal=trend_signal,
            result_signal=result_signal,

            process_result_gap=process_result_gap,

            spike_detected=spike_detected,
            reversal_detected=reversal_detected,

            diagnostics=diagnostics,
        )


# ============================================================
# PUBLIC API
# ============================================================

def analyze_anomaly(
    context: Any,
) -> AnomalyResult:
    """
    Public compatibility wrapper.
    """

    return FormAnomaly().analyze(
        context
    )


__all__ = [
    "FORM_ANOMALY_VERSION",
    "FORMULA_STATUS",
    "CONTRACT_CONSTANT",
    "RESEARCH_PARAMETER",
    "CALIBRATED_PARAMETER",
    "HISTORY_SIZE",
    "MIN_HISTORY_FOR_SIGNAL",
    "TEMPORAL_WEIGHTS",
    "AnomalyResult",
    "FormAnomaly",
    "analyze_anomaly",
]
