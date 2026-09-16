#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
STREAMLIT APP
============================================================

Главный принцип:

UI
 ↓
Soccer365Parser
 ↓
FAJBrain
 ↓
FormContext
 ↓
FormModel / FormWin / Defence / FormControl /
FormAnomaly / FormSpecial
 ↓
GoalModel
 ↓
ProbabilityModel
 ↓
ScorePredictor
 ↓
CornersModel / CardsModel
 ↓
FINAL FAJ PREDICTION

ВАЖНО:
- UI не рассчитывает Poisson.
- UI не рассчитывает xG.
- UI не рассчитывает 1X2.
- UI не рассчитывает BTTS.
- UI не рассчитывает totals.
- UI не рассчитывает score distribution.
- UI не использует Pair Rating.
- UI не использует Winner Synthesis.
- UI не использует database.py для расчёта рейтинга.
- database.py не изменяется.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import streamlit as st

from app.core.faj_brain import FAJBrain
from app.core.form_context import build_form_context
from app.parsers.soccer365_parser import Soccer365Parser


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "FAJ-STREAMLIT-1.0"
HISTORY_SIZE = 6


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FAJ Predictor",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# HELPERS
# ============================================================

def safe_float(value: Any) -> Optional[float]:
    """
    Безопасное преобразование в float.

    None остаётся None.
    dict/list/string без числового значения -> None.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    try:
        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except (TypeError, ValueError):
        return None


def format_number(
    value: Any,
    digits: int = 2,
    suffix: str = "",
) -> str:
    """
    UI formatting only.
    Никаких математических преобразований модели.
    """
    number = safe_float(value)

    if number is None:
        return "—"

    return f"{number:.{digits}f}{suffix}"


def format_probability(value: Any) -> str:
    """
    Brain confidence/probability хранится как 0..1.
    """
    number = safe_float(value)

    if number is None:
        return "—"

    # Только защита отображения.
    if 0.0 <= number <= 1.0:
        return f"{number * 100.0:.1f}%"

    # На случай уже переданного процента.
    return f"{number:.1f}%"


def get_value(
    data: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Безопасное чтение dict/object.
    """
    if data is None:
        return default

    if isinstance(data, dict):
        return data.get(key, default)

    return getattr(data, key, default)


def as_dict(value: Any) -> Dict[str, Any]:
    """
    Преобразует model result в dict, если это возможно.
    """
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    to_dict = getattr(value, "to_dict", None)

    if callable(to_dict):
        try:
            result = to_dict()

            if isinstance(result, dict):
                return result

        except Exception:
            pass

    if hasattr(value, "__dict__"):
        return dict(value.__dict__)

    return {}


def extract_team_name(record: Any, side: str) -> Optional[str]:
    """
    Получает название команды из записи истории.
    """
    if isinstance(record, dict):
        value = record.get(side)

        if value:
            return str(value)

    value = getattr(record, side, None)

    if value:
        return str(value)

    return None


def extract_score(record: Any) -> str:
    """
    UI representation of historical score.
    """
    if isinstance(record, dict):
        value = record.get("score")

        if value is not None:
            return str(value)

    value = getattr(record, "score", None)

    if value is not None:
        return str(value)

    return "—"


def extract_date(record: Any) -> str:
    """
    UI representation of historical date.
    """
    if isinstance(record, dict):
        value = record.get("date")

        if value is not None:
            return str(value)

    value = getattr(record, "date", None)

    if value is not None:
        return str(value)

    return "—"


def extract_url(record: Any) -> Optional[str]:
    """
    UI representation of match URL.
    """
    if isinstance(record, dict):
        value = record.get("url")

        if value:
            return str(value)

    value = getattr(record, "url", None)

    if value:
        return str(value)

    return None


def normalize_records(
    records: Any,
    limit: int = HISTORY_SIZE,
) -> List[Any]:
    """
    Не меняет порядок записей.

    FormContext v1.7 ожидает:
    oldest -> newest

    Здесь мы только ограничиваем количество.
    """
    if records is None:
        return []

    if not isinstance(records, list):
        try:
            records = list(records)
        except Exception:
            return []

    return records[:limit]


# ============================================================
# SOCCER365
# ============================================================

@st.cache_resource
def get_parser() -> Soccer365Parser:
    return Soccer365Parser()


