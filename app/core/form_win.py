#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM WIN v1.4
============================================================

МАТЕМАТИЧЕСКИЙ ОРГАН FAJ

Назначение
----------

FormWin измеряет состояние команды по фактам последних матчей,
которые могут формировать предпосылки для победы.

FormWin = EVIDENCE ORGAN

FormWin НЕ является Winner Predictor.

Архитектура:

    Match Facts
        ↓
    FormContext
        ↓
    FormWin
        ↓
    FormWinState
        ↓
    FAJBrain / AnalysisEngine
        ↓
    Winner synthesis

Главный принцип:

    FormWin = evidence
    Winner synthesis = отдельный уровень FAJBrain/AnalysisEngine

FormWin НЕ:

    - выбирает HOME/AWAY/DRAW как окончательный прогноз;
    - рассчитывает вероятность победы;
    - рассчитывает Poisson;
    - изменяет GoalModel lambda;
    - использует будущий результат;
    - обращается к SQLite;
    - обращается к Soccer365;
    - изменяет Rating;
    - изменяет Team Passport;
    - обучается на текущем результате;
    - изменяет ProbabilityModel;
    - изменяет ScorePredictor.

ВАЖНО
-----

FormWin может вернуть win_form_score и relative_form_win.

Это НЕ probability.

Это ограниченное [-1, +1] evidence.

None != 0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite, tanh
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


FORM_WIN_VERSION = "1.4"

EPSILON = 1e-9


# ============================================================
# TEMPORAL WEIGHTS
#
# История:
#
# oldest → newest
#
# Для N матчей используются первые N весов.
# При N < 6 используются только существующие веса.
# ============================================================

TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
)


# ============================================================
# INTERNAL FORM-WIN WEIGHTS
#
# Эти веса относятся ТОЛЬКО к внутреннему evidence FormWin.
#
# Они НЕ являются:
#   - WinnerState weights;
#   - Probability weights;
#   - GoalModel multipliers;
#   - confidence weights.
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
    """
    Безопасное числовое преобразование.

    None остаётся None.
    bool не считается числом.
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
    Получает значение из dict / mapping / dataclass / object.
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
    """
    Обычное среднее только по существующим значениям.

    None не участвует.
    """

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
    """
    Взвешенное среднее.

    История предполагается oldest → newest.

    Веса сохраняют позиционную recency-структуру.
    None не получает веса и не входит в denominator.
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

    if denominator <= EPSILON:
        return None

    return sum(
        value * weight
        for value, weight in pairs
    ) / denominator


def _ols_slope(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    OLS slope по фактически существующим наблюдениям.

    Индекс сохраняется относительно исходной последовательности,
    чтобы пропуски не сжимали временную шкалу.
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

    x = [
        item[0]
        for item in observations
    ]

    y = [
        item[1]
        for item in observations
    ]

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
    Взвешенное объединение только существующих evidence.

    Отсутствующий компонент НЕ заменяется нулём.
    Вес отсутствующего компонента исключается из denominator.
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


def _extract_history(
    context: Any,
    *names: str,
) -> List[Optional[float]]:
    """
    Извлекает числовую историю.

    Источник обязан передавать историю oldest → newest.
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
            return [
                _safe_float(item)
                for item in value
            ]

    return []


def _normalize_result_code(
    value: Any,
) -> Optional[float]:
    """
    Нормализация результата матча в signal:

        W = +1
        D =  0
        L = -1

    Поддерживаются:
        W / D / L
        WIN / DRAW / LOSS
        1 / X / 2
        числовые -1 / 0 / +1

    Числовые значения вне [-1, +1] не принимаются.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, str):

        code = value.strip().upper()

        mapping = {
            "W": 1.0,
            "WIN": 1.0,
            "1": 1.0,

            "D": 0.0,
            "DRAW": 0.0,
            "X": 0.0,

            "L": -1.0,
            "LOSS": -1.0,
            "LOST": -1.0,
            "2": -1.0,
        }

        if code in mapping:
            return mapping[code]

        numeric = _safe_float(code)

    else:
        numeric = _safe_float(value)

    if numeric is None:
        return None

    if numeric in (-1.0, 0.0, 1.0):
        return numeric

    return None


