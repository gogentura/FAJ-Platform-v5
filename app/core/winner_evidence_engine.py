#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
WINNER EVIDENCE ENGINE v1.0
============================================================

PURPOSE
-------
WinnerEvidenceEngine is an independent analytical evidence layer.

It does NOT:
    - change GoalModel lambda
    - change ProbabilityModel probabilities
    - change ScorePredictor output
    - change home_xg / away_xg
    - change 1X2 / BTTS / totals / score distribution
    - use bookmaker odds
    - use post-match information
    - use observed_xg / final score / future events
    - learn
    - write to database / ETC / Rating / Learning
    - call any parser
    - have side effects

It ONLY answers:

    "How strongly and how independently do the available
     FAJ organs support or contradict the primary 1X2
     direction already produced by ProbabilityModel?"

ARCHITECTURE
------------
    GoalModel
        ↓
    ProbabilityModel
        ↓
    PRIMARY 1X2 (PROBABILITY family)
        ↓
    WinnerEvidenceEngine
        ↓
    Evidence families:
        PROBABILITY
        FORM
        ATTACK
        DEFENCE
        CONTROL
        SPECIAL
        STRUCTURAL
        ↓
    directional consensus per family
        ↓
    evidence_score ∈ [-1, +1]
        ↓
    evidence_preferred_direction
        ↓
    consensus / confidence

DESIGN PRINCIPLES
-----------------
1. Family-first, not organ-voting.
2. Directional consensus via strength × quality,
   not raw count.
3. Correlated signals combined into a single group
   BEFORE family directional consensus.
4. PROBABILITY is PRIMARY; it does NOT contribute
   to evidence_score.
5. evidence_score = mean(FORM, ATTACK, DEFENCE,
   CONTROL, SPECIAL, STRUCTURAL).
6. SPECIAL cannot create STRONG_CONFLICT.
7. DRAW is a separate, restricted channel in v1.
8. None != 0.
9. Missing observations stay UNAVAILABLE.
10. Deterministic.
11. Pure: input -> calculate -> result.
12. All contract constants live at the top of the file.

CONTRACT VERSION
----------------
WEE v1.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# VERSION
# ============================================================

WEE_VERSION = "1.0"


# ============================================================
# CONTRACT CONSTANTS (WEE v1.0)
# ------------------------------------------------------------
# These constants are part of the WEE v1.0 specification.
# Changing any value means a new WEE version.
# ============================================================

# Neutral tolerance for a single normalized signal.
NEUTRAL_TOL = 0.05

# Dominance ratio inside a family directional consensus.
DOMINANCE_RATIO = 0.50

# Thresholds for support / conflict classification.
SUPPORT_TOL = 0.10
CONFLICT_TOL = 0.10
STRONG_TOL = 0.50

# Coverage thresholds.
COVERAGE_MIN = 0.50
COVERAGE_STRONG = 0.83

# Evidence score tolerance.
EVIDENCE_TOL = 0.05

# Confidence contribution constants.
QUALITY_WEIGHT = 0.20
COVERAGE_WEIGHT = 0.10

# Total number of families considered for coverage.
TOTAL_FAMILIES = 6   # FORM, ATTACK, DEFENCE, CONTROL, SPECIAL, STRUCTURAL

# Normalization fallback when history sigma is unavailable.
FALLBACK_SIGMA = 1.0

# Finishing delta scaling.
FINISHING_DELTA_SCALE = 0.5

# PairRating strength enum -> number mapping.
PAIR_STRENGTH_MAP = {
    "NEUTRAL": 0.00,
    "SLIGHT": 0.25,
    "MODERATE": 0.50,
    "STRONG": 0.75,
    "VERY_STRONG": 1.00,
}

# SpecialForm composite range normalization: [-0.30, +0.30] -> [-1, +1].
SPECIAL_COMPOSITE_SCALE = 1.0 / 0.30


# ============================================================
# AVAILABILITY
# ============================================================

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
UNAVAILABLE = "UNAVAILABLE"


# ============================================================
# DIRECTION
# ============================================================

HOME = "HOME"
AWAY = "AWAY"
DRAW = "DRAW"
NEUTRAL = "NEUTRAL"


# ============================================================
# FAMILY NAMES
# ============================================================

FAM_PROBABILITY = "PROBABILITY"
FAM_FORM = "FORM"
FAM_ATTACK = "ATTACK"
FAM_DEFENCE = "DEFENCE"
FAM_CONTROL = "CONTROL"
FAM_SPECIAL = "SPECIAL"
FAM_STRUCTURAL = "STRUCTURAL"


# ============================================================
# CONSENSUS STATES
# ============================================================

CONS_STRONG_SUPPORT = "STRONG_SUPPORT"
CONS_SUPPORT = "SUPPORT"
CONS_WEAK_SUPPORT = "WEAK_SUPPORT"
CONS_CONFLICT = "CONFLICT"
CONS_STRONG_CONFLICT = "STRONG_CONFLICT"
CONS_INSUFFICIENT = "INSUFFICIENT"
CONS_DRAW_SUPPORT = "DRAW_SUPPORT"
CONS_DRAW_CONFLICT_STRONG = "DRAW_CONFLICT_STRONG"
CONS_DRAW_WEAK = "DRAW_WEAK"


# ============================================================
# EVIDENCE SIGNAL
# ============================================================

@dataclass
class EvidenceSignal:
    """
    Single normalized evidence signal.

    direction:
        HOME / AWAY / DRAW / NEUTRAL

    strength:
        [0, 1] or None when UNAVAILABLE.

    quality:
        [0, 1] or None when UNAVAILABLE.

    value:
        original mathematical value (for audit).

    reason:
        short deterministic machine-readable reason.
    """

    name: str
    direction: str
    strength: Optional[float]
    source_family: str
    availability: str
    quality: Optional[float]
    independence_key: str
    value: Optional[float]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# FAMILY RESULT
# ============================================================

@dataclass
class FamilyResult:
    """
    Aggregated result of one evidence family.
    """

    family: str
    direction: str
    strength: Optional[float]
    quality: Optional[float]
    availability: str
    score: Optional[float]        # signed ∈ [-1, +1]
    signal_count: int
    independence_keys: List[str]
    conflict: bool
    strong_conflict: bool
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# WINNER EVIDENCE RESULT
# ============================================================

