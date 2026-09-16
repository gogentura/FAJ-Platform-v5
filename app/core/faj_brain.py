#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN
============================================================

THIN ANALYTICAL ORCHESTRATOR

CANONICAL CHAIN

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
    ProbabilityModel v1.1
            ↓
       1X2 / BTTS
       TOTALS / SCORE MATRIX
            ↓
      ScorePredictor v2.2
            ↓
     predicted / likely /
        top scores

PARALLEL DIAGNOSTIC CHANNELS

    FormWin
    Defence
    FormControl
    FormAnomaly
    FormSpecial

PARALLEL INDEPENDENT MODELS

    CornersModel
    CardsModel

IMPORTANT

Brain does NOT:

    - calculate xG
    - calculate lambda
    - calculate Poisson
    - calculate 1X2
    - calculate BTTS
    - calculate totals
    - calculate score probabilities
    - rank scores again
    - apply rating multipliers
    - modify GoalModel
    - modify ProbabilityModel
    - modify ScorePredictor
    - train parameters
    - write to database

Missing != 0.

Diagnostic failure does not become mathematical data.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .form_context import build_form_context
from .form_model import FormModel
from .goal_model import GoalModel
from .probability_model import ProbabilityModel
from .score_predictor import ScorePredictor

from .form_win import FormWin
from .defence import Defence
from .form_control import FormControl
from .form_anomaly import FormAnomaly
from .special_form import FormSpecial

from .corners_model import CornersModel
from .cards_model import CardsModel


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-3.0"
BRAIN_STATUS = "FINAL"

HISTORY_SIZE = 6


# ============================================================
# EXCEPTION
# ============================================================

class BrainCoreError(RuntimeError):
    """Mandatory FAJ Brain stage failed."""

    pass


# ============================================================
# GENERIC HELPERS
# ============================================================

def _get(obj: Any, *names: str) -> Any:
    """Read a value from dict / sqlite.Row / object."""

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


def _dict(obj: Any) -> Dict[str, Any]:
    """Convert model result to dict without changing its data."""

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
        try:
            result = to_dict()

            if isinstance(result, Mapping):
                return dict(result)

        except Exception:
            pass

    try:
        return dict(vars(obj))

    except Exception:
        return {}


def _serialize(obj: Any) -> Any:
    """Recursively serialize model output."""

    if obj is None:
        return None

    if isinstance(obj, Mapping):
        return {
            key: _serialize(value)
            for key, value in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [
            _serialize(value)
            for value in obj
        ]

    if is_dataclass(obj):
        return _serialize(asdict(obj))

    to_dict = getattr(obj, "to_dict", None)

    if callable(to_dict):
        try:
            return _serialize(to_dict())
        except Exception:
            pass

    return obj


def _num(value: Any) -> Optional[float]:
    """
    Numeric conversion.

    Invalid / missing values remain None.
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


def _prob01(value: Any) -> Optional[float]:
    """
    Normalize already calculated probability to [0, 1].

    This does NOT calculate probability.
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


def _prob100(value: Any) -> Optional[float]:
    """Presentation conversion [0,1] -> percentage."""

    probability = _prob01(value)

    if probability is None:
        return None

    return round(
        probability * 100.0,
        1,
    )


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
# HISTORY
# ============================================================

def _normalize_record(record: Any) -> Dict[str, Any]:
    """
    Preserve Predictor's factual team-record structure.

    No missing value is invented.
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

    return [
        _normalize_record(record)
        for record in matches
    ]


def _history(
    matches: Iterable[Any],
    team_name: str,
) -> List[Any]:
    """
    FAJ Brain requires exactly six records per team.

    Predictor is responsible for selecting the six
    most recent records and ordering them oldest -> newest.
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
            f"{team_name}: FAJ Brain requires exactly "
            f"{HISTORY_SIZE} historical matches; "
            f"received {len(values)}"
        )

    return values


# ============================================================
# FORM CONTEXT
# ============================================================

