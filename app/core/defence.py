#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
DEFENCE v1.0
============================================================

МАТЕМАТИЧЕСКИЙ ОРГАН FAJ

Назначение
----------

Defence измеряет текущее оборонительное состояние команды.

Он отвечает на вопрос:

    Насколько команда сейчас способна ограничивать
    создание и реализацию опасных моментов соперника?

Defence НЕ:

    - прогнозирует счёт;
    - прогнозирует победу;
    - рассчитывает вероятность;
    - рассчитывает Poisson;
    - работает с SQLite;
    - обращается к Soccer365;
    - обращается к parser;
    - изменяет Rating;
    - изменяет Team Passport;
    - использует будущий результат;
    - использует bookmaker odds.

Архитектура:

    Match Facts
        ↓
    FormContext
        ↓
    Defence
        ↓
    DefenceState
        ↓
    FAJ Brain / GoalModel

Математический диапазон:

    DefenceScore ∈ [-1, +1]

    +1 = очень сильное оборонительное состояние
     0 = нейтральное состояние
    -1 = слабое оборонительное состояние
    None = недостаточно данных

ВАЖНО:

    None != 0

Отсутствующие наблюдения никогда не превращаются
в нулевые значения.

============================================================
MATHEMATICAL VERSION
============================================================

DEFENCE v1.0

Structural priors являются предварительной математической
иерархией и НЕ являются обученными коэффициентами.

Окончательная калибровка допускается только после
исторического backtesting.

============================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, tanh
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# VERSION
# ============================================================

DEFENCE_VERSION = "1.0"


# ============================================================
# RESEARCH / STRUCTURAL PRIORS
# ============================================================

TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)


# ------------------------------------------------------------
# Process hierarchy
# ------------------------------------------------------------

PROCESS_WEIGHTS = {
    "xga": 0.55,
    "shots": 0.20,
    "sot": 0.15,
    "big_chances": 0.07,
    "corners": 0.03,
}


# ------------------------------------------------------------
# SOT decomposition
# ------------------------------------------------------------

SOT_VOLUME_WEIGHT = 0.65
SOT_RATE_WEIGHT = 0.35


# ------------------------------------------------------------
# Final state
# ------------------------------------------------------------

FINAL_WEIGHTS = {
    "process": 0.65,
    "outcome": 0.10,
    "momentum": 0.15,
    "venue": 0.10,
}


# ------------------------------------------------------------
# Momentum
# ------------------------------------------------------------

MOMENTUM_WEIGHTS = {
    "xga": 0.50,
    "shots": 0.25,
    "sot": 0.15,
    "goals": 0.10,
}


# ------------------------------------------------------------
# Venue shrinkage
#
# alpha = n / (n + k)
#
# k is not home advantage.
# It is only shrinkage strength.
# ------------------------------------------------------------

VENUE_SHRINKAGE_K = 4.0


# ------------------------------------------------------------
# Bounded secondary signals
# ------------------------------------------------------------

BIG_CHANCES_CAP = 0.50
CORNERS_CAP = 0.40


EPSILON = 1e-9


# ============================================================
# GENERIC HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Safe numeric conversion.

    Missing / invalid / non-finite values remain None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(result):
        return None

    return result


def _get_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Unified access for:

        dict
        sqlite3.Row
        dataclass/object
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


def _clamp(
    value: float,
    low: float = -1.0,
    high: float = 1.0,
) -> float:
    """
    Restrict value to [low, high].
    """

    return max(
        low,
        min(high, value),
    )


