#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
DEFENCE v2.0
============================================================

DEFENCE = defensive evidence organ.

ROLE
----
Defence measures defensive evidence from FACTS/FormContext.

It does NOT:
    - predict the winner;
    - calculate probabilities;
    - calculate Poisson;
    - modify GoalModel;
    - calculate confidence;
    - calculate risk;
    - use future result;
    - use bookmaker odds;
    - generate WinnerState.

ARCHITECTURE
------------

FACTS
  ↓
FormContext
  ↓
Defence
  ↓
DefenceState
  ↓
Winner synthesis / AnalysisEngine

IMPORTANT
---------
Defence is an evidence organ.

Its signals are evidence in [-1, +1]:

    +1 = evidence toward stronger defensive state
    -1 = evidence toward weaker defensive state
     0 = neutral change / no directional movement

None means that the evidence cannot be calculated.

None != 0.

No arbitrary league baseline is used.

Corners remain a separate process and are NOT included
in the main Defence process signal.
============================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, tanh
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# VERSION / CONSTANTS
# ============================================================

DEFENCE_VERSION = "2.0"

EPSILON = 1e-9

# Oldest → newest.
# The newest observation receives the largest weight.
TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)


# Defensive process.
#
# Corners deliberately excluded.
#
# Shots conceded:
#   volume of opponent shooting.
#
# SOT conceded:
#   quality proxy of opponent shots on target.
#
# Big chances:
#   high-danger opportunities conceded.
PROCESS_WEIGHTS = {
    "shots": 0.45,
    "sot": 0.35,
    "big_chances": 0.20,
}


SOT_VOLUME_WEIGHT = 0.65
SOT_RATE_WEIGHT = 0.35


# Outcome is a separate evidence block.
# It is NOT allowed to change GoalModel.
#
# Momentum is a separate evidence block.
#
# Venue is currently unavailable because no defensible
# venue-specific mathematical baseline has been approved.
FINAL_WEIGHTS = {
    "process": 0.65,
    "outcome": 0.10,
    "momentum": 0.15,
    "venue": 0.10,
}


MOMENTUM_WEIGHTS = {
    "shots": 0.50,
    "sot": 0.30,
    "goals": 0.20,
}


# Secondary diagnostic evidence is bounded before being
# combined with another evidence source.
BIG_CHANCES_CAP = 0.50


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Convert a value to finite float.

    Missing/invalid values remain None.
    """

    if value is None or isinstance(value, bool):
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(value):
        return None

    return value


def _get_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Read a value from dict-like objects, mappings or objects.

    This keeps Defence compatible with FormContext dataclasses
    as well as dictionary-based contexts.
    """

    if obj is None:
        return None

    for name in names:

        if isinstance(obj, dict) and name in obj:
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


