#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
SPECIAL FORM v2.0
============================================================

ROLE
----
Independent research/evidence organ.

Architecture:

    FormContext
        ↓
    FormSpecial
        ├── Gladiator
        ├── Fortress
        ├── Leicester
        ├── God Kiss
        ├── Dark Horse
        ├── Lukaku
        ├── Kepa
        └── Haaland
        ↓
    SpecialFormResult
        ↓
    FAJBrain / future synthesis

IMPORTANT
---------
SpecialForm is an evidence organ.

It DOES NOT:
- calculate Poisson;
- calculate probabilities;
- calculate score distribution;
- modify GoalModel;
- modify xG;
- modify λ;
- modify FormWin;
- modify Defence;
- modify Control;
- modify ProbabilityModel;
- modify ScorePredictor;
- apply Winner Signal Override;
- calculate confidence of the final prediction;
- calculate risk;
- write to database;
- learn parameters;
- use future results.

A detected effect is evidence.
An evidence signal is NOT a multiplier.

Missing != 0
------------
Missing observations remain None.

History
-------
FormContext is expected to provide:

    M1 -> M2 -> ... -> M6

oldest -> newest.

This module NEVER reverses history.

MATHEMATICAL CONTRACT
---------------------
FACTS -> STATE/EVIDENCE

Each effect produces:
    signal ∈ [-1, +1] when measurable
    signal = None when evidence is insufficient

The sign is effect-specific and documented below.

No arbitrary predictive weighting is used to create a
match prediction.

Research thresholds are explicitly isolated and must not
be treated as calibrated coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ============================================================
# VERSION
# ============================================================

SPECIAL_FORM_VERSION = "2.0"
VERSION = SPECIAL_FORM_VERSION

FORMULA_STATUS = "DIAGNOSTIC_RESEARCH_EVIDENCE"

CONTRACT = "MATHEMATICAL_CONTRACT_V1"


# ============================================================
# CONTRACT CONSTANTS
# ============================================================

MAX_HISTORY = 6
MIN_HISTORY = 3

SIGNAL_MIN = -1.0
SIGNAL_MAX = 1.0

EPSILON = 1e-9


# ============================================================
# RESEARCH HYPOTHESES
# ============================================================
#
# These are detection thresholds, not prediction coefficients.
#
# They describe research hypotheses already present in the
# Special Form concept.
#
# They must NOT be converted into xG/probability multipliers.
# ============================================================

GLADIATOR_MIN_WINS = 4

FORTRESS_MIN_UNBEATEN = 4

LEICESTER_MIN_WINS = 3
LEICESTER_MIN_MATCHES = 3
LEICESTER_WINDOW = 5

GOD_KISS_MIN_AWAY_STREAK = 3

DARK_HORSE_THRESHOLD = 1.20

LUKAKU_THRESHOLD = 0.80

KEPA_THRESHOLD = 1.30

# Haaland is intentionally retained as a research signal.
# The old arbitrary component weights are removed.
HAALAND_DETECTION_THRESHOLD = 0.50


# ============================================================
# EFFECT SIGNAL
# ============================================================

@dataclass(frozen=True)
class EffectSignal:
    """
    One Special Form evidence signal.

    signal:
        Signed evidence in [-1, +1].

        Positive:
            effect supports stronger attacking/result state.

        Negative:
            effect indicates adverse attacking/defensive condition.

        None:
            insufficient evidence.

    detected:
        Whether the explicit research detection condition
        has been met.

    strength:
        Absolute magnitude of signal.

    evidence_quality:
        Coverage/reliability of the underlying observations.

    adjustment:
        Kept for compatibility with old consumers.

        ALWAYS None in v2.0.

        SpecialForm never applies an adjustment.
    """

    name: str
    detected: bool
    direction: str

    signal: Optional[float]
    strength: Optional[float]

    evidence_quality: Optional[float]

    evidence: Dict[str, Any]

    adjustment: Optional[float] = None

    @property
    def confidence(self) -> Optional[float]:
        """
        Compatibility alias.

        In v2.0 this means evidence quality only.

        It is NOT final prediction confidence.
        """
        return self.evidence_quality


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class SpecialFormResult:
    """
    Complete Special Form evidence state for one team.
    """

    team: str

    signals: Dict[str, EffectSignal]

    composite_signal: Optional[float]

    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# BASIC HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> Optional[float]:

    if value is None or isinstance(value, bool):
        return None

    try:
        number = float(
            str(value).strip().replace(",", ".")
        )
    except (TypeError, ValueError):
        return None

    if not isfinite(number):
        return None

    return number


