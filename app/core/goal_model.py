#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v3.0
============================================================

Назначение
----------
GoalModel v3.0 разделяет долгосрочную силу команды (Fundamental Strength)
и текущую форму (Current Form), а затем объединяет их через
контекстный гейт.

Архитектура:

    FormModel
        │
        ├── Fundamental Strength (xG/xGA сезон)
        ├── Current Form (недавние показатели)
        ├── Regime Change (процессный сигнал)
        └── Opponent Quality (контекст)
        │
        ▼
    GoalModel v3.0
        │
        ├── Fundamental Attack/Defence
        ├── Form Signal (ограниченный)
        ├── Proximity Gate (классовый разрыв)
        ├── Regime Detection
        └── Home Advantage
        │
        ▼
    lambda_home / lambda_away

------------------------------------------------------------
КЛЮЧЕВЫЕ ПРИНЦИПЫ
------------------------------------------------------------

1. Fundamental Strength:
   - Долгосрочное качество команды (сезонные xG/xGA)
   - Логарифмическое масштабирование
   - Вес: 60% xG, 40% xGA

2. Current Form:
   - Недавние показатели (xg_recent, xga_recent, SOT, Shots, points)
   - Влияние ограничено через proximity gate
   - Не может заменить фундаментальную силу

3. Proximity Gate:
   - Чем больше классовый разрыв, тем меньше влияния формы
   - Формула: 1 / (1 + |gap| / 0.90)

4. Regime Change:
   - Требует согласованного сигнала по нескольким метрикам
   - Не срабатывает от одной случайной победы
   - Минимальный порог: 0.55 процесс + 0.55 согласованность

5. Home Advantage:
   - Логистическая поправка +0.12
   - Применяется к итоговому разрыву

6. Goal Allocation:
   - Распределяет общий xG через сигмоиду
   - Максимальная доля: 92%
   - Сохраняет общий объём голов

------------------------------------------------------------
ИЗМЕНЕНИЯ В V3.0
------------------------------------------------------------

- Полное переосмысление архитектуры
- Fundamental Strength отделён от Current Form
- Proximity Gate для контроля влияния формы
- Regime Change как процессный сигнал
- Home Advantage через логит-поправку
- Opponent Quality учитывается в форме

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import math


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "3.0"
FORMULA_STATUS = "RESEARCH_FORMULA"


# ============================================================
# BASE PARAMETERS
# ============================================================

MIN_XG_BASELINE = 0.50
MIN_LAMBDA = 0.15
MAX_LAMBDA = 4.50


# ============================================================
# FUNDAMENTAL STRENGTH PARAMETERS
# ============================================================

FUNDAMENTAL_XG_WEIGHT = 0.60
FUNDAMENTAL_XGA_WEIGHT = 0.40


# ============================================================
# CURRENT FORM PARAMETERS
# ============================================================

FORM_XG_WEIGHT = 0.40
FORM_XGA_WEIGHT = 0.30
FORM_SOT_WEIGHT = 0.15
FORM_SHOTS_WEIGHT = 0.10
FORM_POINTS_WEIGHT = 0.05
FORM_MAX_EFFECT = 0.75
FORM_GAP_SCALE = 0.90


# ============================================================
# REGIME CHANGE PARAMETERS
# ============================================================

REGIME_PROCESS_THRESHOLD = 0.55
REGIME_ALIGNMENT_THRESHOLD = 0.55
REGIME_MAX_BONUS = 0.35


# ============================================================
# HOME ADVANTAGE / ALLOCATION
# ============================================================

HOME_ADVANTAGE_LOGIT = 0.12
SHARE_SLOPE = 1.10
MIN_SHARE = 0.08
MAX_SHARE = 0.92


# ============================================================
# LEGACY EXPORTS (для совместимости)
# ============================================================