@dataclass
class WinnerEvidenceResult:
    """
    Complete WinnerEvidenceEngine v1.0 output.
    """

    model_version: str

    primary_winner: str
    evidence_preferred_direction: Optional[str]

    home_probability: Optional[float]
    draw_probability: Optional[float]
    away_probability: Optional[float]
    probability_margin: Optional[float]
    probability_strength: Optional[float]

    evidence_score: Optional[float]
    evidence_confidence: Optional[float]
    family_coverage: float

    consensus: str

    agreement_count: int
    conflict_count: int
    neutral_count: int
    strong_conflict_count: int

    families: Dict[str, Dict[str, Any]]
    signals: List[Dict[str, Any]]
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Safe conversion to finite float.

    None / bool / NaN / inf remain None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _clamp(
    value: Optional[float],
    low: float = -1.0,
    high: float = 1.0,
) -> Optional[float]:
    if value is None:
        return None
    return max(low, min(high, value))


def _clamp01(value: Optional[float]) -> Optional[float]:
    return _clamp(value, 0.0, 1.0)


def _sign(value: Optional[float]) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _mean(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _std(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    mean = sum(clean) / len(clean)
    variance = sum((v - mean) ** 2 for v in clean) / len(clean)
    return math.sqrt(max(variance, 0.0))


def _get_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Unified access for dict / sqlite3.Row / dataclass / object.
    """

    if obj is None:
        return None

    for name in names:

        if isinstance(obj, dict):
            if name in obj:
                return obj[name]

        try:
            keys = obj.keys()
            if name in keys:
                return obj[name]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(obj, name)
        except AttributeError:
            pass

    return None


def _normalize_ratio_signal(
    home_value: Optional[float],
    away_value: Optional[float],
    scale: float,
) -> Optional[float]:
    """
    Ratio-form normalization for paired values:

        tanh((home - away) / scale)

    None if either side is missing.
    """

    if home_value is None or away_value is None:
        return None

    if scale <= 0:
        return None

    return _clamp(
        math.tanh(
            (home_value - away_value) / scale
        ),
        -1.0,
        1.0,
    )


def _normalize_delta_signal(
    home_value: Optional[float],
    away_value: Optional[float],
    scale: Optional[float],
) -> Optional[float]:
    """
    Delta-form normalization for paired values:

        tanh((home - away) / scale)

    Uses provided scale (e.g. combined historical std).
    If scale is None or too small, returns None.
    """

    if home_value is None or away_value is None:
        return None

    if scale is None or scale <= 1e-9:
        return None

    return _clamp(
        math.tanh(
            (home_value - away_value) / scale
        ),
        -1.0,
        1.0,
    )


def _direction_from_signed(
    value: Optional[float],
    tol: float = NEUTRAL_TOL,
) -> str:
    """
    Convert signed normalized value into HOME / AWAY / NEUTRAL.
    """

    if value is None:
        return NEUTRAL

    if abs(value) < tol:
        return NEUTRAL

    return HOME if value > 0 else AWAY


def _coverage_ratio(
    available: int,
    expected: int,
) -> float:
    if expected <= 0:
        return 0.0
    return max(0.0, min(1.0, available / expected))


# ============================================================
# INDIVIDUAL SIGNAL BUILDERS
# ------------------------------------------------------------
# Each builder returns an EvidenceSignal.
# Builders do not raise on missing data.
# Builders never convert None into 0.
# ============================================================

def _signal_probability(
    probability_result: Any,
) -> EvidenceSignal:
    """
    PROBABILITY family.

    Produces the primary winner and its separation strength.
    Not included in evidence_score.
    """

    home_p = _safe_float(_get_value(probability_result, "home_win"))
    draw_p = _safe_float(_get_value(probability_result, "draw"))
    away_p = _safe_float(_get_value(probability_result, "away_win"))

    probs = {
        HOME: home_p,
        DRAW: draw_p,
        AWAY: away_p,
    }

    available_probs = {k: v for k, v in probs.items() if v is not None}

    if len(available_probs) < 3:
        return EvidenceSignal(
            name="probability",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_PROBABILITY,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="POISSON_PROBABILITY",
            value=None,
            reason="ProbabilityModel result unavailable",
        )

    ordered = sorted(
        available_probs.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    primary, primary_value = ordered[0]
    _, second_value = ordered[1]

    separation = primary_value - second_value
    strength = _clamp01(abs(separation) / 0.25)

    return EvidenceSignal(
        name="probability",
        direction=primary,
        strength=strength,
        source_family=FAM_PROBABILITY,
        availability=AVAILABLE,
        quality=1.0,
        independence_key="POISSON_PROBABILITY",
        value=primary_value,
        reason=f"ProbabilityModel primary winner = {primary}",
    )


def _signal_form_win(
    form_win_comparison: Any,
) -> EvidenceSignal:
    """
    FORM family.

    Uses FormWinComparison.relative_advantage.
    """

    relative = _safe_float(
        _get_value(form_win_comparison, "relative_advantage")
    )
    quality = _safe_float(
        _get_value(form_win_comparison, "evidence_quality")
    )

    if relative is None:
        return EvidenceSignal(
            name="form_win",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_FORM,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="FORM_AGGREGATE",
            value=None,
            reason="FormWinComparison unavailable",
        )

    strength = _clamp01(abs(relative))
    direction = _direction_from_signed(relative)

    return EvidenceSignal(
        name="form_win",
        direction=direction,
        strength=strength,
        source_family=FAM_FORM,
        availability=AVAILABLE if quality is not None else PARTIAL,
        quality=_clamp01(quality) if quality is not None else 0.5,
        independence_key="FORM_AGGREGATE",
        value=relative,
        reason=f"FormWin relative advantage = {relative:+.3f}",
    )


def _signal_defence(
    home_defence: Any,
    away_defence: Any,
) -> EvidenceSignal:
    """
    DEFENCE family.

    Uses home/away DefenceState.defence_score and evidence_quality.
    """

    home_score = _safe_float(_get_value(home_defence, "defence_score"))
    away_score = _safe_float(_get_value(away_defence, "defence_score"))

    home_quality = _safe_float(_get_value(home_defence, "evidence_quality"))
    away_quality = _safe_float(_get_value(away_defence, "evidence_quality"))

    if home_score is None or away_score is None:
        return EvidenceSignal(
            name="defence",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_DEFENCE,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="DEFENCE_AGGREGATE",
            value=None,
            reason="Defence score unavailable for one or both teams",
        )

    delta = _clamp(home_score - away_score, -1.0, 1.0)
    direction = _direction_from_signed(delta)
    strength = _clamp01(abs(delta))

    quality = _mean([home_quality, away_quality])

    return EvidenceSignal(
        name="defence",
        direction=direction,
        strength=strength,
        source_family=FAM_DEFENCE,
        availability=AVAILABLE if quality is not None else PARTIAL,
        quality=_clamp01(quality) if quality is not None else 0.5,
        independence_key="DEFENCE_AGGREGATE",
        value=delta,
        reason=f"Defence delta = {delta:+.3f}",
    )


def _signal_control(
    control_comparison: Any,
) -> EvidenceSignal:
    """
    CONTROL family.

    Uses compare_control(...) output:
        home_signal, away_signal, control_advantage
    """

    home_signal = _safe_float(_get_value(control_comparison, "home_signal"))
    away_signal = _safe_float(_get_value(control_comparison, "away_signal"))

    if home_signal is None or away_signal is None:
        return EvidenceSignal(
            name="control",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_CONTROL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="POSSESSION_CONTROL",
            value=None,
            reason="Control signal unavailable",
        )

    delta = _clamp(home_signal - away_signal, -1.0, 1.0)
    direction = _direction_from_signed(delta)
    strength = _clamp01(abs(delta))

    home_result = _get_value(control_comparison, "home_control") or {}
    away_result = _get_value(control_comparison, "away_control") or {}

    home_cov = _control_coverage(home_result)
    away_cov = _control_coverage(away_result)
    quality = _mean([home_cov, away_cov])

    return EvidenceSignal(
        name="control",
        direction=direction,
        strength=strength,
        source_family=FAM_CONTROL,
        availability=AVAILABLE if quality is not None else PARTIAL,
        quality=_clamp01(quality) if quality is not None else 0.5,
        independence_key="POSSESSION_CONTROL",
        value=delta,
        reason=f"Control delta = {delta:+.3f}",
    )


def _control_coverage(
    control_result: Any,
) -> Optional[float]:
    """
    Coverage of the five control sources:
        possession, passes, pass_accuracy, shots, big_chances
    """

    if control_result is None:
        return None

    raw = _get_value(control_result, "raw_components")
    if not isinstance(raw, dict):
        return None

    keys = (
        "possession",
        "passes",
        "accuracy",
        "shots",
        "big_chances",
    )

    available = 0
    for key in keys:
        value = _safe_float(raw.get(key))
        if value is not None:
            available += 1

    return _coverage_ratio(available, len(keys))


def _signal_anomaly(
    anomaly_result: Any,
    side: str,   # "home" | "away"
) -> EvidenceSignal:
    """
    SPECIAL family.
    Anomaly component.
    """

    signal = _safe_float(_get_value(anomaly_result, "anomaly_signal"))
    quality = _safe_float(_get_value(anomaly_result, "evidence_quality"))

    if signal is None:
        return EvidenceSignal(
            name=f"anomaly_{side}",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_SPECIAL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="ANOMALY",
            value=None,
            reason=f"Anomaly signal unavailable for {side}",
        )

    direction = _direction_from_signed(signal)
    strength = _clamp01(abs(signal))

    return EvidenceSignal(
        name=f"anomaly_{side}",
        direction=direction,
        strength=strength,
        source_family=FAM_SPECIAL,
        availability=AVAILABLE if quality is not None else PARTIAL,
        quality=_clamp01(quality) if quality is not None else 0.5,
        independence_key="ANOMALY",
        value=signal,
        reason=f"Anomaly signal {side} = {signal:+.3f}",
    )


def _signal_special(
    special_result: Any,
    side: str,
) -> EvidenceSignal:
    """
    SPECIAL family.
    SpecialForm component.
    """

    composite = _safe_float(
        _get_value(special_result, "composite_signal")
    )

    diagnostics = _get_value(special_result, "diagnostics") or {}
    detected = 0
    total = 8   # eight special effects in SpecialForm v1.0

    if isinstance(diagnostics, dict):
        detected = int(diagnostics.get("detected_count", 0) or 0)

    quality = _coverage_ratio(detected, total)

    if composite is None:
        return EvidenceSignal(
            name=f"special_{side}",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_SPECIAL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="SPECIAL",
            value=None,
            reason=f"SpecialForm composite unavailable for {side}",
        )

    # Normalize [-0.30, +0.30] -> [-1, +1]
    normalized = _clamp(
        composite * SPECIAL_COMPOSITE_SCALE,
        -1.0,
        1.0,
    )
    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))

    return EvidenceSignal(
        name=f"special_{side}",
        direction=direction,
        strength=strength,
        source_family=FAM_SPECIAL,
        availability=AVAILABLE if quality > 0 else PARTIAL,
        quality=_clamp01(quality),
        independence_key="SPECIAL",
        value=composite,
        reason=f"SpecialForm composite {side} = {composite:+.3f}",
    )


def _signal_pair_rating(
    pair_rating: Any,
) -> EvidenceSignal:
    """
    STRUCTURAL family.

    Uses PairRating (dataclass, dict, or None).
    """

    if pair_rating is None:
        return EvidenceSignal(
            name="pair_rating",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_STRUCTURAL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="STRUCTURAL_RATING",
            value=None,
            reason="PairRating unavailable",
        )

    direction_raw = _get_value(pair_rating, "winner_direction")
    strength_raw = _get_value(pair_rating, "direction_strength")

    if direction_raw is None:
        return EvidenceSignal(
            name="pair_rating",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_STRUCTURAL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="STRUCTURAL_RATING",
            value=None,
            reason="PairRating direction missing",
        )

    if direction_raw == NEUTRAL:
        return EvidenceSignal(
            name="pair_rating",
            direction=NEUTRAL,
            strength=0.0,
            source_family=FAM_STRUCTURAL,
            availability=AVAILABLE,
            quality=1.0,
            independence_key="STRUCTURAL_RATING",
            value=0.0,
            reason="PairRating = NEUTRAL",
        )

    if direction_raw not in (HOME, AWAY):
        return EvidenceSignal(
            name="pair_rating",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_STRUCTURAL,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="STRUCTURAL_RATING",
            value=None,
            reason=f"PairRating direction unrecognized: {direction_raw}",
        )

    strength_value = PAIR_STRENGTH_MAP.get(str(strength_raw), 0.0)

    signed = strength_value if direction_raw == HOME else -strength_value

    return EvidenceSignal(
        name="pair_rating",
        direction=direction_raw,
        strength=strength_value,
        source_family=FAM_STRUCTURAL,
        availability=AVAILABLE,
        quality=1.0,
        independence_key="STRUCTURAL_RATING",
        value=signed,
        reason=f"PairRating = {direction_raw} / {strength_raw}",
    )


# ============================================================
# ATTACK FAMILY — CORRELATED GROUP + SUB-SIGNALS
# ============================================================

def _history_std(
    home_series: Any,
    away_series: Any,
) -> Optional[float]:
    """
    Combined standard deviation for delta normalization.

    Uses both home and away histories.
    Missing observations excluded.
    """

    values: List[Optional[float]] = []

    for series in (home_series, away_series):
        if series is None:
            continue
        try:
            for item in series:
                values.append(_safe_float(item))
        except TypeError:
            continue

    return _std(values)


def _signal_shot_volume(
    home_form_model: Any,
    away_form_model: Any,
) -> EvidenceSignal:
    """
    ATTACK sub-signal (correlated group member).
    """

    home_avg = _safe_float(_get_value(home_form_model, "shots_avg"))
    away_avg = _safe_float(_get_value(away_form_model, "shots_avg"))

    home_hist = _get_value(home_form_model, "shots_history") \
        if _get_value(home_form_model, "shots_history") is not None \
        else _get_value(home_form_model, "shots_history", "_shots")
    away_hist = _get_value(away_form_model, "shots_history")

    scale = _history_std(home_hist, away_hist)

    if home_avg is None or away_avg is None:
        return EvidenceSignal(
            name="shot_volume",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="SHOT_VOLUME",
            value=None,
            reason="Shots average unavailable",
        )

    normalized = _normalize_delta_signal(home_avg, away_avg, scale)
    if normalized is None:
        # Fallback ratio normalization with FALLBACK_SIGMA
        normalized = _normalize_delta_signal(
            home_avg, away_avg, FALLBACK_SIGMA
        )

    if normalized is None:
        return EvidenceSignal(
            name="shot_volume",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=PARTIAL,
            quality=0.5,
            independence_key="SHOT_VOLUME",
            value=None,
            reason="Shots delta could not be normalized",
        )

    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))
    quality = _coverage_ratio(
        int(home_avg is not None) + int(away_avg is not None),
        2,
    )

    return EvidenceSignal(
        name="shot_volume",
        direction=direction,
        strength=strength,
        source_family=FAM_ATTACK,
        availability=AVAILABLE,
        quality=quality,
        independence_key="SHOT_VOLUME",
        value=normalized,
        reason=f"Shot volume delta = {normalized:+.3f}",
    )


def _signal_shot_quality(
    home_form_model: Any,
    away_form_model: Any,
) -> EvidenceSignal:
    """
    ATTACK sub-signal (correlated group member).
    """

    home_avg = _safe_float(_get_value(home_form_model, "shots_on_target_avg"))
    away_avg = _safe_float(_get_value(away_form_model, "shots_on_target_avg"))

    home_hist = _get_value(home_form_model, "shots_on_target_history")
    away_hist = _get_value(away_form_model, "shots_on_target_history")

    scale = _history_std(home_hist, away_hist)

    if home_avg is None or away_avg is None:
        return EvidenceSignal(
            name="shot_quality",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="SHOT_QUALITY",
            value=None,
            reason="Shots on target average unavailable",
        )

    normalized = _normalize_delta_signal(home_avg, away_avg, scale)
    if normalized is None:
        normalized = _normalize_delta_signal(
            home_avg, away_avg, FALLBACK_SIGMA
        )

    if normalized is None:
        return EvidenceSignal(
            name="shot_quality",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=PARTIAL,
            quality=0.5,
            independence_key="SHOT_QUALITY",
            value=None,
            reason="SOT delta could not be normalized",
        )

    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))
    quality = _coverage_ratio(
        int(home_avg is not None) + int(away_avg is not None),
        2,
    )

    return EvidenceSignal(
        name="shot_quality",
        direction=direction,
        strength=strength,
        source_family=FAM_ATTACK,
        availability=AVAILABLE,
        quality=quality,
        independence_key="SHOT_QUALITY",
        value=normalized,
        reason=f"SOT delta = {normalized:+.3f}",
    )


def _signal_big_chances(
    home_form_model: Any,
    away_form_model: Any,
) -> EvidenceSignal:
    """
    ATTACK sub-signal.
    """

    home_avg = _safe_float(_get_value(home_form_model, "big_chances_avg"))
    away_avg = _safe_float(_get_value(away_form_model, "big_chances_avg"))

    home_hist = _get_value(home_form_model, "big_chances_history")
    away_hist = _get_value(away_form_model, "big_chances_history")

    scale = _history_std(home_hist, away_hist)

    if home_avg is None or away_avg is None:
        return EvidenceSignal(
            name="big_chances",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="BIG_CHANCES",
            value=None,
            reason="Big chances average unavailable",
        )

    normalized = _normalize_delta_signal(home_avg, away_avg, scale)
    if normalized is None:
        normalized = _normalize_delta_signal(
            home_avg, away_avg, FALLBACK_SIGMA
        )

    if normalized is None:
        return EvidenceSignal(
            name="big_chances",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=PARTIAL,
            quality=0.5,
            independence_key="BIG_CHANCES",
            value=None,
            reason="Big chances delta could not be normalized",
        )

    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))

    return EvidenceSignal(
        name="big_chances",
        direction=direction,
        strength=strength,
        source_family=FAM_ATTACK,
        availability=AVAILABLE,
        quality=1.0,
        independence_key="BIG_CHANCES",
        value=normalized,
        reason=f"Big chances delta = {normalized:+.3f}",
    )


def _signal_corners(
    home_form_model: Any,
    away_form_model: Any,
) -> EvidenceSignal:
    """
    ATTACK sub-signal (set-piece pressure).
    """

    home_avg = _safe_float(_get_value(home_form_model, "corners_for_avg"))
    away_avg = _safe_float(_get_value(away_form_model, "corners_for_avg"))

    home_hist = _get_value(home_form_model, "corners_for_history")
    away_hist = _get_value(away_form_model, "corners_for_history")

    scale = _history_std(home_hist, away_hist)

    if home_avg is None or away_avg is None:
        return EvidenceSignal(
            name="corners",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="SET_PIECE_PRESSURE",
            value=None,
            reason="Corners average unavailable",
        )

    normalized = _normalize_delta_signal(home_avg, away_avg, scale)
    if normalized is None:
        normalized = _normalize_delta_signal(
            home_avg, away_avg, FALLBACK_SIGMA
        )

    if normalized is None:
        return EvidenceSignal(
            name="corners",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=PARTIAL,
            quality=0.5,
            independence_key="SET_PIECE_PRESSURE",
            value=None,
            reason="Corners delta could not be normalized",
        )

    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))

    return EvidenceSignal(
        name="corners",
        direction=direction,
        strength=strength,
        source_family=FAM_ATTACK,
        availability=AVAILABLE,
        quality=1.0,
        independence_key="SET_PIECE_PRESSURE",
        value=normalized,
        reason=f"Corners delta = {normalized:+.3f}",
    )


def _signal_finishing(
    home_form_model: Any,
    away_form_model: Any,
) -> EvidenceSignal:
    """
    ATTACK sub-signal (finishing delta).
    """

    home_delta = _safe_float(_get_value(home_form_model, "finishing_delta"))
    away_delta = _safe_float(_get_value(away_form_model, "finishing_delta"))

    if home_delta is None or away_delta is None:
        return EvidenceSignal(
            name="finishing",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=UNAVAILABLE,
            quality=None,
            independence_key="FINISHING",
            value=None,
            reason="Finishing delta unavailable",
        )

    normalized = _normalize_ratio_signal(
        home_delta, away_delta, FINISHING_DELTA_SCALE
    )

    if normalized is None:
        return EvidenceSignal(
            name="finishing",
            direction=NEUTRAL,
            strength=None,
            source_family=FAM_ATTACK,
            availability=PARTIAL,
            quality=0.5,
            independence_key="FINISHING",
            value=None,
            reason="Finishing delta could not be normalized",
        )

    direction = _direction_from_signed(normalized)
    strength = _clamp01(abs(normalized))

    return EvidenceSignal(
        name="finishing",
        direction=direction,
        strength=strength,
        source_family=FAM_ATTACK,
        availability=AVAILABLE,
        quality=1.0,
        independence_key="FINISHING",
        value=normalized,
        reason=f"Finishing delta = {normalized:+.3f}",
    )


# ============================================================
# FAMILY AGGREGATION
# ============================================================

def _directional_consensus(
    signals: List[EvidenceSignal],
) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Directional consensus via strength × quality.

    Returns:
        (direction, strength, quality)
    """

    usable = [
        s for s in signals
        if s.availability != UNAVAILABLE
        and s.strength is not None
        and s.quality is not None
    ]

    if not usable:
        return NEUTRAL, None, None

    pos = 0.0
    neg = 0.0
    neutral_w = 0.0
    total_w = 0.0

    for s in usable:
        signed = s.strength * s.quality
        total_w += signed

        if s.direction == HOME:
            pos += signed
        elif s.direction == AWAY:
            neg += signed
        else:
            neutral_w += signed

    T = pos + neg

    if T <= 1e-9:
        return NEUTRAL, 0.0, _clamp01(total_w / max(len(usable), 1))

    D = pos - neg
    dominance = abs(D) / T

    if dominance < DOMINANCE_RATIO:
        return NEUTRAL, 0.0, _clamp01(total_w / max(len(usable), 1))

    direction = HOME if D > 0 else AWAY
    strength = _clamp01(dominance)

    return direction, strength, _clamp01(total_w / max(len(usable), 1))


def _aggregate_family(
    family: str,
    signals: List[EvidenceSignal],
    correlated_groups: Optional[Dict[str, List[str]]] = None,
) -> FamilyResult:
    """
    Aggregate signals into one FamilyResult.

    correlated_groups:
        map group_name -> list of independence_keys that must be
        merged into a single effective signal BEFORE family consensus.
    """

    if correlated_groups is None:
        correlated_groups = {}

    # --------------------------------------------------------
    # Determine if any group keys are present
    # --------------------------------------------------------

    consumed: set = set()
    effective_signals: List[EvidenceSignal] = []

    for group_name, keys in correlated_groups.items():

        group_members = [
            s for s in signals
            if s.independence_key in keys
        ]

        if not group_members:
            continue

        usable = [
            s for s in group_members
            if s.availability != UNAVAILABLE
            and s.strength is not None
            and s.quality is not None
        ]

        if not usable:
            # All members unavailable: skip group
            for s in group_members:
                consumed.add(id(s))
            continue

        signed_values = []
        abs_values = []
        quality_values = []

        for s in usable:
            sign = +1.0 if s.direction == HOME else (
                -1.0 if s.direction == AWAY else 0.0
            )
            signed_values.append(sign * s.strength * s.quality)
            abs_values.append(s.strength * s.quality)
            quality_values.append(s.quality)

        group_raw = sum(signed_values) / len(signed_values)
        group_abs = sum(abs_values) / len(abs_values)
        group_quality = (
            sum(quality_values) / len(quality_values)
        ) * (len(usable) / len(group_members))

        group_direction = _direction_from_signed(group_raw)

        group_signal = EvidenceSignal(
            name=group_name,
            direction=group_direction,
            strength=_clamp01(group_abs),
            source_family=family,
            availability=(
                AVAILABLE if len(usable) == len(group_members)
                else PARTIAL
            ),
            quality=_clamp01(group_quality),
            independence_key=group_name,
            value=group_raw,
            reason=f"{group_name} group raw = {group_raw:+.3f}",
        )

        effective_signals.append(group_signal)

        for s in group_members:
            consumed.add(id(s))

    # --------------------------------------------------------
    # Keep standalone signals
    # --------------------------------------------------------

    for s in signals:
        if id(s) in consumed:
            continue
        effective_signals.append(s)

    # --------------------------------------------------------
    # Directional consensus over effective signals
    # --------------------------------------------------------

    direction, strength, quality = _directional_consensus(effective_signals)

    available_signals = [
        s for s in effective_signals
        if s.availability != UNAVAILABLE
    ]

    # Signed family score
    if strength is None or direction == NEUTRAL:
        score = 0.0
    elif direction == HOME:
        score = strength
    else:
        score = -strength

    availability = (
        AVAILABLE if available_signals else UNAVAILABLE
    )

    independence_keys = sorted(set(
        s.independence_key for s in effective_signals
    ))

    return FamilyResult(
        family=family,
        direction=direction,
        strength=strength,
        quality=quality,
        availability=availability,
        score=score,
        signal_count=len(effective_signals),
        independence_keys=independence_keys,
        conflict=False,
        strong_conflict=False,
        diagnostics={
            "effective_signals": [s.to_dict() for s in effective_signals],
            "correlated_groups_used": list(correlated_groups.keys()),
        },
    )


# ============================================================
# SPECIAL FAMILY AGGREGATION
# ============================================================

def _aggregate_special(
    home_anomaly: Any,
    away_anomaly: Any,
    home_special: Any,
    away_special: Any,
) -> FamilyResult:
    """
    SPECIAL family: aggregates Anomaly + SpecialForm.

    It cannot create STRONG_CONFLICT (enforced at consensus level).
    """

    signals: List[EvidenceSignal] = []

    anom_home = _signal_anomaly(home_anomaly, "home")
    anom_away = _signal_anomaly(away_anomaly, "away")

    # Anomaly is per-team; convert to a differential:
    # positive signal on home minus positive signal on away.
    if (
        anom_home.availability != UNAVAILABLE
        and anom_away.availability != UNAVAILABLE
        and anom_home.strength is not None
        and anom_away.strength is not None
    ):
        home_signed = (
            anom_home.strength if anom_home.direction == HOME else (
                -anom_home.strength if anom_home.direction == AWAY else 0.0
            )
        )
        away_signed = (
            anom_away.strength if anom_away.direction == HOME else (
                -anom_away.strength if anom_away.direction == AWAY else 0.0
            )
        )

        diff = _clamp(home_signed - away_signed, -1.0, 1.0)
        direction = _direction_from_signed(diff)
        strength = _clamp01(abs(diff))

        signals.append(
            EvidenceSignal(
                name="anomaly_differential",
                direction=direction,
                strength=strength,
                source_family=FAM_SPECIAL,
                availability=AVAILABLE,
                quality=_clamp01(
                    _mean([anom_home.quality, anom_away.quality]) or 0.5
                ),
                independence_key="ANOMALY",
                value=diff,
                reason=f"Anomaly differential = {diff:+.3f}",
            )
        )
    else:
        signals.append(
            EvidenceSignal(
                name="anomaly_differential",
                direction=NEUTRAL,
                strength=None,
                source_family=FAM_SPECIAL,
                availability=UNAVAILABLE,
                quality=None,
                independence_key="ANOMALY",
                value=None,
                reason="Anomaly differential unavailable",
            )
        )

    sp_home = _signal_special(home_special, "home")
    sp_away = _signal_special(away_special, "away")

    if (
        sp_home.availability != UNAVAILABLE
        and sp_away.availability != UNAVAILABLE
        and sp_home.strength is not None
        and sp_away.strength is not None
    ):
        home_signed = (
            sp_home.strength if sp_home.direction == HOME else (
                -sp_home.strength if sp_home.direction == AWAY else 0.0
            )
        )
        away_signed = (
            sp_away.strength if sp_away.direction == HOME else (
                -sp_away.strength if sp_away.direction == AWAY else 0.0
            )
        )

        diff = _clamp(home_signed - away_signed, -1.0, 1.0)
        direction = _direction_from_signed(diff)
        strength = _clamp01(abs(diff))

        signals.append(
            EvidenceSignal(
                name="special_differential",
                direction=direction,
                strength=strength,
                source_family=FAM_SPECIAL,
                availability=AVAILABLE,
                quality=_clamp01(
                    _mean([sp_home.quality, sp_away.quality]) or 0.5
                ),
                independence_key="SPECIAL",
                value=diff,
                reason=f"SpecialForm differential = {diff:+.3f}",
            )
        )
    else:
        signals.append(
            EvidenceSignal(
                name="special_differential",
                direction=NEUTRAL,
                strength=None,
                source_family=FAM_SPECIAL,
                availability=UNAVAILABLE,
                quality=None,
                independence_key="SPECIAL",
                value=None,
                reason="SpecialForm differential unavailable",
            )
        )

    return _aggregate_family(
        family=FAM_SPECIAL,
        signals=signals,
        correlated_groups=None,
    )


# ============================================================
# CONSENSUS
# ============================================================

def _classify_consensus(
    primary: str,
    families: Dict[str, FamilyResult],
    evidence_score: Optional[float],
    coverage: float,
) -> Tuple[str, int, int, int, int]:
    """
    Returns:
        (consensus, agreement, conflict, neutral, strong_conflict)
    """

    if primary == DRAW:
        return _classify_draw_consensus(
            families=families,
            coverage=coverage,
        )

    agreement = 0
    conflict = 0
    neutral = 0
    strong_conflict = 0

    primary_sign = +1 if primary == HOME else -1

    for family_name, result in families.items():

        if result.availability == UNAVAILABLE:
            continue

        if result.score is None:
            neutral += 1
            continue

        signed = result.score
        magnitude = abs(signed)

        if magnitude < NEUTRAL_TOL:
            neutral += 1
            continue

        if _sign(signed) == primary_sign:
            if magnitude >= SUPPORT_TOL:
                agreement += 1
            else:
                neutral += 1
        else:
            if magnitude >= CONFLICT_TOL:
                conflict += 1
                if (
                    magnitude >= STRONG_TOL
                    and family_name != FAM_SPECIAL
                ):
                    strong_conflict += 1

    if coverage < COVERAGE_MIN:
        return CONS_INSUFFICIENT, agreement, conflict, neutral, strong_conflict

    if strong_conflict >= 1:
        return CONS_STRONG_CONFLICT, agreement, conflict, neutral, strong_conflict

    if conflict > agreement:
        return CONS_CONFLICT, agreement, conflict, neutral, strong_conflict

    if conflict == 0 and agreement >= 4 and coverage >= COVERAGE_STRONG:
        return CONS_STRONG_SUPPORT, agreement, conflict, neutral, strong_conflict

    if conflict == 0 and agreement >= 2:
        return CONS_SUPPORT, agreement, conflict, neutral, strong_conflict

    return CONS_WEAK_SUPPORT, agreement, conflict, neutral, strong_conflict


def _classify_draw_consensus(
    families: Dict[str, FamilyResult],
    coverage: float,
) -> Tuple[str, int, int, int, int]:
    """
    DRAW handling for v1.0 (restricted channel).
    """

    draw_support = 0
    draw_conflict = 0

    for result in families.values():
        if result.availability == UNAVAILABLE:
            continue
        if result.score is None:
            continue
        if abs(result.score) < NEUTRAL_TOL:
            draw_support += 1
        elif abs(result.score) >= CONFLICT_TOL:
            draw_conflict += 1

    if coverage < COVERAGE_MIN:
        return CONS_INSUFFICIENT, draw_support, draw_conflict, 0, 0

    if draw_conflict >= 2 and draw_conflict > draw_support:
        return CONS_DRAW_CONFLICT_STRONG, draw_support, draw_conflict, 0, 0

    if draw_support >= draw_conflict:
        return CONS_DRAW_SUPPORT, draw_support, draw_conflict, 0, 0

    return CONS_DRAW_WEAK, draw_support, draw_conflict, 0, 0


# ============================================================
# CONFIDENCE
# ============================================================

def _consensus_bonus(consensus: str) -> float:
    return {
        CONS_STRONG_SUPPORT: +0.10,
        CONS_SUPPORT: +0.05,
        CONS_WEAK_SUPPORT: 0.0,
        CONS_CONFLICT: -0.10,
        CONS_STRONG_CONFLICT: -0.15,
        CONS_INSUFFICIENT: -0.15,
        CONS_DRAW_SUPPORT: +0.05,
        CONS_DRAW_CONFLICT_STRONG: -0.10,
        CONS_DRAW_WEAK: 0.0,
    }.get(consensus, 0.0)


def _compute_confidence(
    probability_strength: Optional[float],
    consensus: str,
    family_mean_quality: Optional[float],
    coverage: float,
) -> Optional[float]:
    if probability_strength is None:
        return None

    base = probability_strength
    bonus = _consensus_bonus(consensus)
    q = family_mean_quality if family_mean_quality is not None else 0.5

    raw = (
        base
        + bonus
        + QUALITY_WEIGHT * (q - 0.5)
        + COVERAGE_WEIGHT * (coverage - 0.5)
    )

    return _clamp01(raw)


# ============================================================
# WINNER EVIDENCE ENGINE
# ============================================================

class WinnerEvidenceEngine:
    """
    FAJ Winner Evidence Engine v1.0.

    Pure analytical layer.

    It does NOT modify any upstream data.
    """

    VERSION = WEE_VERSION

    def analyze(
        self,
        probability_result: Any,
        form_win_comparison: Any,
        home_form_model: Any,
        away_form_model: Any,
        home_defence: Any,
        away_defence: Any,
        control_comparison: Any,
        home_anomaly: Any,
        away_anomaly: Any,
        home_special: Any,
        away_special: Any,
        pair_rating: Any,
    ) -> WinnerEvidenceResult:

        # ----------------------------------------------------
        # 1. PROBABILITY (primary)
        # ----------------------------------------------------

        signal_prob = _signal_probability(probability_result)

        primary = signal_prob.direction
        if primary not in (HOME, AWAY, DRAW):
            primary = NEUTRAL

        home_p = _safe_float(_get_value(probability_result, "home_win"))
        draw_p = _safe_float(_get_value(probability_result, "draw"))
        away_p = _safe_float(_get_value(probability_result, "away_win"))

        probs = [p for p in (home_p, draw_p, away_p) if p is not None]
        if len(probs) == 3:
            ordered = sorted(probs, reverse=True)
            probability_margin = ordered[0] - ordered[1]
        else:
            probability_margin = None

        probability_strength = signal_prob.strength

        # ----------------------------------------------------
        # 2. FORM
        # ----------------------------------------------------

        signal_form = _signal_form_win(form_win_comparison)
        family_form = _aggregate_family(
            family=FAM_FORM,
            signals=[signal_form],
            correlated_groups=None,
        )

        # ----------------------------------------------------
        # 3. ATTACK (SHOT_CREATION correlated group)
        # ----------------------------------------------------

        attack_signals = [
            _signal_shot_volume(home_form_model, away_form_model),
            _signal_shot_quality(home_form_model, away_form_model),
            _signal_big_chances(home_form_model, away_form_model),
            _signal_corners(home_form_model, away_form_model),
            _signal_finishing(home_form_model, away_form_model),
        ]

        attack_groups = {
            "SHOT_CREATION": ["SHOT_VOLUME", "SHOT_QUALITY"],
        }

        family_attack = _aggregate_family(
            family=FAM_ATTACK,
            signals=attack_signals,
            correlated_groups=attack_groups,
        )

        # ----------------------------------------------------
        # 4. DEFENCE
        # ----------------------------------------------------

        signal_defence = _signal_defence(home_defence, away_defence)
        family_defence = _aggregate_family(
            family=FAM_DEFENCE,
            signals=[signal_defence],
            correlated_groups=None,
        )

        # ----------------------------------------------------
        # 5. CONTROL
        # ----------------------------------------------------

        signal_control = _signal_control(control_comparison)
        family_control = _aggregate_family(
            family=FAM_CONTROL,
            signals=[signal_control],
            correlated_groups=None,
        )

        # ----------------------------------------------------
        # 6. SPECIAL
        # ----------------------------------------------------

        family_special = _aggregate_special(
            home_anomaly=home_anomaly,
            away_anomaly=away_anomaly,
            home_special=home_special,
            away_special=away_special,
        )

        # ----------------------------------------------------
        # 7. STRUCTURAL
        # ----------------------------------------------------

        signal_structural = _signal_pair_rating(pair_rating)
        family_structural = _aggregate_family(
            family=FAM_STRUCTURAL,
            signals=[signal_structural],
            correlated_groups=None,
        )

        # ----------------------------------------------------
        # 8. Families dict
        # ----------------------------------------------------

        families: Dict[str, FamilyResult] = {
            FAM_PROBABILITY: FamilyResult(
                family=FAM_PROBABILITY,
                direction=signal_prob.direction,
                strength=signal_prob.strength,
                quality=signal_prob.quality,
                availability=signal_prob.availability,
                score=(
                    signal_prob.strength
                    if signal_prob.direction == HOME
                    else -signal_prob.strength
                    if signal_prob.direction == AWAY
                    else 0.0
                ),
                signal_count=1,
                independence_keys=[signal_prob.independence_key],
                conflict=False,
                strong_conflict=False,
                diagnostics={},
            ),
            FAM_FORM: family_form,
            FAM_ATTACK: family_attack,
            FAM_DEFENCE: family_defence,
            FAM_CONTROL: family_control,
            FAM_SPECIAL: family_special,
            FAM_STRUCTURAL: family_structural,
        }

        # ----------------------------------------------------
        # 9. evidence_score
        # ----------------------------------------------------

        contributing_families = [
            FAM_FORM, FAM_ATTACK, FAM_DEFENCE,
            FAM_CONTROL, FAM_SPECIAL, FAM_STRUCTURAL,
        ]

        contributing_scores: List[Optional[float]] = []
        available_families_count = 0

        for name in contributing_families:
            result = families[name]
            if result.availability == UNAVAILABLE:
                continue
            available_families_count += 1
            contributing_scores.append(result.score)

        coverage = available_families_count / TOTAL_FAMILIES

        evidence_score: Optional[float]
        if available_families_count < 2:
            evidence_score = None
        else:
            evidence_score = _mean(contributing_scores)

        if evidence_score is None:
            evidence_preferred_direction: Optional[str] = None
        else:
            if abs(evidence_score) < EVIDENCE_TOL:
                evidence_preferred_direction = NEUTRAL
            else:
                evidence_preferred_direction = (
                    HOME if evidence_score > 0 else AWAY
                )

        # ----------------------------------------------------
        # 10. Consensus
        # ----------------------------------------------------

        consensus, agreement, conflict, neutral, strong_conflict = (
            _classify_consensus(
                primary=primary,
                families={
                    k: v for k, v in families.items()
                    if k != FAM_PROBABILITY
                },
                evidence_score=evidence_score,
                coverage=coverage,
            )
        )

        # ----------------------------------------------------
        # 11. Family mean quality
        # ----------------------------------------------------

        qualities: List[Optional[float]] = []
        for name in contributing_families:
            result = families[name]
            if result.availability == UNAVAILABLE:
                continue
            if result.quality is not None:
                qualities.append(result.quality)

        family_mean_quality = _mean(qualities)

        # ----------------------------------------------------
        # 12. Confidence
        # ----------------------------------------------------

        evidence_confidence = _compute_confidence(
            probability_strength=probability_strength,
            consensus=consensus,
            family_mean_quality=family_mean_quality,
            coverage=coverage,
        )

        # ----------------------------------------------------
        # 13. Signals list (for audit)
        # ----------------------------------------------------

        all_signals: List[EvidenceSignal] = [signal_prob]

        for sig in attack_signals:
            all_signals.append(sig)

        all_signals.extend([
            signal_form,
            signal_defence,
            signal_control,
            signal_structural,
        ])

        # anomaly/special are captured inside family_special diagnostics

        signals_dicts = [s.to_dict() for s in all_signals]

        # ----------------------------------------------------
        # 14. Diagnostics
        # ----------------------------------------------------

        diagnostics = {
            "probability_primary": True,
            "evidence_independent": True,
            "missing_is_not_zero": True,
            "family_caps_applied": False,
            "correlation_protection": True,
            "no_probability_mutation": True,
            "no_xg_mutation": True,
            "no_lambda_mutation": True,
            "no_score_mutation": True,
            "no_post_match_data": True,
            "draw_signal_available": False,
            "draw_signal_note": "reserved_for_A4",
            "neutral_tol": NEUTRAL_TOL,
            "dominance_ratio": DOMINANCE_RATIO,
            "support_tol": SUPPORT_TOL,
            "conflict_tol": CONFLICT_TOL,
            "strong_tol": STRONG_TOL,
            "coverage_min": COVERAGE_MIN,
            "coverage_strong": COVERAGE_STRONG,
            "evidence_tol": EVIDENCE_TOL,
            "quality_weight": QUALITY_WEIGHT,
            "coverage_weight": COVERAGE_WEIGHT,
            "correlated_groups": {
                "SHOT_CREATION": ["SHOT_VOLUME", "SHOT_QUALITY"],
            },
            "special_excluded_from_strong_conflict": True,
            "probability_excluded_from_evidence_score": True,
        }

        # ----------------------------------------------------
        # 15. Return
        # ----------------------------------------------------

        return WinnerEvidenceResult(
            model_version=self.VERSION,

            primary_winner=primary,
            evidence_preferred_direction=evidence_preferred_direction,

            home_probability=home_p,
            draw_probability=draw_p,
            away_probability=away_p,
            probability_margin=probability_margin,
            probability_strength=probability_strength,

            evidence_score=evidence_score,
            evidence_confidence=evidence_confidence,
            family_coverage=coverage,

            consensus=consensus,

            agreement_count=agreement,
            conflict_count=conflict,
            neutral_count=neutral,
            strong_conflict_count=strong_conflict,

            families={k: v.to_dict() for k, v in families.items()},
            signals=signals_dicts,
            diagnostics=diagnostics,
        )


# ============================================================
# CONVENIENCE API
# ============================================================

def analyze_winner_evidence(
    probability_result: Any,
    form_win_comparison: Any,
    home_form_model: Any,
    away_form_model: Any,
    home_defence: Any,
    away_defence: Any,
    control_comparison: Any,
    home_anomaly: Any,
    away_anomaly: Any,
    home_special: Any,
    away_special: Any,
    pair_rating: Any,
) -> Dict[str, Any]:
    """
    Functional convenience wrapper.

    Returns a JSON-safe dict.
    """

    engine = WinnerEvidenceEngine()

    result = engine.analyze(
        probability_result=probability_result,
        form_win_comparison=form_win_comparison,
        home_form_model=home_form_model,
        away_form_model=away_form_model,
        home_defence=home_defence,
        away_defence=away_defence,
        control_comparison=control_comparison,
        home_anomaly=home_anomaly,
        away_anomaly=away_anomaly,
        home_special=home_special,
        away_special=away_special,
        pair_rating=pair_rating,
    )

    return result.to_dict()


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "WEE_VERSION",
    "NEUTRAL_TOL",
    "DOMINANCE_RATIO",
    "SUPPORT_TOL",
    "CONFLICT_TOL",
    "STRONG_TOL",
    "COVERAGE_MIN",
    "COVERAGE_STRONG",
    "EVIDENCE_TOL",
    "EvidenceSignal",
    "FamilyResult",
    "WinnerEvidenceResult",
    "WinnerEvidenceEngine",
    "analyze_winner_evidence",
]
