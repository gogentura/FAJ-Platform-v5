#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v4.0
============================================================

Назначение
----------
GoalModel v4.0 меняет механизм генерации голов.

Ключевое изменение:

    v3.x:
        Home attack × Away defence → base_H
        Away attack × Home defence → base_A
        total = base_H + base_A
        share = sigmoid(strength_gap)
        λH = total × share
        λA = total × (1 - share)

    v4.0:
        Home attack × Away defence → λH
        Away attack × Home defence → λA

То есть каждая команда получает собственный
голевой потенциал, независимо от соперника.

Больше нет:
    - shared total xG;
    - redistribution through strength_gap;
    - доли от общего пирога.

Форма:
    Вместо перераспределения общего xG
    форма корректирует собственный атакующий λ:
        λH = base_H × (1 + 0.15 × form_H)
        λA = base_A × (1 + 0.15 × form_A)

    Максимум ±15% собственного λ.
    Хорошая форма не уменьшает λ соперника.

Home advantage:
    Не используется как отдельный multiplier.
    Venue уже учтён в фундаментальной истории.

------------------------------------------------------------
ПРИНЦИП
------------------------------------------------------------

    Каждая команда имеет собственный
    атакующий потенциал:

        λH = (Attack_H + Defence_A) / 2
        λA = (Attack_A + Defence_H) / 2

    Total xG больше не является управляющей величиной.

    Сила (strength_gap) остаётся только для 1X2,
    но НЕ перераспределяет xG.

------------------------------------------------------------
ЧТО ИЗМЕНЕНО В V4.0
------------------------------------------------------------

- Убран shared total xG;
- Убран sigmoid goal allocation;
- Убран redistribution through strength_gap;
- Форма корректирует собственный λ (не общий);
- MIN_MATCHUP_XG снижен до 0.15 (было 0.50);
- Home advantage не multiplier (venue уже в истории).

------------------------------------------------------------
ИЗМЕНЕНИЯ ВЕРСИЙ
------------------------------------------------------------

v3.2:
    λH = BASE_H × form_modifier_H × home_multiplier
    λA = BASE_A × form_modifier_A

v4.0:
    λH = BASE_H × (1 + 0.15 × form_H)
    λA = BASE_A × (1 + 0.15 × form_A)

    где form_H, form_A ∈ [-1, +1]
    base_H = (Attack_H + Defence_A) / 2
    base_A = (Attack_A + Defence_H) / 2

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import math


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "4.0"
FORMULA_STATUS = "RESEARCH_FORMULA"


# ============================================================
# BASE PARAMETERS
# ============================================================

# v4.0: сниженный минимум matchup
MIN_MATCHUP_XG = 0.15
MIN_XG_BASELINE = 0.50  # оставлен для совместимости
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

# Диагностический масштаб proximity gate
FORM_GAP_SCALE = 0.90

# ------------------------------------------------------------
# v4.0 FORM INFLUENCE
# ------------------------------------------------------------
#
# Максимальное влияние формы на СВОЙ λ:
#     ±15%
#
FORM_XG_INFLUENCE = 0.15


# ============================================================
# REGIME CHANGE PARAMETERS
# ============================================================