def _clean_numeric(
    values: Sequence[Any],
) -> List[float]:

    result: List[float] = []

    for value in values:
        number = _safe_float(value)

        if number is not None:
            result.append(number)

    return result


def _mean(
    values: Sequence[Any],
) -> Optional[float]:

    numbers = _clean_numeric(values)

    if not numbers:
        return None

    return sum(numbers) / len(numbers)


def _median(
    values: Sequence[Any],
) -> Optional[float]:

    numbers = _clean_numeric(values)

    if not numbers:
        return None

    return median(numbers)


def _clamp(
    value: float,
    low: float = SIGNAL_MIN,
    high: float = SIGNAL_MAX,
) -> float:

    return max(
        low,
        min(high, float(value)),
    )


def _sign(
    value: Optional[float],
) -> Optional[int]:

    if value is None:
        return None

    if value > EPSILON:
        return 1

    if value < -EPSILON:
        return -1

    return 0


# ============================================================
# HISTORY
# ============================================================

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
    FormContext already supplies canonical M1 -> M6.

    Never reverse.

    Never select the last six from a longer canonical sequence.
    The module consumes the first six positions.
    """

    return _as_sequence(values)[:MAX_HISTORY]


# ============================================================
# CONTEXT EXTRACTION
# ============================================================

def _extract_field(
    context: Any,
    *names: str,
) -> Any:

    if context is None:
        return None

    for name in names:

        if isinstance(context, dict):
            if name in context:
                return context[name]

        try:
            keys = context.keys()

            if name in keys:
                return context[name]

        except (AttributeError, TypeError):
            pass

        try:
            return getattr(context, name)
        except AttributeError:
            pass

    return None


def _get_history(
    context: Any,
    *names: str,
) -> Tuple[Any, ...]:

    value = _extract_field(
        context,
        *names,
    )

    return _history(value)


def _align_histories(
    context: Any,
) -> Dict[str, Tuple[Any, ...]]:
    """
    Extract SpecialForm inputs.

    All histories remain M1 -> M6.
    """

    return {
        "results": _get_history(
            context,
            "results_history",
            "results",
            "result_history",
        ),

        "venue": _get_history(
            context,
            "venue_history",
        ),

        "goals_for": _get_history(
            context,
            "goals_for_history",
        ),

        "goals_against": _get_history(
            context,
            "goals_against_history",
        ),

        "xg": _get_history(
            context,
            "team_xg_history",
            "recent_xg",
            "xg_history",
        ),

        "xga": _get_history(
            context,
            "opponent_xg_history",
            "recent_xga",
            "xga_history",
        ),

        "shots": _get_history(
            context,
            "shots_history",
            "recent_shots",
        ),

        "shots_on_target": _get_history(
            context,
            "shots_on_target_history",
            "sot_history",
            "recent_shots_on_target",
        ),

        "big_chances": _get_history(
            context,
            "big_chances_history",
            "recent_big_chances",
        ),
    }


# ============================================================
# NORMALIZATION
# ============================================================

def _normalise_result(
    result: Any,
) -> Optional[str]:

    if result is None:
        return None

    value = str(result).strip().upper()

    mapping = {
        "W": "W",
        "WIN": "W",
        "В": "W",
        "ПОБЕДА": "W",

        "D": "D",
        "DRAW": "D",
        "Н": "D",
        "НИЧЬЯ": "D",

        "L": "L",
        "LOSS": "L",
        "LOSE": "L",
        "П": "L",
        "ПОРАЖЕНИЕ": "L",
    }

    return mapping.get(value)


def _normalise_venue(
    venue: Any,
) -> Optional[str]:

    if venue is None:
        return None

    value = str(venue).strip().lower()

    if value in {
        "home",
        "h",
        "дом",
        "дома",
    }:
        return "home"

    if value in {
        "away",
        "a",
        "гости",
        "в гостях",
        "выезд",
    }:
        return "away"

    return None


# ============================================================
# QUALITY
# ============================================================

def _quality(
    values: Sequence[Any],
) -> Optional[float]:
    """
    Valid-observation coverage.

    This is NOT prediction confidence.
    """

    values = tuple(values)[:MAX_HISTORY]

    if not values:
        return None

    valid = sum(
        _safe_float(value) is not None
        for value in values
    )

    return valid / len(values)


def _result_quality(
    values: Sequence[Any],
) -> Optional[float]:

    values = tuple(values)[:MAX_HISTORY]

    if not values:
        return None

    valid = sum(
        _normalise_result(value) is not None
        for value in values
    )

    return valid / len(values)


def _average_quality(
    qualities: Sequence[Optional[float]],
) -> Optional[float]:

    values = [
        value
        for value in qualities
        if value is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def _confidence_from_count(
    count: int,
    target: int = MAX_HISTORY,
) -> Optional[float]:

    if count <= 0:
        return None

    return _clamp(
        count / float(target),
        0.0,
        1.0,
    )


# ============================================================
# PAIRING
# ============================================================

def _paired_values(
    first: Sequence[Any],
    second: Sequence[Any],
) -> Tuple[List[float], List[float]]:
    """
    Pair observations by chronological position.

    Missing pair members are skipped.

    No missing value becomes zero.
    """

    first_result: List[float] = []
    second_result: List[float] = []

    for value_a, value_b in zip(
        first,
        second,
    ):

        number_a = _safe_float(value_a)
        number_b = _safe_float(value_b)

        if number_a is None or number_b is None:
            continue

        first_result.append(number_a)
        second_result.append(number_b)

    return (
        first_result,
        second_result,
    )


# ============================================================
# GENERIC EFFECT
# ============================================================

def _effect(
    name: str,
    signal: Optional[float],
    detected: bool,
    evidence_quality: Optional[float],
    evidence: Dict[str, Any],
) -> EffectSignal:

    if signal is None:
        return EffectSignal(
            name=name,
            detected=False,
            direction="unknown",
            signal=None,
            strength=None,
            evidence_quality=evidence_quality,
            evidence=evidence,
            adjustment=None,
        )

    signal = _clamp(signal)

    if signal > EPSILON:
        direction = "positive"

    elif signal < -EPSILON:
        direction = "negative"

    else:
        direction = "neutral"

    return EffectSignal(
        name=name,
        detected=detected,
        direction=direction,
        signal=signal,
        strength=abs(signal),
        evidence_quality=evidence_quality,
        evidence=evidence,
        adjustment=None,
    )


def _undetected_effect(
    name: str,
    evidence: Dict[str, Any],
    evidence_quality: Optional[float] = None,
) -> EffectSignal:
    """
    Explicitly measurable but detection condition not met.

    signal=0 means:
        the defined hypothesis is not currently detected.

    This is different from:
        signal=None

    None = insufficient evidence.
    0 = sufficient evidence but no directional effect.
    """

    return EffectSignal(
        name=name,
        detected=False,
        direction="neutral",
        signal=0.0,
        strength=0.0,
        evidence_quality=evidence_quality,
        evidence=evidence,
        adjustment=None,
    )


# ============================================================
# GLADIATOR
# ============================================================

def detect_gladiator(
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Gladiator hypothesis:

        4+ consecutive wins.

    Signal:
        streak / 6

    Direction:
        positive.

    This does not predict the next match.
    """

    results = [
        _normalise_result(value)
        for value in tuple(results_history)[:MAX_HISTORY]
    ]

    valid_count = sum(
        value is not None
        for value in results
    )

    streak = 0

    for result in reversed(results):

        if result == "W":
            streak += 1
        else:
            break

    quality = _confidence_from_count(
        valid_count
    )

    evidence = {
        "win_streak": streak,
        "valid_results": valid_count,
        "threshold": GLADIATOR_MIN_WINS,
    }

    if valid_count < MIN_HISTORY:
        return _effect(
            "gladiator",
            None,
            False,
            quality,
            evidence,
        )

    signal = _clamp(
        streak / float(MAX_HISTORY),
        0.0,
        1.0,
    )

    return _effect(
        "gladiator",
        signal,
        streak >= GLADIATOR_MIN_WINS,
        quality,
        evidence,
    )


