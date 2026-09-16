#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM WIN / WINNER STATE v1.3
============================================================

ROLE
----
FormWin is the analytical Winner State.

Pipeline:

    FormContext
        ↓
    FormWin
        ↓
    Winner State
        ↓
    FAJ Brain

The module DOES:
    - analyse directional evidence for HOME / AWAY
    - calculate attack/control/outcome/momentum/venue signals
    - measure evidence agreement
    - detect evidence conflict
    - determine directional winner state
    - calculate winner strength
    - calculate draw pressure
    - expose supporting / contradictory evidence

The module DOES NOT:
    - calculate Poisson probabilities
    - calculate 1X2 probabilities
    - calculate exact scores
    - modify GoalModel lambda
    - modify ProbabilityModel
    - use bookmaker odds
    - access DB
    - access Soccer365
    - use future result
    - train on a single match
    - invent missing values

IMPORTANT
---------
This is evidence/state mathematics.

It is NOT:
    probability calibration
    bookmaker modelling
    result fitting
    arbitrary xG multiplier
    arbitrary lambda multiplier

Missing != 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from math import exp, isfinite, tanh
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# VERSION / CONTRACT
# ============================================================

VERSION = "1.3"
MODEL_NAME = "FormWin"
MODEL_STATUS = "WINNER_STATE_CONTRACT_V1"

MIN_SIGNAL = -1.0
MAX_SIGNAL = 1.0

TEMPORAL_WEIGHTS = (1, 2, 3, 4, 5, 6)

# ------------------------------------------------------------
# Descriptive signal composition.
#
# These are NOT winner probabilities.
# They describe the evidence inside FormWin.
# Winner State combines the resulting evidence structurally.
# ------------------------------------------------------------

ATTACK_WEIGHTS = {
    "sot": 1.0 / 3.0,
    "shots": 0.25,
    "blocked": 1.0 / 12.0,
    "crosses": 1.0 / 12.0,
    "corners": 0.25,
}

CONTROL_WEIGHTS = {
    "possession": 0.60,
    "passes": 0.20,
    "pass_accuracy": 0.20,
}

MOMENTUM_WEIGHTS = {
    "shots_trend": 0.50,
    "sot_trend": 1.0 / 3.0,
    "result_trend": 1.0 / 6.0,
}

# Venue sample shrinkage.
VENUE_SHRINKAGE_K = 4.0

# Signal classes used by Winner State.
DIRECTIONAL_COMPONENTS = (
    "attack",
    "control",
    "outcome",
    "momentum",
    "venue",
)

# Evidence threshold below which a signal is treated as neutral.
NEUTRAL_SIGNAL_THRESHOLD = 0.05

# Minimum number of meaningful directional components before
# calling a directional state strong.
MIN_DIRECTIONAL_COMPONENTS = 2

# Strong directional evidence.
STRONG_STRENGTH_THRESHOLD = 0.60

# Draw pressure thresholds.
DRAW_PRESSURE_HIGH = 0.65
DRAW_PRESSURE_MEDIUM = 0.40


# ============================================================
# GENERIC HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(result):
        return None

    return result


def _clamp(
    value: Optional[float],
    low: float = MIN_SIGNAL,
    high: float = MAX_SIGNAL,
) -> Optional[float]:
    if value is None:
        return None

    return max(low, min(high, value))


def _mean(values: Iterable[Any]) -> Optional[float]:
    clean: List[float] = []

    for value in values:
        number = _safe_float(value)
        if number is not None:
            clean.append(number)

    if not clean:
        return None

    return sum(clean) / len(clean)


def _weighted_mean(
    values: Sequence[Any],
    weights: Sequence[float],
) -> Optional[float]:
    pairs: List[Tuple[float, float]] = []

    for value, weight in zip(values, weights):
        number = _safe_float(value)

        if number is None:
            continue

        if weight <= 0:
            continue

        pairs.append((number, float(weight)))

    if not pairs:
        return None

    numerator = sum(value * weight for value, weight in pairs)
    denominator = sum(weight for _, weight in pairs)

    if denominator <= 0:
        return None

    return numerator / denominator


def _population_std(values: Iterable[Any]) -> Optional[float]:
    clean: List[float] = []

    for value in values:
        number = _safe_float(value)

        if number is not None:
            clean.append(number)

    if not clean:
        return None

    if len(clean) == 1:
        return 0.0

    mean_value = sum(clean) / len(clean)

    variance = sum(
        (value - mean_value) ** 2
        for value in clean
    ) / len(clean)

    return variance ** 0.5