REGIME_PROCESS_THRESHOLD = 0.55
REGIME_ALIGNMENT_THRESHOLD = 0.55
REGIME_MAX_BONUS = 0.35


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
    Результат GoalModel v4.0.

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
# GOAL MODEL v4.0
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v4.0.

    Основная идея:

        HOME ATTACK + AWAY DEFENCE
                    ↓
                   λH

        AWAY ATTACK + HOME DEFENCE
                    ↓
                   λA

    Каждая команда генерирует голы независимо.

    Сила (strength_gap) используется только
    для диагностики и оценки фаворита,
    но НЕ перераспределяет xG.
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

        v4.0:
        - Independent goal generation
        - Form modifies own λ only
        - No shared total
        - No sigmoid allocation
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
        # 6. FORM STRENGTH
        # ----------------------------------------------------

        hfs = self._form_strength(hform, hc, hreg)
        afs = self._form_strength(aform, ac, areg)

        # ----------------------------------------------------
        # 7. DIAGNOSTIC: strength gap и match gap
        #
        # Используется ТОЛЬКО для diagnostics.
        # λ больше не зависит от этих величин.
        # ----------------------------------------------------

        strength_gap = hf["score"] - af["score"]

        proximity = 1.0 / (
            1.0 + abs(strength_gap) / FORM_GAP_SCALE
        )

        form_gap = (hfs - afs) * proximity

        effective_gap = strength_gap + form_gap
        match_gap = effective_gap

        # ====================================================
        # GOAL GENERATION v4.0
        # Independent attacking potential
        # ====================================================

        ha = self._fundamental_attack(h)
        aa = self._fundamental_attack(a)

        hd = self._fundamental_defence(h)
        ad = self._fundamental_defence(a)

        # ----------------------------------------------------
        # 8. Independent matchup xG
        #
        # Home attack vs Away defence
        # Away attack vs Home defence
        #
        # IMPORTANT:
        # No shared total xG.
        # No redistribution through strength_gap.
        # ----------------------------------------------------

        hb = self._independent_matchup(ha, ad)
        ab = self._independent_matchup(aa, hd)

        # ----------------------------------------------------
        # 9. Current form modifies OWN attacking potential only
        # ----------------------------------------------------

        home_form_effect = self._clamp(
            hform["score"] * hc,
            -1.0,
            1.0,
        )

        away_form_effect = self._clamp(
            aform["score"] * ac,
            -1.0,
            1.0,
        )

        if hb is not None:
            hx = hb * (
                1.0 + FORM_XG_INFLUENCE * home_form_effect
            )
        else:
            hx = None

        if ab is not None:
            ax = ab * (
                1.0 + FORM_XG_INFLUENCE * away_form_effect
            )
        else:
            ax = None

        # ----------------------------------------------------
        # 10. Final safety bounds
        # ----------------------------------------------------

        hx = self._clip(hx)
        ax = self._clip(ax)

        # ----------------------------------------------------
        # 11. TOTALS (diagnostics)
        # ----------------------------------------------------

        total_base = (
            None
            if hb is None or ab is None
            else hb + ab
        )

        total_final = (
            None
            if hx is None or ax is None
            else hx + ax
        )

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
                "regime_change": True,
                "opponent_adjustment": True,
                "independent_goal_generation": True,
                "shared_total_used": False,
                "sigmoid_goal_allocation": False,
                "strength_gap_controls_xg_share": False,
                "probability_model": False,
                "score_model": False,
            },

            # ------------------------------------------------
            # FUNDAMENTAL
            # ------------------------------------------------

            "fundamental_strength": {
                "home": hf,
                "away": af,
                "gap": strength_gap,
            },

            # ------------------------------------------------
            # CURRENT FORM
            # ------------------------------------------------

            "current_form": {
                "home": hform,
                "away": aform,

                "raw_gap": hform["score"] - aform["score"],

                "form_strength_home": hfs,
                "form_strength_away": afs,

                "proximity_gate": proximity,
                "effective_gap": effective_gap,
                "match_gap": match_gap,
            },

            # ------------------------------------------------
            # FORM IMPACT
            # ------------------------------------------------

            "form_impact": {
                "direct_xg_influence": FORM_XG_INFLUENCE,

                "home_form_effect": home_form_effect,
                "away_form_effect": away_form_effect,

                "home_modifier": (
                    1.0 + FORM_XG_INFLUENCE * home_form_effect
                ),
                "away_modifier": (
                    1.0 + FORM_XG_INFLUENCE * away_form_effect
                ),

                "principle": (
                    "form_modifies_own_lambda_not_opponent"
                ),
            },

            # ------------------------------------------------
            # REGIME
            # ------------------------------------------------

            "regime_change": {
                "home": hreg,
                "away": areg,
                "principle": (
                    "process_evidence_required_before_strength_shift"
                ),
            },

            # ------------------------------------------------
            # CONFIDENCE
            # ------------------------------------------------

            "confidence": {
                "home": hc,
                "away": ac,
                "home_form_strength": hfs,
                "away_form_strength": afs,
            },

            # ------------------------------------------------
            # OPPONENT QUALITY
            # ------------------------------------------------

            "opponent_adjustment": {
                "home": h["opponent_quality"],
                "away": a["opponent_quality"],
                "used": (
                    h["opponent_quality"] is not None
                    or a["opponent_quality"] is not None
                ),
            },

            # ------------------------------------------------
            # BASE LAMBDA
            # ------------------------------------------------

            "base_lambda": {
                "home": hb,
                "away": ab,
                "total": total_base,
                "source": "independent_attack_defence_matchup",
            },

            # ------------------------------------------------
            # GOAL GENERATION v4.0
            # ------------------------------------------------

            "goal_generation": {
                "version": "4.0",
                "mode": "INDEPENDENT",

                "home": {
                    "attack": ha,
                    "opponent_defence": ad,
                    "base_xg": hb,
                    "form_effect": home_form_effect,
                    "form_multiplier": (
                        1.0 + FORM_XG_INFLUENCE * home_form_effect
                    ),
                    "final_xg": hx,
                },

                "away": {
                    "attack": aa,
                    "opponent_defence": hd,
                    "base_xg": ab,
                    "form_effect": away_form_effect,
                    "form_multiplier": (
                        1.0 + FORM_XG_INFLUENCE * away_form_effect
                    ),
                    "final_xg": ax,
                },

                "shared_total_used": False,
                "strength_gap_used_for_xg_allocation": False,
                "form_used_for_own_xg": True,
            },

            # ------------------------------------------------
            # GOAL ALLOCATION (удалено)
            # ------------------------------------------------

            "goal_allocation": {
                "mode": "INDEPENDENT",
                "home_share": None,
                "away_share": None,
                "shared_total": None,
                "affects_total_xg": False,
                "strength_gap_controls_xg_share": False,
            },

            # ------------------------------------------------
            # FINAL LAMBDA
            # ------------------------------------------------

            "lambda": {
                "home_base": hb,
                "away_base": ab,

                "home_final": hx,
                "away_final": ax,

                "min": MIN_LAMBDA,
                "max": MAX_LAMBDA,

                "total_base": total_base,
                "total_final": total_final,
            },

            # ------------------------------------------------
            # LEGACY SIGNALS
            # ------------------------------------------------

            "legacy_signals": {
                "form_control_received": (
                    home_control is not None
                    or away_control is not None
                ),

                "special_form_received": (
                    home_special is not None
                    or away_special is not None
                ),

                "form_control_used_for_lambda": False,
                "special_form_used_for_lambda": False,
                "winner_signal_v2_3_used": False,
            },

            # ------------------------------------------------
            # EXCLUSIONS
            # ------------------------------------------------

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
    def _snapshot(
        cls,
        s: Any,
    ) -> Dict[str, Optional[float]]:
        """
        Извлекает все необходимые показатели
        из FormModelResult.

        Missing remains None.
        """

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
            n: cls._safe_float(
                cls._get_value(s, n)
            )
            for n in names
        }

    # ========================================================
    # VALUE ACCESS
    # ========================================================

    @staticmethod
    def _get_value(
        s: Any,
        n: str,
        default: Any = None,
    ) -> Any:
        """Унифицированное получение значения."""

        if s is None:
            return default

        if isinstance(s, dict):
            return s.get(n, default)

        return getattr(s, n, default)

    # ========================================================
    # SAFE FLOAT
    # ========================================================

    @staticmethod
    def _safe_float(
        v: Any,
    ) -> Optional[float]:
        """Безопасное преобразование в float."""

        if v is None or isinstance(v, bool):
            return None

        try:
            x = float(v)
        except (TypeError, ValueError):
            return None

        return x if math.isfinite(x) else None

    # ========================================================
    # FUNDAMENTAL ATTACK
    # ========================================================

    @classmethod
    def _fundamental_attack(
        cls,
        s: Dict[str, Optional[float]],
    ) -> Optional[float]:
        """
        Фундаментальная атака:

            90% xG_avg
            10% goals_for_avg
        """

        return cls._weighted([
            (s["xg_avg"], 0.90),
            (s["goals_for_avg"], 0.10),
        ])

    # ========================================================
    # FUNDAMENTAL DEFENCE
    # ========================================================

    @classmethod
    def _fundamental_defence(
        cls,
        s: Dict[str, Optional[float]],
    ) -> Optional[float]:
        """
        Фундаментальная оборона:

            90% xGA_avg
            10% goals_against_avg
        """

        return cls._weighted([
            (s["xga_avg"], 0.90),
            (s["goals_against_avg"], 0.10),
        ])

    # ========================================================
    # FUNDAMENTAL STRENGTH
    # ========================================================

    @classmethod
    def _fundamental(
        cls,
        s: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        """
        Фундаментальная сила команды.

        attack_score:
            log(attack / 1.25)

        defence_score:
            log(1.25 / defence)
        """

        atk = cls._fundamental_attack(s)
        df = cls._fundamental_defence(s)

        ats = (
            None
            if atk is None
            else math.log(
                max(atk, 0.10) / 1.25
            )
        )

        dfs = (
            None
            if df is None
            else math.log(
                1.25 / max(df, 0.10)
            )
        )

        score = cls._weighted([
            (ats, FUNDAMENTAL_XG_WEIGHT),
            (dfs, FUNDAMENTAL_XGA_WEIGHT),
        ])

        return {
            "score": (
                0.0
                if score is None
                else score
            ),

            "attack": atk,
            "defence": df,

            "attack_score": ats,
            "defence_score": dfs,

            "available_components": sum(
                v is not None
                for v in (ats, dfs)
            ),
        }

    # ========================================================
    # CURRENT FORM
    # ========================================================

    @classmethod
    def _form(
        cls,
        s: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        """
        Текущая форма команды.

        Компоненты:

            xG relative
            xGA relative
            SOT ratio
            Shots ratio
            Recent points rate
            Trend
            Opponent quality
        """

        xg = cls._relative(
            s["xg_recent"],
            s["xg_avg"],
            positive=True,
        )

        xga = cls._relative(
            s["xga_recent"],
            s["xga_avg"],
            positive=False,
        )

        sot = cls._ratio(
            s["shots_on_target_avg"],
            4.0,
        )

        shots = cls._ratio(
            s["shots_avg"],
            12.0,
        )

        pts = cls._ratio(
            s["recent_points_rate"],
            1.5,
        )

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
            (
                cls._trend(s["xg_trend"]),
                0.5,
            ),

            (
                cls._trend(-s["xga_trend"])
                if s["xga_trend"] is not None
                else None,
                0.5,
            ),
        ])

        if score is not None and trend is not None:
            score = (
                0.80 * score
                + 0.20 * trend
            )

        # ----------------------------------------------------
        # Opponent quality
        # ----------------------------------------------------

        oq = (
            s["opponent_quality"]
            if s["opponent_quality"] is not None
            else s["opponent_strength"]
        )

        if score is not None and oq is not None:
            score *= (
                0.75
                + 0.25 * cls._clamp(
                    oq,
                    0.70,
                    1.30,
                )
            )

        return {
            "score": (
                0.0
                if score is None
                else cls._clamp(
                    score,
                    -1,
                    1,
                )
            ),

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
    def _confidence(
        cls,
        s: Dict[str, Optional[float]],
    ) -> float:
        """
        Уверенность в данных о команде.

        Учитывает:

            - доступность xG/xGA
            - размер выборки
            - явную FormModel confidence
        """

        vals = (
            s["xg_avg"],
            s["xga_avg"],
            s["xg_recent"],
            s["xga_recent"],
        )

        availability = (
            sum(v is not None for v in vals)
            / 4.0
        )

        n = s["matches_count"]

        sample = (
            1.0
            if n is None
            else cls._clamp(
                n / 6.0,
                0.50,
                1.0,
            )
        )

        explicit = s["form_confidence"]

        if explicit is not None:
            return cls._clamp(
                0.70 * availability * sample
                + 0.30 * cls._clamp(
                    explicit,
                    0,
                    1,
                ),
                0,
                1,
            )

        return cls._clamp(
            availability * sample,
            0,
            1,
        )

    # ========================================================
    # REGIME CHANGE
    # ========================================================

    @classmethod
    def _regime(
        cls,
        s: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        """
        Обнаружение смены режима игры команды.

        Используются:

            xG relative
            xGA relative
            SOT ratio
            Shots ratio
        """

        vals = [
            v
            for v in (
                cls._relative(
                    s["xg_recent"],
                    s["xg_avg"],
                    True,
                ),

                cls._relative(
                    s["xga_recent"],
                    s["xga_avg"],
                    False,
                ),

                cls._ratio(
                    s["shots_on_target_avg"],
                    4.0,
                ),

                cls._ratio(
                    s["shots_avg"],
                    12.0,
                ),
            )
            if v is not None
        ]

        if not vals:
            return {
                "score": 0.0,
                "process": 0.0,
                "alignment": 0.0,
                "active": False,
            }

        pos = sum(
            1 for v in vals
            if v > 0
        )

        neg = sum(
            1 for v in vals
            if v < 0
        )

        alignment = (
            max(pos, neg)
            / len(vals)
        )

        process = (
            sum(vals)
            / len(vals)
        )

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------

        trend = cls._weighted([
            (
                cls._trend(
                    s["xg_trend"]
                ),
                0.5,
            ),

            (
                cls._trend(
                    -s["xga_trend"]
                )
                if s["xga_trend"] is not None
                else None,
                0.5,
            ),
        ])

        if trend is not None:
            process = (
                0.80 * process
                + 0.20 * trend
            )

        active = (
            abs(process)
            >= REGIME_PROCESS_THRESHOLD
            and alignment
            >= REGIME_ALIGNMENT_THRESHOLD
        )

        return {
            "score": cls._clamp(
                process * alignment,
                -1,
                1,
            ),

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
        Итоговая сила формы.

        Regime повышает доказательность формы,
        но не превращает её в новый фундаментальный класс.
        """

        evidence = cls._clamp(
            confidence,
            0.20,
            1.0,
        )

        if regime["active"]:
            evidence = cls._clamp(
                evidence
                + REGIME_MAX_BONUS
                * abs(regime["score"]),
                0,
                1,
            )

        return (
            cls._clamp(
                form["score"],
                -1,
                1,
            )
            * evidence
        )

    # ========================================================
    # INDEPENDENT MATCHUP (v4.0)
    # ========================================================

    @staticmethod
    def _independent_matchup(
        attack: Optional[float],
        opponent_defence: Optional[float],
    ) -> Optional[float]:
        """
        GoalModel v4.0
        Independent goal generation.

        Team attack and opponent defensive vulnerability
        determine the team's own expected goals.

        No shared-total redistribution.

        Сниженный минимум: MIN_MATCHUP_XG = 0.15.
        """
        if attack is None or opponent_defence is None:
            return None

        value = (attack + opponent_defence) / 2.0

        return max(MIN_MATCHUP_XG, float(value))

    # ========================================================
    # LEGACY MATCHUP (для совместимости)
    # ========================================================

    @staticmethod
    def _matchup(
        attack_level: Optional[float],
        opponent_defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Легаси-совместимость.
        Делегирует в _independent_matchup.
        """
        return GoalModel._independent_matchup(
            attack_level,
            opponent_defence_level,
        )

    # ========================================================
    # WEIGHTED
    # ========================================================

    @staticmethod
    def _weighted(
        values: list[
            tuple[
                Optional[float],
                float,
            ]
        ],
    ) -> Optional[float]:
        """
        Взвешенное среднее.

        None исключаются.
        Их веса перераспределяются.

        Missing != 0.
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

            (recent - base)
            / max(|base|, 0.5)

        positive=True:
            рост = улучшение

        positive=False:
            снижение = улучшение
        """

        if recent is None or base is None:
            return None

        diff = (
            recent - base
        ) / max(
            abs(base),
            0.50,
        )

        if not positive:
            diff = -diff

        return GoalModel._clamp(
            diff,
            -1,
            1,
        )

    # ========================================================
    # RATIO GAP
    # ========================================================

    @staticmethod
    def _ratio(
        value: Optional[float],
        baseline: float,
    ) -> Optional[float]:
        """
        Относительное отклонение:

            (value - baseline)
            / max(|baseline|, 0.5)
        """

        if value is None:
            return None

        return GoalModel._clamp(
            (
                value - baseline
            )
            / max(
                abs(baseline),
                0.50,
            ),
            -1,
            1,
        )

    # ========================================================
    # TREND
    # ========================================================

    @staticmethod
    def _trend(
        value: Optional[float],
    ) -> Optional[float]:
        """Нормализация тренда."""

        if value is None:
            return None

        return GoalModel._clamp(
            value / 0.50,
            -1,
            1,
        )

    # ========================================================
    # CLIP
    # ========================================================

    @staticmethod
    def _clip(
        value: Optional[float],
    ) -> Optional[float]:
        """
        Ограничение lambda:

            MIN_LAMBDA ... MAX_LAMBDA
        """

        if value is None:
            return None

        return max(
            MIN_LAMBDA,
            min(
                MAX_LAMBDA,
                float(value),
            ),
        )

    # ========================================================
    # CLAMP
    # ========================================================

    @staticmethod
    def _clamp(
        value: float,
        low: float,
        high: float,
    ) -> float:
        """Ограничение значения."""

        return max(
            low,
            min(
                high,
                value,
            ),
        )


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

    "MIN_MATCHUP_XG",
    "FORM_XG_INFLUENCE",

    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
