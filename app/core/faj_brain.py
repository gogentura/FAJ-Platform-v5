#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN
============================================================

ROLE:
    Thin analytical orchestrator.

CANONICAL MATHEMATICAL CHAIN:

    6 HOME + 6 AWAY
            ↓
       FormContext
            ↓
        FormModel
            ↓
       GoalModel v6.0
            ↓
        λH / λA
            ↓
    ProbabilityModel
            ↓
    1X2 / BTTS / TOTALS /
    JOINT SCORE DISTRIBUTION
            ↓
      ScorePredictor
            ↓
    predicted / likely /
       top scores

PARALLEL CHANNELS:

    FormWin
    Defence
    FormControl
    FormAnomaly
    FormSpecial
    CornersModel
    CardsModel

IMPORTANT:

    Brain does NOT:
        - calculate xG
        - calculate lambda
        - calculate Poisson
        - calculate 1X2
        - calculate BTTS
        - calculate totals
        - calculate score probabilities
        - sort score probabilities
        - apply rating multipliers
        - apply Winner Signal
        - apply Winner Synthesis
        - modify GoalModel formulas
        - modify ProbabilityModel formulas
        - modify ScorePredictor formulas
        - train parameters
        - write to database

    Missing != 0.

    Core mathematical failures are explicit.

    Diagnostic failures are isolated and reported.

============================================================
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


# ============================================================
# CORE MATHEMATICAL ORGANS
# ============================================================

from .form_context import build_form_context
from .form_model import FormModel
from .goal_model import GoalModel
from .probability_model import ProbabilityModel
from .score_predictor import ScorePredictor


# ============================================================
# DIAGNOSTIC ORGANS
# ============================================================

from .form_win import FormWin
from .defence import Defence
from .form_control import FormControl
from .form_anomaly import FormAnomaly
from .special_form import FormSpecial


# ============================================================
# PARALLEL MODELS
# ============================================================

from .corners_model import CornersModel
from .cards_model import CardsModel


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-2.0"
BRAIN_STATUS = "FINAL-CANDIDATE"

HISTORY_SIZE = 6


# ============================================================
# EXCEPTIONS
# ============================================================

class BrainCoreError(RuntimeError):
    """
    Explicit failure of a mandatory mathematical stage.
    """

    pass


# ============================================================
# GENERIC VALUE HELPERS
# ============================================================

def _get(
    obj: Any,
    *names: str,
) -> Any:
    """
    Read a field from dict / Mapping / sqlite.Row /
    dataclass/object.
    """

    if obj is None:
        return None

    for name in names:

        if isinstance(obj, Mapping):
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


def _dict(
    obj: Any,
) -> Dict[str, Any]:
    """
    Serialize model results without changing their contract.
    """

    if obj is None:
        return {}

    if isinstance(obj, dict):
        return dict(obj)

    if isinstance(obj, Mapping):
        return dict(obj)

    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            pass

    to_dict = getattr(obj, "to_dict", None)

    if callable(to_dict):
        result = to_dict()

        if isinstance(result, Mapping):
            return dict(result)

    try:
        return dict(vars(obj))
    except Exception:
        return {}