def _ols_slope(values: Sequence[Any]) -> Optional[float]:
    clean = [
        _safe_float(value)
        for value in values
    ]

    if any(value is None for value in clean):
        return None

    if len(clean) < 2:
        return None

    n = len(clean)

    x_mean = (n - 1) / 2.0
    y_mean = sum(clean) / n

    denominator = sum(
        (index - x_mean) ** 2
        for index in range(n)
    )

    if denominator <= 0:
        return None

    numerator = sum(
        (index - x_mean) * (clean[index] - y_mean)
        for index in range(n)
    )

    return numerator / denominator


def _bounded_deviation(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Compare recent weighted state against historical median.

    Output:
        [-1, +1]

    This is descriptive evidence, not probability.
    """

    clean = [
        _safe_float(value)
        for value in values
    ]

    clean = [
        value for value in clean
        if value is not None
    ]

    if not clean:
        return None

    weights = TEMPORAL_WEIGHTS[-len(values):]

    recent = _weighted_mean(values, weights)

    if recent is None:
        return None

    baseline = median(clean)
    deviation = recent - baseline

    std = _population_std(clean)

    if std is None:
        return None

    if std == 0:
        return 0.0 if deviation == 0 else None

    normalized = deviation / std

    return _clamp(tanh(normalized))


def _bounded_slope(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Normalize OLS trend by population standard deviation.
    """

    slope = _ols_slope(values)

    if slope is None:
        return None

    std = _population_std(values)

    if std is None:
        return None

    if std == 0:
        return 0.0

    return _clamp(tanh(slope / std))


def _safe_ratio(
    numerator: Any,
    denominator: Any,
) -> Optional[float]:
    num = _safe_float(numerator)
    den = _safe_float(denominator)

    if num is None or den is None:
        return None

    if den == 0:
        return None

    return num / den


def _combine_optional(
    components: Sequence[Tuple[Optional[float], float]],
) -> Optional[float]:
    """
    Weighted combination with missing-value renormalisation.

    Missing values are NOT treated as zero.
    """

    valid: List[Tuple[float, float]] = []

    for value, weight in components:
        if value is None:
            continue

        if weight <= 0:
            continue

        valid.append((_clamp(value) or 0.0, float(weight)))

    if not valid:
        return None

    numerator = sum(value * weight for value, weight in valid)
    denominator = sum(weight for _, weight in valid)

    if denominator <= 0:
        return None

    return _clamp(numerator / denominator)


def _availability(values: Sequence[Any]) -> float:
    if not values:
        return 0.0

    available = sum(
        1
        for value in values
        if value is not None
    )

    return available / len(values)


def _weighted_result_mean(
    results: Sequence[Any],
) -> Optional[float]:
    """
    W = +1
    D = 0
    L = -1
    """

    mapped: List[Optional[float]] = []

    for result in results:
        if result is None:
            mapped.append(None)
            continue

        value = str(result).strip().upper()

        if value in {"W", "WIN", "В", "ПОБЕДА"}:
            mapped.append(1.0)

        elif value in {"D", "DRAW", "Н", "НИЧЬЯ"}:
            mapped.append(0.0)

        elif value in {"L", "LOSS", "П", "ПОРАЖЕНИЕ"}:
            mapped.append(-1.0)

        else:
            mapped.append(None)

    weights = TEMPORAL_WEIGHTS[-len(mapped):]

    return _weighted_mean(mapped, weights)


def _normalise_result(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip().upper()

    if text in {"W", "WIN", "В", "ПОБЕДА"}:
        return "W"

    if text in {"D", "DRAW", "Н", "НИЧЬЯ"}:
        return "D"

    if text in {"L", "LOSS", "П", "ПОРАЖЕНИЕ"}:
        return "L"

    return None


def _normalise_venue(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip().lower()

    if text in {
        "home",
        "h",
        "дом",
        "дома",
    }:
        return "home"

    if text in {
        "away",
        "a",
        "гости",
        "выезд",
    }:
        return "away"

    return None


# ============================================================
# HISTORY EXTRACTION
# ============================================================

def _extract_history(
    context: Dict[str, Any],
    *keys: str,
) -> List[Any]:
    for key in keys:
        value = context.get(key)

        if value is None:
            continue

        if isinstance(value, (list, tuple)):
            return list(value)

    return []


def _extract_results(
    context: Dict[str, Any],
) -> List[Optional[str]]:
    values = _extract_history(
        context,
        "results_history",
        "result_history",
        "results",
    )

    return [
        _normalise_result(value)
        for value in values
    ]


def _extract_venues(
    context: Dict[str, Any],
) -> List[Optional[str]]:
    values = _extract_history(
        context,
        "venue_history",
        "venues",
        "venue",
    )

    return [
        _normalise_venue(value)
        for value in values
    ]


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class FormWinSignals:
    """
    Raw and derived directional evidence.

    All directional signals are [-1, +1].
    None means insufficient evidence.
    """

    # xG is deliberately diagnostic only.
    xg_signal: Optional[float] = None

    # Attack
    sot_signal: Optional[float] = None
    shots_signal: Optional[float] = None
    blocked_signal: Optional[float] = None
    crosses_signal: Optional[float] = None
    corners_signal: Optional[float] = None
    attack_signal: Optional[float] = None

    # Control
    possession_signal: Optional[float] = None
    passes_signal: Optional[float] = None
    pass_accuracy_signal: Optional[float] = None
    control_signal: Optional[float] = None

    # Results
    outcome_signal: Optional[float] = None

    # Momentum
    shots_trend: Optional[float] = None
    sot_trend: Optional[float] = None
    result_trend: Optional[float] = None
    momentum_signal: Optional[float] = None

    # Venue
    venue_signal: Optional[float] = None

    # xG diagnostics
    xg_trend: Optional[float] = None
    xga_trend: Optional[float] = None


@dataclass
class TeamFormWin:
    """
    Winner State for one team.
    """

    version: str
    team: Optional[str]

    matches_count: int

    # Legacy / compatibility field.
    # It is diagnostic only and MUST NOT be used as the final
    # winner decision by the Brain.
    win_form_score: Optional[float]

    # Core evidence states.
    attack: Optional[float]
    control: Optional[float]
    outcome: Optional[float]
    momentum: Optional[float]
    venue: Optional[float]

    # Winner State.
    direction: str
    strength: Optional[float]
    agreement: Optional[float]
    draw_pressure: Optional[float]

    # Evidence quality.
    stability: Optional[float]
    evidence_quality: Optional[float]

    signals: FormWinSignals = field(
        default_factory=FormWinSignals
    )

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class FormWinComparison:
    """
    Complete HOME vs AWAY Winner State.
    """

    version: str

    home: TeamFormWin
    away: TeamFormWin

    direction: str

    strength: Optional[float]
    agreement: Optional[float]
    draw_pressure: Optional[float]

    conflict_detected: bool

    supporting_components: Tuple[str, ...]
    contradictory_components: Tuple[str, ...]

    evidence_quality: Optional[float]

    # Compatibility fields.
    relative_advantage: Optional[float]
    home_advantage: Optional[float]
    away_advantage: Optional[float]

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# FORM WIN
# ============================================================

class FormWin:
    """
    FAJ Winner State v1.3.

    FormWin no longer ends at a generic win_form_score.

    It constructs an evidence map and determines:

        HOME
        DRAW
        AWAY
        BALANCED

    without generating 1X2 probabilities.
    """

    VERSION = VERSION
    MODEL_NAME = MODEL_NAME
    MODEL_STATUS = MODEL_STATUS

    def __init__(
        self,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.context = context or {}

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def analyze(
        self,
        context: Optional[Dict[str, Any]] = None,
        *,
        team: Optional[str] = None,
        next_venue: Optional[str] = None,
    ) -> TeamFormWin:

        ctx = context if context is not None else self.context

        results = _extract_results(ctx)

        # Prefer canonical FormContext match count.
        context_matches = _safe_float(
            ctx.get("matches_count")
        )

        if context_matches is not None:
            matches_count = int(context_matches)
        else:
            histories = [
                _extract_history(ctx, "results_history"),
                _extract_history(ctx, "team_xg_history"),
                _extract_history(ctx, "opponent_xg_history"),
                _extract_history(ctx, "shots_history"),
                _extract_history(ctx, "shots_on_target_history"),
            ]

            matches_count = max(
                [len(values) for values in histories] + [0]
            )

        # ----------------------------------------------------
        # Histories
        # ----------------------------------------------------

        xg = _extract_history(
            ctx,
            "team_xg_history",
            "recent_xg",
        )

        xga = _extract_history(
            ctx,
            "opponent_xg_history",
            "recent_xga",
        )

        shots = _extract_history(
            ctx,
            "shots_history",
            "recent_shots",
        )

        sot = _extract_history(
            ctx,
            "shots_on_target_history",
            "sot_history",
            "recent_sot",
        )

        blocked = _extract_history(
            ctx,
            "blocked_shots_history",
            "blocked_history",
            "recent_blocked_shots",
        )

        crosses = _extract_history(
            ctx,
            "crosses_history",
            "recent_crosses",
        )

        corners = _extract_history(
            ctx,
            "corners_history",
            "recent_corners",
        )

        possession = _extract_history(
            ctx,
            "possession_history",
            "recent_possession",
        )

        passes = _extract_history(
            ctx,
            "passes_history",
            "recent_passes",
        )

        pass_accuracy = _extract_history(
            ctx,
            "pass_accuracy_history",
            "recent_pass_accuracy",
        )

        venues = _extract_venues(ctx)

        # ----------------------------------------------------
        # Diagnostic xG signals
        # ----------------------------------------------------

        xg_signal = _bounded_deviation(xg)
        xg_trend = _bounded_slope(xg)
        xga_trend = _bounded_slope(xga)

        # ----------------------------------------------------
        # Attack
        # ----------------------------------------------------

        sot_signal = _bounded_deviation(sot)
        shots_signal = _bounded_deviation(shots)
        crosses_signal = _bounded_deviation(crosses)
        corners_signal = _bounded_deviation(corners)

        blocked_base = _bounded_deviation(blocked)

        if blocked_base is None:
            blocked_signal = None
        else:
            # More blocked shots are treated as a weak negative
            # attacking signal. This remains a descriptive prior.
            blocked_signal = _clamp(
                -0.25 * blocked_base
            )

        attack_signal = _combine_optional(
            [
                (
                    sot_signal,
                    ATTACK_WEIGHTS["sot"],
                ),
                (
                    shots_signal,
                    ATTACK_WEIGHTS["shots"],
                ),
                (
                    blocked_signal,
                    ATTACK_WEIGHTS["blocked"],
                ),
                (
                    crosses_signal,
                    ATTACK_WEIGHTS["crosses"],
                ),
                (
                    corners_signal,
                    ATTACK_WEIGHTS["corners"],
                ),
            ]
        )

        # ----------------------------------------------------
        # Control
        # ----------------------------------------------------

        possession_signal = _bounded_deviation(
            possession
        )

        passes_signal = _bounded_deviation(
            passes
        )

        pass_accuracy_signal = _bounded_deviation(
            pass_accuracy
        )

        control_signal = _combine_optional(
            [
                (
                    possession_signal,
                    CONTROL_WEIGHTS["possession"],
                ),
                (
                    passes_signal,
                    CONTROL_WEIGHTS["passes"],
                ),
                (
                    pass_accuracy_signal,
                    CONTROL_WEIGHTS["pass_accuracy"],
                ),
            ]
        )

        # ----------------------------------------------------
        # Outcome
        # ----------------------------------------------------

        outcome_signal = _weighted_result_mean(
            results
        )

        # ----------------------------------------------------
        # Momentum
        # ----------------------------------------------------

        shots_trend = _bounded_slope(shots)
        sot_trend = _bounded_slope(sot)

        result_numeric = [
            1.0 if value == "W"
            else -1.0 if value == "L"
            else 0.0 if value == "D"
            else None
            for value in results
        ]

        result_trend = _bounded_slope(
            result_numeric
        )

        momentum_signal = _combine_optional(
            [
                (
                    shots_trend,
                    MOMENTUM_WEIGHTS["shots_trend"],
                ),
                (
                    sot_trend,
                    MOMENTUM_WEIGHTS["sot_trend"],
                ),
                (
                    result_trend,
                    MOMENTUM_WEIGHTS["result_trend"],
                ),
            ]
        )

        # ----------------------------------------------------
        # Venue
        # ----------------------------------------------------

        venue_signal = self._venue_signal(
            results,
            venues,
            next_venue,
        )

        # ----------------------------------------------------
        # Stability
        # ----------------------------------------------------

        stability = self._calculate_stability(
            xg=xg,
            xga=xga,
            shots=shots,
            sot=sot,
        )

        # ----------------------------------------------------
        # Evidence quality
        # ----------------------------------------------------

        evidence_quality = self._calculate_evidence_quality(
            xg=xg,
            xga=xga,
            shots=shots,
            sot=sot,
            blocked=blocked,
            crosses=crosses,
            corners=corners,
            possession=possession,
            passes=passes,
            pass_accuracy=pass_accuracy,
            results=results,
        )

        # ----------------------------------------------------
        # Legacy diagnostic score.
        #
        # IMPORTANT:
        # This is retained only for compatibility.
        # New Winner State does NOT depend on it.
        # ----------------------------------------------------

        legacy_score = _combine_optional(
            [
                (attack_signal, 0.50),
                (control_signal, 0.10),
                (outcome_signal, 0.15),
                (momentum_signal, 0.15),
                (venue_signal, 0.10),
            ]
        )

        if legacy_score is not None:
            legacy_score = _clamp(
                tanh(legacy_score)
            )

        # ----------------------------------------------------
        # Local team state
        # ----------------------------------------------------

        local_components = {
            "attack": attack_signal,
            "control": control_signal,
            "outcome": outcome_signal,
            "momentum": momentum_signal,
            "venue": venue_signal,
        }

        local_direction = self._local_direction(
            local_components
        )

        local_strength = self._local_strength(
            local_components
        )

        local_agreement = self._local_agreement(
            local_components
        )

        local_draw_pressure = self._local_draw_pressure(
            local_components
        )

        signals = FormWinSignals(
            xg_signal=xg_signal,
            sot_signal=sot_signal,
            shots_signal=shots_signal,
            blocked_signal=blocked_signal,
            crosses_signal=crosses_signal,
            corners_signal=corners_signal,
            attack_signal=attack_signal,
            possession_signal=possession_signal,
            passes_signal=passes_signal,
            pass_accuracy_signal=pass_accuracy_signal,
            control_signal=control_signal,
            outcome_signal=outcome_signal,
            shots_trend=shots_trend,
            sot_trend=sot_trend,
            result_trend=result_trend,
            momentum_signal=momentum_signal,
            venue_signal=venue_signal,
            xg_trend=xg_trend,
            xga_trend=xga_trend,
        )

        diagnostics = {
            "version": VERSION,
            "model": MODEL_NAME,
            "model_status": MODEL_STATUS,

            "probability_generated": False,
            "score_generated": False,
            "poisson_used": False,

            "xg_used_in_attack": False,
            "xg_used_in_momentum": False,
            "xg_used_as_winner_multiplier": False,

            "legacy_win_form_score_diagnostic_only": True,

            "winner_state": True,
            "winner_direction": local_direction,
            "winner_strength": local_strength,
            "winner_agreement": local_agreement,
            "draw_pressure": local_draw_pressure,

            "next_venue": next_venue,
            "matches_count_source": (
                "form_context"
                if context_matches is not None
                else "history_fallback"
            ),
        }

        return TeamFormWin(
            version=VERSION,
            team=team or ctx.get("team"),
            matches_count=matches_count,

            win_form_score=legacy_score,

            attack=attack_signal,
            control=control_signal,
            outcome=outcome_signal,
            momentum=momentum_signal,
            venue=venue_signal,

            direction=local_direction,
            strength=local_strength,
            agreement=local_agreement,
            draw_pressure=local_draw_pressure,

            stability=stability,
            evidence_quality=evidence_quality,

            signals=signals,
            diagnostics=diagnostics,
        )

    # --------------------------------------------------------
    # HOME vs AWAY
    # --------------------------------------------------------

    def compare(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ) -> FormWinComparison:

        home = self.analyze(
            home_context,
            team=home_context.get("team"),
            next_venue="home",
        )

        away = self.analyze(
            away_context,
            team=away_context.get("team"),
            next_venue="away",
        )

        home_components = {
            "attack": home.attack,
            "control": home.control,
            "outcome": home.outcome,
            "momentum": home.momentum,
            "venue": home.venue,
        }

        away_components = {
            "attack": away.attack,
            "control": away.control,
            "outcome": away.outcome,
            "momentum": away.momentum,
            "venue": away.venue,
        }

        directional_differences: Dict[
            str,
            Optional[float]
        ] = {}

        for name in DIRECTIONAL_COMPONENTS:
            h = home_components.get(name)
            a = away_components.get(name)

            if h is None and a is None:
                directional_differences[name] = None
                continue

            if h is None:
                directional_differences[name] = _clamp(-a)
                continue

            if a is None:
                directional_differences[name] = _clamp(h)
                continue

            directional_differences[name] = _clamp(
                h - a
            )

        # ----------------------------------------------------
        # Evidence map
        #
        # Positive -> HOME
        # Negative -> AWAY
        # Near zero -> neutral
        # ----------------------------------------------------

        meaningful: Dict[str, float] = {}

        for name, value in directional_differences.items():
            if value is None:
                continue

            if abs(value) < NEUTRAL_SIGNAL_THRESHOLD:
                continue

            meaningful[name] = value

        home_support = [
            name
            for name, value in meaningful.items()
            if value > 0
        ]

        away_support = [
            name
            for name, value in meaningful.items()
            if value < 0
        ]

        # ----------------------------------------------------
        # Agreement
        # ----------------------------------------------------

        agreement = self._comparison_agreement(
            meaningful
        )

        # ----------------------------------------------------
        # Conflict
        # ----------------------------------------------------

        conflict_detected = (
            bool(home_support)
            and bool(away_support)
        )

        # ----------------------------------------------------
        # Direction
        # ----------------------------------------------------

        direction = self._comparison_direction(
            meaningful=meaningful,
            agreement=agreement,
        )

        # ----------------------------------------------------
        # Strength
        # ----------------------------------------------------

        strength = self._comparison_strength(
            meaningful=meaningful,
            agreement=agreement,
            direction=direction,
        )

        # ----------------------------------------------------
        # Draw pressure
        # ----------------------------------------------------

        draw_pressure = self._comparison_draw_pressure(
            meaningful=meaningful,
            agreement=agreement,
            home=home,
            away=away,
        )

        # ----------------------------------------------------
        # Compatibility advantage.
        #
        # Still useful as an evidence diagnostic.
        # It is NOT a probability and NOT the final winner
        # decision.
        # ----------------------------------------------------

        relative_advantage = self._legacy_relative_advantage(
            home,
            away,
        )

        home_advantage = (
            max(relative_advantage, 0.0)
            if relative_advantage is not None
            else None
        )

        away_advantage = (
            max(-relative_advantage, 0.0)
            if relative_advantage is not None
            else None
        )

        evidence_quality = _mean(
            [
                home.evidence_quality,
                away.evidence_quality,
            ]
        )

        diagnostics = {
            "version": VERSION,
            "model": MODEL_NAME,
            "model_status": MODEL_STATUS,

            "winner_state": True,

            "direction": direction,
            "strength": strength,
            "agreement": agreement,
            "draw_pressure": draw_pressure,

            "conflict_detected": conflict_detected,

            "home_supporting_components": tuple(
                home_support
            ),

            "away_supporting_components": tuple(
                away_support
            ),

            "component_differences": directional_differences,

            "probability_generated": False,
            "score_generated": False,
            "poisson_used": False,

            "secondary_signals_do_not_modify_lambda": True,
            "secondary_signals_do_not_modify_probability": True,
        }

        return FormWinComparison(
            version=VERSION,

            home=home,
            away=away,

            direction=direction,

            strength=strength,
            agreement=agreement,
            draw_pressure=draw_pressure,

            conflict_detected=conflict_detected,

            supporting_components=tuple(
                home_support
            ),
            contradictory_components=tuple(
                away_support
            ),

            evidence_quality=evidence_quality,

            relative_advantage=relative_advantage,
            home_advantage=home_advantage,
            away_advantage=away_advantage,

            diagnostics=diagnostics,
        )

    # ========================================================
    # WINNER STATE — INTERNAL MATHEMATICS
    # ========================================================

    @staticmethod
    def _local_direction(
        components: Dict[str, Optional[float]],
    ) -> str:

        values = [
            value
            for value in components.values()
            if value is not None
        ]

        if not values:
            return "BALANCED"

        positive = sum(
            1
            for value in values
            if value > NEUTRAL_SIGNAL_THRESHOLD
        )

        negative = sum(
            1
            for value in values
            if value < -NEUTRAL_SIGNAL_THRESHOLD
        )

        if positive > negative:
            return "HOME"

        if negative > positive:
            return "AWAY"

        return "BALANCED"

    @staticmethod
    def _local_strength(
        components: Dict[str, Optional[float]],
    ) -> Optional[float]:

        values = [
            abs(value)
            for value in components.values()
            if value is not None
        ]

        if not values:
            return None

        return _clamp(
            sum(values) / len(values),
            0.0,
            1.0,
        )

    @staticmethod
    def _local_agreement(
        components: Dict[str, Optional[float]],
    ) -> Optional[float]:

        values = [
            value
            for value in components.values()
            if value is not None
            and abs(value) >= NEUTRAL_SIGNAL_THRESHOLD
        ]

        if not values:
            return None

        positive = sum(
            1 for value in values if value > 0
        )

        negative = sum(
            1 for value in values if value < 0
        )

        total = len(values)

        dominant = max(
            positive,
            negative,
        )

        return _clamp(
            dominant / total,
            0.0,
            1.0,
        )

    @staticmethod
    def _local_draw_pressure(
        components: Dict[str, Optional[float]],
    ) -> Optional[float]:

        values = [
            abs(value)
            for value in components.values()
            if value is not None
        ]

        if not values:
            return None

        # Low directional magnitude = balanced state.
        mean_abs = sum(values) / len(values)

        pressure = 1.0 - mean_abs

        return _clamp(
            pressure,
            0.0,
            1.0,
        )

    @staticmethod
    def _comparison_direction(
        meaningful: Dict[str, float],
        agreement: Optional[float],
    ) -> str:

        if not meaningful:
            return "DRAW"

        positive = sum(
            1
            for value in meaningful.values()
            if value > 0
        )

        negative = sum(
            1
            for value in meaningful.values()
            if value < 0
        )

        if positive == negative:
            return "DRAW"

        if positive > negative:
            return "HOME"

        return "AWAY"

    @staticmethod
    def _comparison_strength(
        meaningful: Dict[str, float],
        agreement: Optional[float],
        direction: str,
    ) -> Optional[float]:

        if not meaningful:
            return None

        magnitudes = [
            abs(value)
            for value in meaningful.values()
        ]

        magnitude = sum(magnitudes) / len(magnitudes)

        agreement_value = (
            agreement
            if agreement is not None
            else 0.0
        )

        # Strength is evidence magnitude moderated by
        # agreement. It is NOT a probability.
        strength = (
            0.60 * magnitude
            + 0.40 * agreement_value
        )

        if direction == "DRAW":
            # Draw is not a team win signal.
            # Keep the state descriptive.
            strength *= 0.75

        return _clamp(
            strength,
            0.0,
            1.0,
        )

    @staticmethod
    def _comparison_agreement(
        meaningful: Dict[str, float],
    ) -> Optional[float]:

        if not meaningful:
            return None

        positive = sum(
            1
            for value in meaningful.values()
            if value > 0
        )

        negative = sum(
            1
            for value in meaningful.values()
            if value < 0
        )

        total = positive + negative

        if total == 0:
            return None

        return _clamp(
            max(positive, negative) / total,
            0.0,
            1.0,
        )

    @staticmethod
    def _comparison_draw_pressure(
        meaningful: Dict[str, float],
        agreement: Optional[float],
        home: TeamFormWin,
        away: TeamFormWin,
    ) -> Optional[float]:

        if not meaningful:
            return 1.0

        mean_abs = sum(
            abs(value)
            for value in meaningful.values()
        ) / len(meaningful)

        balance_pressure = 1.0 - mean_abs

        agreement_pressure = (
            1.0 - agreement
            if agreement is not None
            else 0.5
        )

        # Team-local draw pressures are additional evidence,
        # not probability.
        local_draw_values = [
            value
            for value in (
                home.draw_pressure,
                away.draw_pressure,
            )
            if value is not None
        ]

        local_pressure = (
            sum(local_draw_values)
            / len(local_draw_values)
            if local_draw_values
            else 0.5
        )

        pressure = (
            0.50 * balance_pressure
            + 0.30 * agreement_pressure
            + 0.20 * local_pressure
        )

        return _clamp(
            pressure,
            0.0,
            1.0,
        )

    @staticmethod
    def _legacy_relative_advantage(
        home: TeamFormWin,
        away: TeamFormWin,
    ) -> Optional[float]:

        if (
            home.win_form_score is None
            and away.win_form_score is None
        ):
            return None

        home_score = (
            home.win_form_score
            if home.win_form_score is not None
            else 0.0
        )

        away_score = (
            away.win_form_score
            if away.win_form_score is not None
            else 0.0
        )

        return _clamp(
            home_score - away_score
        )

    # ========================================================
    # VENUE
    # ========================================================

    @staticmethod
    def _venue_signal(
        results: Sequence[Optional[str]],
        venues: Sequence[Optional[str]],
        next_venue: Optional[str],
    ) -> Optional[float]:

        if next_venue not in {"home", "away"}:
            return None

        if not results or not venues:
            return None

        general = _weighted_result_mean(
            results
        )

        venue_results: List[Optional[float]] = []

        for result, venue in zip(results, venues):
            if venue != next_venue:
                continue

            if result == "W":
                venue_results.append(1.0)

            elif result == "D":
                venue_results.append(0.0)

            elif result == "L":
                venue_results.append(-1.0)

        if not venue_results:
            return general

        venue_mean = _mean(
            venue_results
        )

        if venue_mean is None:
            return general

        n = len(venue_results)

        alpha = (
            n / (n + VENUE_SHRINKAGE_K)
        )

        if general is None:
            return _clamp(venue_mean)

        return _clamp(
            alpha * venue_mean
            + (1.0 - alpha) * general
        )

    # ========================================================
    # STABILITY / QUALITY
    # ========================================================

    @staticmethod
    def _series_stability(
        values: Sequence[Any],
    ) -> Optional[float]:

        clean = [
            _safe_float(value)
            for value in values
        ]

        clean = [
            value for value in clean
            if value is not None
        ]

        if not clean:
            return None

        mean_value = sum(clean) / len(clean)

        if mean_value == 0:
            std = _population_std(clean)

            if std is None:
                return None

            return 1.0 if std == 0 else 0.0

        std = _population_std(clean)

        if std is None:
            return None

        cv = abs(std / mean_value)

        return _clamp(
            1.0 / (1.0 + cv),
            0.0,
            1.0,
        )

    def _calculate_stability(
        self,
        *,
        xg: Sequence[Any],
        xga: Sequence[Any],
        shots: Sequence[Any],
        sot: Sequence[Any],
    ) -> Optional[float]:

        values = [
            self._series_stability(xg),
            self._series_stability(xga),
            self._series_stability(shots),
            self._series_stability(sot),
        ]

        values = [
            value for value in values
            if value is not None
        ]

        if not values:
            return None

        return _clamp(
            sum(values) / len(values),
            0.0,
            1.0,
        )

    @staticmethod
    def _calculate_evidence_quality(
        *,
        xg: Sequence[Any],
        xga: Sequence[Any],
        shots: Sequence[Any],
        sot: Sequence[Any],
        blocked: Sequence[Any],
        crosses: Sequence[Any],
        corners: Sequence[Any],
        possession: Sequence[Any],
        passes: Sequence[Any],
        pass_accuracy: Sequence[Any],
        results: Sequence[Any],
    ) -> Optional[float]:

        histories = [
            xg,
            xga,
            shots,
            sot,
            blocked,
            crosses,
            corners,
            possession,
            passes,
            pass_accuracy,
            results,
        ]

        available = [
            _availability(history)
            for history in histories
            if history
        ]

        if not available:
            return None

        return _clamp(
            sum(available) / len(available),
            0.0,
            1.0,
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        result: TeamFormWin | FormWinComparison,
    ) -> Dict[str, Any]:

        return asdict(result)


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def analyze_form_win(
    context: Dict[str, Any],
    *,
    team: Optional[str] = None,
    next_venue: Optional[str] = None,
) -> TeamFormWin:

    return FormWin(context).analyze(
        context,
        team=team,
        next_venue=next_venue,
    )


def compare_form_win(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> FormWinComparison:

    return FormWin().compare(
        home_context,
        away_context,
    )


__all__ = [
    "VERSION",
    "MODEL_NAME",
    "MODEL_STATUS",
    "FormWin",
    "FormWinSignals",
    "TeamFormWin",
    "FormWinComparison",
    "analyze_form_win",
    "compare_form_win",
]
