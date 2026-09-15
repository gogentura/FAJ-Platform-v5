#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN — FINAL ORCHESTRATOR
============================================================

ROLE
----
FAJBrain is an orchestration layer.

It does NOT contain an independent mathematical prediction model.

Canonical prediction chain:

    6 historical matches
            ↓
    FormContext
            ↓
    FormModel
            ↓
    GoalModel v6.0
            ↓
        λ Home/Away
            ↓
    ProbabilityModel v1.1
            ↓
    score_distribution
            ↓
    ScorePredictor v2.2
            ↓
    FINAL PREDICTION


DIAGNOSTIC ORGANS
-----------------
These organs are calculated for analytical diagnostics only:

    FormWin
    Defence
    FormControl
    FormAnomaly
    FormSpecial

They MUST NOT modify:

    GoalModel λ
    ProbabilityModel probabilities
    ScorePredictor ranking


HARD RULES
----------
- exactly 6 historical matches per team
- history order is M1 -> M6
- M1 = oldest
- M6 = newest
- Brain never reverses history
- Missing != 0
- Prediction != Fact
- no bookmaker odds
- no future data
- no Winner Synthesis
- no second Poisson implementation
- no second xG model
- no score recalculation inside Brain
- no probability recalculation inside Brain
- database.py is never touched


MATHEMATICAL OWNERSHIP
----------------------
FormModel:
    interprets historical form.

GoalModel v6.0:
    owns λH / λA.

ProbabilityModel v1.1:
    owns Poisson / 1X2 / BTTS / totals /
    joint score distribution.

ScorePredictor v2.2:
    owns exact-score ranking.

Brain:
    connects them.

UI ADAPTER
----------
The public output preserves the contract expected by
faj_predictor.py / streamlit_app.py:

    - 1X2 probabilities
    - xG (λ from GoalModel)
    - BTTS / over25 / over35
    - top scores
    - most/second/third likely score
    - analysis_mode
    - home_matches / away_matches
    - data_quality
    - conclusion
    - factors
    - calculation_meta with goal_model diagnostics
    - calculation_meta["score_forecast"]["top_scores"]

Corners and Cards are not computed here yet.
They remain None until CornersModel / CardsModel are
plugged in as parallel side-channels.
============================================================
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# CORE IMPORTS
# ============================================================

from .form_context import build_form_context
from .form_model import FormModel
from .goal_model import GoalModel
from .probability_model import ProbabilityModel
from .score_predictor import ScorePredictor


# ============================================================
# DIAGNOSTIC ORGANS
# ============================================================

try:
    from .form_win import FormWin
except ImportError:
    FormWin = None


try:
    from .defence import Defence
except ImportError:
    Defence = None


try:
    from .form_control import FormControl
except ImportError:
    FormControl = None


try:
    from .form_anomaly import FormAnomaly
except ImportError:
    FormAnomaly = None


try:
    from .special_form import FormSpecial
except ImportError:
    FormSpecial = None


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-FINAL-2.0"

CONTRACT_VERSION = "3.3"

HISTORY_SIZE = 6


# ============================================================
# GENERIC HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    """
    Safe numeric conversion.

    None stays None.
    Invalid values stay None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not (-float("inf") < number < float("inf")):
        return None

    return number