def _num(
    value: Any,
) -> Optional[float]:
    """
    Numeric normalization.

    Missing / invalid values remain None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        number = float(value)

    except (TypeError, ValueError):
        return None

    if number != number:
        return None

    if number in (
        float("inf"),
        float("-inf"),
    ):
        return None

    return number


def _prob01(
    value: Any,
) -> Optional[float]:
    """
    Normalize probability to [0, 1].

    This does NOT calculate a probability.
    It only normalizes an already calculated model value.
    """

    number = _num(value)

    if number is None:
        return None

    if number > 1.0:
        number /= 100.0

    return max(
        0.0,
        min(1.0, number),
    )


def _prob100(
    value: Any,
) -> Optional[float]:
    """
    Presentation conversion from [0,1] to percentage.
    """

    probability = _prob01(value)

    if probability is None:
        return None

    return round(
        probability * 100.0,
        1,
    )


def _serialize(
    value: Any,
) -> Any:
    """
    Recursively serialize model result structures.
    """

    if value is None:
        return None

    if isinstance(value, Mapping):
        return {
            key: _serialize(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _serialize(item)
            for item in value
        ]

    if is_dataclass(value):
        return _serialize(asdict(value))

    to_dict = getattr(value, "to_dict", None)

    if callable(to_dict):
        result = to_dict()

        return _serialize(result)

    return value


# ============================================================
# HISTORY VALIDATION
# ============================================================

def _history(
    matches: Iterable[Any],
    team_name: str,
) -> List[Any]:
    """
    Validate exactly six historical records.

    Predictor already supplies canonical team-level records.

    Brain does not invent missing matches.
    """

    if matches is None:
        raise BrainCoreError(
            f"{team_name}: historical matches are missing"
        )

    try:
        values = list(matches)

    except TypeError as exc:
        raise BrainCoreError(
            f"{team_name}: invalid history container"
        ) from exc

    if len(values) != HISTORY_SIZE:
        raise BrainCoreError(
            f"{team_name}: FAJBrain requires exactly "
            f"{HISTORY_SIZE} historical matches; "
            f"received {len(values)}"
        )

    return values


# ============================================================
# RECORD NORMALIZATION
# ============================================================

def _normalize_record(
    record: Any,
) -> Dict[str, Any]:
    """
    Preserve the current FAJ Predictor team-record contract.

    Expected canonical fields include:

        team
        team_name
        opponent
        is_home
        venue
        goals_for
        goals_against
        result
        xg
        xga
        corners
        opponent_corners
        yellow_cards
        opponent_yellow_cards
        match_date
        competition
        extra

    No mathematical value is fabricated here.
    """

    if isinstance(record, Mapping):
        return dict(record)

    if is_dataclass(record):
        return asdict(record)

    to_dict = getattr(record, "to_dict", None)

    if callable(to_dict):
        result = to_dict()

        if isinstance(result, Mapping):
            return dict(result)

    try:
        keys = record.keys()

        return {
            key: record[key]
            for key in keys
        }

    except (AttributeError, TypeError):
        pass

    try:
        return dict(vars(record))

    except Exception as exc:
        raise BrainCoreError(
            "Historical record cannot be normalized"
        ) from exc


def _normalize_history(
    matches: Sequence[Any],
) -> List[Dict[str, Any]]:
    """
    Normalize records without changing their factual content.
    """

    return [
        _normalize_record(record)
        for record in matches
    ]


# ============================================================
# FORM CONTEXT
# ============================================================

def _build_context(
    team_name: str,
    history: Sequence[Any],
) -> Dict[str, Any]:
    """
    Canonical history -> FormContext adapter.

    The current FormContext API receives:
        team_name
        records

    It owns the six-match limitation.
    """

    records = _normalize_history(history)

    try:
        context = build_form_context(
            team_name=team_name,
            records=records,
        )

    except Exception as exc:
        raise BrainCoreError(
            f"FormContext failed for {team_name}"
        ) from exc

    context_dict = _dict(context)

    if not isinstance(context_dict, dict):
        raise BrainCoreError(
            f"FormContext returned invalid result for {team_name}"
        )

    return context_dict


# ============================================================
# FORM MODEL
# ============================================================

def _form_models(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any]:
    """
    Mandatory mathematical FormModel stage.
    """

    model = FormModel()

    try:
        home_form = model.analyze(
            form_context=home_context,
            next_venue="home",
        )

        away_form = model.analyze(
            form_context=away_context,
            next_venue="away",
        )

    except Exception as exc:
        raise BrainCoreError(
            "FormModel failed"
        ) from exc

    if home_form is None or away_form is None:
        raise BrainCoreError(
            "FormModel returned missing result"
        )

    return home_form, away_form


# ============================================================
# DIAGNOSTICS
# ============================================================

def _diagnostic_call(
    name: str,
    fn: Any,
    **kwargs: Any,
) -> tuple[Any, Optional[str]]:
    """
    Isolated diagnostic execution.

    Diagnostic failure never creates fake mathematical data.
    """

    try:
        return fn(**kwargs), None

    except Exception as exc:
        return None, f"{name}: {exc}"


def _diagnostics(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Dict[str, Any]:

    diagnostics: Dict[str, Any] = {
        "contract": {
            "prediction_impact": "none",
            "lambda_influence": False,
            "probability_influence": False,
            "score_ranking_influence": False,
        },

        "home": {},
        "away": {},

        "errors": [],
    }

    # --------------------------------------------------------
    # FORM WIN
    # --------------------------------------------------------

    form_win = FormWin()

    home_value, error = _diagnostic_call(
        "FormWin.home",
        form_win.analyze,
        form_context=home_context,
        next_venue="home",
    )

    diagnostics["home"]["form_win"] = _serialize(
        home_value
    )

    if error:
        diagnostics["errors"].append(error)

    away_value, error = _diagnostic_call(
        "FormWin.away",
        form_win.analyze,
        form_context=away_context,
        next_venue="away",
    )

    diagnostics["away"]["form_win"] = _serialize(
        away_value
    )

    if error:
        diagnostics["errors"].append(error)

    # Comparison is diagnostic only.
    comparison, error = _diagnostic_call(
        "FormWin.compare",
        form_win.compare,
        home_context,
        away_context,
    )

    diagnostics["form_win_comparison"] = _serialize(
        comparison
    )

    if error:
        diagnostics["errors"].append(error)

    # --------------------------------------------------------
    # DEFENCE
    # --------------------------------------------------------

    defence = Defence()

    home_value, error = _diagnostic_call(
        "Defence.home",
        defence.calculate,
        context=home_context,
        team_name=home_team,
    )

    diagnostics["home"]["defence"] = _serialize(
        home_value
    )

    if error:
        diagnostics["errors"].append(error)

    away_value, error = _diagnostic_call(
        "Defence.away",
        defence.calculate,
        context=away_context,
        team_name=away_team,
    )

    diagnostics["away"]["defence"] = _serialize(
        away_value
    )

    if error:
        diagnostics["errors"].append(error)

    # --------------------------------------------------------
    # FORM CONTROL
    # --------------------------------------------------------

    control = FormControl()

    home_control, error = _diagnostic_call(
        "FormControl.home",
        control.analyze,
        context=home_context,
        target_team=home_team,
        opponent_team=away_team,
        venue="home",
    )

    diagnostics["home"]["control"] = _serialize(
        home_control
    )

    if error:
        diagnostics["errors"].append(error)

    away_control, error = _diagnostic_call(
        "FormControl.away",
        control.analyze,
        context=away_context,
        target_team=away_team,
        opponent_team=home_team,
        venue="away",
    )

    diagnostics["away"]["control"] = _serialize(
        away_control
    )

    if error:
        diagnostics["errors"].append(error)

    if (
        home_control is not None
        and away_control is not None
    ):
        diagnostics["control_comparison"] = {
            "home_signal": _get(
                home_control,
                "control_signal",
            ),
            "away_signal": _get(
                away_control,
                "control_signal",
            ),
            "home_strength": _get(
                home_control,
                "control_strength",
            ),
            "away_strength": _get(
                away_control,
                "control_strength",
            ),
            "home_result": _serialize(
                home_control
            ),
            "away_result": _serialize(
                away_control
            ),
        }

    else:
        diagnostics["control_comparison"] = None

    # --------------------------------------------------------
    # FORM ANOMALY
    # --------------------------------------------------------

    anomaly = FormAnomaly()

    home_anomaly, error = _diagnostic_call(
        "FormAnomaly.home",
        anomaly.analyze,
        context=home_context,
    )

    diagnostics["home"]["anomaly"] = _serialize(
        home_anomaly
    )

    if error:
        diagnostics["errors"].append(error)

    away_anomaly, error = _diagnostic_call(
        "FormAnomaly.away",
        anomaly.analyze,
        context=away_context,
    )

    diagnostics["away"]["anomaly"] = _serialize(
        away_anomaly
    )

    if error:
        diagnostics["errors"].append(error)

    # --------------------------------------------------------
    # SPECIAL FORM
    # --------------------------------------------------------

    special = FormSpecial()

    home_special, error = _diagnostic_call(
        "FormSpecial.home",
        special.analyze,
        context=home_context,
        team_name=home_team,
    )

    diagnostics["home"]["special_form"] = _serialize(
        home_special
    )

    if error:
        diagnostics["errors"].append(error)

    away_special, error = _diagnostic_call(
        "FormSpecial.away",
        special.analyze,
        context=away_context,
        team_name=away_team,
    )

    diagnostics["away"]["special_form"] = _serialize(
        away_special
    )

    if error:
        diagnostics["errors"].append(error)

    return diagnostics


# ============================================================
# GOAL MODEL
# ============================================================

def _goal_model(
    home_form: Any,
    away_form: Any,
    home_team: str,
    away_team: str,
    home_history: Sequence[Any],
    away_history: Sequence[Any],
    diagnostics: Dict[str, Any],
) -> Any:
    """
    Mandatory GoalModel v6.0 stage.

    GoalModel owns:
        λH
        λA

    Brain does not recalculate them.
    """

    goal_model = GoalModel()

    try:
        result = goal_model.analyze(
            home_form=home_form,
            away_form=away_form,

            home_team=home_team,
            away_team=away_team,

            venue="home",

            home_control=diagnostics["home"].get(
                "control"
            ),
            away_control=diagnostics["away"].get(
                "control"
            ),

            home_special=diagnostics["home"].get(
                "special_form"
            ),
            away_special=diagnostics["away"].get(
                "special_form"
            ),

            home_history=home_history,
            away_history=away_history,
        )

    except Exception as exc:
        raise BrainCoreError(
            "GoalModel failed"
        ) from exc

    if result is None:
        raise BrainCoreError(
            "GoalModel returned missing result"
        )

    return result


def _goal_lambdas(
    goal_result: Any,
) -> tuple[float, float]:
    """
    Extract GoalModel-owned λ values.

    No recalculation.
    """

    data = _dict(goal_result)

    home_xg = _num(
        _get(
            data,
            "home_xg",
            "lambda_home",
            "home_lambda",
        )
    )

    away_xg = _num(
        _get(
            data,
            "away_xg",
            "lambda_away",
            "away_lambda",
        )
    )

    if home_xg is None:
        raise BrainCoreError(
            "GoalModel did not return home_xg"
        )

    if away_xg is None:
        raise BrainCoreError(
            "GoalModel did not return away_xg"
        )

    if not (
        0.0 <= home_xg <= 4.50
    ):
        raise BrainCoreError(
            f"Invalid GoalModel home_xg={home_xg}"
        )

    if not (
        0.0 <= away_xg <= 4.50
    ):
        raise BrainCoreError(
            f"Invalid GoalModel away_xg={away_xg}"
        )

    return home_xg, away_xg


# ============================================================
# PROBABILITY MODEL
# ============================================================

def _probability_model(
    home_xg: float,
    away_xg: float,
) -> Any:
    """
    Mandatory ProbabilityModel stage.

    Brain passes GoalModel lambdas directly.
    """

    model = ProbabilityModel()

    try:
        result = model.calculate(
            home_xg=home_xg,
            away_xg=away_xg,
        )

    except Exception as exc:
        raise BrainCoreError(
            "ProbabilityModel failed"
        ) from exc

    if result is None:
        raise BrainCoreError(
            "ProbabilityModel returned missing result"
        )

    data = _dict(result)

    distribution = _get(
        data,
        "score_distribution",
        "score_probabilities",
        "distribution",
    )

    if distribution is None:
        raise BrainCoreError(
            "ProbabilityModel did not return "
            "score_distribution"
        )

    return result


# ============================================================
# SCORE PREDICTOR
# ============================================================

def _score_predictor(
    probability_result: Any,
    home_xg: float,
    away_xg: float,
) -> Any:
    """
    Mandatory ScorePredictor stage.

    ScorePredictor owns score ranking.
    """

    probability_data = _dict(
        probability_result
    )

    distribution = _get(
        probability_data,
        "score_distribution",
        "score_probabilities",
        "distribution",
    )

    if distribution is None:
        raise BrainCoreError(
            "ScorePredictor input distribution missing"
        )

    predictor = ScorePredictor()

    try:
        result = predictor.predict(
            score_probabilities=distribution,
            home_xg=home_xg,
            away_xg=away_xg,
            probability_result=probability_result,
        )

    except Exception as exc:
        raise BrainCoreError(
            "ScorePredictor failed"
        ) from exc

    if result is None:
        raise BrainCoreError(
            "ScorePredictor returned missing result"
        )

    return result


# ============================================================
# PARALLEL CORNERS / CARDS
# ============================================================

def _side_models(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any, List[str]]:
    """
    Corners and Cards are independent analytical channels.

    They cannot modify:
        xG
        λ
        1X2
        BTTS
        totals
        score distribution
        score ranking
    """

    errors: List[str] = []

    corners = None

    try:
        corners = CornersModel().synthesize_match(
            home_context,
            away_context,
        )

    except Exception as exc:
        errors.append(
            f"CornersModel: {exc}"
        )

    cards = None

    try:
        cards = CardsModel().synthesize_match(
            home_context,
            away_context,
        )

    except Exception as exc:
        errors.append(
            f"CardsModel: {exc}"
        )

    return corners, cards, errors


# ============================================================
# DATA QUALITY
# ============================================================

def _field_coverage(
    records: Sequence[Any],
    field_names: Sequence[str],
) -> Dict[str, Any]:
    """
    Count actual available observations.

    None remains missing.
    """

    total = len(records)

    coverage: Dict[str, Any] = {
        "records": total,
        "fields": {},
    }

    for field in field_names:

        available = 0

        for record in records:
            value = _get(
                record,
                field,
            )

            if value is not None:
                available += 1

        coverage["fields"][field] = {
            "available": available,
            "missing": total - available,
        }

    return coverage


def _data_quality(
    home_history: Sequence[Any],
    away_history: Sequence[Any],
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Transparent data-quality report.

    No quality value is substituted into mathematics.
    """

    home_count = len(home_history)
    away_count = len(away_history)

    history_complete = (
        home_count == HISTORY_SIZE
        and away_count == HISTORY_SIZE
    )

    xg_fields = (
        "xg",
        "xga",
    )

    statistics_fields = (
        "corners",
        "opponent_corners",
        "yellow_cards",
        "opponent_yellow_cards",
    )

    home_xg = _field_coverage(
        home_history,
        xg_fields,
    )

    away_xg = _field_coverage(
        away_history,
        xg_fields,
    )

    home_stats = _field_coverage(
        home_history,
        statistics_fields,
    )

    away_stats = _field_coverage(
        away_history,
        statistics_fields,
    )

    diagnostic_errors = diagnostics.get(
        "errors",
        [],
    )

    diagnostics_available = (
        len(diagnostic_errors) == 0
    )

    return {
        "history": {
            "required_per_team": HISTORY_SIZE,
            "home_matches": home_count,
            "away_matches": away_count,
            "status": (
                "complete"
                if history_complete
                else "partial"
            ),
        },

        "xg": {
            "home": home_xg,
            "away": away_xg,
        },

        "statistics": {
            "home": home_stats,
            "away": away_stats,
        },

        "diagnostics": {
            "available": diagnostics_available,
            "errors": list(
                diagnostic_errors
            ),
        },

        "form_context": {
            "home_matches_count": _get(
                home_context,
                "matches_count",
            ),
            "away_matches_count": _get(
                away_context,
                "matches_count",
            ),
        },

        "missing_is_not_zero": True,
    }