@st.cache_resource
def get_brain() -> FAJBrain:
    return FAJBrain()


def load_team_history(team_url: str) -> List[Any]:
    """
    Получает историю команды через существующий Soccer365Parser.

    Вызов изолирован здесь, чтобы UI не занимался математикой.
    """
    parser = get_parser()

    # Поддерживаем основной контракт parser.
    if hasattr(parser, "parse_team_results"):
        records = parser.parse_team_results(team_url)
        return normalize_records(records, HISTORY_SIZE)

    if hasattr(parser, "get_team_results"):
        records = parser.get_team_results(team_url)
        return normalize_records(records, HISTORY_SIZE)

    if hasattr(parser, "parse_team_history"):
        records = parser.parse_team_history(team_url)
        return normalize_records(records, HISTORY_SIZE)

    raise AttributeError(
        "Soccer365Parser не содержит метода получения истории команды."
    )


# ============================================================
# BRAIN
# ============================================================

def calculate_prediction(
    home_team: str,
    away_team: str,
    home_records: List[Any],
    away_records: List[Any],
) -> Dict[str, Any]:

    brain = get_brain()

    home_records = normalize_records(
        home_records,
        HISTORY_SIZE,
    )

    away_records = normalize_records(
        away_records,
        HISTORY_SIZE,
    )

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_records,
        away_matches=away_records,
    )

    return as_dict(result)


# ============================================================
# FORM CONTEXT
# ============================================================

def build_context_for_display(
    team_name: str,
    records: List[Any],
) -> Dict[str, Any]:

    records = normalize_records(
        records,
        HISTORY_SIZE,
    )

    return build_form_context(
        team_name=team_name,
        records=records,
        limit=HISTORY_SIZE,
    )


# ============================================================
# UI — HISTORY
# ============================================================

