#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v3.1
============================================================

Назначение
----------
GoalModel v3.1 разделяет долгосрочную силу команды
(Fundamental Strength) и текущую форму (Current Form).

v3.1 исправляет два математических узких места v3.0:

1. FORM GAP PROTECTION
   Текущая форма может корректировать классовый разрыв,
   но не должна легко уничтожать большой фундаментальный
   разрыв между командами.

2. BASED GOAL ALLOCATION
   В v3.0 общий xG сначала рассчитывался через Attack x
   Defence, но затем индивидуальные HB/AB фактически
   выбрасывались.

   В v3.1 базовое соотношение HB/AB становится основой
   распределения голов.

   Strength/Form остаются корректирующим сигналом,
   а не единственным механизмом распределения.

Архитектура:

    FormModel
        │
        ├── Fundamental Strength
        ├── Current Form
        ├── Regime Change
        └── Opponent Quality
        │
        ▼
    GoalModel v3.1
        │
        ├── Fundamental Attack/Defence
        ├── Form Signal
        ├── Protected Form Gap
        ├── Proximity Gate
        ├── Regime Detection
        ├── Home Advantage
        └── Base + Context Goal Allocation
        │
        ▼
    lambda_home / lambda_away

------------------------------------------------------------
КЛЮЧЕВЫЕ ПРИНЦИПЫ
------------------------------------------------------------

1. Fundamental Strength:
   - Долгосрочное качество команды
   - Сезонные xG/xGA
   - Логарифмическое масштабирование
   - Вес: 60% xG, 40% xGA

2. Current Form:
   - Недавние xG/xGA/SOT/Shots/points
   - Используется как состояние команды
   - Не заменяет фундаментальный класс

3. Proximity Gate:
   - При большом классовом разрыве влияние формы уменьшается
   - При близких командах форма имеет больше значения

4. Form Protection:
   - Форма не может бесконечно компенсировать
     фундаментальный разрыв
   - При близких командах форма может существенно влиять
   - При большом разрыве её влияние ограничивается

5. Regime Change:
   - Требует согласованного сигнала нескольких метрик
   - Не активируется одной случайной победой

6. Home Advantage:
   - +0.12 к итоговому match gap

7. Goal Allocation:
   - HB/AB задают базовую структуру распределения
   - Strength/Form задают контекстную коррекцию
   - Общий xG сохраняется

------------------------------------------------------------
ИЗМЕНЕНИЯ V3.1
------------------------------------------------------------

V3.0:
    TOTAL = HB + AB

    SHARE = sigmoid(strength/form gap)

    HOME_XG = TOTAL * SHARE
    AWAY_XG = TOTAL * (1 - SHARE)

Проблема:
    индивидуальные HB/AB не участвовали в финальном
    распределении голов.

V3.1:

    BASE_SHARE = HB / (HB + AB)

    CONTEXT_SHARE =
        sigmoid(SHARE_SLOPE * match_gap)

    FINAL_SHARE =
        BASE_SHARE * ALLOCATION_BASE_WEIGHT
        +
        CONTEXT_SHARE * ALLOCATION_CONTEXT_WEIGHT

Таким образом:
    Attack × Defence определяет базовый сценарий,
    Strength/Form корректируют его,
    но не заменяют.

Дополнительно:

    protected_form_effect =
        clamp(
            raw_form_effect,
            -form_limit,
            +form_limit
        )

где:

    form_limit =
        max(
            FORM_MIN_PROTECTED_EFFECT,
            FORM_GAP_PROTECTION * abs(strength_gap)
        )

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import math


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "3.1"
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

# Максимальное исходное влияние формы.
FORM_MAX_EFFECT = 0.75

# Масштаб proximity gate.
FORM_GAP_SCALE = 0.90

# ------------------------------------------------------------
# V3.1 FORM PROTECTION
# ------------------------------------------------------------

# Минимальный диапазон, в котором форма всё ещё может
# влиять у практически равных команд.
FORM_MIN_PROTECTED_EFFECT = 0.25