def _build_context(
    team_name: str,
    history: Sequence[Any],
) -> Dict[str, Any]:
    """
    Build canonical FormContext.

    Current FormContext API:
        build_form_context(
            team_name=...,
            records=...
        )
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

    result = _dict(context)

    if not result:
        raise BrainCoreError(
            f"FormContext returned empty result for {team_name}"
        )

    return result


# ============================================================
# FORM MODEL
# ============================================================

def _run_form_model(
    model: FormModel,
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any]:

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

    if home_form is None:
        raise BrainCoreError(
            "FormModel returned None for home team"
        )

    if away_form is None:
        raise BrainCoreError(
            "FormModel returned None for away team"
        )

    return home_form, away_form


# ============================================================
# DIAGNOSTIC EXECUTION
# ============================================================

def _safe_diagnostic(
    errors: List[str],
    name: str,
    function: Any,
    **kwargs: Any,
) -> Any:
    """
    Execute a diagnostic organ.

    Failure is isolated.
    No fake value is generated.
    """

    try:
        return function(**kwargs)

    except Exception as exc:
        errors.append(
            f"{name}: {exc}"
        )

        return None


def _run_diagnostics(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Dict[str, Any]:
    """
    Run descriptive organs only.

    IMPORTANT:
        There is no winner synthesis here.
        There is no FormWin.compare().
        There is no second mathematical prediction.
    """

    errors: List[str] = []

    result: Dict[str, Any] = {
        "home": {},
        "away": {},
        "errors": errors,
        "contract": {
            "prediction_impact": False,
            "lambda_influence": False,
            "probability_influence": False,
            "score_ranking_influence": False,
        },
    }

    # --------------------------------------------------------
    # FormWin
    # --------------------------------------------------------

    form_win = FormWin()

    result["home"]["form_win"] = _safe_diagnostic(
        errors,
        "FormWin.home",
        form_win.analyze,
        form_context=home_context,
        next_venue="home",
    )

    result["away"]["form_win"] = _safe_diagnostic(
        errors,
        "FormWin.away",
        form_win.analyze,
        form_context=away_context,
        next_venue="away",
    )

    # --------------------------------------------------------
    # Defence
    # --------------------------------------------------------

    defence = Defence()

    result["home"]["defence"] = _safe_diagnostic(
        errors,
        "Defence.home",
        defence.calculate,
        context=home_context,
        team_name=home_team,
    )

    result["away"]["defence"] = _safe_diagnostic(
        errors,
        "Defence.away",
        defence.calculate,
        context=away_context,
        team_name=away_team,
    )

    # --------------------------------------------------------
    # FormControl
    # --------------------------------------------------------

    control = FormControl()

    result["home"]["control"] = _safe_diagnostic(
        errors,
        "FormControl.home",
        control.analyze,
        context=home_context,
        target_team=home_team,
        opponent_team=away_team,
        venue="home",
    )

    result["away"]["control"] = _safe_diagnostic(
        errors,
        "FormControl.away",
        control.analyze,
        context=away_context,
        target_team=away_team,
        opponent_team=home_team,
        venue="away",
    )

    # --------------------------------------------------------
    # FormAnomaly
    # --------------------------------------------------------

    anomaly = FormAnomaly()

    result["home"]["anomaly"] = _safe_diagnostic(
        errors,
        "FormAnomaly.home",
        anomaly.analyze,
        context=home_context,
    )

    result["away"]["anomaly"] = _safe_diagnostic(
        errors,
        "FormAnomaly.away",
        anomaly.analyze,
        context=away_context,
    )

    # --------------------------------------------------------
    # FormSpecial
    # --------------------------------------------------------

    special = FormSpecial()

    result["home"]["special_form"] = _safe_diagnostic(
        errors,
        "FormSpecial.home",
        special.analyze,
        context=home_context,
        team_name=home_team,
    )

    result["away"]["special_form"] = _safe_diagnostic(
        errors,
        "FormSpecial.away",
        special.analyze,
        context=away_context,
        team_name=away_team,
    )

    return result


# ============================================================
# GOAL MODEL
# ============================================================

def _run_goal_model(
    model: GoalModel,
    home_form: Any,
    away_form: Any,
    home_team: str,
    away_team: str,
    home_history: Sequence[Any],
    away_history: Sequence[Any],
    diagnostics: Dict[str, Any],
) -> Any:
    """
    GoalModel is the sole owner of λH / λA.

    Brain does not calculate xG itself.
    """

    try:
        result = model.analyze(
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
            "GoalModel returned None"
        )

    return result


def _goal_lambdas(
    goal_result: Any,
) -> tuple[float, float]:
    """
    Extract GoalModel-owned xG/lambda.

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

    if not 0.0 <= home_xg <= 4.50:
        raise BrainCoreError(
            f"Invalid GoalModel home_xg={home_xg}"
        )

    if not 0.0 <= away_xg <= 4.50:
        raise BrainCoreError(
            f"Invalid GoalModel away_xg={away_xg}"
        )

    return home_xg, away_xg


# ============================================================
# PROBABILITY MODEL
# ============================================================

def _run_probability_model(
    model: ProbabilityModel,
    home_xg: float,
    away_xg: float,
) -> Any:
    """
    ProbabilityModel owns the complete score matrix
    and all derived probabilities.
    """

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
            "ProbabilityModel returned None"
        )

    data = _dict(result)

    distribution = _get(
        data,
        "score_distribution",
    )

    if distribution is None:
        raise BrainCoreError(
            "ProbabilityModel returned no score_distribution"
        )

    return result


# ============================================================
# SCORE PREDICTOR
# ============================================================