def render_history(
    title: str,
    team_name: str,
    records: List[Any],
) -> None:

    st.subheader(title)

    if not records:
        st.info(f"История для {team_name} отсутствует.")
        return

    rows = []

    for index, record in enumerate(records, start=1):

        home = extract_team_name(record, "home")
        away = extract_team_name(record, "away")
        score = extract_score(record)
        date = extract_date(record)
        url = extract_url(record)

        rows.append(
            {
                "M": index,
                "Дата": date,
                "Матч": (
                    f"{home or '—'} — {away or '—'}"
                ),
                "Счёт": score,
                "URL": url or "",
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# UI — FORM CONTEXT
# ============================================================

def render_form_context(
    team_name: str,
    records: List[Any],
) -> None:

    context = build_context_for_display(
        team_name,
        records,
    )

    if not context:
        st.info("FormContext отсутствует.")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Матчей",
            context.get("matches_count", 0),
        )

    with col2:
        st.metric(
            "Победы",
            context.get("wins", 0),
        )

    with col3:
        st.metric(
            "Ничьи",
            context.get("draws", 0),
        )

    with col4:
        st.metric(
            "Поражения",
            context.get("losses", 0),
        )

    st.write("### FormContext")

    xg = context.get("xg")
    xga = context.get("xga")

    corners_for = context.get("corners_for_avg")
    corners_against = context.get("corners_against_avg")

    cards_for = context.get("team_cards_avg")
    cards_against = context.get("opponent_cards_avg")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.metric(
            "xG",
            format_number(xg),
        )

    with c2:
        st.metric(
            "xGA",
            format_number(xga),
        )

    with c3:
        st.metric(
            "Угловые FOR",
            format_number(corners_for),
        )

    with c4:
        st.metric(
            "Угловые AGAINST",
            format_number(corners_against),
        )

    with c5:
        st.metric(
            "Карточки FOR",
            format_number(cards_for),
        )

    with c6:
        st.metric(
            "Карточки AGAINST",
            format_number(cards_against),
        )


# ============================================================
# UI — MAIN RESULT
# ============================================================

def render_main_result(
    prediction: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> None:

    st.header("FAJ Brain — прогноз")

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    st.subheader("Ожидаемые голы")

    home_xg = prediction.get("home_xg")
    away_xg = prediction.get("away_xg")

    x1, x2 = st.columns(2)

    with x1:
        st.metric(
            home_team,
            format_number(home_xg),
        )

    with x2:
        st.metric(
            away_team,
            format_number(away_xg),
        )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    st.subheader("1X2")

    home_win = prediction.get("home_win_probability")
    draw = prediction.get("draw_probability")
    away_win = prediction.get("away_win_probability")

    p1, p2, p3 = st.columns(3)

    with p1:
        st.metric(
            f"{home_team} победа",
            format_probability(home_win),
        )

    with p2:
        st.metric(
            "Ничья",
            format_probability(draw),
        )

    with p3:
        st.metric(
            f"{away_team} победа",
            format_probability(away_win),
        )

    # --------------------------------------------------------
    # BTTS / TOTALS
    # --------------------------------------------------------

    st.subheader("Голы")

    btts = prediction.get("btts_probability")

    over15 = prediction.get("over15_probability")
    over25 = prediction.get("over25_probability")
    over35 = prediction.get("over35_probability")

    g1, g2, g3, g4 = st.columns(4)

    with g1:
        st.metric(
            "BTTS",
            format_probability(btts),
        )

    with g2:
        st.metric(
            "Over 1.5",
            format_probability(over15),
        )

    with g3:
        st.metric(
            "Over 2.5",
            format_probability(over25),
        )

    with g4:
        st.metric(
            "Over 3.5",
            format_probability(over35),
        )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    st.subheader("Точные счета")

    predicted_score = prediction.get("predicted_score")
    most_likely_score = prediction.get("most_likely_score")
    second_score = prediction.get("second_score")
    third_score = prediction.get("third_score")

    if predicted_score is None:
        predicted_score = most_likely_score

    s1, s2, s3 = st.columns(3)

    with s1:
        st.metric(
            "Основной",
            predicted_score or "—",
        )

    with s2:
        st.metric(
            "Второй",
            second_score or "—",
        )

    with s3:
        st.metric(
            "Третий",
            third_score or "—",
        )

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    st.subheader("Угловые")

    home_corners = prediction.get(
        "home_corners_expected"
    )

    away_corners = prediction.get(
        "away_corners_expected"
    )

    corners_total = prediction.get(
        "corners_expected"
    )

    if corners_total is None:
        h = safe_float(home_corners)
        a = safe_float(away_corners)

        if h is not None and a is not None:
            corners_total = h + a

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            home_team,
            format_number(home_corners),
        )

    with c2:
        st.metric(
            away_team,
            format_number(away_corners),
        )

    with c3:
        st.metric(
            "Всего",
            format_number(corners_total),
        )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    st.subheader("Карточки")

    home_cards = prediction.get(
        "home_cards_expected"
    )

    away_cards = prediction.get(
        "away_cards_expected"
    )

    cards_total = prediction.get(
        "cards_expected"
    )

    if cards_total is None:
        h = safe_float(home_cards)
        a = safe_float(away_cards)

        if h is not None and a is not None:
            cards_total = h + a

    k1, k2, k3 = st.columns(3)

    with k1:
        st.metric(
            home_team,
            format_number(home_cards),
        )

    with k2:
        st.metric(
            away_team,
            format_number(away_cards),
        )

    with k3:
        st.metric(
            "Всего",
            format_number(cards_total),
        )


# ============================================================
# UI — CONFIDENCE
# ============================================================

def render_confidence(
    prediction: Dict[str, Any],
) -> None:

    st.subheader("Confidence / Risk")

    confidence = prediction.get("confidence")

    risk = prediction.get("risk")

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "Confidence",
            format_probability(confidence),
        )

    with c2:
        st.metric(
            "Risk",
            str(risk) if risk is not None else "—",
        )


# ============================================================
# UI — CONCLUSION
# ============================================================

def render_conclusion(
    prediction: Dict[str, Any],
) -> None:

    conclusion = prediction.get("conclusion")

    if conclusion:
        st.subheader("FAJ Brain")

        st.info(
            str(conclusion)
        )


# ============================================================
# UI — DIAGNOSTICS
# ============================================================

def render_diagnostics(
    prediction: Dict[str, Any],
) -> None:

    st.subheader("Diagnostics")

    diagnostics = prediction.get("diagnostics")

    if diagnostics is None:
        st.info("Diagnostics отсутствуют.")
        return

    diagnostics = as_dict(diagnostics)

    if not diagnostics:
        st.info("Diagnostics отсутствуют.")
        return

    st.json(diagnostics)


