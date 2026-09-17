#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN v4.0
============================================================

FAJ BRAIN
---------

Чистый orchestration layer нового FAJ.

КАНОНИЧЕСКАЯ ЦЕПОЧКА:

    FACTS
      │
      ▼
    FormContext
      │
      ▼
    FormModel
      │
      ▼
    GoalModel
      │
      ├── home_lambda
      └── away_lambda
              │
              ▼
       ProbabilityModel
              │
              ├── 1X2
              ├── BTTS
              ├── TOTALS
              └── score_distribution
                       │
                       ▼
                ScorePredictor
                       │
                       ├── predicted_score
                       ├── second_score
                       ├── third_score
                       └── top_scores
                       │
                       ▼
                  FINAL BRAIN


ПАРАЛЛЕЛЬНЫЕ STATE:

    FormWin
    Defence
    FormControl
    FormAnomaly
    FormSpecial
    CornersModel
    CardsModel


КРИТИЧЕСКИЙ КОНТРАКТ
--------------------

Диагностические органы:

    НЕ изменяют GoalModel
    НЕ изменяют lambda
    НЕ изменяют ProbabilityModel
    НЕ изменяют score_distribution
    НЕ изменяют ScorePredictor

То есть:

    FormWin      -> evidence
    Defence      -> evidence
    Control      -> evidence
    Anomaly      -> evidence
    SpecialForm  -> evidence
    Corners      -> separate state
    Cards        -> separate state


BRAIN НЕ:

    - считает xG самостоятельно
    - считает lambda самостоятельно
    - считает Poisson
    - пересчитывает 1X2
    - пересчитывает BTTS
    - пересчитывает totals
    - пересчитывает score probabilities
    - меняет P(score)
    - применяет Winner Override
    - применяет Form multiplier
    - применяет Control multiplier
    - применяет Defence multiplier
    - применяет Anomaly multiplier
    - применяет SpecialForm multiplier
    - применяет rating multiplier
    - обучается
    - пишет в database.py
    - использует будущий результат


MATHEMATICAL PRINCIPLE
----------------------

    FACTS
       ↓
    STATE
       ↓
    PROBABILITIES
       ↓
    SYNTHESIS

Никакого:

    Form
      ↓
    coefficient
      ↓
    xG
      ↓
    Poisson


MISSING DATA
------------

    None != 0

Если обязательный Core State отсутствует:

    Brain НЕ придумывает fallback.

Если диагностический State отсутствует:

    Core prediction НЕ ломается.

Диагностическая ошибка сохраняется
в diagnostics.


VERSION
-------

FAJ-BRAIN-4.0
CONTRACT_V1
============================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence


# ============================================================
# CORE IMPORTS
# ============================================================

from .form_context import build_form_context
from .form_model import FormModel
from .goal_model import GoalModel
from .probability_model import ProbabilityModel
from .score_predictor import ScorePredictor


# ============================================================
# OPTIONAL ANALYTICAL ORGANS
# ============================================================

try:
    from .form_win import FormWin
except Exception:
    FormWin = None


try:
    from .defence import Defence
except Exception:
    Defence = None


try:
    from .form_control import FormControl
except Exception:
    FormControl = None


try:
    from .form_anomaly import FormAnomaly
except Exception:
    FormAnomaly = None


try:
    from .special_form import FormSpecial
except Exception:
    FormSpecial = None


try:
    from .corners_model import CornersModel
except Exception:
    CornersModel = None


try:
    from .cards_model import CardsModel
except Exception:
    CardsModel = None


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-4.0"
BRAIN_STATUS = "CONTRACT_V1"

HISTORY_SIZE = 6


# ============================================================
# EXCEPTION
# ============================================================

class BrainCoreError(RuntimeError):
    """
    Mandatory FAJ Brain core stage failed.
    """

    pass


# ============================================================
# RESULT
# ============================================================

