#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM WIN v1.3
============================================================

МАТЕМАТИЧЕСКИЙ ОРГАН FAJ

Назначение
----------

FormWin измеряет состояние команды по фактам последних матчей,
которые связаны с созданием предпосылок для победы.

FormWin НЕ прогнозирует победителя.

Архитектура:

    Match Facts
        ↓
    FormContext
        ↓
    FormWin
        ↓
    FormWinState
        ↓
    WinnerState
        ↓
    FAJ Brain

Главный принцип:

    FormWin = evidence
    WinnerState = synthesis

FormWin НЕ:

    - выбирает HOME/AWAY/DRAW;
    - рассчитывает вероятность победы;
    - рассчитывает Poisson;
    - изменяет GoalModel lambda;
    - использует будущий результат;
    - обращается к SQLite;
    - обращается к Soccer365;
    - изменяет Rating;
    - изменяет Team Passport;
    - обучается на текущем результате.

None != 0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, tanh
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


FORM_WIN_VERSION = "1.3"

EPSILON = 1e-9


TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)


# ============================================================
# INTERNAL STRUCTURAL WEIGHTS
#
# Эти веса относятся только к формированию FormWin evidence.
# Они НЕ являются WinnerState weights.
# ============================================================

ATTACK_WEIGHTS = {
    "sot": 1.0 / 3.0,
    "shots": 1.0 / 4.0,
    "blocked": 1.0 / 12.0,
    "crosses": 1.0 / 12.0,
    "corners": 1.0 / 4.0,
}

CONTROL_WEIGHTS = {
    "possession": 0.60,
    "passes": 0.20,
    "pass_accuracy": 0.20,
}

MOMENTUM_WEIGHTS = {
    "shots": 0.50,
    "sot": 1.0 / 3.0,
    "result": 1.0 / 6.0,
}

FINAL_WEIGHTS = {
    "attack": 0.50,
    "control": 0.10,
    "outcome": 0.15,
    "momentum": 0.15,
    "venue": 0.10,
}

VENUE_SHRINKAGE_K = 4.0


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:

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


def _get_value(obj: Any, *names: str) -> Any:

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

    return max(low, min(high, value))


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
            (numeric, float(weight))
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


