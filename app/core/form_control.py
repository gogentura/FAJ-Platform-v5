#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PLATFORM — FORM CONTROL v1.1

Назначение:
    Измерить контроль игры через владение, пасы, точность,
    прогрессию (навесы, ауты, офсайды) и давление (удары, большие моменты).

Архитектура:
    FormContext → FormControl → ControlSignal

Принципы:
    - None ≠ 0
    - RESEARCH PARAMETERS
    - Компонент независим от FormWin и GoalModel
    - Сигнал ограничен через tanh
    - Явный target_team

Формула v1.1:
    1. Три блока: Control, Progression, Pressure
    2. ControlRaw = 0.50*Control + 0.25*Progression + 0.25*Pressure
    3. ControlSignal = tanh(ControlRaw)
    4. Учёт собственной нормы: 65% vs соперник + 35% vs норма (с std)
    5. Затухающий вес для 6 матчей: [0.08, 0.10, 0.13, 0.18, 0.23, 0.28]
    6. Corners — только диагностический сигнал (не влияет на ControlRaw)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# VERSION
# ============================================================

FORM_CONTROL_VERSION = "1.1"
FORMULA_STATUS = "RESEARCH_FORMULA"

# ============================================================
# RESEARCH PARAMETERS
# ============================================================

# Блок Control (контроль)
CONTROL_POSSESSION_WEIGHT = 0.40
CONTROL_PASSES_WEIGHT = 0.35
CONTROL_ACCURACY_WEIGHT = 0.25

# Блок Progression (прогрессия)
PROGRESSION_CROSSES_WEIGHT = 0.40
PROGRESSION_THROWINS_WEIGHT = 0.35
PROGRESSION_OFFSIDES_WEIGHT = 0.25

# Блок Pressure (давление)
PRESSURE_SHOTS_WEIGHT = 0.60
PRESSURE_BIG_CHANCES_WEIGHT = 0.40

# Итоговый ControlRaw
CONTROL_WEIGHT = 0.50
PROGRESSION_WEIGHT = 0.25
PRESSURE_WEIGHT = 0.25

# Сравнение с собственной нормой
OPPONENT_WEIGHT = 0.65
SELF_WEIGHT = 0.35

# SelfSignal: коэффициент и baseline
SELF_K = 2.0  # RESEARCH PARAMETER
SELF_EPS = 0.01
SELF_BASELINE_STD = 0.15  # если std недоступен

# Веса для временного затухания (M1 → M6)
TEMPORAL_WEIGHTS: Tuple[float, ...] = (0.08, 0.10, 0.13, 0.18, 0.23, 0.28)