@dataclass
class BrainPrediction:
    """
    Final FAJ Brain result.

    BrainPrediction НЕ является новой математической моделью.

    Он объединяет результаты уже существующих State/Model.
    """

    version: str

    home_team: Optional[str]
    away_team: Optional[str]

    # --------------------------------------------------------
    # CORE STATES
    # --------------------------------------------------------

    home_context: Optional[Dict[str, Any]] = None
    away_context: Optional[Dict[str, Any]] = None

    home_form: Any = None
    away_form: Any = None

    goal_state: Any = None

    probability_state: Any = None

    score_state: Any = None

    # --------------------------------------------------------
    # PARALLEL STATES
    # --------------------------------------------------------

    form_win: Dict[str, Any] = field(
        default_factory=dict
    )

    defence: Dict[str, Any] = field(
        default_factory=dict
    )

    control: Dict[str, Any] = field(
        default_factory=dict
    )

    anomaly: Dict[str, Any] = field(
        default_factory=dict
    )

    special_form: Dict[str, Any] = field(
        default_factory=dict
    )

    corners_state: Any = None

    cards_state: Any = None

    # --------------------------------------------------------
    # FINAL CORE PREDICTION
    # --------------------------------------------------------

    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None

    total_lambda: Optional[float] = None

    home_win_probability: Optional[float] = None
    draw_probability: Optional[float] = None
    away_win_probability: Optional[float] = None

    btts_probability: Optional[float] = None

    over_25_probability: Optional[float] = None
    under_25_probability: Optional[float] = None

    over_35_probability: Optional[float] = None
    under_35_probability: Optional[float] = None

    predicted_score: Optional[str] = None
    second_score: Optional[str] = None
    third_score: Optional[str] = None

    predicted_score_probability: Optional[float] = None

    top_scores: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # FINAL STRUCTURAL LABELS
    # --------------------------------------------------------

    primary_outcome: Optional[str] = None

    primary_scenario: Optional[str] = None

    # --------------------------------------------------------
    # CONFIDENCE / RISK
    #
    # Пока НЕ рассчитываются искусственно.
    # --------------------------------------------------------

    confidence: Optional[float] = None
    risk: Optional[float] = None

    # --------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------

    diagnostics: Dict[str, Any] = field(
        default_factory=dict
    )

    errors: List[str] = field(
        default_factory=list
    )


# ============================================================
# GENERIC HELPERS
# ============================================================

def _get(
    obj: Any,
    *names: str,
) -> Any:
    """
    Read value from:

        dict
        Mapping
        sqlite3.Row-like object
        dataclass/object
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

        except (
            AttributeError,
            TypeError,
        ):
            pass

        try:

            return getattr(
                obj,
                name,
            )

        except AttributeError:

            pass

    return None


def _dict(
    obj: Any,
) -> Dict[str, Any]:
    """
    Convert State/Model result to dict.

    Does not invent values.
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

    to_dict = getattr(
        obj,
        "to_dict",
        None,
    )

    if callable(to_dict):

        try:

            result = to_dict()

            if isinstance(
                result,
                Mapping,
            ):
                return dict(result)

        except Exception:
            pass

    try:

        return dict(
            vars(obj)
        )

    except Exception:

        return {}


def _serialize(
    obj: Any,
) -> Any:
    """
    Recursive serialization for final diagnostics/output.
    """

    if obj is None:
        return None

    if isinstance(
        obj,
        Mapping,
    ):
        return {
            key: _serialize(value)
            for key, value in obj.items()
        }

    if isinstance(
        obj,
        (list, tuple),
    ):
        return [
            _serialize(value)
            for value in obj
        ]

    if is_dataclass(obj):

        try:
            return _serialize(
                asdict(obj)
            )

        except Exception:
            pass

    to_dict = getattr(
        obj,
        "to_dict",
        None,
    )

    if callable(to_dict):

        try:
            return _serialize(
                to_dict()
            )

        except Exception:
            pass

    return obj