# Доля фундаментального gap, которую форма может
# компенсировать максимум.
#
# 0.60 означает:
# фундаментальный gap = 1.00
# максимальная компенсация формой = 0.60
#
# Следовательно, форма не может просто перевернуть
# фундаментальный перевес в противоположную сторону.
FORM_GAP_PROTECTION = 0.60


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

# Сила контекстной поправки.
SHARE_SLOPE = 1.10

MIN_SHARE = 0.08
MAX_SHARE = 0.92

# ------------------------------------------------------------
# V3.1 ALLOCATION
# ------------------------------------------------------------

# Базовая доля определяется Attack × Defence.
ALLOCATION_BASE_WEIGHT = 0.70

# Контекстная доля определяется Strength + Form + Home.
ALLOCATION_CONTEXT_WEIGHT = 0.30


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
    Результат GoalModel v3.1.

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
# GOAL MODEL v3.1
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v3.1.

    Основная идея:

        FUNDAMENTAL STRENGTH
                 +
            CURRENT FORM
                 +
          MATCH CONTEXT
                 ↓
             GOAL MODEL

    При этом:

        Attack × Defence
              ↓
          TOTAL xG
        + BASE ALLOCATION

    а:

        Strength + Form + Home
              ↓
        CONTEXT ALLOCATION

    Таким образом форма не подменяет фундаментальный класс.
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

        V3.1:
        - Fundamental Strength
        - Current Form
        - Regime Change
        - Proximity Gate
        - Protected Form Gap
        - Home Advantage
        - Base + Context Goal Allocation
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
        # 7. PROXIMITY GATE
        #
        # Большой фундаментальный разрыв:
        # форма получает меньше влияния.
        # ----------------------------------------------------

        strength_gap = hf["score"] - af["score"]

        proximity = 1.0 / (
            1.0 + abs(strength_gap) / FORM_GAP_SCALE
        )

        # ----------------------------------------------------
        # 8. RAW FORM GAP
        # ----------------------------------------------------

        raw_form_gap = (hfs - afs) * proximity

        # ----------------------------------------------------
        # 9. FORM EFFECT BEFORE PROTECTION
        # ----------------------------------------------------

        raw_form_effect = FORM_MAX_EFFECT * raw_form_gap

        # ----------------------------------------------------
        # 10. V3.1 FORM PROTECTION
        #
        # Форма может сильно влиять у равных команд,
        # но не может полностью уничтожить большой
        # фундаментальный gap.
        #
        # Например:
        #
        # strength_gap = +1.00
        # max compensation = 0.60
        #
        # effective gap останется >= +0.40
        # при максимальной компенсации.
        # ----------------------------------------------------

        form_limit = max(
            FORM_MIN_PROTECTED_EFFECT,
            FORM_GAP_PROTECTION * abs(strength_gap),
        )

        protected_form_effect = self._clamp(
            raw_form_effect,
            -form_limit,
            form_limit,
        )

        effective_gap = strength_gap + protected_form_effect

        # ----------------------------------------------------
        # 11. HOME ADVANTAGE
        # ----------------------------------------------------

        match_gap = effective_gap + HOME_ADVANTAGE_LOGIT

        # ----------------------------------------------------
        # 12. FUNDAMENTAL ATTACK / DEFENCE
        # ----------------------------------------------------

        ha = self._fundamental_attack(h)
        aa = self._fundamental_attack(a)

        hd = self._fundamental_defence(h)
        ad = self._fundamental_defence(a)

        # ----------------------------------------------------
        # 13. BASE LAMBDA
        #
        # Attack × opponent Defence.
        # ----------------------------------------------------

        hb = self._matchup(ha, ad)
        ab = self._matchup(aa, hd)

        total = (
            None
            if hb is None or ab is None
            else hb + ab
        )

        # ----------------------------------------------------
        # 14. GOAL ALLOCATION V3.1
        #
        # В отличие от v3.0:
        #
        # HB / TOTAL
        # AB / TOTAL
        #
        # не выбрасываются.
        #
        # Они являются фундаментальной базовой долей.
        #
        # Затем Strength/Form дают контекстную поправку.
        # ----------------------------------------------------

        if total is None or total <= 0:
            hx = None
            ax = None
            base_share = None
            context_share = None
            hs = None
            aws = None

        else:
            # ------------------------------------------------
            # 14.1 BASE SHARE
            # ------------------------------------------------

            base_share = self._clamp(
                hb / total,
                MIN_SHARE,
                MAX_SHARE,
            )

            # ------------------------------------------------
            # 14.2 CONTEXT SHARE
            # ------------------------------------------------

            context_share = self._clamp(
                self._sigmoid(
                    SHARE_SLOPE * match_gap
                ),
                MIN_SHARE,
                MAX_SHARE,
            )

            # ------------------------------------------------
            # 14.3 FINAL SHARE
            #
            # 70% базовая структура
            # 30% контекст
            # ------------------------------------------------

            hs = (
                ALLOCATION_BASE_WEIGHT * base_share
                + ALLOCATION_CONTEXT_WEIGHT * context_share
            )

            hs = self._clamp(
                hs,
                MIN_SHARE,
                MAX_SHARE,
            )

            aws = 1.0 - hs

            # ------------------------------------------------
            # 14.4 FINAL XG
            # ------------------------------------------------

            hx = self._clip(total * hs)
            ax = self._clip(total * aws)

        # ----------------------------------------------------
        # 15. DIAGNOSTICS
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

                "proximity_adjusted_gap": raw_form_gap,

                "raw_form_effect": raw_form_effect,

                "protected_form_effect": protected_form_effect,

                "protection_limit": form_limit,

                "effective_gap": effective_gap,
            },

            # ------------------------------------------------
            # FORM IMPACT
            # ------------------------------------------------

            "form_impact": {
                "proximity_gate": proximity,

                "max_effect": FORM_MAX_EFFECT,

                "raw_effect": raw_form_effect,

                "protected_effect": protected_form_effect,

                "protection_limit": form_limit,

                "protection_ratio": FORM_GAP_PROTECTION,

                "principle": (
                    "form_is_state_modifier_not_strength_replacement"
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
            # EFFECTIVE STRENGTH
            # ------------------------------------------------

            "effective_strength": {
                "home": (
                    hf["score"]
                    + protected_form_effect
                    if protected_form_effect is not None
                    else hf["score"]
                ),

                "away": (
                    af["score"]
                    - protected_form_effect
                    if protected_form_effect is not None
                    else af["score"]
                ),

                "gap_before_home_advantage": effective_gap,

                "match_gap": match_gap,
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
                "total": total,
                "source": (
                    "fundamental_attack_defence_matchup"
                ),
            },

            # ------------------------------------------------
            # GOAL ALLOCATION
            # ------------------------------------------------

            "goal_allocation": {
                "base_share": base_share,

                "context_share": context_share,

                "home_share": hs,
                "away_share": aws,

                "base_weight": ALLOCATION_BASE_WEIGHT,

                "context_weight": ALLOCATION_CONTEXT_WEIGHT,

                "slope": SHARE_SLOPE,

                "min_share": MIN_SHARE,
                "max_share": MAX_SHARE,

                "base_share_source": (
                    "attack_defence_matchup"
                ),

                "context_share_source": (
                    "strength_form_home_advantage"
                ),

                "affects_total_xg": False,
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

                "total_preserved": (
                    None
                    if hx is None or ax is None
                    else hx + ax
                ),
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
        # 16. RESULT
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
    # MATCHUP
    # ========================================================

    @staticmethod
    def _matchup(
        attack_level: Optional[float],
        opponent_defence_level: Optional[float],
    ) -> Optional[float]:
        """
        Базовый matchup:

            lambda =
                (Attack + OpponentDefence) / 2

        Высокий xGA соперника означает более слабую
        оборону и поэтому повышает ожидаемые голы.
        """

        if (
            attack_level is None
            or opponent_defence_level is None
        ):
            return None

        return max(
            MIN_XG_BASELINE,
            (
                attack_level
                + opponent_defence_level
            ) / 2,
        )

    # ========================================================
    # SIGMOID
    # ========================================================

    @staticmethod
    def _sigmoid(
        x: float,
    ) -> float:
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

    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
