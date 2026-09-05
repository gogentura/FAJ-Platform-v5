#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SPECIAL FORM v1.0
============================================================

Purpose
-------
Special Form converts eight special football effects into
measurable, evidence-aware signals.

Architecture
------------
FormContext
    ↓
SpecialForm
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
FAJBrain

Important
---------
Special Form does NOT:
- calculate probabilities
- calculate Poisson
- modify xG
- modify FormWin
- modify Defence
- modify GoalModel
- make predictions
- train parameters
- directly change team rating

A signal is an observation.
A signal is NOT a multiplier.

None != 0
---------
Missing observations remain missing and are excluded from
mathematical calculations.

History convention
-------------------
M1 = oldest
M6 = newest

Research parameters are intentionally isolated below.
They are priors for later calibration/backtesting.
They must not be tuned against a single match.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple


VERSION = "1.0"


# ============================================================
# RESEARCH PARAMETERS
# ============================================================

# General
MIN_HISTORY = 3
MAX_HISTORY = 6
COMPOSITE_MIN = -0.30
COMPOSITE_MAX = 0.30

# Gladiator
GLADIATOR_MIN_WINS = 4
GLADIATOR_FULL_STREAK = 6
GLADIATOR_ADJUSTMENT_MAX = 0.12

# Fortress
FORTRESS_MIN_UNBEATEN = 4
FORTRESS_FULL_STREAK = 6
FORTRESS_ADJUSTMENT_MAX = 0.08

# Leicester / away strength
LEICESTER_MIN_WINS = 3
LEICESTER_MIN_MATCHES = 3
LEICESTER_WINDOW = 5
LEICESTER_ADJUSTMENT_MAX = 0.10

# God Kiss
GOD_KISS_MIN_AWAY_STREAK = 3
GOD_KISS_FULL_STREAK = 6
GOD_KISS_ADJUSTMENT_MAX = 0.10

# Finishing
DARK_HORSE_THRESHOLD = 1.20
LUKAKU_THRESHOLD = 0.80
FINISHING_NORMAL_RATIO = 1.00
FINISHING_STRENGTH_SCALE = 0.80

DARK_HORSE_ADJUSTMENT_MAX = 0.10
LUKAKU_ADJUSTMENT_MAX = 0.10

# Defensive vulnerability
KEPA_THRESHOLD = 1.30
KEPA_STRENGTH_SCALE = 1.00
KEPA_ADJUSTMENT_MAX = 0.08

# Haaland / attack level
HAALAND_GOALS_BASELINE = 2.50
HAALAND_XG_BASELINE = 2.50
HAALAND_SHOTS_BASELINE = 20.0
HAALAND_SOT_BASELINE = 8.0
HAALAND_BIG_CHANCES_BASELINE = 4.0

HAALAND_GOALS_WEIGHT = 0.30
HAALAND_XG_WEIGHT = 0.25
HAALAND_SHOTS_WEIGHT = 0.20
HAALAND_SOT_WEIGHT = 0.15
HAALAND_BIG_CHANCES_WEIGHT = 0.10

HAALAND_DETECTION_THRESHOLD = 0.50
HAALAND_ADJUSTMENT_MAX = 0.10

# Evidence
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.50
LOW_CONFIDENCE = 0.30


# ============================================================
# DATA CONTRACT
# ============================================================

@dataclass
class EffectSignal:
    """
    One measurable special-form effect.

    strength:
        magnitude of the observed effect, 0..1

    confidence:
        reliability of the signal, 0..1

    adjustment:
        research parameter only.
        SpecialForm NEVER applies it to xG or probability.
    """

    name: str
    detected: bool
    direction: str
    strength: float
    confidence: float
    evidence: Dict[str, Any]
    adjustment: Optional[float] = None


@dataclass
class SpecialFormResult:
    """
    Complete Special Form output for one team.
    """

    team: str
    signals: Dict[str, EffectSignal]
    composite_signal: Optional[float]
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """Convert value to finite float without inventing data."""

    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(result):
        return None

    return result


def _clean_numeric(values: Sequence[Any]) -> List[float]:
    """
    Keep only real numeric observations.

    None is excluded, never converted to 0.
    """

    result: List[float] = []

    for value in values:
        number = _safe_float(value)
        if number is not None:
            result.append(number)

    return result


