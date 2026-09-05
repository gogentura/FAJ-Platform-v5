#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PLATFORM v12.1
FORM ANOMALY v1.0

Diagnostic mathematical organ.

Contract:
    FormContext -> FormAnomaly -> FAJBrain

Does NOT change xG, GoalModel, FormWin, Defence,
probabilities, parameters, database or learning.

History order:
    M1 -> M2 -> M3 -> M4 -> M5 -> M6
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, sqrt, tanh
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


FORM_ANOMALY_VERSION = "1.0"
FORMULA_STATUS = "RESEARCH_FORMULA"

CONTRACT_CONSTANT = "CONTRACT_CONSTANT"
RESEARCH_PARAMETER = "RESEARCH_PARAMETER"
CALIBRATED_PARAMETER = "CALIBRATED_PARAMETER"

HISTORY_SIZE = 6
MIN_HISTORY_FOR_SIGNAL = 3
BASELINE_SIZE = 3

RECENT_WEIGHTS = (0.25, 0.35, 0.40)  # M4, M5, M6
EPSILON = 0.001
K_ZSCORE = 2.0

ANOMALY_XG_WEIGHT = 0.35
ANOMALY_XGA_WEIGHT = 0.30
ANOMALY_TREND_WEIGHT = 0.20
ANOMALY_RESULT_WEIGHT = 0.15

ANOMALY_TYPE_TOLERANCE = 0.10
TREND_MIN_CONSISTENCY = 3

SPIKE_Z_THRESHOLD = 1.75
REVERSAL_MIN_OBSERVATIONS = 4

EVIDENCE_XG_WEIGHT = 0.35
EVIDENCE_XGA_WEIGHT = 0.35
EVIDENCE_RESULT_WEIGHT = 0.30


@dataclass(frozen=True)
class AnomalyResult:
    anomaly_signal: Optional[float]
    anomaly_type: str
    anomaly_strength: float
    evidence_quality: float

    xg_anomaly: Optional[float]
    xga_anomaly: Optional[float]
    trend_signal: Optional[float]
    result_signal: Optional[float]
    process_result_gap: Optional[float]

    spike_detected: bool
    reversal_detected: bool

    diagnostics: Dict[str, Any] = field(default_factory=dict)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        number = float(text)
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _mean(values: Iterable[Any]) -> Optional[float]:
    numbers = [_safe_float(v) for v in values]
    numbers = [v for v in numbers if v is not None]
    return sum(numbers) / len(numbers) if numbers else None


def _weighted_mean(
    values: Sequence[Any],
    weights: Sequence[float],
) -> Optional[float]:
    pairs = [
        (_safe_float(v), float(w))
        for v, w in zip(values, weights)
        if _safe_float(v) is not None and w > 0
    ]
    if not pairs:
        return None
    denominator = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / denominator


def _clamp(
    value: Optional[float],
    lo: float = -1.0,
    hi: float = 1.0,
) -> Optional[float]:
    if value is None:
        return None
    return max(lo, min(hi, float(value)))


def _sign(value: Optional[float]) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _std(values: Sequence[Any]) -> Optional[float]:
    numbers = [_safe_float(v) for v in values]
    numbers = [v for v in numbers if v is not None]
    if not numbers:
        return None
    mean = sum(numbers) / len(numbers)
    variance = sum((v - mean) ** 2 for v in numbers) / len(numbers)
    return sqrt(max(variance, 0.0))


def _extract_field(context: Any, *names: str) -> Any:
    if context is None:
        return None

    for name in names:
        if isinstance(context, dict) and name in context:
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


