#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v2.0
============================================================

Назначение
----------
Преобразует текущее состояние команды из FormModel
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
    GoalModel v2
        │
        ├── Attack Level
        ├── Defence Level
        ├── Trend Adjustment
        └── Match-up
        │
        ▼
    lambda_home / lambda_away

ВАЖНЫЕ ГРАНИЦЫ
--------------
GoalModel НЕ использует:

- Club Rating
- FormWin
- Defence.process_signal
- finishing_delta
- finishing_ratio
- result_strength
- consistency
- effect signals
- bookmaker odds
- venue multiplier

Club Rating остаётся независимым долгосрочным слоем.

FormModel предоставляет текущее состояние.
GoalModel преобразует это состояние в ожидаемые голы.

Математическая формула
----------------------

Attack:

A =
    weighted(
        xG_recent,
        xG_avg,
        goals_for_avg
    )

при полном наборе:

A =
    0.60 * xG_recent
  + 0.30 * xG_avg
  + 0.10 * goals_for_avg


Defence:

D =
    weighted(
        xGA_recent,
        xGA_avg,
        goals_against_avg
    )

при полном наборе:

D =
    0.60 * xGA_recent
  + 0.30 * xGA_avg
  + 0.10 * goals_against_avg


Trend:

T_attack =
    clip(
        xG_trend / max(xG_avg, 0.5),
        -1,
        +1
    )

T_defence =
    clip(
        xGA_trend / max(xGA_avg, 0.5),
        -1,
        +1
    )


Current state:

A* = A * (1 + 0.20 * T_attack)

D* = D * (1 + 0.20 * T_defence)


Match-up:

lambda_home =
    (HomeAttack* + AwayDefence*) / 2

lambda_away =
    (AwayAttack* + HomeDefence*) / 2


Final safety clamp:

0.15 <= lambda <= 4.50

None никогда не превращается в 0.

Если часть данных отсутствует, веса
перенормируются по доступным значениям.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "2.0"
FORMULA_STATUS = "RESEARCH_FORMULA"


