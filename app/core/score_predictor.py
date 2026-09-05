#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
SCORE PREDICTOR v2.0
============================================================

Purpose
-------
Selects the FAJ predicted exact score from an existing
mathematical score distribution.

Architecture
------------
GoalModel
    ↓
home_xg / away_xg
    ↓
ProbabilityModel
    ↓
Poisson score probabilities
    ↓
ScorePredictor
    ├── Poisson probability
    ├── Outcome Fit
    ├── Margin Fit
    ├── BTTS Fit
    ├── Total Fit
    └── State Advantage
    ↓
FAJ Predicted Score

IMPORTANT
---------
ScorePredictor does NOT:
- calculate Poisson probabilities
- modify xG
- modify ProbabilityModel probabilities
- modify FormWin
- modify Defence
- modify FormControl
- modify FormAnomaly
- modify SpecialForm
- train parameters
- learn from the result
- use bookmaker odds

It only selects the best exact-score scenario.

Key distinction
---------------
likely_score:
    Pure mathematical argmax of Poisson score probability.

predicted_score:
    FAJ exact-score decision selected from the same
    mathematical score space using football state signals.

Missing data
------------
None is never converted into zero as factual data.

For optional model signals, missing values are treated
as neutral and the diagnostics record the missing signal.

Invalid xG / invalid probabilities do not produce an invented
prediction.

Formula
-------
OutcomeFit =
    sqrt(P_outcome × StateFit)

MarginFit =
    exp(-abs(score_margin - target_margin) / MARGIN_SIGMA)

BTTSFit =
    P(BTTS)               if both teams score
    1 - P(BTTS)           otherwise

TotalFit =
    P(Over 2.5)           if total >= 3
    P(Under 2.5)          otherwise

ScenarioFit =
    OutcomeFit^0.40
    × MarginFit^0.25
    × BTTSFit^0.15
    × TotalFit^0.20

ScoreUtility =
    ln(P_score)
    + SCENARIO_WEIGHT × ln(ScenarioFit)

predicted_score =
    argmax(ScoreUtility)

Research parameters are structural priors.
They must be calibrated/backtested over historical data,
not tuned against a single match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


# ============================================================
# VERSION / STATUS
# ============================================================

VERSION = "2.0"
FORMULA_STATUS = "RESEARCH_FORMULA"


# ============================================================
# RESEARCH PARAMETERS
# ============================================================

# Overall influence of scenario compatibility relative
# to pure Poisson probability.
SCENARIO_WEIGHT = 0.75

# Scenario component weights.
OUTCOME_WEIGHT = 0.40
MARGIN_WEIGHT = 0.25
BTTS_WEIGHT = 0.15
TOTAL_WEIGHT = 0.20

# State advantage weights.
STATE_ATTACK_WEIGHT = 0.35
STATE_DEFENCE_WEIGHT = 0.25
STATE_MOMENTUM_WEIGHT = 0.20
STATE_CONTROL_WEIGHT = 0.10
STATE_SPECIAL_WEIGHT = 0.10

# Margin calculation.
STATE_MARGIN_FACTOR = 0.80
MARGIN_SIGMA = 0.90

# Numerical protection.
EPSILON = 1e-12

# Maximum number of alternative scores exposed.
TOP_SCORES_COUNT = 10


# ============================================================
# TYPES
# ============================================================

Score = Tuple[int, int]


# ============================================================
# HELPERS
# ============================================================

def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:
    return max(low, min(high, value))


def _clamp_signal(value: float) -> float:
    return _clamp(value, -1.0, 1.0)


def _safe_float(value: Any) -> Optional[float]:
    """
    Convert a value to finite float.

    None remains None.
    Invalid/non-finite values become None.
    """
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _get_value(
    obj: Any,
    *names: str,
) -> Optional[float]:
    """
    Read a numeric attribute from either a dataclass/object
    or a dictionary.
    """
    if obj is None:
        return None

    for name in names:
        if isinstance(obj, Mapping):
            value = obj.get(name)
        else:
            value = getattr(obj, name, None)

        value = _safe_float(value)

        if value is not None:
            return value

    return None


