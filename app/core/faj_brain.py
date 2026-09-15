#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ BRAIN — FINAL ORCHESTRATOR
VERSION 3.2
============================================================

КАНОНИЧЕСКАЯ МАТЕМАТИЧЕСКАЯ ЦЕПОЧКА:

FACTS
  ↓
FormContext
  ↓
FormModel
  ↓
GoalModel v6.0
  ↓
ProbabilityModel v1.1
  ↓
ScorePredictor v2.2
  ↓
FINAL FAJ BRAIN

ПАРАЛЛЕЛЬНЫЕ АНАЛИТИЧЕСКИЕ ОРГАНЫ:

FormWin
Defence
FormControl
FormAnomaly
FormSpecial
CornersModel
CardsModel

PAIR RATING CONTRACT:

Pair Rating — исследовательский сигнал конкретной пары.

Он НЕ меняет:
    - xG
    - GoalModel
    - ProbabilityModel
    - Poisson
    - BTTS
    - totals
    - score distribution

Он используется ТОЛЬКО как диагностический/структурный
сигнал и сохраняется в calculation_meta.

Источники Pair Rating:
    1. manual                — оба рейтинга переданы вручную;
    2. club_rating_fallback  — авто из get_team_rating();
    3. None                  — ни один источник не сработал.

Источник фиксируется в calculation_meta["pair_rating_source"].

ВАЖНО:

- Winner Evidence Engine НЕ используется.
- Winner Synthesis НЕ используется.
- Старый Poisson НЕ используется.
- Старая формула xG НЕ используется.
- Старый xG blend НЕ используется.
- Старый home advantage НЕ используется.
- Brain не изменяет GoalModel.
- Brain не изменяет ProbabilityModel.
- Brain не изменяет ScorePredictor.
- Brain не обучается.
- Brain не пишет в БД.
- Missing != 0.
- ProbabilityModel является единственным источником
  1X2 / BTTS / totals / score distribution.
- Confidence приходит из GoalModel и остаётся в диапазоне 0..1.
- UI probability fields возвращаются в диапазоне 0..100.
============================================================
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence


# ============================================================
# CORE MATHEMATICAL ORGANS
# ============================================================

from .form_context import build_form_context
from .form_model import FormModel
from .goal_model import GoalModel
from .probability_model import ProbabilityModel
from .score_predictor import ScorePredictor


# ============================================================
# ANALYTICAL ORGANS
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

try:
    from .corners_model import CornersModel
except ImportError:
    CornersModel = None

try:
    from .cards_model import CardsModel
except ImportError:
    CardsModel = None


# ============================================================
# PAIR RATING
# ============================================================

try:
    from .pair_rating import calculate_pair_rating
except ImportError:
    calculate_pair_rating = None

try:
    from ..faj_club_ratings import get_team_rating
except ImportError:
    try:
        from app.faj_club_ratings import get_team_rating
    except ImportError:
        get_team_rating = None


# ============================================================
# VERSION / CONTRACT
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-FINAL-3.2"
CONTRACT_VERSION = "4.2"

HISTORY_SIZE = 6

PAIR_RATING_SOURCE_MANUAL = "manual"
PAIR_RATING_SOURCE_FALLBACK = "club_rating_fallback"

PAIR_RATING_MIN = 60
PAIR_RATING_MAX = 100


# ============================================================
# BASIC HELPERS
# ============================================================

def _num(value: Any) -> Optional[float]:
    """
    Безопасное преобразование в float.

    None остаётся None.
    Некорректные значения становятся None.
    NaN / inf становятся None.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result != result:
        return None

    if result in (float("inf"), float("-inf")):
        return None

    return result


def _int(value: Any) -> Optional[int]:
    """
    Безопасное преобразование в int.
    """

    number = _num(value)

    if number is None:
        return None

    return int(number)


def _get(obj: Any, *names: str) -> Any:
    """
    Универсальное получение значения из dict/dataclass/object.
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


