#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM WIN v1.1
============================================================

МАТЕМАТИЧЕСКИЙ ОРГАН FAJ

Назначение
----------

FormWin измеряет совокупное состояние команды,
связанное с предпосылками к победе.

FormWin НЕ:

    - прогнозирует счёт;
    - рассчитывает Poisson;
    - рассчитывает вероятность победы;
    - работает с bookmaker odds;
    - обращается к SQLite;
    - обращается к Soccer365;
    - изменяет Rating;
    - изменяет Team Passport;
    - использует будущий результат;
    - обучается на одном матче.

Архитектура:

    FormContext
        ↓
    FormWin
        ↓
    TeamFormWin
        ↓
    FormWinComparison
        ↓
    FormModel / GoalModel / Brain

Главный принцип:

    FACT
       ↓
    NORMALIZATION
       ↓
    SEMANTIC SIGNAL
       ↓
    COMPONENT
       ↓
    FORM WIN

Никаких magic bonuses.

============================================================
MATHEMATICAL CONTRACT
============================================================

Все индивидуальные сигналы находятся в [-1, +1].

0
    нормальное / нейтральное состояние

+1
    сильное положительное состояние

-1
    сильное отрицательное состояние

None
    недостаточно данных

Missing никогда не превращается в zero.

Woodwork не используется как самостоятельный
положительный или отрицательный фактор,
поскольку он уже является частью Shots.

============================================================
VERSION
============================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp, isfinite, sqrt, tanh
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


FORM_WIN_VERSION = "1.1"


# ============================================================
# RESEARCH PARAMETERS
# ============================================================

# История FormContext:
#
# M1 = oldest
# M6 = newest
#
# Последние матчи получают больший вес.
TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)


# ------------------------------------------------------------
# Structural priors.
#
# Это НЕ обученные коэффициенты.
#
# Они отражают иерархию футбольных сигналов до проведения
# исторической калибровки.
#
# После backtesting могут быть заменены только на основании
# исторических данных.
# ------------------------------------------------------------

ATTACK_WEIGHTS = {
    "xg": 0.40,
    "sot": 0.20,
    "shots": 0.15,
    "blocked": 0.05,
    "crosses": 0.05,
    "corners": 0.15,
}

CONTROL_WEIGHTS = {
    "possession": 0.60,
    "passes": 0.20,
    "pass_accuracy": 0.20,
}

FINAL_WEIGHTS = {
    "attack": 0.50,
    "control": 0.10,
    "outcome": 0.15,
    "momentum": 0.15,
    "venue": 0.10,
}


# SOT rate состоит из объёма SOT и accuracy.
SOT_VOLUME_WEIGHT = 0.65
SOT_RATE_WEIGHT = 0.35

# Passes + accuracy образуют единый control sub-factor.
PASS_VOLUME_WEIGHT = 0.50
PASS_ACCURACY_WEIGHT = 0.50

# Momentum.
MOMENTUM_WEIGHTS = {
    "xg_trend": 0.40,
    "xga_trend": -0.30,
    "shots_trend": 0.15,
    "sot_trend": 0.10,
    "result_trend": 0.05,
}


# Venue shrinkage.
#
# alpha = n_venue / (n_venue + k)
#
# k не является "силой home advantage".
# Это только параметр shrinkage.
VENUE_SHRINKAGE_K = 4.0


# Небольшая защита от деления на ноль.
EPSILON = 1e-9


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Safe numeric conversion.

    Missing / invalid values remain None.
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
    return max(low, min(high, value))


