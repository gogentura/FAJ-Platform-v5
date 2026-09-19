#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN v4.1
============================================================

Чистый orchestration layer FAJ.

КАНОНИЧЕСКАЯ ЦЕПОЧКА (неприкосновенное ядро):

    FACTS -> FormContext -> FormModel -> GoalModel
          -> home_lambda / away_lambda -> ProbabilityModel
          -> ScorePredictor -> FINAL BRAIN

ПАРАЛЛЕЛЬНЫЕ STATE (evidence, не влияют на ядро):

    FormWin, Defence, FormControl, FormAnomaly, FormSpecial,
    CornersModel, CardsModel

DISPLAY-ONLY СИНТЕЗ (v4.1, новое):

    WinnerState — строится ПОСЛЕ ядра, из уже готовых
    вероятностей 1X2 и relative-evidence уже существующих
    compare()-методов. НЕ пересчитывает и не изменяет ядро.

BRAIN НЕ: считает xG/λ/Poisson самостоятельно, пересчитывает
1X2/BTTS/totals/score, применяет Winner Override или любые
multiplier'ы, обучается, пишет в database.py, использует
будущий результат.

MISSING DATA: None != 0. Отсутствие обязательного Core State
поднимает BrainCoreError. Отсутствие diagnostic State не
ломает Core prediction — ошибка сохраняется в diagnostics.

VERSION
-------
FAJ-BRAIN-4.1
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

BRAIN_VERSION = "FAJ-BRAIN-4.1"
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
    Final FAJ Brain result. Объединяет результаты уже
    существующих State/Model, сам новой математикой не является.
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
    # WINNER STATE (v4.1, display-only)
    # --------------------------------------------------------

    winner_state: Optional[Dict[str, Any]] = None

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

    top_scores: List[Dict[str, Any]] = field(default_factory=list)

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
        return {key: _serialize(value) for key, value in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_serialize(value) for value in obj]

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
        return {key: record[key] for key in keys}
    except (AttributeError, TypeError):
        pass

    try:
        return dict(vars(record))
    except Exception as exc:
        raise BrainCoreError("Historical record cannot be normalized") from exc


def _normalize_history(matches: Sequence[Any]) -> List[Dict[str, Any]]:
    return [_normalize_record(record) for record in matches]


def _history(matches: Sequence[Any], team_name: str) -> List[Any]:

    if matches is None:
        raise BrainCoreError(f"{team_name}: history is missing")

    try:
        values = list(matches)
    except TypeError as exc:
        raise BrainCoreError(f"{team_name}: invalid history") from exc

    if not values:
        raise BrainCoreError(f"{team_name}: empty history")

    if len(values) > HISTORY_SIZE:
        values = values[-HISTORY_SIZE:]

    return values


# ============================================================
# FORM CONTEXT
# ============================================================

def _build_context(team_name: str, history: Sequence[Any]) -> Dict[str, Any]:

    records = _normalize_history(history)

    try:
        context = build_form_context(team_name=team_name, records=records)
    except Exception as exc:
        raise BrainCoreError(f"FormContext failed for {team_name}") from exc

    result = _dict(context)

    if not result:
        raise BrainCoreError(f"FormContext returned empty state for {team_name}")

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
        home_form = model.analyze(form_context=home_context, next_venue="home")
        away_form = model.analyze(form_context=away_context, next_venue="away")
    except Exception as exc:
        raise BrainCoreError("FormModel failed") from exc

    if home_form is None:
        raise BrainCoreError("FormModel returned None for home")

    if away_form is None:
        raise BrainCoreError("FormModel returned None for away")

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
        raise BrainCoreError("GoalModel failed") from exc

    if result is None:
        raise BrainCoreError("GoalModel returned None")

    return result


def _extract_lambdas(goal_state: Any) -> tuple[Optional[float], Optional[float]]:

    data = _dict(goal_state)

    home_lambda = _num(_get(data, "home_lambda", "lambda_home"))
    away_lambda = _num(_get(data, "away_lambda", "lambda_away"))

    return home_lambda, away_lambda


# ============================================================
# PROBABILITY MODEL
# ============================================================