# ============================================================
# UI — BRAIN RESULT
# ============================================================

def render_brain_result(
    prediction: Dict[str, Any],
) -> None:

    brain_result = prediction.get("brain_result")

    if not brain_result:
        return

    with st.expander(
        "Полный результат FAJ Brain",
        expanded=False,
    ):
        st.json(
            as_dict(brain_result)
        )


# ============================================================
# UI — DATA QUALITY
# ============================================================

def render_data_quality(
    prediction: Dict[str, Any],
) -> None:

    data_quality = prediction.get("data_quality")

    if not isinstance(data_quality, dict):
        return

    with st.expander(
        "Data Quality",
        expanded=False,
    ):
        st.json(data_quality)


# ============================================================
# UI — GOAL MODEL
# ============================================================

def render_goal_model(
    prediction: Dict[str, Any],
) -> None:

    brain_result = prediction.get("brain_result")

    if not isinstance(brain_result, dict):
        return

    goal_result = brain_result.get("goal_model")

    if not goal_result:
        goal_result = brain_result.get("goal")

    if not goal_result:
        return

    goal_data = as_dict(goal_result)

    if not goal_data:
        return

    st.subheader("GoalModel")

    g1, g2, g3, g4 = st.columns(4)

    with g1:
        st.metric(
            "Home xG",
            format_number(
                goal_data.get("home_xg")
            ),
        )

    with g2:
        st.metric(
            "Away xG",
            format_number(
                goal_data.get("away_xg")
            ),
        )

    with g3:
        st.metric(
            "Home attack",
            format_number(
                goal_data.get("home_attack")
            ),
        )

    with g4:
        st.metric(
            "Away attack",
            format_number(
                goal_data.get("away_attack")
            ),
        )

    diagnostics = goal_data.get(
        "diagnostics"
    )

    if diagnostics:
        with st.expander(
            "GoalModel diagnostics",
            expanded=False,
        ):
            st.json(
                as_dict(diagnostics)
            )


# ============================================================
# UI — SCORE PREDICTOR
# ============================================================

def render_score_predictor(
    prediction: Dict[str, Any],
) -> None:

    brain_result = prediction.get("brain_result")

    if not isinstance(brain_result, dict):
        return

    score_result = brain_result.get(
        "score_predictor"
    )

    if not score_result:
        score_result = brain_result.get(
            "score"
        )

    if not score_result:
        return

    score_data = as_dict(score_result)

    if not score_data:
        return

    with st.expander(
        "ScorePredictor",
        expanded=False,
    ):
        st.json(score_data)


# ============================================================
# UI — PROBABILITY MODEL
# ============================================================

def render_probability_model(
    prediction: Dict[str, Any],
) -> None:

    brain_result = prediction.get("brain_result")

    if not isinstance(brain_result, dict):
        return

    probability_result = brain_result.get(
        "probability_model"
    )

    if not probability_result:
        probability_result = brain_result.get(
            "probability"
        )

    if not probability_result:
        return

    probability_data = as_dict(
        probability_result
    )

    if not probability_data:
        return

    with st.expander(
        "ProbabilityModel",
        expanded=False,
    ):
        st.json(probability_data)


# ============================================================
# UI — FORM DIAGNOSTICS
# ============================================================

def render_form_diagnostics(
    prediction: Dict[str, Any],
) -> None:

    brain_result = prediction.get("brain_result")

    if not isinstance(brain_result, dict):
        return

    diagnostic_names = [
        "form_model",
        "form_win",
        "defence",
        "form_control",
        "form_anomaly",
        "form_special",
    ]

    available = {}

    for name in diagnostic_names:

        value = brain_result.get(name)

        if value is not None:
            available[name] = as_dict(value)

    if not available:
        return

    with st.expander(
        "Form diagnostics",
        expanded=False,
    ):
        st.json(available)


# ============================================================
# UI — RAW PREDICTION
# ============================================================

