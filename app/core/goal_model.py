#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ GoalModel v5.0
============================================================

Purpose
-------
Estimate independent expected goals (lambda) for home and away
teams from:

    Team Class
    + Current Form
    + Opponent Defence
    + Venue Context
    + Available Process Evidence

Core principle
--------------
Football logic first.

The model does NOT:
    - redistribute a shared total xG;
    - use strength gap to steal xG from the opponent;
    - use sigmoid xG allocation;
    - use bookmaker odds;
    - use post-match information;
    - use corners/cards;
    - use prediction results;
    - invent missing values as zero;
    - invent a club rating;
    - apply an arbitrary home-advantage multiplier.

The model generates:

    lambda_home independently
    lambda_away independently

and passes those values downstream to ProbabilityModel.

Architecture
------------
FormContext
    ↓
FormModel
    ↓
Team Class + Current Form
    ↓
Venue shrinkage
    ↓
Opponent Defence
    ↓
Goal Matchup
    ↓
lambda_home / lambda_away
    ↓
ProbabilityModel
    ↓
ScorePredictor

Formula
-------
AttackClass:
    xG average if available
    otherwise goals-for average
    otherwise None

DefenceClass:
    xGA average if available
    otherwise goals-against average
    otherwise None

AttackForm:
    0.60 * xG state
  + 0.25 * xG trend
  + 0.15 * process signal

DefenceForm:
    0.70 * xGA state
  + 0.30 * xGA trend

Effective attack:
    A_eff = A * (1 + 0.12 * F_attack)

Effective defence:
    D_eff = D * (1 - 0.10 * F_defence)

Matchup:
    lambda_home =
        ((A_home_eff + D_away_eff) / 2) * V_home

    lambda_away =
        ((A_away_eff + D_home_eff) / 2) * V_away

Venue
------
No arbitrary home multiplier.

If venue-specific xG is actually supplied, shrink it toward
the overall class:

    alpha = n_venue / (n_venue + 4)

    venue_profile =
        (1 - alpha) * overall_profile
        + alpha * venue_profile

Missing data
------------
Missing != 0.

No fake process data is created from absent histories.

Compatibility
-------------
Existing GoalModelResult fields are retained.
New v5 diagnostics are added through diagnostics.

database.py is not touched.
ProbabilityModel is not touched.
ScorePredictor is not touched.
CornersModel is not touched.
CardsModel is not touched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Sequence
import math


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "5.0"
FORMULA_STATUS = "PRODUCTION_RESEARCH_FORMULA"


# ============================================================
# CORE PARAMETERS
# ============================================================

# Maximum direct influence of current attacking state.
ATTACK_FORM_INFLUENCE = 0.12

# Maximum direct influence of current defensive state.
DEFENCE_FORM_INFLUENCE = 0.10

# Venue shrinkage prior.
VENUE_SHRINKAGE_K = 4.0

# Technical lambda boundaries.
MIN_LAMBDA = 0.0
MAX_LAMBDA = 4.50


# ============================================================
# FORMULA WEIGHTS
# ============================================================

# Attack form.
ATTACK_XG_STATE_WEIGHT = 0.60
ATTACK_XG_TREND_WEIGHT = 0.25
ATTACK_PROCESS_WEIGHT = 0.15

# Process split.
PROCESS_SOT_WEIGHT = 0.50
PROCESS_SHOTS_WEIGHT = 0.50

# Defence form.
DEFENCE_XGA_STATE_WEIGHT = 0.70
DEFENCE_XGA_TREND_WEIGHT = 0.30


# ============================================================
# PROCESS BASELINES
#
# These are used only when actual process averages exist.
# They do NOT create data when fields are missing.
# ============================================================

SHOTS_BASELINE = 12.0
SOT_BASELINE = 4.0


# ============================================================
# ROBUST HISTORY SETTINGS
# ============================================================

EPSILON = 1e-9
MIN_ROBUST_SCALE = 0.25


# ============================================================
# COMPATIBILITY EXPORTS
#
# Existing code may import these names.
# They are retained, but are no longer part of the v5
# mathematical xG allocation.
# ============================================================

MIN_XG_BASELINE = 0.0