def _run_probability_model(
    home_lambda: Optional[float],
    away_lambda: Optional[float],
) -> Any:

    model = ProbabilityModel()

    try:
        result = model.calculate(home_lambda=home_lambda, away_lambda=away_lambda)
    except Exception as exc:
        raise BrainCoreError("ProbabilityModel failed") from exc

    if result is None:
        raise BrainCoreError("ProbabilityModel returned None")

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
    score_distribution = _get(probability_data, "score_distribution")

    predictor = ScorePredictor()

    try:
        result = predictor.predict(
            score_probabilities=score_distribution,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            probability_result=probability_state,
        )
    except Exception as exc:
        raise BrainCoreError("ScorePredictor failed") from exc

    if result is None:
        raise BrainCoreError("ScorePredictor returned None")

    return result


# ============================================================
# ORGAN ERROR HELPER
# ============================================================

def _record_organ_error(errors: List[str], name: str, exc: Exception) -> None:
    errors.append(f"{name}: {type(exc).__name__}: {exc}")


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
        errors.append("FormWin: MODULE_UNAVAILABLE")
        return {}

    try:
        model = FormWin()

        home_state = model.calculate(home_context, team_name=home_team)
        away_state = model.calculate(away_context, team_name=away_team)

        result = {
            "home": _serialize(home_state),
            "away": _serialize(away_state),
        }

        compare_method = getattr(model, "compare", None)

        if callable(compare_method):
            comparison = compare_method(
                home_context, away_context,
                home_team=home_team, away_team=away_team,
            )
            result["comparison"] = _serialize(comparison)

        return result

    except Exception as exc:
        _record_organ_error(errors, "FormWin", exc)
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
    """
    Defence v2.0. Использует .compare(), который сам вызывает
    .calculate() на обе команды и попутно даёт relative-evidence
    (нужно WinnerState) — без отдельных лишних вызовов.
    """

    if Defence is None:
        errors.append("Defence: MODULE_UNAVAILABLE")
        return {}

    try:
        model = Defence()

        comparison = model.compare(
            home_context, away_context,
            home_team=home_team, away_team=away_team,
        )

        return {
            "home": _serialize(comparison.home_state),
            "away": _serialize(comparison.away_state),
            "comparison": {
                "relative_defence_advantage": comparison.relative_defence_advantage,
                "relative_creation": comparison.relative_creation,
                "relative_process": comparison.relative_process,
                "relative_control": comparison.relative_control,
                "relative_outcome": comparison.relative_outcome,
                "relative_momentum": comparison.relative_momentum,
            },
        }

    except Exception as exc:
        _record_organ_error(errors, "Defence", exc)
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
    """
    FormControl v1.2. Использует module-level compare_control(),
    который уже даёт relative_control без дублирования вызовов.
    """

    if FormControl is None or compare_control is None:
        errors.append("FormControl: MODULE_UNAVAILABLE")
        return {}

    try:
        comparison = compare_control(
            home_context, away_context,
            home_team=home_team, away_team=away_team,
        )

        return {
            "home": comparison.get("home_control"),
            "away": comparison.get("away_control"),
            "comparison": {
                "relative_control": comparison.get("relative_control"),
            },
        }

    except Exception as exc:
        _record_organ_error(errors, "FormControl", exc)
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
        errors.append("FormAnomaly: MODULE_UNAVAILABLE")
        return {}

    try:
        model = FormAnomaly()

        home_state = model.analyze(home_context)
        away_state = model.analyze(away_context)

        return {
            "home": _serialize(home_state),
            "away": _serialize(away_state),
        }

    except Exception as exc:
        _record_organ_error(errors, "FormAnomaly", exc)
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
    """
    FormSpecial v2.0. Использует .compare(), даёт "differential"
    напрямую — нужен WinnerState.
    """

    if FormSpecial is None:
        errors.append("FormSpecial: MODULE_UNAVAILABLE")
        return {}

    try:
        model = FormSpecial()

        comparison = model.compare(
            home_context, away_context,
            home_team=home_team, away_team=away_team,
        )

        return {
            "home": _serialize(comparison.get("home")),
            "away": _serialize(comparison.get("away")),
            "comparison": {
                "differential": comparison.get("differential"),
            },
        }

    except Exception as exc:
        _record_organ_error(errors, "FormSpecial", exc)
        return {}