# ============================================================
# MATHEMATICAL CONTRACT
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
# RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Результат GoalModel v2.

    Поля сохранены максимально совместимыми
    с предыдущим контрактом.

    Семантика некоторых полей уточнена:

    home_attack_component
        Home Attack Level

    home_defense_component
        Away Defence Level,
        то есть оборона соперника,
        использованная для расчёта home lambda.

    away_attack_component
        Away Attack Level

    away_defense_component
        Home Defence Level
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
    FAJ GoalModel v2.0

    Stateless model.

    Ответственность:

        FormModel state
            ↓
        Attack / Defence state
            ↓
        Trend adjustment
            ↓
        Match-up
            ↓
        lambda_home / lambda_away

    GoalModel не занимается:

    - вероятностями 1X2
    - BTTS
    - totals
    - exact score
    - Club Rating
    - обучением
    - корректировкой по букмекерским коэффициентам
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
    ) -> GoalModelResult:
        """
        Рассчитать ожидаемые голы для конкретного матча.

        Parameters
        ----------
        home_form:
            FormModelResult или совместимый dict/object
            для домашней команды.

        away_form:
            FormModelResult или совместимый dict/object
            для гостевой команды.

        home_team:
            Название домашней команды.

        away_team:
            Название гостевой команды.

        venue:
            Контекст площадки. Сохраняется в результате,
            но НЕ используется как multiplier λ.
        """

        # ----------------------------------------------------
        # 1. Получаем FormModel state
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
        # 2. Attack Levels
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
        # 3. Defence Levels
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
        # 4. Trend adjustments
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
        # 5. Current Attack / Defence states
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
        # 6. Match-up
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
        # 7. Final lambda safety clamp
        # ----------------------------------------------------

        home_xg = self._clip_lambda(home_base_xg)
        away_xg = self._clip_lambda(away_base_xg)

        # ----------------------------------------------------
        # 8. Diagnostics
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
            home_xg=home_xg,
            away_xg=away_xg,
        )

        # ----------------------------------------------------
        # 9. Result
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

            # Здесь сохраняем старые поля ради совместимости,
            # но меняем их семантику согласно v2.

            home_attack_component=home_attack_current,
            away_attack_component=away_attack_current,

            # home_defense_component = defence соперника
            home_defense_component=away_defence_current,

            # away_defense_component = defence хозяев
            away_defense_component=home_defence_current,

            # Venue не является multiplier.
            # Поля сохраняются ради совместимости.
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

            # Сохраняем поля совместимости.
            # В v2 отдельный FormWin / Strength не рассчитывается.
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
        Calculate current attacking level.

        Full formula:

            0.60 * xG_recent
          + 0.30 * xG_avg
          + 0.10 * GoalsFor_avg

        Missing values are excluded and remaining
        weights are normalized.

        None != 0.
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
        Calculate current defensive level.

        Full formula:

            0.60 * xGA_recent
          + 0.30 * xGA_avg
          + 0.10 * GoalsAgainst_avg

        Lower value = stronger defence.

        Missing values are excluded and remaining
        weights are normalized.
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

        Example:

            xG_recent = 1.50
            xG_avg    = 1.30
            GoalsFor  = None

        result:

            (1.50*0.60 + 1.30*0.30) / 0.90
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
        Calculate bounded relative trend.

        T =
            clip(
                trend / max(baseline, 0.5),
                -1,
                +1
            )

        Returns 0.0 when trend/baseline is unavailable.

        Important:

        For xGA:

            T_D < 0 -> improving defence
            T_D > 0 -> worsening defence
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

        return max(-1.0, min(1.0, value))

    # ========================================================
    # APPLY TREND
    # ========================================================

    @staticmethod
    def _apply_trend(
        level: Optional[float],
        trend_adjustment: float,
    ) -> Optional[float]:
        """
        Apply bounded trend to Attack or Defence.

            Level* =
                Level * (1 + 0.20 * T)
        """

        if level is None:
            return None

        return level * (
            1.0 + TREND_WEIGHT * trend_adjustment
        )

    # ========================================================
    # EXPECTED GOALS
    # ========================================================

    @staticmethod
    def _calculate_expected_goals(
        attack_level: Optional[float],
        opponent_defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Match-up calculation.

            lambda =
                (Attack + OpponentDefence) / 2

        Important:

        opponent_defence_level is xGA-based.

        Therefore a HIGH defensive value means
        the opponent allows more chances and should
        increase the attacking team's expected goals.

        A LOW defensive value means a stronger defence
        and therefore reduces expected goals.
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
    # LAMBDA CLAMP
    # ========================================================

    @staticmethod
    def _clip_lambda(
        value: Optional[float],
    ) -> Optional[float]:
        """
        Safety clamp:

            0.15 <= lambda <= 4.50

        None remains None.
        """

        if value is None:
            return None

        return max(
            MIN_LAMBDA,
            min(MAX_LAMBDA, value),
        )

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
        Read value from either:

        - object attribute
        - dict

        Missing field -> default.
        """

        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(field, default)

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
        Convert numeric value to float.

        Rules:

        None -> None
        bool -> None
        invalid -> None

        No implicit None -> 0.
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            result = float(value)
        except (TypeError, ValueError):
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
        Lightweight data-availability confidence.

        Это НЕ probability и НЕ prediction confidence
        в смысле ProbabilityModel.

        Используется только как диагностическое поле.

        Чем больше компонентов доступно,
        тем выше техническая полнота входных данных.
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

        home_xg: Optional[float],
        away_xg: Optional[float],
    ) -> Dict[str, Any]:
        """
        Full mathematical diagnostics.

        Здесь намеренно нет старого coupling блока.
        """

        return {
            "model": "GoalModel",
            "version": GOAL_MODEL_VERSION,
            "formula_status": FORMULA_STATUS,

            "attack": {
                "home": home_attack,
                "away": away_attack,
                "home_current": home_attack_current,
                "away_current": away_attack_current,
            },

            "defence": {
                "home": home_defence,
                "away": away_defence,
                "home_current": home_defence_current,
                "away_current": away_defence_current,

                # Important semantic clarification:
                "home_defense_component":
                    away_defence_current,

                "away_defense_component":
                    home_defence_current,
            },

            "trend": {
                "home_xg": home_attack_trend,
                "away_xg": away_attack_trend,
                "home_xga": home_defence_trend,
                "away_xga": away_defence_trend,
            },

            "lambda": {
                "home_base": home_base_xg,
                "away_base": away_base_xg,
                "home_final": home_xg,
                "away_final": away_xg,
                "min": MIN_LAMBDA,
                "max": MAX_LAMBDA,
            },

            "weights": {
                "attack_recent": ATTACK_RECENT_WEIGHT,
                "attack_avg": ATTACK_AVG_WEIGHT,
                "attack_goals": ATTACK_GOALS_WEIGHT,

                "defence_recent": DEFENCE_RECENT_WEIGHT,
                "defence_avg": DEFENCE_AVG_WEIGHT,
                "defence_goals": DEFENCE_GOALS_WEIGHT,

                "trend": TREND_WEIGHT,
            },

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
    )


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "GOAL_MODEL_VERSION",
    "FORMULA_STATUS",
    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
