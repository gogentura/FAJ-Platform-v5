#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
GOAL MODEL v6.0
============================================================

STATUS:
    GOLD_FAJ_GOAL

PURPOSE:
    Mathematical expected-goals engine for FAJ Brain.

CORE PRINCIPLE:
    Team State + Matchup State

CORE EQUATIONS:

    A_eff = sqrt(A_structural * A_recent)
    D_eff = sqrt(D_structural * D_recent)

    lambda_home =
        sqrt(A_home_eff * D_away_eff)

    lambda_away =
        sqrt(A_away_eff * D_home_eff)

IMPORTANT:

    xG is the primary attacking/defensive observation.

    xGA is the primary defensive observation.

    Goals are used only as a fallback when xG/xGA
    are genuinely unavailable.

    No league baseline.
    No artificial home coefficient.
    No arbitrary multipliers.
    No sigmoid redistribution.
    No strength-gap redistribution.
    No finishing multiplier.
    No confidence multiplier.
    No post-match information.
    Missing != 0.

============================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from math import sqrt
from typing import Any, Dict, Iterable, List, Mapping, Optional


MODEL_VERSION = "6.0"
MODEL_STATUS = "GOLD_FAJ_GOAL"

MIN_LAMBDA = 0.0
MAX_LAMBDA = 4.50