# ============================================================
# CORNERS
# ============================================================

def _run_corners(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    errors: List[str],
) -> Optional[Dict[str, Any]]:
    """
    CornersModel v1.3. .synthesize_match() — единственный метод,
    реально считающий home/away/total_expected_corners.
    """

    if CornersModel is None:
        errors.append("CornersModel: MODULE_UNAVAILABLE")
        return None

    try:
        model = CornersModel()

        result = model.synthesize_match(home_context, away_context)
        result["state_type"] = "CornerState"

        return result

    except Exception as exc:
        _record_organ_error(errors, "CornersModel", exc)
        return None


# ============================================================
# CARDS
# ============================================================

def _run_cards(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
    errors: List[str],
) -> Optional[Dict[str, Any]]:
    """
    CardsModel v1.3. .synthesize_match() — единственный метод,
    реально считающий home/away/total_expected_cards.
    """

    if CardsModel is None:
        errors.append("CardsModel: MODULE_UNAVAILABLE")
        return None

    try:
        model = CardsModel()

        result = model.synthesize_match(home_context, away_context)
        result["state_type"] = "CardState"

        return result

    except Exception as exc:
        _record_organ_error(errors, "CardsModel", exc)
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
        "form_win": {"home": None, "away": None},
        "defence": {"home": None, "away": None},
        "control": {"home": None, "away": None},
        "anomaly": {"home": None, "away": None},
        "special_form": {"home": None, "away": None},
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

    form_win = _run_form_win(home_context, away_context, home_team, away_team, errors)
    if isinstance(form_win, dict):
        result["form_win"] = {"home": form_win.get("home"), "away": form_win.get("away")}
        if "comparison" in form_win:
            result["form_win"]["comparison"] = form_win["comparison"]

    defence = _run_defence(home_context, away_context, home_team, away_team, errors)
    if isinstance(defence, dict):
        result["defence"] = defence

    control = _run_form_control(home_context, away_context, home_team, away_team, errors)
    if isinstance(control, dict):
        result["control"] = control

    anomaly = _run_form_anomaly(home_context, away_context, errors)
    if isinstance(anomaly, dict):
        result["anomaly"] = anomaly

    special_form = _run_form_special(home_context, away_context, home_team, away_team, errors)
    if isinstance(special_form, dict):
        result["special_form"] = special_form

    result["corners"] = _run_corners(home_context, away_context, errors)
    result["cards"] = _run_cards(home_context, away_context, errors)

    return result


# ============================================================
# WINNER STATE (display-only, после ядра)
# ============================================================

def _extract_comparison_value(
    parallel: Dict[str, Any],
    organ_key: str,
    field_name: str,
) -> Optional[float]:

    organ = parallel.get(organ_key) or {}
    comparison = organ.get("comparison") or {}

    return _num(comparison.get(field_name))


def _anomaly_differential(parallel: Dict[str, Any]) -> Optional[float]:

    anomaly = parallel.get("anomaly") or {}
    home = anomaly.get("home") or {}
    away = anomaly.get("away") or {}

    home_signal = _num(_get(home, "anomaly_signal"))
    away_signal = _num(_get(away, "anomaly_signal"))

    if home_signal is None or away_signal is None:
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
        errors.append("WinnerState: MODULE_UNAVAILABLE")
        return None

    try:
        relative_form_win = _extract_comparison_value(parallel, "form_win", "relative_form_win")
        relative_defence = _extract_comparison_value(parallel, "defence", "relative_defence_advantage")
        relative_control = _extract_comparison_value(parallel, "control", "relative_control")
        special_differential = _extract_comparison_value(parallel, "special_form", "differential")
        anomaly_differential = _anomaly_differential(parallel)

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
        _record_organ_error(errors, "WinnerState", exc)
        return None


# ============================================================
# PRIMARY OUTCOME / SCENARIO / QUALITY
# ============================================================

def _extract_probability(probability_state: Any, field_name: str) -> Optional[float]:

    data = _dict(probability_state)
    return _prob(_get(data, field_name))


def _primary_outcome(
    home_probability: Optional[float],
    draw_probability: Optional[float],
    away_probability: Optional[float],
) -> Optional[str]:

    values = {"HOME": home_probability, "DRAW": draw_probability, "AWAY": away_probability}
    available = {key: value for key, value in values.items() if value is not None}

    if not available:
        return None

    return max(available, key=available.get)


