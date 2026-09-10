#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
GOAL MODEL v5.1
============================================================

Independent Venue-Aware Goal Model

Architecture:

    FormContext
        ↓
    FormModel
        ↓
    Team Class
        +
    Current Form
        +
    HOME/AWAY context
        ↓
    Goal Matchup
        ↓
    λ Home / λ Away
        ↓
    ProbabilityModel
        ↓
    ScorePredictor

Principles
----------
1. xG is the primary attack/defence measure.
2. Goals are fallback / diagnostic, not a second xG model.
3. Home and away context are explicit when real venue data exists.
4. Small venue samples are shrunk toward the overall profile.
5. Current form modifies the team's own λ only.
6. λH and λA are generated independently.
7. No shared total-xG redistribution.
8. No sigmoid allocation.
9. No strength-gap redistribution.
10. No bookmaker odds.
11. No post-match leakage.
12. Missing data = None, never 0.
13. Confidence is descriptive and never changes λ.
14. Finishing is diagnostic only.
15. GoalModel does not modify ProbabilityModel or ScorePredictor.
============================================================
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# VERSION / STATUS
# ============================================================

GOAL_MODEL_VERSION = "5.1"
FORMULA_STATUS = "PRODUCTION_RESEARCH_FORMULA"


# ============================================================
# STRUCTURAL PARAMETERS
# ============================================================

# Maximum influence of current attacking form.
ATTACK_FORM_INFLUENCE = 0.12

# Maximum influence of current defensive form.
DEFENCE_FORM_INFLUENCE = 0.10

# Venue shrinkage:
#
# alpha = n / (n + K)
#
# n=1  -> 0.20
# n=2  -> 0.33
# n=4  -> 0.50
# n=6  -> 0.60
# n=10 -> 0.71
#
VENUE_SHRINKAGE_K = 4.0

# Technical λ limits only.
MIN_LAMBDA = 0.0
MAX_LAMBDA = 4.50

# xG cannot be used as a denominator when effectively zero.
MIN_BASE = 0.50

# Attack-form composition.
ATTACK_XG_WEIGHT = 0.60
ATTACK_TREND_WEIGHT = 0.25
ATTACK_PROCESS_WEIGHT = 0.15

# Process split when both SOT and shots are genuinely available.
PROCESS_SOT_WEIGHT = 0.50
PROCESS_SHOTS_WEIGHT = 0.50

# Defence-form composition.
DEFENCE_XGA_WEIGHT = 0.70
DEFENCE_TREND_WEIGHT = 0.30

# Conservative process reference levels.
#
# These are only used when FormModel exposes process averages
# without histories. They do NOT create data when the fields
# are missing.
SOT_REFERENCE = 4.0
SHOTS_REFERENCE = 12.0


# ============================================================
# LEGACY CONSTANTS
# ============================================================

# Kept for compatibility with older imports.
MIN_XG_BASELINE = 0.0
MIN_MATCHUP_XG = 0.0
HOME_ADVANTAGE_LOGIT = 0.0