def _dict(obj: Any) -> Dict[str, Any]:
    """
    Преобразование результата органа в dict
    для calculation_meta / brain_result.
    """

    if obj is None:
        return {}

    if isinstance(obj, dict):
        return dict(obj)

    to_dict = getattr(obj, "to_dict", None)

    if callable(to_dict):

        try:
            result = to_dict()

            if isinstance(result, dict):
                return dict(result)

        except Exception:
            pass

    if is_dataclass(obj):

        try:
            return asdict(obj)

        except Exception:
            pass

    try:
        return dict(vars(obj))

    except Exception:
        return {}


def _first(data: Dict[str, Any], *names: str) -> Any:
    """
    Получить первое существующее поле.
    """

    for name in names:

        if name in data:
            return data[name]

    return None


# ============================================================
# PROBABILITY HELPERS
# ============================================================

def _prob01(value: Any) -> Optional[float]:
    """
    Внутренний probability contract:

        0.0 .. 1.0

    Если внешний орган вернул 0..100,
    автоматически переводим в 0..1.
    """

    number = _num(value)

    if number is None:
        return None

    if number > 1.0:
        number /= 100.0

    return max(0.0, min(1.0, number))


def _prob100(value: Any) -> Optional[float]:
    """
    UI probability contract:

        0.0 .. 100.0
    """

    number = _prob01(value)

    if number is None:
        return None

    return round(number * 100.0, 1)


# ============================================================
# HISTORY
# ============================================================

def _history(matches: Iterable[Any]) -> List[Any]:
    """
    FAJ Brain работает ровно с шестью последними матчами.

    Порядок входа НЕ переворачивается.
    """

    values = list(matches)

    if len(values) != HISTORY_SIZE:

        raise ValueError(
            "FAJBrain requires exactly "
            f"{HISTORY_SIZE} historical matches; "
            f"received {len(values)}"
        )

    return values


# ============================================================
# HISTORICAL MATCH NORMALIZATION
# ============================================================

def _record(record: Any) -> Dict[str, Any]:
    """
    Нормализация одного исторического матча
    в формат FormContext.

    ВАЖНО:

    отсутствующие значения остаются None.
    """

    def pair(name: str):
        return (
            _get(record, f"home_{name}"),
            _get(record, f"away_{name}"),
        )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = _get(record, "score")

    home_goals = _int(
        _get(
            record,
            "home_goals",
            "home_score",
        )
    )

    away_goals = _int(
        _get(
            record,
            "away_goals",
            "away_score",
        )
    )

    if (
        home_goals is None
        or away_goals is None
    ) and score:

        parts = (
            str(score)
            .replace("-", ":")
            .split(":")
        )

        if len(parts) >= 2:

            parsed_home = _int(parts[0])
            parsed_away = _int(parts[1])

            if home_goals is None:
                home_goals = parsed_home

            if away_goals is None:
                away_goals = parsed_away

    # --------------------------------------------------------
    # XG
    # --------------------------------------------------------

    xg = _get(record, "xg")

    if isinstance(xg, dict):

        home_xg = _num(
            xg.get("home")
        )

        away_xg = _num(
            xg.get("away")
        )

    else:

        home_xg = _num(
            _get(
                record,
                "home_xg",
            )
        )

        away_xg = _num(
            _get(
                record,
                "away_xg",
            )
        )

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    fields = {

        "shots": _int,

        "shots_on_target": _int,

        "blocked_shots": _int,

        "possession": _num,

        "corners": _int,

        "yellow_cards": _int,

        "fouls": _int,

        "offsides": _int,

        "passes": _int,

        "pass_accuracy": _num,

        "crosses": _int,

        "throwins": _int,

        "big_chances": _int,

        "clearances": _int,

        "tackles": _int,

        "woodwork": _int,
    }

    result: Dict[str, Any] = {

        "home_team": _get(
            record,
            "home_team",
            "home_name",
            "home",
        ),

        "away_team": _get(
            record,
            "away_team",
            "away_name",
            "away",
        ),

        "match_date": _get(
            record,
            "match_date",
            "date",
            "match_date_str",
        ),

        "home_goals": home_goals,

        "away_goals": away_goals,

        "xg": {
            "home": home_xg,
            "away": away_xg,
        },
    }

    # --------------------------------------------------------
    # COPY AVAILABLE STATISTICS
    # --------------------------------------------------------

    for name, caster in fields.items():

        home_value, away_value = pair(name)

        if name == "yellow_cards":

            if home_value is None:

                home_value = _get(
                    record,
                    "home_yellow_cards",
                    "home_cards",
                )

            if away_value is None:

                away_value = _get(
                    record,
                    "away_yellow_cards",
                    "away_cards",
                )

        result[
            f"home_{name}"
        ] = caster(home_value)

        result[
            f"away_{name}"
        ] = caster(away_value)

    return result