def _extract_result_history(
    context: Any,
    *names: str,
) -> List[Optional[float]]:
    """
    Отдельный extractor для W/D/L result history.
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
            return [
                _normalize_result_code(item)
                for item in value
            ]

    return []


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class FormWinSignals:
    """
    Низкоуровневые evidence-сигналы FormWin.
    """

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
    """
    Состояние FormWin.

    win_form_score:
        итоговое внутреннее evidence FormWin [-1, +1].

    Это НЕ вероятность победы.
    """

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

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class FormWinComparison:
    """
    Сравнение FormWin двух команд.

    relative_*:

        HOME - AWAY

    Это относительное evidence.

    Это НЕ:
        - Winner probability;
        - окончательный winner;
        - draw probability.
    """

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

    evidence_conflicts: Optional[List[str]] = None


# ============================================================
# FORM WIN
# ============================================================

class FormWin:
    """
    FormWin evidence organ.

    FormWin получает только контекст фактов.

    Он не знает:
        - GoalModel;
        - ProbabilityModel;
        - ScorePredictor;
        - CornersModel;
        - CardsModel;
        - Database;
        - текущий факт будущего матча.
    """

    def __init__(
        self,
        *,
        temporal_weights: Sequence[
            float
        ] = TEMPORAL_WEIGHTS,
    ) -> None:

        weights = tuple(
            float(weight)
            for weight in temporal_weights
        )

        if not weights:
            raise ValueError(
                "temporal_weights must not be empty"
            )

        if any(
            weight <= 0.0
            for weight in weights
        ):
            raise ValueError(
                "temporal_weights must be positive"
            )

        self.temporal_weights = weights

    # ========================================================
    # HISTORIES
    # ========================================================

    def _histories(
        self,
        context: Any,
    ) -> Dict[
        str,
        List[Optional[float]],
    ]:
        """
        Получение фактических историй из FormContext.

        FormContext считается уже нормализованным
        и упорядоченным oldest → newest.
        """

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

            "results": _extract_result_history(
                context,
                "result_codes",
                "result_signal_history",
                "results",
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
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        components: List[
            Tuple[Optional[float], float]
        ] = []

        for key, weight in ATTACK_WEIGHTS.items():

            history = histories.get(
                key,
                [],
            )

            signal = self._positive_state_signal(
                history
            )

            components.append(
                (
                    signal,
                    weight,
                )
            )

        return _combine_optional(
            components
        )

    # ========================================================
    # CONTROL
    # ========================================================

    def _control_signal(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        components: List[
            Tuple[Optional[float], float]
        ] = []

        for key, weight in CONTROL_WEIGHTS.items():

            history = histories.get(
                key,
                [],
            )

            signal = self._positive_state_signal(
                history
            )

            components.append(
                (
                    signal,
                    weight,
                )
            )

        return _combine_optional(
            components
        )

    # ========================================================
    # OUTCOME
    # ========================================================

    def _outcome_signal(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
    ) -> Optional[float]:

        results = histories.get(
            "results",
            [],
        )

        if results:

            return _weighted_mean(
                results,
                self.temporal_weights,
            )

        # Если результатов нет, НЕ подменяем их голами.
        #
        # Goals ≠ Result.
        #
        # Это принципиальная защита от смешения сущностей.

        return None

    # ========================================================
    # MOMENTUM
    # ========================================================

    def _momentum_signal(
        self,
        histories: Dict[
            str,
            List[Optional[float]],
        ],
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

        components: List[
            Tuple[Optional[float], float]
        ] = []

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
    # POSITIVE STATE SIGNAL
    # ========================================================

    def _positive_state_signal(
        self,
        values: Sequence[Optional[float]],
    ) -> Optional[float]:
        """
        Формирует bounded evidence относительно собственного
        среднего состояния команды.

        Это НЕ абсолютная сила команды.

        Пример:

            stable history
                ↓
            signal ≈ 0

        recent increase
                ↓
            positive signal

        recent decrease
                ↓
            negative signal

        Это намеренно diagnostic/evidence behaviour.
        """

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

        slope = _ols_slope(
            values
        )

        if slope is None:
            return None

        clean = [
            value
            for value in values
            if value is not None
        ]

        if len(clean) < 2:
            return None

        mean_value = _mean(clean)

        if mean_value is None:
            return None

        scale = max(
            abs(mean_value),
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
        """
        Среднее покрытие доступных FormWin histories.

        Отсутствующая история полностью исключается.

        None внутри существующей истории считается отсутствующим
        наблюдением.
        """

        relevant: List[float] = []

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

            if not values:
                continue

            coverage = (
                sum(
                    value is not None
                    for value in values
                )
                / len(values)
            )

            relevant.append(
                coverage
            )

        if not relevant:
            return None

        return max(
            0.0,
            min(
                1.0,
                sum(relevant)
                / len(relevant),
            ),
        )

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
        Sample size FormWin.

        Берём максимальное количество фактически существующих
        наблюдений среди историй, которые действительно относятся
        к FormWin.

        Это не matches_count из общего контекста.
        """

        relevant_keys = (
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
        )

        sizes = []

        for key in relevant_keys:

            values = histories.get(
                key,
                [],
            )

            valid_count = sum(
                value is not None
                for value in values
            )

            if valid_count > 0:
                sizes.append(
                    valid_count
                )

        if not sizes:
            return 0

        return max(sizes)

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

        # ----------------------------------------------------
        # PRIMARY EVIDENCE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # INTERNAL FORM-WIN EVIDENCE
        #
        # Это НЕ WinnerState.
        # Это только объединённый evidence FormWin.
        # ----------------------------------------------------

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

            win_form_score = _clamp(
                tanh(
                    win_form_score
                )
            )

        # ----------------------------------------------------
        # EVIDENCE VECTOR
        # ----------------------------------------------------

        evidence_vector: Dict[
            str,
            Optional[float],
        ] = {
            "attack": attack_signal,
            "control": control_signal,
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

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        data_quality = self._data_quality(
            histories
        )

        sample_size = self._sample_size(
            histories
        )

        # ----------------------------------------------------
        # LOW-LEVEL SIGNALS
        # ----------------------------------------------------

        signals = FormWinSignals(

            attack_signal=attack_signal,

            control_signal=control_signal,

            outcome_signal=outcome_signal,

            momentum_signal=momentum_signal,

            venue_signal=venue_signal,

            shots_signal=(
                self._positive_state_signal(
                    histories["shots"]
                )
            ),

            sot_signal=(
                self._positive_state_signal(
                    histories["sot"]
                )
            ),

            blocked_signal=(
                self._positive_state_signal(
                    histories["blocked"]
                )
            ),

            crosses_signal=(
                self._positive_state_signal(
                    histories["crosses"]
                )
            ),

            corners_signal=(
                self._positive_state_signal(
                    histories["corners"]
                )
            ),

            possession_signal=(
                self._positive_state_signal(
                    histories["possession"]
                )
            ),

            passes_signal=(
                self._positive_state_signal(
                    histories["passes"]
                )
            ),

            pass_accuracy_signal=(
                self._positive_state_signal(
                    histories["pass_accuracy"]
                )
            ),

            result_trend_signal=(
                self._positive_trend(
                    histories["results"]
                )
            ),
        )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

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

                "model_role": (
                    "winner_evidence_organ"
                ),

                # ------------------------------------------------
                # ARCHITECTURE
                # ------------------------------------------------

                "winner_state_generated": False,

                "winner_direction_generated": False,

                "winner_probability_generated": False,

                "winner_synthesis_owner": (
                    "FAJBrain/AnalysisEngine"
                ),

                # ------------------------------------------------
                # PROHIBITED DEPENDENCIES
                # ------------------------------------------------

                "poisson_used": False,

                "goalmodel_modified": False,

                "probability_model_modified": False,

                "score_predictor_modified": False,

                "future_result_used": False,

                "database_used": False,

                "rating_used": False,

                "passport_used": False,

                "odds_used": False,

                "winner_override": False,

                # ------------------------------------------------
                # MISSING DATA CONTRACT
                # ------------------------------------------------

                "missing_is_zero": False,

                "none_is_zero": False,

                # ------------------------------------------------
                # INTERNAL FORM-WIN WEIGHTS
                # ------------------------------------------------

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

                "venue_shrinkage_k": (
                    VENUE_SHRINKAGE_K
                ),

                # ------------------------------------------------
                # CONTRACT
                # ------------------------------------------------

                "contract": (
                    "MATHEMATICAL_CONTRACT_V1"
                ),

                "state_role": (
                    "diagnostic_evidence"
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
        """
        Сравнивает FormWin двух команд.

        Все relative значения:

            HOME - AWAY

        Они являются evidence.

        Они НЕ являются:

            Home probability
            Draw probability
            Away probability
            final winner
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
                (
                    "form_win",
                    relative_form_win,
                ),
                (
                    "attack",
                    relative_attack,
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
                (
                    "venue",
                    relative_venue,
                ),
            )
            if value is not None
        ]

        conflicts: List[str] = []

        relative_evidence = {
            "form_win": relative_form_win,
            "attack": relative_attack,
            "control": relative_control,
            "outcome": relative_outcome,
            "momentum": relative_momentum,
            "venue": relative_venue,
        }

        available = [
            value
            for value
            in relative_evidence.values()
            if value is not None
        ]

        if (
            len(available) >= 2
            and any(
                value > 0.15
                for value in available
            )
            and any(
                value < -0.15
                for value in available
            )
        ):
            conflicts.append(
                "home_away_form_win_evidence_conflict"
            )

        return FormWinComparison(

            home_form_win=(
                home.win_form_score
            ),

            away_form_win=(
                away.win_form_score
            ),

            relative_form_win=(
                relative_form_win
            ),

            home_state=home,

            away_state=away,

            relative_attack=(
                relative_attack
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

            relative_venue=(
                relative_venue
            ),

            evidence_sources=sources,

            evidence_conflicts=conflicts,
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    @staticmethod
    def to_dict(
        state: FormWinState,
    ) -> Dict[str, Any]:

        return asdict(
            state
        )


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