def _primary_scenario(score_state: Any) -> Optional[str]:

    data = _dict(score_state)
    score = _get(data, "predicted_score", "likely_score")

    return str(score) if score is not None else None


def _core_quality(goal_state: Any, probability_state: Any, score_state: Any) -> Optional[float]:

    goal_data = _dict(goal_state)
    probability_data = _dict(probability_state)
    score_data = _dict(score_state)

    checks = [
        _num(_get(goal_data, "home_lambda")) is not None,
        _num(_get(goal_data, "away_lambda")) is not None,
        _get(probability_data, "score_distribution") not in (None, {}),
        _get(score_data, "predicted_score", "likely_score") is not None,
    ]

    if not checks:
        return None

    return sum(1 for value in checks if value) / len(checks)


# ============================================================
# FINAL BRAIN
# ============================================================

class FAJBrain:
    """
    FAJ Brain v4.1. Собирает существующие математические органы
    в одну чистую предматчевую цепочку и добавляет display-only
    WinnerState поверх готового результата.
    """

    VERSION = BRAIN_VERSION
    STATUS = BRAIN_STATUS

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
    ) -> BrainPrediction:

        errors: List[str] = []

        home_history = _history(home_history, home_team)
        away_history = _history(away_history, away_team)

        # 1. FORM CONTEXT
        home_context = _build_context(home_team, home_history)
        away_context = _build_context(away_team, away_history)

        # 2. FORM MODEL
        home_form, away_form = _run_form_model(home_context, away_context)

        # 3. PARALLEL STATES
        parallel = _run_parallel_states(home_context, away_context, home_team, away_team)
        errors.extend(parallel.get("errors", []))

        # 4. GOAL STATE
        goal_state = _run_goal_model(home_context, away_context, home_team, away_team)
        home_lambda, away_lambda = _extract_lambdas(goal_state)

        total_lambda = (
            home_lambda + away_lambda
            if home_lambda is not None and away_lambda is not None
            else None
        )

        # 5. PROBABILITY STATE
        probability_state = _run_probability_model(home_lambda, away_lambda)

        # 6. SCORE STATE
        score_state = _run_score_predictor(probability_state, home_lambda, away_lambda)

        # 7. CORE PROBABILITIES
        home_win_probability = _extract_probability(probability_state, "home_win")
        draw_probability = _extract_probability(probability_state, "draw")
        away_win_probability = _extract_probability(probability_state, "away_win")
        btts_probability = _extract_probability(probability_state, "btts")
        over_25_probability = _extract_probability(probability_state, "over_25")
        under_25_probability = _extract_probability(probability_state, "under_25")
        over_35_probability = _extract_probability(probability_state, "over_35")
        under_35_probability = _extract_probability(probability_state, "under_35")

        # 8. SCORE OUTPUT
        score_data = _dict(score_state)

        predicted_score = _get(score_data, "predicted_score", "likely_score")
        second_score = _get(score_data, "second_score")
        third_score = _get(score_data, "third_score")

        predicted_score_probability = _num(
            _get(score_data, "probability_score", "primary_score_value")
        )

        top_scores = _get(score_data, "top_scores")
        if not isinstance(top_scores, list):
            top_scores = []

        # 9. PRIMARY OUTCOME
        primary_outcome = _primary_outcome(
            home_win_probability, draw_probability, away_win_probability
        )

        # 10. PRIMARY SCENARIO
        primary_scenario = _primary_scenario(score_state)

        # 11. CORE QUALITY
        core_quality = _core_quality(goal_state, probability_state, score_state)

        # 12. WINNER STATE (display-only, после core; НЕ влияет на core)
        winner_state = _run_winner_state(
            home_team=home_team,
            away_team=away_team,
            home_win_probability=home_win_probability,
            draw_probability=draw_probability,
            away_win_probability=away_win_probability,
            parallel=parallel,
            errors=errors,
        )

        # 13. DIAGNOSTICS
        diagnostics = {
            "brain_version": BRAIN_VERSION,
            "brain_status": BRAIN_STATUS,
            "formula_status": "CONTRACT_V1",

            "chain": [
                "FACTS", "FormContext", "FormModel", "GoalModel",
                "ProbabilityModel", "ScorePredictor", "FINAL_BRAIN",
            ],

            "parallel_states": [
                "FormWin", "Defence", "FormControl", "FormAnomaly",
                "FormSpecial", "CornersModel", "CardsModel",
            ],

            "display_only_states": ["WinnerState"],

            "lambda_owner": "GoalModel",
            "probability_owner": "ProbabilityModel",
            "score_distribution_owner": "ProbabilityModel",
            "score_ranking_owner": "ScorePredictor",

            "diagnostic_feedback_to_goal": False,
            "diagnostic_feedback_to_probability": False,
            "diagnostic_feedback_to_score": False,

            "winner_override": False,
            "rating_multiplier": False,
            "form_multiplier": False,
            "control_multiplier": False,
            "defence_multiplier": False,
            "anomaly_multiplier": False,
            "special_multiplier": False,
            "finishing_bonus": False,
            "low_score_correction": False,

            "learning": False,
            "database_write": False,
            "future_result_used": False,
            "bookmaker_odds_used": False,

            "core_data_quality": core_quality,
            "home_history_size": len(home_history),
            "away_history_size": len(away_history),
            "missing_is_zero": False,

            "confidence_calculated": False,
            "risk_calculated": False,

            "reason_confidence_none": (
                "Confidence State coefficients are not defined/calibrated in Brain v4.1"
            ),
            "reason_risk_none": (
                "Risk State decomposition is not yet calculated by Brain"
            ),
        }

        diagnostics["parallel_contract"] = parallel.get("contract", {})

        diagnostics["organ_contracts"] = {
            "FormWin": {
                "api": "calculate(context, team_name=...) / compare(...)",
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
            "Defence": {
                "api": "compare(home_context, away_context, home_team=..., away_team=...)",
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
            "FormControl": {
                "api": "compare_control(home_context, away_context, home_team=..., away_team=...)",
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
                "api": "compare(home_context, away_context, home_team=..., away_team=...)",
                "role": "evidence",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
            "CornersModel": {
                "api": "synthesize_match(home_context, away_context)",
                "role": "separate_state",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
            "CardsModel": {
                "api": "synthesize_match(home_context, away_context)",
                "role": "separate_state",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
            "WinnerState": {
                "api": "build(home_win_probability=..., draw_probability=..., away_win_probability=..., ...)",
                "role": "display_only_synthesis",
                "modifies_goal_model": False,
                "modifies_probability": False,
                "winner_override": False,
            },
        }

        diagnostics["core_integrity"] = {
            "goal_model_owner_of_lambda": True,
            "probability_model_owner_of_probability": True,
            "score_predictor_owner_of_score_ranking": True,
            "diagnostic_organs_modify_lambda": False,
            "diagnostic_organs_modify_probability": False,
            "diagnostic_organs_modify_score_distribution": False,
            "winner_state_modifies_core": False,
            "none_is_zero": False,
            "future_result_used": False,
            "database_write": False,
            "learning": False,
        }

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
            form_win=parallel["form_win"],
            defence=parallel["defence"],
            control=parallel["control"],
            anomaly=parallel["anomaly"],
            special_form=parallel["special_form"],
            corners_state=parallel["corners"],
            cards_state=parallel["cards"],
            winner_state=winner_state,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            total_lambda=total_lambda,
            home_win_probability=home_win_probability,
            draw_probability=draw_probability,
            away_win_probability=away_win_probability,
            btts_probability=btts_probability,
            over_25_probability=over_25_probability,
            under_25_probability=under_25_probability,
            over_35_probability=over_35_probability,
            under_35_probability=under_35_probability,
            predicted_score=predicted_score,
            second_score=second_score,
            third_score=third_score,
            predicted_score_probability=predicted_score_probability,
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
) -> BrainPrediction:

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

    return predict(
        home_team=home_team,
        away_team=away_team,
        home_history=home_history,
        away_history=away_history,
    )


__all__ = [
    "BRAIN_VERSION", "BRAIN_STATUS", "HISTORY_SIZE",
    "BrainCoreError", "BrainPrediction", "FAJBrain",
    "predict", "predict_match",
]
