#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
GOAL MODEL v6.0
============================================================

STATUS:
    FINAL CANDIDATE / MATHEMATICAL CORE

PURPOSE:
    Generate independent expected-goal lambdas:

        lambda_home
        lambda_away

CONTRACT:

    FACTS / FormModel
            ↓
    structural state + recent state
            ↓
    effective attack / defensive exposure
            ↓
    venue-aware match state
            ↓
    independent home / away matchup
            ↓
    λH / λA
            ↓
    ProbabilityModel

CORE PRINCIPLE:

    xG  = primary attacking observation
    xGA = primary defensive-exposure observation

    Missing xG/xGA may fall back to goals only when
    the corresponding xG/xGA value is genuinely unavailable.

    Missing != 0.

    Venue data is used only when it is actually available
    from historical match records.

    Home advantage is a bounded fallback only when
    venue-specific information is unavailable.

IMPORTANT:

    GoalModel does NOT:
        - calculate Poisson probabilities
        - calculate 1X2
        - calculate BTTS
        - calculate totals
        - select exact scores
        - redistribute a shared total
        - use strength-gap redistribution
        - use finishing multipliers
        - use confidence to modify λ
        - use FormAnomaly to modify λ
        - use SpecialForm to modify λ
        - use controls to modify λ

    ProbabilityModel owns probability generation.
    ScorePredictor owns score ranking.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from typing import Any, Iterable, Mapping, Optional


# ============================================================
# MODEL CONSTANTS
# ============================================================

MODEL_VERSION = "6.0"
MODEL_STATUS = "FINAL_CANDIDATE"

MIN_LAMBDA = 0.0
MAX_LAMBDA = 4.50

# Used ONLY when venue-specific attack/defence information
# is unavailable for the relevant matchup.
HOME_ADVANTAGE_FALLBACK = 1.10

# Safety floor for relative-state diagnostics.
RELATIVE_DELTA_FLOOR = 0.75


# ============================================================
# RESULT
# ============================================================

@dataclass
class GoalModelResult:
    """
    Public GoalModel result.

    Compatibility fields are intentionally retained because
    downstream Brain / adapters may already expect them.
    """

    home_xg: float
    away_xg: float

    home_base_xg: float
    away_base_xg: float

    home_attack: float
    away_attack: float

    home_defence: float
    away_defence: float

    home_form_effect: float
    away_form_effect: float

    confidence: float

    finishing_delta_home: Optional[float]
    finishing_delta_away: Optional[float]

    diagnostics: dict[str, Any]

    model_version: str = MODEL_VERSION
    model_status: str = MODEL_STATUS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# GOAL MODEL
# ============================================================