def _get_raw_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Read a raw attribute from object/dict.
    """
    if obj is None:
        return None

    for name in names:
        if isinstance(obj, Mapping):
            if name in obj:
                return obj[name]
        else:
            if hasattr(obj, name):
                return getattr(obj, name)

    return None


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _log_safe(value: float) -> float:
    return math.log(max(value, EPSILON))


def _geometric_mean(
    components: Iterable[Tuple[float, float]],
) -> float:
    """
    Weighted geometric mean.

    components:
        iterable of (value, weight)
    """
    total_weight = 0.0
    weighted_log = 0.0

    for value, weight in components:
        value = _clamp(value)
        weight = max(float(weight), 0.0)

        weighted_log += weight * _log_safe(value)
        total_weight += weight

    if total_weight <= 0.0:
        return 0.0

    return _clamp(
        math.exp(weighted_log / total_weight)
    )


# ============================================================
# RESULT
# ============================================================

@dataclass
class ScorePrediction:
    """
    Result of FAJ ScorePredictor.
    """

    # --------------------------------------------------------
    # Mathematical score
    # --------------------------------------------------------

    likely_score: Optional[Score]
    likely_score_string: Optional[str]

    # --------------------------------------------------------
    # FAJ selected score
    # --------------------------------------------------------

    predicted_score: Optional[Score]
    predicted_score_string: Optional[str]

    # --------------------------------------------------------
    # Alternatives
    # --------------------------------------------------------

    second_score: Optional[Score]
    second_score_string: Optional[str]

    third_score: Optional[Score]
    third_score_string: Optional[str]

    # --------------------------------------------------------
    # Decision values
    # --------------------------------------------------------

    primary_score_value: Optional[float]
    second_score_value: Optional[float]
    third_score_value: Optional[float]

    # --------------------------------------------------------
    # Components of primary prediction
    # --------------------------------------------------------

    probability_score: Optional[float]
    outcome_fit_score: Optional[float]
    margin_fit_score: Optional[float]
    btts_fit_score: Optional[float]
    total_fit_score: Optional[float]
    scenario_fit_score: Optional[float]
    state_advantage: Optional[float]

    # --------------------------------------------------------
    # Ranked candidate scores
    # --------------------------------------------------------

    top_scores: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    formula_status: str = FORMULA_STATUS

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# SCORE PREDICTOR
# ============================================================

class ScorePredictor:
    """
    FAJ exact-score decision organ.

    It does not generate probabilities.

    It selects an exact-score scenario from the existing
    ProbabilityModel distribution.
    """

    VERSION = VERSION

    # ========================================================
    # PUBLIC API
    # ========================================================

    def predict(
        self,
        score_probabilities: Any,
        home_xg: Optional[float],
        away_xg: Optional[float],
        probability_result: Any = None,
        home_form_win: Any = None,
        away_form_win: Any = None,
        home_defence: Any = None,
        away_defence: Any = None,
        control_advantage: Optional[str] = None,
        control_strength: Optional[float] = None,
        anomaly_signal: Optional[float] = None,
        special_composite: Optional[float] = None,
    ) -> ScorePrediction:
        """
        Select FAJ exact predicted score.

        Parameters
        ----------
        score_probabilities:
            Existing score distribution from ProbabilityModel.

            Supported formats:

            1. Dict:
                {(0, 0): 0.10, (1, 0): 0.15, ...}

            2. List of dictionaries:
                [
                    {
                        "score": (2, 0),
                        "probability": 0.15,
                    },
                    ...
                ]

            3. List using score_string:
                [
                    {
                        "score_string": "2:0",
                        "probability": 0.15,
                    },
                    ...
                ]

        home_xg / away_xg:
            Expected goals already produced by GoalModel.

        probability_result:
            Optional ProbabilityResult from ProbabilityModel.

            If supplied, the predictor uses:
                home_win
                draw
                away_win
                btts
                over_25
                under_25

            If absent, these values are derived from the supplied
            score distribution.

        home_form_win / away_form_win:
            FormWin results.

        home_defence / away_defence:
            Defence results.

        control_advantage:
            "HOME", "AWAY" or "EQUAL".

        control_strength:
            0..1.

        anomaly_signal:
            Directional home-vs-away anomaly signal, -1..1.

        special_composite:
            Directional home-vs-away special-form signal,
            -0.30..0.30.

        Returns
        -------
        ScorePrediction
        """

        # ----------------------------------------------------
        # 1. Validate xG
        # ----------------------------------------------------

        home_xg_value = _safe_float(home_xg)
        away_xg_value = _safe_float(away_xg)

        if (
            home_xg_value is None
            or away_xg_value is None
            or home_xg_value < 0.0
            or away_xg_value < 0.0
        ):
            return self._unavailable_prediction(
                reason="INVALID_OR_MISSING_XG"
            )

        # ----------------------------------------------------
        # 2. Normalize score distribution
        # ----------------------------------------------------

        candidates = self._normalize_score_probabilities(
            score_probabilities
        )

        if not candidates:
            return self._unavailable_prediction(
                reason="NO_SCORE_PROBABILITIES"
            )

        # ----------------------------------------------------
        # 3. Mathematical likely score
        # ----------------------------------------------------

        likely = max(
            candidates,
            key=lambda item: item["probability"],
        )

        likely_score = likely["score"]
        likely_probability = likely["probability"]

        # ----------------------------------------------------
        # 4. Extract / derive probability summaries
        # ----------------------------------------------------

        summary = self._extract_probability_summary(
            probability_result=probability_result,
            candidates=candidates,
        )

        # ----------------------------------------------------
        # 5. Extract state signals
        # ----------------------------------------------------

        state = self._calculate_state_advantage(
            home_form_win=home_form_win,
            away_form_win=away_form_win,
            home_defence=home_defence,
            away_defence=away_defence,
            control_advantage=control_advantage,
            control_strength=control_strength,
            anomaly_signal=anomaly_signal,
            special_composite=special_composite,
        )

        state_advantage = state["state_advantage"]

        # ----------------------------------------------------
        # 6. Evaluate every candidate
        # ----------------------------------------------------

        evaluated: List[Dict[str, Any]] = []

        for candidate in candidates:
            score = candidate["score"]
            probability = candidate["probability"]

            home_goals, away_goals = score

            outcome_fit = self._calculate_outcome_fit(
                home_goals=home_goals,
                away_goals=away_goals,
                home_win_probability=summary["home_win"],
                draw_probability=summary["draw"],
                away_win_probability=summary["away_win"],
                state_advantage=state_advantage,
            )

            margin_fit = self._calculate_margin_fit(
                home_goals=home_goals,
                away_goals=away_goals,
                home_xg=home_xg_value,
                away_xg=away_xg_value,
                state_advantage=state_advantage,
            )

            btts_fit = self._calculate_btts_fit(
                home_goals=home_goals,
                away_goals=away_goals,
                btts_probability=summary["btts"],
            )

            total_fit = self._calculate_total_fit(
                home_goals=home_goals,
                away_goals=away_goals,
                over_25_probability=summary["over_25"],
                under_25_probability=summary["under_25"],
            )

            scenario_fit = _geometric_mean(
                [
                    (outcome_fit, OUTCOME_WEIGHT),
                    (margin_fit, MARGIN_WEIGHT),
                    (btts_fit, BTTS_WEIGHT),
                    (total_fit, TOTAL_WEIGHT),
                ]
            )

            score_utility = (
                _log_safe(probability)
                + SCENARIO_WEIGHT
                * _log_safe(scenario_fit)
            )

            evaluated.append(
                {
                    "score": score,
                    "score_string": (
                        f"{home_goals}:{away_goals}"
                    ),
                    "probability": probability,
                    "outcome_fit": outcome_fit,
                    "margin_fit": margin_fit,
                    "btts_fit": btts_fit,
                    "total_fit": total_fit,
                    "scenario_fit": scenario_fit,
                    "score_utility": score_utility,
                }
            )

        # ----------------------------------------------------
        # 7. Rank by FAJ utility
        # ----------------------------------------------------

        evaluated.sort(
            key=lambda item: item["score_utility"],
            reverse=True,
        )

        primary = evaluated[0]

        second = (
            evaluated[1]
            if len(evaluated) > 1
            else None
        )

        third = (
            evaluated[2]
            if len(evaluated) > 2
            else None
        )

        # ----------------------------------------------------
        # 8. Build result
        # ----------------------------------------------------

        return ScorePrediction(
            likely_score=likely_score,
            likely_score_string=(
                f"{likely_score[0]}:{likely_score[1]}"
            ),
            predicted_score=primary["score"],
            predicted_score_string=primary["score_string"],
            second_score=(
                second["score"]
                if second is not None
                else None
            ),
            second_score_string=(
                second["score_string"]
                if second is not None
                else None
            ),
            third_score=(
                third["score"]
                if third is not None
                else None
            ),
            third_score_string=(
                third["score_string"]
                if third is not None
                else None
            ),
            primary_score_value=primary["score_utility"],
            second_score_value=(
                second["score_utility"]
                if second is not None
                else None
            ),
            third_score_value=(
                third["score_utility"]
                if third is not None
                else None
            ),
            probability_score=primary["probability"],
            outcome_fit_score=primary["outcome_fit"],
            margin_fit_score=primary["margin_fit"],
            btts_fit_score=primary["btts_fit"],
            total_fit_score=primary["total_fit"],
            scenario_fit_score=primary["scenario_fit"],
            state_advantage=state_advantage,
            top_scores=evaluated[
                :TOP_SCORES_COUNT
            ],
            formula_status=FORMULA_STATUS,
            diagnostics={
                "version": self.VERSION,
                "formula_status": FORMULA_STATUS,
                "home_xg": home_xg_value,
                "away_xg": away_xg_value,
                "candidate_count": len(candidates),
                "likely_score": (
                    f"{likely_score[0]}:{likely_score[1]}"
                ),
                "likely_probability": likely_probability,
                "predicted_score": primary[
                    "score_string"
                ],
                "probability_summary": summary,
                "state": state,
                "weights": {
                    "scenario": SCENARIO_WEIGHT,
                    "outcome": OUTCOME_WEIGHT,
                    "margin": MARGIN_WEIGHT,
                    "btts": BTTS_WEIGHT,
                    "total": TOTAL_WEIGHT,
                    "state_attack": (
                        STATE_ATTACK_WEIGHT
                    ),
                    "state_defence": (
                        STATE_DEFENCE_WEIGHT
                    ),
                    "state_momentum": (
                        STATE_MOMENTUM_WEIGHT
                    ),
                    "state_control": (
                        STATE_CONTROL_WEIGHT
                    ),
                    "state_special": (
                        STATE_SPECIAL_WEIGHT
                    ),
                },
            },
        )

    # ========================================================
    # SCORE INPUT NORMALIZATION
    # ========================================================

    def _normalize_score_probabilities(
        self,
        score_probabilities: Any,
    ) -> List[Dict[str, Any]]:
        """
        Normalize supported ProbabilityModel score formats.
        """

        result: List[Dict[str, Any]] = []

        if score_probabilities is None:
            return result

        # ----------------------------------------------------
        # Dict format
        # ----------------------------------------------------

        if isinstance(
            score_probabilities,
            Mapping,
        ):
            for raw_score, raw_probability in (
                score_probabilities.items()
            ):
                score = self._parse_score(
                    raw_score
                )

                probability = _safe_float(
                    raw_probability
                )

                if (
                    score is None
                    or probability is None
                    or probability <= 0.0
                ):
                    continue

                if probability > 1.0:
                    continue

                result.append(
                    {
                        "score": score,
                        "probability": probability,
                    }
                )

            return result

        # ----------------------------------------------------
        # List / iterable format
        # ----------------------------------------------------

        try:
            iterable = list(score_probabilities)
        except TypeError:
            return result

        for item in iterable:
            if not isinstance(item, Mapping):
                continue

            raw_score = item.get("score")

            if raw_score is None:
                raw_score = item.get(
                    "score_string"
                )

            probability = item.get(
                "probability"
            )

            if probability is None:
                probability = item.get(
                    "prob"
                )

            score = self._parse_score(
                raw_score
            )

            probability = _safe_float(
                probability
            )

            if (
                score is None
                or probability is None
                or probability <= 0.0
                or probability > 1.0
            ):
                continue

            result.append(
                {
                    "score": score,
                    "probability": probability,
                }
            )

        return result

    def _parse_score(
        self,
        raw_score: Any,
    ) -> Optional[Score]:
        """
        Parse:
            (2, 0)
            [2, 0]
            "2:0"
        """

        if isinstance(
            raw_score,
            (tuple, list),
        ):
            if len(raw_score) != 2:
                return None

            try:
                home = int(raw_score[0])
                away = int(raw_score[1])
            except (
                TypeError,
                ValueError,
            ):
                return None

        elif isinstance(
            raw_score,
            str,
        ):
            parts = raw_score.strip().split(":")

            if len(parts) != 2:
                return None

            try:
                home = int(parts[0])
                away = int(parts[1])
            except (
                TypeError,
                ValueError,
            ):
                return None

        else:
            return None

        if home < 0 or away < 0:
            return None

        return home, away

    # ========================================================
    # PROBABILITY SUMMARY
    # ========================================================

    def _extract_probability_summary(
        self,
        probability_result: Any,
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Optional[float]]:
        """
        Read summary probabilities from ProbabilityModel.

        If ProbabilityResult is unavailable, derive them from
        the supplied score distribution.

        Derived values may be incomplete if only TOP-N scores
        were supplied. Diagnostics record this.
        """

        home_win = _get_value(
            probability_result,
            "home_win",
        )

        draw = _get_value(
            probability_result,
            "draw",
        )

        away_win = _get_value(
            probability_result,
            "away_win",
        )

        btts = _get_value(
            probability_result,
            "btts",
        )

        over_25 = _get_value(
            probability_result,
            "over_25",
        )

        under_25 = _get_value(
            probability_result,
            "under_25",
        )

        source = "ProbabilityModel"

        if (
            home_win is None
            or draw is None
            or away_win is None
            or btts is None
            or over_25 is None
            or under_25 is None
        ):
            (
                derived_home,
                derived_draw,
                derived_away,
                derived_btts,
                derived_over,
                derived_under,
            ) = self._derive_probability_summary(
                candidates
            )

            if home_win is None:
                home_win = derived_home

            if draw is None:
                draw = derived_draw

            if away_win is None:
                away_win = derived_away

            if btts is None:
                btts = derived_btts

            if over_25 is None:
                over_25 = derived_over

            if under_25 is None:
                under_25 = derived_under

            source = "DERIVED_FROM_SCORE_DISTRIBUTION"

        return {
            "home_win": (
                _clamp(home_win)
                if home_win is not None
                else None
            ),
            "draw": (
                _clamp(draw)
                if draw is not None
                else None
            ),
            "away_win": (
                _clamp(away_win)
                if away_win is not None
                else None
            ),
            "btts": (
                _clamp(btts)
                if btts is not None
                else None
            ),
            "over_25": (
                _clamp(over_25)
                if over_25 is not None
                else None
            ),
            "under_25": (
                _clamp(under_25)
                if under_25 is not None
                else None
            ),
            "source": source,
        }

    def _derive_probability_summary(
        self,
        candidates: List[Dict[str, Any]],
    ) -> Tuple[
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
    ]:
        """
        Derive summary probabilities from the supplied score
        distribution.

        This is exact only when the supplied distribution
        contains the complete score matrix.
        """

        if not candidates:
            return (
                None,
                None,
                None,
                None,
                None,
                None,
            )

        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        btts = 0.0
        over_25 = 0.0
        under_25 = 0.0

        total_mass = 0.0

        for item in candidates:
            home, away = item["score"]
            probability = item["probability"]

            total_mass += probability

            if home > away:
                home_win += probability
            elif home == away:
                draw += probability
            else:
                away_win += probability

            if home > 0 and away > 0:
                btts += probability

            if home + away >= 3:
                over_25 += probability
            else:
                under_25 += probability

        if total_mass <= EPSILON:
            return (
                None,
                None,
                None,
                None,
                None,
                None,
            )

        # Normalize because a TOP-N score list may not sum to 1.
        home_win /= total_mass
        draw /= total_mass
        away_win /= total_mass
        btts /= total_mass
        over_25 /= total_mass
        under_25 /= total_mass

        return (
            home_win,
            draw,
            away_win,
            btts,
            over_25,
            under_25,
        )

    # ========================================================
    # STATE ADVANTAGE
    # ========================================================

    def _calculate_state_advantage(
        self,
        home_form_win: Any,
        away_form_win: Any,
        home_defence: Any,
        away_defence: Any,
        control_advantage: Optional[str],
        control_strength: Optional[float],
        anomaly_signal: Optional[float],
        special_composite: Optional[float],
    ) -> Dict[str, Any]:
        """
        Build directional home-vs-away state advantage.

        Positive:
            home state advantage.

        Negative:
            away state advantage.

        Missing signals are neutral for calculation but are
        recorded in diagnostics.
        """

        # ----------------------------------------------------
        # Attack
        # ----------------------------------------------------

        home_attack = _get_value(
            home_form_win,
            "attack_signal",
            "attack",
        )

        away_attack = _get_value(
            away_form_win,
            "attack_signal",
            "attack",
        )

        attack_available = (
            home_attack is not None
            and away_attack is not None
        )

        if home_attack is None:
            home_attack = 0.0

        if away_attack is None:
            away_attack = 0.0

        attack_advantage = _clamp_signal(
            home_attack - away_attack
        )

        # ----------------------------------------------------
        # Defence
        # ----------------------------------------------------

        home_defence_signal = _get_value(
            home_defence,
            "process_signal",
            "defence_signal",
            "defence",
        )

        away_defence_signal = _get_value(
            away_defence,
            "process_signal",
            "defence_signal",
            "defence",
        )

        defence_available = (
            home_defence_signal is not None
            and away_defence_signal is not None
        )

        if home_defence_signal is None:
            home_defence_signal = 0.0

        if away_defence_signal is None:
            away_defence_signal = 0.0

        defence_advantage = _clamp_signal(
            home_defence_signal
            - away_defence_signal
        )

        # ----------------------------------------------------
        # Momentum / anomaly
        # ----------------------------------------------------

        anomaly_available = (
            anomaly_signal is not None
        )

        anomaly = _safe_float(
            anomaly_signal
        )

        if anomaly is None:
            anomaly = 0.0

        anomaly = _clamp_signal(anomaly)

        # ----------------------------------------------------
        # Control
        # ----------------------------------------------------

        control_available = (
            control_advantage is not None
            and control_strength is not None
        )

        strength = _safe_float(
            control_strength
        )

        if strength is None:
            strength = 0.0

        strength = _clamp(strength)

        control_name = (
            str(control_advantage).upper().strip()
            if control_advantage is not None
            else "EQUAL"
        )

        if control_name == "HOME":
            control_advantage_value = strength
        elif control_name == "AWAY":
            control_advantage_value = -strength
        else:
            control_advantage_value = 0.0

        control_advantage_value = _clamp_signal(
            control_advantage_value
        )

        # ----------------------------------------------------
        # Special form
        # ----------------------------------------------------

        special_available = (
            special_composite is not None
        )

        special = _safe_float(
            special_composite
        )

        if special is None:
            special = 0.0

        special = _clamp_signal(special)

        # ----------------------------------------------------
        # Aggregate
        # ----------------------------------------------------

        state_advantage = (
            STATE_ATTACK_WEIGHT
            * attack_advantage
            + STATE_DEFENCE_WEIGHT
            * defence_advantage
            + STATE_MOMENTUM_WEIGHT
            * anomaly
            + STATE_CONTROL_WEIGHT
            * control_advantage_value
            + STATE_SPECIAL_WEIGHT
            * special
        )

        state_advantage = _clamp_signal(
            state_advantage
        )

        return {
            "state_advantage": state_advantage,
            "attack_advantage": attack_advantage,
            "defence_advantage": defence_advantage,
            "momentum_advantage": anomaly,
            "control_advantage": (
                control_advantage_value
            ),
            "special_advantage": special,
            "availability": {
                "attack": attack_available,
                "defence": defence_available,
                "momentum": anomaly_available,
                "control": control_available,
                "special": special_available,
            },
        }

    # ========================================================
    # OUTCOME FIT
    # ========================================================

    def _calculate_outcome_fit(
        self,
        home_goals: int,
        away_goals: int,
        home_win_probability: Optional[float],
        draw_probability: Optional[float],
        away_win_probability: Optional[float],
        state_advantage: float,
    ) -> float:
        """
        Compatibility between candidate outcome,
        ProbabilityModel outcome probability and team state.
        """

        if home_goals > away_goals:
            probability = (
                home_win_probability
                if home_win_probability is not None
                else 0.5
            )

            state_fit = (
                0.5
                + 0.5
                * math.tanh(
                    2.0 * state_advantage
                )
            )

        elif home_goals < away_goals:
            probability = (
                away_win_probability
                if away_win_probability is not None
                else 0.5
            )

            state_fit = (
                0.5
                - 0.5
                * math.tanh(
                    2.0 * state_advantage
                )
            )

        else:
            probability = (
                draw_probability
                if draw_probability is not None
                else 0.5
            )

            state_fit = (
                1.0
                - abs(state_advantage)
            )

        probability = _clamp(
            probability
        )

        state_fit = _clamp(
            state_fit
        )

        return _clamp(
            math.sqrt(
                max(
                    probability,
                    EPSILON,
                )
                * max(
                    state_fit,
                    EPSILON,
                )
            )
        )

    # ========================================================
    # MARGIN FIT
    # ========================================================

    def _calculate_margin_fit(
        self,
        home_goals: int,
        away_goals: int,
        home_xg: float,
        away_xg: float,
        state_advantage: float,
    ) -> float:
        """
        Measure whether the candidate goal difference matches
        the expected strength difference.

        Base expected margin:
            abs(home_xg - away_xg)

        State can strengthen the expected margin:

            target_margin =
                xG_difference
                + STATE_MARGIN_FACTOR × abs(state_advantage)

        Direction is taken from xG first and state second.
        """

        xg_difference = (
            home_xg - away_xg
        )

        xg_direction = _sign(
            xg_difference
        )

        state_direction = _sign(
            state_advantage
        )

        if xg_direction != 0:
            expected_direction = xg_direction
        else:
            expected_direction = state_direction

        expected_margin = abs(
            xg_difference
        )

        if expected_direction != 0:
            expected_margin += (
                STATE_MARGIN_FACTOR
                * abs(state_advantage)
            )

        candidate_difference = (
            home_goals - away_goals
        )

        candidate_direction = _sign(
            candidate_difference
        )

        # A score on the wrong side of the expected
        # advantage receives a strong but continuous penalty.
        direction_penalty = 1.0

        if (
            expected_direction != 0
            and candidate_direction != 0
            and candidate_direction
            != expected_direction
        ):
            direction_penalty = 0.35

        if (
            expected_direction != 0
            and candidate_direction == 0
        ):
            direction_penalty = 0.70

        candidate_margin = abs(
            candidate_difference
        )

        margin_distance = abs(
            candidate_margin
            - expected_margin
        )

        fit = math.exp(
            -margin_distance
            / MARGIN_SIGMA
        )

        return _clamp(
            fit * direction_penalty
        )

    # ========================================================
    # BTTS FIT
    # ========================================================

    def _calculate_btts_fit(
        self,
        home_goals: int,
        away_goals: int,
        btts_probability: Optional[float],
    ) -> float:
        """
        Candidate compatibility with BTTS probability.
        """

        if btts_probability is None:
            return 0.5

        btts_probability = _clamp(
            btts_probability
        )

        candidate_btts = (
            home_goals > 0
            and away_goals > 0
        )

        if candidate_btts:
            return max(
                btts_probability,
                EPSILON,
            )

        return max(
            1.0 - btts_probability,
            EPSILON,
        )

    # ========================================================
    # TOTAL FIT
    # ========================================================

    def _calculate_total_fit(
        self,
        home_goals: int,
        away_goals: int,
        over_25_probability: Optional[float],
        under_25_probability: Optional[float],
    ) -> float:
        """
        Candidate compatibility with O/U 2.5.
        """

        if (
            over_25_probability is None
            and under_25_probability is None
        ):
            return 0.5

        total = (
            home_goals
            + away_goals
        )

        if total >= 3:
            if over_25_probability is None:
                return 0.5

            return max(
                _clamp(
                    over_25_probability
                ),
                EPSILON,
            )

        if under_25_probability is None:
            return 0.5

        return max(
            _clamp(
                under_25_probability
            ),
            EPSILON,
        )

    # ========================================================
    # UNAVAILABLE RESULT
    # ========================================================

    def _unavailable_prediction(
        self,
        reason: str,
    ) -> ScorePrediction:
        """
        Return a transparent no-prediction result.

        No invented score is produced.
        """

        return ScorePrediction(
            likely_score=None,
            likely_score_string=None,
            predicted_score=None,
            predicted_score_string=None,
            second_score=None,
            second_score_string=None,
            third_score=None,
            third_score_string=None,
            primary_score_value=None,
            second_score_value=None,
            third_score_value=None,
            probability_score=None,
            outcome_fit_score=None,
            margin_fit_score=None,
            btts_fit_score=None,
            total_fit_score=None,
            scenario_fit_score=None,
            state_advantage=None,
            top_scores=[],
            formula_status=FORMULA_STATUS,
            diagnostics={
                "version": self.VERSION,
                "formula_status": FORMULA_STATUS,
                "available": False,
                "reason": reason,
            },
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def predict_score(
    score_probabilities: Any,
    home_xg: Optional[float],
    away_xg: Optional[float],
    probability_result: Any = None,
    home_form_win: Any = None,
    away_form_win: Any = None,
    home_defence: Any = None,
    away_defence: Any = None,
    control_advantage: Optional[str] = None,
    control_strength: Optional[float] = None,
    anomaly_signal: Optional[float] = None,
    special_composite: Optional[float] = None,
) -> ScorePrediction:
    """
    Convenience wrapper for ScorePredictor.predict().
    """

    predictor = ScorePredictor()

    return predictor.predict(
        score_probabilities=score_probabilities,
        home_xg=home_xg,
        away_xg=away_xg,
        probability_result=probability_result,
        home_form_win=home_form_win,
        away_form_win=away_form_win,
        home_defence=home_defence,
        away_defence=away_defence,
        control_advantage=control_advantage,
        control_strength=control_strength,
        anomaly_signal=anomaly_signal,
        special_composite=special_composite,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "VERSION",
    "FORMULA_STATUS",
    "ScorePrediction",
    "ScorePredictor",
    "predict_score",
]