def _mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _weighted_mean(
    values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Weighted mean preserving temporal position.

    None observation is excluded together with its weight.
    """

    pairs = []

    for value, weight in zip(values, weights):

        if value is None:
            continue

        numeric = _safe_float(value)

        if numeric is None:
            continue

        pairs.append(
            (numeric, float(weight))
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


def _population_std(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    mean = sum(clean) / len(clean)

    variance = sum(
        (value - mean) ** 2
        for value in clean
    ) / len(clean)

    return sqrt(variance)


def _ols_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    OLS slope.

    None observations are excluded.

    Returned slope remains in the original units.
    """

    observations = [
        float(value)
        for value in values
        if value is not None
    ]

    n = len(observations)

    if n < 2:
        return None

    x = list(range(n))

    x_mean = sum(x) / n
    y_mean = sum(observations) / n

    numerator = sum(
        (xi - x_mean) * (yi - y_mean)
        for xi, yi in zip(x, observations)
    )

    denominator = sum(
        (xi - x_mean) ** 2
        for xi in x
    )

    if denominator <= 0:
        return None

    return numerator / denominator


def _bounded_deviation(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Converts a time-series state into [-1,+1].

    Recent weighted mean is compared with the historical
    center.

    Scale is derived from the series itself.

    No arbitrary football coefficient is introduced.
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

    if recent is None:
        return None

    center = median(clean)

    scale = _population_std(
        clean
    )

    if scale is None or scale < EPSILON:

        if abs(recent - center) < EPSILON:
            return 0.0

        # Если показатель постоянен, любое отличие
        # невозможно статистически оценить.
        return None

    return _clamp(
        tanh(
            (recent - center)
            / scale
        )
    )


def _bounded_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Converts OLS trend into [-1,+1].

    Scale comes from historical volatility.
    """

    slope = _ols_slope(values)

    if slope is None:
        return None

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    scale = _population_std(clean)

    if scale is None or scale < EPSILON:
        return None

    return _clamp(
        tanh(
            slope / scale
        )
    )


def _safe_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
) -> Optional[float]:

    if numerator is None:
        return None

    if denominator is None:
        return None

    if abs(denominator) < EPSILON:
        return None

    return numerator / denominator


def _weighted_result_mean(
    results: Sequence[Optional[str]],
) -> Optional[float]:
    """
    W = +1
    D = 0
    L = -1
    """

    values = []

    for result in results:

        if result == "W":
            values.append(1.0)

        elif result == "D":
            values.append(0.0)

        elif result == "L":
            values.append(-1.0)

        else:
            values.append(None)

    return _weighted_mean(
        values
    )


def _availability(
    values: Sequence[Optional[float]],
) -> float:

    if not values:
        return 0.0

    available = sum(
        1
        for value in values
        if value is not None
    )

    return available / len(values)


def _combine_optional(
    components: Sequence[Tuple[Optional[float], float]],
) -> Optional[float]:
    """
    Weighted combination.

    Missing components are removed together with their weights.

    This is important:

        missing xG
        !=
        xG = 0
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

    if denominator <= 0:
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
    names: Sequence[str],
) -> List[Optional[float]]:
    """
    Extract a history from FormContext.

    Supports both:

        *_history

    and possible legacy names.

    Missing fields remain None.
    """

    for name in names:

        value = _get_value(
            context,
            name,
        )

        if value is None:
            continue

        if isinstance(value, (list, tuple)):

            result = []

            for item in value:
                result.append(
                    _safe_float(item)
                )

            return result

    return []


def _extract_results(
    context: Any,
) -> List[Optional[str]]:

    for name in (
        "results_history",
        "result_history",
        "results",
    ):

        value = _get_value(
            context,
            name,
        )

        if value is None:
            continue

        if isinstance(value, (list, tuple)):

            result = []

            for item in value:

                if item is None:
                    result.append(None)
                    continue

                text = str(item).strip().upper()

                if text in {
                    "W",
                    "D",
                    "L",
                }:
                    result.append(text)

                elif text in {
                    "В",
                    "Н",
                    "П",
                }:

                    mapping = {
                        "В": "W",
                        "Н": "D",
                        "П": "L",
                    }

                    result.append(
                        mapping[text]
                    )

                else:
                    result.append(None)

            return result

    return []


def _extract_venues(
    context: Any,
) -> List[Optional[str]]:

    for name in (
        "venue_history",
        "venues",
    ):

        value = _get_value(
            context,
            name,
        )

        if isinstance(value, (list, tuple)):

            return [
                (
                    str(item).strip().lower()
                    if item is not None
                    else None
                )
                for item in value
            ]

    return []


# ============================================================
# DATA CONTAINER
# ============================================================

@dataclass
class FormWinSignals:
    """
    Diagnostic individual signals.
    """

    xg_signal: Optional[float] = None
    sot_signal: Optional[float] = None
    sot_volume_signal: Optional[float] = None
    sot_rate_signal: Optional[float] = None

    shots_signal: Optional[float] = None
    blocked_signal: Optional[float] = None
    crosses_signal: Optional[float] = None
    corners_signal: Optional[float] = None

    possession_signal: Optional[float] = None
    passes_signal: Optional[float] = None
    pass_accuracy_signal: Optional[float] = None

    attack_signal: Optional[float] = None
    control_signal: Optional[float] = None

    outcome_signal: Optional[float] = None
    momentum_signal: Optional[float] = None
    venue_signal: Optional[float] = None

    xg_trend: Optional[float] = None
    xga_trend: Optional[float] = None
    shots_trend: Optional[float] = None
    sot_trend: Optional[float] = None
    result_trend: Optional[float] = None


@dataclass
class TeamFormWin:
    """
    Complete internal FormWin state.
    """

    version: str

    team: Optional[str]

    matches_count: int

    attack_signal: Optional[float]
    control_signal: Optional[float]
    outcome_signal: Optional[float]
    momentum_signal: Optional[float]
    venue_signal: Optional[float]

    stability: Optional[float]
    evidence_quality: float

    win_form_score: Optional[float]

    signals: FormWinSignals

    diagnostics: Dict[str, Any]


@dataclass
class FormWinComparison:
    """
    Relative FormWin state for two teams.

    This is still NOT a probability.
    """

    version: str

    home_team: Optional[str]
    away_team: Optional[str]

    home: TeamFormWin
    away: TeamFormWin

    relative_advantage: Optional[float]

    home_advantage: Optional[float]
    away_advantage: Optional[float]

    evidence_quality: float

    diagnostics: Dict[str, Any]


# ============================================================
# FORM WIN ENGINE
# ============================================================

class FormWin:
    """
    FAJ FormWin mathematical engine.

    Input:
        existing FormContext

    Output:
        TeamFormWin
        FormWinComparison

    No database access.
    No network access.
    No future result.
    No bookmaker data.
    """

    # ========================================================
    # PUBLIC API
    # ========================================================

    def analyze(
        self,
        form_context: Any,
        next_venue: Optional[str] = None,
    ) -> TeamFormWin:
        """
        Analyze one team's historical state.
        """

        team = _get_value(
            form_context,
            "team",
            "team_name",
        )

        results = _extract_results(
            form_context
        )

        venues = _extract_venues(
            form_context
        )

        xg = _extract_history(
            form_context,
            (
                "team_xg_history",
                "xg_history",
                "recent_xg",
            ),
        )

        xga = _extract_history(
            form_context,
            (
                "opponent_xg_history",
                "xga_history",
                "recent_xga",
            ),
        )

        shots = _extract_history(
            form_context,
            (
                "shots_history",
                "team_shots_history",
                "recent_shots",
            ),
        )

        sot = _extract_history(
            form_context,
            (
                "shots_on_target_history",
                "sot_history",
                "team_sot_history",
                "recent_shots_on_target",
            ),
        )

        blocked = _extract_history(
            form_context,
            (
                "blocked_shots_history",
                "team_blocked_shots_history",
                "recent_blocked_shots",
            ),
        )

        crosses = _extract_history(
            form_context,
            (
                "crosses_history",
                "team_crosses_history",
                "recent_crosses",
            ),
        )

        corners = _extract_history(
            form_context,
            (
                "corners_for_history",
                "team_corners_history",
                "corners_history",
            ),
        )

        possession = _extract_history(
            form_context,
            (
                "possession_history",
                "team_possession_history",
                "recent_possession",
            ),
        )

        passes = _extract_history(
            form_context,
            (
                "total_passes_history",
                "passes_history",
                "team_total_passes_history",
                "recent_total_passes",
            ),
        )

        pass_accuracy = _extract_history(
            form_context,
            (
                "pass_accuracy_history",
                "team_pass_accuracy_history",
                "recent_pass_accuracy",
            ),
        )

        # ----------------------------------------------------
        # Individual signals
        # ----------------------------------------------------

        signals = FormWinSignals()

        signals.xg_signal = _bounded_deviation(xg)

        # ----------------------------------------------------
        # Shots
        # ----------------------------------------------------

        signals.shots_signal = _bounded_deviation(
            shots
        )

        # ----------------------------------------------------
        # SOT
        # ----------------------------------------------------

        signals.sot_volume_signal = _bounded_deviation(
            sot
        )

        sot_rates = []

        for sot_value, shots_value in zip(
            sot,
            shots,
        ):

            ratio = _safe_ratio(
                sot_value,
                shots_value,
            )

            sot_rates.append(
                ratio
            )

        signals.sot_rate_signal = _bounded_deviation(
            sot_rates
        )

        signals.sot_signal = _combine_optional(
            (
                (
                    signals.sot_volume_signal,
                    SOT_VOLUME_WEIGHT,
                ),
                (
                    signals.sot_rate_signal,
                    SOT_RATE_WEIGHT,
                ),
            )
        )

        # ----------------------------------------------------
        # Blocked shots
        # ----------------------------------------------------
        #
        # Important:
        #
        # blocked shots are NOT a direct penalty.
        #
        # Only blocked/shots rate is considered as a small
        # corrective signal inside attack creation.
        # ----------------------------------------------------

        blocked_rates = []

        for blocked_value, shots_value in zip(
            blocked,
            shots,
        ):

            ratio = _safe_ratio(
                blocked_value,
                shots_value,
            )

            blocked_rates.append(
                ratio
            )

        blocked_state = _bounded_deviation(
            blocked_rates
        )

        if blocked_state is not None:
            signals.blocked_signal = _clamp(
                -0.25 * blocked_state
            )
        else:
            signals.blocked_signal = None

        # ----------------------------------------------------
        # Crosses
        # ----------------------------------------------------

        signals.crosses_signal = _bounded_deviation(
            crosses
        )

        # ----------------------------------------------------
        # Corners
        # ----------------------------------------------------

        signals.corners_signal = _bounded_deviation(
            corners
        )

        # ----------------------------------------------------
        # Attack
        # ----------------------------------------------------

        signals.attack_signal = _combine_optional(
            (
                (
                    signals.xg_signal,
                    ATTACK_WEIGHTS["xg"],
                ),
                (
                    signals.sot_signal,
                    ATTACK_WEIGHTS["sot"],
                ),
                (
                    signals.shots_signal,
                    ATTACK_WEIGHTS["shots"],
                ),
                (
                    signals.blocked_signal,
                    ATTACK_WEIGHTS["blocked"],
                ),
                (
                    signals.crosses_signal,
                    ATTACK_WEIGHTS["crosses"],
                ),
                (
                    signals.corners_signal,
                    ATTACK_WEIGHTS["corners"],
                ),
            )
        )

        # ----------------------------------------------------
        # CONTROL
        # ----------------------------------------------------

        signals.possession_signal = _bounded_deviation(
            possession
        )

        signals.passes_signal = _bounded_deviation(
            passes
        )

        signals.pass_accuracy_signal = _bounded_deviation(
            pass_accuracy
        )

        pass_control = _combine_optional(
            (
                (
                    signals.passes_signal,
                    PASS_VOLUME_WEIGHT,
                ),
                (
                    signals.pass_accuracy_signal,
                    PASS_ACCURACY_WEIGHT,
                ),
            )
        )

        # ----------------------------------------------------
        # Possession must not automatically mean attack.
        #
        # It is therefore used as control, not as an
        # independent goal signal.
        # ----------------------------------------------------

        signals.control_signal = _combine_optional(
            (
                (
                    signals.possession_signal,
                    CONTROL_WEIGHTS["possession"],
                ),
                (
                    pass_control,
                    CONTROL_WEIGHTS["passes"]
                    + CONTROL_WEIGHTS["pass_accuracy"],
                ),
            )
        )

        # ----------------------------------------------------
        # OUTCOME
        # ----------------------------------------------------

        signals.outcome_signal = _weighted_result_mean(
            results
        )

        # ----------------------------------------------------
        # MOMENTUM
        # ----------------------------------------------------

        signals.xg_trend = _bounded_slope(
            xg
        )

        signals.xga_trend = _bounded_slope(
            xga
        )

        signals.shots_trend = _bounded_slope(
            shots
        )

        signals.sot_trend = _bounded_slope(
            sot
        )

        result_numeric = []

        for result in results:

            if result == "W":
                result_numeric.append(1.0)

            elif result == "D":
                result_numeric.append(0.0)

            elif result == "L":
                result_numeric.append(-1.0)

            else:
                result_numeric.append(None)

        signals.result_trend = _bounded_slope(
            result_numeric
        )

        signals.momentum_signal = _combine_optional(
            (
                (
                    signals.xg_trend,
                    MOMENTUM_WEIGHTS["xg_trend"],
                ),
                (
                    signals.xga_trend,
                    MOMENTUM_WEIGHTS["xga_trend"],
                ),
                (
                    signals.shots_trend,
                    MOMENTUM_WEIGHTS["shots_trend"],
                ),
                (
                    signals.sot_trend,
                    MOMENTUM_WEIGHTS["sot_trend"],
                ),
                (
                    signals.result_trend,
                    MOMENTUM_WEIGHTS["result_trend"],
                ),
            )
        )

        # ----------------------------------------------------
        # VENUE
        # ----------------------------------------------------

        signals.venue_signal = self._venue_signal(
            results=results,
            venues=venues,
            next_venue=next_venue,
        )

        # ----------------------------------------------------
        # STABILITY
        # ----------------------------------------------------

        stability = self._stability(
            xg=xg,
            xga=xga,
            shots=shots,
            sot=sot,
        )

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        evidence_quality = self._evidence_quality(
            results=results,
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
        )

        # ----------------------------------------------------
        # FINAL FORM WIN
        # ----------------------------------------------------

        raw_components = (
            (
                signals.attack_signal,
                FINAL_WEIGHTS["attack"],
            ),
            (
                signals.control_signal,
                FINAL_WEIGHTS["control"],
            ),
            (
                signals.outcome_signal,
                FINAL_WEIGHTS["outcome"],
            ),
            (
                signals.momentum_signal,
                FINAL_WEIGHTS["momentum"],
            ),
            (
                signals.venue_signal,
                FINAL_WEIGHTS["venue"],
            ),
        )

        combined = _combine_optional(
            raw_components
        )

        if combined is None:
            win_form_score = None
        else:
            win_form_score = _clamp(
                tanh(combined)
            )

        return TeamFormWin(
            version=FORM_WIN_VERSION,
            team=team,
            matches_count=max(
                len(results),
                len(xg),
                len(shots),
                len(sot),
            ),
            attack_signal=signals.attack_signal,
            control_signal=signals.control_signal,
            outcome_signal=signals.outcome_signal,
            momentum_signal=signals.momentum_signal,
            venue_signal=signals.venue_signal,
            stability=stability,
            evidence_quality=evidence_quality,
            win_form_score=win_form_score,
            signals=signals,
            diagnostics={
                "next_venue": next_venue,
                "woodwork_used": False,
                "missing_is_zero": False,
                "bookmaker_data_used": False,
                "future_result_used": False,
                "temporal_weights": list(
                    TEMPORAL_WEIGHTS
                ),
                "attack_weights": dict(
                    ATTACK_WEIGHTS
                ),
                "control_weights": dict(
                    CONTROL_WEIGHTS
                ),
                "final_weights": dict(
                    FINAL_WEIGHTS
                ),
            },
        )

    # ========================================================
    # COMPARISON
    # ========================================================

    def compare(
        self,
        home_context: Any,
        away_context: Any,
    ) -> FormWinComparison:
        """
        Compare home and away FormWin states.

        This produces a relative state.

        It does NOT produce probabilities.
        """

        home_venue = "home"
        away_venue = "away"

        home = self.analyze(
            home_context,
            next_venue=home_venue,
        )

        away = self.analyze(
            away_context,
            next_venue=away_venue,
        )

        if (
            home.win_form_score is None
            or away.win_form_score is None
        ):
            relative = None

        else:
            relative = _clamp(
                home.win_form_score
                - away.win_form_score
            )

        evidence_values = [
            home.evidence_quality,
            away.evidence_quality,
        ]

        evidence_quality = (
            sum(evidence_values)
            / len(evidence_values)
        )

        return FormWinComparison(
            version=FORM_WIN_VERSION,
            home_team=home.team,
            away_team=away.team,
            home=home,
            away=away,
            relative_advantage=relative,
            home_advantage=(
                max(relative, 0.0)
                if relative is not None
                else None
            ),
            away_advantage=(
                max(-relative, 0.0)
                if relative is not None
                else None
            ),
            evidence_quality=evidence_quality,
            diagnostics={
                "probability_generated": False,
                "score_generated": False,
                "poisson_used": False,
            },
        )

    # ========================================================
    # VENUE
    # ========================================================

    def _venue_signal(
        self,
        results: Sequence[Optional[str]],
        venues: Sequence[Optional[str]],
        next_venue: Optional[str],
    ) -> Optional[float]:

        if not next_venue:
            return None

        target = next_venue.strip().lower()

        if target in {
            "home",
            "h",
            "дома",
        }:
            target_values = {
                "home",
                "h",
                "дома",
            }

        elif target in {
            "away",
            "a",
            "гости",
        }:
            target_values = {
                "away",
                "a",
                "гости",
            }

        else:
            return None

        venue_results = []

        for result, venue in zip(
            results,
            venues,
        ):

            if venue is None:
                continue

            normalized = venue.strip().lower()

            if normalized not in target_values:
                continue

            if result == "W":
                venue_results.append(1.0)

            elif result == "D":
                venue_results.append(0.0)

            elif result == "L":
                venue_results.append(-1.0)

        if not venue_results:
            return None

        venue_rate = _mean(
            venue_results
        )

        general_rate = _weighted_result_mean(
            results
        )

        if venue_rate is None:
            return None

        if general_rate is None:
            return venue_rate

        n = len(venue_results)

        alpha = (
            n
            /
            (
                n
                + VENUE_SHRINKAGE_K
            )
        )

        return _clamp(
            alpha * venue_rate
            +
            (1.0 - alpha)
            * general_rate
        )

    # ========================================================
    # STABILITY
    # ========================================================

    def _stability(
        self,
        xg: Sequence[Optional[float]],
        xga: Sequence[Optional[float]],
        shots: Sequence[Optional[float]],
        sot: Sequence[Optional[float]],
    ) -> Optional[float]:

        series = (
            xg,
            xga,
            shots,
            sot,
        )

        values = []

        for data in series:

            clean = [
                float(value)
                for value in data
                if value is not None
            ]

            if len(clean) < 2:
                continue

            mean = _mean(
                clean
            )

            std = _population_std(
                clean
            )

            if (
                mean is None
                or std is None
            ):
                continue

            scale = max(
                abs(mean),
                EPSILON,
            )

            cv = std / scale

            stability = (
                1.0
                /
                (
                    1.0
                    + cv
                )
            )

            values.append(
                stability
            )

        if not values:
            return None

        return max(
            0.0,
            min(
                1.0,
                sum(values)
                / len(values),
            ),
        )

    # ========================================================
    # EVIDENCE QUALITY
    # ========================================================

    def _evidence_quality(
        self,
        results: Sequence[Optional[str]],
        xg: Sequence[Optional[float]],
        xga: Sequence[Optional[float]],
        shots: Sequence[Optional[float]],
        sot: Sequence[Optional[float]],
        blocked: Sequence[Optional[float]],
        crosses: Sequence[Optional[float]],
        corners: Sequence[Optional[float]],
        possession: Sequence[Optional[float]],
        passes: Sequence[Optional[float]],
        pass_accuracy: Sequence[Optional[float]],
    ) -> float:
        """
        Measures factual coverage.

        This is NOT a performance score.
        """

        histories = (
            results,
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
        )

        available = []

        for history in histories:

            if not history:
                continue

            numeric = [
                item
                for item in history
                if item is not None
            ]

            if not numeric:
                continue

            available.append(
                len(numeric)
                /
                len(history)
            )

        if not available:
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                sum(available)
                / len(available),
            ),
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        result: TeamFormWin | FormWinComparison,
    ) -> Dict[str, Any]:
        """
        Convert result to a JSON-compatible dictionary.
        """

        return asdict(
            result
        )


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def calculate_form_win(
    form_context: Any,
    next_venue: Optional[str] = None,
) -> TeamFormWin:
    """
    Convenience API.
    """

    return FormWin().analyze(
        form_context=form_context,
        next_venue=next_venue,
    )


def compare_form_win(
    home_context: Any,
    away_context: Any,
) -> FormWinComparison:
    """
    Convenience API.
    """

    return FormWin().compare(
        home_context=home_context,
        away_context=away_context,
    )