def _num(
    value: Any,
) -> Optional[float]:
    """
    Safe numeric conversion.

    Missing stays None.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:

        result = float(value)

    except (
        TypeError,
        ValueError,
    ):

        return None

    if not math.isfinite(result):
        return None

    return result


def _prob(
    value: Any,
) -> Optional[float]:
    """
    Read an already calculated probability.

    This function does NOT calculate probability.

    Supports:

        0.42
        42
    """

    number = _num(value)

    if number is None:
        return None

    if number > 1.0:
        number /= 100.0

    if number < 0.0:
        return None

    if number > 1.0:
        return None

    return number


# ============================================================
# HISTORY
# ============================================================

def _normalize_record(
    record: Any,
) -> Dict[str, Any]:
    """
    Convert historical record to dict.
    """

    if isinstance(
        record,
        Mapping,
    ):
        return dict(record)

    if is_dataclass(record):

        try:
            return asdict(record)

        except Exception:
            pass

    to_dict = getattr(
        record,
        "to_dict",
        None,
    )

    if callable(to_dict):

        result = to_dict()

        if isinstance(
            result,
            Mapping,
        ):
            return dict(result)

    try:

        keys = record.keys()

        return {
            key: record[key]
            for key in keys
        }

    except (
        AttributeError,
        TypeError,
    ):
        pass

    try:

        return dict(
            vars(record)
        )

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
    matches: Sequence[Any],
    team_name: str,
) -> List[Any]:
    """
    Brain expects N <= 6.

    Predictor/FormContext is responsible for selecting
    the historical window and preserving oldest -> newest.

    Brain never fabricates a missing match.

    N may be 1..6.

    Core GoalModel itself determines whether enough
    xG observations exist for lambda.
    """

    if matches is None:

        raise BrainCoreError(
            f"{team_name}: history is missing"
        )

    try:

        values = list(matches)

    except TypeError as exc:

        raise BrainCoreError(
            f"{team_name}: invalid history"
        ) from exc

    if not values:

        raise BrainCoreError(
            f"{team_name}: empty history"
        )

    if len(values) > HISTORY_SIZE:

        values = values[
            -HISTORY_SIZE:
        ]

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
    """

    records = _normalize_history(
        history
    )

    try:

        context = build_form_context(
            team_name=team_name,
            records=records,
        )

    except Exception as exc:

        raise BrainCoreError(
            f"FormContext failed for {team_name}"
        ) from exc

    result = _dict(
        context
    )

    if not result:

        raise BrainCoreError(
            f"FormContext returned empty state "
            f"for {team_name}"
        )

    return result


# ============================================================
# FORM MODEL
# ============================================================