class GoalModel:
    """
    FAJ GoalModel v6.0.

    Mathematical chain:

        structural attack
                +
        recent attack
                ↓
        geometric mean
                ↓
        venue-aware attack

        structural xGA
                +
        recent xGA
                ↓
        geometric mean
                ↓
        venue-aware defensive exposure

        λH = sqrt(
            home_attack_match
            * away_defensive_exposure_match
        )

        λA = sqrt(
            away_attack_match
            * home_defensive_exposure_match
        )

    Venue-specific data has priority.

    If venue-specific data is unavailable:

        λH *= HOME_ADVANTAGE_FALLBACK

    λA is not multiplied.

    This is intentionally simple.
    """

    VERSION = MODEL_VERSION
    STATUS = MODEL_STATUS

    MIN_LAMBDA = MIN_LAMBDA
    MAX_LAMBDA = MAX_LAMBDA

    HOME_ADVANTAGE_FALLBACK = HOME_ADVANTAGE_FALLBACK

    # --------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------

    def analyze(
        self,
        home_form: Any,
        away_form: Any,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        venue: Optional[str] = None,
        home_control: Any = None,
        away_control: Any = None,
        home_special: Any = None,
        away_special: Any = None,
        home_history: Any = None,
        away_history: Any = None,
        **kwargs: Any,
    ) -> GoalModelResult:
        """
        Main GoalModel entry point.

        home_form / away_form:
            FormModel result, dict, dataclass, sqlite.Row,
            or compatible object.

        home_history / away_history:
            Historical match records.

        Additional compatibility arguments are accepted but
        intentionally do not modify λ.
        """

        home = self._mapping(home_form)
        away = self._mapping(away_form)

        # ----------------------------------------------------
        # STRUCTURAL STATE
        # ----------------------------------------------------

        home_structural_attack = self._structural_attack(home)
        away_structural_attack = self._structural_attack(away)

        home_structural_defence = self._structural_defence(home)
        away_structural_defence = self._structural_defence(away)

        # ----------------------------------------------------
        # RECENT STATE
        # ----------------------------------------------------

        home_recent_attack = self._recent_attack(
            home,
            structural_value=home_structural_attack,
        )

        away_recent_attack = self._recent_attack(
            away,
            structural_value=away_structural_attack,
        )

        home_recent_defence = self._recent_defence(
            home,
            structural_value=home_structural_defence,
        )

        away_recent_defence = self._recent_defence(
            away,
            structural_value=away_structural_defence,
        )

        # ----------------------------------------------------
        # EFFECTIVE STATE
        # ----------------------------------------------------

        home_attack_eff = self._geometric_state(
            home_structural_attack,
            home_recent_attack,
        )

        away_attack_eff = self._geometric_state(
            away_structural_attack,
            away_recent_attack,
        )

        home_defence_eff = self._geometric_state(
            home_structural_defence,
            home_recent_defence,
        )

        away_defence_eff = self._geometric_state(
            away_structural_defence,
            away_recent_defence,
        )

        # ----------------------------------------------------
        # VENUE STATE
        # ----------------------------------------------------

        home_venue = self._venue_profile(
            history=home_history,
            required_side="home",
        )

        away_venue = self._venue_profile(
            history=away_history,
            required_side="away",
        )

        venue_split_available = (
            home_venue["attack_xg"] is not None
            and home_venue["defence_xga"] is not None
            and away_venue["attack_xg"] is not None
            and away_venue["defence_xga"] is not None
        )

        # ----------------------------------------------------
        # MATCH-SPECIFIC ATTACK
        # ----------------------------------------------------
        #
        # Venue-specific value replaces the generic effective
        # state. It is NOT multiplied into it.
        #
        # This prevents double counting venue.
        # ----------------------------------------------------

        home_attack_match = (
            home_venue["attack_xg"]
            if home_venue["attack_xg"] is not None
            else home_attack_eff
        )

        away_attack_match = (
            away_venue["attack_xg"]
            if away_venue["attack_xg"] is not None
            else away_attack_eff
        )

        # ----------------------------------------------------
        # MATCH-SPECIFIC DEFENSIVE EXPOSURE
        # ----------------------------------------------------

        home_defence_match = (
            home_venue["defence_xga"]
            if home_venue["defence_xga"] is not None
            else home_defence_eff
        )

        away_defence_match = (
            away_venue["defence_xga"]
            if away_venue["defence_xga"] is not None
            else away_defence_eff
        )

        # ----------------------------------------------------
        # INDEPENDENT MATCHUP
        # ----------------------------------------------------

        home_lambda = self._matchup(
            attack=home_attack_match,
            opponent_defence_exposure=away_defence_match,
        )

        away_lambda = self._matchup(
            attack=away_attack_match,
            opponent_defence_exposure=home_defence_match,
        )

        # ----------------------------------------------------
        # HOME ADVANTAGE FALLBACK
        # ----------------------------------------------------

        home_advantage_applied = False

        if not venue_split_available:
            home_lambda *= self.HOME_ADVANTAGE_FALLBACK
            home_advantage_applied = True

        # ----------------------------------------------------
        # SAFETY
        # ----------------------------------------------------

        home_lambda = self._clip_lambda(home_lambda)
        away_lambda = self._clip_lambda(away_lambda)

        # ----------------------------------------------------
        # FORM DIAGNOSTIC
        # ----------------------------------------------------
        #
        # Form is already incorporated into A_eff / D_eff.
        #
        # These fields are retained for compatibility and
        # diagnostics only. They do NOT modify λ again.
        # ----------------------------------------------------

        home_form_effect = self._form_effect_diagnostic(
            structural=home_structural_attack,
            recent=home_recent_attack,
        )

        away_form_effect = self._form_effect_diagnostic(
            structural=away_structural_attack,
            recent=away_recent_attack,
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        confidence = self._confidence(
            home=home,
            away=away,
            home_history=home_history,
            away_history=away_history,
            venue_split_available=venue_split_available,
        )

        # ----------------------------------------------------
        # FINISHING DIAGNOSTIC
        # ----------------------------------------------------

        finishing_delta_home = self._optional_float(
            home.get("finishing_delta")
        )

        finishing_delta_away = self._optional_float(
            away.get("finishing_delta")
        )

        # ----------------------------------------------------
        # RELATIVE STATE DIAGNOSTICS
        # ----------------------------------------------------

        home_attack_delta = self._relative_delta(
            home_structural_attack,
            home_recent_attack,
        )

        away_attack_delta = self._relative_delta(
            away_structural_attack,
            away_recent_attack,
        )

        home_defence_delta = self._relative_delta(
            home_structural_defence,
            home_recent_defence,
        )

        away_defence_delta = self._relative_delta(
            away_structural_defence,
            away_recent_defence,
        )

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics: dict[str, Any] = {
            "model": "FAJ GoalModel",
            "version": MODEL_VERSION,
            "status": MODEL_STATUS,

            "principles": {
                "xg_primary": True,
                "xga_primary": True,
                "goals_fallback_only": True,
                "missing_is_not_zero": True,
                "independent_lambdas": True,
                "shared_total": False,
                "sigmoid": False,
                "strength_gap_redistribution": False,
                "finishing_multiplier": False,
                "confidence_multiplier": False,
                "control_multiplier": False,
                "special_multiplier": False,
                "league_baseline": False,
            },

            "formula": {
                "effective_attack":
                    "sqrt(structural_attack * recent_attack)",
                "effective_defence":
                    "sqrt(structural_xga * recent_xga)",
                "home_lambda":
                    "sqrt(home_attack_match * away_defensive_exposure_match)",
                "away_lambda":
                    "sqrt(away_attack_match * home_defensive_exposure_match)",
            },

            "home": {
                "team": home_team,
                "structural_attack": home_structural_attack,
                "recent_attack": home_recent_attack,
                "effective_attack": home_attack_eff,

                "structural_xga": home_structural_defence,
                "recent_xga": home_recent_defence,
                "effective_xga": home_defence_eff,

                "venue_attack_xg": home_venue["attack_xg"],
                "venue_defence_xga": home_venue["defence_xga"],

                "match_attack": home_attack_match,
                "match_defensive_exposure": home_defence_match,

                "recent_attack_delta": home_attack_delta,
                "recent_xga_delta": home_defence_delta,
            },

            "away": {
                "team": away_team,
                "structural_attack": away_structural_attack,
                "recent_attack": away_recent_attack,
                "effective_attack": away_attack_eff,

                "structural_xga": away_structural_defence,
                "recent_xga": away_recent_defence,
                "effective_xga": away_defence_eff,

                "venue_attack_xg": away_venue["attack_xg"],
                "venue_defence_xga": away_venue["defence_xga"],

                "match_attack": away_attack_match,
                "match_defensive_exposure": away_defence_match,

                "recent_attack_delta": away_attack_delta,
                "recent_xga_delta": away_defence_delta,
            },

            "venue": {
                "venue": venue,
                "venue_split_available": venue_split_available,
                "home_advantage_fallback":
                    self.HOME_ADVANTAGE_FALLBACK,
                "home_advantage_applied": home_advantage_applied,
            },

            "lambda": {
                "home": home_lambda,
                "away": away_lambda,
                "total": home_lambda + away_lambda,
            },

            "compatibility_inputs_ignored_for_lambda": {
                "home_control": home_control is not None,
                "away_control": away_control is not None,
                "home_special": home_special is not None,
                "away_special": away_special is not None,
            },
        }

        return GoalModelResult(
            home_xg=home_lambda,
            away_xg=away_lambda,

            home_base_xg=home_lambda,
            away_base_xg=away_lambda,

            home_attack=home_attack_match,
            away_attack=away_attack_match,

            home_defence=home_defence_match,
            away_defence=away_defence_match,

            home_form_effect=home_form_effect,
            away_form_effect=away_form_effect,

            confidence=confidence,

            finishing_delta_home=finishing_delta_home,
            finishing_delta_away=finishing_delta_away,

            diagnostics=diagnostics,
        )

    # --------------------------------------------------------
    # COMPATIBILITY ALIASES
    # --------------------------------------------------------

    def predict(
        self,
        home_form: Any,
        away_form: Any,
        **kwargs: Any,
    ) -> GoalModelResult:
        return self.analyze(
            home_form=home_form,
            away_form=away_form,
            **kwargs,
        )

    def calculate(
        self,
        home_form: Any,
        away_form: Any,
        **kwargs: Any,
    ) -> GoalModelResult:
        return self.analyze(
            home_form=home_form,
            away_form=away_form,
            **kwargs,
        )

    # --------------------------------------------------------
    # STRUCTURAL ATTACK
    # --------------------------------------------------------

    def _structural_attack(
        self,
        state: Mapping[str, Any],
    ) -> Optional[float]:
        """
        Primary:
            xg_avg

        Fallback:
            goals_for_avg

        Missing != 0.
        """

        xg = self._optional_float(state.get("xg_avg"))

        if xg is not None:
            return self._non_negative(xg)

        goals = self._optional_float(
            state.get("goals_for_avg")
        )

        if goals is not None:
            return self._non_negative(goals)

        return None

    # --------------------------------------------------------
    # STRUCTURAL DEFENSIVE EXPOSURE
    # --------------------------------------------------------

    def _structural_defence(
        self,
        state: Mapping[str, Any],
    ) -> Optional[float]:
        """
        Primary:
            xga_avg

        Fallback:
            goals_against_avg

        Lower xGA = stronger defensive performance.

        xGA itself is stored as defensive exposure, not
        defensive strength.

        Missing != 0.
        """

        xga = self._optional_float(state.get("xga_avg"))

        if xga is not None:
            return self._non_negative(xga)

        goals_against = self._optional_float(
            state.get("goals_against_avg")
        )

        if goals_against is not None:
            return self._non_negative(goals_against)

        return None

    # --------------------------------------------------------
    # RECENT ATTACK
    # --------------------------------------------------------

    def _recent_attack(
        self,
        state: Mapping[str, Any],
        structural_value: Optional[float],
    ) -> Optional[float]:
        """
        Priority:

            xg_recent
            mean(xg_history)
            structural attack
        """

        recent = self._optional_float(
            state.get("xg_recent")
        )

        if recent is not None:
            return self._non_negative(recent)

        history = self._extract_numeric_history(
            state.get("xg_history")
        )

        if history:
            return self._mean(history)

        return structural_value

    # --------------------------------------------------------
    # RECENT DEFENCE
    # --------------------------------------------------------

    def _recent_defence(
        self,
        state: Mapping[str, Any],
        structural_value: Optional[float],
    ) -> Optional[float]:
        """
        Priority:

            xga_recent
            mean(xga_history)
            structural xGA
        """

        recent = self._optional_float(
            state.get("xga_recent")
        )

        if recent is not None:
            return self._non_negative(recent)

        history = self._extract_numeric_history(
            state.get("xga_history")
        )

        if history:
            return self._mean(history)

        return structural_value

    # --------------------------------------------------------
    # GEOMETRIC STATE
    # --------------------------------------------------------

    def _geometric_state(
        self,
        structural: Optional[float],
        recent: Optional[float],
    ) -> Optional[float]:
        """
        Effective state:

            sqrt(structural * recent)

        If one component is unavailable, use the other.

        If both are unavailable, return None.
        """

        if structural is None and recent is None:
            return None

        if structural is None:
            return self._non_negative(recent)

        if recent is None:
            return self._non_negative(structural)

        return sqrt(
            self._non_negative(structural)
            * self._non_negative(recent)
        )

    # --------------------------------------------------------
    # MATCHUP
    # --------------------------------------------------------

    def _matchup(
        self,
        attack: Optional[float],
        opponent_defence_exposure: Optional[float],
    ) -> float:
        """
        Independent matchup:

            sqrt(Attack × Opponent xGA)

        If one component is missing, use the available
        component.

        If both are missing, return zero.

        This is a safety fallback only; upstream data
        completeness should normally prevent this case.
        """

        if attack is None and opponent_defence_exposure is None:
            return 0.0

        if attack is None:
            return self._non_negative(
                opponent_defence_exposure
            )

        if opponent_defence_exposure is None:
            return self._non_negative(attack)

        return sqrt(
            self._non_negative(attack)
            * self._non_negative(
                opponent_defence_exposure
            )
        )

    # --------------------------------------------------------
    # VENUE PROFILE
    # --------------------------------------------------------

    def _venue_profile(
        self,
        history: Any,
        required_side: str,
    ) -> dict[str, Optional[float]]:
        """
        Extract venue-specific:

            attack_xg
            defence_xga

        from historical match records.

        required_side:
            "home" or "away"

        A record qualifies only when its venue can be
        reliably determined.

        Attack uses xG.
        Defence uses xGA.

        One metric is never reused as the other.
        """

        records = self._records(history)

        attack_values: list[float] = []
        defence_values: list[float] = []

        for record in records:
            row = self._mapping(record)

            side = self._record_side(row)

            if side != required_side:
                continue

            xg = self._extract_record_xg(row)
            xga = self._extract_record_xga(row)

            if xg is not None:
                attack_values.append(xg)

            if xga is not None:
                defence_values.append(xga)

        return {
            "attack_xg": (
                self._mean(attack_values)
                if attack_values
                else None
            ),
            "defence_xga": (
                self._mean(defence_values)
                if defence_values
                else None
            ),
        }

    # --------------------------------------------------------
    # RECORD SIDE
    # --------------------------------------------------------

    def _record_side(
        self,
        row: Mapping[str, Any],
    ) -> Optional[str]:
        """
        Robustly determine home/away side.

        Supported examples:

            is_home=True
            is_home=False

            is_home="true"
            is_home="false"

            home=True
            home=False

            side="home"
            side="away"

            venue="home"
            venue="away"

        No blind bool("false") conversion.
        """

        for key in (
            "side",
            "venue_side",
            "team_side",
        ):
            value = row.get(key)

            normalized = self._normalize_side(value)

            if normalized is not None:
                return normalized

        for key in (
            "is_home",
            "home",
        ):
            if key in row:
                value = row.get(key)

                parsed = self._parse_bool(value)

                if parsed is True:
                    return "home"

                if parsed is False:
                    return "away"

        return None

    # --------------------------------------------------------
    # RECORD XG
    # --------------------------------------------------------

    def _extract_record_xg(
        self,
        row: Mapping[str, Any],
    ) -> Optional[float]:
        """
        xG field priority.
        """

        for key in (
            "xg",
            "expected_goals",
            "external_xg",
            "expected_goal",
        ):
            value = self._optional_float(row.get(key))

            if value is not None:
                return self._non_negative(value)

        return None

    # --------------------------------------------------------
    # RECORD XGA
    # --------------------------------------------------------

    def _extract_record_xga(
        self,
        row: Mapping[str, Any],
    ) -> Optional[float]:
        """
        xGA field priority.

        Prefer explicit xGA fields.

        If explicit xGA is absent, derive team xGA from
        opponent xG only when the record contains an explicit
        opponent xG field.

        Never use team's own xG as xGA.
        """

        for key in (
            "xga",
            "xGA",
            "expected_goals_against",
            "expected_goals_conceded",
            "opponent_xg",
            "opp_xg",
            "against_xg",
        ):
            value = self._optional_float(row.get(key))

            if value is not None:
                return self._non_negative(value)

        return None

    # --------------------------------------------------------
    # HISTORY RECORD NORMALIZATION
    # --------------------------------------------------------

    def _records(
        self,
        history: Any,
    ) -> list[Any]:
        """
        Normalize arbitrary history containers.
        """

        if history is None:
            return []

        if isinstance(history, Mapping):
            # A single record.
            if self._looks_like_record(history):
                return [history]

            # Common nested containers.
            for key in (
                "matches",
                "history",
                "records",
                "items",
                "data",
            ):
                value = history.get(key)

                if value is not None:
                    return self._records(value)

            return []

        if isinstance(history, (str, bytes)):
            return []

        try:
            return list(history)
        except TypeError:
            return []

    def _looks_like_record(
        self,
        value: Mapping[str, Any],
    ) -> bool:
        keys = set(value.keys())

        interesting = {
            "xg",
            "xga",
            "external_xg",
            "expected_goals",
            "is_home",
            "home",
            "side",
            "venue",
        }

        return bool(keys.intersection(interesting))

    # --------------------------------------------------------
    # GENERIC MAPPING
    # --------------------------------------------------------

    def _mapping(
        self,
        value: Any,
    ) -> dict[str, Any]:
        """
        Convert common FAJ result objects into a dict-like
        structure.

        Supports:
            dict
            sqlite.Row
            dataclass
            objects with __dict__
            objects with to_dict()
        """

        if value is None:
            return {}

        if isinstance(value, Mapping):
            return dict(value)

        to_dict = getattr(value, "to_dict", None)

        if callable(to_dict):
            try:
                result = to_dict()

                if isinstance(result, Mapping):
                    return dict(result)
            except Exception:
                pass

        # sqlite.Row and similar mapping-like objects.
        keys = getattr(value, "keys", None)

        if callable(keys):
            try:
                return {
                    key: value[key]
                    for key in keys()
                }
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            try:
                return dict(vars(value))
            except Exception:
                pass

        return {}

    # --------------------------------------------------------
    # NUMERIC HISTORY
    # --------------------------------------------------------

    def _extract_numeric_history(
        self,
        history: Any,
    ) -> list[float]:
        """
        Extract scalar values from:

            [1.2, 1.5, 0.8]

        or:

            [{"xg": 1.2}, {"xg": 1.5}]

        or:

            sqlite.Row / dataclass records.

        This helper is intentionally generic and is used
        only for xG/xGA histories.
        """

        if history is None:
            return []

        if isinstance(history, Mapping):
            # Direct scalar record.
            for key in (
                "value",
                "xg",
                "xga",
            ):
                if key in history:
                    value = self._optional_float(
                        history.get(key)
                    )

                    if value is not None:
                        return [self._non_negative(value)]

            return []

        if isinstance(history, (str, bytes)):
            return []

        scalar = self._optional_float(history)

        if scalar is not None:
            return [self._non_negative(scalar)]

        try:
            items = list(history)
        except TypeError:
            return []

        result: list[float] = []

        for item in items:
            if isinstance(item, Mapping):
                row = self._mapping(item)

                value = None

                for key in (
                    "value",
                    "xg",
                    "xga",
                ):
                    if key in row:
                        value = self._optional_float(
                            row.get(key)
                        )

                        if value is not None:
                            break

                if value is not None:
                    result.append(
                        self._non_negative(value)
                    )

                continue

            value = self._optional_float(item)

            if value is not None:
                result.append(
                    self._non_negative(value)
                )

        return result

    # --------------------------------------------------------
    # FORM DIAGNOSTIC
    # --------------------------------------------------------

    def _form_effect_diagnostic(
        self,
        structural: Optional[float],
        recent: Optional[float],
    ) -> float:
        """
        Descriptive form signal only.

        It does NOT modify λ.

        Uses bounded relative change:

            (recent - structural)
            /
            max(|structural|, 0.75)

        This avoids explosive ratios when the baseline
        is very small.
        """

        if structural is None or recent is None:
            return 0.0

        denominator = max(
            abs(structural),
            RELATIVE_DELTA_FLOOR,
        )

        delta = (
            recent - structural
        ) / denominator

        return self._clip(
            delta,
            -1.0,
            1.0,
        )

    def _relative_delta(
        self,
        base: Optional[float],
        recent: Optional[float],
    ) -> Optional[float]:
        if base is None or recent is None:
            return None

        denominator = max(
            abs(base),
            RELATIVE_DELTA_FLOOR,
        )

        return self._clip(
            (recent - base) / denominator,
            -1.0,
            1.0,
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    def _confidence(
        self,
        home: Mapping[str, Any],
        away: Mapping[str, Any],
        home_history: Any,
        away_history: Any,
        venue_split_available: bool,
    ) -> float:
        """
        Descriptive confidence only.

        NEVER modifies λ.

        Confidence is deliberately conservative.

        It reflects data completeness, not team strength.
        """

        scores: list[float] = []

        for state in (home, away):
            score = 0.0
            count = 0.0

            for key in (
                "xg_avg",
                "xga_avg",
                "xg_recent",
                "xga_recent",
            ):
                count += 1.0

                if self._optional_float(
                    state.get(key)
                ) is not None:
                    score += 1.0

            if count > 0:
                scores.append(score / count)

        if not scores:
            confidence = 0.0
        else:
            confidence = self._mean(scores)

        # Venue information is useful evidence but should not
        # become a strength multiplier.
        if venue_split_available:
            confidence += 0.10

        # Historical availability gives a small descriptive
        # confidence contribution.
        if self._records(home_history):
            confidence += 0.05

        if self._records(away_history):
            confidence += 0.05

        return self._clip(
            confidence,
            0.0,
            1.0,
        )

    # --------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------

    @staticmethod
    def _optional_float(
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

        # NaN / infinity protection.
        if number != number:
            return None

        if number == float("inf"):
            return None

        if number == float("-inf"):
            return None

        return number

    @staticmethod
    def _non_negative(
        value: Optional[float],
    ) -> Optional[float]:
        if value is None:
            return None

        return max(
            0.0,
            float(value),
        )

    @staticmethod
    def _mean(
        values: Iterable[float],
    ) -> float:
        items = [
            float(value)
            for value in values
        ]

        if not items:
            return 0.0

        return sum(items) / len(items)

    @staticmethod
    def _clip(
        value: float,
        lower: float,
        upper: float,
    ) -> float:
        return max(
            lower,
            min(
                upper,
                value,
            ),
        )

    def _clip_lambda(
        self,
        value: Optional[float],
    ) -> float:
        if value is None:
            return 0.0

        return self._clip(
            float(value),
            self.MIN_LAMBDA,
            self.MAX_LAMBDA,
        )

    @staticmethod
    def _normalize_side(
        value: Any,
    ) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip().lower()

        if text in {
            "home",
            "h",
            "host",
            "hosts",
            "дом",
            "хозяева",
            "true",
            "1",
        }:
            return "home"

        if text in {
            "away",
            "a",
            "visitor",
            "visitors",
            "гости",
            "false",
            "0",
        }:
            return "away"

        return None

    @staticmethod
    def _parse_bool(
        value: Any,
    ) -> Optional[bool]:
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            if value == 1:
                return True

            if value == 0:
                return False

            return None

        text = str(value).strip().lower()

        if text in {
            "true",
            "1",
            "yes",
            "y",
            "да",
            "home",
        }:
            return True

        if text in {
            "false",
            "0",
            "no",
            "n",
            "нет",
            "away",
        }:
            return False

        return None


# ============================================================
# MODULE CONVENIENCE API
# ============================================================

def calculate_expected_goals(
    home_form: Any,
    away_form: Any,
    **kwargs: Any,
) -> GoalModelResult:
    """
    Convenience wrapper.
    """

    return GoalModel().analyze(
        home_form=home_form,
        away_form=away_form,
        **kwargs,
    )


# ============================================================
# END
# ============================================================