FUNDAMENTAL_XG_WEIGHT = 0.60
FUNDAMENTAL_XGA_WEIGHT = 0.40

FORM_XG_WEIGHT = 0.40
FORM_XGA_WEIGHT = 0.30
FORM_SOT_WEIGHT = 0.15
FORM_SHOTS_WEIGHT = 0.10
FORM_POINTS_WEIGHT = 0.05

FORM_MAX_EFFECT = ATTACK_FORM_INFLUENCE
FORM_GAP_SCALE = 0.90

REGIME_PROCESS_THRESHOLD = 0.55
REGIME_ALIGNMENT_THRESHOLD = 0.55
REGIME_MAX_BONUS = 0.35

HOME_ADVANTAGE_LOGIT = 0.0

SHARE_SLOPE = 0.0
MIN_SHARE = 0.0
MAX_SHARE = 1.0

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
# PUBLIC RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Backward-compatible public result.

    Existing positional fields are retained.

    v5-specific information is available through diagnostics.
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
    FAJ GoalModel v5.0.

    The model separates:

        Team Class
            from
        Current State

    and then creates independent goal expectations for both sides.

    No shared total xG is constructed.
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

        home = self._snapshot(home_form)
        away = self._snapshot(away_form)

        # ----------------------------------------------------
        # 1. TEAM CLASS
        # ----------------------------------------------------

        home_attack_class = self._attack_class(home)
        away_attack_class = self._attack_class(away)

        home_defence_class = self._defence_class(home)
        away_defence_class = self._defence_class(away)

        # ----------------------------------------------------
        # 2. CURRENT FORM
        # ----------------------------------------------------

        home_attack_form = self._attack_form(home)
        away_attack_form = self._attack_form(away)

        home_defence_form = self._defence_form(home)
        away_defence_form = self._defence_form(away)

        # ----------------------------------------------------
        # 3. VENUE PROFILE
        # ----------------------------------------------------

        home_attack_venue = self._venue_adjusted_profile(
            overall=home_attack_class,
            venue_value=home.get("venue_attack_xg"),
            venue_matches=home.get("venue_matches"),
        )

        away_attack_venue = self._venue_adjusted_profile(
            overall=away_attack_class,
            venue_value=away.get("venue_attack_xg"),
            venue_matches=away.get("venue_matches"),
        )

        home_defence_venue = self._venue_adjusted_profile(
            overall=home_defence_class,
            venue_value=home.get("venue_defence_xga"),
            venue_matches=home.get("venue_matches"),
        )

        away_defence_venue = self._venue_adjusted_profile(
            overall=away_defence_class,
            venue_value=away.get("venue_defence_xga"),
            venue_matches=away.get("venue_matches"),
        )

        # ----------------------------------------------------
        # 4. EFFECTIVE ATTACK
        # ----------------------------------------------------

        effective_home_attack = self._apply_attack_form(
            home_attack_venue,
            home_attack_form["score"],
        )

        effective_away_attack = self._apply_attack_form(
            away_attack_venue,
            away_attack_form["score"],
        )

        # ----------------------------------------------------
        # 5. EFFECTIVE DEFENCE
        # ----------------------------------------------------

        effective_home_defence = self._apply_defence_form(
            home_defence_venue,
            home_defence_form["score"],
        )

        effective_away_defence = self._apply_defence_form(
            away_defence_venue,
            away_defence_form["score"],
        )

        # ----------------------------------------------------
        # 6. INDEPENDENT MATCHUPS
        #
        # Home goals:
        #     home attack + away defence
        #
        # Away goals:
        #     away attack + home defence
        #
        # Neither branch depends on opponent attack.
        # ----------------------------------------------------

        home_base_xg = self._matchup(
            effective_home_attack,
            effective_away_defence,
        )

        away_base_xg = self._matchup(
            effective_away_attack,
            effective_home_defence,
        )

        # ----------------------------------------------------
        # 7. VENUE MULTIPLIER
        #
        # No arbitrary home advantage.
        #
        # V = 1.0 unless an actual venue-specific profile is
        # available and has been shrunk above.
        #
        # The venue information therefore enters through the
        # profile itself, not through a magic 1.12 multiplier.
        # ----------------------------------------------------

        venue_home = 1.0
        venue_away = 1.0

        home_xg = self._clip_lambda(
            None
            if home_base_xg is None
            else home_base_xg * venue_home
        )

        away_xg = self._clip_lambda(
            None
            if away_base_xg is None
            else away_base_xg * venue_away
        )

        # ----------------------------------------------------
        # 8. DATA CONFIDENCE
        #
        # Descriptive only.
        # It NEVER changes lambda.
        # ----------------------------------------------------

        home_confidence = self._data_confidence(home)
        away_confidence = self._data_confidence(away)

        # ----------------------------------------------------
        # 9. DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics: Dict[str, Any] = {
            "model": "GoalModel",

            "version": GOAL_MODEL_VERSION,

            "formula_status": FORMULA_STATUS,

            "architecture": {
                "team_class": True,
                "current_form": True,
                "venue_context": True,
                "opponent_defence": True,
                "independent_lambda_home": True,
                "independent_lambda_away": True,
                "shared_total_xg": False,
                "sigmoid_xg_allocation": False,
                "strength_gap_controls_xg": False,
                "probability_model": False,
                "score_model": False,
            },

            "formula": {
                "attack_class": (
                    "xG_avg if available, else goals_for_avg"
                ),
                "defence_class": (
                    "xGA_avg if available, else goals_against_avg"
                ),
                "attack_form": (
                    "0.60*R_xG + 0.25*T_xG + 0.15*P_process"
                ),
                "defence_form": (
                    "0.70*R_xGA + 0.30*T_xGA"
                ),
                "effective_attack": (
                    "A * (1 + 0.12*F_attack)"
                ),
                "effective_defence": (
                    "D * (1 - 0.10*F_defence)"
                ),
                "home_lambda": (
                    "((A_home_eff + D_away_eff) / 2) * V_home"
                ),
                "away_lambda": (
                    "((A_away_eff + D_home_eff) / 2) * V_away"
                ),
            },

            "team_class": {
                "home": {
                    "attack_class": home_attack_class,
                    "defence_class": home_defence_class,
                },
                "away": {
                    "attack_class": away_attack_class,
                    "defence_class": away_defence_class,
                },
            },

            "attack_profile": {
                "home": {
                    "overall": home_attack_class,
                    "venue_adjusted": home_attack_venue,
                },
                "away": {
                    "overall": away_attack_class,
                    "venue_adjusted": away_attack_venue,
                },
            },

            "defence_profile": {
                "home": {
                    "overall": home_defence_class,
                    "venue_adjusted": home_defence_venue,
                },
                "away": {
                    "overall": away_defence_class,
                    "venue_adjusted": away_defence_venue,
                },
            },

            "attack_form": {
                "home": home_attack_form["score"],
                "away": away_attack_form["score"],
            },

            "defence_form": {
                "home": home_defence_form["score"],
                "away": away_defence_form["score"],
            },

            "xg_signal": {
                "home": home_attack_form["xg_signal"],
                "away": away_attack_form["xg_signal"],
            },

            "xg_trend_signal": {
                "home": home_attack_form["xg_trend_signal"],
                "away": away_attack_form["xg_trend_signal"],
            },

            "xga_signal": {
                "home": home_defence_form["xga_signal"],
                "away": away_defence_form["xga_signal"],
            },

            "xga_trend_signal": {
                "home": home_defence_form["xga_trend_signal"],
                "away": away_defence_form["xga_trend_signal"],
            },

            "shots_signal": {
                "home": home_attack_form["shots_signal"],
                "away": away_attack_form["shots_signal"],
            },

            "sot_signal": {
                "home": home_attack_form["sot_signal"],
                "away": away_attack_form["sot_signal"],
            },

            "process_signal": {
                "home": home_attack_form["process_signal"],
                "away": away_attack_form["process_signal"],
            },

            "finishing_delta": {
                "home": home.get("finishing_delta"),
                "away": away.get("finishing_delta"),
            },

            "finishing_signal": {
                "home": self._finishing_signal(home),
                "away": self._finishing_signal(away),
            },

            "venue_effect": {
                "home": venue_home,
                "away": venue_away,
                "home_venue_matches": home.get("venue_matches"),
                "away_venue_matches": away.get("venue_matches"),
                "home_venue_alpha": self._venue_alpha(
                    home.get("venue_matches")
                ),
                "away_venue_alpha": self._venue_alpha(
                    away.get("venue_matches")
                ),
                "arbitrary_home_multiplier_used": False,
            },

            "opponent_effect": {
                "home_attack_vs_away_defence": effective_away_defence,
                "away_attack_vs_home_defence": effective_home_defence,
                "home_opponent_attack_used": False,
                "away_opponent_attack_used": False,
            },

            "effective_components": {
                "home_attack": effective_home_attack,
                "away_attack": effective_away_attack,
                "home_defence": effective_home_defence,
                "away_defence": effective_away_defence,
            },

            "base_lambda": {
                "home": home_base_xg,
                "away": away_base_xg,
                "source": "independent_attack_defence_matchup",
            },

            "lambda": {
                "home_base": home_base_xg,
                "away_base": away_base_xg,
                "home_final": home_xg,
                "away_final": away_xg,
                "min": MIN_LAMBDA,
                "max": MAX_LAMBDA,
            },

            "data_confidence": {
                "home": home_confidence,
                "away": away_confidence,
                "descriptive_only": True,
                "changes_lambda": False,
            },

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
                "winner_signal_used": False,
            },

            "exclusions": {
                "club_rating_used": False,
                "invented_rating": False,
                "form_win_used_for_lambda": False,
                "result_strength_used_for_lambda": False,
                "post_match_facts_used": False,
                "bookmaker_odds_used": False,
                "corners_used": False,
                "cards_used": False,
                "prediction_result_leakage": False,
                "shared_total_xg": False,
                "sigmoid_allocation": False,
                "strength_gap_xg_redistribution": False,
                "arbitrary_home_advantage": False,
                "finishing_direct_xg_adjustment": False,
                "missing_data_as_zero": False,
            },

            "availability": {
                "home": self._availability(home),
                "away": self._availability(away),
            },

            "final_outputs": {
                "attack_class_home": home_attack_class,
                "attack_class_away": away_attack_class,
                "defence_class_home": home_defence_class,
                "defence_class_away": away_defence_class,
                "home_base_xg": home_base_xg,
                "away_base_xg": away_base_xg,
                "home_xg": home_xg,
                "away_xg": away_xg,
            },
        }

        return GoalModelResult(
            version=GOAL_MODEL_VERSION,
            home_team=home_team,
            away_team=away_team,
            venue=venue,
            home_xg=home_xg,
            away_xg=away_xg,
            home_base_xg=home_base_xg,
            away_base_xg=away_base_xg,
            home_attack_component=home_attack_class,
            away_attack_component=away_attack_class,
            home_defense_component=away_defence_class,
            away_defense_component=home_defence_class,
            home_venue_component=venue_home,
            away_venue_component=venue_away,
            home_xg_confidence=home_confidence,
            away_xg_confidence=away_confidence,
            attack_strength=home_attack_class,
            defense_strength=home_defence_class,
            formula_status=FORMULA_STATUS,
            diagnostics=diagnostics,
        )

    # ========================================================
    # SNAPSHOT
    # ========================================================

    @classmethod
    def _snapshot(cls, source: Any) -> Dict[str, Any]:
        """
        Extract only values that actually exist.

        Missing values remain None.
        """

        names = (
            # Main six-match values.
            "xg_recent",
            "xg_avg",
            "goals_for_avg",
            "xga_recent",
            "xga_avg",
            "goals_against_avg",

            # Trends.
            "xg_trend",
            "xga_trend",

            # Process averages.
            "shots_avg",
            "shots_against_avg",
            "shots_on_target_avg",
            "shots_on_target_against_avg",

            # Results/context.
            "recent_points_rate",
            "points_rate",
            "home_points_rate",
            "away_points_rate",

            # Sample.
            "matches_count",

            # Existing contextual fields.
            "opponent_strength",
            "opponent_quality",
            "form_confidence",

            # Finishing.
            "finishing_delta",
            "finishing_ratio",

            # Venue profile candidates.
            "home_xg_avg",
            "away_xg_avg",
            "home_xga_avg",
            "away_xga_avg",

            "venue_xg_avg",
            "venue_xga_avg",
            "venue_attack_xg",
            "venue_defence_xga",
            "venue_matches",

            # Possible history fields.
            "xg_history",
            "xga_history",
            "shots_history",
            "shots_against_history",
            "shots_on_target_history",
            "shots_on_target_against_history",

            "recent_xg",
            "recent_xga",
            "recent_shots",
            "recent_sot",
        )

        snapshot: Dict[str, Any] = {}

        for name in names:
            value = cls._get_value(source, name)

            if name.endswith("_history"):
                snapshot[name] = cls._safe_history(value)
            else:
                snapshot[name] = cls._safe_float(value)

        # ----------------------------------------------------
        # Aliases for venue information.
        # ----------------------------------------------------

        if snapshot["venue_attack_xg"] is None:
            snapshot["venue_attack_xg"] = snapshot["home_xg_avg"]

        if snapshot["venue_defence_xga"] is None:
            snapshot["venue_defence_xga"] = snapshot["home_xga_avg"]

        # venue_xg_avg is a generic optional explicit venue field.
        if snapshot["venue_attack_xg"] is None:
            snapshot["venue_attack_xg"] = snapshot["venue_xg_avg"]

        if snapshot["venue_defence_xga"] is None:
            snapshot["venue_defence_xga"] = snapshot["venue_xga_avg"]

        # ----------------------------------------------------
        # FormModel-compatible aliases.
        # ----------------------------------------------------

        if snapshot["xg_recent"] is None:
            snapshot["xg_recent"] = snapshot["recent_xg"]

        if snapshot["xga_recent"] is None:
            snapshot["xga_recent"] = snapshot["recent_xga"]

        return snapshot

    # ========================================================
    # TEAM CLASS
    # ========================================================

    @classmethod
    def _attack_class(cls, s: Dict[str, Any]) -> Optional[float]:
        """
        Structural attacking class.

        Priority:
            xG average
            →
            goals-for average
            →
            None

        Goals are NOT blended with xG when xG exists.
        """

        xg = s.get("xg_avg")

        if xg is not None:
            return max(0.0, xg)

        goals = s.get("goals_for_avg")

        if goals is not None:
            return max(0.0, goals)

        return None

    @classmethod
    def _defence_class(cls, s: Dict[str, Any]) -> Optional[float]:
        """
        Structural defensive exposure.

        Priority:
            xGA average
            →
            goals-against average
            →
            None

        Lower xGA = stronger defence.
        """

        xga = s.get("xga_avg")

        if xga is not None:
            return max(0.0, xga)

        goals_against = s.get("goals_against_avg")

        if goals_against is not None:
            return max(0.0, goals_against)

        return None

    # ========================================================
    # ATTACK FORM
    # ========================================================

    @classmethod
    def _attack_form(cls, s: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Current attacking state.

        F_A =
            0.60 R_xG
          + 0.25 T_xG
          + 0.15 P_process
        """

        xg_signal = cls._relative_state(
            s.get("xg_recent"),
            s.get("xg_avg"),
            positive=True,
        )

        xg_trend_signal = cls._xg_trend_signal(
            s.get("xg_trend"),
            s.get("xg_avg"),
        )

        shots_signal = cls._process_average_signal(
            s.get("shots_avg"),
            SHOTS_BASELINE,
        )

        sot_signal = cls._process_average_signal(
            s.get("shots_on_target_avg"),
            SOT_BASELINE,
        )

        process_signal = cls._weighted_available(
            (
                (sot_signal, PROCESS_SOT_WEIGHT),
                (shots_signal, PROCESS_SHOTS_WEIGHT),
            )
        )

        score = cls._weighted_available(
            (
                (xg_signal, ATTACK_XG_STATE_WEIGHT),
                (xg_trend_signal, ATTACK_XG_TREND_WEIGHT),
                (process_signal, ATTACK_PROCESS_WEIGHT),
            )
        )

        return {
            "score": cls._clamp(
                0.0 if score is None else score,
                -1.0,
                1.0,
            ),
            "xg_signal": xg_signal,
            "xg_trend_signal": xg_trend_signal,
            "shots_signal": shots_signal,
            "sot_signal": sot_signal,
            "process_signal": process_signal,
        }

    # ========================================================
    # DEFENCE FORM
    # ========================================================

    @classmethod
    def _defence_form(cls, s: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Current defensive state.

        Positive value = improving defence.

        F_D =
            0.70 R_xGA
          + 0.30 T_xGA
        """

        xga_signal = cls._relative_state(
            s.get("xga_recent"),
            s.get("xga_avg"),
            positive=False,
        )

        xga_trend_signal = cls._xga_trend_signal(
            s.get("xga_trend"),
            s.get("xga_avg"),
        )

        score = cls._weighted_available(
            (
                (xga_signal, DEFENCE_XGA_STATE_WEIGHT),
                (xga_trend_signal, DEFENCE_XGA_TREND_WEIGHT),
            )
        )

        return {
            "score": cls._clamp(
                0.0 if score is None else score,
                -1.0,
                1.0,
            ),
            "xga_signal": xga_signal,
            "xga_trend_signal": xga_trend_signal,
        }

    # ========================================================
    # EFFECTIVE ATTACK / DEFENCE
    # ========================================================

    @classmethod
    def _apply_attack_form(
        cls,
        attack_class: Optional[float],
        form: Optional[float],
    ) -> Optional[float]:

        if attack_class is None:
            return None

        f = 0.0 if form is None else cls._clamp(form, -1.0, 1.0)

        return max(
            0.0,
            attack_class * (
                1.0 + ATTACK_FORM_INFLUENCE * f
            ),
        )

    @classmethod
    def _apply_defence_form(
        cls,
        defence_class: Optional[float],
        form: Optional[float],
    ) -> Optional[float]:

        if defence_class is None:
            return None

        f = 0.0 if form is None else cls._clamp(form, -1.0, 1.0)

        return max(
            0.0,
            defence_class * (
                1.0 - DEFENCE_FORM_INFLUENCE * f
            ),
        )

    # ========================================================
    # MATCHUP
    # ========================================================

    @classmethod
    def _matchup(
        cls,
        attack: Optional[float],
        opponent_defence: Optional[float],
    ) -> Optional[float]:
        """
        Independent goal branch.

        No arbitrary minimum xG floor.
        """

        if attack is None or opponent_defence is None:
            return None

        return max(
            MIN_LAMBDA,
            (attack + opponent_defence) / 2.0,
        )

    # ========================================================
    # VENUE
    # ========================================================

    @classmethod
    def _venue_adjusted_profile(
        cls,
        *,
        overall: Optional[float],
        venue_value: Optional[float],
        venue_matches: Optional[float],
    ) -> Optional[float]:
        """
        Shrink venue-specific evidence toward the overall class.

            alpha = n / (n + 4)

            profile =
                (1-alpha)*overall + alpha*venue_value
        """

        if overall is None:
            return venue_value

        if venue_value is None:
            return overall

        alpha = cls._venue_alpha(venue_matches)

        return (
            (1.0 - alpha) * overall
            + alpha * venue_value
        )

    @staticmethod
    def _venue_alpha(
        venue_matches: Optional[float],
    ) -> float:

        if venue_matches is None:
            return 0.0

        n = max(0.0, float(venue_matches))

        return n / (n + VENUE_SHRINKAGE_K)

    # ========================================================
    # STATE SIGNALS
    # ========================================================

    @classmethod
    def _relative_state(
        cls,
        recent: Optional[float],
        baseline: Optional[float],
        *,
        positive: bool,
    ) -> Optional[float]:
        """
        Relative recent-vs-class signal.

        Positive=True:
            higher recent value is better.

        Positive=False:
            lower recent value is better.

        Denominator uses the actual baseline.
        A small technical epsilon is used only to prevent
        division by zero.
        """

        if recent is None or baseline is None:
            return None

        denominator = max(abs(baseline), EPSILON)

        delta = (recent - baseline) / denominator

        if not positive:
            delta = -delta

        return cls._clamp(delta, -1.0, 1.0)

    @classmethod
    def _xg_trend_signal(
        cls,
        trend: Optional[float],
        baseline: Optional[float],
    ) -> Optional[float]:
        """
        T_xG = tanh(xG_trend / xG_avg)

        No arbitrary ±0.50 normalization.
        """

        if trend is None:
            return None

        denominator = max(
            abs(baseline) if baseline is not None else 0.0,
            EPSILON,
        )

        return cls._clamp(
            math.tanh(trend / denominator),
            -1.0,
            1.0,
        )

    @classmethod
    def _xga_trend_signal(
        cls,
        trend: Optional[float],
        baseline: Optional[float],
    ) -> Optional[float]:
        """
        T_xGA = -tanh(xGA_trend / xGA_avg)

        Increasing xGA = worse defence.
        Decreasing xGA = better defence.
        """

        if trend is None:
            return None

        denominator = max(
            abs(baseline) if baseline is not None else 0.0,
            EPSILON,
        )

        return cls._clamp(
            -math.tanh(trend / denominator),
            -1.0,
            1.0,
        )

    @classmethod
    def _process_average_signal(
        cls,
        value: Optional[float],
        baseline: float,
    ) -> Optional[float]:

        if value is None:
            return None

        denominator = max(abs(baseline), EPSILON)

        return cls._clamp(
            (value - baseline) / denominator,
            -1.0,
            1.0,
        )

    # ========================================================
    # PROCESS HISTORY
    # ========================================================

    @classmethod
    def _history_process_signal(
        cls,
        history: Optional[Sequence[Any]],
    ) -> Optional[float]:
        """
        Optional robust recent-vs-history process signal.

        This function is deliberately conservative.

        It returns None unless an actual history is supplied.
        """

        values = cls._numeric_history(history)

        if len(values) < 2:
            return None

        midpoint = max(1, len(values) // 2)

        baseline_values = values[:midpoint]
        recent_values = values[midpoint:]

        if not baseline_values or not recent_values:
            return None

        baseline = cls._median(baseline_values)
        recent = cls._median(recent_values)

        scale = cls._robust_scale(baseline_values)

        denominator = max(
            scale,
            MIN_ROBUST_SCALE,
        )

        return cls._clamp(
            (recent - baseline) / denominator,
            -1.0,
            1.0,
        )

    # ========================================================
    # FINISHING
    # ========================================================

    @classmethod
    def _finishing_signal(
        cls,
        s: Dict[str, Any],
    ) -> Optional[float]:
        """
        Finishing remains diagnostic in v5.0.

        It does NOT modify lambda.
        """

        delta = s.get("finishing_delta")

        if delta is not None:
            return cls._clamp(
                math.tanh(delta),
                -1.0,
                1.0,
            )

        ratio = s.get("finishing_ratio")

        if ratio is not None:
            return cls._clamp(
                math.tanh(ratio - 1.0),
                -1.0,
                1.0,
            )

        gf = s.get("goals_for_avg")
        xg = s.get("xg_avg")

        if gf is None or xg is None:
            return None

        return cls._clamp(
            math.tanh(gf - xg),
            -1.0,
            1.0,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @classmethod
    def _data_confidence(
        cls,
        s: Dict[str, Any],
    ) -> Optional[float]:
        """
        Descriptive data quality only.

        IMPORTANT:
            confidence NEVER modifies lambda.
        """

        dimensions = []

        # Sample.
        n = s.get("matches_count")

        if n is not None:
            dimensions.append(
                cls._clamp(n / 6.0, 0.0, 1.0)
            )

        # xG availability.
        xg_available = (
            s.get("xg_avg") is not None
            and s.get("xga_avg") is not None
        )

        dimensions.append(
            1.0 if xg_available else 0.0
        )

        # Recent xG availability.
        recent_available = (
            s.get("xg_recent") is not None
            and s.get("xga_recent") is not None
        )

        dimensions.append(
            1.0 if recent_available else 0.0
        )

        # Process availability.
        process_available = (
            s.get("shots_avg") is not None
            or s.get("shots_on_target_avg") is not None
        )

        dimensions.append(
            1.0 if process_available else 0.0
        )

        # Venue availability.
        venue_available = (
            s.get("venue_attack_xg") is not None
            and s.get("venue_matches") is not None
            and s.get("venue_matches", 0.0) > 0
        )

        dimensions.append(
            1.0 if venue_available else 0.0
        )

        if not dimensions:
            return None

        return cls._clamp(
            sum(dimensions) / len(dimensions),
            0.0,
            1.0,
        )

    # ========================================================
    # AVAILABILITY
    # ========================================================

    @classmethod
    def _availability(
        cls,
        s: Dict[str, Any],
    ) -> Dict[str, bool]:

        return {
            "xg_avg": s.get("xg_avg") is not None,
            "xga_avg": s.get("xga_avg") is not None,
            "goals_for_avg": s.get("goals_for_avg") is not None,
            "goals_against_avg": s.get("goals_against_avg") is not None,
            "xg_recent": s.get("xg_recent") is not None,
            "xga_recent": s.get("xga_recent") is not None,
            "xg_trend": s.get("xg_trend") is not None,
            "xga_trend": s.get("xga_trend") is not None,
            "shots_avg": s.get("shots_avg") is not None,
            "shots_on_target_avg": (
                s.get("shots_on_target_avg") is not None
            ),
            "shots_history": bool(s.get("shots_history")),
            "sot_history": bool(
                s.get("shots_on_target_history")
            ),
            "venue_profile": (
                s.get("venue_attack_xg") is not None
                and s.get("venue_matches") is not None
            ),
        }

    # ========================================================
    # NUMERIC HELPERS
    # ========================================================

    @staticmethod
    def _get_value(
        source: Any,
        name: str,
        default: Any = None,
    ) -> Any:

        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(name, default)

        return getattr(source, name, default)

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(number):
            return None

        return number

    @classmethod
    def _safe_history(
        cls,
        value: Any,
    ) -> Optional[tuple]:

        if value is None:
            return None

        if isinstance(value, (str, bytes)):
            return None

        try:
            values = tuple(value)
        except TypeError:
            return None

        result = []

        for item in values:
            number = cls._safe_float(item)

            if number is not None:
                result.append(number)

        return tuple(result) if result else None

    @classmethod
    def _numeric_history(
        cls,
        history: Optional[Sequence[Any]],
    ) -> tuple:

        if not history:
            return ()

        values = []

        for item in history:
            number = cls._safe_float(item)

            if number is not None:
                values.append(number)

        return tuple(values)

    @staticmethod
    def _weighted_available(
        values: Iterable,
    ) -> Optional[float]:

        total = 0.0
        weight_total = 0.0

        for value, weight in values:
            if value is None:
                continue

            total += float(value) * float(weight)
            weight_total += float(weight)

        if weight_total <= 0.0:
            return None

        return total / weight_total

    @staticmethod
    def _clamp(
        value: float,
        low: float,
        high: float,
    ) -> float:

        return max(low, min(high, value))

    @classmethod
    def _clip_lambda(
        cls,
        value: Optional[float],
    ) -> Optional[float]:

        if value is None:
            return None

        return cls._clamp(
            float(value),
            MIN_LAMBDA,
            MAX_LAMBDA,
        )

    # ========================================================
    # ROBUST STATISTICS
    # ========================================================

    @staticmethod
    def _median(
        values: Sequence[float],
    ) -> float:

        ordered = sorted(values)

        n = len(ordered)

        if n == 0:
            return 0.0

        middle = n // 2

        if n % 2:
            return ordered[middle]

        return (
            ordered[middle - 1]
            + ordered[middle]
        ) / 2.0

    @classmethod
    def _robust_scale(
        cls,
        values: Sequence[float],
    ) -> float:

        if not values:
            return 0.0

        median = cls._median(values)

        deviations = [
            abs(value - median)
            for value in values
        ]

        return cls._median(deviations)

    # ========================================================
    # PUBLIC FUNCTION
    # ========================================================


def calculate_expected_goals(
    home_form: Any,
    away_form: Any,
    **kwargs: Any,
) -> GoalModelResult:
    """
    Backward-compatible helper.
    """

    return GoalModel().analyze(
        home_form,
        away_form,
        **kwargs,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "GOAL_MODEL_VERSION",
    "FORMULA_STATUS",
    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
