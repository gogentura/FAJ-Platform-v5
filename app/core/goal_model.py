#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v2.3
============================================================

Назначение
----------
Преобразует текущее состояние команд из FormModel
в ожидаемые голы (lambda) конкретного матча.

Архитектура:

    FormModel
        │
        ├── xG_recent
        ├── xG_avg
        ├── goals_for_avg
        ├── xGA_recent
        ├── xGA_avg
        ├── goals_against_avg
        ├── xG_trend
        └── xGA_trend
        │
        ▼
    GoalModel v2.3
        │
        ├── Attack Level
        ├── Defence Level
        ├── Trend Adjustment
        ├── Match-up
        ├── Dominance Adjustment
        ├── FormControl Adjustment
        ├── SpecialForm Adjustment
        └── Winner Signal v2.3
        │
        ▼
    lambda_home / lambda_away

------------------------------------------------------------
WINNER SIGNAL v2.3
------------------------------------------------------------
Цель:
    Определить относительную силу команд и распределить
    существующий goal volume.

Принцип:
    λH + λA (до allocation) = λH + λA (после allocation)

Winner Signal компоненты:
    75% — качество игры:
        xG      30%
        xGA     20%
        SOT     15%
        Shots   10%
    15% — форма:
        Recent Points  5%
        Points         5%
        Venue Points   5%
    10% — тренд:
        xG trend       5%
        xGA trend      5%

Распределение:
    home_share = 0.50 + 0.18 * winner_signal
    away_share = 1.0 - home_share
    ограничение: home_share ∈ [0.32, 0.68]

------------------------------------------------------------
ГРАНИЦЫ МОДЕЛИ
------------------------------------------------------------

GoalModel НЕ использует:

- Club Rating
- FormWin
- FormWin result strength
- Defence.process_signal
- finishing_delta
- finishing_ratio
- bookmaker odds
- corners
- cards
- venue multiplier
- post-match facts
- prediction/result leakage

GoalModel использует:

1. объективное атакующее состояние;
2. объективное оборонительное состояние;
3. динамику xG/xGA;
4. opponent-relative dominance;
5. FormControl как ограниченный дополнительный сигнал;
6. SpecialForm как ограниченный дополнительный сигнал;
7. Winner Signal v2.3 для распределения goal volume.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import numpy as np


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "2.3"
FORMULA_STATUS = "RESEARCH_FORMULA"


# ============================================================
# BASE MATHEMATICAL PARAMETERS
# ============================================================

ATTACK_RECENT_WEIGHT = 0.60
ATTACK_AVG_WEIGHT = 0.30
ATTACK_GOALS_WEIGHT = 0.10

DEFENCE_RECENT_WEIGHT = 0.60
DEFENCE_AVG_WEIGHT = 0.30
DEFENCE_GOALS_WEIGHT = 0.10

TREND_WEIGHT = 0.20

MIN_XG_BASELINE = 0.5

MIN_LAMBDA = 0.15
MAX_LAMBDA = 4.50


# ============================================================
# DOMINANCE PARAMETERS
# ============================================================

DOMINANCE_XG_WEIGHT = 0.50
DOMINANCE_XGA_WEIGHT = 0.30
DOMINANCE_GOALS_WEIGHT = 0.20

DOMINANCE_WEIGHT = 0.10

DOMINANCE_XG_BASELINE = 1.25
DOMINANCE_XGA_BASELINE = 1.25
DOMINANCE_GOALS_BASELINE = 2.00


# ============================================================
# CONTROL / SPECIAL PARAMETERS
# ============================================================

CONTROL_MAX_INFLUENCE = 0.05
SPECIAL_MAX_INFLUENCE = 0.05

SPECIAL_SIGNAL_MIN = -0.30
SPECIAL_SIGNAL_MAX = 0.30

MAX_TOTAL_ADJUSTMENT = 0.20


# ============================================================
# WINNER SIGNAL v2.3
# ============================================================
# Winner Signal определяет только распределение общего xG
# между командами. Он НЕ создаёт дополнительный объём голов.
#
# 75% — качество игры
# 15% — текущая форма
# 10% — тренд
# ============================================================

WINNER_XG_WEIGHT = 0.30
WINNER_XGA_WEIGHT = 0.20
WINNER_SOT_WEIGHT = 0.15
WINNER_SHOTS_WEIGHT = 0.10
WINNER_RECENT_POINTS_WEIGHT = 0.05
WINNER_POINTS_WEIGHT = 0.05
WINNER_VENUE_POINTS_WEIGHT = 0.05
WINNER_XG_TREND_WEIGHT = 0.05
WINNER_XGA_TREND_WEIGHT = 0.05

WINNER_MAX_SIGNAL = 1.00

# Максимальное изменение доли общего xG:
# 0.50 ± 0.18 => 32% ... 68%
WINNER_MAX_SHARE_SHIFT = 0.18
WINNER_MIN_HOME_SHARE = 0.32
WINNER_MAX_HOME_SHARE = 0.68

# Нормализаторы сравнительных показателей.
WINNER_XG_BASELINE = 1.25
WINNER_XGA_BASELINE = 1.25
WINNER_SOT_BASELINE = 4.00
WINNER_SHOTS_BASELINE = 12.00
WINNER_POINTS_BASELINE = 1.50
WINNER_TREND_BASELINE = 0.50