def _safe_int(value: Any) -> Optional[int]:
    """
    Safe integer conversion.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _get_value(
    obj: Any,
    *names: str,
) -> Any:
    """
    Unified access for:

        dict
        sqlite3.Row
        dataclass
        regular object
    """

    if obj is None:
        return None

    for name in names:

        if isinstance(obj, dict):

            if name in obj:
                return obj[name]

        try:
            keys = obj.keys()

            if name in keys:
                return obj[name]

        except (AttributeError, TypeError):
            pass

        try:
            return getattr(obj, name)

        except AttributeError:
            pass

    return None


def _to_dict(
    value: Any,
) -> Dict[str, Any]:
    """
    Convert a model result to a dictionary.

    Supports:
        dict
        dataclass
        objects with to_dict()
        regular objects
    """

    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    to_dict = getattr(value, "to_dict", None)

    if callable(to_dict):

        try:
            result = to_dict()

            if isinstance(result, dict):
                return dict(result)

        except Exception:
            pass

    if is_dataclass(value):

        try:
            return asdict(value)

        except Exception:
            pass

    try:
        return dict(vars(value))

    except Exception:
        return {}


def _first(
    data: Dict[str, Any],
    *names: str,
    default: Any = None,
) -> Any:
    """
    Return first existing key.

    Important:
        existing None is returned as None.
        None is not converted to default.
    """

    for name in names:

        if name in data:
            return data[name]

    return default


# ============================================================
# HISTORY NORMALIZATION
# ============================================================

def _normalize_history(
    matches: Iterable[Any],
    team_name: Optional[str] = None,
) -> List[Any]:
    """
    Normalize history without changing chronological order.

    Contract:

        M1 -> M2 -> M3 -> M4 -> M5 -> M6

    M1:
        oldest

    M6:
        newest

    Brain does NOT sort and does NOT reverse.

    The upstream Predictor is responsible for providing
    canonical chronological history.

    team_name:
        Optional. Retained for call-site compatibility.
        Does NOT affect ordering or content.
    """

    history = list(matches)

    if len(history) != HISTORY_SIZE:

        raise ValueError(
            "FAJBrain requires exactly "
            f"{HISTORY_SIZE} historical matches; "
            f"received {len(history)}."
        )

    return history


# ============================================================
# MATCH -> BRAIN RECORD
# ============================================================

def _build_brain_record(
    record: Any,
) -> Dict[str, Any]:
    """
    Normalize an external historical record into the common
    factual structure expected by FormContext / Brain.

    Missing values remain None.
    """

    home_team = _get_value(
        record,
        "home_team",
        "home_name",
        "home",
    )

    away_team = _get_value(
        record,
        "away_team",
        "away_name",
        "away",
    )

    match_date = _get_value(
        record,
        "match_date",
        "date",
        "match_date_str",
    )

    home_goals = _safe_int(
        _get_value(
            record,
            "home_goals",
        )
    )

    away_goals = _safe_int(
        _get_value(
            record,
            "away_goals",
        )
    )

    score = _get_value(
        record,
        "score",
    )

    if (
        home_goals is None
        or away_goals is None
    ):

        if score:

            text = str(score)

            parts = text.replace(
                "-",
                ":",
            ).split(":")

            if len(parts) >= 2:

                home_goals = _safe_int(
                    parts[0].strip()
                )

                away_goals = _safe_int(
                    parts[1].strip()
                )

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    xg = _get_value(
        record,
        "xg",
    )

    home_xg = None
    away_xg = None

    if isinstance(xg, dict):

        home_xg = _safe_float(
            xg.get("home")
        )

        away_xg = _safe_float(
            xg.get("away")
        )

    else:

        home_xg = _safe_float(
            _get_value(
                record,
                "home_xg",
            )
        )

        away_xg = _safe_float(
            _get_value(
                record,
                "away_xg",
            )
        )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    def field(
        name: str,
        home_name: Optional[str] = None,
        away_name: Optional[str] = None,
    ) -> Tuple[Any, Any]:

        home_key = (
            home_name
            or f"home_{name}"
        )

        away_key = (
            away_name
            or f"away_{name}"
        )

        return (
            _get_value(
                record,
                home_key,
            ),
            _get_value(
                record,
                away_key,
            ),
        )

    home_shots, away_shots = field(
        "shots"
    )

    home_sot, away_sot = field(
        "shots_on_target"
    )

    home_possession, away_possession = field(
        "possession"
    )

    home_corners, away_corners = field(
        "corners"
    )

    home_cards, away_cards = field(
        "yellow_cards"
    )

    if home_cards is None:
        home_cards = _get_value(
            record,
            "home_cards",
        )

    if away_cards is None:
        away_cards = _get_value(
            record,
            "away_cards",
        )

    home_fouls, away_fouls = field(
        "fouls"
    )

    home_big_chances, away_big_chances = field(
        "big_chances"
    )

    home_passes, away_passes = field(
        "passes"
    )

    home_pass_accuracy, away_pass_accuracy = field(
        "pass_accuracy"
    )

    return {
        "home_team": home_team,
        "away_team": away_team,
        "match_date": match_date,
        "home_goals": home_goals,
        "away_goals": away_goals,
        "xg": {
            "home": home_xg,
            "away": away_xg,
        },
        "home_shots": _safe_int(home_shots),
        "away_shots": _safe_int(away_shots),
        "home_shots_on_target": _safe_int(home_sot),
        "away_shots_on_target": _safe_int(away_sot),
        "home_possession": _safe_float(home_possession),
        "away_possession": _safe_float(away_possession),
        "home_corners": _safe_int(home_corners),
        "away_corners": _safe_int(away_corners),
        "home_yellow_cards": _safe_int(home_cards),
        "away_yellow_cards": _safe_int(away_cards),
        "home_fouls": _safe_int(home_fouls),
        "away_fouls": _safe_int(away_fouls),
        "home_big_chances": _safe_int(home_big_chances),
        "away_big_chances": _safe_int(away_big_chances),
        "home_passes": _safe_int(home_passes),
        "away_passes": _safe_int(away_passes),
        "home_pass_accuracy": _safe_float(
            home_pass_accuracy
        ),
        "away_pass_accuracy": _safe_float(
            away_pass_accuracy
        ),
    }


# ============================================================
# FORM CONTEXT
# ============================================================

def _build_form(
    team: str,
    history: Sequence[Any],
) -> Dict[str, Any]:
    """
    Build canonical FormContext dictionary.

    The history is already M1 -> M6.
    """

    records = [
        _build_brain_record(record)
        for record in history
    ]

    context = build_form_context(
        team_name=team,
        records=records,
        limit=HISTORY_SIZE,
    )

    if not isinstance(context, dict):

        context = _to_dict(context)

    return context


# ============================================================
# FAJ BRAIN — FINAL ORCHESTRATOR
# ============================================================

class FAJBrain:

    """
    FAJ Brain — Final Orchestrator.

    Brain is not a mathematical model.

    It:

        1. normalizes 6+6 historical matches;
        2. builds canonical FormContext;
        3. runs FormModel;
        4. runs diagnostic organs (side-channel);
        5. runs the canonical mathematical chain:
               GoalModel → ProbabilityModel → ScorePredictor
        6. adapts the result to the Predictor / UI contract.

    Brain never:

        - recalculates λ
        - recalculates Poisson
        - recalculates probabilities
        - recalculates score ranking
        - modifies FormContext ordering
    """

    VERSION = BRAIN_VERSION

    def __init__(self) -> None:

        self.version = BRAIN_VERSION

    # ========================================================
    # FORM MODEL
    # ========================================================

    def _run_form_model(
        self,
        form_context: Any,
        next_venue: str,
    ) -> Any:

        """
        FormModel v1.2.

        Input:
            FormContext
            next_venue ("home" or "away")

        Output:
            FormModelResult
        """

        if form_context is None:
            return None

        model = FormModel()

        return model.analyze(
            form_context=form_context,
            next_venue=next_venue,
        )

    # ========================================================
    # DIAGNOSTIC ORGANS
    # ========================================================

    def _run_diagnostics(
        self,
        home_form_context: Any,
        away_form_context: Any,
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:

        """
        Side-channel diagnostics.

        Each organ is executed independently and wrapped in
        its own try/except.

        Failure of one organ never breaks the mathematical
        chain.

        The organs have different signatures and are called
        explicitly.
        """

        diagnostics: Dict[str, Any] = {
            "home": {},
            "away": {},
            "contract": {
                "prediction_impact": "none",
                "lambda_influence": False,
                "probability_influence": False,
                "score_ranking_influence": False,
            },
        }

        # ----------------------------------------------------
        # Defence
        # ----------------------------------------------------

        if Defence is not None:

            try:
                diagnostics["home"]["defence"] = (
                    Defence().calculate(
                        context=home_form_context,
                        team_name=home_team,
                    )
                )
            except Exception:
                diagnostics["home"]["defence"] = None

            try:
                diagnostics["away"]["defence"] = (
                    Defence().calculate(
                        context=away_form_context,
                        team_name=away_team,
                    )
                )
            except Exception:
                diagnostics["away"]["defence"] = None

        # ----------------------------------------------------
        # FormWin
        # ----------------------------------------------------

        if FormWin is not None:

            try:
                diagnostics["home"]["form_win"] = (
                    FormWin().analyze(
                        form_context=home_form_context,
                        next_venue="home",
                    )
                )
            except Exception:
                diagnostics["home"]["form_win"] = None

            try:
                diagnostics["away"]["form_win"] = (
                    FormWin().analyze(
                        form_context=away_form_context,
                        next_venue="away",
                    )
                )
            except Exception:
                diagnostics["away"]["form_win"] = None

        # ----------------------------------------------------
        # FormControl
        # ----------------------------------------------------

        if FormControl is not None:

            try:
                diagnostics["home"]["control"] = (
                    FormControl().analyze(
                        context=home_form_context,
                        target_team=home_team,
                        opponent_team=away_team,
                        venue="home",
                    )
                )
            except Exception:
                diagnostics["home"]["control"] = None

            try:
                diagnostics["away"]["control"] = (
                    FormControl().analyze(
                        context=away_form_context,
                        target_team=away_team,
                        opponent_team=home_team,
                        venue="away",
                    )
                )
            except Exception:
                diagnostics["away"]["control"] = None

        # ----------------------------------------------------
        # FormAnomaly
        # ----------------------------------------------------

        if FormAnomaly is not None:

            try:
                diagnostics["home"]["anomaly"] = (
                    FormAnomaly().analyze(
                        context=home_form_context,
                    )
                )
            except Exception:
                diagnostics["home"]["anomaly"] = None

            try:
                diagnostics["away"]["anomaly"] = (
                    FormAnomaly().analyze(
                        context=away_form_context,
                    )
                )
            except Exception:
                diagnostics["away"]["anomaly"] = None

        # ----------------------------------------------------
        # FormSpecial
        # ----------------------------------------------------

        if FormSpecial is not None:

            try:
                diagnostics["home"]["special_form"] = (
                    FormSpecial().analyze(
                        context=home_form_context,
                        team_name=home_team,
                    )
                )
            except Exception:
                diagnostics["home"]["special_form"] = None

            try:
                diagnostics["away"]["special_form"] = (
                    FormSpecial().analyze(
                        context=away_form_context,
                        team_name=away_team,
                    )
                )
            except Exception:
                diagnostics["away"]["special_form"] = None

        return diagnostics

    # ========================================================
    # GOAL MODEL
    # ========================================================

    def _run_goal_model(
        self,
        home_form_model: Any,
        away_form_model: Any,
        home_team: str,
        away_team: str,
        home_history: Any,
        away_history: Any,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Any:

        """
        GoalModel v6.0.

        Sole responsibility:

            history / form state
                ↓
            λH / λA

        It does NOT calculate:

            - Poisson
            - 1X2
            - BTTS
            - totals
            - exact score
            - score ranking
        """

        model = GoalModel()

        home_control = None
        away_control = None
        home_special = None
        away_special = None

        if diagnostics:
            home_control = diagnostics["home"].get("control")
            away_control = diagnostics["away"].get("control")
            home_special = diagnostics["home"].get("special_form")
            away_special = diagnostics["away"].get("special_form")

        result = model.analyze(
            home_form=home_form_model,
            away_form=away_form_model,
            home_team=home_team,
            away_team=away_team,
            venue="HOME",
            home_control=home_control,
            away_control=away_control,
            home_special=home_special,
            away_special=away_special,
            home_history=home_history,
            away_history=away_history,
        )

        if result is None:
            raise RuntimeError(
                "GoalModel returned None"
            )

        return result

    def _extract_goal_data(
        self,
        goal_result: Any,
    ) -> Dict[str, Any]:

        """
        Normalize GoalModelResult into the Brain contract.

        Brain does NOT recalculate xG.
        Brain only extracts GoalModel output.
        """

        data = _to_dict(goal_result)

        home_xg = _first(
            data,
            "home_xg",
            "lambda_home",
            "home_lambda",
        )

        away_xg = _first(
            data,
            "away_xg",
            "lambda_away",
            "away_lambda",
        )

        if home_xg is None:
            raise ValueError(
                "GoalModel did not return home_xg"
            )

        if away_xg is None:
            raise ValueError(
                "GoalModel did not return away_xg"
            )

        home_xg = _safe_float(home_xg)
        away_xg = _safe_float(away_xg)

        if home_xg is None:
            raise ValueError(
                "GoalModel home_xg is not numeric"
            )

        if away_xg is None:
            raise ValueError(
                "GoalModel away_xg is not numeric"
            )

        return {
            "home_xg": home_xg,
            "away_xg": away_xg,
            "home_base_xg": _first(
                data,
                "home_base_xg",
            ),
            "away_base_xg": _first(
                data,
                "away_base_xg",
            ),
            "home_attack": _first(
                data,
                "home_attack",
            ),
            "away_attack": _first(
                data,
                "away_attack",
            ),
            "home_defence": _first(
                data,
                "home_defence",
            ),
            "away_defence": _first(
                data,
                "away_defence",
            ),
            "home_form_effect": _first(
                data,
                "home_form_effect",
            ),
            "away_form_effect": _first(
                data,
                "away_form_effect",
            ),
            "confidence": _first(
                data,
                "confidence",
            ),
            "finishing_delta_home": _first(
                data,
                "finishing_delta_home",
                "home_finishing_delta",
            ),
            "finishing_delta_away": _first(
                data,
                "finishing_delta_away",
                "away_finishing_delta",
            ),
            "diagnostics": _first(
                data,
                "diagnostics",
            ),
            "model_version": _first(
                data,
                "model_version",
                "version",
            ),
            "model_status": _first(
                data,
                "model_status",
                "status",
            ),
        }

    def _validate_lambda(
        self,
        home_xg: Optional[float],
        away_xg: Optional[float],
    ) -> None:

        """
        Brain-level integrity check.

        This is NOT a new mathematical formula.

        Only GoalModel result is validated:

            0.0 <= λ <= 4.50
        """

        if home_xg is None or away_xg is None:
            raise ValueError(
                "Lambda cannot be None"
            )

        if home_xg < 0.0 or home_xg > 4.50:
            raise ValueError(
                f"Invalid home lambda: {home_xg}"
            )

        if away_xg < 0.0 or away_xg > 4.50:
            raise ValueError(
                f"Invalid away lambda: {away_xg}"
            )

    # ========================================================
    # PROBABILITY MODEL
    # ========================================================

    def _run_probability_model(
        self,
        home_xg: float,
        away_xg: float,
    ) -> Any:

        """
        ProbabilityModel v1.1.

        Input:
            λH
            λA

        Output:
            joint score matrix
            1X2
            BTTS
            totals
            score_distribution
            top_scores

        Brain does NOT recalculate Poisson.
        Brain does NOT modify λ.
        """

        if home_xg is None or away_xg is None:
            raise ValueError(
                "ProbabilityModel requires both home_xg and away_xg"
            )

        model = ProbabilityModel()

        result = model.calculate(
            home_xg=home_xg,
            away_xg=away_xg,
        )

        if result is None:
            raise RuntimeError(
                "ProbabilityModel returned None"
            )

        return result

    def _extract_probability_data(
        self,
        probability_result: Any,
    ) -> Dict[str, Any]:

        """
        Extract ProbabilityModel v1.1 result.

        No new mathematical calculations.
        """

        data = _to_dict(probability_result)

        score_distribution = _first(
            data,
            "score_distribution",
            "score_probabilities",
            "distribution",
        )

        if score_distribution is None:
            raise ValueError(
                "ProbabilityModel did not return score_distribution"
            )

        return {
            "home_win": _first(
                data,
                "home_win",
                "home_win_probability",
                "prob_home_win",
            ),
            "draw": _first(
                data,
                "draw",
                "draw_probability",
                "prob_draw",
            ),
            "away_win": _first(
                data,
                "away_win",
                "away_win_probability",
                "prob_away_win",
            ),
            "btts": _first(
                data,
                "btts",
                "btts_probability",
            ),
            "over15": _first(
                data,
                "over15",
                "over_15",
                "over15_probability",
                "over_15_probability",
            ),
            "over25": _first(
                data,
                "over25",
                "over_25",
                "over25_probability",
                "over_25_probability",
            ),
            "over35": _first(
                data,
                "over35",
                "over_35",
                "over35_probability",
                "over_35_probability",
            ),
            "under25": _first(
                data,
                "under25",
                "under_25",
                "under25_probability",
                "under_25_probability",
            ),
            "under35": _first(
                data,
                "under35",
                "under_35",
                "under35_probability",
                "under_35_probability",
            ),
            "score_distribution": score_distribution,
            "total_goals_distribution": _first(
                data,
                "total_goals_distribution",
                "totals_distribution",
            ),
            "top_scores": _first(
                data,
                "top_scores",
            ),
            "model_version": _first(
                data,
                "model_version",
                "version",
            ),
            "calibration_status": _first(
                data,
                "calibration_status",
            ),
            "diagnostics": _first(
                data,
                "diagnostics",
            ),
        }

    # ========================================================
    # SCORE PREDICTOR
    # ========================================================

    def _run_score_predictor(
        self,
        score_distribution: Any,
        home_xg: float,
        away_xg: float,
        probability_result: Any,
    ) -> Any:

        """
        ScorePredictor v2.2.

        Critical:

            ProbabilityModel
                    ↓
            score_distribution
                    ↓
            ScorePredictor
                    ↓
            ranking scores

        ScorePredictor does not create a second probability.
        """

        if score_distribution is None:
            raise ValueError(
                "ScorePredictor requires score_distribution"
            )

        model = ScorePredictor()

        result = model.predict(
            score_probabilities=score_distribution,
            home_xg=home_xg,
            away_xg=away_xg,
            probability_result=probability_result,
        )

        if result is None:
            raise RuntimeError(
                "ScorePredictor returned None"
            )

        return result

    def _extract_score_data(
        self,
        score_result: Any,
        probability_data: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Normalize ScorePredictor v2.2.

        ScorePredictor is the source of:

            - predicted_score
            - likely_score
            - second_score
            - third_score
            - top_scores
            - primary_score_value
            - second_score_value
            - third_score_value
        """

        data = _to_dict(score_result)

        predicted_score = _first(
            data,
            "predicted_score",
            "likely_score",
        )

        likely_score = _first(
            data,
            "likely_score",
            "predicted_score",
        )

        second_score = _first(
            data,
            "second_score",
        )

        third_score = _first(
            data,
            "third_score",
        )

        top_scores = _first(
            data,
            "top_scores",
            "top_10_scores",
            "ranked_scores",
        )

        top_3_scores = _first(
            data,
            "top_3_scores",
            "top3_scores",
        )

        if top_3_scores is None and top_scores is not None:

            try:
                top_3_scores = list(top_scores)[:3]

            except (TypeError, ValueError):
                top_3_scores = None

        score_distribution = _first(
            data,
            "score_distribution",
            "score_probabilities",
        )

        if score_distribution is None:
            score_distribution = probability_data.get(
                "score_distribution"
            )

        return {
            "predicted_score": predicted_score,
            "likely_score": likely_score,
            "second_score": second_score,
            "third_score": third_score,
            "top_scores": top_scores,
            "top_3_scores": top_3_scores,
            "primary_score_value": _first(
                data,
                "primary_score_value",
            ),
            "second_score_value": _first(
                data,
                "second_score_value",
            ),
            "third_score_value": _first(
                data,
                "third_score_value",
            ),
            "probability_score": _first(
                data,
                "probability_score",
            ),
            "score_distribution": score_distribution,
            "model_version": _first(
                data,
                "model_version",
                "version",
            ),
            "formula_status": _first(
                data,
                "formula_status",
                "status",
            ),
            "diagnostics": _first(
                data,
                "diagnostics",
            ),
        }

    # ========================================================
    # CORE PREDICTION
    # ========================================================

    def _run_core_prediction(
        self,
        home_form_model: Any,
        away_form_model: Any,
        home_team: str,
        away_team: str,
        home_history: Any,
        away_history: Any,
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Authoritative mathematical chain:

            FormModel
                ↓
            GoalModel v6.0
                ↓
                λH / λA
                ↓
            ProbabilityModel v1.1
                ↓
            score_distribution
                ↓
            ScorePredictor v2.2
        """

        # ====================================================
        # 1. GoalModel
        # ====================================================

        goal_result = self._run_goal_model(
            home_form_model=home_form_model,
            away_form_model=away_form_model,
            home_team=home_team,
            away_team=away_team,
            home_history=home_history,
            away_history=away_history,
            diagnostics=diagnostics,
        )

        goal_data = self._extract_goal_data(
            goal_result
        )

        self._validate_lambda(
            goal_data["home_xg"],
            goal_data["away_xg"],
        )

        # ====================================================
        # 2. ProbabilityModel
        # ====================================================

        probability_result = self._run_probability_model(
            home_xg=goal_data["home_xg"],
            away_xg=goal_data["away_xg"],
        )

        probability_data = self._extract_probability_data(
            probability_result
        )

        # ====================================================
        # 3. ScorePredictor
        # ====================================================

        score_result = self._run_score_predictor(
            score_distribution=(
                probability_data["score_distribution"]
            ),
            home_xg=goal_data["home_xg"],
            away_xg=goal_data["away_xg"],
            probability_result=probability_result,
        )

        score_data = self._extract_score_data(
            score_result=score_result,
            probability_data=probability_data,
        )

        # ====================================================
        # 4. Audit snapshot
        # ====================================================

        stage = {
            "goal_model": {
                "version": goal_data.get(
                    "model_version"
                ),
                "status": goal_data.get(
                    "model_status"
                ),
                "lambda_home": goal_data.get(
                    "home_xg"
                ),
                "lambda_away": goal_data.get(
                    "away_xg"
                ),
            },
            "probability_model": {
                "version": probability_data.get(
                    "model_version"
                ),
                "calibration_status": probability_data.get(
                    "calibration_status"
                ),
                "home_win": probability_data.get(
                    "home_win"
                ),
                "draw": probability_data.get(
                    "draw"
                ),
                "away_win": probability_data.get(
                    "away_win"
                ),
                "btts": probability_data.get(
                    "btts"
                ),
                "over25": probability_data.get(
                    "over25"
                ),
                "over35": probability_data.get(
                    "over35"
                ),
            },
            "score_predictor": {
                "version": score_data.get(
                    "model_version"
                ),
                "formula_status": score_data.get(
                    "formula_status"
                ),
                "predicted_score": score_data.get(
                    "predicted_score"
                ),
                "likely_score": score_data.get(
                    "likely_score"
                ),
                "second_score": score_data.get(
                    "second_score"
                ),
                "third_score": score_data.get(
                    "third_score"
                ),
                "top_scores": score_data.get(
                    "top_scores"
                ),
            },
            "contract": {
                "goal_model_to_probability": True,
                "probability_to_score_predictor": True,
                "second_poisson_model": False,
                "lambda_recalculation": False,
                "probability_recalculation": False,
                "score_recalculation": False,
            },
        }

        return {
            "goal_result": goal_result,
            "goal_data": goal_data,
            "probability_result": probability_result,
            "probability_data": probability_data,
            "score_result": score_result,
            "score_data": score_data,
            "stage": stage,
        }

    # ========================================================
    # UI ADAPTER: PROBABILITY NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_probability(value: Any) -> Optional[float]:
        """
        Bring a probability to the 0..1 range.

        This is output formatting only.
        It does not modify any mathematical model.
        """

        if value is None:
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if value > 1.0:
            value /= 100.0

        return max(0.0, min(1.0, value))

    # ========================================================
    # UI ADAPTER: ANALYSIS MODE
    # ========================================================

    @staticmethod
    def _build_analysis_mode(
        home_matches: int,
        away_matches: int,
    ) -> str:
        """
        Descriptive label based on the number of matches.
        """

        minimum = min(
            home_matches,
            away_matches,
        )

        if minimum >= 6:
            return "Расширенный"

        if minimum >= 3:
            return "Базовый+"

        if minimum >= 2:
            return "Базовый"

        return "Экспресс"

    # ========================================================
    # UI ADAPTER: DATA QUALITY
    # ========================================================

    @staticmethod
    def _build_data_quality(
        home_form_context: Any,
        away_form_context: Any,
    ) -> Optional[float]:
        """
        Rough factual completeness measure.

        Not a model confidence.
        """

        values: List[float] = []

        for context in (
            home_form_context,
            away_form_context,
        ):

            if not isinstance(context, dict):
                continue

            matches = context.get(
                "matches",
                [],
            )

            if not matches:
                continue

            fields = (
                "goals_for",
                "goals_against",
                "xg",
                "xga",
            )

            available = 0
            total = 0

            for match in matches:

                for name in fields:

                    total += 1

                    if _get_value(
                        match,
                        name,
                    ) is not None:
                        available += 1

            if total > 0:
                values.append(
                    available / total
                )

        if not values:
            return None

        return round(
            100.0
            * (
                sum(values)
                / len(values)
            ),
            1,
        )

    # ========================================================
    # UI ADAPTER: CONCLUSION
    # ========================================================

    @staticmethod
    def _build_conclusion(
        home_team: str,
        away_team: str,
        home_win: Optional[float],
        draw: Optional[float],
        away_win: Optional[float],
        btts: Optional[float],
        over25: Optional[float],
    ) -> Tuple[str, List[str]]:
        """
        Descriptive conclusion based on 1X2 / BTTS / totals.

        No additional mathematics.
        """

        factors: List[str] = []

        probabilities = {
            home_team: home_win,
            "DRAW": draw,
            away_team: away_win,
        }

        available = {
            key: value
            for key, value in probabilities.items()
            if value is not None
        }

        if available:

            favorite = max(
                available,
                key=available.get,
            )

            if favorite == "DRAW":
                factors.append(
                    "Модель не видит явного фаворита."
                )
                winner_text = "равновесие сил"
            else:
                factors.append(
                    f"Модель видит преимущество {favorite}."
                )
                winner_text = f"преимущество {favorite}"

        else:

            winner_text = "недостаточно данных"
            factors.append(
                "Модель не смогла определить фаворита."
            )

        if btts is not None:
            if btts >= 0.60:
                factors.append(
                    "Вероятность обмена голами повышена."
                )
            elif btts <= 0.40:
                factors.append(
                    "Модель не ожидает высокой вероятности обмена голами."
                )

        if over25 is not None:
            if over25 >= 0.60:
                factors.append(
                    "Сценарий с 3+ голами выглядит вероятным."
                )
            elif over25 <= 0.40:
                factors.append(
                    "Модель скорее склоняется к умеренной результативности."
                )

        conclusion = (
            f"FAJ: {winner_text}. "
            + " ".join(factors)
        )

        return conclusion, factors

    # ========================================================
    # FINAL OUTPUT ADAPTER
    # ========================================================

    def _build_final_output(
        self,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
        home_form_context: Any,
        away_form_context: Any,
        home_form_model: Any,
        away_form_model: Any,
        diagnostics: Dict[str, Any],
        core: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Final public Brain output.

        Preserves the UI contract expected by
        faj_predictor.py 1.2.
        """

        goal_data = core["goal_data"]
        probability_data = core["probability_data"]
        score_data = core["score_data"]

        # ----------------------------------------------------
        # Probabilities (0..1 for UI)
        # ----------------------------------------------------

        home_win = self._normalize_probability(
            probability_data.get("home_win")
        )

        draw = self._normalize_probability(
            probability_data.get("draw")
        )

        away_win = self._normalize_probability(
            probability_data.get("away_win")
        )

        btts_probability = self._normalize_probability(
            probability_data.get("btts")
        )

        over15_probability = self._normalize_probability(
            probability_data.get("over15")
        )

        over25_probability = self._normalize_probability(
            probability_data.get("over25")
        )

        over35_probability = self._normalize_probability(
            probability_data.get("over35")
        )

        # ----------------------------------------------------
        # Confidence (descriptive only, does not affect λ)
        # ----------------------------------------------------

        confidence = self._normalize_probability(
            goal_data.get("confidence")
        )

        # ----------------------------------------------------
        # Risk (descriptive only)
        # ----------------------------------------------------

        risk: Optional[str] = None

        if confidence is not None:

            if confidence >= 0.75:
                risk = "LOW"
            elif confidence >= 0.60:
                risk = "MEDIUM"
            else:
                risk = "HIGH"

        # ----------------------------------------------------
        # Top scores (top-3 in UI format)
        # ----------------------------------------------------

        top_scores = score_data.get(
            "top_scores"
        ) or []

        top_3_scores = score_data.get(
            "top_3_scores"
        ) or []

        likely_score = score_data.get(
            "likely_score"
        )

        second_score = score_data.get(
            "second_score"
        )

        third_score = score_data.get(
            "third_score"
        )

        # ----------------------------------------------------
        # Descriptive mode / quality / conclusion / factors
        # ----------------------------------------------------

        home_matches = len(home_history)
        away_matches = len(away_history)

        analysis_mode = self._build_analysis_mode(
            home_matches=home_matches,
            away_matches=away_matches,
        )

        data_quality = self._build_data_quality(
            home_form_context,
            away_form_context,
        )

        conclusion, factors = self._build_conclusion(
            home_team=home_team,
            away_team=away_team,
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            btts=btts_probability,
            over25=over25_probability,
        )

        # ----------------------------------------------------
        # score_forecast (for UI)
        # ----------------------------------------------------

        score_forecast = {
            "predicted_score": score_data.get(
                "predicted_score"
            ),
            "likely_score": likely_score,
            "second_score": second_score,
            "third_score": third_score,
            "top_scores": top_scores,
            "top_3_scores": top_3_scores,
            "primary_score_value": score_data.get(
                "primary_score_value"
            ),
            "second_score_value": score_data.get(
                "second_score_value"
            ),
            "third_score_value": score_data.get(
                "third_score_value"
            ),
        }

        # ----------------------------------------------------
        # calculation_meta
        # ----------------------------------------------------

        calculation_meta = {
            "brain_version": BRAIN_VERSION,
            "contract_version": CONTRACT_VERSION,
            "goal_model_version": goal_data.get(
                "model_version"
            ),
            "probability_model_version": (
                probability_data.get(
                    "model_version"
                )
            ),
            "score_predictor_version": (
                score_data.get(
                    "model_version"
                )
            ),
            "probability_calibration": (
                probability_data.get(
                    "calibration_status"
                )
            ),
            "formula_status": (
                score_data.get(
                    "formula_status"
                )
            ),
            "diagnostics_prediction_impact": "none",
            "goal_model": _to_dict(
                core.get("goal_result")
            ),
            "probability_model": _to_dict(
                core.get("probability_result")
            ),
            "score_predictor": _to_dict(
                core.get("score_result")
            ),
            "score_forecast": score_forecast,
            "home_form_model": _to_dict(
                home_form_model
            ),
            "away_form_model": _to_dict(
                away_form_model
            ),
            "home_matches": home_matches,
            "away_matches": away_matches,
        }

        # ----------------------------------------------------
        # Public output
        # ----------------------------------------------------

        return {

            # =================================================
            # TEAMS
            # =================================================

            "home_team": home_team,
            "away_team": away_team,

            # =================================================
            # MATCH COUNTS (for UI)
            # =================================================

            "home_matches": home_matches,
            "away_matches": away_matches,

            # =================================================
            # ANALYSIS MODE / DATA QUALITY
            # =================================================

            "analysis_mode": analysis_mode,
            "data_quality": data_quality,

            # =================================================
            # 1X2
            # =================================================

            "home_win_probability": home_win,
            "draw_probability": draw,
            "away_win_probability": away_win,

            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,

            # =================================================
            # BTTS / TOTALS
            # =================================================

            "btts": (
                btts_probability >= 0.5
                if btts_probability is not None
                else None
            ),
            "btts_probability": btts_probability,

            "over25": (
                over25_probability >= 0.5
                if over25_probability is not None
                else None
            ),
            "over25_probability": over25_probability,

            "over35": (
                over35_probability >= 0.5
                if over35_probability is not None
                else None
            ),
            "over35_probability": over35_probability,

            "over15_probability": over15_probability,

            # =================================================
            # xG (λ from GoalModel)
            # =================================================

            "home_xg": goal_data["home_xg"],
            "away_xg": goal_data["away_xg"],

            "home_xg_internal": goal_data["home_xg"],
            "away_xg_internal": goal_data["away_xg"],

            # =================================================
            # SCORE (UI + Brain)
            # =================================================

            "predicted_score": score_data.get(
                "predicted_score"
            ),
            "likely_score": likely_score,
            "second_score": second_score,
            "third_score": third_score,

            "top_scores": top_scores,
            "top_3_scores": top_3_scores,

            # ---------------------------------------------
            # UI compat aliases
            # ---------------------------------------------

            "most_likely_score": likely_score,
            "second_likely_score": second_score,
            "third_likely_score": third_score,

            # =================================================
            # DIAGNOSTIC SUMMARY
            # =================================================

            "confidence": confidence,
            "risk": risk,

            "conclusion": conclusion,
            "factors": factors,

            # =================================================
            # PARALLEL ORGANS (not yet wired)
            # =================================================

            "corners": None,
            "cards": None,

            # =================================================
            # RAW CHAIN OUTPUTS
            # =================================================

            "home_form_context": home_form_context,
            "away_form_context": away_form_context,

            "data": {
                "home": {
                    "form_context": home_form_context,
                    "form_model": _to_dict(
                        home_form_model
                    ),
                },
                "away": {
                    "form_context": away_form_context,
                    "form_model": _to_dict(
                        away_form_model
                    ),
                },
                "goal_model": goal_data,
                "probability_model": probability_data,
                "score_predictor": score_data,
            },

            "brain_result": {
                "brain_version": BRAIN_VERSION,
                "contract_version": CONTRACT_VERSION,
                "teams": {
                    "home": home_team,
                    "away": away_team,
                },
                "history": {
                    "home": home_form_context,
                    "away": away_form_context,
                },
                "form_model": {
                    "home": _to_dict(
                        home_form_model
                    ),
                    "away": _to_dict(
                        away_form_model
                    ),
                },
                "diagnostics": diagnostics,
                "goal_model": goal_data,
                "probability_model": probability_data,
                "score_predictor": score_data,
                "stages": {
                    "form": {
                        "home": _to_dict(
                            home_form_model
                        ),
                        "away": _to_dict(
                            away_form_model
                        ),
                    },
                    "probability_score": core.get(
                        "stage"
                    ),
                },
            },

            "calculation_meta": calculation_meta,

            "diagnostics": diagnostics,
        }

    # ========================================================
    # PUBLIC API
    # ========================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_matches: Iterable[Any],
        away_matches: Iterable[Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:

        """
        PUBLIC FAJ BRAIN API.

        Requires exactly six historical matches per team.

        Order:

            M1 oldest ... M6 newest

        Brain does NOT sort history.
        """

        # ====================================================
        # 1. Normalize history
        # ====================================================

        home_history = _normalize_history(
            home_matches,
            home_team,
        )

        away_history = _normalize_history(
            away_matches,
            away_team,
        )

        # ====================================================
        # 2. Canonical FormContext
        # ====================================================

        home_form_context = _build_form(
            home_team,
            home_history,
        )

        away_form_context = _build_form(
            away_team,
            away_history,
        )

        if home_form_context is None:
            raise RuntimeError(
                f"Failed to build FormContext for "
                f"{home_team}"
            )

        if away_form_context is None:
            raise RuntimeError(
                f"Failed to build FormContext for "
                f"{away_team}"
            )

        # ====================================================
        # 3. FormModel
        # ====================================================

        home_form_model = self._run_form_model(
            home_form_context,
            next_venue="home",
        )

        away_form_model = self._run_form_model(
            away_form_context,
            next_venue="away",
        )

        if home_form_model is None:
            raise RuntimeError(
                f"FormModel returned None for "
                f"{home_team}"
            )

        if away_form_model is None:
            raise RuntimeError(
                f"FormModel returned None for "
                f"{away_team}"
            )

        # ====================================================
        # 4. Diagnostic organs
        # ====================================================

        diagnostics = self._run_diagnostics(
            home_form_context=home_form_context,
            away_form_context=away_form_context,
            home_team=home_team,
            away_team=away_team,
        )

        # ====================================================
        # 5. Core mathematical chain
        # ====================================================

        core = self._run_core_prediction(
            home_form_model=home_form_model,
            away_form_model=away_form_model,
            home_team=home_team,
            away_team=away_team,
            home_history=home_history,
            away_history=away_history,
            diagnostics=diagnostics,
        )

        # ====================================================
        # 6. Final output
        # ====================================================

        return self._build_final_output(
            home_team=home_team,
            away_team=away_team,
            home_history=home_history,
            away_history=away_history,
            home_form_context=home_form_context,
            away_form_context=away_form_context,
            home_form_model=home_form_model,
            away_form_model=away_form_model,
            diagnostics=diagnostics,
            core=core,
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def predict_match(
    home_team: str,
    away_team: str,
    home_matches: Iterable[Any],
    away_matches: Iterable[Any],
) -> Dict[str, Any]:
    """
    Convenience API.
    """

    brain = FAJBrain()

    return brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_matches,
        away_matches=away_matches,
    )