# ============================================================
# FORTRESS
# ============================================================

def detect_fortress(
    venue_history: Sequence[Any],
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Fortress hypothesis:

        4+ consecutive home matches without defeat.

    Away matches are not treated as home observations.
    """

    venues = tuple(venue_history)[:MAX_HISTORY]
    results = tuple(results_history)[:MAX_HISTORY]

    home_results: List[str] = []

    for venue, result in zip(
        venues,
        results,
    ):

        normalised_venue = _normalise_venue(venue)
        normalised_result = _normalise_result(result)

        if (
            normalised_venue == "home"
            and normalised_result is not None
        ):
            home_results.append(
                normalised_result
            )

    streak = 0

    for result in reversed(home_results):

        if result in {"W", "D"}:
            streak += 1
        else:
            break

    quality = _confidence_from_count(
        len(home_results)
    )

    evidence = {
        "home_matches": len(home_results),
        "home_unbeaten_streak": streak,
        "threshold": FORTRESS_MIN_UNBEATEN,
    }

    if len(home_results) < MIN_HISTORY:
        return _effect(
            "fortress",
            None,
            False,
            quality,
            evidence,
        )

    signal = _clamp(
        streak / float(MAX_HISTORY),
        0.0,
        1.0,
    )

    return _effect(
        "fortress",
        signal,
        streak >= FORTRESS_MIN_UNBEATEN,
        quality,
        evidence,
    )


# ============================================================
# LEICESTER
# ============================================================

def detect_leicester(
    venue_history: Sequence[Any],
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Leicester hypothesis:

        3+ away wins in at least 3 away matches.

    Latest available five away observations are examined.
    """

    venues = tuple(venue_history)[:MAX_HISTORY]
    results = tuple(results_history)[:MAX_HISTORY]

    away_results: List[str] = []

    for venue, result in zip(
        venues,
        results,
    ):

        normalised_venue = _normalise_venue(venue)
        normalised_result = _normalise_result(result)

        if (
            normalised_venue == "away"
            and normalised_result is not None
        ):
            away_results.append(
                normalised_result
            )

    away_window = away_results[-LEICESTER_WINDOW:]

    wins = sum(
        result == "W"
        for result in away_window
    )

    matches = len(away_window)

    quality = _confidence_from_count(
        matches,
        target=LEICESTER_WINDOW,
    )

    evidence = {
        "away_matches": matches,
        "away_wins": wins,
        "window": LEICESTER_WINDOW,
        "min_matches": LEICESTER_MIN_MATCHES,
        "min_wins": LEICESTER_MIN_WINS,
    }

    if matches < LEICESTER_MIN_MATCHES:
        return _effect(
            "leicester",
            None,
            False,
            quality,
            evidence,
        )

    signal = _clamp(
        wins / float(
            max(
                matches,
                1,
            )
        ),
        0.0,
        1.0,
    )

    return _effect(
        "leicester",
        signal,
        wins >= LEICESTER_MIN_WINS,
        quality,
        evidence,
    )


# ============================================================
# GOD KISS
# ============================================================

def detect_god_kiss(
    venue_history: Sequence[Any],
) -> EffectSignal:
    """
    God Kiss hypothesis:

        3+ consecutive away matches at the end of history.

    Interpretation:
        contextual schedule pattern.

    It does NOT imply a future home win.
    """

    venues = [
        _normalise_venue(value)
        for value in tuple(venue_history)[:MAX_HISTORY]
    ]

    valid_count = sum(
        value is not None
        for value in venues
    )

    away_streak = 0

    for venue in reversed(venues):

        if venue == "away":
            away_streak += 1
        else:
            break

    quality = _confidence_from_count(
        valid_count
    )

    evidence = {
        "away_streak": away_streak,
        "valid_venue_observations": valid_count,
        "threshold": GOD_KISS_MIN_AWAY_STREAK,
    }

    if valid_count < MIN_HISTORY:
        return _effect(
            "god_kiss",
            None,
            False,
            quality,
            evidence,
        )

    signal = _clamp(
        away_streak / float(MAX_HISTORY),
        0.0,
        1.0,
    )

    return _effect(
        "god_kiss",
        signal,
        away_streak >= GOD_KISS_MIN_AWAY_STREAK,
        quality,
        evidence,
    )


# ============================================================
# DARK HORSE
# ============================================================

def detect_dark_horse(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
) -> EffectSignal:
    """
    Dark Horse hypothesis:

        goals / xG > 1.20

    This is a finishing-overperformance observation.

    It does NOT create a permanent finishing bonus.
    """

    goals, xg = _paired_values(
        goals_for,
        xg_history,
    )

    quality = _confidence_from_count(
        len(goals)
    )

    evidence: Dict[str, Any] = {
        "paired_observations": len(goals),
        "threshold": DARK_HORSE_THRESHOLD,
    }

    if len(goals) < MIN_HISTORY:
        return _effect(
            "dark_horse",
            None,
            False,
            quality,
            evidence,
        )

    goals_avg = _mean(goals)
    xg_avg = _mean(xg)

    if (
        goals_avg is None
        or xg_avg is None
        or xg_avg <= EPSILON
    ):
        evidence.update({
            "goals_avg": goals_avg,
            "xg_avg": xg_avg,
        })

        return _effect(
            "dark_horse",
            None,
            False,
            quality,
            evidence,
        )

    ratio = goals_avg / xg_avg

    evidence.update({
        "goals_avg": goals_avg,
        "xg_avg": xg_avg,
        "finishing_ratio": ratio,
    })

    # Map ratio to a bounded research signal.
    # 1.20 is the detection threshold.
    # No xG adjustment is produced.
    signal = _clamp(
        (ratio - 1.0) / 1.0,
        -1.0,
        1.0,
    )

    return _effect(
        "dark_horse",
        signal,
        ratio >= DARK_HORSE_THRESHOLD,
        quality,
        evidence,
    )


# ============================================================
# LUKAKU
# ============================================================

def detect_lukaku(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
) -> EffectSignal:
    """
    Lukaku hypothesis:

        goals / xG < 0.80

    This is finishing-underperformance evidence.
    """

    goals, xg = _paired_values(
        goals_for,
        xg_history,
    )

    quality = _confidence_from_count(
        len(goals)
    )

    evidence: Dict[str, Any] = {
        "paired_observations": len(goals),
        "threshold": LUKAKU_THRESHOLD,
    }

    if len(goals) < MIN_HISTORY:
        return _effect(
            "lukaku",
            None,
            False,
            quality,
            evidence,
        )

    goals_avg = _mean(goals)
    xg_avg = _mean(xg)

    if (
        goals_avg is None
        or xg_avg is None
        or xg_avg <= EPSILON
    ):
        evidence.update({
            "goals_avg": goals_avg,
            "xg_avg": xg_avg,
        })

        return _effect(
            "lukaku",
            None,
            False,
            quality,
            evidence,
        )

    ratio = goals_avg / xg_avg

    evidence.update({
        "goals_avg": goals_avg,
        "xg_avg": xg_avg,
        "finishing_ratio": ratio,
    })

    signal = _clamp(
        (ratio - 1.0) / 1.0,
        -1.0,
        1.0,
    )

    return _effect(
        "lukaku",
        signal,
        ratio <= LUKAKU_THRESHOLD,
        quality,
        evidence,
    )


# ============================================================
# KEPA
# ============================================================

def detect_kepa(
    goals_against: Sequence[Any],
    xga_history: Sequence[Any],
) -> EffectSignal:
    """
    Kepa hypothesis:

        goals_against / xGA > 1.30

    Positive ratio means worse defensive outcome.

    Therefore the SpecialForm signal is negative.
    """

    goals_against_values, xga = _paired_values(
        goals_against,
        xga_history,
    )

    quality = _confidence_from_count(
        len(goals_against_values)
    )

    evidence: Dict[str, Any] = {
        "paired_observations": len(
            goals_against_values
        ),
        "threshold": KEPA_THRESHOLD,
    }

    if len(goals_against_values) < MIN_HISTORY:
        return _effect(
            "kepa",
            None,
            False,
            quality,
            evidence,
        )

    ga_avg = _mean(
        goals_against_values
    )

    xga_avg = _mean(xga)

    if (
        ga_avg is None
        or xga_avg is None
        or xga_avg <= EPSILON
    ):
        evidence.update({
            "goals_against_avg": ga_avg,
            "xga_avg": xga_avg,
        })

        return _effect(
            "kepa",
            None,
            False,
            quality,
            evidence,
        )

    ratio = ga_avg / xga_avg

    evidence.update({
        "goals_against_avg": ga_avg,
        "xga_avg": xga_avg,
        "defensive_ratio": ratio,
    })

    # Higher GA/xGA = negative defensive evidence.
    signal = _clamp(
        -(ratio - 1.0),
        -1.0,
        1.0,
    )

    return _effect(
        "kepa",
        signal,
        ratio >= KEPA_THRESHOLD,
        quality,
        evidence,
    )


# ============================================================
# HAALAND
# ============================================================

def _normalized_level(
    average: Optional[float],
    baseline: Optional[float],
) -> Optional[float]:
    """
    Normalise an observed attacking level against an explicitly
    defined research baseline.

    Returns:
        None if input/baseline is unavailable.
        Otherwise bounded 0..1.

    This is descriptive research evidence only.
    """

    if (
        average is None
        or baseline is None
        or baseline <= EPSILON
    ):
        return None

    return _clamp(
        average / baseline,
        0.0,
        1.0,
    )


def detect_haaland(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
    shots_history: Sequence[Any],
    shots_on_target: Sequence[Any],
    big_chances: Sequence[Any],
) -> EffectSignal:
    """
    Haaland hypothesis:

        unusually strong attacking state.

    IMPORTANT
    ---------
    The previous version used arbitrary weights:

        goals 30%
        xG 25%
        shots 20%
        SOT 15%
        big chances 10%

    Those weights are removed.

    v2.0 treats each attacking dimension as independent
    evidence and combines available dimensions using the
    median.

    Research baselines remain explicit and are not converted
    into xG/probability adjustments.
    """

    goals = tuple(goals_for)[:MAX_HISTORY]
    xg = tuple(xg_history)[:MAX_HISTORY]
    shots = tuple(shots_history)[:MAX_HISTORY]
    sot = tuple(shots_on_target)[:MAX_HISTORY]
    big = tuple(big_chances)[:MAX_HISTORY]

    goals_avg = _mean(goals)
    xg_avg = _mean(xg)
    shots_avg = _mean(shots)
    sot_avg = _mean(sot)
    big_avg = _mean(big)

    # Research baselines retained from v1.0.
    #
    # They are descriptive thresholds, not league strengths.
    #
    # Goals and xG are deliberately not invented if absent.
    levels = [
        _normalized_level(
            goals_avg,
            2.5,
        ),
        _normalized_level(
            xg_avg,
            2.5,
        ),
        _normalized_level(
            shots_avg,
            20.0,
        ),
        _normalized_level(
            sot_avg,
            8.0,
        ),
        _normalized_level(
            big_avg,
            4.0,
        ),
    ]

    available_levels = [
        value
        for value in levels
        if value is not None
    ]

    qualities = [
        _quality(goals),
        _quality(xg),
        _quality(shots),
        _quality(sot),
        _quality(big),
    ]

    evidence_quality = _average_quality(
        qualities
    )

    evidence: Dict[str, Any] = {
        "goals_avg": goals_avg,
        "xg_avg": xg_avg,
        "shots_avg": shots_avg,
        "sot_avg": sot_avg,
        "big_chances_avg": big_avg,

        "goals_level": levels[0],
        "xg_level": levels[1],
        "shots_level": levels[2],
        "sot_level": levels[3],
        "big_chances_level": levels[4],

        "available_dimensions": len(
            available_levels
        ),

        "baselines": {
            "goals": 2.5,
            "xg": 2.5,
            "shots": 20.0,
            "sot": 8.0,
            "big_chances": 4.0,
        },

        "detection_threshold": (
            HAALAND_DETECTION_THRESHOLD
        ),
    }

    if len(available_levels) < 2:
        return _effect(
            "haaland",
            None,
            False,
            evidence_quality,
            evidence,
        )

    # Median = no arbitrary component weighting.
    level = _clamp(
        median(available_levels),
        0.0,
        1.0,
    )

    evidence["attack_level"] = level

    # Convert 0..1 attacking level into signed evidence.
    #
    # 0.5 = neutral reference.
    # Above 0.5 = positive.
    # Below 0.5 = negative.
    #
    # This is descriptive only.
    signal = _clamp(
        2.0 * (level - 0.5),
        -1.0,
        1.0,
    )

    detected = (
        level >= HAALAND_DETECTION_THRESHOLD
    )

    return _effect(
        "haaland",
        signal,
        detected,
        evidence_quality,
        evidence,
    )


# ============================================================
# COMPOSITE SPECIAL FORM SIGNAL
# ============================================================

def aggregate_signals(
    signals: Dict[str, EffectSignal],
) -> Optional[float]:
    """
    Robust descriptive aggregation of SpecialForm evidence.

    Only measurable signals are used.

    Median is used instead of fixed effect weights.

    This prevents:
        Gladiator = 15%
        Fortress = 20%
        etc.

    from becoming hidden prediction coefficients.

    IMPORTANT:
        composite_signal is an evidence summary.

        It is NOT:
        - xG multiplier;
        - probability multiplier;
        - winner probability;
        - confidence;
        - risk.
    """

    values: List[float] = []

    for signal in signals.values():

        if signal.signal is None:
            continue

        values.append(
            _clamp(signal.signal)
        )

    if not values:
        return None

    return _clamp(
        median(values)
    )


# ============================================================
# SPECIAL FORM ORGAN
# ============================================================

class FormSpecial:
    """
    Independent SpecialForm evidence organ.
    """

    VERSION = SPECIAL_FORM_VERSION

    def analyze(
        self,
        context: Any,
        team_name: Optional[str] = None,
    ) -> SpecialFormResult:

        if team_name is None:
            team_name = _extract_field(
                context,
                "team",
                "team_name",
            )

        if team_name is None:
            team_name = "unknown"

        histories = _align_histories(
            context
        )

        signals: Dict[str, EffectSignal] = {}

        # ----------------------------------------------------
        # 1. Gladiator
        # ----------------------------------------------------

        signals["gladiator"] = detect_gladiator(
            histories["results"]
        )

        # ----------------------------------------------------
        # 2. Fortress
        # ----------------------------------------------------

        signals["fortress"] = detect_fortress(
            histories["venue"],
            histories["results"],
        )

        # ----------------------------------------------------
        # 3. Leicester
        # ----------------------------------------------------

        signals["leicester"] = detect_leicester(
            histories["venue"],
            histories["results"],
        )

        # ----------------------------------------------------
        # 4. God Kiss
        # ----------------------------------------------------

        signals["god_kiss"] = detect_god_kiss(
            histories["venue"]
        )

        # ----------------------------------------------------
        # 5. Dark Horse
        # ----------------------------------------------------

        signals["dark_horse"] = detect_dark_horse(
            histories["goals_for"],
            histories["xg"],
        )

        # ----------------------------------------------------
        # 6. Lukaku
        # ----------------------------------------------------

        signals["lukaku"] = detect_lukaku(
            histories["goals_for"],
            histories["xg"],
        )

        # ----------------------------------------------------
        # 7. Kepa
        # ----------------------------------------------------

        signals["kepa"] = detect_kepa(
            histories["goals_against"],
            histories["xga"],
        )

        # ----------------------------------------------------
        # 8. Haaland
        # ----------------------------------------------------

        signals["haaland"] = detect_haaland(
            histories["goals_for"],
            histories["xg"],
            histories["shots"],
            histories["shots_on_target"],
            histories["big_chances"],
        )

        # ----------------------------------------------------
        # Composite evidence
        # ----------------------------------------------------

        composite_signal = aggregate_signals(
            signals
        )

        detected_effects = [
            name
            for name, signal in signals.items()
            if signal.detected
        ]

        measurable_effects = [
            name
            for name, signal in signals.items()
            if signal.signal is not None
        ]

        positive_effects = [
            name
            for name, signal in signals.items()
            if signal.signal is not None
            and signal.signal > EPSILON
        ]

        negative_effects = [
            name
            for name, signal in signals.items()
            if signal.signal is not None
            and signal.signal < -EPSILON
        ]

        unknown_effects = [
            name
            for name, signal in signals.items()
            if signal.signal is None
        ]

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        diagnostics: Dict[str, Any] = {

            "version": self.VERSION,

            "formula_status": FORMULA_STATUS,

            "contract": CONTRACT,

            "model_role": (
                "independent_special_form_evidence"
            ),

            "history_order": "M1->M6",

            "history_max_size": MAX_HISTORY,

            "missing_is_zero": False,

            # ----------------------------------------------
            # Architecture
            # ----------------------------------------------

            "prediction_generated": False,

            "probability_generated": False,

            "poisson_used": False,

            "score_generated": False,

            "goal_model_modified": False,

            "form_win_modified": False,

            "defence_modified": False,

            "control_modified": False,

            "probability_model_modified": False,

            "score_predictor_modified": False,

            # ----------------------------------------------
            # Forbidden coupling
            # ----------------------------------------------

            "xg_multiplier_applied": False,

            "lambda_multiplier_applied": False,

            "winner_override": False,

            "confidence_generated": False,

            "risk_generated": False,

            "learning_performed": False,

            "database_accessed": False,

            "future_result_used": False,

            "known_result_as_prediction_input": False,

            # ----------------------------------------------
            # Other states
            # ----------------------------------------------

            "corners_used": False,

            "cards_used": False,

            # ----------------------------------------------
            # Research coefficients
            # ----------------------------------------------

            "fixed_predictive_weights": False,

            "effect_weights_used": False,

            "composite_method": (
                "median_of_measurable_effect_signals"
            ),

            "composite_is_prediction": False,

            "composite_is_probability": False,

            "composite_is_xg_adjustment": False,

            # ----------------------------------------------
            # Results
            # ----------------------------------------------

            "detected_effects": detected_effects,

            "measurable_effects": measurable_effects,

            "positive_effects": positive_effects,

            "negative_effects": negative_effects,

            "unknown_effects": unknown_effects,

            "detected_count": len(
                detected_effects
            ),

            "measurable_count": len(
                measurable_effects
            ),

            # ----------------------------------------------
            # Contract
            # ----------------------------------------------

            "signal_range": [
                SIGNAL_MIN,
                SIGNAL_MAX,
            ],

            "none_semantics": (
                "insufficient evidence"
            ),

            "zero_semantics": (
                "measurable neutral state"
            ),

            "adjustment_semantics": (
                "compatibility field only; always None"
            ),

            "state_changes_other_state": False,

            "state_is_winner_state": False,

            "state_is_probability_state": False,

            "state_is_score_state": False,
        }

        return SpecialFormResult(
            team=str(team_name),

            signals=signals,

            composite_signal=composite_signal,

            diagnostics=diagnostics,
        )

    # --------------------------------------------------------
    # COMPARE
    # --------------------------------------------------------

    def compare(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Descriptive comparison only.

        Does not calculate match probability.
        """

        home = self.analyze(
            home_context,
            team_name=home_team,
        )

        away = self.analyze(
            away_context,
            team_name=away_team,
        )

        if (
            home.composite_signal is None
            or away.composite_signal is None
        ):
            differential = None

        else:
            differential = _clamp(
                home.composite_signal
                - away.composite_signal
            )

        return {
            "home": home,
            "away": away,
            "differential": differential,

            "diagnostics": {
                "comparison_is_prediction": False,

                "winner_direction_generated": False,

                "winner_probability_generated": False,

                "probability_generated": False,

                "xg_modified": False,

                "home_composite": (
                    home.composite_signal
                ),

                "away_composite": (
                    away.composite_signal
                ),

                "differential": differential,
            },
        }


# ============================================================
# PUBLIC CONVENIENCE API
# ============================================================

def analyze_special(
    context: Any,
    team_name: Optional[str] = None,
) -> SpecialFormResult:
    """
    Public convenience wrapper.
    """

    return FormSpecial().analyze(
        context=context,
        team_name=team_name,
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "SPECIAL_FORM_VERSION",
    "VERSION",
    "FORMULA_STATUS",
    "CONTRACT",

    "EffectSignal",
    "SpecialFormResult",

    "FormSpecial",

    "analyze_special",
    "aggregate_signals",

    "detect_gladiator",
    "detect_fortress",
    "detect_leicester",
    "detect_god_kiss",
    "detect_dark_horse",
    "detect_lukaku",
    "detect_kepa",
    "detect_haaland",
]