def _as_sequence(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _history(values: Any) -> Tuple[Any, ...]:
    # Contract: input is already M1 -> M6.
    # Never reverse it here.
    return _as_sequence(values)[:HISTORY_SIZE]


def _result_value(result: Any) -> Optional[float]:
    if result is None:
        return None

    text = str(result).strip().upper()

    if text in {"W", "WIN", "В"}:
        return 1.0
    if text in {"D", "DRAW", "Н"}:
        return 0.0
    if text in {"L", "LOSS", "П"}:
        return -1.0

    return None


def _baseline_recent(
    values: Sequence[Any],
) -> Tuple[Optional[float], Optional[float]]:
    values = tuple(values)[:HISTORY_SIZE]

    baseline = _mean(values[:3])
    recent = _weighted_mean(
        values[3:6],
        RECENT_WEIGHTS,
    )
    return baseline, recent


def _anomaly_from_values(values: Sequence[Any]) -> Optional[float]:
    values = tuple(values)[:HISTORY_SIZE]

    available = sum(_safe_float(v) is not None for v in values)
    if available < MIN_HISTORY_FOR_SIGNAL:
        return None

    baseline, recent = _baseline_recent(values)

    if baseline is None or recent is None:
        return None

    std = _std(values)
    if std is None:
        return None

    z_score = (recent - baseline) / (std + EPSILON)
    return _clamp(tanh(z_score / K_ZSCORE))


def _calculate_xg_anomaly(values: Sequence[Any]) -> Optional[float]:
    return _anomaly_from_values(values)


def _calculate_xga_anomaly(values: Sequence[Any]) -> Optional[float]:
    signal = _anomaly_from_values(values)
    # xGA down = defensive improvement = positive.
    return _clamp(-signal) if signal is not None else None


def _calculate_trend_signal(values: Sequence[Any]) -> Optional[float]:
    """
    Checks M3-M6 against the Baseline direction.

    If at least 3 of the 4 observations support the same direction,
    the trend is considered sustained.
    """

    values = tuple(values)[:HISTORY_SIZE]

    baseline, recent = _baseline_recent(values)
    if baseline is None or recent is None:
        return None

    direction = _sign(recent - baseline)
    if direction == 0:
        return 0.0

    window = values[2:6]  # M3, M4, M5, M6
    valid = [_safe_float(v) for v in window]
    valid = [v for v in valid if v is not None]

    if len(valid) < 3:
        return 0.0

    consistency = sum(
        _sign(v - baseline) == direction
        for v in valid
    )

    if consistency < TREND_MIN_CONSISTENCY:
        return 0.0

    # Contract strength is consistency / 4.
    return _clamp(direction * (consistency / 4.0))


def _calculate_result_signal(results: Sequence[Any]) -> Optional[float]:
    values = tuple(_result_value(v) for v in tuple(results)[:HISTORY_SIZE])

    if sum(v is not None for v in values) < MIN_HISTORY_FOR_SIGNAL:
        return None

    baseline, recent = _baseline_recent(values)

    if baseline is None or recent is None:
        return None

    return _clamp(tanh(recent - baseline))


def _calculate_gap(
    xg_anomaly: Optional[float],
    xga_anomaly: Optional[float],
    result_signal: Optional[float],
) -> Optional[float]:
    if xg_anomaly is None or xga_anomaly is None or result_signal is None:
        return None

    process_score = (
        0.50 * xg_anomaly
        + 0.50 * (-xga_anomaly)
    )
    return _clamp(process_score - result_signal)


def _quality(values: Sequence[Any]) -> float:
    values = tuple(values)[:HISTORY_SIZE]
    available = sum(_safe_float(v) is not None for v in values)
    return max(0.0, min(1.0, available / HISTORY_SIZE))


def _calculate_evidence_quality(
    xg: Sequence[Any],
    xga: Sequence[Any],
    results: Sequence[Any],
) -> float:
    return (
        EVIDENCE_XG_WEIGHT * _quality(xg)
        + EVIDENCE_XGA_WEIGHT * _quality(xga)
        + EVIDENCE_RESULT_WEIGHT * _quality(results)
    )


def _evidence_status(value: float) -> str:
    if value >= 0.80:
        return "HIGH"
    if value >= 0.50:
        return "MEDIUM"
    if value >= 0.30:
        return "LOW"
    return "INSUFFICIENT"


def _detect_spike(values: Sequence[Any]) -> bool:
    values = tuple(values)[:HISTORY_SIZE]
    valid = [_safe_float(v) for v in values]
    valid = [v for v in valid if v is not None]

    if len(valid) < MIN_HISTORY_FOR_SIGNAL:
        return False

    previous = valid[:-1]
    if len(previous) < 2:
        return False

    std = _std(previous)
    if std is None:
        return False

    z = abs(valid[-1] - _mean(previous)) / (std + EPSILON)
    return z >= SPIKE_Z_THRESHOLD


def _detect_reversal(values: Sequence[Any]) -> bool:
    values = tuple(values)[:HISTORY_SIZE]
    valid = [_safe_float(v) for v in values]
    valid = [v for v in valid if v is not None]

    if len(valid) < REVERSAL_MIN_OBSERVATIONS:
        return False

    tail = valid[-4:]
    deltas = [
        tail[i] - tail[i - 1]
        for i in range(1, len(tail))
    ]

    first_direction = _sign(deltas[0])
    previous_direction = _sign(deltas[-2])
    last_direction = _sign(deltas[-1])

    if first_direction == 0 or previous_direction == 0 or last_direction == 0:
        return False

    return (
        first_direction == previous_direction
        and last_direction != first_direction
    )


def _combine(
    xg: Optional[float],
    xga: Optional[float],
    trend: Optional[float],
    result: Optional[float],
) -> Optional[float]:
    components = (
        (xg, ANOMALY_XG_WEIGHT),
        (xga, ANOMALY_XGA_WEIGHT),
        (trend, ANOMALY_TREND_WEIGHT),
        (result, ANOMALY_RESULT_WEIGHT),
    )

    available = [(v, w) for v, w in components if v is not None]
    if not available:
        return None

    weight_sum = sum(w for _, w in available)
    signal = sum(v * w for v, w in available) / weight_sum

    return _clamp(signal)


def _classify(signal: Optional[float]) -> Tuple[str, float]:
    if signal is None:
        return "none", 0.0

    strength = abs(signal)

    if signal > ANOMALY_TYPE_TOLERANCE:
        return "positive", strength

    if signal < -ANOMALY_TYPE_TOLERANCE:
        return "negative", strength

    return "none", strength


def _extract_histories(context: Any) -> Tuple[Tuple[Any, ...], ...]:
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


class FormAnomaly:
    """Deterministic detector of sustained form anomalies."""

    def analyze(self, context: Any) -> AnomalyResult:
        xg_history, xga_history, results_history = _extract_histories(context)

        xg_anomaly = _calculate_xg_anomaly(xg_history)
        xga_anomaly = _calculate_xga_anomaly(xga_history)

        # Prefer xG as the primary process trend.
        trend_signal = _calculate_trend_signal(xg_history)
        if trend_signal is None:
            trend_signal = _calculate_trend_signal(xga_history)

        result_signal = _calculate_result_signal(results_history)

        gap = _calculate_gap(
            xg_anomaly,
            xga_anomaly,
            result_signal,
        )

        anomaly_signal = _combine(
            xg_anomaly,
            xga_anomaly,
            trend_signal,
            result_signal,
        )

        anomaly_type, anomaly_strength = _classify(anomaly_signal)

        evidence_quality = _calculate_evidence_quality(
            xg_history,
            xga_history,
            results_history,
        )

        spike_detected = (
            _detect_spike(xg_history)
            or _detect_spike(xga_history)
        )

        reversal_detected = (
            _detect_reversal(xg_history)
            or _detect_reversal(xga_history)
        )

        xg_baseline, xg_recent = _baseline_recent(xg_history)
        xga_baseline, xga_recent = _baseline_recent(xga_history)

        result_values = tuple(_result_value(v) for v in results_history)
        result_baseline, result_recent = _baseline_recent(result_values)

        diagnostics = {
            "version": FORM_ANOMALY_VERSION,
            "formula_status": FORMULA_STATUS,
            "history_order": "M1->M6",
            "baseline": ["M1", "M2", "M3"],
            "recent": ["M4", "M5", "M6"],
            "recent_weights": list(RECENT_WEIGHTS),
            "epsilon": EPSILON,
            "k_zscore": K_ZSCORE,
            "xg_baseline": xg_baseline,
            "xg_recent": xg_recent,
            "xga_baseline": xga_baseline,
            "xga_recent": xga_recent,
            "result_baseline": result_baseline,
            "result_recent": result_recent,
            "xg_observations": _quality(xg_history),
            "xga_observations": _quality(xga_history),
            "result_observations": _quality(results_history),
            "evidence_status": _evidence_status(evidence_quality),
            "spike_detected": spike_detected,
            "reversal_detected": reversal_detected,
            "prediction_impact": "none",
            "final_formula": (
                "0.35*xG_Anomaly + 0.30*xGA_Anomaly "
                "+ 0.20*TrendSignal + 0.15*ResultSignal"
            ),
            "gap_formula": (
                "0.50*xG_Anomaly + 0.50*(-xGA_Anomaly) "
                "- ResultSignal"
            ),
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
            process_result_gap=gap,
            spike_detected=spike_detected,
            reversal_detected=reversal_detected,
            diagnostics=diagnostics,
        )


def analyze_anomaly(context: Any) -> AnomalyResult:
    return FormAnomaly().analyze(context)


__all__ = [
    "FORM_ANOMALY_VERSION",
    "FORMULA_STATUS",
    "AnomalyResult",
    "FormAnomaly",
    "analyze_anomaly",
]