# ============================================================
# SCORE EXTRACTION
# ============================================================

def _score_output(
    score_result: Any,
) -> Dict[str, Any]:
    """
    Extract ScorePredictor-owned output.

    Brain does not rank scores again.
    """

    data = _dict(score_result)

    top_scores = _get(
        data,
        "top_scores",
    )

    predicted_score = _get(
        data,
        "predicted_score",
    )

    likely_score = _get(
        data,
        "likely_score",
        "most_likely_score",
    )

    return {
        "predicted_score": predicted_score,
        "most_likely_score": likely_score,
        "top_scores": top_scores,
    }


# ============================================================
# SIDE VALUE EXTRACTION
# ============================================================

def _expected_side_value(
    result: Any,
    *names: str,
) -> Optional[float]:
    data = _dict(result)

    return _num(
        _get(
            data,
            *names,
        )
    )


# ============================================================
# CONFIDENCE
# ============================================================

def _confidence(
    goal_result: Any,
) -> Optional[float]:
    """
    Confidence source:

        GoalModel.confidence

    Brain does not calculate a new confidence score.
    """

    data = _dict(goal_result)

    return _prob01(
        _get(
            data,
            "confidence",
        )
    )


# ============================================================
# MODEL METADATA
# ============================================================

def _model_version(
    result: Any,
    *names: str,
) -> Optional[str]:
    data = _dict(result)

    value = _get(
        data,
        *names,
    )

    if value is None:
        return None

    return str(value)


