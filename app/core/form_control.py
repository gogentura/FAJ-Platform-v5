#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FORM CONTROL v1.2
============================================================

МАТЕМАТИЧЕСКИЙ ОРГАН FAJ

Назначение
----------

FormControl измеряет evidence контроля команды по фактам
последних матчей.

FormControl = CONTROL EVIDENCE ORGAN

Он измеряет:

    Control
        ├── possession
        ├── passes
        └── pass accuracy

    Progression
        ├── crosses
        ├── throw-ins
        └── offsides

    Pressure
        ├── shots
        └── big chances

Corners являются отдельным диагностическим сигналом.

Архитектура:

    FormContext
        ↓
    FormControl
        ↓
    ControlResult
        ↓
    FAJBrain / AnalysisEngine

FormControl НЕ:

    - прогнозирует победителя;
    - выбирает HOME/AWAY/DRAW;
    - рассчитывает вероятность;
    - рассчитывает Poisson;
    - изменяет GoalModel;
    - изменяет ProbabilityModel;
    - изменяет ScorePredictor;
    - зависит от FormWin;
    - изменяет xG;
    - изменяет Rating;
    - обращается к SQLite;
    - обращается к Soccer365;
    - использует будущий результат.

Главный принцип:

    ControlSignal = evidence

Это НЕ:

    probability
    confidence
    winner prediction

None != 0
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ============================================================
# VERSION
# ============================================================

FORM_CONTROL_VERSION = "1.2"
FORMULA_STATUS = "RESEARCH_FORMULA"

EPSILON = 1e-9


# ============================================================
# TEMPORAL WEIGHTS
#
# История FormContext:
#
# oldest → newest
#
# Последний матч получает максимальный вес.
# ============================================================

TEMPORAL_WEIGHTS: Tuple[float, ...] = (
    0.08,
    0.10,
    0.13,
    0.18,
    0.23,
    0.28,
)


# ============================================================
# INTERNAL RESEARCH PARAMETERS
#
# Эти веса относятся только к FormControl.
#
# Они НЕ являются:
#   - Winner weights;
#   - GoalModel multipliers;
#   - Probability weights;
#   - Confidence weights;
#   - Risk weights.
# ============================================================

CONTROL_POSSESSION_WEIGHT = 0.40
CONTROL_PASSES_WEIGHT = 0.35
CONTROL_ACCURACY_WEIGHT = 0.25

PROGRESSION_CROSSES_WEIGHT = 0.40
PROGRESSION_THROWINS_WEIGHT = 0.35
PROGRESSION_OFFSIDES_WEIGHT = 0.25

PRESSURE_SHOTS_WEIGHT = 0.60
PRESSURE_BIG_CHANCES_WEIGHT = 0.40

CONTROL_WEIGHT = 0.50
PROGRESSION_WEIGHT = 0.25
PRESSURE_WEIGHT = 0.25

OPPONENT_WEIGHT = 0.65
SELF_WEIGHT = 0.35

SELF_K = 2.0

# ============================================================
# ВАЖНО:
#
# MAX_CONTROL_INFLUENCE удалён.
#
# FormControl не должен заранее диктовать Brain:
# "влияние только ±5%".
#
# Brain/AnalysisEngine сам решает, как интерпретировать
# evidence в общей системе.
# ============================================================


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> Optional[float]:
    """
    Безопасное преобразование в float.

    None остаётся None.
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


def _get_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Читает значение из:

        dict
        mapping-like object
        dataclass/object

    Позволяет FormControl работать с текущим FormContext
    без создания нового schema.
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
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Среднее только по существующим значениям.
    """

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _std(
    values: Sequence[Optional[float]],
) -> Optional[float]:
    """
    Population standard deviation.

    None исключаются.
    """

    clean = [
        value
        for value in values
        if value is not None
    ]

    if len(clean) < 2:
        return None

    mean_value = sum(clean) / len(clean)

    variance = (
        sum(
            (value - mean_value) ** 2
            for value in clean
        )
        / len(clean)
    )

    return math.sqrt(
        variance
    )