# ============================================================
# FORM CONTEXT
# ============================================================

def _context(
    team: str,
    history: Sequence[Any],
) -> Dict[str, Any]:
    """
    Построение FormContext из шести исторических матчей.
    """

    records = [
        _record(match)
        for match in history
    ]

    context = build_form_context(
        team_name=team,
        records=records,
        limit=HISTORY_SIZE,
    )

    if isinstance(context, dict):
        return context

    return _dict(context)


# ============================================================
# PAIR RATING RESOLUTION
# ============================================================

def _resolve_pair_rating(
    home_team: str,
    away_team: str,
    home_pair_rating: Optional[Any],
    away_pair_rating: Optional[Any],
) -> tuple[
    Optional[Any],
    Optional[str],
]:
    """
    Возвращает (pair_rating, pair_rating_source).

    Приоритет:
        1. manual                — оба рейтинга переданы вручную;
        2. club_rating_fallback  — авто из get_team_rating();
        3. None                  — ни один источник не сработал.

    Никаких side effects.
    """

    if calculate_pair_rating is None:
        return None, None

    # ----------------------------------------------------
    # 1. MANUAL
    # ----------------------------------------------------

    if (
        home_pair_rating is not None
        and away_pair_rating is not None
    ):

        try:
            home_value = int(home_pair_rating)
            away_value = int(away_pair_rating)

            if (
                PAIR_RATING_MIN <= home_value <= PAIR_RATING_MAX
                and PAIR_RATING_MIN <= away_value <= PAIR_RATING_MAX
            ):
                pair_rating = calculate_pair_rating(
                    home_rating=home_value,
                    away_rating=away_value,
                    home_team=home_team,
                    away_team=away_team,
                )
                return (
                    pair_rating,
                    PAIR_RATING_SOURCE_MANUAL,
                )
        except (TypeError, ValueError):
            pass

    # ----------------------------------------------------
    # 2. CLUB RATING FALLBACK
    # ----------------------------------------------------

    if get_team_rating is not None:

        home_rating = None
        away_rating = None

        try:
            home_rating = get_team_rating(home_team)
        except Exception:
            home_rating = None

        try:
            away_rating = get_team_rating(away_team)
        except Exception:
            away_rating = None

        if home_rating is not None and away_rating is not None:
            try:
                home_rating_value = int(home_rating)
                away_rating_value = int(away_rating)

                if (
                    PAIR_RATING_MIN <= home_rating_value <= PAIR_RATING_MAX
                    and PAIR_RATING_MIN <= away_rating_value <= PAIR_RATING_MAX
                ):
                    pair_rating = calculate_pair_rating(
                        home_rating=home_rating_value,
                        away_rating=away_rating_value,
                        home_team=home_team,
                        away_team=away_team,
                    )
                    return (
                        pair_rating,
                        PAIR_RATING_SOURCE_FALLBACK,
                    )
            except (TypeError, ValueError):
                pass

    # ----------------------------------------------------
    # 3. NONE
    # ----------------------------------------------------

    return None, None


# ============================================================
# SAFE DIAGNOSTIC CALL
# ============================================================

def _safe_call(
    function,
    **kwargs: Any,
) -> Any:
    """
    Диагностический орган не должен разрушать
    основную математическую цепочку.

    Исключение → None.

    Основные математические органы GoalModel,
    ProbabilityModel и ScorePredictor здесь
    НЕ вызываются через этот механизм.
    """

    try:

        return function(**kwargs)

    except Exception:

        return None


# ============================================================
# FAJ BRAIN
# ============================================================