# ============================================================
# RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Public result returned by GoalModel.

    Compatibility fields are intentionally retained so that
    downstream FAJ Brain / ProbabilityModel components can
    continue consuming the object without requiring a parallel
    schema.
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v6.0.

    The model converts pre-match team state into expected goals.

    It deliberately does NOT attempt to:
        - predict 1X2 directly;
        - redistribute probability;
        - fit historical match results;
        - use post-match information;
        - create an artificial league average;
        - use confidence as a prediction multiplier.

    GoalModel owns only lambda generation.
    """

    VERSION = MODEL_VERSION
    STATUS = MODEL_STATUS

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
        Calculate expected goals for the match.

        Parameters
        ----------
        home_form:
            FormModel result / dict / compatible object.

        away_form:
            FormModel result / dict / compatible object.

        home_history:
            Optional historical records used only for data-driven
            home venue context.

        away_history:
            Optional historical records used only for data-driven
            away venue context.

        home_control / away_control:
            Accepted for pipeline compatibility.

        home_special / away_special:
            Accepted for pipeline compatibility.

        They are intentionally NOT used as arbitrary lambda
        multipliers in v6.0.
        """

        home = self._snapshot(home_form)
        away = self._snapshot(away_form)

        # ----------------------------------------------------
        # 1. STRUCTURAL TEAM STATE
        # ----------------------------------------------------

        home_struct_attack = self._structural_attack(home)
        away_struct_attack = self._structural_attack(away)

        home_struct_defense = self._structural_defense(home)
        away_struct_defense = self._structural_defense(away)

        # ----------------------------------------------------
        # 2. RECENT TEAM STATE
        # ----------------------------------------------------

        home_recent_attack = self._recent_attack(
            home,
            fallback=home_struct_attack,
        )

        away_recent_attack = self._recent_attack(
            away,
            fallback=away_struct_attack,
        )

        home_recent_defense = self._recent_defense(
            home,
            fallback=home_struct_defense,
        )

        away_recent_defense = self._recent_defense(
            away,
            fallback=away_struct_defense,
        )

        # ----------------------------------------------------
        # 3. EFFECTIVE TEAM STATE
        #
        # Geometric mean prevents one component from completely
        # dominating the other and keeps the scale in xG units.
        # ----------------------------------------------------

        home_attack_eff = self._geometric(
            home_struct_attack,
            home_recent_attack,
        )

        away_attack_eff = self._geometric(
            away_struct_attack,
            away_recent_attack,
        )

        home_defense_eff = self._geometric(
            home_struct_defense,
            home_recent_defense,
        )

        away_defense_eff = self._geometric(
            away_struct_defense,
            away_recent_defense,
        )

        # ----------------------------------------------------
        # 4. VENUE CONTEXT
        #
        # No artificial coefficient.
        #
        # If historical venue-specific xG exists, it can provide
        # an observed venue component.
        #
        # Otherwise venue component remains neutral (1.0).
        # ----------------------------------------------------

        home_venue = self._venue_xg(
            home_history,
            is_home=True,
        )

        away_venue = self._venue_xg(
            away_history,
            is_home=False,
        )

        home_structural_for_match = self._combine_venue_context(
            home_attack_eff,
            home_venue,
        )

        away_structural_for_match = self._combine_venue_context(
            away_attack_eff,
            away_venue,
        )

        home_defensive_for_match = self._combine_venue_context(
            home_defense_eff,
            home_venue,
        )

        away_defensive_for_match = self._combine_venue_context(
            away_defense_eff,
            away_venue,
        )

        # ----------------------------------------------------
        # 5. MATCHUP
        #
        # This is the mathematical heart of v6.0.
        #
        # Attack of one team interacts directly with defence
        # of the opponent.
        #
        # Both quantities are measured in goals/match.
        #
        # sqrt(A * D) therefore remains in goals/match.
        # ----------------------------------------------------

        home_lambda = self._matchup(
            home_structural_for_match,
            away_defensive_for_match,
        )

        away_lambda = self._matchup(
            away_structural_for_match,
            home_defensive_for_match,
        )

        # ----------------------------------------------------
        # 6. NUMERICAL SAFETY BOUND
        #
        # This is NOT a football coefficient.
        # It only prevents numerical explosions downstream.
        # ----------------------------------------------------

        home_lambda = self._clip_lambda(home_lambda)
        away_lambda = self._clip_lambda(away_lambda)

        # ----------------------------------------------------
        # 7. DIAGNOSTIC INFORMATION
        #
        # Diagnostics describe the calculation.
        # They do not modify lambda.
        # ----------------------------------------------------

        home_confidence = self._confidence(home)
        away_confidence = self._confidence(away)

        home_finishing = self._num(home.get("finishing_delta"))
        away_finishing = self._num(away.get("finishing_delta"))

        diagnostics = {
            "model": "FAJ GoalModel",
            "version": self.VERSION,
            "status": self.STATUS,

            "formula": {
                "effective_attack":
                    "sqrt(structural_attack * recent_attack)",
                "effective_defense":
                    "sqrt(structural_defense * recent_defense)",
                "home_lambda":
                    "sqrt(home_attack_eff * away_defense_eff)",
                "away_lambda":
                    "sqrt(away_attack_eff * home_defense_eff)",
            },

            "principles": [
                "xG is primary attacking observation",
                "xGA is primary defensive observation",
                "goals are fallback only when xG/xGA are unavailable",
                "structural state and recent state are geometrically combined",
                "attack interacts directly with opponent defence",
                "no artificial home advantage coefficient",
                "no league baseline",
                "no sigmoid redistribution",
                "no strength-gap redistribution",
                "no finishing multiplier",
                "no confidence multiplier",
                "missing != 0",
                "post-match data forbidden",
            ],

            "home": {
                "structural_attack": home_struct_attack,
                "recent_attack": home_recent_attack,
                "effective_attack": home_attack_eff,

                "structural_defense": home_struct_defense,
                "recent_defense": home_recent_defense,
                "effective_defense": home_defense_eff,

                "venue_xg": home_venue,
                "confidence": home_confidence,
                "finishing_delta": home_finishing,
            },

            "away": {
                "structural_attack": away_struct_attack,
                "recent_attack": away_recent_attack,
                "effective_attack": away_attack_eff,

                "structural_defense": away_struct_defense,
                "recent_defense": away_recent_defense,
                "effective_defense": away_defense_eff,

                "venue_xg": away_venue,
                "confidence": away_confidence,
                "finishing_delta": away_finishing,
            },

            "matchup": {
                "home_attack_vs_away_defense": home_lambda,
                "away_attack_vs_home_defense": away_lambda,
            },

            "lambda": {
                "home": home_lambda,
                "away": away_lambda,
                "total": self._sum(home_lambda, away_lambda),
            },

            "ignored_inputs": {
                "home_control": home_control is not None,
                "away_control": away_control is not None,
                "home_special": home_special is not None,
                "away_special": away_special is not None,
            },
        }

        # ----------------------------------------------------
        # Compatibility fields
        #
        # "base_xg" now means matchup lambda.
        # No second hidden formula exists.
        # ----------------------------------------------------

        return GoalModelResult(
            version=self.VERSION,
            home_team=home_team,
            away_team=away_team,
            venue=venue,

            home_xg=home_lambda,
            away_xg=away_lambda,

            home_base_xg=home_lambda,
            away_base_xg=away_lambda,

            home_attack_component=home_attack_eff,
            away_attack_component=away_attack_eff,

            home_defense_component=home_defense_eff,
            away_defense_component=away_defense_eff,

            home_venue_component=home_venue,
            away_venue_component=away_venue,

            home_xg_confidence=home_confidence,
            away_xg_confidence=away_confidence,

            attack_strength=None,
            defense_strength=None,

            formula_status=self.STATUS,

            diagnostics=diagnostics,
        )

    # ========================================================
    # SNAPSHOT / INPUT NORMALIZATION
    # ========================================================

    @staticmethod
    def _snapshot(value: Any) -> Dict[str, Any]:
        """
        Convert dataclass / dict / normal object into a safe dict.

        No mutation of the original object.
        """

        if value is None:
            return {}

        if isinstance(value, Mapping):
            return dict(value)

        if is_dataclass(value):
            try:
                return asdict(value)
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            try:
                return dict(vars(value))
            except Exception:
                pass

        return {}

    # ========================================================
    # STRUCTURAL ATTACK
    # ========================================================

    def _structural_attack(
        self,
        form: Dict[str, Any],
    ) -> Optional[float]:
        """
        Primary:
            xg_avg

        Fallback:
            goals_for_avg

        Important:
            zero is a valid numeric value.
            Only None means missing.
        """

        xg = self._num(form.get("xg_avg"))

        if xg is not None:
            return xg

        goals = self._num(form.get("goals_for_avg"))

        return goals

    # ========================================================
    # STRUCTURAL DEFENCE
    # ========================================================

    def _structural_defense(
        self,
        form: Dict[str, Any],
    ) -> Optional[float]:
        """
        Primary:
            xga_avg

        Fallback:
            goals_against_avg

        Lower xGA means stronger defensive resistance.
        The model intentionally keeps xGA in its observed
        goals/match scale instead of converting it into an
        invented "defence strength" coefficient.
        """

        xga = self._num(form.get("xga_avg"))

        if xga is not None:
            return xga

        goals_against = self._num(
            form.get("goals_against_avg")
        )

        return goals_against

    # ========================================================
    # RECENT ATTACK
    # ========================================================

    def _recent_attack(
        self,
        form: Dict[str, Any],
        *,
        fallback: Optional[float],
    ) -> Optional[float]:
        """
        Primary:
            FormModel.xg_recent

        Fallback:
            structural attack.

        xg_recent is already temporally weighted by FormModel.
        """

        recent = self._num(form.get("xg_recent"))

        if recent is not None:
            return recent

        history = self._numeric_history(
            form.get("xg_history")
        )

        if history:
            return self._mean(history)

        return fallback

    # ========================================================
    # RECENT DEFENCE
    # ========================================================

    def _recent_defense(
        self,
        form: Dict[str, Any],
        *,
        fallback: Optional[float],
    ) -> Optional[float]:
        """
        Primary:
            FormModel.xga_recent

        Fallback:
            structural defence.
        """

        recent = self._num(form.get("xga_recent"))

        if recent is not None:
            return recent

        history = self._numeric_history(
            form.get("xga_history")
        )

        if history:
            return self._mean(history)

        return fallback

    # ========================================================
    # GEOMETRIC TEAM STATE
    # ========================================================

    @staticmethod
    def _geometric(
        first: Optional[float],
        second: Optional[float],
    ) -> Optional[float]:
        """
        Geometric combination.

        If both observations exist:

            sqrt(first * second)

        If one is missing, the available observation is used.

        If both are missing, result is None.
        """

        if first is None and second is None:
            return None

        if first is None:
            return second

        if second is None:
            return first

        if first < 0 or second < 0:
            return None

        return sqrt(first * second)

    # ========================================================
    # MATCHUP
    # ========================================================

    @staticmethod
    def _matchup(
        attack: Optional[float],
        opponent_defense: Optional[float],
    ) -> Optional[float]:
        """
        Core FAJ matchup equation:

            lambda = sqrt(attack * opponent_defense)

        Both operands are goals/match.

        Therefore:

            sqrt((goals/match) * (goals/match))
                = goals/match

        No normalization coefficient is required.
        """

        if attack is None or opponent_defense is None:
            return None

        if attack < 0 or opponent_defense < 0:
            return None

        return sqrt(attack * opponent_defense)

    # ========================================================
    # VENUE CONTEXT
    # ========================================================

    def _venue_xg(
        self,
        history: Any,
        *,
        is_home: bool,
    ) -> Optional[float]:
        """
        Extract venue-specific observed xG from historical records.

        This is NOT an artificial home advantage.

        It is simply an observed venue-specific state when the
        supplied history explicitly contains venue information.

        Accepted fields:
            xg
            expected_goals
            external_xg

        Venue:
            is_home
            home

        The method returns None when venue information is absent.
        """

        records = self._records(history)

        if not records:
            return None

        values: List[float] = []

        for record in records:
            item = self._snapshot(record)

            venue_flag = item.get("is_home")

            if venue_flag is None:
                venue_flag = item.get("home")

            if venue_flag is None:
                continue

            if bool(venue_flag) != bool(is_home):
                continue

            xg = self._first_numeric(
                item,
                (
                    "xg",
                    "expected_goals",
                    "external_xg",
                ),
            )

            if xg is not None:
                values.append(xg)

        if not values:
            return None

        return self._mean(values)

    @staticmethod
    def _combine_venue_context(
        base: Optional[float],
        venue_value: Optional[float],
    ) -> Optional[float]:
        """
        Venue context is data, not a coefficient.

        When venue data exists, combine it geometrically with the
        general state.

        When absent, preserve the general state unchanged.
        """

        if base is None:
            return venue_value

        if venue_value is None:
            return base

        if base < 0 or venue_value < 0:
            return base

        return sqrt(base * venue_value)

    # ========================================================
    # HISTORY EXTRACTION
    # ========================================================

    @staticmethod
    def _records(value: Any) -> List[Any]:
        """
        Extract historical records from common containers.
        """

        if value is None:
            return []

        if isinstance(value, Mapping):
            for key in (
                "matches",
                "history",
                "records",
                "recent",
            ):
                candidate = value.get(key)

                if isinstance(candidate, Iterable) and not isinstance(
                    candidate,
                    (str, bytes, Mapping),
                ):
                    return list(candidate)

            return []

        if isinstance(value, Iterable) and not isinstance(
            value,
            (str, bytes),
        ):
            return list(value)

        for key in (
            "matches",
            "history",
            "records",
            "recent",
        ):
            candidate = getattr(value, key, None)

            if isinstance(candidate, Iterable) and not isinstance(
                candidate,
                (str, bytes, Mapping),
            ):
                return list(candidate)

        return []

    # ========================================================
    # NUMERIC HELPERS
    # ========================================================

    @staticmethod
    def _num(value: Any) -> Optional[float]:
        """
        Safe numeric conversion.

        None stays None.
        Empty strings stay missing.
        Invalid values stay missing.

        Importantly:
            0 is NOT treated as missing.
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

            value = value.replace(",", ".")

        try:
            result = float(value)
        except (TypeError, ValueError):
            return None

        if result != result:
            return None

        return result

    @classmethod
    def _first_numeric(
        cls,
        mapping: Mapping[str, Any],
        keys: Iterable[str],
    ) -> Optional[float]:
        for key in keys:
            value = cls._num(mapping.get(key))

            if value is not None:
                return value

        return None

    @classmethod
    def _numeric_history(
        cls,
        value: Any,
    ) -> List[float]:
        if not isinstance(value, Iterable):
            return []

        result: List[float] = []

        for item in value:
            number = cls._num(item)

            if number is not None:
                result.append(number)

        return result

    @staticmethod
    def _mean(values: List[float]) -> Optional[float]:
        if not values:
            return None

        return sum(values) / len(values)

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @classmethod
    def _confidence(
        cls,
        form: Dict[str, Any],
    ) -> Optional[float]:
        """
        Diagnostic data completeness.

        IMPORTANT:
            confidence never changes lambda.
        """

        possible = (
            "xg_avg",
            "xga_avg",
            "xg_recent",
            "xga_recent",
            "shots_avg",
            "shots_against_avg",
            "shots_on_target_avg",
            "shots_on_target_against_avg",
        )

        present = 0

        for key in possible:
            if cls._num(form.get(key)) is not None:
                present += 1

        if not present:
            return None

        return present / len(possible)

    # ========================================================
    # SAFETY
    # ========================================================

    @staticmethod
    def _clip_lambda(
        value: Optional[float],
    ) -> Optional[float]:
        """
        Numerical safety only.

        No artificial floor.

        0 remains 0.
        None remains None.
        """

        if value is None:
            return None

        return max(
            MIN_LAMBDA,
            min(MAX_LAMBDA, value),
        )

    # ========================================================
    # MISC
    # ========================================================

    @staticmethod
    def _sum(
        first: Optional[float],
        second: Optional[float],
    ) -> Optional[float]:
        if first is None or second is None:
            return None

        return first + second

    # ========================================================
    # OPTIONAL ALIASES
    # ========================================================

    def predict(
        self,
        home_form: Any,
        away_form: Any,
        **kwargs: Any,
    ) -> GoalModelResult:
        """
        Compatibility alias.

        GoalModel prediction is still only expected-goal generation.
        """

        return self.analyze(
            home_form,
            away_form,
            **kwargs,
        )

    def calculate(
        self,
        home_form: Any,
        away_form: Any,
        **kwargs: Any,
    ) -> GoalModelResult:
        """
        Compatibility alias for older callers.
        """

        return self.analyze(
            home_form,
            away_form,
            **kwargs,
        )


# ============================================================
# MODULE-LEVEL CONVENIENCE FUNCTION
# ============================================================

def calculate_expected_goals(
    home_form: Any,
    away_form: Any,
    **kwargs: Any,
) -> GoalModelResult:
    """
    Convenience API for callers that prefer a function.
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
    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
    "MODEL_VERSION",
    "MODEL_STATUS",
]