def _weighted_mean(
    values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Взвешенное среднее.

    Веса принадлежат исходным позициям матчей.

    None:
        - не получает вес;
        - не входит в denominator.
    """

    pairs: List[Tuple[float, float]] = []

    for index, value in enumerate(values):

        if index >= len(weights):
            break

        numeric = _safe_float(
            value
        )

        if numeric is None:
            continue

        weight = float(
            weights[index]
        )

        if weight <= EPSILON:
            continue

        pairs.append(
            (
                numeric,
                weight,
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

    return (
        sum(
            value * weight
            for value, weight in pairs
        )
        / denominator
    )


def _weighted_pair_advantage(
    target_values: Sequence[Optional[float]],
    opponent_values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Взвешенное относительное преимущество target относительно
    opponent.

    Formula:

        A = (target - opponent)
            / (abs(target) + abs(opponent))

    Результат:

        [-1, +1]

    Это symmetric bounded evidence.

    Важное отличие от старой версии:

        denominator никогда не использует
        target + opponent.

    Поэтому корректно работает и для нулевых значений.
    """

    if not target_values:
        return None

    if not opponent_values:
        return None

    total_weight = 0.0
    weighted_sum = 0.0

    limit = min(
        len(target_values),
        len(opponent_values),
        len(weights),
        6,
    )

    for index in range(limit):

        target = _safe_float(
            target_values[index]
        )

        opponent = _safe_float(
            opponent_values[index]
        )

        if (
            target is None
            or opponent is None
        ):
            continue

        denominator = (
            abs(target)
            + abs(opponent)
        )

        # Оба значения действительно равны нулю.
        # Это не преимущество ни одной стороны.
        if denominator <= EPSILON:
            advantage = 0.0

        else:
            advantage = (
                target - opponent
            ) / denominator

        weight = float(
            weights[index]
        )

        if weight <= EPSILON:
            continue

        weighted_sum += (
            weight * advantage
        )

        total_weight += weight

    if total_weight <= EPSILON:
        return None

    return _clamp(
        weighted_sum / total_weight
    )


def _weighted_possession_advantage(
    target_values: Sequence[Optional[float]],
    opponent_values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Преимущество во владении.

    Formula:

        (target - opponent) / 100

    При нормальном футбольном владении:

        55% vs 45%
            ↓
        +0.10

        45% vs 55%
            ↓
        -0.10
    """

    if not target_values:
        return None

    if not opponent_values:
        return None

    total_weight = 0.0
    weighted_sum = 0.0

    limit = min(
        len(target_values),
        len(opponent_values),
        len(weights),
        6,
    )

    for index in range(limit):

        target = _safe_float(
            target_values[index]
        )

        opponent = _safe_float(
            opponent_values[index]
        )

        if (
            target is None
            or opponent is None
        ):
            continue

        advantage = (
            target - opponent
        ) / 100.0

        weight = float(
            weights[index]
        )

        if weight <= EPSILON:
            continue

        weighted_sum += (
            weight * advantage
        )

        total_weight += weight

    if total_weight <= EPSILON:
        return None

    return _clamp(
        weighted_sum / total_weight
    )


def _weighted_accuracy_advantage(
    target_values: Sequence[Optional[float]],
    opponent_values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Преимущество точности пасов.

    Formula:

        (target - opponent) / 100
    """

    if not target_values:
        return None

    if not opponent_values:
        return None

    total_weight = 0.0
    weighted_sum = 0.0

    limit = min(
        len(target_values),
        len(opponent_values),
        len(weights),
        6,
    )

    for index in range(limit):

        target = _safe_float(
            target_values[index]
        )

        opponent = _safe_float(
            opponent_values[index]
        )

        if (
            target is None
            or opponent is None
        ):
            continue

        advantage = (
            target - opponent
        ) / 100.0

        weight = float(
            weights[index]
        )

        if weight <= EPSILON:
            continue

        weighted_sum += (
            weight * advantage
        )

        total_weight += weight

    if total_weight <= EPSILON:
        return None

    return _clamp(
        weighted_sum / total_weight
    )


def _weighted_self_state(
    values: Sequence[Optional[float]],
    weights: Sequence[float] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Последнее взвешенное состояние относительно собственной
    исторической нормы.

    Formula:

        recent = WeightedMean(history)

        baseline = Mean(history)

        relative =
            (recent - baseline)
            / max(abs(baseline), scale)

    Здесь scale определяется самим показателем.

    Это diagnostic evidence, а не абсолютная сила команды.
    """

    clean = [
        value
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    recent = _weighted_mean(
        values,
        weights,
    )

    baseline = _mean(
        clean
    )

    if (
        recent is None
        or baseline is None
    ):
        return None

    scale = max(
        abs(baseline),
        1.0,
    )

    relative = (
        recent - baseline
    ) / scale

    return _clamp(
        math.tanh(relative)
    )


def _combine_optional(
    components: Sequence[
        Tuple[Optional[float], float]
    ],
) -> Optional[float]:
    """
    Взвешенное объединение доступных компонентов.

    Отсутствующий компонент не заменяется нулём.
    Его вес исключается из denominator.
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
    Извлекает историю из FormContext.

    История предполагается oldest → newest.
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
                for item in value[:6]
            ]

    return []


# ============================================================
# RESULT STRUCTURES
# ============================================================

@dataclass
class ControlBlock:
    """
    Результат отдельного блока FormControl.
    """

    raw: Optional[float]

    normalized: Optional[float]

    components: Dict[
        str,
        Optional[float],
    ]

    data_quality: Optional[float] = None

    sample_size: int = 0

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class ControlResult:
    """
    Полное состояние FormControl.

    control_signal:
        bounded evidence [-1, +1]

    control_strength:
        |control_signal| [0, 1]

    Это НЕ вероятность.
    """

    version: str

    target_team: Optional[str]

    opponent_team: Optional[str]

    venue: Optional[str]

    control_signal: Optional[float]

    control_strength: Optional[float]

    control_block: Optional[ControlBlock]

    progression_block: Optional[ControlBlock]

    pressure_block: Optional[ControlBlock]

    opponent_signal: Optional[float]

    self_signal: Optional[float]

    self_norm: Optional[float]

    self_std: Optional[float]

    self_z_score: Optional[float]

    corners_signal: Optional[float]

    raw_components: Dict[
        str,
        Optional[float],
    ]

    formula_status: str

    data_quality: Optional[float]

    sample_size: int

    diagnostics: Dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


# ============================================================
# FORM CONTROL
# ============================================================

class FormControl:
    """
    FormControl v1.2.

    Измеряет контроль как отдельный evidence-орган.

    Основная логика:

        opponent evidence
                +
        self-state evidence
                ↓
        ControlSignal

    Но:

        ControlSignal != winner
        ControlSignal != probability
        ControlSignal != confidence
    """

    VERSION = FORM_CONTROL_VERSION

    FORMULA_STATUS = FORMULA_STATUS

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
    # PUBLIC API
    # ========================================================

    def analyze(
        self,
        context: Any,
        target_team: Optional[str] = None,
        opponent_team: Optional[str] = None,
        venue: Optional[str] = None,
    ) -> ControlResult:
        """
        Анализирует контроль target_team.

        Parameters
        ----------
        context:
            FormContext.

        target_team:
            Целевая команда.

        opponent_team:
            Соперник.

        venue:
            home / away / None.

        Context должен содержать истории:

            team values
            opponent values

        FormControl не создаёт новый context/schema.
        """

        # ====================================================
        # 1. HISTORIES
        # ====================================================

        target_possession = _extract_history(
            context,
            "possession_history",
            "team_possession_history",
        )

        opponent_possession = _extract_history(
            context,
            "opponent_possession_history",
            "opponent_possession",
        )

        target_passes = _extract_history(
            context,
            "passes_history",
            "team_passes_history",
        )

        opponent_passes = _extract_history(
            context,
            "opponent_passes_history",
            "passes_against_history",
        )

        target_accuracy = _extract_history(
            context,
            "pass_accuracy_history",
            "team_pass_accuracy_history",
        )

        opponent_accuracy = _extract_history(
            context,
            "opponent_pass_accuracy_history",
            "pass_accuracy_against_history",
        )

        target_crosses = _extract_history(
            context,
            "crosses_history",
            "team_crosses_history",
        )

        opponent_crosses = _extract_history(
            context,
            "opponent_crosses_history",
            "crosses_against_history",
        )

        target_throwins = _extract_history(
            context,
            "throw_ins_history",
            "team_throw_ins_history",
        )

        opponent_throwins = _extract_history(
            context,
            "opponent_throw_ins_history",
            "throw_ins_against_history",
        )

        target_offsides = _extract_history(
            context,
            "offsides_history",
            "team_offsides_history",
        )

        opponent_offsides = _extract_history(
            context,
            "opponent_offsides_history",
            "offsides_against_history",
        )

        target_shots = _extract_history(
            context,
            "shots_history",
            "team_shots_history",
        )

        opponent_shots = _extract_history(
            context,
            "shots_conceded_history",
            "opponent_shots_history",
            "team_opponent_shots_history",
        )

        target_big_chances = _extract_history(
            context,
            "big_chances_history",
            "team_big_chances_history",
        )

        opponent_big_chances = _extract_history(
            context,
            "big_chances_against_history",
            "opponent_big_chances_history",
        )

        target_corners = _extract_history(
            context,
            "corners_history",
            "team_corners_history",
            "corners_for_history",
        )

        opponent_corners = _extract_history(
            context,
            "opponent_corners_history",
            "corners_against_history",
        )

        # ====================================================
        # 2. OPPONENT EVIDENCE
        # ====================================================

        possession_advantage = (
            _weighted_possession_advantage(
                target_possession,
                opponent_possession,
                self.temporal_weights,
            )
        )

        passes_advantage = (
            _weighted_pair_advantage(
                target_passes,
                opponent_passes,
                self.temporal_weights,
            )
        )

        accuracy_advantage = (
            _weighted_accuracy_advantage(
                target_accuracy,
                opponent_accuracy,
                self.temporal_weights,
            )
        )

        crosses_advantage = (
            _weighted_pair_advantage(
                target_crosses,
                opponent_crosses,
                self.temporal_weights,
            )
        )

        throwins_advantage = (
            _weighted_pair_advantage(
                target_throwins,
                opponent_throwins,
                self.temporal_weights,
            )
        )

        offsides_advantage = (
            _weighted_pair_advantage(
                target_offsides,
                opponent_offsides,
                self.temporal_weights,
            )
        )

        shots_advantage = (
            _weighted_pair_advantage(
                target_shots,
                opponent_shots,
                self.temporal_weights,
            )
        )

        big_chances_advantage = (
            _weighted_pair_advantage(
                target_big_chances,
                opponent_big_chances,
                self.temporal_weights,
            )
        )

        corners_advantage = (
            _weighted_pair_advantage(
                target_corners,
                opponent_corners,
                self.temporal_weights,
            )
        )

        # ====================================================
        # 3. RAW COMPONENTS
        # ====================================================

        raw_components: Dict[
            str,
            Optional[float],
        ] = {

            "possession": possession_advantage,

            "passes": passes_advantage,

            "accuracy": accuracy_advantage,

            "crosses": crosses_advantage,

            "throwins": throwins_advantage,

            "offsides": offsides_advantage,

            "shots": shots_advantage,

            "big_chances": big_chances_advantage,

            "corners": corners_advantage,
        }

        # ====================================================
        # 4. BLOCKS
        # ====================================================

        control_block = self._calculate_control(
            possession_advantage,
            passes_advantage,
            accuracy_advantage,
        )

        progression_block = (
            self._calculate_progression(
                crosses_advantage,
                throwins_advantage,
                offsides_advantage,
            )
        )

        pressure_block = (
            self._calculate_pressure(
                shots_advantage,
                big_chances_advantage,
            )
        )

        # ====================================================
        # 5. CONTROL RAW
        # ====================================================

        control_raw = (
            self._calculate_control_raw(
                control_block,
                progression_block,
                pressure_block,
            )
        )

        # ====================================================
        # 6. OPPONENT SIGNAL
        # ====================================================

        opponent_signal = self._apply_tanh(
            control_raw
        )

        # ====================================================
        # 7. SELF STATE
        #
        # Только собственная история target_team.
        #
        # Не используем:
        #   fixed league baseline
        #   rating
        #   opponent result
        #   future result
        # ====================================================

        self_possession = (
            _weighted_self_state(
                target_possession,
                self.temporal_weights,
            )
        )

        self_passes = (
            _weighted_self_state(
                target_passes,
                self.temporal_weights,
            )
        )

        self_accuracy = (
            _weighted_self_state(
                target_accuracy,
                self.temporal_weights,
            )
        )

        self_signal = _combine_optional(
            (
                (
                    self_possession,
                    CONTROL_POSSESSION_WEIGHT,
                ),
                (
                    self_passes,
                    CONTROL_PASSES_WEIGHT,
                ),
                (
                    self_accuracy,
                    CONTROL_ACCURACY_WEIGHT,
                ),
            )
        )

        if self_signal is not None:
            self_signal = _clamp(
                math.tanh(
                    SELF_K * self_signal
                )
            )

        # ====================================================
        # 8. SELF DIAGNOSTIC VALUES
        #
        # Без искусственных baseline 300 / 60 / 50.
        # ====================================================

        self_norm = self._self_norm(
            target_possession,
            target_passes,
            target_accuracy,
        )

        self_std = self._self_std(
            target_possession,
            target_passes,
            target_accuracy,
        )

        self_z_score = self._self_z_score(
            self_signal,
            self_std,
        )

        # ====================================================
        # 9. FINAL CONTROL EVIDENCE
        #
        # opponent evidence 65%
        # self-state evidence 35%
        #
        # Это внутреннее объединение FormControl.
        # Это НЕ Brain weighting.
        # ====================================================

        final_signal = self._combine_signals(
            opponent_signal,
            self_signal,
        )

        if final_signal is not None:
            final_signal = _clamp(
                final_signal
            )

        # ====================================================
        # 10. STRENGTH
        # ====================================================

        control_strength = (
            abs(final_signal)
            if final_signal is not None
            else None
        )

        # ====================================================
        # 11. QUALITY
        # ====================================================

        data_quality = self._data_quality(
            raw_components
        )

        sample_size = self._sample_size(
            raw_components
        )

        # ====================================================
        # 12. DIAGNOSTICS
        # ====================================================

        diagnostics = self._build_diagnostics(
            raw_components=raw_components,
            control_block=control_block,
            progression_block=progression_block,
            pressure_block=pressure_block,
            control_raw=control_raw,
            opponent_signal=opponent_signal,
            self_signal=self_signal,
            final_signal=final_signal,
            self_norm=self_norm,
            self_std=self_std,
            self_z_score=self_z_score,
            corners_adv=corners_advantage,
            target_team=target_team,
            opponent_team=opponent_team,
            venue=venue,
        )

        # ====================================================
        # 13. RESULT
        # ====================================================

        return ControlResult(

            version=self.VERSION,

            target_team=target_team,

            opponent_team=opponent_team,

            venue=venue,

            control_signal=final_signal,

            control_strength=control_strength,

            control_block=control_block,

            progression_block=progression_block,

            pressure_block=pressure_block,

            opponent_signal=opponent_signal,

            self_signal=self_signal,

            self_norm=self_norm,

            self_std=self_std,

            self_z_score=self_z_score,

            corners_signal=corners_advantage,

            raw_components=raw_components,

            formula_status=self.FORMULA_STATUS,

            data_quality=data_quality,

            sample_size=sample_size,

            diagnostics=diagnostics,
        )

    # ========================================================
    # CONTROL BLOCK
    # ========================================================

    def _calculate_control(
        self,
        possession: Optional[float],
        passes: Optional[float],
        accuracy: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Control block.

        Formula:

            0.40 possession
          + 0.35 passes
          + 0.25 accuracy
        """

        components = {
            "possession": possession,
            "passes": passes,
            "accuracy": accuracy,
        }

        values = [
            (
                possession,
                CONTROL_POSSESSION_WEIGHT,
            ),
            (
                passes,
                CONTROL_PASSES_WEIGHT,
            ),
            (
                accuracy,
                CONTROL_ACCURACY_WEIGHT,
            ),
        ]

        normalized = _combine_optional(
            values
        )

        if normalized is None:
            return None

        available = [
            value
            for value, _ in values
            if value is not None
        ]

        return ControlBlock(
            raw=normalized,
            normalized=normalized,
            components=components,
            data_quality=(
                len(available)
                / len(values)
            ),
            sample_size=len(available),
        )

    # ========================================================
    # PROGRESSION BLOCK
    # ========================================================

    def _calculate_progression(
        self,
        crosses: Optional[float],
        throwins: Optional[float],
        offsides: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Progression block.

        Formula:

            0.40 crosses
          + 0.35 throw-ins
          + 0.25 offsides
        """

        components = {
            "crosses": crosses,
            "throwins": throwins,
            "offsides": offsides,
        }

        values = [
            (
                crosses,
                PROGRESSION_CROSSES_WEIGHT,
            ),
            (
                throwins,
                PROGRESSION_THROWINS_WEIGHT,
            ),
            (
                offsides,
                PROGRESSION_OFFSIDES_WEIGHT,
            ),
        ]

        normalized = _combine_optional(
            values
        )

        if normalized is None:
            return None

        available = [
            value
            for value, _ in values
            if value is not None
        ]

        return ControlBlock(
            raw=normalized,
            normalized=normalized,
            components=components,
            data_quality=(
                len(available)
                / len(values)
            ),
            sample_size=len(available),
        )

    # ========================================================
    # PRESSURE BLOCK
    # ========================================================

    def _calculate_pressure(
        self,
        shots: Optional[float],
        big_chances: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Pressure block.

        Formula:

            0.60 shots
          + 0.40 big chances
        """

        components = {
            "shots": shots,
            "big_chances": big_chances,
        }

        values = [
            (
                shots,
                PRESSURE_SHOTS_WEIGHT,
            ),
            (
                big_chances,
                PRESSURE_BIG_CHANCES_WEIGHT,
            ),
        ]

        normalized = _combine_optional(
            values
        )

        if normalized is None:
            return None

        available = [
            value
            for value, _ in values
            if value is not None
        ]

        return ControlBlock(
            raw=normalized,
            normalized=normalized,
            components=components,
            data_quality=(
                len(available)
                / len(values)
            ),
            sample_size=len(available),
        )

    # ========================================================
    # CONTROL RAW
    # ========================================================

    def _calculate_control_raw(
        self,
        control: Optional[ControlBlock],
        progression: Optional[ControlBlock],
        pressure: Optional[ControlBlock],
    ) -> Optional[float]:
        """
        Formula:

            ControlRaw =
                0.50 * Control
              + 0.25 * Progression
              + 0.25 * Pressure

        Missing blocks:
            excluded from denominator.

        Missing != 0.
        """

        components = [
            (
                control.normalized
                if control is not None
                else None,
                CONTROL_WEIGHT,
            ),
            (
                progression.normalized
                if progression is not None
                else None,
                PROGRESSION_WEIGHT,
            ),
            (
                pressure.normalized
                if pressure is not None
                else None,
                PRESSURE_WEIGHT,
            ),
        ]

        return _combine_optional(
            components
        )

    # ========================================================
    # SELF NORM
    # ========================================================

    def _self_norm(
        self,
        possession: Sequence[Optional[float]],
        passes: Sequence[Optional[float]],
        accuracy: Sequence[Optional[float]],
    ) -> Optional[float]:
        """
        Собственная историческая норма.

        Никаких league baselines.
        Никаких rating baselines.
        """

        possession_mean = _mean(
            possession
        )

        passes_mean = _mean(
            passes
        )

        accuracy_mean = _mean(
            accuracy
        )

        components: List[
            Tuple[Optional[float], float]
        ] = []

        if possession_mean is not None:
            components.append(
                (
                    possession_mean,
                    CONTROL_POSSESSION_WEIGHT,
                )
            )

        if passes_mean is not None:
            components.append(
                (
                    passes_mean,
                    CONTROL_PASSES_WEIGHT,
                )
            )

        if accuracy_mean is not None:
            components.append(
                (
                    accuracy_mean,
                    CONTROL_ACCURACY_WEIGHT,
                )
            )

        if not components:
            return None

        return (
            sum(
                value * weight
                for value, weight in components
            )
            /
            sum(
                weight
                for _, weight in components
            )
        )

    # ========================================================
    # SELF STD
    # ========================================================

    def _self_std(
        self,
        possession: Sequence[Optional[float]],
        passes: Sequence[Optional[float]],
        accuracy: Sequence[Optional[float]],
    ) -> Optional[float]:
        """
        Диагностическая агрегированная вариативность.

        Не используется как скрытый multiplier.
        """

        stds: List[
            Tuple[float, float]
        ] = []

        possession_std = _std(
            possession
        )

        passes_std = _std(
            passes
        )

        accuracy_std = _std(
            accuracy
        )

        if possession_std is not None:
            stds.append(
                (
                    possession_std,
                    CONTROL_POSSESSION_WEIGHT,
                )
            )

        if passes_std is not None:
            stds.append(
                (
                    passes_std,
                    CONTROL_PASSES_WEIGHT,
                )
            )

        if accuracy_std is not None:
            stds.append(
                (
                    accuracy_std,
                    CONTROL_ACCURACY_WEIGHT,
                )
            )

        if not stds:
            return None

        denominator = sum(
            weight
            for _, weight in stds
        )

        if denominator <= EPSILON:
            return None

        return (
            sum(
                value * weight
                for value, weight in stds
            )
            / denominator
        )

    # ========================================================
    # SELF Z-SCORE
    # ========================================================

    def _self_z_score(
        self,
        self_signal: Optional[float],
        self_std: Optional[float],
    ) -> Optional[float]:
        """
        Диагностический показатель.

        Важно:
        это не вероятность и не confidence.
        """

        if self_signal is None:
            return None

        if (
            self_std is None
            or self_std <= EPSILON
        ):
            return None

        return (
            self_signal
            / self_std
        )

    # ========================================================
    # TANH
    # ========================================================

    def _apply_tanh(
        self,
        value: Optional[float],
    ) -> Optional[float]:

        if value is None:
            return None

        return _clamp(
            math.tanh(value)
        )

    # ========================================================
    # SIGNAL COMBINATION
    # ========================================================

    def _combine_signals(
        self,
        opponent_signal: Optional[float],
        self_signal: Optional[float],
    ) -> Optional[float]:
        """
        Internal FormControl synthesis:

            65% opponent evidence
            35% self-state evidence

        Это всё ещё FormControl evidence.

        Это НЕ Winner synthesis.
        """

        return _combine_optional(
            (
                (
                    opponent_signal,
                    OPPONENT_WEIGHT,
                ),
                (
                    self_signal,
                    SELF_WEIGHT,
                ),
            )
        )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    def _data_quality(
        self,
        components: Dict[
            str,
            Optional[float],
        ],
    ) -> Optional[float]:
        """
        Покрытие доступных component evidence.
        """

        if not components:
            return None

        available = [
            value
            for value in components.values()
            if value is not None
        ]

        if not available:
            return None

        return (
            len(available)
            / len(components)
        )

    # ========================================================
    # SAMPLE SIZE
    # ========================================================

    def _sample_size(
        self,
        components: Dict[
            str,
            Optional[float],
        ],
    ) -> int:
        """
        Для ControlResult это число доступных evidence
        components, а не число матчей.

        Реальный sample size каждой истории определяется
        исходным FormContext и диагностикой конкретного блока.
        """

        return sum(
            value is not None
            for value in components.values()
        )

    # ========================================================
    # DIAGNOSTICS
    # ========================================================

    def _build_diagnostics(
        self,
        *,
        raw_components: Dict[
            str,
            Optional[float],
        ],
        control_block: Optional[ControlBlock],
        progression_block: Optional[ControlBlock],
        pressure_block: Optional[ControlBlock],
        control_raw: Optional[float],
        opponent_signal: Optional[float],
        self_signal: Optional[float],
        final_signal: Optional[float],
        self_norm: Optional[float],
        self_std: Optional[float],
        self_z_score: Optional[float],
        corners_adv: Optional[float],
        target_team: Optional[str],
        opponent_team: Optional[str],
        venue: Optional[str],
    ) -> Dict[str, Any]:

        return {

            "model": "FormControl",

            "version": self.VERSION,

            "formula_status": (
                self.FORMULA_STATUS
            ),

            "model_role": (
                "control_evidence_organ"
            ),

            "target_team": target_team,

            "opponent_team": opponent_team,

            "venue": venue,

            # ------------------------------------------------
            # RAW COMPONENTS
            # ------------------------------------------------

            "raw_components": raw_components,

            # ------------------------------------------------
            # BLOCKS
            # ------------------------------------------------

            "control_block": (
                control_block.to_dict()
                if control_block
                else None
            ),

            "progression_block": (
                progression_block.to_dict()
                if progression_block
                else None
            ),

            "pressure_block": (
                pressure_block.to_dict()
                if pressure_block
                else None
            ),

            # ------------------------------------------------
            # SIGNALS
            # ------------------------------------------------

            "control_raw": control_raw,

            "opponent_signal": opponent_signal,

            "self_signal": self_signal,

            "final_signal": final_signal,

            # ------------------------------------------------
            # SELF DIAGNOSTICS
            # ------------------------------------------------

            "self_norm": self_norm,

            "self_std": self_std,

            "self_z_score": self_z_score,

            "self_k": SELF_K,

            # ------------------------------------------------
            # INTERNAL WEIGHTS
            # ------------------------------------------------

            "opponent_weight": (
                OPPONENT_WEIGHT
            ),

            "self_weight": SELF_WEIGHT,

            "control_weight": (
                CONTROL_WEIGHT
            ),

            "progression_weight": (
                PROGRESSION_WEIGHT
            ),

            "pressure_weight": (
                PRESSURE_WEIGHT
            ),

            "temporal_weights": list(
                self.temporal_weights
            ),

            # ------------------------------------------------
            # CORNERS
            # ------------------------------------------------

            "corners_signal": corners_adv,

            "corners_excluded_from_control_raw": (
                True
            ),

            # ------------------------------------------------
            # PROHIBITED DEPENDENCIES
            # ------------------------------------------------

            "form_win_used": False,

            "goal_model_used": False,

            "probability_model_used": False,

            "score_predictor_used": False,

            "rating_used": False,

            "database_used": False,

            "future_result_used": False,

            "winner_prediction_generated": False,

            "winner_probability_generated": False,

            "confidence_generated": False,

            "risk_generated": False,

            # ------------------------------------------------
            # DATA CONTRACT
            # ------------------------------------------------

            "missing_is_zero": False,

            "none_is_zero": False,

            "absolute_league_baseline_used": False,

            "hidden_brain_multiplier": False,

            # ------------------------------------------------
            # ARCHITECTURE
            # ------------------------------------------------

            "winner_synthesis_owner": (
                "FAJBrain/AnalysisEngine"
            ),

            "state_role": (
                "diagnostic_evidence"
            ),

            "contract": (
                "MATHEMATICAL_CONTRACT_V1"
            ),

            "status": (
                "RESEARCH_FORMULA"
            ),
        }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def analyze_control(
    context: Any,
    target_team: Optional[str] = None,
    opponent_team: Optional[str] = None,
    venue: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Удобная функциональная оболочка.

    Example:

        result = analyze_control(
            context,
            target_team="Зенит",
            opponent_team="Спартак",
            venue="home",
        )

        signal = result["control_signal"]
    """

    model = FormControl()

    return model.analyze(
        context,
        target_team=target_team,
        opponent_team=opponent_team,
        venue=venue,
    ).to_dict()


# ============================================================
# COMPARE CONTROL
# ============================================================

def compare_control(
    home_context: Any,
    away_context: Any,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Сравнение FormControl двух отдельных контекстов.

    ВАЖНО:

    Эта функция НЕ выдаёт winner.

    Она возвращает только:

        home signal
        away signal
        relative evidence

    Это необходимо для последующего Brain/AnalysisEngine.
    """

    model = FormControl()

    home_result = model.analyze(
        home_context,
        target_team=home_team,
        opponent_team=away_team,
        venue="home",
    )

    away_result = model.analyze(
        away_context,
        target_team=away_team,
        opponent_team=home_team,
        venue="away",
    )

    home_signal = (
        home_result.control_signal
    )

    away_signal = (
        away_result.control_signal
    )

    if (
        home_signal is None
        or away_signal is None
    ):
        relative = None

    else:
        relative = _clamp(
            home_signal
            - away_signal
        )

    return {

        "home_control": (
            home_result.to_dict()
        ),

        "away_control": (
            away_result.to_dict()
        ),

        "home_signal": home_signal,

        "away_signal": away_signal,

        "relative_control": relative,

        "control_evidence_available": (
            relative is not None
        ),
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "FORM_CONTROL_VERSION",
    "FORMULA_STATUS",
    "TEMPORAL_WEIGHTS",
    "ControlBlock",
    "ControlResult",
    "FormControl",
    "analyze_control",
    "compare_control",
]