# ============================================================
# MAIN BRAIN
# ============================================================

class FAJBrain:
    """
    FAJ Brain v2.0.

    Thin orchestrator over the current mathematical organs.
    """

    VERSION = BRAIN_VERSION
    STATUS = BRAIN_STATUS

    def __init__(self) -> None:

        self.version = BRAIN_VERSION

        # ----------------------------------------------------
        # Real mathematical organs
        # ----------------------------------------------------

        self.form_model = FormModel()
        self.goal_model = GoalModel()
        self.probability_model = ProbabilityModel()
        self.score_predictor = ScorePredictor()

        # ----------------------------------------------------
        # Real diagnostic organs
        # ----------------------------------------------------

        self.form_win = FormWin()
        self.defence = Defence()
        self.form_control = FormControl()
        self.form_anomaly = FormAnomaly()
        self.form_special = FormSpecial()

        # ----------------------------------------------------
        # Independent side models
        # ----------------------------------------------------

        self.corners_model = CornersModel()
        self.cards_model = CardsModel()

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
        Execute the complete FAJ Brain chain.

        Required input:
            exactly 6 home historical matches
            exactly 6 away historical matches

        The current Predictor already supplies team-level
        historical records. Brain preserves those facts.
        """

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not isinstance(
            home_team,
            str,
        ) or not home_team.strip():

            raise BrainCoreError(
                "home_team is required"
            )

        if not isinstance(
            away_team,
            str,
        ) or not away_team.strip():

            raise BrainCoreError(
                "away_team is required"
            )

        home_team = home_team.strip()
        away_team = away_team.strip()

        home_history = _history(
            home_matches,
            home_team,
        )

        away_history = _history(
            away_matches,
            away_team,
        )

        # ----------------------------------------------------
        # FORM CONTEXT
        # ----------------------------------------------------

        home_context = _build_context(
            home_team,
            home_history,
        )

        away_context = _build_context(
            away_team,
            away_history,
        )

        # ----------------------------------------------------
        # FORM MODEL
        # ----------------------------------------------------

        home_form, away_form = _form_models(
            home_context,
            away_context,
        )

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics = _diagnostics(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        # ----------------------------------------------------
        # GOAL MODEL
        # ----------------------------------------------------

        goal_result = self.goal_model.analyze(
            home_form=home_form,
            away_form=away_form,

            home_team=home_team,
            away_team=away_team,

            venue="home",

            home_control=diagnostics["home"].get(
                "control"
            ),
            away_control=diagnostics["away"].get(
                "control"
            ),

            home_special=diagnostics["home"].get(
                "special_form"
            ),
            away_special=diagnostics["away"].get(
                "special_form"
            ),

            home_history=home_history,
            away_history=away_history,
        )

        if goal_result is None:
            raise BrainCoreError(
                "GoalModel returned None"
            )

        home_xg, away_xg = _goal_lambdas(
            goal_result
        )

        # ----------------------------------------------------
        # PROBABILITY MODEL
        # ----------------------------------------------------

        probability_result = self.probability_model.calculate(
            home_xg=home_xg,
            away_xg=away_xg,
        )

        if probability_result is None:
            raise BrainCoreError(
                "ProbabilityModel returned None"
            )

        probability_data = _dict(
            probability_result
        )

        score_distribution = _get(
            probability_data,
            "score_distribution",
            "score_probabilities",
            "distribution",
        )

        if score_distribution is None:
            raise BrainCoreError(
                "ProbabilityModel returned no "
                "score_distribution"
            )

        # ----------------------------------------------------
        # SCORE PREDICTOR
        # ----------------------------------------------------

        score_result = self.score_predictor.predict(
            score_probabilities=score_distribution,
            home_xg=home_xg,
            away_xg=away_xg,
            probability_result=probability_result,
        )

        if score_result is None:
            raise BrainCoreError(
                "ScorePredictor returned None"
            )

        score_data = _dict(
            score_result
        )

        score_output = _score_output(
            score_result
        )

        # ----------------------------------------------------
        # PARALLEL CORNERS / CARDS
        # ----------------------------------------------------

        corners_result, cards_result, side_errors = (
            _side_models(
                home_context,
                away_context,
            )
        )

        if side_errors:
            diagnostics.setdefault(
                "errors",
                [],
            ).extend(side_errors)

        # ----------------------------------------------------
        # PROBABILITIES
        # ----------------------------------------------------

        home_win = _prob01(
            _get(
                probability_data,
                "home_win",
                "home_win_probability",
            )
        )

        draw = _prob01(
            _get(
                probability_data,
                "draw",
                "draw_probability",
            )
        )

        away_win = _prob01(
            _get(
                probability_data,
                "away_win",
                "away_win_probability",
            )
        )

        btts = _prob01(
            _get(
                probability_data,
                "btts",
                "btts_probability",
            )
        )

        over25 = _prob01(
            _get(
                probability_data,
                "over25",
                "over_25",
                "over25_probability",
            )
        )

        over35 = _prob01(
            _get(
                probability_data,
                "over35",
                "over_35",
                "over35_probability",
            )
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        confidence = _confidence(
            goal_result
        )

        # ----------------------------------------------------
        # CORNERS
        # ----------------------------------------------------

        corners_value = None

        if corners_result is not None:
            corners_value = _expected_side_value(
                corners_result,
                "total_expected_corners",
                "expected_corners",
                "total_corners",
            )

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------

        cards_value = None

        if cards_result is not None:
            cards_value = _expected_side_value(
                cards_result,
                "total_expected_cards",
                "expected_cards",
                "total_cards",
            )

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        data_quality = _data_quality(
            home_history=home_history,
            away_history=away_history,
            home_context=home_context,
            away_context=away_context,
            diagnostics=diagnostics,
        )

        # ----------------------------------------------------
        # CALCULATION META
        # ----------------------------------------------------

        calculation_meta: Dict[str, Any] = {
            "brain": {
                "version": BRAIN_VERSION,
                "status": BRAIN_STATUS,
                "history_size": HISTORY_SIZE,
            },

            "chain": [
                "FormContext",
                "FormModel",
                "GoalModel",
                "ProbabilityModel",
                "ScorePredictor",
            ],

            "goal_model": _serialize(
                goal_result
            ),

            "probability_model": _serialize(
                probability_result
            ),

            "score_predictor": _serialize(
                score_result
            ),

            "corners_model": _serialize(
                corners_result
            ),

            "cards_model": _serialize(
                cards_result
            ),

            "form_model": {
                "home": _serialize(
                    home_form
                ),
                "away": _serialize(
                    away_form
                ),
            },

            "diagnostics": diagnostics,

            "ownership": {
                "xg": "GoalModel",
                "lambda": "GoalModel",
                "probabilities": "ProbabilityModel",
                "score_distribution": "ProbabilityModel",
                "score_ranking": "ScorePredictor",
                "corners": "CornersModel",
                "cards": "CardsModel",
            },

            "diagnostic_policy": {
                "form_win_affects_prediction": False,
                "defence_affects_prediction": False,
                "form_control_affects_prediction": False,
                "form_anomaly_affects_prediction": False,
                "form_special_affects_prediction": False,
                "corners_affects_goal_model": False,
                "cards_affects_goal_model": False,
            },

            "math_integrity": {
                "brain_recalculates_xg": False,
                "brain_recalculates_lambda": False,
                "brain_recalculates_poisson": False,
                "brain_recalculates_1x2": False,
                "brain_recalculates_btts": False,
                "brain_recalculates_totals": False,
                "brain_reranks_scores": False,
                "winner_synthesis": False,
                "winner_signal": False,
                "rating_multiplier": False,
                "missing_is_not_zero": True,
            },

            "model_versions": {
                "goal_model": _model_version(
                    goal_result,
                    "model_version",
                    "version",
                ),
                "probability_model": _model_version(
                    probability_result,
                    "model_version",
                    "version",
                ),
                "score_predictor": _model_version(
                    score_result,
                    "model_version",
                    "version",
                ),
            },
        }

        # ----------------------------------------------------
        # FINAL OUTPUT
        # ----------------------------------------------------

        return {
            # ------------------------------------------------
            # MATCH
            # ------------------------------------------------

            "home_team": home_team,
            "away_team": away_team,

            "home_matches": len(
                home_history
            ),
            "away_matches": len(
                away_history
            ),

            # ------------------------------------------------
            # GOALS
            # ------------------------------------------------

            "home_xg": home_xg,
            "away_xg": away_xg,

            # ------------------------------------------------
            # 1X2
            # ------------------------------------------------

            "home_win_probability": _prob100(
                home_win
            ),

            "draw_probability": _prob100(
                draw
            ),

            "away_win_probability": _prob100(
                away_win
            ),

            # ------------------------------------------------
            # BTTS / TOTALS
            # ------------------------------------------------

            "btts_probability": _prob100(
                btts
            ),

            "over25_probability": _prob100(
                over25
            ),

            "over35_probability": _prob100(
                over35
            ),

            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            "predicted_score": score_output[
                "predicted_score"
            ],

            "most_likely_score": score_output[
                "most_likely_score"
            ],

            "top_scores": score_output[
                "top_scores"
            ],

            # ------------------------------------------------
            # PARALLEL MODELS
            # ------------------------------------------------

            "corners": corners_value,
            "cards": cards_value,

            # ------------------------------------------------
            # DIAGNOSTICS
            # ------------------------------------------------

            "diagnostics": _serialize(
                diagnostics
            ),

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            "data_quality": data_quality,

            # ------------------------------------------------
            # CONFIDENCE / RISK
            # ------------------------------------------------

            "confidence": confidence,

            # No current mathematical owner.
            "risk": None,

            # No current analytical conclusion engine.
            "conclusion": None,

            # ------------------------------------------------
            # META
            # ------------------------------------------------

            "calculation_meta": calculation_meta,

            "model_version": BRAIN_VERSION,

            # ------------------------------------------------
            # FULL ORGAN OUTPUT
            # ------------------------------------------------

            "brain_result": {
                "brain_version": BRAIN_VERSION,
                "brain_status": BRAIN_STATUS,

                "teams": {
                    "home": home_team,
                    "away": away_team,
                },

                "home_form_context": _serialize(
                    home_context
                ),

                "away_form_context": _serialize(
                    away_context
                ),

                "home_form_model": _serialize(
                    home_form
                ),

                "away_form_model": _serialize(
                    away_form
                ),

                "goal_model": _serialize(
                    goal_result
                ),

                "probability_model": _serialize(
                    probability_result
                ),

                "score_predictor": _serialize(
                    score_result
                ),

                "corners_model": _serialize(
                    corners_result
                ),

                "cards_model": _serialize(
                    cards_result
                ),

                "diagnostics": _serialize(
                    diagnostics
                ),
            },
        }


# ============================================================
# CONVENIENCE API
# ============================================================

def predict_match(
    home_team: str,
    away_team: str,
    home_matches: Iterable[Any],
    away_matches: Iterable[Any],
) -> Dict[str, Any]:
    """
    Module-level convenience API.
    """

    return FAJBrain().predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_matches,
        away_matches=away_matches,
    )


# ============================================================
# END
# ============================================================