def _mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:
    """
    Arithmetic mean over available observations only.
    """

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _median(
    values: Iterable[Optional[float]],
) -> Optional[float]:
    """
    Median over available observations only.
    """

    clean = [
        float(value)
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
    """
    Temporal weighted mean.

    None observations are removed together with their weights.
    """

    pairs: List[Tuple[float, float]] = []

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

    if denominator <= 0:
        return None

    numerator = sum(
        value * weight
        for value, weight in pairs
    )

    return numerator / denominator


def _mad(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Median Absolute Deviation.
    """

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    center = median(clean)

    deviations = [
        abs(value - center)
        for value in clean
    ]

    return float(
        median(deviations)
    )


def _robust_scale(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Robust scale:

        sigma_robust = 1.4826 * MAD

    If MAD is zero, a small deterministic fallback based
    on the data range is used.

    No missing value becomes zero.
    """

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if len(clean) < 2:
        return None

    mad = _mad(
        clean
    )

    if mad is not None and mad > EPSILON:

        return (
            1.4826 * mad
        )

    data_range = (
        max(clean) - min(clean)
    )

    if data_range > EPSILON:

        return data_range / 2.0

    return None


def _ols_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    OLS slope preserving temporal order.

    None observations are skipped.

    The temporal positions of available observations
    are preserved.
    """

    observations: List[Tuple[float, float]] = []

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

    x_values = [
        item[0]
        for item in observations
    ]

    y_values = [
        item[1]
        for item in observations
    ]

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)

    numerator = sum(
        (
            x - x_mean
        ) * (
            y - y_mean
        )
        for x, y in zip(
            x_values,
            y_values,
        )
    )

    denominator = sum(
        (
            x - x_mean
        ) ** 2
        for x in x_values
    )

    if denominator <= EPSILON:
        return None

    return numerator / denominator


# ============================================================
# NORMALIZATION
# ============================================================

def _inverse_state_signal(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Converts a defensive metric into [-1,+1].

    Higher metric value means worse defence.

    Therefore:

        below historical center → positive Defence
        above historical center → negative Defence

    Formula:

        center = median(history)

        scale = robust_scale(history)

        recent =
            weighted_mean(history)

        z =
            (recent - center) / scale

        signal =
            -tanh(z)
    """

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if len(clean) < 2:
        return None

    recent = _weighted_mean(
        values
    )

    center = _median(
        values
    )

    scale = _robust_scale(
        values
    )

    if (
        recent is None
        or center is None
        or scale is None
        or scale <= EPSILON
    ):
        return None

    return _clamp(
        -tanh(
            (recent - center)
            / scale
        )
    )


def _inverse_trend_signal(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Converts defensive OLS trend into [-1,+1].

    For defensive metrics:

        decreasing metric → positive signal
        increasing metric → negative signal
    """

    slope = _ols_slope(
        values
    )

    scale = _robust_scale(
        values
    )

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
    """
    Restrict an existing [-1,+1] signal
    to [-cap,+cap].
    """

    if value is None:
        return None

    return max(
        -cap,
        min(cap, value),
    )


def _combine_optional(
    components: Sequence[
        Tuple[
            Optional[float],
            float,
        ]
    ],
) -> Optional[float]:
    """
    Weighted combination of available components.

    Missing components are removed together with their weight.
    """

    available = [
        (
            value,
            weight,
        )
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

    numerator = sum(
        value * weight
        for value, weight in available
    )

    return _clamp(
        numerator / denominator
    )


# ============================================================
# HISTORY EXTRACTION
# ============================================================

def _extract_history(
    context: Any,
    *names: str,
) -> List[Optional[float]]:
    """
    Extract numeric history from FormContext.

    Supports multiple compatible field names.

    None remains None.
    """

    for name in names:

        value = _get_value(
            context,
            name,
        )

        if value is None:
            continue

        if isinstance(
            value,
            (list, tuple),
        ):

            result: List[
                Optional[float]
            ] = []

            for item in value:

                result.append(
                    _safe_float(item)
                )

            return result

    return []


def _extract_results(
    context: Any,
) -> List[Optional[str]]:
    """
    Extract W/D/L history.
    """

    for name in (
        "results_history",
        "result_history",
        "results",
    ):

        value = _get_value(
            context,
            name,
        )

        if not isinstance(
            value,
            (list, tuple),
        ):
            continue

        result: List[
            Optional[str]
        ] = []

        for item in value:

            if item is None:

                result.append(
                    None
                )

                continue

            text = (
                str(item)
                .strip()
                .upper()
            )

            mapping = {
                "В": "W",
                "Н": "D",
                "П": "L",
            }

            if text in mapping:

                result.append(
                    mapping[text]
                )

            elif text in {
                "W",
                "D",
                "L",
            }:

                result.append(
                    text
                )

            else:

                result.append(
                    None
                )

        return result

    return []


def _extract_venues(
    context: Any,
) -> List[Optional[str]]:
    """
    Extract venue history.
    """

    for name in (
        "venue_history",
        "venues",
    ):

        value = _get_value(
            context,
            name,
        )

        if not isinstance(
            value,
            (list, tuple),
        ):
            continue

        result: List[
            Optional[str]
        ] = []

        for item in value:

            if item is None:

                result.append(
                    None
                )

            else:

                result.append(
                    str(item)
                    .strip()
                    .lower()
                )

        return result

    return []


# ============================================================
# RESULT DATACLASSES
# ============================================================

@dataclass
class DefenceSignals:
    """
    Individual defensive diagnostic signals.
    """

    xga_signal: Optional[float] = None

    shots_conceded_signal: Optional[float] = None

    sot_conceded_signal: Optional[float] = None

    sot_volume_signal: Optional[float] = None

    sot_rate_signal: Optional[float] = None

    big_chances_signal: Optional[float] = None

    corners_conceded_signal: Optional[float] = None

    goals_conceded_signal: Optional[float] = None

    possession_signal: Optional[float] = None

    blocked_shots_signal: Optional[float] = None

    blocked_rate_signal: Optional[float] = None

    woodwork_signal: Optional[float] = None

    dangerous_attacks_signal: Optional[float] = None

    attacks_signal: Optional[float] = None

    defensive_creation_signal: Optional[float] = None

    defensive_control_signal: Optional[float] = None

    defensive_outcome_signal: Optional[float] = None

    defensive_momentum_signal: Optional[float] = None

    venue_signal: Optional[float] = None


@dataclass
class DefenceState:
    """
    Complete mathematical state of one team's defence.
    """

    version: str

    team: Optional[str]

    signals: DefenceSignals

    process_signal: Optional[float]

    outcome_signal: Optional[float]

    momentum_signal: Optional[float]

    venue_signal: Optional[float]

    stability: Optional[float]

    evidence_quality: float

    defence_score: Optional[float]

    sample_size: int

    available_xga: int

    available_shots: int

    available_sot: int

    available_big_chances: int

    available_corners: int

    available_goals: int

    diagnostics: Dict[str, Any]


@dataclass
class DefenceComparison:
    """
    Relative defensive comparison.
    """

    home_defence: Optional[float]

    away_defence: Optional[float]

    relative_defence_advantage: Optional[float]

    home_state: Optional[DefenceState] = None

    away_state: Optional[DefenceState] = None


# ============================================================
# DEFENCE MODEL
# ============================================================

class Defence:
    """
    Mathematical defensive state model.

    The model receives FormContext and produces DefenceState.

    It does not access external data.
    """

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
    # INTERNAL HISTORY
    # ========================================================

    def _histories(
        self,
        context: Any,
    ) -> Dict[
        str,
        List[Optional[float]],
    ]:
        """
        Extract all histories needed by Defence.

        Multiple aliases are supported to preserve
        compatibility with existing FormContext variants.
        """

        return {

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
        shots: Sequence[
            Optional[float]
        ],
        sot: Sequence[
            Optional[float]
        ],
    ) -> Tuple[
        Optional[float],
        Optional[float],
        Optional[float],
    ]:
        """
        Calculate:

            SOT volume
            SOT rate
            combined SOT signal

        Rate is only calculated when both
        shots and SOT are available.
        """

        sot_volume_signal = (
            _inverse_state_signal(
                sot
            )
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
            ):

                rate_history.append(
                    None
                )

                continue

            if shots_value <= EPSILON:

                rate_history.append(
                    None
                )

                continue

            rate = (
                sot_value
                / shots_value
            )

            rate_history.append(
                rate
            )

        sot_rate_signal = (
            _inverse_state_signal(
                rate_history
            )
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
    # BLOCKED SHOTS
    # ========================================================

    def _blocked_diagnostics(
        self,
        shots: Sequence[
            Optional[float]
        ],
        blocked: Sequence[
            Optional[float]
        ],
    ) -> Tuple[
        Optional[float],
        Optional[float],
    ]:
        """
        Blocked shots are diagnostic only.

        They are deliberately excluded from the main
        DefenceScore because the direction is ambiguous.

        We calculate the rate for auditing.
        """

        blocked_signal = None

        blocked_rate_history: List[
            Optional[float]
        ] = []

        for shots_value, blocked_value in zip(
            shots,
            blocked,
        ):

            if (
                shots_value is None
                or blocked_value is None
                or shots_value <= EPSILON
            ):

                blocked_rate_history.append(
                    None
                )

                continue

            blocked_rate_history.append(
                blocked_value
                / shots_value
            )

        blocked_rate_signal = (
            _inverse_state_signal(
                blocked_rate_history
            )
        )

        return (
            blocked_signal,
            blocked_rate_signal,
        )

    # ========================================================
    # PROCESS
    # ========================================================

    def _process_signal(
        self,
        *,
        xga_signal: Optional[float],
        shots_signal: Optional[float],
        sot_signal: Optional[float],
        big_chances_signal: Optional[float],
        corners_signal: Optional[float],
    ) -> Optional[float]:
        """
        Defensive process signal.

        Structural hierarchy:

            xGA       55%
            shots     20%
            SOT       15%
            big       7%
            corners   3%

        Missing components are excluded together with
        their weights.
        """

        big_chances_signal = _bounded(
            big_chances_signal,
            BIG_CHANCES_CAP,
        )

        corners_signal = _bounded(
            corners_signal,
            CORNERS_CAP,
        )

        return _combine_optional(
            (
                (
                    xga_signal,
                    PROCESS_WEIGHTS["xga"],
                ),
                (
                    shots_signal,
                    PROCESS_WEIGHTS["shots"],
                ),
                (
                    sot_signal,
                    PROCESS_WEIGHTS["sot"],
                ),
                (
                    big_chances_signal,
                    PROCESS_WEIGHTS["big_chances"],
                ),
                (
                    corners_signal,
                    PROCESS_WEIGHTS["corners"],
                ),
            )
        )

    # ========================================================
    # MOMENTUM
    # ========================================================

    def _momentum(
        self,
        *,
        xga: Sequence[
            Optional[float]
        ],
        shots: Sequence[
            Optional[float]
        ],
        sot: Sequence[
            Optional[float]
        ],
        goals: Sequence[
            Optional[float]
        ],
    ) -> Optional[float]:
        """
        Defensive momentum.

        Decreasing xGA / shots / SOT / goals means
        improving defensive state.

        Momentum is a state-change signal,
        not a second Defence score.
        """

        xga_trend = _inverse_trend_signal(
            xga
        )

        shots_trend = _inverse_trend_signal(
            shots
        )

        sot_trend = _inverse_trend_signal(
            sot
        )

        goals_trend = _inverse_trend_signal(
            goals
        )

        return _combine_optional(
            (
                (
                    xga_trend,
                    MOMENTUM_WEIGHTS["xga"],
                ),
                (
                    shots_trend,
                    MOMENTUM_WEIGHTS["shots"],
                ),
                (
                    sot_trend,
                    MOMENTUM_WEIGHTS["sot"],
                ),
                (
                    goals_trend,
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
        """
        Stability of the observed defensive state.

        Uses the coefficient of variation across
        the main defensive process indicators.

        Stability does NOT directly add points.
        """

        cv_values: List[float] = []

        for key in (
            "xga",
            "shots",
            "sot",
            "big_chances",
        ):

            values = [
                value
                for value in histories.get(
                    key,
                    [],
                )
                if value is not None
            ]

            if len(values) < 2:
                continue

            mean_value = (
                sum(values)
                / len(values)
            )

            if abs(mean_value) <= EPSILON:
                continue

            scale = _robust_scale(
                values
            )

            if scale is None:
                continue

            cv = (
                scale
                / abs(mean_value)
            )

            cv_values.append(
                cv
            )

        if not cv_values:
            return None

        average_cv = (
            sum(cv_values)
            / len(cv_values)
        )

        stability = (
            1.0
            / (
                1.0
                + average_cv
            )
        )

        return max(
            0.0,
            min(1.0, stability),
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
        Venue-specific defensive signal.

        The venue subset is shrunk toward the general
        defensive state.

            alpha = n / (n + k)

        where k = VENUE_SHRINKAGE_K.
        """

        venue_history = _extract_venues(
            context
        )

        xga_history = histories.get(
            "xga",
            [],
        )

        if not venue_history:
            return None

        target_venue = _get_value(
            context,
            "current_venue",
            "venue",
            "match_venue",
        )

        if target_venue is None:
            return None

        target = (
            str(target_venue)
            .strip()
            .lower()
        )

        if target not in {
            "home",
            "away",
            "дома",
            "гости",
            "h",
            "a",
        }:
            return None

        if target in {
            "home",
            "дома",
            "h",
        }:
            aliases = {
                "home",
                "дома",
                "h",
            }
        else:
            aliases = {
                "away",
                "гости",
                "a",
            }

        venue_values: List[
            Optional[float]
        ] = []

        for venue, value in zip(
            venue_history,
            xga_history,
        ):

            if (
                venue in aliases
                and value is not None
            ):

                venue_values.append(
                    value
                )

        if len(venue_values) < 1:
            return None

        general_signal = (
            _inverse_state_signal(
                xga_history
            )
        )

        venue_signal_raw = (
            _inverse_state_signal(
                venue_values
            )
        )

        if venue_signal_raw is None:
            return None

        n = len(venue_values)

        alpha = (
            n
            / (
                n
                + VENUE_SHRINKAGE_K
            )
        )

        if general_signal is None:
            return _clamp(
                venue_signal_raw
                * alpha
            )

        return _clamp(
            alpha * venue_signal_raw
            + (
                1.0 - alpha
            ) * general_signal
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
    ) -> float:
        """
        Weighted completeness of the evidence base.

        xGA receives the highest importance because it is
        the primary defensive process metric.

        This measures data availability, not model confidence.
        """

        importance = {
            "xga": 0.55,
            "shots": 0.20,
            "sot": 0.15,
            "big_chances": 0.07,
            "corners": 0.03,
        }

        numerator = 0.0
        denominator = 0.0

        for key, weight in importance.items():

            values = histories.get(
                key,
                [],
            )

            if not values:
                continue

            availability = (
                sum(
                    1
                    for value in values
                    if value is not None
                )
                / len(values)
            )

            numerator += (
                availability
                * weight
            )

            denominator += weight

        if denominator <= EPSILON:
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                numerator / denominator,
            ),
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def calculate(
        self,
        context: Any,
        *,
        team_name: Optional[str] = None,
    ) -> DefenceState:
        """
        Calculate defensive state from FormContext.

        No external data access is performed.
        """

        histories = self._histories(
            context
        )

        xga = histories["xga"]
        shots = histories["shots"]
        sot = histories["sot"]
        blocked = histories["blocked"]
        woodwork = histories["woodwork"]
        corners = histories["corners"]
        big_chances = histories["big_chances"]
        goals = histories["goals"]
        possession = histories[
            "possession_opponent"
        ]
        attacks = histories["attacks"]
        dangerous_attacks = histories[
            "dangerous_attacks"
        ]

        # ----------------------------------------------------
        # Primary defensive signals
        # ----------------------------------------------------

        xga_signal = (
            _inverse_state_signal(
                xga
            )
        )

        shots_signal = (
            _inverse_state_signal(
                shots
            )
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

        corners_signal = (
            _inverse_state_signal(
                corners
            )
        )

        goals_signal = (
            _inverse_state_signal(
                goals
            )
        )

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        (
            blocked_signal,
            blocked_rate_signal,
        ) = self._blocked_diagnostics(
            shots,
            blocked,
        )

        # Woodwork deliberately remains diagnostic only.
        woodwork_signal = None

        # Possession is contextual and not part of the
        # primary defensive score.
        possession_signal = (
            _inverse_state_signal(
                possession
            )
        )

        attacks_signal = (
            _inverse_state_signal(
                attacks
            )
        )

        dangerous_attacks_signal = (
            _inverse_state_signal(
                dangerous_attacks
            )
        )

        # ----------------------------------------------------
        # Process
        # ----------------------------------------------------

        process_signal = (
            self._process_signal(
                xga_signal=xga_signal,
                shots_signal=shots_signal,
                sot_signal=sot_signal,
                big_chances_signal=big_chances_signal,
                corners_signal=corners_signal,
            )
        )

        # ----------------------------------------------------
        # Outcome
        # ----------------------------------------------------

        outcome_signal = (
            goals_signal
        )

        # ----------------------------------------------------
        # Momentum
        # ----------------------------------------------------

        momentum_signal = (
            self._momentum(
                xga=xga,
                shots=shots,
                sot=sot,
                goals=goals,
            )
        )

        # ----------------------------------------------------
        # Venue
        # ----------------------------------------------------

        venue_signal = (
            self._venue_signal(
                histories=histories,
                context=context,
            )
        )

        # ----------------------------------------------------
        # Stability
        # ----------------------------------------------------

        stability = (
            self._stability(
                histories
            )
        )

        # ----------------------------------------------------
        # Evidence
        # ----------------------------------------------------

        evidence_quality = (
            self._evidence_quality(
                histories
            )
        )

        # ----------------------------------------------------
        # Final score
        # ----------------------------------------------------

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
        # Diagnostic signal groups
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

        signals = DefenceSignals(
            xga_signal=xga_signal,

            shots_conceded_signal=shots_signal,

            sot_conceded_signal=sot_signal,

            sot_volume_signal=sot_volume_signal,

            sot_rate_signal=sot_rate_signal,

            big_chances_signal=big_chances_signal,

            corners_conceded_signal=corners_signal,

            goals_conceded_signal=goals_signal,

            possession_signal=possession_signal,

            blocked_shots_signal=blocked_signal,

            blocked_rate_signal=blocked_rate_signal,

            woodwork_signal=woodwork_signal,

            dangerous_attacks_signal=(
                dangerous_attacks_signal
            ),

            attacks_signal=attacks_signal,

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

        sample_size = max(
            len(xga),
            len(shots),
            len(sot),
            len(goals),
            len(corners),
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

            available_xga=sum(
                value is not None
                for value in xga
            ),

            available_shots=sum(
                value is not None
                for value in shots
            ),

            available_sot=sum(
                value is not None
                for value in sot
            ),

            available_big_chances=sum(
                value is not None
                for value in big_chances
            ),

            available_corners=sum(
                value is not None
                for value in corners
            ),

            available_goals=sum(
                value is not None
                for value in goals
            ),

            diagnostics={
                "blocked_shots_are_diagnostic_only": True,
                "woodwork_is_diagnostic_only": True,
                "possession_is_contextual_only": True,
                "dangerous_attacks_are_diagnostic_only": True,
                "attacks_are_diagnostic_only": True,
                "temporal_weights": list(
                    self.temporal_weights
                ),
                "process_weights": dict(
                    PROCESS_WEIGHTS
                ),
                "final_weights": dict(
                    FINAL_WEIGHTS
                ),
                "momentum_weights": dict(
                    MOMENTUM_WEIGHTS
                ),
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
        """
        Calculate and return a serializable dictionary.
        """

        state = self.calculate(
            context,
            team_name=team_name,
        )

        return asdict(
            state
        )

    # ========================================================
    # COMPARISON
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
        Compare defensive states of two teams.

        The comparison is purely relative and is NOT
        a probability.
        """

        home_state = self.calculate(
            home_context,
            team_name=home_team,
        )

        away_state = self.calculate(
            away_context,
            team_name=away_team,
        )

        home_score = (
            home_state.defence_score
        )

        away_score = (
            away_state.defence_score
        )

        if (
            home_score is None
            or away_score is None
        ):

            relative = None

        else:

            relative = _clamp(
                home_score
                - away_score
            )

        return DefenceComparison(
            home_defence=home_score,

            away_defence=away_score,

            relative_defence_advantage=relative,

            home_state=home_state,

            away_state=away_state,
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        state: DefenceState,
    ) -> Dict[str, Any]:
        """
        Convert DefenceState into a dictionary.
        """

        return asdict(
            state
        )


# ============================================================
# FUNCTIONAL API
# ============================================================

def calculate_defence(
    context: Any,
    *,
    team_name: Optional[str] = None,
) -> DefenceState:
    """
    Functional convenience API.
    """

    model = Defence()

    return model.calculate(
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
    """
    Functional comparison API.
    """

    model = Defence()

    return model.compare(
        home_context,
        away_context,
        home_team=home_team,
        away_team=away_team,
    )