# Максимальное влияние ControlSignal на Brain
MAX_CONTROL_INFLUENCE = 0.05  # ±5%


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """Безопасное преобразование в float. None остаётся None."""
    if value is None:
        return None
    try:
        result = float(value)
        if not math.isfinite(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _mean(values: List[Optional[float]]) -> Optional[float]:
    """Среднее арифметическое. None исключаются."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _std(values: List[Optional[float]]) -> Optional[float]:
    """Стандартное отклонение. None исключаются."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    mean_val = sum(clean) / len(clean)
    variance = sum((v - mean_val) ** 2 for v in clean) / len(clean)
    return math.sqrt(variance)


def _weighted_advantage(
    home_values: List[Optional[float]],
    away_values: List[Optional[float]],
    weights: Tuple[float, ...] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Вычисляет взвешенное преимущество с затуханием.
    
    Вес принадлежит матчу, а не позиции после удаления None.
    """
    if not home_values or not away_values:
        return None
    
    # Берём последние 6
    home = home_values[:6]
    away = away_values[:6]
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for i, (h, a) in enumerate(zip(home, away)):
        if h is not None and a is not None:
            total = h + a
            if total != 0:
                weight = weights[i] if i < len(weights) else 0.0
                advantage = (h - a) / total
                weighted_sum += weight * advantage
                total_weight += weight
    
    if total_weight == 0:
        return None
    
    return weighted_sum / total_weight


def _weighted_possession_advantage(
    home_values: List[Optional[float]],
    away_values: List[Optional[float]],
    weights: Tuple[float, ...] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Вычисляет взвешенное преимущество во владении.
    
    Formula: D_possession = (possession - 50) / 50
    """
    if not home_values or not away_values:
        return None
    
    home = home_values[:6]
    away = away_values[:6]
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for i, (h, a) in enumerate(zip(home, away)):
        if h is not None and a is not None:
            weight = weights[i] if i < len(weights) else 0.0
            h_norm = (h - 50.0) / 50.0
            a_norm = (a - 50.0) / 50.0
            advantage = h_norm - a_norm
            weighted_sum += weight * advantage
            total_weight += weight
    
    if total_weight == 0:
        return None
    
    return weighted_sum / total_weight


def _weighted_accuracy_advantage(
    home_values: List[Optional[float]],
    away_values: List[Optional[float]],
    weights: Tuple[float, ...] = TEMPORAL_WEIGHTS,
) -> Optional[float]:
    """
    Вычисляет взвешенное преимущество в точности пасов.
    
    Formula: D_accuracy = (home - away) / 100
    """
    if not home_values or not away_values:
        return None
    
    home = home_values[:6]
    away = away_values[:6]
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for i, (h, a) in enumerate(zip(home, away)):
        if h is not None and a is not None:
            weight = weights[i] if i < len(weights) else 0.0
            advantage = (h - a) / 100.0
            weighted_sum += weight * advantage
            total_weight += weight
    
    if total_weight == 0:
        return None
    
    return weighted_sum / total_weight


def _extract_history(
    context: Dict[str, Any],
    field_home: str,
    field_away: str,
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """Извлекает историю из FormContext для домашней и гостевой команды."""
    home_history = context.get(field_home, [])
    away_history = context.get(field_away, [])
    
    if not isinstance(home_history, list):
        home_history = []
    if not isinstance(away_history, list):
        away_history = []
    
    return home_history[:6], away_history[:6]


# ============================================================
# RESULT STRUCTURES
# ============================================================

@dataclass
class ControlBlock:
    """Результат одного блока контроля."""
    raw: Optional[float]
    normalized: Optional[float]
    components: Dict[str, Optional[float]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ControlResult:
    """Полный результат FormControl."""
    version: str
    target_team: Optional[str]
    opponent_team: Optional[str]
    venue: Optional[str]
    
    # Итоговый сигнал
    control_signal: Optional[float]  # [-1, 1]
    control_strength: Optional[float]  # [0, 1]
    
    # Блоки
    control_block: Optional[ControlBlock]
    progression_block: Optional[ControlBlock]
    pressure_block: Optional[ControlBlock]
    
    # Сравнение с соперником
    opponent_signal: Optional[float]
    
    # Сравнение с собственной нормой
    self_signal: Optional[float]
    self_norm: Optional[float]
    self_std: Optional[float]
    self_z_score: Optional[float]
    
    # Диагностические сигналы (не влияют на ControlRaw)
    corners_signal: Optional[float]
    
    # Сырые компоненты
    raw_components: Dict[str, Optional[float]]
    
    # Мета
    formula_status: str
    diagnostics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.control_block:
            result["control_block"] = self.control_block.to_dict()
        if self.progression_block:
            result["progression_block"] = self.progression_block.to_dict()
        if self.pressure_block:
            result["pressure_block"] = self.pressure_block.to_dict()
        return result


# ============================================================
# FORM CONTROL
# ============================================================

class FormControl:
    """
    Модель контроля игры v1.1.
    
    Вход:
        FormContext (с историческими данными)
    
    Выход:
        ControlResult с ограниченным сигналом [-1, 1]
    
    Принцип:
        - Не дублирует FormWin
        - Не рассчитывает xG
        - Не выдаёт вероятности
        - Только измеряет контроль
        - Явный target_team
    """
    
    VERSION = FORM_CONTROL_VERSION
    FORMULA_STATUS = FORMULA_STATUS
    
    def __init__(self) -> None:
        pass
    
    # ============================================================
    # PUBLIC API
    # ============================================================
    
    def analyze(
        self,
        context: Dict[str, Any],
        target_team: str,
        opponent_team: str,
        venue: str = "home",
    ) -> ControlResult:
        """
        Анализирует контроль игры для целевой команды.
        
        Parameters
        ----------
        context : Dict[str, Any]
            Enriched FormContext с историями
        target_team : str
            Команда, для которой считаем сигнал
        opponent_team : str
            Команда-соперник
        venue : str
            "home" или "away" (для целевой команды)
        
        Returns
        -------
        ControlResult
            Результат анализа контроля
        """
        # ============================================================
        # 1. Извлекаем истории
        # ============================================================
        
        home_possession, away_possession = _extract_history(
            context, "possession_history", "opponent_possession_history"
        )
        home_passes, away_passes = _extract_history(
            context, "passes_history", "opponent_passes_history"
        )
        home_accuracy, away_accuracy = _extract_history(
            context, "pass_accuracy_history", "opponent_pass_accuracy_history"
        )
        home_crosses, away_crosses = _extract_history(
            context, "crosses_history", "opponent_crosses_history"
        )
        home_throwins, away_throwins = _extract_history(
            context, "throw_ins_history", "opponent_throw_ins_history"
        )
        home_offsides, away_offsides = _extract_history(
            context, "offsides_history", "opponent_offsides_history"
        )
        home_shots, away_shots = _extract_history(
            context, "shots_history", "shots_conceded_history"
        )
        home_big_chances, away_big_chances = _extract_history(
            context, "big_chances_history", "big_chances_against_history"
        )
        home_corners, away_corners = _extract_history(
            context, "corners_for_history", "corners_against_history"
        )
        
        # ============================================================
        # 2. Вычисляем нормализованные преимущества
        # ============================================================
        
        # Control
        possession_adv = _weighted_possession_advantage(
            home_possession, away_possession
        )
        passes_adv = _weighted_advantage(home_passes, away_passes)
        accuracy_adv = _weighted_accuracy_advantage(home_accuracy, away_accuracy)
        
        # Progression
        crosses_adv = _weighted_advantage(home_crosses, away_crosses)
        throwins_adv = _weighted_advantage(home_throwins, away_throwins)
        offsides_adv = _weighted_advantage(home_offsides, away_offsides)
        
        # Pressure
        shots_adv = _weighted_advantage(home_shots, away_shots)
        big_chances_adv = _weighted_advantage(home_big_chances, away_big_chances)
        
        # Corners (диагностика)
        corners_adv = _weighted_advantage(home_corners, away_corners)
        
        # ============================================================
        # 3. Собираем компоненты
        # ============================================================
        
        raw_components = {
            "possession": possession_adv,
            "passes": passes_adv,
            "accuracy": accuracy_adv,
            "crosses": crosses_adv,
            "throwins": throwins_adv,
            "offsides": offsides_adv,
            "shots": shots_adv,
            "big_chances": big_chances_adv,
            "corners": corners_adv,
        }
        
        # ============================================================
        # 4. Вычисляем блоки
        # ============================================================
        
        control_block = self._calculate_control(
            possession_adv, passes_adv, accuracy_adv
        )
        progression_block = self._calculate_progression(
            crosses_adv, throwins_adv, offsides_adv
        )
        pressure_block = self._calculate_pressure(
            shots_adv, big_chances_adv
        )
        
        # ============================================================
        # 5. Вычисляем ControlRaw
        # ============================================================
        
        control_raw = self._calculate_control_raw(
            control_block, progression_block, pressure_block
        )
        
        # ============================================================
        # 6. Применяем tanh
        # ============================================================
        
        control_signal = self._apply_tanh(control_raw)
        
        # ============================================================
        # 7. Сравнение с собственной нормой
        # ============================================================
        
        self_norm, self_std = self._calculate_norm_and_std(
            home_possession, home_passes, home_accuracy
        )
        self_z_score = self._calculate_z_score(
            home_possession, home_passes, home_accuracy,
            self_norm, self_std
        )
        self_signal = self._calculate_self_signal(self_z_score)
        
        opponent_signal = control_signal
        
        # ============================================================
        # 8. Итоговый сигнал
        # ============================================================
        
        final_signal = self._combine_signals(
            opponent_signal, self_signal
        )
        
        # ============================================================
        # 9. Сила сигнала
        # ============================================================
        
        control_strength = abs(final_signal) if final_signal is not None else None
        
        # ============================================================
        # 10. Диагностика
        # ============================================================
        
        diagnostics = self._build_diagnostics(
            raw_components=raw_components,
            control_block=control_block,
            progression_block=progression_block,
            pressure_block=pressure_block,
            control_raw=control_raw,
            control_signal=control_signal,
            opponent_signal=opponent_signal,
            self_signal=self_signal,
            self_norm=self_norm,
            self_std=self_std,
            self_z_score=self_z_score,
            corners_adv=corners_adv,
            target_team=target_team,
            opponent_team=opponent_team,
            venue=venue,
        )
        
        # ============================================================
        # 11. Возвращаем результат
        # ============================================================
        
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
            corners_signal=corners_adv,
            raw_components=raw_components,
            formula_status=self.FORMULA_STATUS,
            diagnostics=diagnostics,
        )
    
    # ============================================================
    # BLOCK CALCULATIONS
    # ============================================================
    
    def _calculate_control(
        self,
        possession: Optional[float],
        passes: Optional[float],
        accuracy: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Вычисляет блок Control (контроль).
        
        Formula:
            C = 0.40*possession + 0.35*passes + 0.25*accuracy
        """
        components = {
            "possession": possession,
            "passes": passes,
            "accuracy": accuracy,
        }
        
        raw = 0.0
        has_value = False
        
        if possession is not None:
            raw += CONTROL_POSSESSION_WEIGHT * possession
            has_value = True
        if passes is not None:
            raw += CONTROL_PASSES_WEIGHT * passes
            has_value = True
        if accuracy is not None:
            raw += CONTROL_ACCURACY_WEIGHT * accuracy
            has_value = True
        
        if not has_value:
            return None
        
        total_weight = 0.0
        if possession is not None:
            total_weight += CONTROL_POSSESSION_WEIGHT
        if passes is not None:
            total_weight += CONTROL_PASSES_WEIGHT
        if accuracy is not None:
            total_weight += CONTROL_ACCURACY_WEIGHT
        
        if total_weight == 0:
            return None
        
        normalized = raw / total_weight
        
        return ControlBlock(
            raw=raw,
            normalized=normalized,
            components=components,
        )
    
    def _calculate_progression(
        self,
        crosses: Optional[float],
        throwins: Optional[float],
        offsides: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Вычисляет блок Progression (прогрессия).
        
        Formula:
            P = 0.40*crosses + 0.35*throwins + 0.25*offsides
        """
        components = {
            "crosses": crosses,
            "throwins": throwins,
            "offsides": offsides,
        }
        
        raw = 0.0
        has_value = False
        
        if crosses is not None:
            raw += PROGRESSION_CROSSES_WEIGHT * crosses
            has_value = True
        if throwins is not None:
            raw += PROGRESSION_THROWINS_WEIGHT * throwins
            has_value = True
        if offsides is not None:
            raw += PROGRESSION_OFFSIDES_WEIGHT * offsides
            has_value = True
        
        if not has_value:
            return None
        
        total_weight = 0.0
        if crosses is not None:
            total_weight += PROGRESSION_CROSSES_WEIGHT
        if throwins is not None:
            total_weight += PROGRESSION_THROWINS_WEIGHT
        if offsides is not None:
            total_weight += PROGRESSION_OFFSIDES_WEIGHT
        
        if total_weight == 0:
            return None
        
        normalized = raw / total_weight
        
        return ControlBlock(
            raw=raw,
            normalized=normalized,
            components=components,
        )
    
    def _calculate_pressure(
        self,
        shots: Optional[float],
        big_chances: Optional[float],
    ) -> Optional[ControlBlock]:
        """
        Вычисляет блок Pressure (давление).
        
        Formula:
            R = 0.60*shots + 0.40*big_chances
        """
        components = {
            "shots": shots,
            "big_chances": big_chances,
        }
        
        raw = 0.0
        has_value = False
        
        if shots is not None:
            raw += PRESSURE_SHOTS_WEIGHT * shots
            has_value = True
        if big_chances is not None:
            raw += PRESSURE_BIG_CHANCES_WEIGHT * big_chances
            has_value = True
        
        if not has_value:
            return None
        
        total_weight = 0.0
        if shots is not None:
            total_weight += PRESSURE_SHOTS_WEIGHT
        if big_chances is not None:
            total_weight += PRESSURE_BIG_CHANCES_WEIGHT
        
        if total_weight == 0:
            return None
        
        normalized = raw / total_weight
        
        return ControlBlock(
            raw=raw,
            normalized=normalized,
            components=components,
        )
    
    def _calculate_control_raw(
        self,
        control: Optional[ControlBlock],
        progression: Optional[ControlBlock],
        pressure: Optional[ControlBlock],
    ) -> Optional[float]:
        """
        Вычисляет ControlRaw из трёх блоков.
        
        Formula:
            ControlRaw = 0.50*Control + 0.25*Progression + 0.25*Pressure
        """
        raw = 0.0
        total_weight = 0.0
        
        if control is not None and control.normalized is not None:
            raw += CONTROL_WEIGHT * control.normalized
            total_weight += CONTROL_WEIGHT
        
        if progression is not None and progression.normalized is not None:
            raw += PROGRESSION_WEIGHT * progression.normalized
            total_weight += PROGRESSION_WEIGHT
        
        if pressure is not None and pressure.normalized is not None:
            raw += PRESSURE_WEIGHT * pressure.normalized
            total_weight += PRESSURE_WEIGHT
        
        if total_weight == 0:
            return None
        
        return raw / total_weight
    
    # ============================================================
    # SELF SIGNAL
    # ============================================================
    
    def _calculate_norm_and_std(
        self,
        possession_history: List[Optional[float]],
        passes_history: List[Optional[float]],
        accuracy_history: List[Optional[float]],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Вычисляет норму и стандартное отклонение команды.
        """
        # Нормализуем каждый показатель
        possession_norm = None
        passes_norm = None
        accuracy_norm = None
        
        possession_mean = _mean(possession_history)
        passes_mean = _mean(passes_history)
        accuracy_mean = _mean(accuracy_history)
        
        if possession_mean is not None:
            possession_norm = (possession_mean - 50.0) / 50.0
        if passes_mean is not None:
            passes_norm = (passes_mean - 300.0) / 300.0
        if accuracy_mean is not None:
            accuracy_norm = (accuracy_mean - 60.0) / 30.0
        
        # Агрегируем норму
        values = []
        weights = []
        
        if possession_norm is not None:
            values.append(possession_norm)
            weights.append(0.40)
        if passes_norm is not None:
            values.append(passes_norm)
            weights.append(0.35)
        if accuracy_norm is not None:
            values.append(accuracy_norm)
            weights.append(0.25)
        
        if not values:
            return None, None
        
        total_weight = sum(weights)
        if total_weight == 0:
            return None, None
        
        norm = sum(v * w for v, w in zip(values, weights)) / total_weight
        
        # Вычисляем стандартное отклонение для каждого показателя
        possession_std = _std(possession_history)
        passes_std = _std(passes_history)
        accuracy_std = _std(accuracy_history)
        
        # Нормализуем std
        possession_std_norm = possession_std / 50.0 if possession_std is not None else None
        passes_std_norm = passes_std / 300.0 if passes_std is not None else None
        accuracy_std_norm = accuracy_std / 30.0 if accuracy_std is not None else None
        
        # Агрегируем std
        std_values = []
        std_weights = []
        
        if possession_std_norm is not None:
            std_values.append(possession_std_norm)
            std_weights.append(0.40)
        if passes_std_norm is not None:
            std_values.append(passes_std_norm)
            std_weights.append(0.35)
        if accuracy_std_norm is not None:
            std_values.append(accuracy_std_norm)
            std_weights.append(0.25)
        
        if not std_values:
            return norm, None
        
        total_std_weight = sum(std_weights)
        if total_std_weight == 0:
            return norm, None
        
        std = sum(v * w for v, w in zip(std_values, std_weights)) / total_std_weight
        
        return norm, std
    
    def _calculate_z_score(
        self,
        possession_history: List[Optional[float]],
        passes_history: List[Optional[float]],
        accuracy_history: List[Optional[float]],
        norm: Optional[float],
        std: Optional[float],
    ) -> Optional[float]:
        """
        Вычисляет Z-score текущего состояния относительно нормы.
        """
        if norm is None:
            return None
        
        # Вычисляем текущее состояние (последние 6 матчей с весом)
        possession_recent = possession_history[-6:] if possession_history else []
        passes_recent = passes_history[-6:] if passes_history else []
        accuracy_recent = accuracy_history[-6:] if accuracy_history else []
        
        possession_current = _weighted_advantage(
            possession_recent, [50.0] * len(possession_recent)
        )
        passes_current = _weighted_advantage(
            passes_recent, [300.0] * len(passes_recent)
        )
        accuracy_current = _weighted_advantage(
            accuracy_recent, [60.0] * len(accuracy_recent)
        )
        
        # Агрегируем текущее состояние
        values = []
        weights = []
        
        if possession_current is not None:
            values.append(possession_current)
            weights.append(0.40)
        if passes_current is not None:
            values.append(passes_current)
            weights.append(0.35)
        if accuracy_current is not None:
            values.append(accuracy_current)
            weights.append(0.25)
        
        if not values:
            return None
        
        total_weight = sum(weights)
        if total_weight == 0:
            return None
        
        current = sum(v * w for v, w in zip(values, weights)) / total_weight
        
        # Z-score
        if std is not None and std > SELF_EPS:
            return (current - norm) / std
        else:
            return (current - norm) / SELF_BASELINE_STD
    
    def _calculate_self_signal(self, z_score: Optional[float]) -> Optional[float]:
        """
        Вычисляет SelfSignal из Z-score.
        
        Formula:
            SelfSignal = tanh(K * z_score)
        """
        if z_score is None:
            return None
        return math.tanh(SELF_K * z_score)
    
    # ============================================================
    # SIGNAL COMBINATION
    # ============================================================
    
    def _apply_tanh(self, value: Optional[float]) -> Optional[float]:
        """
        Применяет tanh для ограничения сигнала.
        
        tanh(x) ∈ [-1, 1]
        """
        if value is None:
            return None
        return math.tanh(value)
    
    def _combine_signals(
        self,
        opponent_signal: Optional[float],
        self_signal: Optional[float],
    ) -> Optional[float]:
        """
        Комбинирует сигналы: 65% vs соперник + 35% vs собственная норма.
        """
        if opponent_signal is None and self_signal is None:
            return None
        
        result = 0.0
        total_weight = 0.0
        
        if opponent_signal is not None:
            result += OPPONENT_WEIGHT * opponent_signal
            total_weight += OPPONENT_WEIGHT
        
        if self_signal is not None:
            result += SELF_WEIGHT * self_signal
            total_weight += SELF_WEIGHT
        
        if total_weight == 0:
            return None
        
        return result / total_weight
    
    # ============================================================
    # DIAGNOSTICS
    # ============================================================
    
    def _build_diagnostics(
        self,
        raw_components: Dict[str, Optional[float]],
        control_block: Optional[ControlBlock],
        progression_block: Optional[ControlBlock],
        pressure_block: Optional[ControlBlock],
        control_raw: Optional[float],
        control_signal: Optional[float],
        opponent_signal: Optional[float],
        self_signal: Optional[float],
        self_norm: Optional[float],
        self_std: Optional[float],
        self_z_score: Optional[float],
        corners_adv: Optional[float],
        target_team: str,
        opponent_team: str,
        venue: str,
    ) -> Dict[str, Any]:
        """
        Строит диагностический блок.
        """
        return {
            "model": "FormControl",
            "version": self.VERSION,
            "formula_status": self.FORMULA_STATUS,
            "target_team": target_team,
            "opponent_team": opponent_team,
            "venue": venue,
            "raw_components": raw_components,
            "control_block": control_block.to_dict() if control_block else None,
            "progression_block": progression_block.to_dict() if progression_block else None,
            "pressure_block": pressure_block.to_dict() if pressure_block else None,
            "corners_signal": corners_adv,  # Только диагностика
            "control_raw": control_raw,
            "control_signal": control_signal,
            "opponent_signal": opponent_signal,
            "self_signal": self_signal,
            "self_norm": self_norm,
            "self_std": self_std,
            "self_z_score": self_z_score,
            "self_k": SELF_K,
            "opponent_weight": OPPONENT_WEIGHT,
            "self_weight": SELF_WEIGHT,
            "control_weight": CONTROL_WEIGHT,
            "progression_weight": PROGRESSION_WEIGHT,
            "pressure_weight": PRESSURE_WEIGHT,
            "temporal_weights": list(TEMPORAL_WEIGHTS),
            "max_influence": MAX_CONTROL_INFLUENCE,
            "status": "RESEARCH_FORMULA",
            "note": "ControlSignal ограничен через tanh. Влияние на Brain не более ±5%.",
            "corners_excluded_from_raw": True,
        }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def analyze_control(
    context: Dict[str, Any],
    target_team: str,
    opponent_team: str,
    venue: str = "home",
) -> Dict[str, Any]:
    """
    Удобная обёртка для FormControl.analyze().
    
    Example
    -------
    result = analyze_control(
        home_enriched_context,
        target_team="Зенит",
        opponent_team="Спартак",
        venue="home",
    )
    result["control_signal"]
    """
    model = FormControl()
    return model.analyze(context, target_team, opponent_team, venue).to_dict()


def compare_control(
    context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Dict[str, Any]:
    """
    Сравнивает контроль двух команд.
    
    Returns
    -------
    {
        "home_control": ...,
        "away_control": ...,
        "control_advantage": "HOME" | "AWAY" | "EQUAL",
        "control_strength": ...,
    }
    """
    home_result = analyze_control(context, home_team, away_team, venue="home")
    away_result = analyze_control(context, away_team, home_team, venue="away")
    
    home_signal = home_result.get("control_signal")
    away_signal = away_result.get("control_signal")
    
    if home_signal is None and away_signal is None:
        advantage = "EQUAL"
        strength = 0.0
    elif home_signal is None:
        advantage = "AWAY"
        strength = abs(away_signal) if away_signal is not None else 0.0
    elif away_signal is None:
        advantage = "HOME"
        strength = abs(home_signal) if home_signal is not None else 0.0
    else:
        diff = home_signal - away_signal
        if diff > 0.10:
            advantage = "HOME"
            strength = min(abs(diff), 1.0)
        elif diff < -0.10:
            advantage = "AWAY"
            strength = min(abs(diff), 1.0)
        else:
            advantage = "EQUAL"
            strength = abs(diff)
    
    return {
        "home_control": home_result,
        "away_control": away_result,
        "control_advantage": advantage,
        "control_strength": strength,
        "home_signal": home_signal,
        "away_signal": away_signal,
    }


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "FORM_CONTROL_VERSION",
    "FORMULA_STATUS",
    "MAX_CONTROL_INFLUENCE",
    "FormControl",
    "ControlBlock",
    "ControlResult",
    "analyze_control",
    "compare_control",
]