# ============================================================
# RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Результат GoalModel v2.3.

    Старые поля сохранены ради совместимости
    с FAJBrain и остальным pipeline.
    """

    version: str

    home_team: Optional[str]
    away_team: Optional[str]
    venue: str

    home_xg: Optional[float]
    away_xg: Optional[float]

    home_base_xg: Optional[float]
    away_base_xg: Optional[float]

    home_attack_component: Optional[float]
    away_attack_component: Optional[float]

    home_defense_component: Optional[float]
    away_defense_component: Optional[float]

    home_venue_component: Optional[float]
    away_venue_component: Optional[float]

    home_xg_confidence: Optional[float]
    away_xg_confidence: Optional[float]

    attack_strength: Optional[float]
    defense_strength: Optional[float]

    formula_status: str

    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v2.3

    Основной источник силы:
        FormModel xG/xGA

    Дополнительные bounded signals:
        Dominance
        FormControl
        SpecialForm
        Winner Signal v2.3

    Важно:

    FormControl и SpecialForm не являются
    самостоятельными моделями голов.

    Они только корректируют уже рассчитанное
    objective xG состояние.

    Winner Signal распределяет существующий goal volume.
    """

    def __init__(self) -> None:
        pass

    # ========================================================
    # PUBLIC API
    # ========================================================

    def analyze(
        self,
        home_form: Any,
        away_form: Any,
        *,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        venue: str = "HOME",
        home_control: Any = None,
        away_control: Any = None,
        home_special: Any = None,
        away_special: Any = None,
    ) -> GoalModelResult:
        """
        Рассчитать ожидаемые голы.

        Основные входы:
            home_form
            away_form

        Дополнительные необязательные сигналы:

            home_control
            away_control

        FormControlResult или dict/object.

            home_special
            away_special

        SpecialFormResult или dict/object.

        Если дополнительные сигналы не переданы,
        базовый GoalModel продолжает работать без них.

        Это сохраняет обратную совместимость.
        """

        # ----------------------------------------------------
        # 1. HOME FORM
        # ----------------------------------------------------

        home_xg_recent = self._safe_float(
            self._get_value(home_form, "xg_recent")
        )

        home_xg_avg = self._safe_float(
            self._get_value(home_form, "xg_avg")
        )

        home_goals_for_avg = self._safe_float(
            self._get_value(home_form, "goals_for_avg")
        )

        home_xga_recent = self._safe_float(
            self._get_value(home_form, "xga_recent")
        )

        home_xga_avg = self._safe_float(
            self._get_value(home_form, "xga_avg")
        )

        home_goals_against_avg = self._safe_float(
            self._get_value(home_form, "goals_against_avg")
        )

        home_xg_trend = self._safe_float(
            self._get_value(home_form, "xg_trend")
        )

        home_xga_trend = self._safe_float(
            self._get_value(home_form, "xga_trend")
        )

        # ----------------------------------------------------
        # 1A. HOME FORM — SHOTS / SOT
        # ----------------------------------------------------

        home_shots_avg = self._safe_float(
            self._get_value(home_form, "shots_avg")
        )

        home_shots_against_avg = self._safe_float(
            self._get_value(home_form, "shots_against_avg")
        )

        home_sot_avg = self._safe_float(
            self._get_value(home_form, "shots_on_target_avg")
        )

        home_sot_against_avg = self._safe_float(
            self._get_value(home_form, "shots_on_target_against_avg")
        )

        # ----------------------------------------------------
        # 2. AWAY FORM
        # ----------------------------------------------------

        away_xg_recent = self._safe_float(
            self._get_value(away_form, "xg_recent")
        )

        away_xg_avg = self._safe_float(
            self._get_value(away_form, "xg_avg")
        )

        away_goals_for_avg = self._safe_float(
            self._get_value(away_form, "goals_for_avg")
        )

        away_xga_recent = self._safe_float(
            self._get_value(away_form, "xga_recent")
        )

        away_xga_avg = self._safe_float(
            self._get_value(away_form, "xga_avg")
        )

        away_goals_against_avg = self._safe_float(
            self._get_value(away_form, "goals_against_avg")
        )

        away_xg_trend = self._safe_float(
            self._get_value(away_form, "xg_trend")
        )

        away_xga_trend = self._safe_float(
            self._get_value(away_form, "xga_trend")
        )

        # ----------------------------------------------------
        # 2A. AWAY FORM — SHOTS / SOT
        # ----------------------------------------------------

        away_shots_avg = self._safe_float(
            self._get_value(away_form, "shots_avg")
        )

        away_shots_against_avg = self._safe_float(
            self._get_value(away_form, "shots_against_avg")
        )

        away_sot_avg = self._safe_float(
            self._get_value(away_form, "shots_on_target_avg")
        )

        away_sot_against_avg = self._safe_float(
            self._get_value(away_form, "shots_on_target_against_avg")
        )

        # ----------------------------------------------------
        # 3. ATTACK
        # ----------------------------------------------------

        home_attack = self._calculate_attack_level(
            home_xg_recent,
            home_xg_avg,
            home_goals_for_avg,
        )

        away_attack = self._calculate_attack_level(
            away_xg_recent,
            away_xg_avg,
            away_goals_for_avg,
        )

        # ----------------------------------------------------
        # 4. DEFENCE
        # ----------------------------------------------------

        home_defence = self._calculate_defence_level(
            home_xga_recent,
            home_xga_avg,
            home_goals_against_avg,
        )

        away_defence = self._calculate_defence_level(
            away_xga_recent,
            away_xga_avg,
            away_goals_against_avg,
        )

        # ----------------------------------------------------
        # 5. TREND
        # ----------------------------------------------------

        home_attack_trend = self._calculate_trend_adjustment(
            home_xg_trend,
            home_xg_avg,
        )

        away_attack_trend = self._calculate_trend_adjustment(
            away_xg_trend,
            away_xg_avg,
        )

        home_defence_trend = self._calculate_trend_adjustment(
            home_xga_trend,
            home_xga_avg,
        )

        away_defence_trend = self._calculate_trend_adjustment(
            away_xga_trend,
            away_xga_avg,
        )

        # ----------------------------------------------------
        # 6. CURRENT ATTACK / DEFENCE
        # ----------------------------------------------------

        home_attack_current = self._apply_trend(
            home_attack,
            home_attack_trend,
        )

        away_attack_current = self._apply_trend(
            away_attack,
            away_attack_trend,
        )

        home_defence_current = self._apply_trend(
            home_defence,
            home_defence_trend,
        )

        away_defence_current = self._apply_trend(
            away_defence,
            away_defence_trend,
        )

        # ----------------------------------------------------
        # 7. BASE MATCHUP
        # ----------------------------------------------------

        home_base_xg = self._calculate_expected_goals(
            home_attack_current,
            away_defence_current,
        )

        away_base_xg = self._calculate_expected_goals(
            away_attack_current,
            home_defence_current,
        )

        # ----------------------------------------------------
        # 8. DOMINANCE
        # ----------------------------------------------------

        dominance = self._calculate_dominance_gap(
            home_xg_recent=home_xg_recent,
            home_xg_avg=home_xg_avg,
            home_xga_recent=home_xga_recent,
            home_xga_avg=home_xga_avg,
            home_goals_for_avg=home_goals_for_avg,
            home_goals_against_avg=home_goals_against_avg,

            away_xg_recent=away_xg_recent,
            away_xg_avg=away_xg_avg,
            away_xga_recent=away_xga_recent,
            away_xga_avg=away_xga_avg,
            away_goals_for_avg=away_goals_for_avg,
            away_goals_against_avg=away_goals_against_avg,
        )

        dominance_adjustment = (
            dominance * DOMINANCE_WEIGHT
            if dominance is not None
            else 0.0
        )

        # ----------------------------------------------------
        # 9. FORM CONTROL
        # ----------------------------------------------------

        home_control_signal = self._extract_control_signal(
            home_control
        )

        away_control_signal = self._extract_control_signal(
            away_control
        )

        control_gap = self._calculate_gap(
            home_control_signal,
            away_control_signal,
        )

        control_adjustment = (
            control_gap * CONTROL_MAX_INFLUENCE
            if control_gap is not None
            else 0.0
        )

        # ----------------------------------------------------
        # 10. SPECIAL FORM
        # ----------------------------------------------------

        home_special_signal = self._extract_special_signal(
            home_special
        )

        away_special_signal = self._extract_special_signal(
            away_special
        )

        special_gap = self._calculate_gap(
            home_special_signal,
            away_special_signal,
        )

        special_adjustment = 0.0

        if special_gap is not None:
            special_adjustment = (
                special_gap
                / max(
                    abs(SPECIAL_SIGNAL_MIN),
                    abs(SPECIAL_SIGNAL_MAX),
                )
            )

            special_adjustment = self._clamp(
                special_adjustment,
                -1.0,
                1.0,
            )

            special_adjustment *= SPECIAL_MAX_INFLUENCE

        # ----------------------------------------------------
        # 11. DOMINANCE / CONTROL / SPECIAL ADJUSTMENT
        # ----------------------------------------------------

        total_adjustment = (
            dominance_adjustment
            + control_adjustment
            + special_adjustment
        )

        total_adjustment = self._clamp(
            total_adjustment,
            -MAX_TOTAL_ADJUSTMENT,
            MAX_TOTAL_ADJUSTMENT,
        )

        home_xg = self._apply_match_adjustment(
            home_base_xg,
            total_adjustment,
        )

        away_xg = self._apply_match_adjustment(
            away_base_xg,
            -total_adjustment,
        )

        # ----------------------------------------------------
        # 12. WINNER SIGNAL v2.3
        #
        # Winner Signal НЕ увеличивает общий объём голов.
        # Он только распределяет уже рассчитанный total_xg.
        # ----------------------------------------------------

        total_before_allocation = (
            home_xg + away_xg
            if home_xg is not None and away_xg is not None
            else None
        )

        winner_signal, winner_diagnostics = self._calculate_winner_signal(
            home_form,
            away_form,
        )

        if winner_signal is None or total_before_allocation is None or total_before_allocation <= 0:
            # При отсутствии достаточных данных сохраняем
            # существующее распределение.
            if total_before_allocation is not None and total_before_allocation > 0:
                home_share = (
                    home_xg / total_before_allocation
                    if home_xg is not None
                    else 0.50
                )
            else:
                home_share = 0.50
            allocation_adjustment = 0.0
        else:
            # 0.50 = нейтральный матч
            # +0.18 = максимум в пользу хозяев
            # -0.18 = максимум в пользу гостей
            home_share = (
                0.50
                + WINNER_MAX_SHARE_SHIFT * winner_signal
            )
            home_share = float(np.clip(
                home_share,
                WINNER_MIN_HOME_SHARE,
                WINNER_MAX_HOME_SHARE,
            ))
            allocation_adjustment = home_share - 0.50

        away_share = 1.0 - home_share

        # Распределяем ТОТ ЖЕ общий xG.
        if total_before_allocation is not None and total_before_allocation > 0:
            home_xg = total_before_allocation * home_share
            away_xg = total_before_allocation * away_share
        else:
            home_xg = None
            away_xg = None

        total_after_allocation = (
            home_xg + away_xg
            if home_xg is not None and away_xg is not None
            else None
        )

        # ----------------------------------------------------
        # 13. FINAL CLAMP
        # ----------------------------------------------------

        home_xg = self._clip_lambda(home_xg)
        away_xg = self._clip_lambda(away_xg)

        # ----------------------------------------------------
        # 14. DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics = self._build_diagnostics(
            home_attack=home_attack,
            away_attack=away_attack,

            home_defence=home_defence,
            away_defence=away_defence,

            home_attack_current=home_attack_current,
            away_attack_current=away_attack_current,

            home_defence_current=home_defence_current,
            away_defence_current=away_defence_current,

            home_attack_trend=home_attack_trend,
            away_attack_trend=away_attack_trend,

            home_defence_trend=home_defence_trend,
            away_defence_trend=away_defence_trend,

            home_base_xg=home_base_xg,
            away_base_xg=away_base_xg,

            dominance=dominance,
            dominance_adjustment=dominance_adjustment,

            home_control=home_control_signal,
            away_control=away_control_signal,
            control_gap=control_gap,
            control_adjustment=control_adjustment,

            home_special=home_special_signal,
            away_special=away_special_signal,
            special_gap=special_gap,
            special_adjustment=special_adjustment,

            total_adjustment=total_adjustment,

            winner_signal=winner_signal,
            winner_diagnostics=winner_diagnostics,
            home_share=home_share,
            away_share=away_share,
            allocation_adjustment=allocation_adjustment,

            total_before_allocation=total_before_allocation,
            total_after_allocation=total_after_allocation,

            home_xg=home_xg,
            away_xg=away_xg,
        )

        # ----------------------------------------------------
        # 15. RESULT
        # ----------------------------------------------------

        return GoalModelResult(
            version=GOAL_MODEL_VERSION,

            home_team=home_team,
            away_team=away_team,
            venue=venue,

            home_xg=home_xg,
            away_xg=away_xg,

            home_base_xg=home_base_xg,
            away_base_xg=away_base_xg,

            home_attack_component=home_attack_current,
            away_attack_component=away_attack_current,

            # Для home lambda используется
            # defence гостевой команды.
            home_defense_component=away_defence_current,

            # Для away lambda используется
            # defence домашней команды.
            away_defense_component=home_defence_current,

            # Venue НЕ является multiplier.
            home_venue_component=None,
            away_venue_component=None,

            home_xg_confidence=self._calculate_confidence(
                home_xg,
                home_attack,
                away_defence,
            ),

            away_xg_confidence=self._calculate_confidence(
                away_xg,
                away_attack,
                home_defence,
            ),

            # Compatibility fields.
            attack_strength=home_attack,
            defense_strength=home_defence,

            formula_status=FORMULA_STATUS,

            diagnostics=diagnostics,
        )

    # ========================================================
    # ATTACK
    # ========================================================

    @staticmethod
    def _calculate_attack_level(
        xg_recent: Optional[float],
        xg_avg: Optional[float],
        goals_for_avg: Optional[float],
    ) -> Optional[float]:
        """
        Attack:

            0.60*xG_recent
          + 0.30*xG_avg
          + 0.10*GoalsFor_avg

        Missing values:
            excluded + remaining weights normalized.
        """

        values = [
            (xg_recent, ATTACK_RECENT_WEIGHT),
            (xg_avg, ATTACK_AVG_WEIGHT),
            (goals_for_avg, ATTACK_GOALS_WEIGHT),
        ]

        return GoalModel._weighted_available(values)

    # ========================================================
    # DEFENCE
    # ========================================================

    @staticmethod
    def _calculate_defence_level(
        xga_recent: Optional[float],
        xga_avg: Optional[float],
        goals_against_avg: Optional[float],
    ) -> Optional[float]:
        """
        Defence:

            0.60*xGA_recent
          + 0.30*xGA_avg
          + 0.10*GoalsAgainst_avg

        Higher xGA:
            weaker defence.

        Lower xGA:
            stronger defence.
        """

        values = [
            (xga_recent, DEFENCE_RECENT_WEIGHT),
            (xga_avg, DEFENCE_AVG_WEIGHT),
            (goals_against_avg, DEFENCE_GOALS_WEIGHT),
        ]

        return GoalModel._weighted_available(values)

    # ========================================================
    # WEIGHTED AVAILABLE
    # ========================================================

    @staticmethod
    def _weighted_available(
        values: list[tuple[Optional[float], float]],
    ) -> Optional[float]:
        """
        Weighted mean over available values only.

        None никогда не заменяется нулём.
        """

        weighted_sum = 0.0
        weight_sum = 0.0

        for value, weight in values:

            if value is None:
                continue

            weighted_sum += value * weight
            weight_sum += weight

        if weight_sum <= 0.0:
            return None

        return weighted_sum / weight_sum

    # ========================================================
    # TREND
    # ========================================================

    @staticmethod
    def _calculate_trend_adjustment(
        trend: Optional[float],
        baseline: Optional[float],
    ) -> float:
        """
        Relative trend:

            trend / max(baseline, 0.5)

        clipped to [-1,+1].
        """

        if trend is None:
            return 0.0

        baseline_value = (
            baseline
            if baseline is not None
            else MIN_XG_BASELINE
        )

        baseline_value = max(
            baseline_value,
            MIN_XG_BASELINE,
        )

        value = trend / baseline_value

        return GoalModel._clamp(
            value,
            -1.0,
            1.0,
        )

    # ========================================================
    # APPLY TREND
    # ========================================================

    @staticmethod
    def _apply_trend(
        level: Optional[float],
        trend_adjustment: float,
    ) -> Optional[float]:
        """
        Level* =
            Level * (1 + 0.20*T)
        """

        if level is None:
            return None

        return level * (
            1.0
            + TREND_WEIGHT * trend_adjustment
        )

    # ========================================================
    # BASE EXPECTED GOALS
    # ========================================================

    @staticmethod
    def _calculate_expected_goals(
        attack_level: Optional[float],
        opponent_defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Base matchup:

            lambda =
                (Attack + OpponentDefence) / 2

        xGA is interpreted correctly:

            high opponent xGA
                -> easier opponent defence
                -> higher lambda

            low opponent xGA
                -> stronger opponent defence
                -> lower lambda
        """

        if attack_level is None:
            return None

        if opponent_defence_level is None:
            return None

        return (
            attack_level
            + opponent_defence_level
        ) / 2.0

    # ========================================================
    # DOMINANCE
    # ========================================================

    @classmethod
    def _calculate_dominance_gap(
        cls,
        *,
        home_xg_recent: Optional[float],
        home_xg_avg: Optional[float],
        home_xga_recent: Optional[float],
        home_xga_avg: Optional[float],
        home_goals_for_avg: Optional[float],
        home_goals_against_avg: Optional[float],

        away_xg_recent: Optional[float],
        away_xg_avg: Optional[float],
        away_xga_recent: Optional[float],
        away_xga_avg: Optional[float],
        away_goals_for_avg: Optional[float],
        away_goals_against_avg: Optional[float],
    ) -> Optional[float]:
        """
        Opponent-relative team dominance.

        Positive:
            Home stronger.

        Negative:
            Away stronger.

        Components:

            xG dominance
            xGA dominance
            goals dominance

        Все компоненты optional.

        Доступные компоненты получают
        перенормированные веса.
        """

        # ----------------------------------------------------
        # xG component
        # ----------------------------------------------------

        home_xg = cls._available_mean(
            home_xg_recent,
            home_xg_avg,
        )

        away_xg = cls._available_mean(
            away_xg_recent,
            away_xg_avg,
        )

        xg_component = cls._relative_gap(
            home_xg,
            away_xg,
            DOMINANCE_XG_BASELINE,
        )

        # ----------------------------------------------------
        # xGA component
        #
        # LOWER xGA = stronger defence.
        #
        # Поэтому знак инвертируется.
        # ----------------------------------------------------

        home_xga = cls._available_mean(
            home_xga_recent,
            home_xga_avg,
        )

        away_xga = cls._available_mean(
            away_xga_recent,
            away_xga_avg,
        )

        xga_component_raw = cls._relative_gap(
            home_xga,
            away_xga,
            DOMINANCE_XGA_BASELINE,
        )

        xga_component = (
            -xga_component_raw
            if xga_component_raw is not None
            else None
        )

        # ----------------------------------------------------
        # Goals component
        #
        # Net attacking result:
        #
        # GoalsFor - GoalsAgainst
        # ----------------------------------------------------

        home_net = cls._net_goals(
            home_goals_for_avg,
            home_goals_against_avg,
        )

        away_net = cls._net_goals(
            away_goals_for_avg,
            away_goals_against_avg,
        )

        goals_component = cls._relative_gap(
            home_net,
            away_net,
            DOMINANCE_GOALS_BASELINE,
        )

        # ----------------------------------------------------
        # Weighted available components
        # ----------------------------------------------------

        components = [
            (
                xg_component,
                DOMINANCE_XG_WEIGHT,
            ),
            (
                xga_component,
                DOMINANCE_XGA_WEIGHT,
            ),
            (
                goals_component,
                DOMINANCE_GOALS_WEIGHT,
            ),
        ]

        weighted_sum = 0.0
        weight_sum = 0.0

        for value, weight in components:

            if value is None:
                continue

            weighted_sum += value * weight
            weight_sum += weight

        if weight_sum <= 0.0:
            return None

        return cls._clamp(
            weighted_sum / weight_sum,
            -1.0,
            1.0,
        )

    # ========================================================
    # DOMINANCE HELPERS
    # ========================================================

    @staticmethod
    def _available_mean(
        first: Optional[float],
        second: Optional[float],
    ) -> Optional[float]:

        values = [
            value
            for value in (
                first,
                second,
            )
            if value is not None
        ]

        if not values:
            return None

        return sum(values) / len(values)

    @classmethod
    def _relative_gap(
        cls,
        home_value: Optional[float],
        away_value: Optional[float],
        baseline: float,
    ) -> Optional[float]:
        """
        Normalized opponent-relative difference.

            (home - away) / baseline

        clipped [-1,+1].
        """

        if home_value is None:
            return None

        if away_value is None:
            return None

        denominator = max(
            abs(baseline),
            MIN_XG_BASELINE,
        )

        value = (
            home_value
            - away_value
        ) / denominator

        return cls._clamp(
            value,
            -1.0,
            1.0,
        )

    @staticmethod
    def _net_goals(
        goals_for: Optional[float],
        goals_against: Optional[float],
    ) -> Optional[float]:

        if goals_for is None:
            return None

        if goals_against is None:
            return None

        return (
            goals_for
            - goals_against
        )

    # ========================================================
    # CONTROL SIGNAL
    # ========================================================

    @classmethod
    def _extract_control_signal(
        cls,
        source: Any,
    ) -> Optional[float]:
        """
        FormControl v1.1:

            control_signal [-1,+1]

        Supports:
            ControlResult
            dict
            compatible object
        """

        if source is None:
            return None

        value = cls._get_value(
            source,
            "control_signal",
        )

        value = cls._safe_float(value)

        if value is None:
            return None

        return cls._clamp(
            value,
            -1.0,
            1.0,
        )

    # ========================================================
    # SPECIAL SIGNAL
    # ========================================================

    @classmethod
    def _extract_special_signal(
        cls,
        source: Any,
    ) -> Optional[float]:
        """
        SpecialForm v1.0:

            composite_signal [-0.30,+0.30]
        """

        if source is None:
            return None

        value = cls._get_value(
            source,
            "composite_signal",
        )

        value = cls._safe_float(value)

        if value is None:
            return None

        return cls._clamp(
            value,
            SPECIAL_SIGNAL_MIN,
            SPECIAL_SIGNAL_MAX,
        )

    # ========================================================
    # GAP
    # ========================================================

    @staticmethod
    def _calculate_gap(
        home_value: Optional[float],
        away_value: Optional[float],
    ) -> Optional[float]:

        if home_value is None:
            return None

        if away_value is None:
            return None

        return GoalModel._clamp(
            home_value - away_value,
            -1.0,
            1.0,
        )

    # ========================================================
    # APPLY MATCH ADJUSTMENT
    # ========================================================

    @staticmethod
    def _apply_match_adjustment(
        value: Optional[float],
        adjustment: float,
    ) -> Optional[float]:
        """
        Apply bounded asymmetric correction.
        """

        if value is None:
            return None

        return value * (
            1.0 + adjustment
        )

    # ========================================================
    # CLAMP
    # ========================================================

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """
        Ограничение значения заданным диапазоном.

        Используется для всех bounded signals:
            trend
            dominance
            control
            special
            total adjustment
            allocation
        """

        return max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

    # ========================================================
    # LAMBDA CLAMP
    # ========================================================

    @staticmethod
    def _clip_lambda(
        value: Optional[float],
    ) -> Optional[float]:
        """
        Final safety:

            0.15 <= lambda <= 4.50

        None remains None.
        """

        if value is None:
            return None

        return max(
            MIN_LAMBDA,
            min(
                MAX_LAMBDA,
                value,
            ),
        )

    # ========================================================
    # WINNER SIGNAL v2.3
    # ========================================================

    def _winner_relative_gap(
        self,
        home: Optional[float],
        away: Optional[float],
        baseline: float,
        invert: bool = False,
    ) -> Optional[float]:
        """
        Сравнивает два показателя и возвращает сигнал [-1, +1].
        +1 = преимущество хозяев
        -1 = преимущество гостей
        invert=True используется для xGA:
        меньше xGA = лучше.
        """
        if home is None or away is None:
            return None
        try:
            home = float(home)
            away = float(away)
            baseline = max(float(baseline), 1e-9)
        except (TypeError, ValueError):
            return None
        gap = (home - away) / baseline
        if invert:
            gap = -gap
        return float(np.clip(gap, -1.0, 1.0))

    def _weighted_signal(
        self,
        components: list[tuple[Optional[float], float]],
    ) -> Optional[float]:
        """
        Missing values не превращаются в 0.
        Если показатель отсутствует, его вес перераспределяется
        между доступными показателями.
        """
        available = [
            (value, weight)
            for value, weight in components
            if value is not None
        ]
        if not available:
            return None
        weight_sum = sum(weight for _, weight in available)
        if weight_sum <= 0:
            return None
        signal = sum(
            float(value) * weight
            for value, weight in available
        ) / weight_sum
        return float(np.clip(
            signal,
            -WINNER_MAX_SIGNAL,
            WINNER_MAX_SIGNAL,
        ))

    def _calculate_winner_signal(
        self,
        home_form: Any,
        away_form: Any,
    ) -> tuple[Optional[float], dict]:
        """
        Winner Signal v2.3.
        Использует только предматчевые данные FormModel.

        75% — качество:
            xG      30%
            xGA     20%
            SOT     15%
            Shots   10%

        15% — форма:
            Recent Points  5%
            Points         5%
            Venue Points   5%

        10% — тренд:
            xG trend       5%
            xGA trend      5%
        """

        xg_gap = self._winner_relative_gap(
            getattr(home_form, "xg_avg", None),
            getattr(away_form, "xg_avg", None),
            WINNER_XG_BASELINE,
        )

        xga_gap = self._winner_relative_gap(
            getattr(home_form, "xga_avg", None),
            getattr(away_form, "xga_avg", None),
            WINNER_XGA_BASELINE,
            invert=True,
        )

        sot_gap = self._winner_relative_gap(
            getattr(home_form, "shots_on_target_avg", None),
            getattr(away_form, "shots_on_target_avg", None),
            WINNER_SOT_BASELINE,
        )

        shots_gap = self._winner_relative_gap(
            getattr(home_form, "shots_avg", None),
            getattr(away_form, "shots_avg", None),
            WINNER_SHOTS_BASELINE,
        )

        recent_points_gap = self._winner_relative_gap(
            getattr(home_form, "recent_points_rate", None),
            getattr(away_form, "recent_points_rate", None),
            WINNER_POINTS_BASELINE,
        )

        points_gap = self._winner_relative_gap(
            getattr(home_form, "points_rate", None),
            getattr(away_form, "points_rate", None),
            WINNER_POINTS_BASELINE,
        )

        venue_gap = self._winner_relative_gap(
            getattr(home_form, "home_points_rate", None),
            getattr(away_form, "away_points_rate", None),
            WINNER_POINTS_BASELINE,
        )

        xg_trend_gap = self._winner_relative_gap(
            getattr(home_form, "xg_trend", None),
            getattr(away_form, "xg_trend", None),
            WINNER_TREND_BASELINE,
        )

        # Для xGA: снижение xGA = улучшение.
        xga_trend_gap = self._winner_relative_gap(
            getattr(home_form, "xga_trend", None),
            getattr(away_form, "xga_trend", None),
            WINNER_TREND_BASELINE,
            invert=True,
        )

        signal = self._weighted_signal([
            (xg_gap, WINNER_XG_WEIGHT),
            (xga_gap, WINNER_XGA_WEIGHT),
            (sot_gap, WINNER_SOT_WEIGHT),
            (shots_gap, WINNER_SHOTS_WEIGHT),
            (recent_points_gap, WINNER_RECENT_POINTS_WEIGHT),
            (points_gap, WINNER_POINTS_WEIGHT),
            (venue_gap, WINNER_VENUE_POINTS_WEIGHT),
            (xg_trend_gap, WINNER_XG_TREND_WEIGHT),
            (xga_trend_gap, WINNER_XGA_TREND_WEIGHT),
        ])

        diagnostics = {
            "signal": signal,
            "components": {
                "xg": xg_gap,
                "xga": xga_gap,
                "sot": sot_gap,
                "shots": shots_gap,
                "recent_points": recent_points_gap,
                "points": points_gap,
                "venue_points": venue_gap,
                "xg_trend": xg_trend_gap,
                "xga_trend": xga_trend_gap,
            },
            "weights": {
                "xg": WINNER_XG_WEIGHT,
                "xga": WINNER_XGA_WEIGHT,
                "sot": WINNER_SOT_WEIGHT,
                "shots": WINNER_SHOTS_WEIGHT,
                "recent_points": WINNER_RECENT_POINTS_WEIGHT,
                "points": WINNER_POINTS_WEIGHT,
                "venue_points": WINNER_VENUE_POINTS_WEIGHT,
                "xg_trend": WINNER_XG_TREND_WEIGHT,
                "xga_trend": WINNER_XGA_TREND_WEIGHT,
            },
        }

        return signal, diagnostics

    # ========================================================
    # VALUE ACCESS
    # ========================================================

    @staticmethod
    def _get_value(
        source: Any,
        field: str,
        default: Any = None,
    ) -> Any:
        """
        Read from:

            dict
            object attribute

        Missing:
            default
        """

        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(
                field,
                default,
            )

        return getattr(
            source,
            field,
            default,
        )

    # ========================================================
    # SAFE FLOAT
    # ========================================================

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:
        """
        Safe finite float.

        None != 0.
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not (
            result == result
            and result not in (
                float("inf"),
                float("-inf"),
            )
        ):
            return None

        return result

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @staticmethod
    def _calculate_confidence(
        xg: Optional[float],
        attack_level: Optional[float],
        defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Technical data availability only.

        Это НЕ probability confidence.
        """

        if xg is None:
            return None

        available = sum(
            value is not None
            for value in (
                attack_level,
                defence_level,
            )
        )

        if available == 2:
            return 1.0

        if available == 1:
            return 0.5

        return 0.0

    # ========================================================
    # DIAGNOSTICS
    # ========================================================

    @staticmethod
    def _build_diagnostics(
        *,
        home_attack: Optional[float],
        away_attack: Optional[float],

        home_defence: Optional[float],
        away_defence: Optional[float],

        home_attack_current: Optional[float],
        away_attack_current: Optional[float],

        home_defence_current: Optional[float],
        away_defence_current: Optional[float],

        home_attack_trend: float,
        away_attack_trend: float,

        home_defence_trend: float,
        away_defence_trend: float,

        home_base_xg: Optional[float],
        away_base_xg: Optional[float],

        dominance: Optional[float],
        dominance_adjustment: float,

        home_control: Optional[float],
        away_control: Optional[float],
        control_gap: Optional[float],
        control_adjustment: float,

        home_special: Optional[float],
        away_special: Optional[float],
        special_gap: Optional[float],
        special_adjustment: float,

        total_adjustment: float,

        winner_signal: Optional[float],
        winner_diagnostics: dict,
        home_share: float,
        away_share: float,
        allocation_adjustment: float,

        total_before_allocation: Optional[float],
        total_after_allocation: Optional[float],

        home_xg: Optional[float],
        away_xg: Optional[float],
    ) -> Dict[str, Any]:
        """
        Полная прозрачность расчёта.

        Основная задача diagnostics:

            увидеть, почему новая модель
            дала другой lambda.
        """

        # ----------------------------------------------------
        # Total preservation check
        # ----------------------------------------------------

        total_preserved = None

        if (
            total_before_allocation is not None
            and total_after_allocation is not None
        ):
            total_preserved = (
                abs(
                    total_before_allocation
                    - total_after_allocation
                ) < 1e-9
            )

        return {
            "model": "GoalModel",

            "version": GOAL_MODEL_VERSION,

            "formula_status": FORMULA_STATUS,

            "architecture": {
                "base": "FORM_MODEL_XG_XGA",
                "dominance": True,
                "form_control": True,
                "special_form": True,
                "winner_signal": True,
                "goal_allocation_version": "2.3",
                "probability_model": False,
                "score_model": False,
            },

            "attack": {
                "home": home_attack,
                "away": away_attack,

                "home_current":
                    home_attack_current,

                "away_current":
                    away_attack_current,
            },

            "defence": {
                "home": home_defence,
                "away": away_defence,

                "home_current":
                    home_defence_current,

                "away_current":
                    away_defence_current,

                "home_defense_component":
                    away_defence_current,

                "away_defense_component":
                    home_defence_current,
            },

            "trend": {
                "home_xg":
                    home_attack_trend,

                "away_xg":
                    away_attack_trend,

                "home_xga":
                    home_defence_trend,

                "away_xga":
                    away_defence_trend,
            },

            "base_lambda": {
                "home":
                    home_base_xg,

                "away":
                    away_base_xg,
            },

            "dominance": {
                "signal":
                    dominance,

                "weight":
                    DOMINANCE_WEIGHT,

                "adjustment":
                    dominance_adjustment,

                "used":
                    dominance is not None,
            },

            "form_control": {
                "home":
                    home_control,

                "away":
                    away_control,

                "gap":
                    control_gap,

                "max_influence":
                    CONTROL_MAX_INFLUENCE,

                "adjustment":
                    control_adjustment,

                "used":
                    control_gap is not None,
            },

            "special_form": {
                "home":
                    home_special,

                "away":
                    away_special,

                "gap":
                    special_gap,

                "max_influence":
                    SPECIAL_MAX_INFLUENCE,

                "adjustment":
                    special_adjustment,

                "used":
                    special_gap is not None,
            },

            "adjustment": {
                "dominance":
                    dominance_adjustment,

                "control":
                    control_adjustment,

                "special":
                    special_adjustment,

                "total":
                    total_adjustment,

                "max":
                    MAX_TOTAL_ADJUSTMENT,
            },

            # ----------------------------------------------------
            # WINNER SIGNAL v2.3
            # ----------------------------------------------------

            "winner_signal": {
                **winner_diagnostics,
                "max_share_shift": WINNER_MAX_SHARE_SHIFT,
                "adjustment": allocation_adjustment,
                "home_share": home_share,
                "away_share": away_share,
                "affects_total_xg": False,
            },

            "goal_allocation": {
                "version": "2.3",
                "signal": winner_signal,
                "adjustment": allocation_adjustment,
                "max_share_shift": WINNER_MAX_SHARE_SHIFT,
                "home_share": home_share,
                "away_share": away_share,
                "affects_total_xg": False,
            },

            "allocation_shift": {
                "home_share": home_share,
                "away_share": away_share,
            },

            "lambda": {
                "home_base":
                    home_base_xg,

                "away_base":
                    away_base_xg,

                "home_final":
                    home_xg,

                "away_final":
                    away_xg,

                "min":
                    MIN_LAMBDA,

                "max":
                    MAX_LAMBDA,
            },

            "total_before_allocation": total_before_allocation,
            "total_after_allocation": total_after_allocation,
            "total_preserved": total_preserved,

            "weights": {
                "attack_recent":
                    ATTACK_RECENT_WEIGHT,

                "attack_avg":
                    ATTACK_AVG_WEIGHT,

                "attack_goals":
                    ATTACK_GOALS_WEIGHT,

                "defence_recent":
                    DEFENCE_RECENT_WEIGHT,

                "defence_avg":
                    DEFENCE_AVG_WEIGHT,

                "defence_goals":
                    DEFENCE_GOALS_WEIGHT,

                "trend":
                    TREND_WEIGHT,

                "dominance_xg":
                    DOMINANCE_XG_WEIGHT,

                "dominance_xga":
                    DOMINANCE_XGA_WEIGHT,

                "dominance_goals":
                    DOMINANCE_GOALS_WEIGHT,
            },

            # ------------------------------------------------
            # Explicit exclusions
            # ------------------------------------------------

            "club_rating_used": False,

            "form_win_used": False,

            "defence_signal_used": False,

            "finishing_delta_used": False,

            "finishing_ratio_used": False,

            "result_strength_used": False,

            "consistency_used": False,

            "effect_signals_used": False,

            "bookmaker_odds_used": False,

            "venue_multiplier_used": False,

            "corners_used": False,

            "cards_used": False,

            "probability_model_used": False,

            "score_predictor_used": False,
        }


# ============================================================
# CONVENIENCE API
# ============================================================

def calculate_expected_goals(
    home_form: Any,
    away_form: Any,
    *,
    home_team: Optional[str] = None,
    away_team: Optional[str] = None,
    venue: str = "HOME",
    home_control: Any = None,
    away_control: Any = None,
    home_special: Any = None,
    away_special: Any = None,
) -> GoalModelResult:
    """
    Convenience wrapper around GoalModel.analyze().
    """

    model = GoalModel()

    return model.analyze(
        home_form,
        away_form,

        home_team=home_team,
        away_team=away_team,

        venue=venue,

        home_control=home_control,
        away_control=away_control,

        home_special=home_special,
        away_special=away_special,
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "GOAL_MODEL_VERSION",
    "FORMULA_STATUS",

    "ATTACK_RECENT_WEIGHT",
    "ATTACK_AVG_WEIGHT",
    "ATTACK_GOALS_WEIGHT",

    "DEFENCE_RECENT_WEIGHT",
    "DEFENCE_AVG_WEIGHT",
    "DEFENCE_GOALS_WEIGHT",

    "TREND_WEIGHT",

    "DOMINANCE_WEIGHT",
    "CONTROL_MAX_INFLUENCE",
    "SPECIAL_MAX_INFLUENCE",
    "MAX_TOTAL_ADJUSTMENT",

    "WINNER_XG_WEIGHT",
    "WINNER_XGA_WEIGHT",
    "WINNER_SOT_WEIGHT",
    "WINNER_SHOTS_WEIGHT",
    "WINNER_RECENT_POINTS_WEIGHT",
    "WINNER_POINTS_WEIGHT",
    "WINNER_VENUE_POINTS_WEIGHT",
    "WINNER_XG_TREND_WEIGHT",
    "WINNER_XGA_TREND_WEIGHT",
    "WINNER_MAX_SHARE_SHIFT",

    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