class FAJBrain:
    """
    Главный математический оркестратор FAJ.

    Brain не содержит собственной альтернативной
    математической модели.

    Все основные математические решения принадлежат
    специализированным органам.
    """

    VERSION = BRAIN_VERSION

    def __init__(self) -> None:

        self.version = BRAIN_VERSION

    # ========================================================
    # FORM MODELS
    # ========================================================

    def _form_models(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ):
        """
        FormModel — первый математический орган.
        """

        home_form = FormModel().analyze(
            form_context=home_context,
            next_venue="home",
        )

        away_form = FormModel().analyze(
            form_context=away_context,
            next_venue="away",
        )

        return home_form, away_form

    # ========================================================
    # DIAGNOSTIC ORGANS
    # ========================================================

    def _diagnostics(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Параллельные аналитические органы.

        Они не изменяют:

        - xG;
        - lambda;
        - 1X2;
        - BTTS;
        - totals;
        - score distribution.
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
        # DEFENCE
        # ----------------------------------------------------

        if Defence:

            diagnostics["home"]["defence"] = _safe_call(
                Defence().calculate,
                context=home_context,
                team_name=home_team,
            )

            diagnostics["away"]["defence"] = _safe_call(
                Defence().calculate,
                context=away_context,
                team_name=away_team,
            )

        # ----------------------------------------------------
        # FORM WIN
        # ----------------------------------------------------

        if FormWin:

            diagnostics["home"]["form_win"] = _safe_call(
                FormWin().analyze,
                form_context=home_context,
                next_venue="home",
            )

            diagnostics["away"]["form_win"] = _safe_call(
                FormWin().analyze,
                form_context=away_context,
                next_venue="away",
            )

            try:

                diagnostics[
                    "form_win_comparison"
                ] = FormWin().compare(
                    home_context,
                    away_context,
                )

            except Exception:

                diagnostics[
                    "form_win_comparison"
                ] = None

        # ----------------------------------------------------
        # FORM CONTROL
        # ----------------------------------------------------

        if FormControl:

            diagnostics["home"]["control"] = _safe_call(
                FormControl().analyze,
                context=home_context,
                target_team=home_team,
                opponent_team=away_team,
                venue="home",
            )

            diagnostics["away"]["control"] = _safe_call(
                FormControl().analyze,
                context=away_context,
                target_team=away_team,
                opponent_team=home_team,
                venue="away",
            )

            home_control = diagnostics[
                "home"
            ].get("control")

            away_control = diagnostics[
                "away"
            ].get("control")

            if (
                home_control is not None
                and away_control is not None
            ):

                diagnostics[
                    "control_comparison"
                ] = {

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

                    "home_result": home_control,

                    "away_result": away_control,
                }

            else:

                diagnostics[
                    "control_comparison"
                ] = None

        # ----------------------------------------------------
        # FORM ANOMALY
        # ----------------------------------------------------

        if FormAnomaly:

            diagnostics["home"]["anomaly"] = _safe_call(
                FormAnomaly().analyze,
                context=home_context,
            )

            diagnostics["away"]["anomaly"] = _safe_call(
                FormAnomaly().analyze,
                context=away_context,
            )

        # ----------------------------------------------------
        # SPECIAL FORM
        # ----------------------------------------------------

        if FormSpecial:

            diagnostics[
                "home"
            ]["special_form"] = _safe_call(
                FormSpecial().analyze,
                context=home_context,
                team_name=home_team,
            )

            diagnostics[
                "away"
            ]["special_form"] = _safe_call(
                FormSpecial().analyze,
                context=away_context,
                team_name=away_team,
            )

        return diagnostics

    # ========================================================
    # GOAL MODEL
    # ========================================================

    def _goal(
        self,
        home_form: Any,
        away_form: Any,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
        diagnostics: Dict[str, Any],
    ):
        """
        Единственный вызов GoalModel.

        Никаких дополнительных xG формул здесь нет.
        """

        return GoalModel().analyze(

            home_form=home_form,

            away_form=away_form,

            home_team=home_team,

            away_team=away_team,

            venue="HOME",

            home_control=diagnostics[
                "home"
            ].get("control"),

            away_control=diagnostics[
                "away"
            ].get("control"),

            home_special=diagnostics[
                "home"
            ].get("special_form"),

            away_special=diagnostics[
                "away"
            ].get("special_form"),

            home_history=home_history,

            away_history=away_history,
        )

    # ========================================================
    # CORE MATHEMATICAL PIPELINE
    # ========================================================

    def _core(
        self,
        home_form: Any,
        away_form: Any,
        home_team: str,
        away_team: str,
        home_history: Sequence[Any],
        away_history: Sequence[Any],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Главная математическая цепочка:

        GoalModel
            ↓
        ProbabilityModel
            ↓
        ScorePredictor
        """

        # ----------------------------------------------------
        # GOAL MODEL
        # ----------------------------------------------------

        goal = self._goal(
            home_form,
            away_form,
            home_team,
            away_team,
            home_history,
            away_history,
            diagnostics,
        )

        goal_data = _dict(goal)

        home_xg = _num(
            _first(
                goal_data,
                "home_xg",
                "lambda_home",
                "home_lambda",
            )
        )

        away_xg = _num(
            _first(
                goal_data,
                "away_xg",
                "lambda_away",
                "away_lambda",
            )
        )

        # ----------------------------------------------------
        # VALIDATE GOAL MODEL OUTPUT
        # ----------------------------------------------------

        if (
            home_xg is None
            or away_xg is None
        ):

            raise ValueError(
                "GoalModel returned missing lambda"
            )

        if not (
            0.0
            <= home_xg
            <= 4.5
        ):

            raise ValueError(
                "GoalModel returned invalid home lambda"
            )

        if not (
            0.0
            <= away_xg
            <= 4.5
        ):

            raise ValueError(
                "GoalModel returned invalid away lambda"
            )

        # ----------------------------------------------------
        # PROBABILITY MODEL
        # ----------------------------------------------------

        probability = ProbabilityModel().calculate(

            home_xg=home_xg,

            away_xg=away_xg,
        )

        probability_data = _dict(
            probability
        )

        score_distribution = _first(

            probability_data,

            "score_distribution",

            "score_probabilities",

            "distribution",
        )

        if score_distribution is None:

            raise ValueError(
                "ProbabilityModel did not return "
                "score_distribution"
            )

        # ----------------------------------------------------
        # SCORE PREDICTOR
        # ----------------------------------------------------

        score = ScorePredictor().predict(

            score_probabilities=score_distribution,

            home_xg=home_xg,

            away_xg=away_xg,

            probability_result=probability,
        )

        score_data = _dict(score)

        return {

            "goal": goal,

            "goal_data": goal_data,

            "probability": probability,

            "probability_data": probability_data,

            "score": score,

            "score_data": score_data,
        }

    # ========================================================
    # CORNERS / CARDS
    # ========================================================

    def _side_channels(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ):
        """
        Corners и Cards — независимые каналы.

        Они не влияют на:

        - xG;
        - lambda;
        - 1X2;
        - BTTS;
        - totals;
        - score distribution.
        """

        corners = None

        cards = None

        if CornersModel:

            try:

                corners = (
                    CornersModel()
                    .synthesize_match(
                        home_context,
                        away_context,
                    )
                )

            except Exception:

                corners = None

        if CardsModel:

            try:

                cards = (
                    CardsModel()
                    .synthesize_match(
                        home_context,
                        away_context,
                    )
                )

            except Exception:

                cards = None

        return corners, cards

    # ========================================================
    # SCORE EXTRACTION
    # ========================================================

    @staticmethod
    def _scores(
        score_data: Dict[str, Any],
        probability_data: Dict[str, Any],
    ):
        """
        Извлечение top scores без дополнительной математики.
        """

        top = (
            score_data.get("top_scores")
            or probability_data.get("top_scores")
            or []
        )

        top3 = score_data.get(
            "top_3_scores"
        )

        if top3 is None:

            try:

                top3 = list(top)[:3]

            except Exception:

                top3 = []

        return top, top3

    # ========================================================
    # CONCLUSION
    # ========================================================

    @staticmethod
    def _conclusion(
        home_team: str,
        away_team: str,
        home_probability: Optional[float],
        draw_probability: Optional[float],
        away_probability: Optional[float],
        btts_probability: Optional[float],
        over25_probability: Optional[float],
    ):
        """
        Чистая текстовая интерпретация уже рассчитанных
        вероятностей.

        Никаких дополнительных коэффициентов.
        """

        values = {

            home_team: home_probability,

            "DRAW": draw_probability,

            away_team: away_probability,
        }

        values = {

            key: value

            for key, value in values.items()

            if value is not None
        }

        factors: List[str] = []

        if values:

            favorite = max(
                values,
                key=values.get,
            )

            if favorite == "DRAW":

                factors.append(
                    "Модель не видит явного фаворита."
                )

                winner = "равновесие сил"

            else:

                factors.append(
                    f"Модель видит преимущество {favorite}."
                )

                winner = (
                    f"преимущество {favorite}"
                )

        else:

            winner = "недостаточно данных"

            factors.append(
                "Недостаточно вероятностных данных."
            )

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        if btts_probability is not None:

            if btts_probability >= 0.60:

                factors.append(
                    "Вероятность обмена голами повышена."
                )

            elif btts_probability <= 0.40:

                factors.append(
                    "Модель скорее не ожидает обмена голами."
                )

            else:

                factors.append(
                    "Вероятность обмена голами близка "
                    "к нейтральной."
                )

        # ----------------------------------------------------
        # OVER 2.5
        # ----------------------------------------------------

        if over25_probability is not None:

            if over25_probability >= 0.60:

                factors.append(
                    "Сценарий 3+ голов имеет повышенную вероятность."
                )

            elif over25_probability <= 0.40:

                factors.append(
                    "Модель скорее склоняется "
                    "к умеренной результативности."
                )

            else:

                factors.append(
                    "Тотал 2.5 близок "
                    "к нейтральному сценарию."
                )

        return (
            f"FAJ: {winner}. "
            + " ".join(factors),
            factors,
        )

    # ========================================================
    # PUBLIC PREDICT
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
        Главный публичный метод FAJ Brain.

        kwargs принимает:

            - home_pair_rating
            - away_pair_rating

        Winner Evidence Engine и Winner Synthesis
        здесь НЕ используются.
        """

        # ----------------------------------------------------
        # PAIR RATING INPUTS
        # ----------------------------------------------------

        home_pair_rating_input = kwargs.get(
            "home_pair_rating"
        )

        away_pair_rating_input = kwargs.get(
            "away_pair_rating"
        )

        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        home_history = _history(
            home_matches
        )

        away_history = _history(
            away_matches
        )

        # ----------------------------------------------------
        # FORM CONTEXT
        # ----------------------------------------------------

        home_context = _context(
            home_team,
            home_history,
        )

        away_context = _context(
            away_team,
            away_history,
        )

        # ----------------------------------------------------
        # FORM MODEL
        # ----------------------------------------------------

        home_form, away_form = (
            self._form_models(
                home_context,
                away_context,
            )
        )

        # ----------------------------------------------------
        # DIAGNOSTIC ORGANS
        # ----------------------------------------------------

        diagnostics = self._diagnostics(

            home_context,

            away_context,

            home_team,

            away_team,
        )

        # ----------------------------------------------------
        # CORE MATHEMATICS
        # ----------------------------------------------------

        core = self._core(

            home_form,

            away_form,

            home_team,

            away_team,

            home_history,

            away_history,

            diagnostics,
        )

        # ----------------------------------------------------
        # CORNERS / CARDS
        # ----------------------------------------------------

        corners, cards = self._side_channels(

            home_context,

            away_context,
        )

        # ----------------------------------------------------
        # CORE DATA
        # ----------------------------------------------------

        probability_data = core[
            "probability_data"
        ]

        goal_data = core[
            "goal_data"
        ]

        score_data = core[
            "score_data"
        ]

        # ----------------------------------------------------
        # PROBABILITIES
        # ----------------------------------------------------

        home_probability = _prob01(
            probability_data.get(
                "home_win"
            )
        )

        draw_probability = _prob01(
            probability_data.get(
                "draw"
            )
        )

        away_probability = _prob01(
            probability_data.get(
                "away_win"
            )
        )

        btts_probability = _prob01(
            probability_data.get(
                "btts"
            )
        )

        over15_probability = _prob01(
            probability_data.get(
                "over_15"
            )
        )

        over25_probability = _prob01(
            probability_data.get(
                "over_25"
            )
        )

        over35_probability = _prob01(
            probability_data.get(
                "over_35"
            )
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        confidence = _prob01(
            goal_data.get(
                "confidence"
            )
        )

        if confidence is not None:

            if confidence >= 0.75:

                risk = "LOW"

            elif confidence >= 0.60:

                risk = "MEDIUM"

            else:

                risk = "HIGH"

        else:

            risk = None

        # ----------------------------------------------------
        # SCORE FORECAST
        # ----------------------------------------------------

        top_scores, top3_scores = self._scores(

            score_data,

            probability_data,
        )

        predicted_score = score_data.get(
            "predicted_score"
        )

        likely_score = score_data.get(
            "likely_score",
            predicted_score,
        )

        second_score = score_data.get(
            "second_score"
        )

        third_score = score_data.get(
            "third_score"
        )

        # ----------------------------------------------------
        # PAIR RATING RESOLUTION
        # ----------------------------------------------------

        pair_rating, pair_rating_source = (
            _resolve_pair_rating(
                home_team=home_team,
                away_team=away_team,
                home_pair_rating=home_pair_rating_input,
                away_pair_rating=away_pair_rating_input,
            )
        )

        pair_rating_dict = None

        if pair_rating is not None:

            pair_rating_dict = (
                _dict(pair_rating)
                if not isinstance(pair_rating, dict)
                else pair_rating
            )

        # ----------------------------------------------------
        # TEXT CONCLUSION
        # ----------------------------------------------------

        conclusion, factors = self._conclusion(

            home_team,

            away_team,

            home_probability,

            draw_probability,

            away_probability,

            btts_probability,

            over25_probability,
        )

        # ====================================================
        # GOAL MODEL META
        # ====================================================

        goal_model_meta = dict(
            goal_data
        )

        goal_model_meta[
            "diagnostics"
        ] = goal_data.get(
            "diagnostics",
            {},
        )

        # ====================================================
        # CALCULATION META
        # ====================================================

        calculation_meta = {

            "brain_version": BRAIN_VERSION,

            "contract_version": CONTRACT_VERSION,

            "goal_model_version": goal_data.get(
                "model_version"
            ),

            "probability_model_version": probability_data.get(
                "model_version"
            ),

            "score_predictor_version": score_data.get(
                "model_version"
            ),

            # ----------------------------------------------
            # GOAL MODEL
            # ----------------------------------------------

            "goal_model": goal_model_meta,

            # ----------------------------------------------
            # PROBABILITY MODEL
            # ----------------------------------------------

            "probability_model": _dict(
                core["probability"]
            ),

            # ----------------------------------------------
            # SCORE PREDICTOR
            # ----------------------------------------------

            "score_predictor": _dict(
                core["score"]
            ),

            # ----------------------------------------------
            # SCORE FORECAST
            # ----------------------------------------------

            "score_forecast": {

                "predicted_score": predicted_score,

                "likely_score": likely_score,

                "second_score": second_score,

                "third_score": third_score,

                "top_scores": top_scores,

                "top_3_scores": top3_scores,
            },

            # ----------------------------------------------
            # PAIR RATING
            # ----------------------------------------------

            "pair_rating": pair_rating_dict,

            "pair_rating_source": pair_rating_source,

            # ----------------------------------------------
            # CORNERS
            # ----------------------------------------------

            "corners_model": (
                _dict(corners)
                if corners is not None
                else None
            ),

            # ----------------------------------------------
            # CARDS
            # ----------------------------------------------

            "cards_model": (
                _dict(cards)
                if cards is not None
                else None
            ),

            # ----------------------------------------------
            # FORM
            # ----------------------------------------------

            "home_form_model": _dict(
                home_form
            ),

            "away_form_model": _dict(
                away_form
            ),

            # ----------------------------------------------
            # HISTORY
            # ----------------------------------------------

            "home_matches": HISTORY_SIZE,

            "away_matches": HISTORY_SIZE,

            # ----------------------------------------------
            # DIAGNOSTICS
            # ----------------------------------------------

            "diagnostics": diagnostics,
        }

        # ====================================================
        # FINAL PUBLIC OUTPUT
        # ====================================================

        return {

            # ------------------------------------------------
            # TEAMS
            # ------------------------------------------------

            "home_team": home_team,

            "away_team": away_team,

            "home_matches": HISTORY_SIZE,

            "away_matches": HISTORY_SIZE,

            # ------------------------------------------------
            # UI
            # ------------------------------------------------

            "analysis_mode": "Расширенный",

            "data_quality": None,

            # ------------------------------------------------
            # 1X2
            #
            # UI contract = 0..100
            # ------------------------------------------------

            "home_win_probability": _prob100(
                home_probability
            ),

            "draw_probability": _prob100(
                draw_probability
            ),

            "away_win_probability": _prob100(
                away_probability
            ),

            # Compatibility aliases

            "home_win": _prob100(
                home_probability
            ),

            "draw": _prob100(
                draw_probability
            ),

            "away_win": _prob100(
                away_probability
            ),

            # ------------------------------------------------
            # BTTS
            # ------------------------------------------------

            "btts": (
                btts_probability >= 0.5
                if btts_probability is not None
                else None
            ),

            "btts_probability": _prob100(
                btts_probability
            ),

            # ------------------------------------------------
            # OVER 2.5
            # ------------------------------------------------

            "over25": (
                over25_probability >= 0.5
                if over25_probability is not None
                else None
            ),

            "over25_probability": _prob100(
                over25_probability
            ),

            # ------------------------------------------------
            # OVER 3.5
            # ------------------------------------------------

            "over35": (
                over35_probability >= 0.5
                if over35_probability is not None
                else None
            ),

            "over35_probability": _prob100(
                over35_probability
            ),

            # ------------------------------------------------
            # OVER 1.5
            # ------------------------------------------------

            "over15_probability": _prob100(
                over15_probability
            ),

            # ------------------------------------------------
            # XG
            # ------------------------------------------------

            "home_xg": _num(
                goal_data.get(
                    "home_xg"
                )
            ),

            "away_xg": _num(
                goal_data.get(
                    "away_xg"
                )
            ),

            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            "predicted_score": predicted_score,

            "likely_score": likely_score,

            "second_score": second_score,

            "third_score": third_score,

            "most_likely_score": likely_score,

            "second_likely_score": second_score,

            "third_likely_score": third_score,

            "top_scores": top_scores,

            "top_3_scores": top3_scores,

            # ------------------------------------------------
            # CONFIDENCE
            #
            # UI expects 0..1 and multiplies by 100.
            # ------------------------------------------------

            "confidence": confidence,

            "risk": risk,

            # ------------------------------------------------
            # TEXT
            # ------------------------------------------------

            "conclusion": conclusion,

            "factors": factors,

            # ------------------------------------------------
            # CORNERS
            # ------------------------------------------------

            "corners": (
                _get(
                    corners,
                    "total_expected_corners",
                )
                if corners is not None
                else None
            ),

            # ------------------------------------------------
            # CARDS
            # ------------------------------------------------

            "cards": (
                _get(
                    cards,
                    "total_expected_cards",
                )
                if cards is not None
                else None
            ),

            # ------------------------------------------------
            # CONTEXT
            # ------------------------------------------------

            "home_form_context": home_context,

            "away_form_context": away_context,

            # ------------------------------------------------
            # META
            # ------------------------------------------------

            "calculation_meta": calculation_meta,

            "diagnostics": diagnostics,

            # =================================================
            # BRAIN RESULT
            # =================================================

            "brain_result": {

                "brain_version": BRAIN_VERSION,

                "contract_version": CONTRACT_VERSION,

                "teams": {

                    "home": home_team,

                    "away": away_team,
                },

                "form_model": {

                    "home": _dict(
                        home_form
                    ),

                    "away": _dict(
                        away_form
                    ),
                },

                "goal_model": goal_data,

                "probability_model": probability_data,

                "score_predictor": score_data,

                "pair_rating": pair_rating_dict,

                "pair_rating_source": pair_rating_source,

                "corners_model": (
                    _dict(corners)
                    if corners is not None
                    else None
                ),

                "cards_model": (
                    _dict(cards)
                    if cards is not None
                    else None
                ),

                "diagnostics": diagnostics,
            },
        }


# ============================================================
# MODULE-LEVEL CONVENIENCE API
# ============================================================

def predict_match(
    home_team: str,
    away_team: str,
    home_matches: Iterable[Any],
    away_matches: Iterable[Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Удобный внешний API.
    """

    return FAJBrain().predict(
        home_team,
        away_team,
        home_matches,
        away_matches,
        **kwargs,
    )