def render_raw_prediction(
    prediction: Dict[str, Any],
) -> None:

    with st.expander(
        "Полный Prediction",
        expanded=False,
    ):
        st.json(prediction)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.title("⚽ FAJ Predictor")

    st.caption(
        f"FAJ Platform v12.1 · {APP_VERSION}"
    )

    st.markdown(
        """
        **FAJ Brain** — единый источник математического прогноза.

        История → FormContext → аналитические органы →
        GoalModel → ProbabilityModel → ScorePredictor.
        """
    )

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    st.sidebar.header("Матч")

    home_team = st.sidebar.text_input(
        "Хозяева",
        value="",
        placeholder="Например: Валенсия",
    )

    away_team = st.sidebar.text_input(
        "Гости",
        value="",
        placeholder="Например: Барселона",
    )

    st.sidebar.markdown(
        "---"
    )

    home_url = st.sidebar.text_input(
        "Soccer365 URL хозяев",
        value="",
        placeholder="https://soccer365.ru/clubs/...",
    )

    away_url = st.sidebar.text_input(
        "Soccer365 URL гостей",
        value="",
        placeholder="https://soccer365.ru/clubs/...",
    )

    run_prediction = st.sidebar.button(
        "🚀 РАССЧИТАТЬ",
        type="primary",
        use_container_width=True,
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not home_team.strip():
        st.info(
            "Введите команду хозяев."
        )
        return

    if not away_team.strip():
        st.info(
            "Введите команду гостей."
        )
        return

    if not home_url.strip():
        st.info(
            "Введите Soccer365 URL хозяев."
        )
        return

    if not away_url.strip():
        st.info(
            "Введите Soccer365 URL гостей."
        )
        return

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    if not run_prediction:
        st.info(
            "Введите команды и ссылки Soccer365, "
            "затем нажмите «РАССЧИТАТЬ»."
        )
        return

    # --------------------------------------------------------
    # LOAD HISTORY
    # --------------------------------------------------------

    with st.spinner(
        "Получаю последние 6 матчей..."
    ):

        try:
            home_records = load_team_history(
                home_url.strip()
            )

            away_records = load_team_history(
                away_url.strip()
            )

        except Exception as exc:

            st.error(
                "Ошибка получения истории Soccer365."
            )

            st.exception(exc)

            return

    # --------------------------------------------------------
    # HISTORY CHECK
    # --------------------------------------------------------

    st.success(
        f"{home_team}: {len(home_records)} матчей | "
        f"{away_team}: {len(away_records)} матчей"
    )

    # --------------------------------------------------------
    # RAW HISTORY
    # --------------------------------------------------------

    with st.expander(
        "История команд",
        expanded=False,
    ):

        render_history(
            f"{home_team} — последние матчи",
            home_team,
            home_records,
        )

        render_history(
            f"{away_team} — последние матчи",
            away_team,
            away_records,
        )

    # --------------------------------------------------------
    # FORM CONTEXT
    # --------------------------------------------------------

    with st.expander(
        "FormContext",
        expanded=False,
    ):

        render_form_context(
            home_team,
            home_records,
        )

        render_form_context(
            away_team,
            away_records,
        )

    # --------------------------------------------------------
    # BRAIN
    # --------------------------------------------------------

    with st.spinner(
        "FAJ Brain рассчитывает прогноз..."
    ):

        try:
            prediction = calculate_prediction(
                home_team=home_team.strip(),
                away_team=away_team.strip(),
                home_records=home_records,
                away_records=away_records,
            )

        except Exception as exc:

            st.error(
                "Ошибка FAJ Brain."
            )

            st.exception(exc)

            return

    if not prediction:
        st.error(
            "FAJ Brain вернул пустой результат."
        )
        return

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    render_main_result(
        prediction,
        home_team.strip(),
        away_team.strip(),
    )

    st.divider()

    render_confidence(
        prediction
    )

    render_conclusion(
        prediction
    )

    st.divider()

    # --------------------------------------------------------
    # MODEL DETAILS
    # --------------------------------------------------------

    render_goal_model(
        prediction
    )

    render_probability_model(
        prediction
    )

    render_score_predictor(
        prediction
    )

    render_form_diagnostics(
        prediction
    )

    # --------------------------------------------------------
    # QUALITY / DIAGNOSTICS
    # --------------------------------------------------------

    st.divider()

    render_data_quality(
        prediction
    )

    render_diagnostics(
        prediction
    )

    render_brain_result(
        prediction
    )

    render_raw_prediction(
        prediction
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