def _last_six(values: Sequence[Any]) -> List[Any]:
    """Return the latest six observations preserving chronological order."""

    return list(values[-MAX_HISTORY:])


def _mean(values: Sequence[Any]) -> Optional[float]:
    numbers = _clean_numeric(values)

    if not numbers:
        return None

    return mean(numbers)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalise_result(result: Any) -> Optional[str]:
    """
    Normalise common result representations.

    Supported:
        W / D / L
        В / Н / П
        win / draw / loss
    """

    if result is None:
        return None

    value = str(result).strip().upper()

    mapping = {
        "W": "W",
        "WIN": "W",
        "В": "W",

        "D": "D",
        "DRAW": "D",
        "Н": "D",

        "L": "L",
        "LOSS": "L",
        "LOSE": "L",
        "П": "L",
    }

    return mapping.get(value)


def _normalise_venue(venue: Any) -> Optional[str]:
    """
    Normalise venue values.

    Supported:
        home / h / дома
        away / a / в гостях
    """

    if venue is None:
        return None

    value = str(venue).strip().lower()

    if value in {
        "home",
        "h",
        "дома",
        "дом",
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


def _missing_signal(
    name: str,
    evidence: Optional[Dict[str, Any]] = None,
) -> EffectSignal:
    """Create a neutral non-detected signal."""

    return EffectSignal(
        name=name,
        detected=False,
        direction="neutral",
        strength=0.0,
        confidence=0.0,
        evidence=evidence or {},
        adjustment=None,
    )


def _confidence_from_count(count: int, target: int = 6) -> float:
    if count <= 0:
        return 0.0

    return _clamp(count / float(target), 0.0, 1.0)


def _paired_values(
    first: Sequence[Any],
    second: Sequence[Any],
) -> Tuple[List[float], List[float]]:
    """
    Align two histories by position.

    Only pairs where BOTH observations exist are retained.

    This preserves chronological identity and avoids replacing
    missing values with zero.
    """

    first_result: List[float] = []
    second_result: List[float] = []

    for a, b in zip(first, second):
        a_value = _safe_float(a)
        b_value = _safe_float(b)

        if a_value is None or b_value is None:
            continue

        first_result.append(a_value)
        second_result.append(b_value)

    return first_result, second_result


def calculate_consistency(
    first: Sequence[Any],
    second: Sequence[Any],
) -> float:
    """
    Estimate consistency of a finishing/defensive relationship.

    For each available match:
        ratio = first / second

    The signal is considered consistent when the majority of
    observations remain on the same side of the neutral ratio 1.0.

    Returns 0..1.
    """

    paired_first, paired_second = _paired_values(first, second)

    if len(paired_first) < MIN_HISTORY:
        return _confidence_from_count(len(paired_first))

    ratios: List[float] = []

    for value_a, value_b in zip(paired_first, paired_second):
        if value_b <= 0:
            continue

        ratios.append(value_a / value_b)

    if len(ratios) < MIN_HISTORY:
        return _confidence_from_count(len(ratios))

    above = sum(1 for ratio in ratios if ratio > FINISHING_NORMAL_RATIO)
    below = sum(1 for ratio in ratios if ratio < FINISHING_NORMAL_RATIO)

    dominant = max(above, below)

    directional_consistency = dominant / len(ratios)
    evidence_confidence = _confidence_from_count(len(ratios))

    return _clamp(
        directional_consistency * evidence_confidence,
        0.0,
        1.0,
    )


def _get_history(
    context: Any,
    *names: str,
) -> List[Any]:
    """
    Retrieve the first available history field from FormContext.

    Primary fields are those used by FormContext v1.7.
    Aliases are kept for compatibility.
    """

    for name in names:
        if hasattr(context, name):
            value = getattr(context, name)

            if value is not None:
                try:
                    return list(value)
                except TypeError:
                    pass

    return []


def _align_histories(
    context: Any,
) -> Dict[str, List[Any]]:
    """
    Extract all histories required by Special Form.

    Histories remain in the original M1 -> M6 order.
    """

    return {
        "results": _last_six(
            _get_history(
                context,
                "results_history",
                "results",
                "result_history",
            )
        ),
        "venue": _last_six(
            _get_history(
                context,
                "venue_history",
            )
        ),
        "goals_for": _last_six(
            _get_history(
                context,
                "goals_for_history",
            )
        ),
        "goals_against": _last_six(
            _get_history(
                context,
                "goals_against_history",
            )
        ),
        "xg": _last_six(
            _get_history(
                context,
                "team_xg_history",
                "recent_xg",
                "xg_history",
            )
        ),
        "xga": _last_six(
            _get_history(
                context,
                "opponent_xg_history",
                "recent_xga",
                "xga_history",
            )
        ),
        "shots": _last_six(
            _get_history(
                context,
                "shots_history",
                "recent_shots",
            )
        ),
        "shots_on_target": _last_six(
            _get_history(
                context,
                "shots_on_target_history",
                "sot_history",
                "recent_shots_on_target",
            )
        ),
        "big_chances": _last_six(
            _get_history(
                context,
                "big_chances_history",
                "recent_big_chances",
            )
        ),
    }


# ============================================================
# EFFECT 1 — GLADIATOR
# ============================================================

def detect_gladiator(
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Gladiator:
        4+ consecutive wins.

    Strength:
        streak / 6

    Confidence:
        streak / 5
    """

    results = [
        _normalise_result(result)
        for result in _last_six(results_history)
    ]

    win_streak = 0

    for result in reversed(results):
        if result == "W":
            win_streak += 1
        else:
            break

    evidence = {
        "win_streak": win_streak,
        "matches_available": len(
            [result for result in results if result is not None]
        ),
    }

    if win_streak < GLADIATOR_MIN_WINS:
        return _missing_or_neutral_effect(
            name="gladiator",
            evidence=evidence,
        )

    strength = _clamp(
        win_streak / GLADIATOR_FULL_STREAK,
        0.0,
        1.0,
    )

    confidence = _clamp(
        win_streak / 5.0,
        0.0,
        1.0,
    )

    return EffectSignal(
        name="gladiator",
        detected=True,
        direction="positive",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=strength * GLADIATOR_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 2 — FORTRESS
# ============================================================

def detect_fortress(
    venue_history: Sequence[Any],
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Fortress:
        4+ consecutive home matches without defeat.

    Important:
        Only actual home matches are counted.
        Away matches do not break the home sequence.
    """

    paired: List[Tuple[str, str]] = []

    for venue, result in zip(
        _last_six(venue_history),
        _last_six(results_history),
    ):
        normalised_venue = _normalise_venue(venue)
        normalised_result = _normalise_result(result)

        if normalised_venue == "home" and normalised_result is not None:
            paired.append((normalised_venue, normalised_result))

    home_unbeaten = 0

    for _, result in reversed(paired):
        if result in ("W", "D"):
            home_unbeaten += 1
        else:
            break

    evidence = {
        "home_unbeaten": home_unbeaten,
        "home_matches": len(paired),
    }

    if home_unbeaten < FORTRESS_MIN_UNBEATEN:
        return _missing_or_neutral_effect(
            name="fortress",
            evidence=evidence,
        )

    strength = _clamp(
        home_unbeaten / FORTRESS_FULL_STREAK,
        0.0,
        1.0,
    )

    confidence = _clamp(
        home_unbeaten / 5.0,
        0.0,
        1.0,
    )

    return EffectSignal(
        name="fortress",
        detected=True,
        direction="positive",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=strength * FORTRESS_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 3 — LEICESTER
# ============================================================

def detect_leicester(
    venue_history: Sequence[Any],
    results_history: Sequence[Any],
) -> EffectSignal:
    """
    Leicester:
        At least 3 away wins in at least 3 away matches.

    Uses the latest five available away matches.
    """

    paired: List[Tuple[str, str]] = []

    venues = _last_six(venue_history)
    results = _last_six(results_history)

    for venue, result in zip(venues, results):
        normalised_venue = _normalise_venue(venue)
        normalised_result = _normalise_result(result)

        if normalised_venue == "away" and normalised_result is not None:
            paired.append((normalised_venue, normalised_result))

    away_window = paired[-LEICESTER_WINDOW:]

    away_wins = sum(
        1
        for _, result in away_window
        if result == "W"
    )

    away_matches = len(away_window)

    evidence = {
        "away_wins": away_wins,
        "away_matches": away_matches,
        "window": LEICESTER_WINDOW,
    }

    if (
        away_matches < LEICESTER_MIN_MATCHES
        or away_wins < LEICESTER_MIN_WINS
    ):
        return _missing_or_neutral_effect(
            name="leicester",
            evidence=evidence,
        )

    strength = _clamp(
        away_wins / float(LEICESTER_WINDOW),
        0.0,
        1.0,
    )

    confidence = _clamp(
        away_matches / float(LEICESTER_WINDOW),
        0.0,
        1.0,
    )

    return EffectSignal(
        name="leicester",
        detected=True,
        direction="positive",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=strength * LEICESTER_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 4 — GOD KISS
# ============================================================

def detect_god_kiss(
    venue_history: Sequence[Any],
) -> EffectSignal:
    """
    God Kiss:
        3+ consecutive away matches immediately preceding
        the current point in history.

    This is a contextual home-return signal.

    It does not itself mean the next home match must be won.
    """

    venues = [
        _normalise_venue(venue)
        for venue in _last_six(venue_history)
    ]

    away_streak = 0

    for venue in reversed(venues):
        if venue == "away":
            away_streak += 1
        else:
            break

    evidence = {
        "away_streak": away_streak,
        "matches_available": len(
            [venue for venue in venues if venue is not None]
        ),
    }

    if away_streak < GOD_KISS_MIN_AWAY_STREAK:
        return _missing_or_neutral_effect(
            name="god_kiss",
            evidence=evidence,
        )

    strength = _clamp(
        away_streak / GOD_KISS_FULL_STREAK,
        0.0,
        1.0,
    )

    confidence = _clamp(
        away_streak / 5.0,
        0.0,
        1.0,
    )

    return EffectSignal(
        name="god_kiss",
        detected=True,
        direction="positive",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=strength * GOD_KISS_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 5 — DARK HORSE
# ============================================================

def detect_dark_horse(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
) -> EffectSignal:
    """
    Dark Horse:
        Low/ordinary xG combined with sustained overperformance
        in goals relative to xG.

    ratio = goals_avg / xG_avg

    Detection:
        ratio > 1.20
    """

    goals = _last_six(goals_for)
    xg = _last_six(xg_history)

    paired_goals, paired_xg = _paired_values(goals, xg)

    evidence: Dict[str, Any] = {
        "observations": len(paired_goals),
    }

    if len(paired_goals) < MIN_HISTORY:
        return _missing_or_neutral_effect(
            name="dark_horse",
            evidence=evidence,
        )

    goals_avg = _mean(paired_goals)
    xg_avg = _mean(paired_xg)

    if goals_avg is None or xg_avg is None or xg_avg <= 0:
        evidence.update({
            "goals_avg": goals_avg,
            "xg_avg": xg_avg,
        })

        return _missing_or_neutral_effect(
            name="dark_horse",
            evidence=evidence,
        )

    finishing_ratio = goals_avg / xg_avg

    evidence.update({
        "goals_avg": goals_avg,
        "xg_avg": xg_avg,
        "finishing_ratio": finishing_ratio,
    })

    if finishing_ratio <= DARK_HORSE_THRESHOLD:
        return _missing_or_neutral_effect(
            name="dark_horse",
            evidence=evidence,
        )

    strength = _clamp(
        (finishing_ratio - FINISHING_NORMAL_RATIO)
        / FINISHING_STRENGTH_SCALE,
        0.0,
        1.0,
    )

    confidence = calculate_consistency(
        paired_goals,
        paired_xg,
    )

    return EffectSignal(
        name="dark_horse",
        detected=True,
        direction="positive",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=strength * DARK_HORSE_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 6 — LUKAKU
# ============================================================

def detect_lukaku(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
) -> EffectSignal:
    """
    Lukaku:
        Sustained underperformance in finishing.

    ratio = goals_avg / xG_avg

    Detection:
        ratio < 0.80
    """

    goals = _last_six(goals_for)
    xg = _last_six(xg_history)

    paired_goals, paired_xg = _paired_values(goals, xg)

    evidence: Dict[str, Any] = {
        "observations": len(paired_goals),
    }

    if len(paired_goals) < MIN_HISTORY:
        return _missing_or_neutral_effect(
            name="lukaku",
            evidence=evidence,
        )

    goals_avg = _mean(paired_goals)
    xg_avg = _mean(paired_xg)

    if goals_avg is None or xg_avg is None or xg_avg <= 0:
        evidence.update({
            "goals_avg": goals_avg,
            "xg_avg": xg_avg,
        })

        return _missing_or_neutral_effect(
            name="lukaku",
            evidence=evidence,
        )

    finishing_ratio = goals_avg / xg_avg

    evidence.update({
        "goals_avg": goals_avg,
        "xg_avg": xg_avg,
        "finishing_ratio": finishing_ratio,
    })

    if finishing_ratio >= LUKAKU_THRESHOLD:
        return _missing_or_neutral_effect(
            name="lukaku",
            evidence=evidence,
        )

    strength = _clamp(
        (FINISHING_NORMAL_RATIO - finishing_ratio)
        / FINISHING_STRENGTH_SCALE,
        0.0,
        1.0,
    )

    confidence = calculate_consistency(
        paired_goals,
        paired_xg,
    )

    return EffectSignal(
        name="lukaku",
        detected=True,
        direction="negative",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=-strength * LUKAKU_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 7 — KEPA
# ============================================================

def detect_kepa(
    goals_against: Sequence[Any],
    xga_history: Sequence[Any],
) -> EffectSignal:
    """
    Kepa:
        Goals conceded materially exceed expected goals conceded.

    ratio = goals_against_avg / xGA_avg

    Detection:
        ratio > 1.30
    """

    goals_against_values = _last_six(goals_against)
    xga_values = _last_six(xga_history)

    paired_ga, paired_xga = _paired_values(
        goals_against_values,
        xga_values,
    )

    evidence: Dict[str, Any] = {
        "observations": len(paired_ga),
    }

    if len(paired_ga) < MIN_HISTORY:
        return _missing_or_neutral_effect(
            name="kepa",
            evidence=evidence,
        )

    ga_avg = _mean(paired_ga)
    xga_avg = _mean(paired_xga)

    if ga_avg is None or xga_avg is None or xga_avg <= 0:
        evidence.update({
            "ga_avg": ga_avg,
            "xga_avg": xga_avg,
        })

        return _missing_or_neutral_effect(
            name="kepa",
            evidence=evidence,
        )

    defensive_ratio = ga_avg / xga_avg

    evidence.update({
        "ga_avg": ga_avg,
        "xga_avg": xga_avg,
        "defensive_ratio": defensive_ratio,
    })

    if defensive_ratio <= KEPA_THRESHOLD:
        return _missing_or_neutral_effect(
            name="kepa",
            evidence=evidence,
        )

    strength = _clamp(
        (defensive_ratio - FINISHING_NORMAL_RATIO)
        / KEPA_STRENGTH_SCALE,
        0.0,
        1.0,
    )

    confidence = calculate_consistency(
        paired_ga,
        paired_xga,
    )

    return EffectSignal(
        name="kepa",
        detected=True,
        direction="negative",
        strength=strength,
        confidence=confidence,
        evidence=evidence,
        adjustment=-strength * KEPA_ADJUSTMENT_MAX,
    )


# ============================================================
# EFFECT 8 — HAALAND
# ============================================================

def detect_haaland(
    goals_for: Sequence[Any],
    xg_history: Sequence[Any],
    shots_history: Sequence[Any],
    shots_on_target: Sequence[Any],
    big_chances: Sequence[Any],
) -> EffectSignal:
    """
    Haaland:
        Composite attacking power signal.

    Components:
        goals           30%
        xG              25%
        shots           20%
        shots on target 15%
        big chances     10%

    All components are normalised against research baselines.

    The signal is observational only.
    """

    goals = _last_six(goals_for)
    xg = _last_six(xg_history)
    shots = _last_six(shots_history)
    sot = _last_six(shots_on_target)
    big = _last_six(big_chances)

    component_values: Dict[str, Optional[float]] = {
        "goals_avg": _mean(goals),
        "xg_avg": _mean(xg),
        "shots_avg": _mean(shots),
        "sot_avg": _mean(sot),
        "big_chances_avg": _mean(big),
    }

    available_components = sum(
        value is not None
        for value in component_values.values()
    )

    if component_values["goals_avg"] is None:
        return _missing_or_neutral_effect(
            name="haaland",
            evidence={
                **component_values,
                "available_components": available_components,
            },
        )

    scores: Dict[str, Optional[float]] = {
        "goals_score": (
            _clamp(
                component_values["goals_avg"]
                / HAALAND_GOALS_BASELINE,
                0.0,
                1.0,
            )
            if component_values["goals_avg"] is not None
            else None
        ),
        "xg_score": (
            _clamp(
                component_values["xg_avg"]
                / HAALAND_XG_BASELINE,
                0.0,
                1.0,
            )
            if component_values["xg_avg"] is not None
            else None
        ),
        "shots_score": (
            _clamp(
                component_values["shots_avg"]
                / HAALAND_SHOTS_BASELINE,
                0.0,
                1.0,
            )
            if component_values["shots_avg"] is not None
            else None
        ),
        "sot_score": (
            _clamp(
                component_values["sot_avg"]
                / HAALAND_SOT_BASELINE,
                0.0,
                1.0,
            )
            if component_values["sot_avg"] is not None
            else None
        ),
        "big_chances_score": (
            _clamp(
                component_values["big_chances_avg"]
                / HAALAND_BIG_CHANCES_BASELINE,
                0.0,
                1.0,
            )
            if component_values["big_chances_avg"] is not None
            else None
        ),
    }

    weighted_components = [
        ("goals_score", HAALAND_GOALS_WEIGHT),
        ("xg_score", HAALAND_XG_WEIGHT),
        ("shots_score", HAALAND_SHOTS_WEIGHT),
        ("sot_score", HAALAND_SOT_WEIGHT),
        ("big_chances_score", HAALAND_BIG_CHANCES_WEIGHT),
    ]

    numerator = 0.0
    denominator = 0.0

    for key, weight in weighted_components:
        value = scores[key]

        if value is None:
            continue

        numerator += value * weight
        denominator += weight

    if denominator <= 0:
        return _missing_or_neutral_effect(
            name="haaland",
            evidence={
                **component_values,
                **scores,
                "available_components": available_components,
            },
        )

    attack_level = _clamp(
        numerator / denominator,
        0.0,
        1.0,
    )

    # Confidence has two components:
    # 1. how many observations exist for the primary history
    # 2. how many attack dimensions are available
    primary_count = len(
        _clean_numeric(goals)
    )

    history_confidence = _confidence_from_count(
        primary_count
    )

    component_confidence = _clamp(
        available_components / 5.0,
        0.0,
        1.0,
    )

    confidence = (
        0.70 * history_confidence
        + 0.30 * component_confidence
    )

    detected = attack_level >= HAALAND_DETECTION_THRESHOLD

    evidence = {
        **component_values,
        **scores,
        "available_components": available_components,
        "attack_level": attack_level,
    }

    return EffectSignal(
        name="haaland",
        detected=detected,
        direction="positive" if detected else "neutral",
        strength=attack_level,
        confidence=confidence,
        evidence=evidence,
        adjustment=(
            attack_level * HAALAND_ADJUSTMENT_MAX
            if detected
            else None
        ),
    )


# ============================================================
# INTERNAL NEUTRAL EFFECT
# ============================================================

def _missing_or_neutral_effect(
    name: str,
    evidence: Dict[str, Any],
) -> EffectSignal:
    """
    Return neutral signal while preserving evidence.

    detected=False does NOT mean the effect is disproved.
    It means the defined detection condition is not currently met.
    """

    return EffectSignal(
        name=name,
        detected=False,
        direction="neutral",
        strength=0.0,
        confidence=0.0,
        evidence=evidence,
        adjustment=None,
    )


# ============================================================
# AGGREGATION
# ============================================================

def aggregate_signals(
    signals: Dict[str, EffectSignal],
) -> Optional[float]:
    """
    Aggregate detected special effects.

    Each signal contributes:

        strength × confidence

    Positive effects and negative effects are separated.

    The result is bounded to:
        [-0.30, +0.30]

    Important:
        This is a descriptive composite signal.
        It is NOT an xG multiplier.
    """

    positive_values: List[float] = []
    negative_values: List[float] = []

    for signal in signals.values():
        if not signal.detected:
            continue

        contribution = (
            _clamp(signal.strength, 0.0, 1.0)
            * _clamp(signal.confidence, 0.0, 1.0)
        )

        if signal.direction == "positive":
            positive_values.append(contribution)

        elif signal.direction == "negative":
            negative_values.append(contribution)

    if not positive_values and not negative_values:
        return None

    positive_mean = (
        mean(positive_values)
        if positive_values
        else 0.0
    )

    negative_mean = (
        mean(negative_values)
        if negative_values
        else 0.0
    )

    composite = positive_mean - negative_mean

    return _clamp(
        composite,
        COMPOSITE_MIN,
        COMPOSITE_MAX,
    )


# ============================================================
# SPECIAL FORM
# ============================================================

class FormSpecial:
    """
    Special Form analytical organ.

    It consumes FormContext and produces measurable special
    effect signals.

    It does not modify context or any other FAJ model.
    """

    VERSION = VERSION

    def analyze(
        self,
        context: Any,
        team_name: Optional[str] = None,
    ) -> SpecialFormResult:
        """
        Analyse one team's special form.

        Parameters
        ----------
        context:
            FormContext instance.

        team_name:
            Optional explicit team name.

        Returns
        -------
        SpecialFormResult
        """

        if team_name is None:
            team_name = getattr(
                context,
                "team",
                None,
            )

        if team_name is None:
            team_name = getattr(
                context,
                "team_name",
                "unknown",
            )

        histories = _align_histories(context)

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
        # Composite
        # ----------------------------------------------------

        composite = aggregate_signals(signals)

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        detected_names = [
            name
            for name, signal in signals.items()
            if signal.detected
        ]

        positive_names = [
            name
            for name, signal in signals.items()
            if signal.detected
            and signal.direction == "positive"
        ]

        negative_names = [
            name
            for name, signal in signals.items()
            if signal.detected
            and signal.direction == "negative"
        ]

        diagnostics = {
            "version": self.VERSION,
            "history_order": "M1 -> M6",
            "history_length": {
                key: len(value)
                for key, value in histories.items()
            },
            "detected_effects": detected_names,
            "positive_effects": positive_names,
            "negative_effects": negative_names,
            "detected_count": len(detected_names),
            "positive_count": len(positive_names),
            "negative_count": len(negative_names),
            "composite_signal": composite,
            "composite_range": [
                COMPOSITE_MIN,
                COMPOSITE_MAX,
            ],
            "adjustments_are_applied": False,
        }

        return SpecialFormResult(
            team=str(team_name),
            signals=signals,
            composite_signal=composite,
            diagnostics=diagnostics,
        )

    def compare(
        self,
        home_context: Any,
        away_context: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare Special Form of two teams.

        This method remains descriptive.

        It does NOT calculate match probability.
        It does NOT modify xG.
        """

        home_result = self.analyze(
            home_context,
            team_name=home_team,
        )

        away_result = self.analyze(
            away_context,
            team_name=away_team,
        )

        home_signal = home_result.composite_signal
        away_signal = away_result.composite_signal

        differential: Optional[float]

        if home_signal is None or away_signal is None:
            differential = None
        else:
            differential = _clamp(
                home_signal - away_signal,
                COMPOSITE_MIN,
                COMPOSITE_MAX,
            )

        return {
            "home": home_result,
            "away": away_result,
            "differential": differential,
            "diagnostics": {
                "home_composite": home_signal,
                "away_composite": away_signal,
                "differential": differential,
                "used_for_prediction": False,
            },
        }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def analyze_special(
    context: Any,
    team_name: Optional[str] = None,
) -> SpecialFormResult:
    """
    Convenience wrapper.
    """

    return FormSpecial().analyze(
        context=context,
        team_name=team_name,
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "VERSION",
    "EffectSignal",
    "SpecialFormResult",
    "FormSpecial",
    "analyze_special",
    "aggregate_signals",
    "calculate_consistency",
    "detect_gladiator",
    "detect_fortress",
    "detect_leicester",
    "detect_god_kiss",
    "detect_dark_horse",
    "detect_lukaku",
    "detect_kepa",
    "detect_haaland",
]