def _run_form_model(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any]:
    """
    FormModel remains diagnostic.

    It does not directly alter GoalModel.
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

    if home_form is None:

        raise BrainCoreError(
            "FormModel returned None for home"
        )

    if away_form is None:

        raise BrainCoreError(
            "FormModel returned None for away"
        )

    return (
        home_form,
        away_form,
    )


# ============================================================
# GOAL MODEL
# ============================================================

def _run_goal_model(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Any:
    """
    GoalModel owns xG/lambda mathematics.

    Brain does NOT calculate lambda.
    """

    model = GoalModel()

    try:

        result = model.calculate(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
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


# ============================================================
# EXTRACT GOAL STATE
# ============================================================

def _extract_lambdas(
    goal_state: Any,
) -> tuple[
    Optional[float],
    Optional[float],
]:
    """
    Extract lambda owned by GoalModel.

    No recalculation.
    """

    data = _dict(
        goal_state
    )

    home_lambda = _num(
        _get(
            data,
            "home_lambda",
            "lambda_home",
        )
    )

    away_lambda = _num(
        _get(
            data,
            "away_lambda",
            "lambda_away",
        )
    )

    return (
        home_lambda,
        away_lambda,
    )


# ============================================================
# PROBABILITY MODEL
# ============================================================

def _run_probability_model(
    home_lambda: Optional[float],
    away_lambda: Optional[float],
) -> Any:
    """
    ProbabilityModel is the only probability mathematics
    in the Brain core.
    """

    model = ProbabilityModel()

    try:

        result = model.calculate(
            home_lambda=home_lambda,
            away_lambda=away_lambda,
        )

    except Exception as exc:

        raise BrainCoreError(
            "ProbabilityModel failed"
        ) from exc

    if result is None:

        raise BrainCoreError(
            "ProbabilityModel returned None"
        )

    return result


# ============================================================
# SCORE PREDICTOR
# ============================================================

def _run_score_predictor(
    probability_state: Any,
    home_lambda: Optional[float],
    away_lambda: Optional[float],
) -> Any:
    """
    ScorePredictor receives the score distribution.

    It does not calculate Poisson.
    """

    probability_data = _dict(
        probability_state
    )

    score_distribution = _get(
        probability_data,
        "score_distribution",
    )

    predictor = ScorePredictor()

    try:

        result = predictor.predict(
            score_probabilities=score_distribution,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            probability_result=probability_state,
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
# DIAGNOSTIC ORGAN HELPERS
# ============================================================

def _run_optional(
    name: str,
    constructor: Any,
    calls: Sequence[Dict[str, Any]],
    errors: List[str],
) -> Any:
    """
    Run an analytical organ without allowing it
    to contaminate Core mathematics.

    The function supports several public method names
    used by the current FAJ organs:

        analyze
        calculate
        compare
        predict

    No fallback numeric value is generated.
    """

    if constructor is None:

        errors.append(
            f"{name}: MODULE_UNAVAILABLE"
        )

        return None

    try:

        instance = constructor()

    except Exception as exc:

        errors.append(
            f"{name}: INIT_FAILED: {exc}"
        )

        return None

    methods = (
        "analyze",
        "calculate",
        "compare",
        "predict",
    )

    method = None

    for method_name in methods:

        candidate = getattr(
            instance,
            method_name,
            None,
        )

        if callable(candidate):

            method = candidate
            break

    if method is None:

        errors.append(
            f"{name}: NO_SUPPORTED_PUBLIC_METHOD"
        )

        return None

    last_error: Optional[Exception] = None

    for kwargs in calls:

        try:

            return method(
                **kwargs
            )

        except TypeError as exc:

            last_error = exc

            continue

        except Exception as exc:

            errors.append(
                f"{name}: {exc}"
            )

            return None

    if last_error is not None:

        errors.append(
            f"{name}: {last_error}"
        )

    return None


# ============================================================
# PARALLEL DIAGNOSTICS
# ============================================================

def _run_parallel_states(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Dict[str, Any]:
    """
    Run analytical organs independently.

    IMPORTANT:

    These states are observational.

    They do not feed back into:
        GoalModel
        ProbabilityModel
        ScorePredictor
    """

    errors: List[str] = []

    result: Dict[str, Any] = {

        "form_win": {
            "home": None,
            "away": None,
        },

        "defence": {
            "home": None,
            "away": None,
        },

        "control": {
            "home": None,
            "away": None,
        },

        "anomaly": {
            "home": None,
            "away": None,
        },

        "special_form": {
            "home": None,
            "away": None,
        },

        "corners": None,

        "cards": None,

        "errors": errors,

        "contract": {
            "changes_lambda": False,
            "changes_probability": False,
            "changes_score_distribution": False,
            "changes_score_ranking": False,
        },
    }

    # --------------------------------------------------------
    # FORM WIN
    # --------------------------------------------------------

    result["form_win"]["home"] = _run_optional(
        "FormWin.home",
        FormWin,
        [
            {
                "form_context": home_context,
                "next_venue": "home",
            },
            {
                "context": home_context,
                "next_venue": "home",
            },
        ],
        errors,
    )

    result["form_win"]["away"] = _run_optional(
        "FormWin.away",
        FormWin,
        [
            {
                "form_context": away_context,
                "next_venue": "away",
            },
            {
                "context": away_context,
                "next_venue": "away",
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # DEFENCE
    # --------------------------------------------------------

    result["defence"]["home"] = _run_optional(
        "Defence.home",
        Defence,
        [
            {
                "context": home_context,
                "team_name": home_team,
            },
            {
                "form_context": home_context,
                "team_name": home_team,
            },
        ],
        errors,
    )

    result["defence"]["away"] = _run_optional(
        "Defence.away",
        Defence,
        [
            {
                "context": away_context,
                "team_name": away_team,
            },
            {
                "form_context": away_context,
                "team_name": away_team,
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # CONTROL
    # --------------------------------------------------------

    result["control"]["home"] = _run_optional(
        "FormControl.home",
        FormControl,
        [
            {
                "context": home_context,
                "target_team": home_team,
                "opponent_team": away_team,
                "venue": "home",
            },
            {
                "form_context": home_context,
                "target_team": home_team,
                "opponent_team": away_team,
                "venue": "home",
            },
        ],
        errors,
    )

    result["control"]["away"] = _run_optional(
        "FormControl.away",
        FormControl,
        [
            {
                "context": away_context,
                "target_team": away_team,
                "opponent_team": home_team,
                "venue": "away",
            },
            {
                "form_context": away_context,
                "target_team": away_team,
                "opponent_team": home_team,
                "venue": "away",
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # ANOMALY
    # --------------------------------------------------------

    result["anomaly"]["home"] = _run_optional(
        "FormAnomaly.home",
        FormAnomaly,
        [
            {
                "context": home_context,
            },
            {
                "form_context": home_context,
            },
        ],
        errors,
    )

    result["anomaly"]["away"] = _run_optional(
        "FormAnomaly.away",
        FormAnomaly,
        [
            {
                "context": away_context,
            },
            {
                "form_context": away_context,
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # SPECIAL FORM
    # --------------------------------------------------------

    result["special_form"]["home"] = _run_optional(
        "FormSpecial.home",
        FormSpecial,
        [
            {
                "context": home_context,
                "team_name": home_team,
            },
            {
                "form_context": home_context,
                "team_name": home_team,
            },
        ],
        errors,
    )

    result["special_form"]["away"] = _run_optional(
        "FormSpecial.away",
        FormSpecial,
        [
            {
                "context": away_context,
                "team_name": away_team,
            },
            {
                "form_context": away_context,
                "team_name": away_team,
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    result["corners"] = _run_optional(
        "CornersModel",
        CornersModel,
        [
            {
                "home_context": home_context,
                "away_context": away_context,
                "home_team": home_team,
                "away_team": away_team,
            },
            {
                "home_context": home_context,
                "away_context": away_context,
            },
        ],
        errors,
    )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    result["cards"] = _run_optional(
        "CardsModel",
        CardsModel,
        [
            {
                "home_context": home_context,
                "away_context": away_context,
                "home_team": home_team,
                "away_team": away_team,
            },
            {
                "home_context": home_context,
                "away_context": away_context,
            },
        ],
        errors,
    )

    return result


# ============================================================
# CORE PROBABILITIES
# ============================================================

def _extract_probability(
    probability_state: Any,
    field_name: str,
) -> Optional[float]:
    """
    Extract probability already calculated by ProbabilityModel.
    """

    data = _dict(
        probability_state
    )

    return _prob(
        _get(
            data,
            field_name,
        )
    )


# ============================================================
# PRIMARY OUTCOME
# ============================================================

def _primary_outcome(
    home_probability: Optional[float],
    draw_probability: Optional[float],
    away_probability: Optional[float],
) -> Optional[str]:
    """
    Primary outcome is simply the maximum of the three
    probabilities already calculated by ProbabilityModel.

    It is NOT a new WinnerModel.

    No adjustment.
    No override.
    """

    values = {
        "HOME": home_probability,
        "DRAW": draw_probability,
        "AWAY": away_probability,
    }

    available = {
        key: value
        for key, value in values.items()
        if value is not None
    }

    if not available:
        return None

    return max(
        available,
        key=available.get,
    )


# ============================================================
# PRIMARY SCENARIO
# ============================================================

def _primary_scenario(
    score_state: Any,
) -> Optional[str]:
    """
    Scenario is taken from the top exact score.

    No secondary state can alter it.
    """

    data = _dict(
        score_state
    )

    score = _get(
        data,
        "predicted_score",
        "likely_score",
    )

    if score is None:
        return None

    return str(score)


# ============================================================
# DATA QUALITY
# ============================================================

def _core_quality(
    goal_state: Any,
    probability_state: Any,
    score_state: Any,
) -> Optional[float]:
    """
    Descriptive Core availability.

    This is NOT confidence.

    1.0 means all three core layers returned usable state.
    """

    goal_data = _dict(
        goal_state
    )

    probability_data = _dict(
        probability_state
    )

    score_data = _dict(
        score_state
    )

    checks = [

        _num(
            _get(
                goal_data,
                "home_lambda",
            )
        ) is not None,

        _num(
            _get(
                goal_data,
                "away_lambda",
            )
        ) is not None,

        _get(
            probability_data,
            "score_distribution",
        ) not in (
            None,
            {},
        ),

        _get(
            score_data,
            "predicted_score",
            "likely_score",
        ) is not None,
    ]

    if not checks:
        return None

    return (
        sum(
            1
            for value in checks
            if value
        )
        / len(checks)
    )


# ============================================================
# FINAL BRAIN
# ============================================================

class FAJBrain:
    """
    FAJ Brain v4.0.

    Главная задача:

        собрать существующие математические органы
        в одну чистую предматчевую цепочку.

    Brain не является дополнительной математической моделью.
    """

    VERSION = BRAIN_VERSION
    STATUS = BRAIN_STATUS

    # ========================================================
    # PREDICT
    # ========================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
    ) -> BrainPrediction:
        """
        Main FAJ prediction.

        Parameters
        ----------

        home_team:
            Home team name.

        away_team:
            Away team name.

        home_history:
            Historical matches oldest -> newest.

        away_history:
            Historical matches oldest -> newest.

        N:
            1..6 accepted.

        The Brain never invents missing matches.
        """

        errors: List[str] = []

        # ----------------------------------------------------
        # Validate history
        # ----------------------------------------------------

        home_history = _history(
            home_history,
            home_team,
        )

        away_history = _history(
            away_history,
            away_team,
        )

        # ----------------------------------------------------
        # 1. FORM CONTEXT
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
        # 2. FORM MODEL
        #
        # Diagnostic state.
        # ----------------------------------------------------

        home_form, away_form = (
            _run_form_model(
                home_context,
                away_context,
            )
        )

        # ----------------------------------------------------
        # 3. PARALLEL STATES
        #
        # IMPORTANT:
        #
        # Run BEFORE final synthesis,
        # but NEVER feed them back into Core.
        # ----------------------------------------------------

        parallel = _run_parallel_states(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        errors.extend(
            parallel.get(
                "errors",
                [],
            )
        )

        # ----------------------------------------------------
        # 4. GOAL STATE
        #
        # Sole owner of lambda.
        # ----------------------------------------------------

        goal_state = _run_goal_model(
            home_context=home_context,
            away_context=away_context,
            home_team=home_team,
            away_team=away_team,
        )

        (
            home_lambda,
            away_lambda,
        ) = _extract_lambdas(
            goal_state
        )

        total_lambda = None

        if (
            home_lambda is not None
            and away_lambda is not None
        ):
            total_lambda = (
                home_lambda
                + away_lambda
            )

        # ----------------------------------------------------
        # 5. PROBABILITY STATE
        #
        # Sole owner of Poisson probabilities.
        # ----------------------------------------------------

        probability_state = (
            _run_probability_model(
                home_lambda=home_lambda,
                away_lambda=away_lambda,
            )
        )

        # ----------------------------------------------------
        # 6. SCORE STATE
        #
        # Sole ranking layer.
        # ----------------------------------------------------

        score_state = _run_score_predictor(
            probability_state=probability_state,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
        )

        # ----------------------------------------------------
        # 7. EXTRACT FINAL CORE PROBABILITIES
        # ----------------------------------------------------

        home_win_probability = (
            _extract_probability(
                probability_state,
                "home_win",
            )
        )

        draw_probability = (
            _extract_probability(
                probability_state,
                "draw",
            )
        )

        away_win_probability = (
            _extract_probability(
                probability_state,
                "away_win",
            )
        )

        btts_probability = (
            _extract_probability(
                probability_state,
                "btts",
            )
        )

        over_25_probability = (
            _extract_probability(
                probability_state,
                "over_25",
            )
        )

        under_25_probability = (
            _extract_probability(
                probability_state,
                "under_25",
            )
        )

        over_35_probability = (
            _extract_probability(
                probability_state,
                "over_35",
            )
        )

        under_35_probability = (
            _extract_probability(
                probability_state,
                "under_35",
            )
        )

        # ----------------------------------------------------
        # 8. SCORE OUTPUT
        # ----------------------------------------------------

        score_data = _dict(
            score_state
        )

        predicted_score = _get(
            score_data,
            "predicted_score",
            "likely_score",
        )

        second_score = _get(
            score_data,
            "second_score",
        )

        third_score = _get(
            score_data,
            "third_score",
        )

        predicted_score_probability = _num(
            _get(
                score_data,
                "probability_score",
                "primary_score_value",
            )
        )

        top_scores = _get(
            score_data,
            "top_scores",
        )

        if not isinstance(
            top_scores,
            list,
        ):
            top_scores = []

        # ----------------------------------------------------
        # 9. PRIMARY OUTCOME
        # ----------------------------------------------------

        primary_outcome = _primary_outcome(
            home_probability=home_win_probability,
            draw_probability=draw_probability,
            away_probability=away_win_probability,
        )

        # ----------------------------------------------------
        # 10. PRIMARY SCORE SCENARIO
        # ----------------------------------------------------

        primary_scenario = _primary_scenario(
            score_state
        )

        # ----------------------------------------------------
        # 11. CORE QUALITY
        #
        # NOT confidence.
        # ----------------------------------------------------

        core_quality = _core_quality(
            goal_state=goal_state,
            probability_state=probability_state,
            score_state=score_state,
        )

        # ----------------------------------------------------
        # 12. FINAL DIAGNOSTICS
        # ----------------------------------------------------

        diagnostics = {

            "brain_version":
                BRAIN_VERSION,

            "brain_status":
                BRAIN_STATUS,

            "formula_status":
                "CONTRACT_V1",

            # ------------------------------------------------
            # Canonical chain
            # ------------------------------------------------

            "chain": [
                "FACTS",
                "FormContext",
                "FormModel",
                "GoalModel",
                "ProbabilityModel",
                "ScorePredictor",
                "FINAL_BRAIN",
            ],

            # ------------------------------------------------
            # Parallel states
            # ------------------------------------------------

            "parallel_states": [
                "FormWin",
                "Defence",
                "FormControl",
                "FormAnomaly",
                "FormSpecial",
                "CornersModel",
                "CardsModel",
            ],

            # ------------------------------------------------
            # Ownership
            # ------------------------------------------------

            "lambda_owner":
                "GoalModel",

            "probability_owner":
                "ProbabilityModel",

            "score_distribution_owner":
                "ProbabilityModel",

            "score_ranking_owner":
                "ScorePredictor",

            # ------------------------------------------------
            # Forbidden feedback
            # ------------------------------------------------

            "diagnostic_feedback_to_goal":
                False,

            "diagnostic_feedback_to_probability":
                False,

            "diagnostic_feedback_to_score":
                False,

            "winner_override":
                False,

            "rating_multiplier":
                False,

            "form_multiplier":
                False,

            "control_multiplier":
                False,

            "defence_multiplier":
                False,

            "anomaly_multiplier":
                False,

            "special_multiplier":
                False,

            "finishing_bonus":
                False,

            "low_score_correction":
                False,

            # ------------------------------------------------
            # Learning / DB
            # ------------------------------------------------

            "learning":
                False,

            "database_write":
                False,

            "future_result_used":
                False,

            "bookmaker_odds_used":
                False,

            # ------------------------------------------------
            # Data quality
            # ------------------------------------------------

            "core_data_quality":
                core_quality,

            "home_history_size":
                len(home_history),

            "away_history_size":
                len(away_history),

            "missing_is_zero":
                False,

            # ------------------------------------------------
            # Confidence / risk
            # ------------------------------------------------

            "confidence_calculated":
                False,

            "risk_calculated":
                False,

            "reason_confidence_none":
                (
                    "Confidence State coefficients are "
                    "not defined/calibrated in Brain v4.0"
                ),

            "reason_risk_none":
                (
                    "Risk State decomposition is "
                    "not yet calculated by Brain"
                ),
        }

        # ----------------------------------------------------
        # Add parallel contract
        # ----------------------------------------------------

        diagnostics[
            "parallel_contract"
        ] = parallel.get(
            "contract",
            {},
        )

        # ----------------------------------------------------
        # FINAL OBJECT
        # ----------------------------------------------------

        return BrainPrediction(

            version=BRAIN_VERSION,

            home_team=home_team,
            away_team=away_team,

            home_context=home_context,
            away_context=away_context,

            home_form=home_form,
            away_form=away_form,

            goal_state=goal_state,

            probability_state=probability_state,

            score_state=score_state,

            form_win=parallel[
                "form_win"
            ],

            defence=parallel[
                "defence"
            ],

            control=parallel[
                "control"
            ],

            anomaly=parallel[
                "anomaly"
            ],

            special_form=parallel[
                "special_form"
            ],

            corners_state=parallel[
                "corners"
            ],

            cards_state=parallel[
                "cards"
            ],

            home_lambda=home_lambda,
            away_lambda=away_lambda,

            total_lambda=total_lambda,

            home_win_probability=
                home_win_probability,

            draw_probability=
                draw_probability,

            away_win_probability=
                away_win_probability,

            btts_probability=
                btts_probability,

            over_25_probability=
                over_25_probability,

            under_25_probability=
                under_25_probability,

            over_35_probability=
                over_35_probability,

            under_35_probability=
                under_35_probability,

            predicted_score=
                predicted_score,

            second_score=
                second_score,

            third_score=
                third_score,

            predicted_score_probability=
                predicted_score_probability,

            top_scores=top_scores,

            primary_outcome=
                primary_outcome,

            primary_scenario=
                primary_scenario,

            # ------------------------------------------------
            # НЕ придумываем confidence/risk.
            # ------------------------------------------------

            confidence=None,
            risk=None,

            diagnostics=diagnostics,

            errors=errors,
        )


# ============================================================
# MODULE-LEVEL API
# ============================================================

def predict(
    home_team: str,
    away_team: str,
    home_history: Sequence[Any],
    away_history: Sequence[Any],
) -> BrainPrediction:
    """
    Convenience API.
    """

    return FAJBrain().predict(
        home_team=home_team,
        away_team=away_team,
        home_history=home_history,
        away_history=away_history,
    )


def predict_match(
    home_team: str,
    away_team: str,
    home_history: Sequence[Any],
    away_history: Sequence[Any],
) -> BrainPrediction:
    """
    Compatibility alias.
    """

    return predict(
        home_team=home_team,
        away_team=away_team,
        home_history=home_history,
        away_history=away_history,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "BRAIN_VERSION",
    "BRAIN_STATUS",
    "HISTORY_SIZE",
    "BrainCoreError",
    "BrainPrediction",
    "FAJBrain",
    "predict",
    "predict_match",
]