def _clamp(
    value: float,
    low: float = -1.0,
    high: float = 1.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


def _mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _median(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return float(median(clean))


def _weighted_mean(
    values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:

    pairs = []

    for value, weight in zip(values, weights):

        numeric = _safe_float(value)

        if numeric is None:
            continue

        pairs.append(
            (
                numeric,
                float(weight),
            )
        )

    if not pairs:
        return None

    denominator = sum(
        weight
        for _, weight in pairs
    )

    if denominator <= EPSILON:
        return None

    return sum(
        value * weight
        for value, weight in pairs
    ) / denominator


def _mad(
    values: Sequence[Optional[float]],
) -> Optional[float]:

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    center = median(clean)

    return float(
        median(
            abs(value - center)
            for value in clean
        )
    )


def _robust_scale(
    values: Sequence[Optional[float]],
) -> Optional[float]:

    clean = [
        value
        for value in values
        if value is not None
    ]

    if len(clean) < 2:
        return None

    mad = _mad(clean)

    if mad is not None and mad > EPSILON:
        return 1.4826 * mad

    data_range = max(clean) - min(clean)

    if data_range <= EPSILON:
        return None

    return data_range / 2.0


def _ols_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:

    observations = []

    for index, value in enumerate(values):

        numeric = _safe_float(value)

        if numeric is None:
            continue

        observations.append(
            (
                float(index),
                numeric,
            )
        )

    if len(observations) < 2:
        return None

    x = [item[0] for item in observations]
    y = [item[1] for item in observations]

    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)

    denominator = sum(
        (xi - x_mean) ** 2
        for xi in x
    )

    if denominator <= EPSILON:
        return None

    numerator = sum(
        (xi - x_mean) * (yi - y_mean)
        for xi, yi in zip(x, y)
    )

    return numerator / denominator


def _combine_optional(
    components: Sequence[
        Tuple[Optional[float], float]
    ],
) -> Optional[float]:
    """
    Weighted combination with renormalisation over available
    evidence only.

    Missing evidence is NOT converted to zero.
    """

    available = [
        (value, weight)
        for value, weight in components
        if value is not None
    ]

    if not available:
        return None

    denominator = sum(
        weight
        for _, weight in available
    )

    if denominator <= EPSILON:
        return None

    result = (
        sum(
            value * weight
            for value, weight in available
        )
        / denominator
    )

    return _clamp(result)


def _availability(
    values: Sequence[Optional[float]],
) -> Optional[float]:

    if not values:
        return None

    return (
        sum(
            value is not None
            for value in values
        )
        / len(values)
    )


def _valid_count(
    values: Sequence[Optional[float]],
) -> int:

    return sum(
        value is not None
        for value in values
    )


def _extract_history(
    context: Any,
    *names: str,
) -> List[Optional[float]]:

    for name in names:

        value = _get_value(
            context,
            name,
        )

        if isinstance(
            value,
            (list, tuple),
        ):

            return [
                _safe_float(item)
                for item in value
            ]

    return []


# ============================================================
# DEFENSIVE SIGNALS
# ============================================================

def _inverse_state_signal(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Defensive state-change signal.

    Lower recent conceded volume relative to the team's own
    historical centre produces positive defensive evidence.

    No external baseline is used.

    IMPORTANT:
        This does NOT say that the team is absolutely strong.
        It says whether the recent defensive state is moving
        in a better/worse direction relative to its own history.

    Therefore:
        constant history -> None
        insufficient variation -> None
    """

    clean = [
        value
        for value in values
        if value is not None
    ]

    if len(clean) < 2:
        return None

    recent = _weighted_mean(values)
    center = _median(values)
    scale = _robust_scale(values)

    if (
        recent is None
        or center is None
        or scale is None
        or scale <= EPSILON
    ):
        return None

    return _clamp(
        -tanh(
            (recent - center) / scale
        )
    )


def _inverse_trend_signal(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Defensive trend signal.

    Falling conceded values => positive evidence.
    Rising conceded values => negative evidence.
    """

    slope = _ols_slope(values)
    scale = _robust_scale(values)

    if (
        slope is None
        or scale is None
        or scale <= EPSILON
    ):
        return None

    return _clamp(
        -tanh(
            slope / scale
        )
    )


def _bounded(
    value: Optional[float],
    cap: float,
) -> Optional[float]:

    if value is None:
        return None

    return max(
        -cap,
        min(cap, value),
    )


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class DefenceSignals:

    # Primary defensive evidence
    xga_signal: Optional[float] = None

    shots_conceded_signal: Optional[float] = None
    sot_conceded_signal: Optional[float] = None

    sot_volume_signal: Optional[float] = None
    sot_rate_signal: Optional[float] = None

    big_chances_signal: Optional[float] = None

    goals_conceded_signal: Optional[float] = None

    # Secondary defensive evidence
    possession_signal: Optional[float] = None

    blocked_shots_signal: Optional[float] = None
    blocked_rate_signal: Optional[float] = None

    woodwork_signal: Optional[float] = None

    dangerous_attacks_signal: Optional[float] = None
    attacks_signal: Optional[float] = None

    # Derived defensive evidence blocks
    defensive_creation_signal: Optional[float] = None
    defensive_control_signal: Optional[float] = None
    defensive_outcome_signal: Optional[float] = None
    defensive_momentum_signal: Optional[float] = None

    venue_signal: Optional[float] = None


@dataclass
class DefenceState:

    version: str
    team: Optional[str]

    signals: DefenceSignals

    # Independent evidence blocks
    process_signal: Optional[float]
    outcome_signal: Optional[float]
    momentum_signal: Optional[float]
    venue_signal: Optional[float]

    # Diagnostics
    stability: Optional[float]
    evidence_quality: Optional[float]

    # Compatibility aggregate.
    #
    # This is NOT a WinnerState.
    # It is NOT a probability.
    # It must not override other states.
    defence_score: Optional[float]

    # Number of distinct match positions containing at least
    # one usable defensive observation.
    sample_size: int

    available_xga: int
    available_shots: int
    available_sot: int
    available_big_chances: int
    available_corners: int
    available_goals: int

    evidence_vector: Dict[
        str,
        Optional[float],
    ]

    evidence_sources: List[str]

    evidence_conflicts: List[str]

    defensive_quality: Optional[float]

    process_data_quality: Optional[float]
    creation_data_quality: Optional[float]
    outcome_data_quality: Optional[float]
    momentum_data_quality: Optional[float]

    diagnostics: Dict[str, Any]


@dataclass
class DefenceComparison:

    home_defence: Optional[float]
    away_defence: Optional[float]

    relative_defence_advantage: Optional[float]

    home_state: Optional[DefenceState] = None
    away_state: Optional[DefenceState] = None

    relative_creation: Optional[float] = None
    relative_process: Optional[float] = None
    relative_control: Optional[float] = None
    relative_outcome: Optional[float] = None
    relative_momentum: Optional[float] = None

    evidence_sources: Optional[List[str]] = None


# ============================================================
# DEFENCE
# ============================================================

class Defence:

    def __init__(
        self,
        *,
        temporal_weights: Sequence[
            float
        ] = TEMPORAL_WEIGHTS,
    ) -> None:

        self.temporal_weights = tuple(
            float(weight)
            for weight in temporal_weights
        )

    # ========================================================
    # HISTORIES
    # ========================================================

    def _histories(
        self,
        context: Any,
    ) -> Dict[str, List[Optional[float]]]:

        return {

            # xGA = independent primary defensive evidence.
            "xga": _extract_history(
                context,
                "recent_xga",
                "team_xga_history",
                "xga_history",
                "opponent_xg_history",
            ),

            "shots": _extract_history(
                context,
                "shots_against_history",
                "opponent_shots_history",
                "shots_conceded_history",
                "team_shots_against_history",
            ),

            "sot": _extract_history(
                context,
                "shots_on_target_against_history",
                "opponent_shots_on_target_history",
                "sot_conceded_history",
                "opponent_sot_history",
            ),

            "blocked": _extract_history(
                context,
                "blocked_shots_against_history",
                "opponent_blocked_shots_history",
                "blocked_shots_conceded_history",
            ),

            "woodwork": _extract_history(
                context,
                "woodwork_against_history",
                "opponent_woodwork_history",
                "woodwork_conceded_history",
            ),

            "possession_opponent": _extract_history(
                context,
                "opponent_possession_history",
                "possession_against_history",
            ),

            "corners": _extract_history(
                context,
                "corners_against_history",
            ),

            "big_chances": _extract_history(
                context,
                "big_chances_against_history",
                "opponent_big_chances_history",
                "big_chances_conceded_history",
            ),

            "attacks": _extract_history(
                context,
                "attacks_against_history",
                "opponent_attacks_history",
                "attacks_conceded_history",
            ),

            "dangerous_attacks": _extract_history(
                context,
                "dangerous_attacks_against_history",
                "opponent_dangerous_attacks_history",
                "dangerous_attacks_conceded_history",
            ),

            "goals": _extract_history(
                context,
                "goals_against_history",
                "team_goals_against_history",
            ),
        }

    # ========================================================
    # SOT
    # ========================================================

    def _sot_signals(
        self,
        shots: Sequence[Optional[float]],
        sot: Sequence[Optional[float]],
    ) -> Tuple[
        Optional[float],
        Optional[float],
        Optional[float],
    ]:

        sot_volume_signal = _inverse_state_signal(
            sot
        )

        rate_history: List[
            Optional[float]
        ] = []

        for shots_value, sot_value in zip(
            shots,
            sot,
        ):

            if (
                shots_value is None
                or sot_value is None
                or shots_value <= EPSILON
            ):
                rate_history.append(None)

            else:
                rate_history.append(
                    sot_value / shots_value
                )

        sot_rate_signal = _inverse_state_signal(
            rate_history
        )

        sot_signal = _combine_optional(
            (
                (
                    sot_volume_signal,
                    SOT_VOLUME_WEIGHT,
                ),
                (
                    sot_rate_signal,
                    SOT_RATE_WEIGHT,
                ),
            )
        )

        return (
            sot_signal,
            sot_volume_signal,
            sot_rate_signal,
        )

    # ========================================================
    # PROCESS
    # ========================================================

    def _process_signal(
        self,
        *,
        shots_signal: Optional[float],
        sot_signal: Optional[float],
        big_chances_signal: Optional[float],
    ) -> Optional[float]:
        """
        Core defensive process.

        IMPORTANT:
            corners are intentionally NOT included.

        Corner State owns corner mathematics.
        """

        return _combine_optional(
            (
                (
                    shots_signal,
                    PROCESS_WEIGHTS["shots"],
                ),
                (
                    sot_signal,
                    PROCESS_WEIGHTS["sot"],
                ),
                (
                    _bounded(
                        big_chances_signal,
                        BIG_CHANCES_CAP,
                    ),
                    PROCESS_WEIGHTS["big_chances"],
                ),
            )
        )

    # ========================================================
    # MOMENTUM
    # ========================================================

    def _momentum(
        self,
        *,
        shots: Sequence[Optional[float]],
        sot: Sequence[Optional[float]],
        goals: Sequence[Optional[float]],
    ) -> Optional[float]:

        return _combine_optional(
            (
                (
                    _inverse_trend_signal(shots),
                    MOMENTUM_WEIGHTS["shots"],
                ),
                (
                    _inverse_trend_signal(sot),
                    MOMENTUM_WEIGHTS["sot"],
                ),
                (
                    _inverse_trend_signal(goals),
                    MOMENTUM_WEIGHTS["goals"],
                ),
            )
        )

    # ========================================================
    # STABILITY
    # ========================================================

    def _stability(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        values = []

        for key in (
            "xga",
            "shots",
            "sot",
            "big_chances",
        ):

            history = [
                value
                for value in histories.get(
                    key,
                    [],
                )
                if value is not None
            ]

            if len(history) < 2:
                continue

            mean_value = _mean(history)
            scale = _robust_scale(history)

            if (
                mean_value is None
                or scale is None
                or abs(mean_value) <= EPSILON
            ):
                continue

            values.append(
                scale / abs(mean_value)
            )

        if not values:
            return None

        average = sum(values) / len(values)

        return max(
            0.0,
            min(
                1.0,
                1.0 / (1.0 + average),
            ),
        )

    # ========================================================
    # EVIDENCE QUALITY
    # ========================================================

    def _evidence_quality(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        importance = {
            "xga": 0.55,
            "shots": 0.20,
            "sot": 0.15,
            "big_chances": 0.10,
        }

        numerator = 0.0
        denominator = 0.0

        for key, weight in importance.items():

            history = histories.get(
                key,
                [],
            )

            availability = _availability(
                history
            )

            if availability is None:
                continue

            numerator += (
                availability * weight
            )

            denominator += weight

        if denominator <= EPSILON:
            return None

        return _clamp(
            numerator / denominator,
            0.0,
            1.0,
        )

    # ========================================================
    # VENUE
    # ========================================================

    def _venue_signal(
        self,
        *,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
        context: Any,
    ) -> Optional[float]:
        """
        No defensible venue-specific mathematical model has
        been approved.

        Therefore venue evidence remains None.
        """

        return None

    # ========================================================
    # SAMPLE SIZE
    # ========================================================

    def _sample_size(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> int:
        """
        Count distinct match positions with at least one
        usable defensive observation.

        This avoids the old:

            max(len(history))

        problem.
        """

        relevant_keys = (
            "xga",
            "shots",
            "sot",
            "big_chances",
            "goals",
            "corners",
            "blocked",
            "woodwork",
            "possession_opponent",
            "attacks",
            "dangerous_attacks",
        )

        max_length = max(
            (
                len(histories.get(key, []))
                for key in relevant_keys
            ),
            default=0,
        )

        count = 0

        for index in range(max_length):

            has_value = False

            for key in relevant_keys:

                history = histories.get(
                    key,
                    [],
                )

                if (
                    index < len(history)
                    and history[index] is not None
                ):
                    has_value = True
                    break

            if has_value:
                count += 1

        return count

    # ========================================================
    # CONFLICTS
    # ========================================================

    def _detect_conflicts(
        self,
        evidence: Dict[
            str,
            Optional[float],
        ],
    ) -> List[str]:

        available = {
            key: value
            for key, value in evidence.items()
            if value is not None
        }

        if len(available) < 2:
            return []

        conflicts: List[str] = []

        positive = [
            key
            for key, value in available.items()
            if value > 0.15
        ]

        negative = [
            key
            for key, value in available.items()
            if value < -0.15
        ]

        if positive and negative:
            conflicts.append(
                "defensive_evidence_conflict"
            )

        xga = evidence.get("xga")
        process = evidence.get("process")

        if (
            xga is not None
            and process is not None
            and (
                (
                    xga > 0.25
                    and process < -0.25
                )
                or
                (
                    xga < -0.25
                    and process > 0.25
                )
            )
        ):
            conflicts.append(
                "xga_process_conflict"
            )

        momentum = evidence.get(
            "momentum"
        )

        if (
            process is not None
            and momentum is not None
            and (
                (
                    process > 0.25
                    and momentum < -0.25
                )
                or
                (
                    process < -0.25
                    and momentum > 0.25
                )
            )
        ):
            conflicts.append(
                "process_momentum_conflict"
            )

        return conflicts

    # ========================================================
    # DEFENSIVE QUALITY
    # ========================================================

    def _defensive_quality(
        self,
        *,
        evidence: Dict[
            str,
            Optional[float],
        ],
        stability: Optional[float],
        evidence_quality: Optional[float],
    ) -> Optional[float]:
        """
        Descriptive evidence quality.

        This is NOT confidence.

        It measures how much usable evidence exists and how
        internally aligned that evidence is.
        """

        available = [
            value
            for value in evidence.values()
            if value is not None
        ]

        if not available:
            return None

        if evidence_quality is None:
            return None

        agreement = abs(
            sum(available)
            / len(available)
        )

        agreement = min(
            1.0,
            agreement,
        )

        if stability is None:
            return (
                evidence_quality
                * agreement
            )

        return (
            evidence_quality
            * stability
            * agreement
        )

    # ========================================================
    # CALCULATE
    # ========================================================

    def calculate(
        self,
        context: Any,
        *,
        team_name: Optional[str] = None,
    ) -> DefenceState:

        histories = self._histories(
            context
        )

        xga = histories["xga"]
        shots = histories["shots"]
        sot = histories["sot"]
        corners = histories["corners"]
        big_chances = histories["big_chances"]
        goals = histories["goals"]

        # ----------------------------------------------------
        # PRIMARY DEFENSIVE SIGNALS
        # ----------------------------------------------------

        xga_signal = _inverse_state_signal(
            xga
        )

        shots_signal = _inverse_state_signal(
            shots
        )

        (
            sot_signal,
            sot_volume_signal,
            sot_rate_signal,
        ) = self._sot_signals(
            shots,
            sot,
        )

        big_chances_signal = (
            _inverse_state_signal(
                big_chances
            )
        )

        goals_signal = (
            _inverse_state_signal(
                goals
            )
        )

        # ----------------------------------------------------
        # SECONDARY DIAGNOSTIC SIGNALS
        # ----------------------------------------------------

        blocked_signal = (
            _inverse_state_signal(
                histories["blocked"]
            )
        )

        woodwork_signal = (
            _inverse_state_signal(
                histories["woodwork"]
            )
        )

        possession_signal = (
            _inverse_state_signal(
                histories[
                    "possession_opponent"
                ]
            )
        )

        attacks_signal = (
            _inverse_state_signal(
                histories["attacks"]
            )
        )

        dangerous_attacks_signal = (
            _inverse_state_signal(
                histories[
                    "dangerous_attacks"
                ]
            )
        )

        # ----------------------------------------------------
        # CORE DEFENSIVE PROCESS
        # ----------------------------------------------------

        process_signal = self._process_signal(
            shots_signal=shots_signal,
            sot_signal=sot_signal,
            big_chances_signal=(
                big_chances_signal
            ),
        )

        # ----------------------------------------------------
        # OUTCOME
        # ----------------------------------------------------

        outcome_signal = goals_signal

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        momentum_signal = self._momentum(
            shots=shots,
            sot=sot,
            goals=goals,
        )

        # ----------------------------------------------------
        # VENUE
        # ----------------------------------------------------

        venue_signal = self._venue_signal(
            histories=histories,
            context=context,
        )

        # ----------------------------------------------------
        # DIAGNOSTIC STATE
        # ----------------------------------------------------

        stability = self._stability(
            histories
        )

        evidence_quality = (
            self._evidence_quality(
                histories
            )
        )

        # ----------------------------------------------------
        # DEFENSIVE SUB-STATES
        # ----------------------------------------------------

        defensive_creation_signal = (
            _combine_optional(
                (
                    (
                        xga_signal,
                        0.70,
                    ),
                    (
                        big_chances_signal,
                        0.30,
                    ),
                )
            )
        )

        defensive_control_signal = (
            _combine_optional(
                (
                    (
                        shots_signal,
                        0.60,
                    ),
                    (
                        sot_signal,
                        0.40,
                    ),
                )
            )
        )

        defensive_outcome_signal = (
            outcome_signal
        )

        defensive_momentum_signal = (
            momentum_signal
        )

        # ----------------------------------------------------
        # COMPATIBILITY AGGREGATE
        # ----------------------------------------------------
        #
        # This is deliberately retained for compatibility with
        # existing callers.
        #
        # It is NOT WinnerState.
        # It is NOT probability.
        # It must NOT override independent evidence.
        #

        defence_score = _combine_optional(
            (
                (
                    process_signal,
                    FINAL_WEIGHTS["process"],
                ),
                (
                    outcome_signal,
                    FINAL_WEIGHTS["outcome"],
                ),
                (
                    momentum_signal,
                    FINAL_WEIGHTS["momentum"],
                ),
                (
                    venue_signal,
                    FINAL_WEIGHTS["venue"],
                ),
            )
        )

        # ----------------------------------------------------
        # EVIDENCE VECTOR
        # ----------------------------------------------------

        evidence_vector = {
            "xga": xga_signal,
            "process": process_signal,
            "creation": (
                defensive_creation_signal
            ),
            "control": (
                defensive_control_signal
            ),
            "outcome": outcome_signal,
            "momentum": momentum_signal,
            "venue": venue_signal,
        }

        evidence_sources = [
            key
            for key, value
            in evidence_vector.items()
            if value is not None
        ]

        evidence_conflicts = (
            self._detect_conflicts(
                evidence_vector
            )
        )

        defensive_quality = (
            self._defensive_quality(
                evidence=evidence_vector,
                stability=stability,
                evidence_quality=(
                    evidence_quality
                ),
            )
        )

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        process_data_quality = _mean(
            (
                _availability(shots),
                _availability(sot),
                _availability(
                    big_chances
                ),
            )
        )

        creation_data_quality = _mean(
            (
                _availability(xga),
                _availability(
                    big_chances
                ),
            )
        )

        outcome_data_quality = (
            _availability(goals)
        )

        momentum_data_quality = _mean(
            (
                _availability(shots),
                _availability(sot),
                _availability(goals),
            )
        )

        # ----------------------------------------------------
        # SAMPLE SIZE
        # ----------------------------------------------------

        sample_size = self._sample_size(
            histories
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        signals = DefenceSignals(

            xga_signal=xga_signal,

            shots_conceded_signal=(
                shots_signal
            ),

            sot_conceded_signal=(
                sot_signal
            ),

            sot_volume_signal=(
                sot_volume_signal
            ),

            sot_rate_signal=(
                sot_rate_signal
            ),

            big_chances_signal=(
                big_chances_signal
            ),

            goals_conceded_signal=(
                goals_signal
            ),

            possession_signal=(
                possession_signal
            ),

            blocked_shots_signal=(
                blocked_signal
            ),

            blocked_rate_signal=None,

            woodwork_signal=(
                woodwork_signal
            ),

            dangerous_attacks_signal=(
                dangerous_attacks_signal
            ),

            attacks_signal=(
                attacks_signal
            ),

            defensive_creation_signal=(
                defensive_creation_signal
            ),

            defensive_control_signal=(
                defensive_control_signal
            ),

            defensive_outcome_signal=(
                defensive_outcome_signal
            ),

            defensive_momentum_signal=(
                defensive_momentum_signal
            ),

            venue_signal=venue_signal,
        )

        return DefenceState(

            version=DEFENCE_VERSION,

            team=team_name,

            signals=signals,

            process_signal=process_signal,

            outcome_signal=outcome_signal,

            momentum_signal=momentum_signal,

            venue_signal=venue_signal,

            stability=stability,

            evidence_quality=evidence_quality,

            defence_score=defence_score,

            sample_size=sample_size,

            available_xga=_valid_count(
                xga
            ),

            available_shots=_valid_count(
                shots
            ),

            available_sot=_valid_count(
                sot
            ),

            available_big_chances=(
                _valid_count(
                    big_chances
                )
            ),

            available_corners=_valid_count(
                corners
            ),

            available_goals=_valid_count(
                goals
            ),

            evidence_vector=evidence_vector,

            evidence_sources=(
                evidence_sources
            ),

            evidence_conflicts=(
                evidence_conflicts
            ),

            defensive_quality=(
                defensive_quality
            ),

            process_data_quality=(
                process_data_quality
            ),

            creation_data_quality=(
                creation_data_quality
            ),

            outcome_data_quality=(
                outcome_data_quality
            ),

            momentum_data_quality=(
                momentum_data_quality
            ),

            diagnostics={

                "version": DEFENCE_VERSION,

                "model_role": (
                    "defensive_evidence"
                ),

                # ------------------------------------------
                # Architecture
                # ------------------------------------------

                "winner_state_generated": False,

                "winner_direction_generated": False,

                "winner_probability_generated": False,

                "probability_generated": False,

                "poisson_used": False,

                "score_generated": False,

                "goalmodel_modified": False,

                "winner_override": False,

                # ------------------------------------------
                # Independence
                # ------------------------------------------

                "independent_from_goalmodel": True,

                "independent_from_probability": True,

                "independent_from_score": True,

                "independent_from_winner": True,

                "independent_from_confidence": True,

                "independent_from_risk": True,

                # ------------------------------------------
                # Mathematical boundaries
                # ------------------------------------------

                "xga_is_independent_evidence": True,

                "xga_used_in_process_signal": False,

                "xga_used_in_momentum_signal": False,

                "xga_used_in_venue_signal": False,

                "corners_used_in_process_signal": False,

                "corners_are_separate_state": True,

                # ------------------------------------------
                # Missing-data contract
                # ------------------------------------------

                "missing_is_zero": False,

                "missing_values_preserved": True,

                "available_samples_are_not_zero_filled": True,

                # ------------------------------------------
                # Prediction leakage
                # ------------------------------------------

                "future_result_used": False,

                "observed_result_as_prediction_input": False,

                "known_result_as_model_input": False,

                # ------------------------------------------
                # State semantics
                # ------------------------------------------

                "signals_are_evidence": True,

                "signals_are_probabilities": False,

                "defensive_quality_is_confidence": False,

                "stability_is_confidence": False,

                "defence_score_is_winner_prediction": False,

                "defence_score_is_compatibility_aggregate": True,

                # ------------------------------------------
                # Formula status
                # ------------------------------------------

                "contract": (
                    "MATHEMATICAL_CONTRACT_V1"
                ),

                "formula_status": (
                    "RESEARCH_FORMULA"
                ),

                "no_external_baseline": True,

                "no_league_strength": True,

                "no_rating_multiplier": True,

                "no_form_multiplier": True,

                "no_home_advantage_multiplier": True,

                "no_winner_signal_override": True,

                # ------------------------------------------
                # Evidence
                # ------------------------------------------

                "evidence_sources": (
                    evidence_sources
                ),

                "evidence_conflicts": (
                    evidence_conflicts
                ),

                # ------------------------------------------
                # Version history
                # ------------------------------------------

                "change_log": [

                    "v2.0: defensive evidence organ",

                    "v2.0: no WinnerState",

                    "v2.0: no probability",

                    "v2.0: no Poisson",

                    "v2.0: no GoalModel modification",

                    "v2.0: corners removed from core defence process",

                    "v2.0: corners remain separate-state evidence",

                    "v2.0: sample_size counts usable match positions",

                    "v2.0: None preserved for missing evidence",

                    "v2.0: no external defensive baseline",

                    "v2.0: independent defensive evidence blocks",

                    "v2.0: defence_score retained only for compatibility",
                ],
            },
        )

    # ========================================================
    # DICT API
    # ========================================================

    def calculate_dict(
        self,
        context: Any,
        *,
        team_name: Optional[str] = None,
    ) -> Dict[str, Any]:

        return asdict(
            self.calculate(
                context,
                team_name=team_name,
            )
        )

    # ========================================================
    # COMPARE
    # ========================================================

    def compare(
        self,
        home_context: Any,
        away_context: Any,
        *,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
    ) -> DefenceComparison:
        """
        Compare two independent Defence states.

        This method produces relative evidence only.

        It does NOT say:
            home wins,
            away wins,
            draw,
            probability.

        Winner synthesis belongs later.
        """

        home = self.calculate(
            home_context,
            team_name=home_team,
        )

        away = self.calculate(
            away_context,
            team_name=away_team,
        )

        def relative(
            home_value: Optional[float],
            away_value: Optional[float],
        ) -> Optional[float]:

            if (
                home_value is None
                or away_value is None
            ):
                return None

            return _clamp(
                home_value - away_value
            )

        relative_defence = relative(
            home.defence_score,
            away.defence_score,
        )

        relative_creation = relative(
            home.signals.defensive_creation_signal,
            away.signals.defensive_creation_signal,
        )

        relative_process = relative(
            home.process_signal,
            away.process_signal,
        )

        relative_control = relative(
            home.signals.defensive_control_signal,
            away.signals.defensive_control_signal,
        )

        relative_outcome = relative(
            home.outcome_signal,
            away.outcome_signal,
        )

        relative_momentum = relative(
            home.momentum_signal,
            away.momentum_signal,
        )

        sources = [
            name
            for name, value in (
                (
                    "defence",
                    relative_defence,
                ),
                (
                    "creation",
                    relative_creation,
                ),
                (
                    "process",
                    relative_process,
                ),
                (
                    "control",
                    relative_control,
                ),
                (
                    "outcome",
                    relative_outcome,
                ),
                (
                    "momentum",
                    relative_momentum,
                ),
            )
            if value is not None
        ]

        return DefenceComparison(

            home_defence=(
                home.defence_score
            ),

            away_defence=(
                away.defence_score
            ),

            relative_defence_advantage=(
                relative_defence
            ),

            home_state=home,

            away_state=away,

            relative_creation=(
                relative_creation
            ),

            relative_process=(
                relative_process
            ),

            relative_control=(
                relative_control
            ),

            relative_outcome=(
                relative_outcome
            ),

            relative_momentum=(
                relative_momentum
            ),

            evidence_sources=sources,
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        state: DefenceState,
    ) -> Dict[str, Any]:

        return asdict(state)


# ============================================================
# FUNCTIONAL API
# ============================================================

def calculate_defence(
    context: Any,
    *,
    team_name: Optional[str] = None,
) -> DefenceState:

    return Defence().calculate(
        context,
        team_name=team_name,
    )


def compare_defence(
    home_context: Any,
    away_context: Any,
    *,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
) -> DefenceComparison:

    return Defence().compare(
        home_context,
        away_context,
        home_team=home_team,
        away_team=away_team,
    )
