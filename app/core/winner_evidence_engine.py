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
        home_delta, away_delta,
