"""
FAJ Platform — Goal Model v1.0

Purpose
-------
GoalModel converts two FormModelResult objects into expected goals (xG)
for the upcoming match.

Architectural role
------------------
FormContext
    ↓
FormModel
    ↓
GoalModel
    ↓
home_xg / away_xg
    ↓
Poisson / Score Distribution

GoalModel v1.0 does NOT:
- calculate Poisson probabilities;
- calculate exact scores;
- calculate 1X2 probabilities;
- calculate BTTS;
- calculate totals;
- use bookmaker odds;
- use club rating;
- use goals scored/conceded as predictive multipliers;
- use finishing_delta as a multiplier;
- use finishing_ratio as a multiplier;
- use trend as a multiplier;
- use consistency as a multiplier;
- use special effects as xG multipliers;
- apply a hard-coded home advantage multiplier;
- invent values when xG/xGA is missing.

The model is deliberately transparent and research-oriented.

Formula v1.0
------------
Home xG =
    (Home team's historical xG average
     + Away team's historical xGA average) / 2

Away xG =
    (Away team's historical xG average
     + Home team's historical xGA average) / 2

Status
------
RESEARCH_FORMULA

The arithmetic mean is a research baseline, not a claimed optimum.
Alternative synthesis methods can be evaluated later through backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional


GOAL_MODEL_VERSION = "1.0"
FORMULA_STATUS = "RESEARCH_FORMULA"


@dataclass(frozen=True)
class GoalModelResult:
    """
    Immutable result returned by GoalModel.

    The result deliberately exposes the components used to calculate xG.
    This makes the calculation auditable and prevents hidden mathematics
    inside the Brain layer.
    """

    version: str

    home_team: str
    away_team: str
    venue: str

    # Final expected goals
    home_xg: Optional[float]
    away_xg: Optional[float]

    # Base xG values before any future extensions
    home_base_xg: Optional[float]
    away_base_xg: Optional[float]

    # Components used by the formula
    home_attack_component: Optional[float]
    away_attack_component: Optional[float]

    home_defense_component: Optional[float]
    away_defense_component: Optional[float]

    # Reserved for future calibrated venue model
    home_venue_component: Optional[float]
    away_venue_component: Optional[float]

    # Reserved until statistically defined
    home_xg_confidence: Optional[float]
    away_xg_confidence: Optional[float]

    # Reserved until league/team baseline exists
    attack_strength: Optional[float]
    defense_strength: Optional[float]

    formula_status: str
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dictionary representation."""
        return asdict(self)