def _ols_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:

    observations = []

    for index, value in enumerate(values):

        numeric = _safe_float(value)

        if numeric is None:
            continue

        observations.append(
            (float(index), numeric)
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


def _normalize_signal(
    value: Optional[float],
    scale: Optional[float] = None,
) -> Optional[float]:

    if value is None:
        return None

    if scale is not None and scale > EPSILON:
        return _clamp(tanh(value / scale))

    return _clamp(tanh(value))


def _combine_optional(
    components: Sequence[
        Tuple[Optional[float], float]
    ],
) -> Optional[float]:

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

    numerator = sum(
        value * weight
        for value, weight in available
    )

    return _clamp(
        numerator / denominator
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

        if value is None:
            continue

        if isinstance(value, (list, tuple)):

            return [
                _safe_float(item)
                for item in value
            ]

    return []


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class FormWinSignals:

    attack_signal: Optional[float] = None

    control_signal: Optional[float] = None

    outcome_signal: Optional[float] = None

    momentum_signal: Optional[float] = None

    venue_signal: Optional[float] = None

    shots_signal: Optional[float] = None

    sot_signal: Optional[float] = None

    blocked_signal: Optional[float] = None

    crosses_signal: Optional[float] = None

    corners_signal: Optional[float] = None

    possession_signal: Optional[float] = None

    passes_signal: Optional[float] = None

    pass_accuracy_signal: Optional[float] = None

    result_trend_signal: Optional[float] = None


@dataclass
class FormWinState:

    version: str

    team: Optional[str]

    signals: FormWinSignals

    attack_signal: Optional[float]

    control_signal: Optional[float]

    outcome_signal: Optional[float]

    momentum_signal: Optional[float]

    venue_signal: Optional[float]

    win_form_score: Optional[float]

    evidence_vector: Dict[
        str,
        Optional[float],
    ]

    evidence_sources: List[str]

    evidence_conflicts: List[str]

    data_quality: Optional[float]

    sample_size: int

    diagnostics: Dict[str, Any]


@dataclass
class FormWinComparison:

    home_form_win: Optional[float]

    away_form_win: Optional[float]

    relative_form_win: Optional[float]

    home_state: Optional[FormWinState] = None

    away_state: Optional[FormWinState] = None

    relative_attack: Optional[float] = None

    relative_control: Optional[float] = None

    relative_outcome: Optional[float] = None

    relative_momentum: Optional[float] = None

    relative_venue: Optional[float] = None

    evidence_sources: Optional[List[str]] = None


# ============================================================
# FORM WIN
# ============================================================

class FormWin:

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

            "shots": _extract_history(
                context,
                "shots_history",
                "team_shots_history",
                "shots",
            ),

            "sot": _extract_history(
                context,
                "shots_on_target_history",
                "sot_history",
                "team_sot_history",
            ),

            "blocked": _extract_history(
                context,
                "blocked_shots_history",
                "team_blocked_shots_history",
            ),

            "crosses": _extract_history(
                context,
                "crosses_history",
                "team_crosses_history",
            ),

            "corners": _extract_history(
                context,
                "corners_history",
                "team_corners_history",
            ),

            "possession": _extract_history(
                context,
                "possession_history",
                "team_possession_history",
            ),

            "passes": _extract_history(
                context,
                "passes_history",
                "team_passes_history",
            ),

            "pass_accuracy": _extract_history(
                context,
                "pass_accuracy_history",
                "team_pass_accuracy_history",
            ),

            "goals": _extract_history(
                context,
                "goals_history",
                "team_goals_history",
                "goals_for_history",
            ),

            "results": _extract_history(
                context,
                "result_codes",
                "result_signal_history",
            ),

            "venue": _extract_history(
                context,
                "venue_signal_history",
            ),
        }

    # ========================================================
    # ATTACK
    # ========================================================

    def _attack_signal(
        self,
        histories: Dict[str, List[Optional[float]]],
    ) -> Optional[float]:

        components = []

        for key, weight in ATTACK_WEIGHTS.items():

            history = histories.get(
                key,
                [],
            )

            signal = self._positive_state_signal(
                history
            )

            components.append(
                (signal, weight)
            )

        return _combine_optional(
            components
        )

    # ========================================================
    # CONTROL
    # ========================================================

    def _control_signal(
        self,
        histories: Dict[str, List[Optional[float]]],
    ) -> Optional[float]:

        components = []

        for key, weight in CONTROL_WEIGHTS.items():

            history = histories.get(
                key,
                [],
            )

            signal = self._positive_state_signal(
                history
            )

            components.append(
                (signal, weight)
            )

        return _combine_optional(
            components
        )

    # ========================================================
    # OUTCOME
    # ========================================================

    def _outcome_signal(
        self,
        histories: Dict[str, List[Optional[float]]],
    ) -> Optional[float]:

        results = histories.get(
            "results",
            [],
        )

        if not results:

            goals = histories.get(
                "goals",
                [],
            )

            if not goals:
                return None

            return self._positive_state_signal(
                goals
            )

        return _weighted_mean(
            results,
            self.temporal_weights,
        )

    # ========================================================
    # MOMENTUM
    # ========================================================

    def _momentum_signal(
        self,
        histories: Dict[str, List[Optional[float]]],
    ) -> Optional[float]:

        shots = histories.get(
            "shots",
            [],
        )

        sot = histories.get(
            "sot",
            [],
        )

        results = histories.get(
            "results",
            [],
        )

        components = []

        shots_trend = self._positive_trend(
            shots
        )

        sot_trend = self._positive_trend(
            sot
        )

        result_trend = self._positive_trend(
            results
        )

        components.extend(
            (
                (
                    shots_trend,
                    MOMENTUM_WEIGHTS["shots"],
                ),
                (
                    sot_trend,
                    MOMENTUM_WEIGHTS["sot"],
                ),
                (
                    result_trend,
                    MOMENTUM_WEIGHTS["result"],
                ),
            )
        )

        return _combine_optional(
            components
        )

    # ========================================================
    # POSITIVE SIGNAL
    # ========================================================

    def _positive_state_signal(
        self,
        values: Sequence[Optional[float]],
    ) -> Optional[float]:

        clean = [
            value
            for value in values
            if value is not None
        ]

        if not clean:
            return None

        weighted = _weighted_mean(
            values,
            self.temporal_weights,
        )

        if weighted is None:
            return None

        center = _mean(clean)

        if center is None:
            return None

        if abs(center) <= EPSILON:

            if weighted > EPSILON:
                return 1.0

            if weighted < -EPSILON:
                return -1.0

            return 0.0

        relative = (
            weighted - center
        ) / max(
            abs(center),
            EPSILON,
        )

        return _clamp(
            tanh(relative)
        )

    # ========================================================
    # POSITIVE TREND
    # ========================================================

    def _positive_trend(
        self,
        values: Sequence[Optional[float]],
    ) -> Optional[float]:

        slope = _ols_slope(values)

        if slope is None:
            return None

        clean = [
            value
            for value in values
            if value is not None
        ]

        if len(clean) < 2:
            return None

        scale = max(
            abs(_mean(clean) or 0.0),
            1.0,
        )

        return _clamp(
            tanh(
                slope / scale
            )
        )

    # ========================================================
    # VENUE
    # ========================================================

    def _venue_signal(
        self,
        context: Any,
    ) -> Optional[float]:

        venue = _get_value(
            context,
            "venue_signal",
            "home_away_signal",
        )

        numeric = _safe_float(
            venue
        )

        if numeric is None:
            return None

        return _clamp(
            numeric
        )

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

        available = [
            value
            for value in evidence.values()
            if value is not None
        ]

        if len(available) < 2:
            return []

        positive = sum(
            value > 0.15
            for value in available
        )

        negative = sum(
            value < -0.15
            for value in available
        )

        if positive and negative:
            return [
                "form_win_evidence_conflict"
            ]

        return []

    # ========================================================
    # DATA QUALITY
    # ========================================================

    def _data_quality(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        relevant = []

        for key in (
            "shots",
            "sot",
            "blocked",
            "crosses",
            "corners",
            "possession",
            "passes",
            "pass_accuracy",
            "goals",
            "results",
        ):

            values = histories.get(
                key,
                [],
            )

            if values:
                relevant.append(
                    sum(
                        value is not None
                        for value in values
                    )
                    / len(values)
                )

        if not relevant:
            return None

        return max(
            0.0,
            min(
                1.0,
                sum(relevant) / len(relevant),
            ),
        )

    # ========================================================
    # CALCULATE
    # ========================================================

    def calculate(
        self,
        context: Any,
        *,
        team_name: Optional[str] = None,
    ) -> FormWinState:

        histories = self._histories(
            context
        )

        attack_signal = self._attack_signal(
            histories
        )

        control_signal = self._control_signal(
            histories
        )

        outcome_signal = self._outcome_signal(
            histories
        )

        momentum_signal = self._momentum_signal(
            histories
        )

        venue_signal = self._venue_signal(
            context
        )

        win_form_score = _combine_optional(
            (
                (
                    attack_signal,
                    FINAL_WEIGHTS["attack"],
                ),
                (
                    control_signal,
                    FINAL_WEIGHTS["control"],
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

        if win_form_score is not None:
            win_form_score = tanh(
                win_form_score
            )

        evidence_vector = {
            "attack": attack_signal,
            "control": control_signal,
            "outcome": outcome_signal,
            "momentum": momentum_signal,
            "venue": venue_signal,
        }

        evidence_sources = [
            key
            for key, value in evidence_vector.items()
            if value is not None
        ]

        evidence_conflicts = (
            self._detect_conflicts(
                evidence_vector
            )
        )

        data_quality = self._data_quality(
            histories
        )

        sample_size = max(
            (
                len(value)
                for value in histories.values()
            ),
            default=0,
        )

        signals = FormWinSignals(
            attack_signal=attack_signal,
            control_signal=control_signal,
            outcome_signal=outcome_signal,
            momentum_signal=momentum_signal,
            venue_signal=venue_signal,

            shots_signal=self._positive_state_signal(
                histories["shots"]
            ),

            sot_signal=self._positive_state_signal(
                histories["sot"]
            ),

            blocked_signal=self._positive_state_signal(
                histories["blocked"]
            ),

            crosses_signal=self._positive_state_signal(
                histories["crosses"]
            ),

            corners_signal=self._positive_state_signal(
                histories["corners"]
            ),

            possession_signal=self._positive_state_signal(
                histories["possession"]
            ),

            passes_signal=self._positive_state_signal(
                histories["passes"]
            ),

            pass_accuracy_signal=self._positive_state_signal(
                histories["pass_accuracy"]
            ),

            result_trend_signal=self._positive_trend(
                histories["results"]
            ),
        )

        return FormWinState(
            version=FORM_WIN_VERSION,
            team=team_name,
            signals=signals,

            attack_signal=attack_signal,
            control_signal=control_signal,
            outcome_signal=outcome_signal,
            momentum_signal=momentum_signal,
            venue_signal=venue_signal,

            win_form_score=win_form_score,

            evidence_vector=evidence_vector,
            evidence_sources=evidence_sources,
            evidence_conflicts=evidence_conflicts,

            data_quality=data_quality,
            sample_size=sample_size,

            diagnostics={
                "version": FORM_WIN_VERSION,
                "model_role": "winner_evidence",
                "winner_state_generated": False,
                "winner_direction_generated": False,
                "winner_probability_generated": False,
                "poisson_used": False,
                "goalmodel_modified": False,
                "future_result_used": False,
                "missing_is_zero": False,
                "winner_override": False,

                "attack_weights": dict(
                    ATTACK_WEIGHTS
                ),

                "control_weights": dict(
                    CONTROL_WEIGHTS
                ),

                "momentum_weights": dict(
                    MOMENTUM_WEIGHTS
                ),

                "final_weights": dict(
                    FINAL_WEIGHTS
                ),

                "contract": (
                    "MATHEMATICAL_CONTRACT_V1"
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
    ) -> FormWinComparison:

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

        relative_form_win = relative(
            home.win_form_score,
            away.win_form_score,
        )

        relative_attack = relative(
            home.attack_signal,
            away.attack_signal,
        )

        relative_control = relative(
            home.control_signal,
            away.control_signal,
        )

        relative_outcome = relative(
            home.outcome_signal,
            away.outcome_signal,
        )

        relative_momentum = relative(
            home.momentum_signal,
            away.momentum_signal,
        )

        relative_venue = relative(
            home.venue_signal,
            away.venue_signal,
        )

        sources = [
            name
            for name, value in (
                ("form_win", relative_form_win),
                ("attack", relative_attack),
                ("control", relative_control),
                ("outcome", relative_outcome),
                ("momentum", relative_momentum),
                ("venue", relative_venue),
            )
            if value is not None
        ]

        return FormWinComparison(
            home_form_win=home.win_form_score,
            away_form_win=away.win_form_score,
            relative_form_win=relative_form_win,

            home_state=home,
            away_state=away,

            relative_attack=relative_attack,
            relative_control=relative_control,
            relative_outcome=relative_outcome,
            relative_momentum=relative_momentum,
            relative_venue=relative_venue,

            evidence_sources=sources,
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        state: FormWinState,
    ) -> Dict[str, Any]:

        return asdict(state)


# ============================================================
# FUNCTIONAL API
# ============================================================

def calculate_form_win(
    context: Any,
    *,
    team_name: Optional[str] = None,
) -> FormWinState:

    return FormWin().calculate(
        context,
        team_name=team_name,
    )


def compare_form_win(
    home_context: Any,
    away_context: Any,
    *,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
) -> FormWinComparison:

    return FormWin().compare(
        home_context,
        away_context,
        home_team=home_team,
        away_team=away_team,
    )