def _run_score_predictor(
    predictor: ScorePredictor,
    probability_result: Any,
    home_xg: float,
    away_xg: float,
) -> Any:
    """
    ScorePredictor owns exact-score ranking.

    Brain does not sort scores itself.
    """

    probability_data = _dict(
        probability_result
    )

    distribution = _get(
        probability_data,
        "score_distribution",
    )

    if distribution is None:
        raise BrainCoreError(
            "ScorePredictor received no score_distribution"
        )

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
            "ScorePredictor returned None"
        )

    return result


# ============================================================
# SIDE MODELS
# ============================================================

def _run_side_models(
    corners_model: CornersModel,
    cards_model: CardsModel,
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any, List[str]]:

    errors: List[str] = []

    corners_result = None

    try:
        corners_result = (
            corners_model.synthesize_match(
                home_context,
                away_context,
            )
        )

    except Exception as exc:
        errors.append(
            f"CornersModel: {exc}"
        )

    cards_result = None

    try:
        cards_result = (
            cards_model.synthesize_match(
                home_context,
                away_context,
            )
        )

    except Exception as exc:
        errors.append(
            f"CardsModel: {exc}"
        )

    return (
        corners_result,
        cards_result,
        errors,
    )


# ============================================================
# DATA QUALITY
# ============================================================

def _field_coverage(
    records: Sequence[Any],
    fields: Sequence[str],
) -> Dict[str, Any]:

    total = len(records)

    result = {
        "records": total,
        "fields": {},
    }

    for field in fields:

        available = sum(
            1
            for record in records
            if _get(record, field) is not None
        )

        result["fields"][field] = {
            "available": available,
            "missing": total - available,
        }

    return result


