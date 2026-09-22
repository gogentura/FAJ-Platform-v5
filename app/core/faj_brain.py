#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN v4.2
============================================================

Чистый orchestration layer FAJ.

КАНОНИЧЕСКАЯ ЦЕПОЧКА:

    FACTS
      ->
    FormContext
      ->
    FormModel
      ->
    GoalModel
      ->
    λ Home / λ Away
      ->
    RatingReconciliation
      ->
    λ Home / λ Away
      ->
    ProbabilityModel
      ->
    ScorePredictor
      ->
    FINAL BRAIN

RATING RECONCILIATION:

    Club Rating + Pair Rating
             ->
       RatingReconciliation
             ->
       redistribution of λ
             ->
       ProbabilityModel

ВАЖНО:

- GoalModel остаётся владельцем исходных λ.
- RatingReconciliation НЕ считает xG.
- RatingReconciliation НЕ меняет общий scoring mass.
- RatingReconciliation только перераспределяет λ между Home/Away.
- ProbabilityModel получает уже согласованные λ.
- ScorePredictor получает результат ProbabilityModel.
- WinnerState не влияет на core.
- Parallel State не влияет на core.
- Нет Winner Override.
- Нет rating multiplier.
- Нет обучения.
- Нет записи в database.py.
- Нет использования будущего результата.

MISSING DATA:

    None != 0

Если Club Rating отсутствует, используется Pair Rating.
Если Pair Rating отсутствует, используется Club Rating.
Если отсутствуют оба источника, λ остаются исходными GoalModel.

RATING RECONCILIATION v1.0:

    ClubGap = ClubHome - ClubAway
    PairGap  = PairHome - PairAway

    R = 0.50 * ClubGap + 0.50 * PairGap

    S = tanh(R / 15.0)

    B = λH0 / (λH0 + λA0)

    B' = clamp(B + 0.15 * S, 0.20, 0.80)

    λH = T * B'
    λA = T * (1 - B')

where:

    T = λH0 + λA0

VERSION
-------
FAJ-BRAIN-4.2
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
# RATING IMPORTS
# ============================================================

from .pair_rating import calculate_pair_rating

from .rating_reconciliation import (
    reconcile_ratings,
    reconcile_lambda,
)


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
    from .form_control import FormControl, compare_control
except Exception:
    FormControl = None
    compare_control = None

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

try:
    from .winner_state import WinnerStateBuilder
except Exception:
    WinnerStateBuilder = None


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-4.2"
BRAIN_STATUS = "CONTRACT_V1"

HISTORY_SIZE = 6


# ============================================================
# EXCEPTION
# ============================================================

class BrainCoreError(RuntimeError):
    """Mandatory FAJ Brain core stage failed."""
    pass


# ============================================================
# RESULT
# ============================================================

@dataclass
class BrainPrediction:
    """
    Final FAJ Brain result.

    BrainPrediction не содержит собственной новой математики.
    Он объединяет результаты существующих State/Model.
    """

    version: str

    home_team: Optional[str]
    away_team: Optional[str]

    home_context: Optional[Dict[str, Any]] = None
    away_context: Optional[Dict[str, Any]] = None

    home_form: Any = None
    away_form: Any = None

    goal_state: Any = None
    probability_state: Any = None
    score_state: Any = None

    form_win: Dict[str, Any] = field(default_factory=dict)
    defence: Dict[str, Any] = field(default_factory=dict)
    control: Dict[str, Any] = field(default_factory=dict)
    anomaly: Dict[str, Any] = field(default_factory=dict)
    special_form: Dict[str, Any] = field(default_factory=dict)

    corners_state: Any = None
    cards_state: Any = None

    # --------------------------------------------------------
    # WINNER STATE (display-only)
    # --------------------------------------------------------

    winner_state: Optional[Dict[str, Any]] = None

    # --------------------------------------------------------
    # RATING RECONCILIATION
    # --------------------------------------------------------

    rating_reconciliation: Optional[Dict[str, Any]] = None
    lambda_reconciliation: Optional[Dict[str, Any]] = None

    # --------------------------------------------------------
    # CORE λ
    # --------------------------------------------------------

    home_lambda: Optional[float] = None
    away_lambda: Optional[float] = None
    total_lambda: Optional[float] = None

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    home_win_probability: Optional[float] = None
    draw_probability: Optional[float] = None
    away_win_probability: Optional[float] = None

    # --------------------------------------------------------
    # GOAL MARKETS
    # --------------------------------------------------------

    btts_probability: Optional[float] = None

    over_25_probability: Optional[float] = None
    under_25_probability: Optional[float] = None
    over_35_probability: Optional[float] = None
    under_35_probability: Optional[float] = None

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    predicted_score: Optional[str] = None
    second_score: Optional[str] = None
    third_score: Optional[str] = None

    predicted_score_probability: Optional[float] = None

    top_scores: List[Dict[str, Any]] = field(default_factory=list)

    # --------------------------------------------------------
    # FINAL LABELS
    # --------------------------------------------------------

    primary_outcome: Optional[str] = None
    primary_scenario: Optional[str] = None

    confidence: Optional[float] = None
    risk: Optional[float] = None

    diagnostics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ============================================================
# GENERIC HELPERS
# ============================================================

def _get(obj: Any, *names: str) -> Any:

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
        try:
            return _serialize(asdict(obj))
        except Exception:
            pass

    to_dict = getattr(obj, "to_dict", None)

    if callable(to_dict):
        try:
            return _serialize(to_dict())
        except Exception:
            pass

    return obj


def _num(value: Any) -> Optional[float]:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _prob(value: Any) -> Optional[float]:

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

def _normalize_record(record: Any) -> Dict[str, Any]:

    if isinstance(record, Mapping):
        return dict(record)

    if is_dataclass(record):
        try:
            return asdict(record)
        except Exception:
            pass

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
    matches: Sequence[Any],
    team_name: str,
) -> List[Any]:

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
        values = values[-HISTORY_SIZE:]

    return values