ATTACK_RECENT_WEIGHT = 0.60
ATTACK_AVG_WEIGHT = 0.30
ATTACK_GOALS_WEIGHT = 0.10
DEFENCE_RECENT_WEIGHT = 0.60
DEFENCE_AVG_WEIGHT = 0.30
DEFENCE_GOALS_WEIGHT = 0.10
TREND_WEIGHT = 0.20
DOMINANCE_WEIGHT = 0.10
CONTROL_MAX_INFLUENCE = 0.05
SPECIAL_MAX_INFLUENCE = 0.05
MAX_TOTAL_ADJUSTMENT = 0.20
WINNER_XG_WEIGHT = 0.30
WINNER_XGA_WEIGHT = 0.20
WINNER_SOT_WEIGHT = 0.15
WINNER_SHOTS_WEIGHT = 0.10
WINNER_RECENT_POINTS_WEIGHT = 0.05
WINNER_POINTS_WEIGHT = 0.05
WINNER_VENUE_POINTS_WEIGHT = 0.05
WINNER_XG_TREND_WEIGHT = 0.05
WINNER_XGA_TREND_WEIGHT = 0.05
WINNER_MAX_SHARE_SHIFT = 0.18


# ============================================================
# RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Результат GoalModel v3.0.

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
# GOAL MODEL v3.0
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v3.0

    Разделяет долгосрочную силу команды (Fundamental Strength)
    и текущую форму (Current Form).

    Fundamental Strength:
        - Долгосрочное качество (сезонные xG/xGA)
        - Логарифмическое масштабирование
        - Вес: 60% xG, 40% xGA

    Current Form:
        - Недавние показатели
        - Ограничена через proximity gate
        - Не может заменить фундаментальную силу

    Regime Change:
        - Требует согласованного сигнала по нескольким метрикам
        - Не срабатывает от одной случайной победы

    Home Advantage:
        - Логистическая поправка +0.12
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

        v3.0:
        - Fundamental Strength (долгосрочная сила)
        - Current Form (ограниченная форма)
        - Regime Change (процессный сигнал)
        - Proximity Gate (классовый разрыв)
        - Home Advantage (логистическая поправка)
        """

        # ----------------------------------------------------
        # 1. SNAPSHOT
        # ----------------------------------------------------

        h = self._snapshot(home_form)
        a = self._snapshot(away_form)

        # ----------------------------------------------------
        # 2. FUNDAMENTAL STRENGTH
        # ----------------------------------------------------

        hf = self._fundamental(h)
        af = self._fundamental(a)

        # ----------------------------------------------------
        # 3. CONFIDENCE
        # ----------------------------------------------------

        hc = self._confidence(h)
        ac = self._confidence(a)

        # ----------------------------------------------------
        # 4. CURRENT FORM
        # ----------------------------------------------------

        hform = self._form(h)
        aform = self._form(a)

        # ----------------------------------------------------
        # 5. REGIME CHANGE
        # ----------------------------------------------------

        hreg = self._regime(h)
        areg = self._regime(a)

        # ----------------------------------------------------
        # 6. FORM STRENGTH (с учётом уверенности и режима)
        # ----------------------------------------------------

        hfs = self._form_strength(hform, hc, hreg)
        afs = self._form_strength(aform, ac, areg)

        # ----------------------------------------------------
        # 7. PROXIMITY GATE
        #
        # Чем больше классовый разрыв, тем меньше влияния формы.
        # ----------------------------------------------------

        strength_gap = hf["score"] - af["score"]
        proximity = 1.0 / (1.0 + abs(strength_gap) / FORM_GAP_SCALE)

        # ----------------------------------------------------
        # 8. EFFECTIVE GAP
        # ----------------------------------------------------

        form_gap = (hfs - afs) * proximity
        effective_gap = strength_gap + FORM_MAX_EFFECT * form_gap

        # ----------------------------------------------------
        # 9. HOME ADVANTAGE
        # ----------------------------------------------------

        match_gap = effective_gap + HOME_ADVANTAGE_LOGIT

        # ----------------------------------------------------
        # 10. BASE LAMBDA (из фундаментальной атаки/обороны)
        # ----------------------------------------------------

        ha = self._fundamental_attack(h)
        aa = self._fundamental_attack(a)

        hd = self._fundamental_defence(h)
        ad = self._fundamental_defence(a)

        hb = self._matchup(ha, ad)
        ab = self._matchup(aa, hd)

        total = None if hb is None or ab is None else hb + ab

        # ----------------------------------------------------
        # 11. GOAL ALLOCATION (через сигмоиду)
        # ----------------------------------------------------

        if total is None:
            hx = None
            ax = None
            hs = None
            aws = None
        else:
            hs = self._clamp(
                self._sigmoid(SHARE_SLOPE * match_gap),
                MIN_SHARE,
                MAX_SHARE,
            )
            aws = 1.0 - hs
            hx = self._clip(total * hs)
            ax = self._clip(total * aws)

        # ----------------------------------------------------
        # 12. DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics = {
            "model": "GoalModel",
            "version": GOAL_MODEL_VERSION,
            "formula_status": FORMULA_STATUS,

            "architecture": {
                "fundamental_strength": True,
                "current_form": True,
                "contextual_form_gate": True,
                "regime_change": True,
                "opponent_adjustment": True,
                "home_advantage": True,
                "probability_model": False,
                "score_model": False,
            },

            "fundamental_strength": {
                "home": hf,
                "away": af,
                "gap": strength_gap,
            },

            "current_form": {
                "home": hform,
                "away": aform,
                "raw_gap": hform["score"] - aform["score"],
                "effective_gap": form_gap,
            },

            "form_impact": {
                "proximity_gate": proximity,
                "max_effect": FORM_MAX_EFFECT,
                "applied_effect": FORM_MAX_EFFECT * form_gap,
                "principle": "form_is_state_modifier_not_strength_replacement",
            },

            "regime_change": {
                "home": hreg,
                "away": areg,
                "principle": "process_evidence_required_before_strength_shift",
            },

            "effective_strength": {
                "home": hf["score"] + FORM_MAX_EFFECT * hfs * proximity,
                "away": af["score"] + FORM_MAX_EFFECT * afs * proximity,
                "gap_before_home_advantage": effective_gap,
                "match_gap": match_gap,
            },

            "confidence": {
                "home": hc,
                "away": ac,
                "home_form_strength": hfs,
                "away_form_strength": afs,
            },

            "opponent_adjustment": {
                "home": h["opponent_quality"],
                "away": a["opponent_quality"],
                "used": h["opponent_quality"] is not None or a["opponent_quality"] is not None,
            },

            "base_lambda": {
                "home": hb,
                "away": ab,
                "total": total,
                "source": "fundamental_attack_defence_matchup",
            },

            "goal_allocation": {
                "home_share": hs,
                "away_share": aws,
                "slope": SHARE_SLOPE,
                "min_share": MIN_SHARE,
                "max_share": MAX_SHARE,
                "affects_total_xg": False,
            },

            "lambda": {
                "home_base": hb,
                "away_base": ab,
                "home_final": hx,
                "away_final": ax,
                "min": MIN_LAMBDA,
                "max": MAX_LAMBDA,
            },

            "legacy_signals": {
                "form_control_received": home_control is not None or away_control is not None,
                "special_form_received": home_special is not None or away_special is not None,
                "form_control_used_for_lambda": False,
                "special_form_used_for_lambda": False,
                "winner_signal_v2_3_used": False,
            },

            "exclusions": {
                "club_rating_used": False,
                "form_win_used": False,
                "result_strength_used": False,
                "post_match_facts_used": False,
                "bookmaker_odds_used": False,
                "corners_used": False,
                "cards_used": False,
                "prediction_result_leakage": False,
                "venue_multiplier_used": False,
            },
        }

        # ----------------------------------------------------
        # 13. RESULT
        # ----------------------------------------------------

        return GoalModelResult(
            version=GOAL_MODEL_VERSION,

            home_team=home_team,
            away_team=away_team,
            venue=venue,

            home_xg=hx,
            away_xg=ax,

            home_base_xg=hb,
            away_base_xg=ab,

            home_attack_component=ha,
            away_attack_component=aa,

            home_defense_component=ad,
            away_defense_component=hd,

            home_venue_component=None,
            away_venue_component=None,

            home_xg_confidence=hc,
            away_xg_confidence=ac,

            attack_strength=hf["attack"],
            defense_strength=hf["defence"],

            formula_status=FORMULA_STATUS,

            diagnostics=diagnostics,
        )

    # ========================================================
    # SNAPSHOT
    # ========================================================

    @classmethod
    def _snapshot(cls, s: Any) -> Dict[str, Optional[float]]:
        """Извлекает все необходимые показатели из FormModelResult."""
        names = (
            "xg_recent",
            "xg_avg",
            "goals_for_avg",
            "xga_recent",
            "xga_avg",
            "goals_against_avg",
            "xg_trend",
            "xga_trend",
            "shots_avg",
            "shots_against_avg",
            "shots_on_target_avg",
            "shots_on_target_against_avg",
            "recent_points_rate",
            "points_rate",
            "home_points_rate",
            "away_points_rate",
            "matches_count",
            "opponent_strength",
            "opponent_quality",
            "form_confidence",
        )
        return {
            n: cls._safe_float(cls._get_value(s, n))
            for n in names
        }

    @staticmethod
    def _get_value(s: Any, n: str, default: Any = None) -> Any:
        """Унифицированное получение значения."""
        if s is None:
            return default
        if isinstance(s, dict):
            return s.get(n, default)
        return getattr(s, n, default)

    @staticmethod
    def _safe_float(v: Any) -> Optional[float]:
        """Безопасное преобразование в float."""
        if v is None or isinstance(v, bool):
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        return x if math.isfinite(x) else None

    # ========================================================
    # FUNDAMENTAL STRENGTH
    # ========================================================

    @classmethod
    def _fundamental_attack(cls, s: Dict[str, Optional[float]]) -> Optional[float]:
        """Фундаментальная атака: 90% xG_avg + 10% goals_for_avg."""
        return cls._weighted([
            (s["xg_avg"], 0.90),
            (s["goals_for_avg"], 0.10),
        ])

    @classmethod
    def _fundamental_defence(cls, s: Dict[str, Optional[float]]) -> Optional[float]:
        """Фундаментальная оборона: 90% xGA_avg + 10% goals_against_avg."""
        return cls._weighted([
            (s["xga_avg"], 0.90),
            (s["goals_against_avg"], 0.10),
        ])

    @classmethod
    def _fundamental(cls, s: Dict[str, Optional[float]]) -> Dict[str, Any]:
        """
        Фундаментальная сила команды.

        Логарифмическое масштабирование относительно baseline:
            attack_score = log(attack / 1.25)
            defence_score = log(1.25 / defence)
        """
        atk = cls._fundamental_attack(s)
        df = cls._fundamental_defence(s)

        ats = None if atk is None else math.log(max(atk, 0.10) / 1.25)
        dfs = None if df is None else math.log(1.25 / max(df, 0.10))

        score = cls._weighted([
            (ats, FUNDAMENTAL_XG_WEIGHT),
            (dfs, FUNDAMENTAL_XGA_WEIGHT),
        ])

        return {
            "score": 0.0 if score is None else score,
            "attack": atk,
            "defence": df,
            "attack_score": ats,
            "defence_score": dfs,
            "available_components": sum(v is not None for v in (ats, dfs)),
        }

    # ========================================================
    # CURRENT FORM
    # ========================================================

    @classmethod
    def _form(cls, s: Dict[str, Optional[float]]) -> Dict[str, Any]:
        """
        Текущая форма команды.

        Компоненты:
            - xG relative (xg_recent vs xg_avg)
            - xGA relative (xga_recent vs xga_avg, инвертирован)
            - SOT ratio
            - Shots ratio
            - Recent points rate
            - Trend (xg_trend + xga_trend)
            - Opponent quality (контекст)
        """
        xg = cls._relative(s["xg_recent"], s["xg_avg"], positive=True)
        xga = cls._relative(s["xga_recent"], s["xga_avg"], positive=False)
        sot = cls._ratio(s["shots_on_target_avg"], 4.0)
        shots = cls._ratio(s["shots_avg"], 12.0)
        pts = cls._ratio(s["recent_points_rate"], 1.5)

        score = cls._weighted([
            (xg, FORM_XG_WEIGHT),
            (xga, FORM_XGA_WEIGHT),
            (sot, FORM_SOT_WEIGHT),
            (shots, FORM_SHOTS_WEIGHT),
            (pts, FORM_POINTS_WEIGHT),
        ])

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------
        trend = cls._weighted([
            (cls._trend(s["xg_trend"]), 0.5),
            (
                cls._trend(-s["xga_trend"]) if s["xga_trend"] is not None else None,
                0.5,
            ),
        ])

        if score is not None and trend is not None:
            score = 0.80 * score + 0.20 * trend

        # ----------------------------------------------------
        # Opponent quality
        # ----------------------------------------------------
        oq = s["opponent_quality"] if s["opponent_quality"] is not None else s["opponent_strength"]

        if score is not None and oq is not None:
            score *= 0.75 + 0.25 * cls._clamp(oq, 0.70, 1.30)

        return {
            "score": 0.0 if score is None else cls._clamp(score, -1, 1),
            "xg": xg,
            "xga": xga,
            "sot": sot,
            "shots": shots,
            "points": pts,
            "trend": trend,
            "opponent_quality": oq,
        }

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @classmethod
    def _confidence(cls, s: Dict[str, Optional[float]]) -> float:
        """
        Уверенность в данных о команде.

        Учитывает:
            - Доступность xG/xGA данных
            - Количество матчей в выборке
            - Явную уверенность из FormModel (если есть)
        """
        vals = (s["xg_avg"], s["xga_avg"], s["xg_recent"], s["xga_recent"])
        availability = sum(v is not None for v in vals) / 4.0

        n = s["matches_count"]
        sample = 1.0 if n is None else cls._clamp(n / 6.0, 0.50, 1.0)

        explicit = s["form_confidence"]

        if explicit is not None:
            return cls._clamp(
                0.70 * availability * sample + 0.30 * cls._clamp(explicit, 0, 1),
                0,
                1,
            )

        return cls._clamp(availability * sample, 0, 1)

    # ========================================================
    # REGIME CHANGE
    # ========================================================

    @classmethod
    def _regime(cls, s: Dict[str, Optional[float]]) -> Dict[str, Any]:
        """
        Обнаружение смены режима игры команды.

        Требует согласованного сигнала по нескольким метрикам:
            - xG relative
            - xGA relative
            - SOT ratio
            - Shots ratio

        Активна только когда:
            - |process| >= 0.55
            - alignment >= 0.55
        """
        vals = [
            v for v in (
                cls._relative(s["xg_recent"], s["xg_avg"], True),
                cls._relative(s["xga_recent"], s["xga_avg"], False),
                cls._ratio(s["shots_on_target_avg"], 4.0),
                cls._ratio(s["shots_avg"], 12.0),
            )
            if v is not None
        ]

        if not vals:
            return {"score": 0.0, "process": 0.0, "alignment": 0.0, "active": False}

        pos = sum(1 for v in vals if v > 0)
        neg = sum(1 for v in vals if v < 0)
        alignment = max(pos, neg) / len(vals)
        process = sum(vals) / len(vals)

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------
        trend = cls._weighted([
            (cls._trend(s["xg_trend"]), 0.5),
            (
                cls._trend(-s["xga_trend"]) if s["xga_trend"] is not None else None,
                0.5,
            ),
        ])

        if trend is not None:
            process = 0.80 * process + 0.20 * trend

        active = (
            abs(process) >= REGIME_PROCESS_THRESHOLD
            and alignment >= REGIME_ALIGNMENT_THRESHOLD
        )

        return {
            "score": cls._clamp(process * alignment, -1, 1),
            "process": process,
            "alignment": alignment,
            "active": active,
        }

    # ========================================================
    # FORM STRENGTH
    # ========================================================

    @classmethod
    def _form_strength(
        cls,
        form: Dict[str, Any],
        confidence: float,
        regime: Dict[str, Any],
    ) -> float:
        """
        Итоговая сила формы с учётом уверенности и режима.

        Если обнаружена смена режима, уверенность получает бонус.
        """
        evidence = cls._clamp(confidence, 0.20, 1.0)

        if regime["active"]:
            evidence = cls._clamp(
                evidence + REGIME_MAX_BONUS * abs(regime["score"]),
                0,
                1,
            )

        return cls._clamp(form["score"], -1, 1) * evidence

    # ========================================================
    # MATCHUP
    # ========================================================

    @staticmethod
    def _matchup(
        attack_level: Optional[float],
        opponent_defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Базовый matchup:
            lambda = (Attack + OpponentDefence) / 2

        xGA интерпретируется правильно:
            высокий xGA соперника → слабая оборона → высокий lambda
        """
        if attack_level is None or opponent_defence_level is None:
            return None
        return max(MIN_XG_BASELINE, (attack_level + opponent_defence_level) / 2)

    # ========================================================
    # SIGMOID
    # ========================================================

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Логистическая функция."""
        if x >= 0:
            z = math.exp(-x)
            return 1 / (1 + z)
        z = math.exp(x)
        return z / (1 + z)

    # ========================================================
    # WEIGHTED
    # ========================================================

    @staticmethod
    def _weighted(
        values: list[tuple[Optional[float], float]],
    ) -> Optional[float]:
        """
        Взвешенное среднее.

        None значения исключаются, их веса перераспределяются.
        """
        total = 0.0
        weight_sum = 0.0

        for value, weight in values:
            if value is None:
                continue
            total += value * weight
            weight_sum += weight

        if weight_sum <= 0:
            return None

        return total / weight_sum

    # ========================================================
    # RELATIVE GAP
    # ========================================================

    @staticmethod
    def _relative(
        recent: Optional[float],
        base: Optional[float],
        positive: bool,
    ) -> Optional[float]:
        """
        Относительное изменение:
            (recent - base) / max(|base|, 0.5)

        positive=True: положительное = улучшение
        positive=False: отрицательное = улучшение (для xGA)
        """
        if recent is None or base is None:
            return None

        diff = (recent - base) / max(abs(base), 0.50)

        if not positive:
            diff = -diff

        return GoalModel._clamp(diff, -1, 1)

    # ========================================================
    # RATIO GAP
    # ========================================================

    @staticmethod
    def _ratio(
        value: Optional[float],
        baseline: float,
    ) -> Optional[float]:
        """
        Относительное отклонение от baseline:
            (value - baseline) / max(|baseline|, 0.5)
        """
        if value is None:
            return None
        return GoalModel._clamp(
            (value - baseline) / max(abs(baseline), 0.50),
            -1,
            1,
        )

    # ========================================================
    # TREND
    # ========================================================

    @staticmethod
    def _trend(value: Optional[float]) -> Optional[float]:
        """Нормализация тренда."""
        if value is None:
            return None
        return GoalModel._clamp(value / 0.50, -1, 1)

    # ========================================================
    # CLAMP / CLIP
    # ========================================================

    @staticmethod
    def _clip(value: Optional[float]) -> Optional[float]:
        """Ограничение lambda в безопасный диапазон."""
        if value is None:
            return None
        return max(MIN_LAMBDA, min(MAX_LAMBDA, float(value)))

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        """Ограничение значения в диапазоне."""
        return max(low, min(high, value))


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
    return GoalModel().analyze(
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

    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