# ============================================================
# PUBLIC RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Public GoalModel result.

    Legacy fields are preserved for downstream compatibility.
    New v5.1 information is exposed through diagnostics.
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
    FAJ GoalModel v5.1.

    The model estimates expected goals independently:

        λH = matchup(Home attack, Away defence)

        λA = matchup(Away attack, Home defence)

    Current form modifies the team's own attack/defence class.

    Venue information is applied only when genuine venue-specific
    historical data is available.

    No arbitrary home multiplier is used.
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
        home_history: Any = None,
        away_history: Any = None,
    ) -> GoalModelResult:
        """
        Calculate independent expected goals.

        Existing callers using the old signature remain valid.

        Optional:
            home_history
            away_history

        If supplied, these may contain historical match records.
        They are used only to derive genuine venue-specific
        profiles.
        """

        h = self._snapshot(home_form)
        a = self._snapshot(away_form)

        # ----------------------------------------------------
        # Optional raw history
        # ----------------------------------------------------

        h_history = self._extract_history(
            home_history,
            home_form,
        )

        a_history = self._extract_history(
            away_history,
            away_form,
        )

        # ----------------------------------------------------
        # Overall team classes
        # ----------------------------------------------------

        home_attack_class = self._fundamental_attack(h)
        away_attack_class = self._fundamental_attack(a)

        home_defence_class = self._fundamental_defence(h)
        away_defence_class = self._fundamental_defence(a)

        # ----------------------------------------------------
        # Venue-aware profiles
        # ----------------------------------------------------

        home_attack_profile, home_attack_venue_meta = (
            self._venue_profile(
                overall=home_attack_class,
                form_snapshot=h,
                history=h_history,
                venue="HOME",
                kind="attack",
            )
        )

        away_attack_profile, away_attack_venue_meta = (
            self._venue_profile(
                overall=away_attack_class,
                form_snapshot=a,
                history=a_history,
                venue="AWAY",
                kind="attack",
            )
        )

        home_defence_profile, home_defence_venue_meta = (
            self._venue_profile(
                overall=home_defence_class,
                form_snapshot=h,
                history=h_history,
                venue="HOME",
                kind="defence",
            )
        )

        away_defence_profile, away_defence_venue_meta = (
            self._venue_profile(
                overall=away_defence_class,
                form_snapshot=a,
                history=a_history,
                venue="AWAY",
                kind="defence",
            )
        )

        # ----------------------------------------------------
        # Current attack form
        # ----------------------------------------------------

        home_attack_form_data = self._attack_form(h)
        away_attack_form_data = self._attack_form(a)

        # ----------------------------------------------------
        # Current defence form
        # ----------------------------------------------------

        home_defence_form_data = self._defence_form(h)
        away_defence_form_data = self._defence_form(a)

        # ----------------------------------------------------
        # Effective attack
        # ----------------------------------------------------

        home_attack_effective = self._apply_attack_form(
            home_attack_profile,
            home_attack_form_data["score"],
        )

        away_attack_effective = self._apply_attack_form(
            away_attack_profile,
            away_attack_form_data["score"],
        )

        # ----------------------------------------------------
        # Effective defence
        #
        # Lower xGA = stronger defence.
        #
        # F_D > 0:
        #     good defensive form
        #     lowers opponent λ
        #
        # F_D < 0:
        #     bad defensive form
        #     raises opponent λ
        # ----------------------------------------------------

        home_defence_effective = self._apply_defence_form(
            home_defence_profile,
            home_defence_form_data["score"],
        )

        away_defence_effective = self._apply_defence_form(
            away_defence_profile,
            away_defence_form_data["score"],
        )

        # ----------------------------------------------------
        # Independent matchups
        # ----------------------------------------------------

        home_base_xg = self._matchup(
            home_attack_effective,
            away_defence_effective,
        )

        away_base_xg = self._matchup(
            away_attack_effective,
            home_defence_effective,
        )

        # ----------------------------------------------------
        # Venue factor
        #
        # IMPORTANT:
        #
        # There is NO arbitrary 1.06 / 1.10 / 1.12.
        #
        # If explicit venue data exists, the venue-specific
        # profile itself changes the matchup.
        #
        # Otherwise V = 1.
        # ----------------------------------------------------

        home_venue_effect = (
            home_attack_venue_meta.get("effect", 1.0)
        )

        away_venue_effect = (
            away_attack_venue_meta.get("effect", 1.0)
        )

        # Venue is already represented through the profile.
        # Therefore no second multiplier is applied.
        venue_home_multiplier = 1.0
        venue_away_multiplier = 1.0

        home_xg = self._clip(
            None
            if home_base_xg is None
            else home_base_xg * venue_home_multiplier
        )

        away_xg = self._clip(
            None
            if away_base_xg is None
            else away_base_xg * venue_away_multiplier
        )

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------

        home_confidence = self._confidence(
            h,
            venue_meta=home_attack_venue_meta,
        )

        away_confidence = self._confidence(
            a,
            venue_meta=away_attack_venue_meta,
        )

        # ----------------------------------------------------
        # Finishing diagnostic
        # ----------------------------------------------------

        home_finishing_delta = self._safe_float(
            h.get("finishing_delta")
        )

        away_finishing_delta = self._safe_float(
            a.get("finishing_delta")
        )

        home_finishing_signal = self._finishing_signal(
            home_finishing_delta
        )

        away_finishing_signal = self._finishing_signal(
            away_finishing_delta
        )

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        diagnostics: Dict[str, Any] = {
            "model": "GoalModel",
            "version": GOAL_MODEL_VERSION,
            "formula_status": FORMULA_STATUS,

            "architecture": {
                "team_class": True,
                "current_form": True,
                "venue_context": True,
                "venue_shrinkage": True,
                "independent_lambda": True,
                "opponent_defence": True,
                "finishing_diagnostic": True,
                "probability_model": False,
                "score_model": False,
                "corners_model": False,
                "cards_model": False,
            },

            "formula": {
                "home": (
                    "((A_home_eff + D_away_eff) / 2) * V_home"
                ),
                "away": (
                    "((A_away_eff + D_home_eff) / 2) * V_away"
                ),
                "attack_form_influence": ATTACK_FORM_INFLUENCE,
                "defence_form_influence": DEFENCE_FORM_INFLUENCE,
            },

            "team_class": {
                "home_attack": home_attack_class,
                "away_attack": away_attack_class,
                "home_defence": home_defence_class,
                "away_defence": away_defence_class,
            },

            "attack_profile": {
                "home": home_attack_profile,
                "away": away_attack_profile,
            },

            "defence_profile": {
                "home": home_defence_profile,
                "away": away_defence_profile,
            },

            "attack_form": {
                "home": home_attack_form_data["score"],
                "away": away_attack_form_data["score"],
            },

            "defence_form": {
                "home": home_defence_form_data["score"],
                "away": away_defence_form_data["score"],
            },

            "xg_signal": {
                "home": home_attack_form_data["xg_signal"],
                "away": away_attack_form_data["xg_signal"],
            },

            "xg_trend_signal": {
                "home": home_attack_form_data["trend_signal"],
                "away": away_attack_form_data["trend_signal"],
            },

            "shots_signal": {
                "home": home_attack_form_data["shots_signal"],
                "away": away_attack_form_data["shots_signal"],
            },

            "sot_signal": {
                "home": home_attack_form_data["sot_signal"],
                "away": away_attack_form_data["sot_signal"],
            },

            "finishing_delta": {
                "home": home_finishing_delta,
                "away": away_finishing_delta,
            },

            "finishing_signal": {
                "home": home_finishing_signal,
                "away": away_finishing_signal,
            },

            "venue_effect": {
                "home": home_venue_effect,
                "away": away_venue_effect,
                "home_multiplier": venue_home_multiplier,
                "away_multiplier": venue_away_multiplier,
                "home_data_available": (
                    home_attack_venue_meta.get("available", False)
                ),
                "away_data_available": (
                    away_attack_venue_meta.get("available", False)
                ),
            },

            "venue_meta": {
                "home_attack": home_attack_venue_meta,
                "away_attack": away_attack_venue_meta,
                "home_defence": home_defence_venue_meta,
                "away_defence": away_defence_venue_meta,
            },

            "opponent_effect": {
                "home": away_defence_effective,
                "away": home_defence_effective,
            },

            "data_confidence": {
                "home": home_confidence,
                "away": away_confidence,
            },

            "home_base_xg": home_base_xg,
            "away_base_xg": away_base_xg,

            "home_xg": home_xg,
            "away_xg": away_xg,

            "effective_components": {
                "home_attack": home_attack_effective,
                "away_attack": away_attack_effective,
                "home_defence": home_defence_effective,
                "away_defence": away_defence_effective,
            },

            "lambda": {
                "home_base": home_base_xg,
                "away_base": away_base_xg,
                "home_final": home_xg,
                "away_final": away_xg,
                "min": MIN_LAMBDA,
                "max": MAX_LAMBDA,
            },

            "independence": {
                "home_lambda_depends_on_away_attack": False,
                "away_lambda_depends_on_home_attack": False,
                "shared_total_used": False,
                "strength_gap_controls_xg_share": False,
                "sigmoid_allocation_used": False,
                "total_xg_redistribution": False,
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
                "form_win_used": False,
                "result_strength_used": False,
                "post_match_facts_used": False,
                "bookmaker_odds_used": False,
                "corners_used": False,
                "cards_used": False,
                "prediction_result_leakage": False,
                "arbitrary_home_multiplier_used": False,
                "finishing_used_for_lambda": False,
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

            # Preserve legacy component semantics:
            # attack component = own attack class
            # defence component = opponent defence class
            home_attack_component=home_attack_class,
            away_attack_component=away_attack_class,
            home_defense_component=away_defence_class,
            away_defense_component=home_defence_class,

            home_venue_component=(
                home_venue_effect
                if home_attack_venue_meta.get("available", False)
                else None
            ),
            away_venue_component=(
                away_venue_effect
                if away_attack_venue_meta.get("available", False)
                else None
            ),

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
        Extract known FormModel fields.

        Unknown fields remain None.

        Missing != 0.
        """

        names = (
            # Main xG / goals
            "xg_recent",
            "xg_avg",
            "goals_for_avg",
            "xga_recent",
            "xga_avg",
            "goals_against_avg",

            # Trend
            "xg_trend",
            "xga_trend",

            # Process averages
            "shots_avg",
            "shots_against_avg",
            "shots_on_target_avg",
            "shots_on_target_against_avg",

            # Process histories
            "shots_history",
            "shots_against_history",
            "shots_on_target_history",
            "shots_on_target_against_history",

            # xG histories
            "xg_history",
            "xga_history",

            # Form / context
            "recent_points_rate",
            "points_rate",
            "home_points_rate",
            "away_points_rate",
            "matches_count",
            "opponent_strength",
            "opponent_quality",
            "form_confidence",

            # Explicit venue fields if a future FormModel exposes them
            "venue_attack_xg",
            "venue_defence_xga",
            "venue_matches",

            "home_xg_avg",
            "away_xg_avg",
            "home_xga_avg",
            "away_xga_avg",

            # Existing FormModel diagnostics
            "finishing_delta",
            "finishing_ratio",
            "defensive_delta",

            "home_coverage",
            "away_coverage",
        )

        result: Dict[str, Any] = {}

        for name in names:
            result[name] = cls._safe_value(
                cls._get_value(source, name)
            )

        return result

    # ========================================================
    # HISTORY
    # ========================================================

    @classmethod
    def _extract_history(
        cls,
        explicit_history: Any,
        form_source: Any,
    ) -> Optional[Sequence[Any]]:
        """
        Extract raw historical records if genuinely available.

        Priority:
            1. explicit_history
            2. history / matches fields on FormModel object
            3. None

        No synthetic history is created.
        """

        if explicit_history is not None:
            if isinstance(explicit_history, (list, tuple)):
                return explicit_history

            value = cls._get_value(
                explicit_history,
                "matches",
                None,
            )

            if isinstance(value, (list, tuple)):
                return value

            value = cls._get_value(
                explicit_history,
                "history",
                None,
            )

            if isinstance(value, (list, tuple)):
                return value

        for name in (
            "history",
            "matches",
            "recent_matches",
            "match_history",
            "records",
        ):
            value = cls._get_value(form_source, name, None)

            if isinstance(value, (list, tuple)):
                return value

        return None

    # ========================================================
    # TEAM CLASS
    # ========================================================

    @classmethod
    def _fundamental_attack(
        cls,
        snapshot: Dict[str, Any],
    ) -> Optional[float]:
        """
        Attack class:

            xG average
            fallback goals-for average

        Goals are not blended with xG.
        """

        xg = snapshot.get("xg_avg")

        if xg is not None:
            return max(0.0, xg)

        goals = snapshot.get("goals_for_avg")

        if goals is not None:
            return max(0.0, goals)

        return None

    @classmethod
    def _fundamental_defence(
        cls,
        snapshot: Dict[str, Any],
    ) -> Optional[float]:
        """
        Defensive exposure class:

            xGA average
            fallback goals-against average

        Lower is better.
        """

        xga = snapshot.get("xga_avg")

        if xga is not None:
            return max(0.0, xga)

        goals_against = snapshot.get("goals_against_avg")

        if goals_against is not None:
            return max(0.0, goals_against)

        return None

    # ========================================================
    # VENUE PROFILE
    # ========================================================

    @classmethod
    def _venue_profile(
        cls,
        *,
        overall: Optional[float],
        form_snapshot: Dict[str, Any],
        history: Optional[Sequence[Any]],
        venue: str,
        kind: str,
    ) -> Tuple[Optional[float], Dict[str, Any]]:
        """
        Build venue-specific profile.

        Strict rule:

        Explicit venue data only.

        No guessing that a generic home_xg_avg means venue
        data unless the field is explicitly present as such.

        If history is supplied, it may be used to derive the
        profile from actual HOME/AWAY records.
        """

        if overall is None:
            return None, {
                "available": False,
                "effect": 1.0,
                "sample": 0,
                "alpha": 0.0,
                "reason": "overall_profile_missing",
            }

        explicit_value = cls._explicit_venue_value(
            form_snapshot,
            venue=venue,
            kind=kind,
        )

        explicit_n = cls._explicit_venue_sample(
            form_snapshot,
        )

        if explicit_value is not None and explicit_n is not None:
            return cls._shrink_venue(
                overall=overall,
                venue_value=explicit_value,
                n=explicit_n,
                source="explicit_form_model",
            )

        # ----------------------------------------------------
        # Derive venue profile from genuine raw history.
        # ----------------------------------------------------

        if history:
            values = []

            for record in history:
                if not cls._record_matches_venue(record, venue):
                    continue

                value = cls._record_metric(
                    record,
                    kind=kind,
                )

                if value is not None:
                    values.append(value)

            if values:
                venue_value = sum(values) / len(values)

                return cls._shrink_venue(
                    overall=overall,
                    venue_value=venue_value,
                    n=len(values),
                    source="raw_history",
                )

        return overall, {
            "available": False,
            "effect": 1.0,
            "sample": 0,
            "alpha": 0.0,
            "profile": overall,
            "source": "overall_only",
        }

    @classmethod
    def _explicit_venue_value(
        cls,
        snapshot: Dict[str, Any],
        *,
        venue: str,
        kind: str,
    ) -> Optional[float]:
        """
        Read only semantically explicit venue fields.

        For the actual current FormModel v1.2 contract these
        fields may be absent. In that case None is returned.
        """

        if kind == "attack":
            if venue == "HOME":
                return snapshot.get("venue_attack_xg")

            if venue == "AWAY":
                value = snapshot.get("venue_attack_xg")

                if value is not None:
                    return value

        if kind == "defence":
            if venue == "HOME":
                return snapshot.get("venue_defence_xga")

            if venue == "AWAY":
                value = snapshot.get("venue_defence_xga")

                if value is not None:
                    return value

        return None

    @classmethod
    def _explicit_venue_sample(
        cls,
        snapshot: Dict[str, Any],
    ) -> Optional[int]:
        value = snapshot.get("venue_matches")

        if value is None:
            return None

        try:
            n = int(value)
        except (TypeError, ValueError):
            return None

        return max(0, n)

    @classmethod
    def _shrink_venue(
        cls,
        *,
        overall: float,
        venue_value: float,
        n: int,
        source: str,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Shrink venue profile toward overall profile.

            alpha = n / (n + 4)

            result = overall*(1-alpha) + venue*alpha
        """

        if n <= 0:
            return overall, {
                "available": False,
                "effect": 1.0,
                "sample": 0,
                "alpha": 0.0,
                "profile": overall,
                "source": source,
            }

        alpha = n / (n + VENUE_SHRINKAGE_K)

        profile = (
            (1.0 - alpha) * overall
            + alpha * max(0.0, venue_value)
        )

        effect = (
            profile / overall
            if overall > 1e-9
            else 1.0
        )

        return profile, {
            "available": True,
            "effect": effect,
            "sample": n,
            "alpha": alpha,
            "overall": overall,
            "venue_raw": venue_value,
            "profile": profile,
            "source": source,
        }

    # ========================================================
    # ATTACK FORM
    # ========================================================

    @classmethod
    def _attack_form(
        cls,
        snapshot: Dict[str, Any],
    ) -> Dict[str, Optional[float]]:
        """
        Attack form:

            0.60 xG state
            0.25 xG trend
            0.15 process

        xG is primary.

        Shots/SOT are residual process evidence only.
        """

        xg_signal = cls._relative(
            snapshot.get("xg_recent"),
            snapshot.get("xg_avg"),
            positive=True,
        )

        trend_signal = cls._xg_trend_signal(
            snapshot.get("xg_trend"),
            snapshot.get("xg_avg"),
        )

        sot_signal = cls._process_signal(
            snapshot,
            average_name="shots_on_target_avg",
            history_name="shots_on_target_history",
            reference=SOT_REFERENCE,
        )

        shots_signal = cls._process_signal(
            snapshot,
            average_name="shots_avg",
            history_name="shots_history",
            reference=SHOTS_REFERENCE,
        )

        process = cls._weighted(
            [
                (sot_signal, PROCESS_SOT_WEIGHT),
                (shots_signal, PROCESS_SHOTS_WEIGHT),
            ]
        )

        score = cls._weighted(
            [
                (xg_signal, ATTACK_XG_WEIGHT),
                (trend_signal, ATTACK_TREND_WEIGHT),
                (process, ATTACK_PROCESS_WEIGHT),
            ]
        )

        if score is None:
            score = 0.0

        return {
            "score": cls._clamp(score, -1.0, 1.0),
            "xg_signal": xg_signal,
            "trend_signal": trend_signal,
            "shots_signal": shots_signal,
            "sot_signal": sot_signal,
            "process_signal": process,
        }

    # ========================================================
    # DEFENCE FORM
    # ========================================================

    @classmethod
    def _defence_form(
        cls,
        snapshot: Dict[str, Any],
    ) -> Dict[str, Optional[float]]:
        """
        Defence form:

            0.70 xGA state
            0.30 xGA trend

        Lower recent xGA than normal = positive defensive form.
        """

        xga_signal = cls._relative(
            snapshot.get("xga_recent"),
            snapshot.get("xga_avg"),
            positive=False,
        )

        trend_signal = cls._xga_trend_signal(
            snapshot.get("xga_trend"),
            snapshot.get("xga_avg"),
        )

        score = cls._weighted(
            [
                (xga_signal, DEFENCE_XGA_WEIGHT),
                (trend_signal, DEFENCE_TREND_WEIGHT),
            ]
        )

        if score is None:
            score = 0.0

        return {
            "score": cls._clamp(score, -1.0, 1.0),
            "xga_signal": xga_signal,
            "trend_signal": trend_signal,
        }

    # ========================================================
    # FORM APPLICATION
    # ========================================================

    @classmethod
    def _apply_attack_form(
        cls,
        attack_class: Optional[float],
        form_score: Optional[float],
    ) -> Optional[float]:
        if attack_class is None:
            return None

        if form_score is None:
            return attack_class

        return max(
            0.0,
            attack_class
            * (
                1.0
                + ATTACK_FORM_INFLUENCE
                * cls._clamp(form_score, -1.0, 1.0)
            ),
        )

    @classmethod
    def _apply_defence_form(
        cls,
        defence_class: Optional[float],
        form_score: Optional[float],
    ) -> Optional[float]:
        if defence_class is None:
            return None

        if form_score is None:
            return defence_class

        return max(
            0.0,
            defence_class
            * (
                1.0
                - DEFENCE_FORM_INFLUENCE
                * cls._clamp(form_score, -1.0, 1.0)
            ),
        )

    # ========================================================
    # MATCHUP
    # ========================================================

    @staticmethod
    def _matchup(
        attack: Optional[float],
        opponent_defence: Optional[float],
    ) -> Optional[float]:
        """
        Independent matchup.

            λ = (attack + opponent defensive exposure) / 2

        No minimum football prior is imposed.
        """

        if attack is None or opponent_defence is None:
            return None

        return max(
            MIN_LAMBDA,
            (
                max(0.0, attack)
                + max(0.0, opponent_defence)
            )
            / 2.0,
        )

    # ========================================================
    # PROCESS SIGNAL
    # ========================================================

    @classmethod
    def _process_signal(
        cls,
        snapshot: Dict[str, Any],
        *,
        average_name: str,
        history_name: str,
        reference: float,
    ) -> Optional[float]:
        """
        Process signal.

        Priority:

        1. Genuine history → recent-vs-median robust signal.
        2. Otherwise explicit process average → conservative
           reference signal.
        3. Missing → None.

        No zero is fabricated.
        """

        history = snapshot.get(history_name)

        if isinstance(history, (list, tuple)):
            values = []

            for value in history:
                x = cls._safe_float(value)

                if x is not None:
                    values.append(x)

            if len(values) >= 2:
                median = cls._median(values)

                recent = values[-1]

                deviations = [
                    abs(v - median)
                    for v in values
                ]

                mad = cls._median(deviations)

                scale = max(
                    1.4826 * mad,
                    0.50,
                )

                return cls._clamp(
                    (recent - median) / scale,
                    -1.0,
                    1.0,
                )

        average = snapshot.get(average_name)

        if average is None:
            return None

        return cls._clamp(
            (average - reference)
            / max(abs(reference), MIN_BASE),
            -1.0,
            1.0,
        )

    # ========================================================
    # TREND SIGNALS
    # ========================================================

    @classmethod
    def _xg_trend_signal(
        cls,
        trend: Optional[float],
        average: Optional[float],
    ) -> Optional[float]:
        if trend is None:
            return None

        denominator = max(
            abs(average) if average is not None else MIN_BASE,
            MIN_BASE,
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
        average: Optional[float],
    ) -> Optional[float]:
        if trend is None:
            return None

        denominator = max(
            abs(average) if average is not None else MIN_BASE,
            MIN_BASE,
        )

        # Positive defensive signal means improving defence,
        # therefore a positive xGA trend must be inverted.
        return cls._clamp(
            -math.tanh(trend / denominator),
            -1.0,
            1.0,
        )

    # ========================================================
    # RELATIVE SIGNAL
    # ========================================================

    @classmethod
    def _relative(
        cls,
        recent: Optional[float],
        base: Optional[float],
        positive: bool,
    ) -> Optional[float]:
        if recent is None or base is None:
            return None

        denominator = max(
            abs(base),
            MIN_BASE,
        )

        delta = (recent - base) / denominator

        if not positive:
            delta = -delta

        return cls._clamp(
            delta,
            -1.0,
            1.0,
        )

    # ========================================================
    # FINISHING
    # ========================================================

    @classmethod
    def _finishing_signal(
        cls,
        finishing_delta: Optional[float],
    ) -> Optional[float]:
        """
        Finishing is diagnostic only.

        It does NOT modify λ.
        """

        if finishing_delta is None:
            return None

        return cls._clamp(
            math.tanh(finishing_delta / 0.50),
            -1.0,
            1.0,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @classmethod
    def _confidence(
        cls,
        snapshot: Dict[str, Any],
        *,
        venue_meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        """
        Descriptive confidence.

        IMPORTANT:
        It never modifies expected goals.
        """

        values = (
            snapshot.get("xg_avg"),
            snapshot.get("xga_avg"),
            snapshot.get("xg_recent"),
            snapshot.get("xga_recent"),
        )

        availability = (
            sum(v is not None for v in values)
            / float(len(values))
        )

        n = snapshot.get("matches_count")

        if n is None:
            sample = 1.0
        else:
            sample = cls._clamp(
                float(n) / 6.0,
                0.50,
                1.0,
            )

        confidence = availability * sample

        explicit = snapshot.get("form_confidence")

        if explicit is not None:
            confidence = (
                0.70 * confidence
                + 0.30 * cls._clamp(
                    explicit,
                    0.0,
                    1.0,
                )
            )

        if venue_meta and venue_meta.get("available"):
            # Venue availability is descriptive only.
            # It does not affect λ.
            confidence = min(
                1.0,
                confidence + 0.05,
            )

        return cls._clamp(
            confidence,
            0.0,
            1.0,
        )

    # ========================================================
    # RAW HISTORY HELPERS
    # ========================================================

    @classmethod
    def _record_matches_venue(
        cls,
        record: Any,
        venue: str,
    ) -> bool:
        """
        Determine whether a historical record is actually
        HOME/AWAY for the team.

        Supported representations:
            venue = HOME/AWAY
            is_home = True/False
            home_team / away_team

        If relationship cannot be established, record is ignored.
        """

        value = cls._get_value(
            record,
            "venue",
            None,
        )

        if isinstance(value, str):
            normalized = value.strip().upper()

            if normalized in {
                "HOME",
                "H",
                "ДОМА",
                "Д",
            }:
                return venue == "HOME"

            if normalized in {
                "AWAY",
                "A",
                "GUEST",
                "ГОСТИ",
                "Г",
            }:
                return venue == "AWAY"

        is_home = cls._get_value(
            record,
            "is_home",
            None,
        )

        if isinstance(is_home, bool):
            return is_home if venue == "HOME" else not is_home

        return False

    @classmethod
    def _record_metric(
        cls,
        record: Any,
        *,
        kind: str,
    ) -> Optional[float]:
        if kind == "attack":
            for name in (
                "xg",
                "expected_goals",
                "team_xg",
                "xgf",
            ):
                value = cls._safe_float(
                    cls._get_value(record, name, None)
                )

                if value is not None:
                    return value

            return None

        if kind == "defence":
            for name in (
                "xga",
                "opponent_xg",
                "against_xg",
                "xg_against",
            ):
                value = cls._safe_float(
                    cls._get_value(record, name, None)
                )

                if value is not None:
                    return value

            return None

        return None

    # ========================================================
    # GENERIC HELPERS
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

        return getattr(
            source,
            name,
            default,
        )

    @classmethod
    def _safe_value(
        cls,
        value: Any,
    ) -> Any:
        """
        Preserve histories/lists while safely normalizing scalars.
        """

        if isinstance(value, (list, tuple)):
            return value

        return cls._safe_float(value)

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None

        try:
            x = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(x):
            return None

        return x

    @staticmethod
    def _weighted(
        values: Iterable[Tuple[Optional[float], float]],
    ) -> Optional[float]:
        total = 0.0
        weight = 0.0

        for value, wt in values:
            if value is None:
                continue

            if wt <= 0:
                continue

            total += value * wt
            weight += wt

        if weight <= 0:
            return None

        return total / weight

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

    @staticmethod
    def _clip(
        value: Optional[float],
    ) -> Optional[float]:
        if value is None:
            return None

        return max(
            MIN_LAMBDA,
            min(
                MAX_LAMBDA,
                float(value),
            ),
        )

    @staticmethod
    def _clamp(
        value: float,
        low: float,
        high: float,
    ) -> float:
        return max(
            low,
            min(
                high,
                value,
            ),
        )


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

def calculate_expected_goals(
    home_form: Any,
    away_form: Any,
    **kwargs: Any,
) -> GoalModelResult:
    """
    Compatibility wrapper.
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