class GoalModel:
    """
    GoalModel v1.0.

    Input:
        home_form: FormModelResult-like object
        away_form: FormModelResult-like object

    Required values:
        home_form.xg_avg
        home_form.xga_avg
        away_form.xg_avg
        away_form.xga_avg

    The model accepts either:
        - dataclass/object attributes
        - dictionaries

    This makes the model compatible with the current FAJ architecture
    while keeping the mathematical contract explicit.
    """

    VERSION = GOAL_MODEL_VERSION
    FORMULA_STATUS = FORMULA_STATUS

    def __init__(self) -> None:
        """Initialize a stateless GoalModel."""
        pass

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

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
        Calculate expected goals for the upcoming match.

        Parameters
        ----------
        home_form:
            FormModelResult or dictionary containing xg_avg and xga_avg.

        away_form:
            FormModelResult or dictionary containing xg_avg and xga_avg.

        home_team:
            Optional team name.

        away_team:
            Optional team name.

        venue:
            Match venue/context. v1.0 records it but does not use it
            as a numerical multiplier.

        Returns
        -------
        GoalModelResult
            Transparent result containing xG values and diagnostics.
        """

        home_xg_avg = self._get_value(home_form, "xg_avg")
        home_xga_avg = self._get_value(home_form, "xga_avg")

        away_xg_avg = self._get_value(away_form, "xg_avg")
        away_xga_avg = self._get_value(away_form, "xga_avg")

        # --------------------------------------------------------------
        # HOME
        #
        # Home attack:
        #     home team's xG
        #
        # Away defence:
        #     away team's xGA
        #
        # Home xG:
        #     (home_xG + away_xGA) / 2
        # --------------------------------------------------------------

        home_xg = self._calculate_expected_goals(
            attack_xg=home_xg_avg,
            opponent_xga=away_xga_avg,
        )

        # --------------------------------------------------------------
        # AWAY
        #
        # Away attack:
        #     away team's xG
        #
        # Home defence:
        #     home team's xGA
        #
        # Away xG:
        #     (away_xG + home_xGA) / 2
        # --------------------------------------------------------------

        away_xg = self._calculate_expected_goals(
            attack_xg=away_xg_avg,
            opponent_xga=home_xga_avg,
        )

        diagnostics = self._build_diagnostics(
            home_xg_avg=home_xg_avg,
            away_xg_avg=away_xg_avg,
            home_xga_avg=home_xga_avg,
            away_xga_avg=away_xga_avg,
            home_xg=home_xg,
            away_xg=away_xg,
        )

        return GoalModelResult(
            version=self.VERSION,
            home_team=home_team or self._get_value(
                home_form,
                "team_name",
                default="HOME",
            ),
            away_team=away_team or self._get_value(
                away_form,
                "team_name",
                default="AWAY",
            ),
            venue=venue,

            home_xg=home_xg,
            away_xg=away_xg,

            home_base_xg=home_xg,
            away_base_xg=away_xg,

            # Home attacking component
            home_attack_component=home_xg_avg,

            # Away attacking component
            away_attack_component=away_xg_avg,

            # Component of opponent's defence
            # used against each attack
            home_defense_component=away_xga_avg,
            away_defense_component=home_xga_avg,

            # No venue multiplier in v1.0
            home_venue_component=None,
            away_venue_component=None,

            # Confidence is deliberately undefined in v1.0
            home_xg_confidence=None,
            away_xg_confidence=None,

            # Relative strength requires baseline
            attack_strength=None,
            defense_strength=None,

            formula_status=self.FORMULA_STATUS,
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------------
    # FORMULA
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_expected_goals(
        attack_xg: Optional[float],
        opponent_xga: Optional[float],
    ) -> Optional[float]:
        """
        Calculate expected goals using the v1.0 research formula.

        Formula:
            ExpectedGoals = (AttackXG + OpponentXGA) / 2

        Missing-data rule:
            If either component is None, return None.

        Never:
            None → 0
            None → ignored from the formula
            None → replacement estimate
        """

        if attack_xg is None or opponent_xga is None:
            return None

        attack_xg = GoalModel._safe_float(attack_xg)
        opponent_xga = GoalModel._safe_float(opponent_xga)

        if attack_xg is None or opponent_xga is None:
            return None

        return (attack_xg + opponent_xga) / 2.0

    # ------------------------------------------------------------------
    # DATA ACCESS
    # ------------------------------------------------------------------

    @staticmethod
    def _get_value(
        source: Any,
        field: str,
        default: Any = None,
    ) -> Any:
        """
        Read a value from either a dictionary or an object.

        Supported:
            dict["field"]
            object.field
        """

        if source is None:
            return default

        if isinstance(source, dict):
            return source.get(field, default)

        return getattr(source, field, default)

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """
        Convert a numeric value to float.

        Invalid or missing values become None.

        No fallback numeric value is invented.
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            result = float(value)
        except (TypeError, ValueError):
            return None

        return result

    # ------------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------------

    def _build_diagnostics(
        self,
        *,
        home_xg_avg: Optional[float],
        away_xg_avg: Optional[float],
        home_xga_avg: Optional[float],
        away_xga_avg: Optional[float],
        home_xg: Optional[float],
        away_xg: Optional[float],
    ) -> dict[str, Any]:
        """
        Build an explicit audit trail for the calculation.

        Diagnostics contain no additional mathematical adjustment.
        """

        home_components_available = (
            home_xg_avg is not None
            and away_xga_avg is not None
        )

        away_components_available = (
            away_xg_avg is not None
            and home_xga_avg is not None
        )

        return {
            "model": "GoalModel",
            "version": self.VERSION,

            "formula": {
                "home": "(home_xg_avg + away_xga_avg) / 2",
                "away": "(away_xg_avg + home_xga_avg) / 2",
            },

            "formula_status": self.FORMULA_STATUS,

            "home_components_available": home_components_available,
            "away_components_available": away_components_available,

            "home_xg_result": home_xg,
            "away_xg_result": away_xg,

            # Explicit architectural boundaries
            "baseline_available": False,
            "venue_used_as_multiplier": False,
            "finishing_delta_used": False,
            "finishing_ratio_used": False,
            "trend_used_as_multiplier": False,
            "consistency_used_as_multiplier": False,
            "result_strength_used_as_multiplier": False,
            "effect_signals_used_as_multiplier": False,
            "club_rating_used": False,
            "goals_for_used_as_multiplier": False,
            "goals_against_used_as_multiplier": False,
            "bookmaker_odds_used": False,

            # Missing-data policy
            "missing_component_policy": "return_none",

            # Future research
            "alternative_formula_candidates": [
                "arithmetic_mean",
                "geometric_mean",
                "harmonic_mean",
            ],

            # Future extensions
            "future_calibration_required": True,
        }


# ----------------------------------------------------------------------
# CONVENIENCE FUNCTION
# ----------------------------------------------------------------------

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

    Example
    -------
    result = calculate_expected_goals(
        zenit_form,
        cska_form,
        home_team="Zenit",
        away_team="CSKA",
    )

    result.home_xg
    result.away_xg
    """

    model = GoalModel()

    return model.analyze(
        home_form,
        away_form,
        home_team=home_team,
        away_team=away_team,
        venue=venue,
    )


__all__ = [
    "GOAL_MODEL_VERSION",
    "FORMULA_STATUS",
    "GoalModel",
    "GoalModelResult",
    "calculate_expected_goals",
]