# ============================================================
# FORM CONTEXT
# ============================================================

def _build_context(
    team_name: str,
    history: Sequence[Any],
) -> Dict[str, Any]:

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
            f"FormContext returned empty state for {team_name}"
        )

    return result


# ============================================================
# FORM MODEL
# ============================================================

def _run_form_model(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> tuple[Any, Any]:

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

    return home_form, away_form


# ============================================================
# GOAL MODEL
# ============================================================

def _run_goal_model(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> Any:

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


def _extract_lambdas(
    goal_state: Any,
) -> tuple[Optional[float], Optional[float]]:

    data = _dict(goal_state)

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

    return home_lambda, away_lambda


# ============================================================
# RATING RECONCILIATION
# ============================================================

def _build_rating_reconciliation(
    *,
    home_team: str,
    away_team: str,
    home_rating: Optional[float],
    away_rating: Optional[float],
    pair_home_rating: Optional[float],
    pair_away_rating: Optional[float],
) -> Any:
    """
    Builds the Club Rating + Pair Rating reconciliation state.

    Club Rating:
        objective / seasonal / club-level strength

    Pair Rating:
        manual / match-specific context

    The reconciliation organ combines the two signals.
    """

    pair = None

    if (
        pair_home_rating is not None
        and pair_away_rating is not None
    ):
        try:
            pair = calculate_pair_rating(
                home_rating=pair_home_rating,
                away_rating=pair_away_rating,
                home_team=home_team,
                away_team=away_team,
            )
        except Exception as exc:
            raise BrainCoreError(
                "PairRating calculation failed"
            ) from exc

    try:
        reconciliation = reconcile_ratings(
            home_team=home_team,
            away_team=away_team,
            club_home_rating=home_rating,
            club_away_rating=away_rating,
            pair_home_rating=pair_home_rating,
            pair_away_rating=pair_away_rating,
        )

    except Exception as exc:
        raise BrainCoreError(
            "RatingReconciliation failed"
        ) from exc

    return pair, reconciliation


def _run_lambda_reconciliation(
    *,
    lambda_home: Optional[float],
    lambda_away: Optional[float],
    reconciliation: Any,
) -> Any:
    """
    Applies RatingReconciliation to GoalModel λ.

    IMPORTANT:

        GoalModel owns λ before reconciliation.

        RatingReconciliation only redistributes
        the existing total scoring mass.

        T = λH0 + λA0

        T_after == T_before
    """

    if lambda_home is None or lambda_away is None:
        raise BrainCoreError(
            "Cannot reconcile lambda: GoalModel lambda is missing"
        )

    signal = _num(
        _get(
            reconciliation,
            "reconciled_signal",
        )
    )

    try:
        result = reconcile_lambda(
            lambda_home=lambda_home,
            lambda_away=lambda_away,
            reconciled_signal=signal,
        )

    except Exception as exc:
        raise BrainCoreError(
            "LambdaReconciliation failed"
        ) from exc

    if result is None:
        raise BrainCoreError(
            "LambdaReconciliation returned None"
        )

    return result


def _serialize_rating_state(
    state: Any,
) -> Optional[Dict[str, Any]]:

    if state is None:
        return None

    result = _serialize(state)

    if isinstance(result, dict):
        return result

    return None


def _serialize_lambda_reconciliation(
    state: Any,
) -> Optional[Dict[str, Any]]:

    if state is None:
        return None

    result = _serialize(state)

    if isinstance(result, dict):
        return result

    return None


# ============================================================
# PROBABILITY MODEL
# ============================================================

def _run_probability_model(
    home_lambda: Optional[float],
    away_lambda: Optional[float],
) -> Any:

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

    probability_data = _dict(probability_state)

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
# ORGAN ERROR HELPER
# ============================================================

def _record_organ_error(
    errors: List[str],
    name: str,
    exc: Exception,
) -> None:

    errors.append(
        f"{name}: {type(exc).__name__}: {exc}"
    )


# ============================================================
# FORMWIN
# ============================================================

def _run_form_win(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
    errors: List[str],
) -> Dict[str, Any]:

    if FormWin is None:
        errors.append(
            "FormWin: MODULE_UNAVAILABLE"
        )
        return {}

    try:
        model = FormWin()

        home_state = model.calculate(
            home_context,
            team_name=home_team,
        )

        away_state = model.calculate(
            away_context,
            team_name=away_team,
        )

        result = {
            "home": _serialize(home_state),
            "away": _serialize(away_state),
        }

        compare_method = getattr(
            model,
            "compare",
            None,
        )

        if callable(compare_method):

            comparison = compare_method(
                home_context,
                away_context,
                home_team=home_team,
                away_team=away_team,
            )

            result["comparison"] = _serialize(
                comparison
            )

        return result

    except Exception as exc:
        _record_organ_error(
            errors,
            "FormWin",
            exc,
        )
        return {}


# ============================================================
# DEFENCE
# ============================================================

def _run_defence(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
    errors: List[str],
) -> Dict[str, Any]:

    if Defence is None:
        errors.append(
            "Defence: MODULE_UNAVAILABLE"
        )
        return {}

    try:
        model = Defence()

        comparison = model.compare(
            home_context,
            away_context,
            home_team=home_team,
            away_team=away_team,
        )

        return {
            "home": _serialize(
                comparison.home_state
            ),
            "away": _serialize(
                comparison.away_state
            ),
            "comparison": {
                "relative_defence_advantage":
                    comparison.relative_defence_advantage,

                "relative_creation":
                    comparison.relative_creation,

                "relative_process":
                    comparison.relative_process,

                "relative_control":
                    comparison.relative_control,

                "relative_outcome":
                    comparison.relative_outcome,

                "relative_momentum":
                    comparison.relative_momentum,
            },
        }

    except Exception as exc:
        _record_organ_error(
            errors,
            "Defence",
            exc,
        )
        return {}


# ============================================================
# FORM CONTROL
# ============================================================

def _run_form_control(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
    errors: List[str],
) -> Dict[str, Any]:

    if (
        FormControl is None
        or compare_control is None
    ):
        errors.append(
            "FormControl: MODULE_UNAVAILABLE"
        )
        return {}

    try:
        comparison = compare_control(
            home_context,
            away_context,
            home_team=home_team,
            away_team=away_team,
        )

        return {
            "home": comparison.get(
                "home_control"
            ),
            "away": comparison.get(
                "away_control"
            ),
            "comparison": {
                "relative_control":
                    comparison.get(
                        "relative_control"
                    ),
            },
        }

    except Exception as exc:
        _record_organ_error(
            errors,
            "FormControl",
            exc,
        )
        return {}


# ============================================================
# FORM ANOMALY
# ============================================================

def _run_form_anomaly(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    errors: List[str],
) -> Dict[str, Any]:

    if FormAnomaly is None:
        errors.append(
            "FormAnomaly: MODULE_UNAVAILABLE"
        )
        return {}

    try:
        model = FormAnomaly()

        home_state = model.analyze(
            home_context
        )

        away_state = model.analyze(
            away_context
        )

        return {
            "home": _serialize(home_state),
            "away": _serialize(away_state),
        }

    except Exception as exc:
        _record_organ_error(
            errors,
            "FormAnomaly",
            exc,
        )
        return {}


# ============================================================
# FORM SPECIAL
# ============================================================

def _run_form_special(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    home_team: str,
    away_team: str,
    errors: List[str],
) -> Dict[str, Any]:

    if FormSpecial is None:
        errors.append(
            "FormSpecial: MODULE_UNAVAILABLE"
        )
        return {}

    try:
        model = FormSpecial()

        comparison = model.compare(
            home_context,
            away_context,
            home_team=home_team,
            away_team=away_team,
        )

        return {
            "home": _serialize(
                comparison.get("home")
            ),
            "away": _serialize(
                comparison.get("away")
            ),
            "comparison": {
                "differential":
                    comparison.get(
                        "differential"
                    ),
            },
        }

    except Exception as exc:
        _record_organ_error(
            errors,
            "FormSpecial",
            exc,
        )
        return {}


# ============================================================
# CORNERS
# ============================================================

def _run_corners(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    errors: List[str],
) -> Optional[Dict[str, Any]]:

    if CornersModel is None:
        errors.append(
            "CornersModel: MODULE_UNAVAILABLE"
        )
        return None

    try:
        model = CornersModel()

        result = model.synthesize_match(
            home_context,
            away_context,
        )

        result["state_type"] = "CornerState"

        return result

    except Exception as exc:
        _record_organ_error(
            errors,
            "CornersModel",
            exc,
        )
        return None


# ============================================================
# CARDS
# ============================================================

def _run_cards(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    errors: List[str],
) -> Optional[Dict[str, Any]]:

    if CardsModel is None:
        errors.append(
            "CardsModel: MODULE_UNAVAILABLE"
        )
        return None

    try:
        model = CardsModel()

        result = model.synthesize_match(
            home_context,
            away_context,
        )

        result["state_type"] = "CardState"

        return result

    except Exception as exc:
        _record_organ_error(
            errors,
            "CardsModel",
            exc,
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

    form_win = _run_form_win(
        home_context,
        away_context,
        home_team,
        away_team,
        errors,
    )

    if isinstance(form_win, dict):

        result["form_win"] = {
            "home": form_win.get("home"),
            "away": form_win.get("away"),
        }

        if "comparison" in form_win:
            result["form_win"]["comparison"] = (
                form_win["comparison"]
            )

    defence = _run_defence(
        home_context,
        away_context,
        home_team,
        away_team,
        errors,
    )

    if isinstance(defence, dict):
        result["defence"] = defence

    control = _run_form_control(
        home_context,
        away_context,
        home_team,
        away_team,
        errors,
    )

    if isinstance(control, dict):
        result["control"] = control

    anomaly = _run_form_anomaly(
        home_context,
        away_context,
        errors,
    )

    if isinstance(anomaly, dict):
        result["anomaly"] = anomaly

    special_form = _run_form_special(
        home_context,
        away_context,
        home_team,
        away_team,
        errors,
    )

    if isinstance(special_form, dict):
        result["special_form"] = special_form

    result["corners"] = _run_corners(
        home_context,
        away_context,
        errors,
    )

    result["cards"] = _run_cards(
        home_context,
        away_context,
        errors,
    )

    return result


# ============================================================
# WINNER STATE
# ============================================================

def _extract_comparison_value(
    parallel: Dict[str, Any],
    organ_key: str,
    field_name: str,
) -> Optional[float]:

    organ = parallel.get(
        organ_key
    ) or {}

    comparison = organ.get(
        "comparison"
    ) or {}

    return _num(
        comparison.get(field_name)
    )


def _anomaly_differential(
    parallel: Dict[str, Any],
) -> Optional[float]:

    anomaly = parallel.get(
        "anomaly"
    ) or {}

    home = anomaly.get(
        "home"
    ) or {}

    away = anomaly.get(
        "away"
    ) or {}

    home_signal = _num(
        _get(
            home,
            "anomaly_signal",
        )
    )

    away_signal = _num(
        _get(
            away,
            "anomaly_signal",
        )
    )

    if (
        home_signal is None
        or away_signal is None
    ):
        return None

    return home_signal - away_signal


def _run_winner_state(
    *,
    home_team: str,
    away_team: str,
    home_win_probability: Optional[float],
    draw_probability: Optional[float],
    away_win_probability: Optional[float],
    parallel: Dict[str, Any],
    errors: List[str],
) -> Optional[Dict[str, Any]]:

    if WinnerStateBuilder is None:
        errors.append(
            "WinnerState: MODULE_UNAVAILABLE"
        )
        return None

    try:

        relative_form_win = _extract_comparison_value(
            parallel,
            "form_win",
            "relative_form_win",
        )

        relative_defence = _extract_comparison_value(
            parallel,
            "defence",
            "relative_defence_advantage",
        )

        relative_control = _extract_comparison_value(
            parallel,
            "control",
            "relative_control",
        )

        special_differential = _extract_comparison_value(
            parallel,
            "special_form",
            "differential",
        )

        anomaly_differential = _anomaly_differential(
            parallel
        )

        state = WinnerStateBuilder().build(
            home_win_probability=home_win_probability,
            draw_probability=draw_probability,
            away_win_probability=away_win_probability,
            home_team=home_team,
            away_team=away_team,
            relative_form_win=relative_form_win,
            relative_defence=relative_defence,
            relative_control=relative_control,
            special_differential=special_differential,
            anomaly_differential=anomaly_differential,
        )

        return state.to_dict()

    except Exception as exc:
        _record_organ_error(
            errors,
            "WinnerState",
            exc,
        )
        return None


# ============================================================
# PRIMARY OUTCOME / SCENARIO / QUALITY
# ============================================================

def _extract_probability(
    probability_state: Any,
    field_name: str,
) -> Optional[float]:

    data = _dict(probability_state)

    return _prob(
        _get(
            data,
            field_name,
        )
    )


def _primary_outcome(
    home_probability: Optional[float],
    draw_probability: Optional[float],
    away_probability: Optional[float],
) -> Optional[str]:

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


def _primary_scenario(
    score_state: Any,
) -> Optional[str]:

    data = _dict(score_state)

    score = _get(
        data,
        "predicted_score",
        "likely_score",
    )

    return (
        str(score)
        if score is not None
        else None
    )


def _core_quality(
    goal_state: Any,
    probability_state: Any,
    score_state: Any,
) -> Optional[float]:

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
        ) not in (None, {}),

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
    FAJ Brain v4.2.

    Каноническое ядро:

        FormContext
        ->
        FormModel
        ->
        GoalModel
        ->
        RatingReconciliation
        ->
        ProbabilityModel
        ->
        ScorePredictor

    RatingReconciliation является единственным новым
    математическим органом между GoalModel и ProbabilityModel.

    Club Rating и Pair Rating не заменяют друг друга.
    Они объединяются в отдельный диагностический сигнал.
    """

    VERSION = BRAIN_VERSION
    STATUS = BRAIN_STATUS

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
        home_rating: Optional[float] = None,
        away_rating: Optional[float] = None,
        pair_home_rating: Optional[float] = None,
        pair_away_rating: Optional[float] = None,
    ) -> BrainPrediction:

        errors: List[str] = []

        # ====================================================
        # 0. HISTORY
        # ====================================================

        home_history = _history(
            home_history,
            home_team,
        )

        away_history = _history(
            away_history,
            away_team,
        )

        # ====================================================
        # 1. FORM CONTEXT
        # ====================================================

        home_context = _build_context(
            home_team,
            home_history,
        )

        away_context = _build_context(
            away_team,
            away_history,
        )

        # ====================================================
        # 2. FORM MODEL
        # ====================================================

        home_form, away_form = _run_form_model(
            home_context,
            away_context,
        )

        # ====================================================
        # 3. PARALLEL STATES
        # ====================================================

        parallel = _run_parallel_states(
            home_context,
            away_context,
            home_team,
            away_team,
        )

        errors.extend(
            parallel.get(
                "errors",
                [],
            )
        )

        # ====================================================
        # 4. GOAL MODEL
        # ====================================================

        goal_state = _run_goal_model(
            home_context,
            away_context,
            home_team,
            away_team,
        )

        # GoalModel is the OWNER of original λ
        home_lambda_before, away_lambda_before = (
            _extract_lambdas(goal_state)
        )

        if (
            home_lambda_before is None
            or away_lambda_before is None
        ):
            raise BrainCoreError(
                "GoalModel returned incomplete lambda state"
            )

        total_lambda_before = (
            home_lambda_before
            + away_lambda_before
        )

        # ====================================================
        # 5. RATING RECONCILIATION
        # ====================================================

        pair_rating_state, rating_reconciliation = (
            _build_rating_reconciliation(
                home_team=home_team,
                away_team=away_team,
                home_rating=home_rating,
                away_rating=away_rating,
                pair_home_rating=pair_home_rating,
                pair_away_rating=pair_away_rating,
            )
        )

        lambda_reconciliation = _run_lambda_reconciliation(
            lambda_home=home_lambda_before,
            lambda_away=away_lambda_before,
            reconciliation=rating_reconciliation,
        )

        lambda_reconciliation_data = (
            _serialize_lambda_reconciliation(
                lambda_reconciliation
            )
        )

        if lambda_reconciliation_data is None:
            raise BrainCoreError(
                "LambdaReconciliation returned invalid state"
            )

        # ----------------------------------------------------
        # FINAL λ AFTER RECONCILIATION
        # ----------------------------------------------------

        home_lambda = _num(
            _get(
                lambda_reconciliation_data,
                "lambda_home_after",
                "home_lambda_after",
            )
        )

        away_lambda = _num(
            _get(
                lambda_reconciliation_data,
                "lambda_away_after",
                "away_lambda_after",
            )
        )

        if home_lambda is None:
            raise BrainCoreError(
                "LambdaReconciliation returned no home lambda"
            )

        if away_lambda is None:
            raise BrainCoreError(
                "LambdaReconciliation returned no away lambda"
            )

        total_lambda = (
            home_lambda
            + away_lambda
        )

        # ====================================================
        # 6. PROBABILITY MODEL
        # ====================================================

        probability_state = _run_probability_model(
            home_lambda,
            away_lambda,
        )

        # ====================================================
        # 7. SCORE STATE
        # ====================================================

        score_state = _run_score_predictor(
            probability_state,
            home_lambda,
            away_lambda,
        )

        # ====================================================
        # 8. CORE PROBABILITIES
        # ====================================================

        home_win_probability = _extract_probability(
            probability_state,
            "home_win",
        )

        draw_probability = _extract_probability(
            probability_state,
            "draw",
        )

        away_win_probability = _extract_probability(
            probability_state,
            "away_win",
        )

        btts_probability = _extract_probability(
            probability_state,
            "btts",
        )

        over_25_probability = _extract_probability(
            probability_state,
            "over_25",
        )

        under_25_probability = _extract_probability(
            probability_state,
            "under_25",
        )

        over_35_probability = _extract_probability(
            probability_state,
            "over_35",
        )

        under_35_probability = _extract_probability(
            probability_state,
            "under_35",
        )

        # ====================================================
        # 9. SCORE OUTPUT
        # ====================================================

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

        # ====================================================
        # 10. PRIMARY OUTCOME
        # ====================================================

        primary_outcome = _primary_outcome(
            home_win_probability,
            draw_probability,
            away_win_probability,
        )

        # ====================================================
        # 11. PRIMARY SCENARIO
        # ====================================================

        primary_scenario = _primary_scenario(
            score_state
        )

        # ====================================================
        # 12. CORE QUALITY
        # ====================================================

        core_quality = _core_quality(
            goal_state,
            probability_state,
            score_state,
        )

        # ====================================================
        # 13. WINNER STATE
        # ====================================================

        winner_state = _run_winner_state(
            home_team=home_team,
            away_team=away_team,
            home_win_probability=home_win_probability,
            draw_probability=draw_probability,
            away_win_probability=away_win_probability,
            parallel=parallel,
            errors=errors,
        )

        # ====================================================
        # 14. RATING DIAGNOSTICS
        # ====================================================

        rating_reconciliation_data = (
            _serialize_rating_state(
                rating_reconciliation
            )
        )

        pair_rating_data = (
            _serialize_rating_state(
                pair_rating_state
            )
        )

        # ====================================================
        # 15. DIAGNOSTICS
        # ====================================================

        diagnostics = {

            "brain_version": BRAIN_VERSION,
            "brain_status": BRAIN_STATUS,
            "formula_status": "CONTRACT_V1",

            # ------------------------------------------------
            # CANONICAL CHAIN
            # ------------------------------------------------

            "chain": [
                "FACTS",
                "FormContext",
                "FormModel",
                "GoalModel",
                "RatingReconciliation",
                "ProbabilityModel",
                "ScorePredictor",
                "FINAL_BRAIN",
            ],

            # ------------------------------------------------
            # PARALLEL STATES
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

            "display_only_states": [
                "WinnerState"
            ],

            # ------------------------------------------------
            # OWNERSHIP
            # ------------------------------------------------

            "lambda_owner": "GoalModel",

            "lambda_reconciliation_owner": (
                "RatingReconciliation"
            ),

            "probability_owner": (
                "ProbabilityModel"
            ),

            "score_distribution_owner": (
                "ProbabilityModel"
            ),

            "score_ranking_owner": (
                "ScorePredictor"
            ),

            # ------------------------------------------------
            # RATING ARCHITECTURE
            # ------------------------------------------------

            "club_rating_used": (
                home_rating is not None
                and away_rating is not None
            ),

            "pair_rating_used": (
                pair_home_rating is not None
                and pair_away_rating is not None
            ),

            "pair_rating_state": pair_rating_data,

            "rating_reconciliation": (
                rating_reconciliation_data
            ),

            "lambda_reconciliation": (
                lambda_reconciliation_data
            ),

            # ------------------------------------------------
            # λ INTEGRITY
            # ------------------------------------------------

            "lambda_before": {
                "home": home_lambda_before,
                "away": away_lambda_before,
                "total": total_lambda_before,
            },

            "lambda_after": {
                "home": home_lambda,
                "away": away_lambda,
                "total": total_lambda,
            },

            "lambda_total_preserved": (
                math.isclose(
                    total_lambda_before,
                    total_lambda,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                )
            ),

            # ------------------------------------------------
            # NO UNAUTHORIZED FEEDBACK
            # ------------------------------------------------

            "diagnostic_feedback_to_goal": False,

            "diagnostic_feedback_to_probability": (
                False
            ),

            "diagnostic_feedback_to_score": (
                False
            ),

            # ------------------------------------------------
            # RATING IS THE EXPLICIT CORE INPUT
            # ------------------------------------------------

            "rating_reconciliation_changes_lambda": (
                True
            ),

            "rating_reconciliation_changes_total_lambda": (
                False
            ),

            "rating_reconciliation_changes_home_away_allocation": (
                True
            ),

            # ------------------------------------------------
            # OVERRIDES / MULTIPLIERS
            # ------------------------------------------------

            "winner_override": False,

            "rating_multiplier": False,

            "form_multiplier": False,

            "control_multiplier": False,

            "defence_multiplier": False,

            "anomaly_multiplier": False,

            "special_multiplier": False,

            "finishing_bonus": False,

            "low_score_correction": False,

            # ------------------------------------------------
            # LEARNING / DB / FUTURE
            # ------------------------------------------------

            "learning": False,

            "database_write": False,

            "future_result_used": False,

            "bookmaker_odds_used": False,

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            "core_data_quality": core_quality,

            "home_history_size": len(
                home_history
            ),

            "away_history_size": len(
                away_history
            ),

            "missing_is_zero": False,

            # ------------------------------------------------
            # CONFIDENCE / RISK
            # ------------------------------------------------

            "confidence_calculated": False,

            "risk_calculated": False,

            "reason_confidence_none": (
                "Confidence State coefficients are "
                "not defined/calibrated in Brain v4.2"
            ),

            "reason_risk_none": (
                "Risk State decomposition is not yet "
                "calculated by Brain"
            ),
        }

        diagnostics["parallel_contract"] = (
            parallel.get(
                "contract",
                {},
            )
        )

        # ====================================================
        # ORGAN CONTRACTS
        # ====================================================

        diagnostics["organ_contracts"] = {

            "FormWin": {
                "api": (
                    "calculate(context, team_name=...) "
                    "/ compare(...)"
                ),
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "Defence": {
                "api": (
                    "compare(home_context, away_context, "
                    "home_team=..., away_team=...)"
                ),
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "FormControl": {
                "api": (
                    "compare_control(home_context, "
                    "away_context, home_team=..., "
                    "away_team=...)"
                ),
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "FormAnomaly": {
                "api": "analyze(context)",
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "FormSpecial": {
                "api": (
                    "compare(home_context, away_context, "
                    "home_team=..., away_team=...)"
                ),
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "CornersModel": {
                "api": (
                    "synthesize_match("
                    "home_context, away_context)"
                ),
                "role": "separate_state",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "CardsModel": {
                "api": (
                    "synthesize_match("
                    "home_context, away_context)"
                ),
                "role": "separate_state",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "RatingReconciliation": {
                "api": (
                    "reconcile_ratings(...) / "
                    "reconcile_lambda(...)"
                ),
                "role": (
                    "core_lambda_allocation"
                ),
                "modifies_goal_model_formula": False,
                "modifies_goal_model_output": False,
                "modifies_lambda_allocation": True,
                "modifies_total_lambda": False,
                "modifies_probability": False,
                "winner_override": False,
            },

            "WinnerState": {
                "api": (
                    "build(home_win_probability=..., "
                    "draw_probability=..., "
                    "away_win_probability=..., ...)"
                ),
                "role": (
                    "display_only_synthesis"
                ),
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
        }

        # ====================================================
        # CORE INTEGRITY
        # ====================================================

        diagnostics["core_integrity"] = {

            "goal_model_owner_of_lambda": True,

            "rating_reconciliation_owner_of_lambda_allocation": (
                True
            ),

            "rating_reconciliation_changes_total_lambda": (
                False
            ),

            "probability_model_owner_of_probability": (
                True
            ),

            "score_predictor_owner_of_score_ranking": (
                True
            ),

            "diagnostic_organs_modify_lambda": False,

            "diagnostic_organs_modify_probability": (
                False
            ),

            "diagnostic_organs_modify_score_distribution": (
                False
            ),

            "winner_state_modifies_core": False,

            "none_is_zero": False,

            "future_result_used": False,

            "database_write": False,

            "learning": False,
        }

        # ====================================================
        # FINAL RESULT
        # ====================================================

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

            winner_state=winner_state,

            rating_reconciliation=(
                rating_reconciliation_data
            ),

            lambda_reconciliation=(
                lambda_reconciliation_data
            ),

            home_lambda=home_lambda,

            away_lambda=away_lambda,

            total_lambda=total_lambda,

            home_win_probability=(
                home_win_probability
            ),

            draw_probability=(
                draw_probability
            ),

            away_win_probability=(
                away_win_probability
            ),

            btts_probability=(
                btts_probability
            ),

            over_25_probability=(
                over_25_probability
            ),

            under_25_probability=(
                under_25_probability
            ),

            over_35_probability=(
                over_35_probability
            ),

            under_35_probability=(
                under_35_probability
            ),

            predicted_score=predicted_score,

            second_score=second_score,

            third_score=third_score,

            predicted_score_probability=(
                predicted_score_probability
            ),

            top_scores=top_scores,

            primary_outcome=primary_outcome,

            primary_scenario=primary_scenario,

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
    home_rating: Optional[float] = None,
    away_rating: Optional[float] = None,
    pair_home_rating: Optional[float] = None,
    pair_away_rating: Optional[float] = None,
) -> BrainPrediction:

    return FAJBrain().predict(
        home_team=home_team,
        away_team=away_team,
        home_history=home_history,
        away_history=away_history,
        home_rating=home_rating,
        away_rating=away_rating,
        pair_home_rating=pair_home_rating,
        pair_away_rating=pair_away_rating,
    )


def predict_match(
    home_team: str,
    away_team: str,
    home_history: Sequence[Any],
    away_history: Sequence[Any],
    home_rating: Optional[float] = None,
    away_rating: Optional[float] = None,
    pair_home_rating: Optional[float] = None,
    pair_away_rating: Optional[float] = None,
) -> BrainPrediction:

    return predict(
        home_team=home_team,
        away_team=away_team,
        home_history=home_history,
        away_history=away_history,
        home_rating=home_rating,
        away_rating=away_rating,
        pair_home_rating=pair_home_rating,
        pair_away_rating=pair_away_rating,
    )


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