def _data_quality(
    home_history: Sequence[Any],
    away_history: Sequence[Any],
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    diagnostics: Dict[str, Any],
) -> Dict[str, Any]:

    history_complete = (
        len(home_history) == HISTORY_SIZE
        and len(away_history) == HISTORY_SIZE
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

    diagnostic_errors = diagnostics.get(
        "errors",
        [],
    )

    return {
        "history": {
            "required_per_team": HISTORY_SIZE,
            "home_matches": len(home_history),
            "away_matches": len(away_history),
            "status": (
                "complete"
                if history_complete
                else "partial"
            ),
        },

        "xg": {
            "home": _field_coverage(
                home_history,
                xg_fields,
            ),
            "away": _field_coverage(
                away_history,
                xg_fields,
            ),
        },

        "statistics": {
            "home": _field_coverage(
                home_history,
                statistics_fields,
            ),
            "away": _field_coverage(
                away_history,
                statistics_fields,
            ),
        },

        "diagnostics": {
            "available": (
                len(diagnostic_errors) == 0
            ),
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
# SCORE OUTPUT
# ============================================================

def _score_output(
    score_result: Any,
) -> Dict[str, Any]:

    data = _dict(score_result)

    return {
        "predicted_score": _get(
            data,
            "predicted_score",
        ),

        "most_likely_score": _get(
            data,
            "likely_score",
            "most_likely_score",
        ),

        "top_scores": _get(
            data,
            "top_scores",
        ),

        "second_score": _get(
            data,
            "second_score",
        ),

        "third_score": _get(
            data,
            "third_score",
        ),
    }


# ============================================================
# SIDE VALUES
# ============================================================

def _side_value(
    result: Any,
    *names: str,
) -> Optional[float]:

    if result is None:
        return None

    data = _dict(result)

    return _num(
        _get(
            data,
            *names,
        )
    )


# ============================================================
# MAIN BRAIN
# ============================================================

class FAJBrain:
    """
    FAJ Brain v3.0.

    Thin orchestrator.

    No duplicate mathematics.
    """

    VERSION = BRAIN_VERSION
    STATUS = BRAIN_STATUS

    def __init__(self) -> None:

        self.version = BRAIN_VERSION

        self.form_model = FormModel()
        self.goal_model = GoalModel()
        self.probability_model = ProbabilityModel()
        self.score_predictor = ScorePredictor()

        self.form_win = FormWin()
        self.defence = Defence()
        self.form_control = FormControl()
        self.form_anomaly = FormAnomaly()
        self.form_special = FormSpecial()

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

        home_form, away_form = _run_form_model(
            self.form_model,
            home_context,
            away_context,
        )

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics = _run_diagnostics(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        # ----------------------------------------------------
        # GOAL MODEL
        # ----------------------------------------------------

        goal_result = _run_goal_model(
            self.goal_model,
            home_form=home_form,
            away_form=away_form,
            home_team=home_team,
            away_team=away_team,
            home_history=home_history,
            away_history=away_history,
            diagnostics=diagnostics,
        )

        home_xg, away_xg = _goal_lambdas(
            goal_result
        )

        # ----------------------------------------------------
        # PROBABILITY MODEL
        # ----------------------------------------------------

        probability_result = (
            _run_probability_model(
                self.probability_model,
                home_xg,
                away_xg,
            )
        )

        probability_data = _dict(
            probability_result
        )

        # ----------------------------------------------------
        # SCORE PREDICTOR
        # ----------------------------------------------------

        score_result = _run_score_predictor(
            self.score_predictor,
            probability_result,
            home_xg,
            away_xg,
        )

        score_output = _score_output(
            score_result
        )

        # ----------------------------------------------------
        # PARALLEL MODELS
        # ----------------------------------------------------

        (
            corners_result,
            cards_result,
            side_errors,
        ) = _run_side_models(
            self.corners_model,
            self.cards_model,
            home_context,
            away_context,
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
            )
        )

        draw = _prob01(
            _get(
                probability_data,
                "draw",
            )
        )

        away_win = _prob01(
            _get(
                probability_data,
                "away_win",
            )
        )

        btts = _prob01(
            _get(
                probability_data,
                "btts",
            )
        )

        over15 = _prob01(
            _get(
                probability_data,
                "over_15",
                "over15",
            )
        )

        over25 = _prob01(
            _get(
                probability_data,
                "over_25",
                "over25",
            )
        )

        over35 = _prob01(
            _get(
                probability_data,
                "over_35",
                "over35",
            )
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        goal_data = _dict(
            goal_result
        )

        confidence = _prob01(
            _get(
                goal_data,
                "confidence",
            )
        )

        # ----------------------------------------------------
        # CORNERS / CARDS
        # ----------------------------------------------------

        corners_value = _side_value(
            corners_result,
            "total_expected_corners",
            "expected_corners",
            "total_corners",
        )

        cards_value = _side_value(
            cards_result,
            "total_expected_cards",
            "expected_cards",
            "total_cards",
        )

        # ----------------------------------------------------
        # QUALITY
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

        calculation_meta = {
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

            "ownership": {
                "xg": "GoalModel",
                "lambda": "GoalModel",
                "probabilities": "ProbabilityModel",
                "score_distribution": "ProbabilityModel",
                "score_ranking": "ScorePredictor",
                "corners": "CornersModel",
                "cards": "CardsModel",
            },

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

            "diagnostics": _serialize(
                diagnostics
            ),

            "math_integrity": {
                "brain_recalculates_xg": False,
                "brain_recalculates_lambda": False,
                "brain_recalculates_poisson": False,
                "brain_recalculates_1x2": False,
                "brain_recalculates_btts": False,
                "brain_recalculates_totals": False,
                "brain_reranks_scores": False,
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
                    "version",
                    "model_version",
                ),
            },
        }

        # ----------------------------------------------------
        # FINAL OUTPUT
        # ----------------------------------------------------

        return {

            # =================================================
            # MATCH
            # =================================================

            "home_team": home_team,
            "away_team": away_team,

            "home_matches": len(
                home_history
            ),

            "away_matches": len(
                away_history
            ),

            # =================================================
            # GOALS
            # =================================================

            "home_xg": home_xg,
            "away_xg": away_xg,

            # =================================================
            # 1X2
            # =================================================

            "home_win_probability": _prob100(
                home_win
            ),

            "draw_probability": _prob100(
                draw
            ),

            "away_win_probability": _prob100(
                away_win
            ),

            # =================================================
            # BTTS / TOTALS
            # =================================================

            "btts_probability": _prob100(
                btts
            ),

            "over15_probability": _prob100(
                over15
            ),

            "over25_probability": _prob100(
                over25
            ),

            "over35_probability": _prob100(
                over35
            ),

            # =================================================
            # SCORE
            # =================================================

            "predicted_score": score_output[
                "predicted_score"
            ],

            "most_likely_score": score_output[
                "most_likely_score"
            ],

            "second_score": score_output[
                "second_score"
            ],

            "third_score": score_output[
                "third_score"
            ],

            "top_scores": score_output[
                "top_scores"
            ],

            # =================================================
            # PARALLEL MODELS
            # =================================================

            "corners": corners_value,
            "cards": cards_value,

            # =================================================
            # DIAGNOSTICS
            # =================================================

            "diagnostics": _serialize(
                diagnostics
            ),

            # =================================================
            # DATA QUALITY
            # =================================================

            "data_quality": data_quality,

            # =================================================
            # CONFIDENCE
            # =================================================

            "confidence": confidence,

            # =================================================
            # NO OWNER
            # =================================================

            "risk": None,
            "conclusion": None,

            # =================================================
            # META
            # =================================================

            "calculation_meta": calculation_meta,

            "model_version": BRAIN_VERSION,

            # =================================================
            # COMPLETE ORGAN OUTPUT
            # =================================================

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

    return FAJBrain().predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_matches,
        away_matches=away_matches,
    )


# ============================================================
# END
# ============================================================
