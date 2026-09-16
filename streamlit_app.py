#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Standalone Streamlit entrypoint

ARCHITECTURE
------------
UI -> FAJBrain -> canonical mathematical organs

The UI does NOT calculate:
- Poisson
- 1X2
- BTTS
- Totals
- xG / lambda
- exact-score probabilities
- corners model
- cards model
- Pair Rating
- Winner Synthesis
- ETC / Learning

The UI only:
- collects six historical matches
- builds FormContext
- calls FAJBrain
- displays Brain results
- displays factual historical averages
- displays diagnostics

Missing values remain None.
Missing != 0.
"""

from __future__ import annotations

from datetime import date, datetime
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

st.set_page_config(
    page_title="FAJ Brain",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# COMMON HELPERS
# ============================================================

def safe_float(value: Any) -> Optional[float]:
    """
    Convert a scalar to float.

    Dict/list/None stay None.
    Missing values are never converted to zero.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (dict, list, tuple, set)):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> Optional[int]:
    """
    Convert a scalar to int.
    Missing values remain None.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (dict, list, tuple, set)):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def pct01(value: Any, digits: int = 1) -> str:
    """
    Format a probability/confidence.

    Canonical Brain values are expected to be 0..1.
    If a value is already 0..100, preserve it as percentage.
    """
    number = safe_float(value)

    if number is None:
        return "—"

    if 0.0 <= number <= 1.0:
        number *= 100.0

    return f"{number:.{digits}f}%"


def number(value: Any, digits: int = 2) -> str:
    """
    Display numeric value without inventing a zero.
    """
    number_value = safe_float(value)

    if number_value is None:
        return "—"

    return f"{number_value:.{digits}f}"


def value_or_dash(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            if isinstance(result, dict):
                return result
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            pass

    return {}


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def display_date(value: Any) -> str:
    parsed = parse_date(value)

    if parsed is None:
        return value_or_dash(value)

    return parsed.strftime("%d.%m.%Y")


def get_field(record: Any, *names: str) -> Any:
    """
    Read a field from dict/object without inventing values.
    """
    if record is None:
        return None

    if isinstance(record, dict):
        for name in names:
            if name in record:
                return record.get(name)

    for name in names:
        if hasattr(record, name):
            try:
                return getattr(record, name)
            except Exception:
                pass

    return None


# ============================================================
# STREAMLIT STATE
# ============================================================

def init_state() -> None:
    defaults = {
        "faj_competition": "",
        "faj_forecast_date": date.today(),
        "faj_home_team": None,
        "faj_away_team": None,
        "faj_home_matches": [],
        "faj_away_matches": [],
        "faj_home_context": None,
        "faj_away_context": None,
        "faj_prediction": None,
        "faj_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================
# PARSER
# ============================================================

@st.cache_resource
def get_parser() -> Soccer365Parser:
    return Soccer365Parser()


@st.cache_resource
def get_brain() -> FAJBrain:
    return FAJBrain()


# ============================================================
# TEAM LIST
# ============================================================

def load_teams() -> List[str]:
    parser = get_parser()

    candidates = (
        "get_all_teams",
        "get_teams",
        "load_teams",
    )

    for method_name in candidates:
        method = getattr(parser, method_name, None)

        if not callable(method):
            continue

        try:
            result = method()

            if isinstance(result, dict):
                result = list(result.keys())

            if isinstance(result, (list, tuple, set)):
                teams = []

                for item in result:
                    if isinstance(item, str):
                        teams.append(item)
                    elif isinstance(item, dict):
                        name = first_not_none(
                            item.get("name"),
                            item.get("team_name"),
                            item.get("title"),
                        )
                        if name:
                            teams.append(str(name))

                teams = sorted(set(teams), key=str.lower)

                if teams:
                    return teams

        except Exception:
            continue

    return []


# ============================================================
# HISTORY NORMALIZATION
# ============================================================

def normalize_records(records: List[Any]) -> List[Dict[str, Any]]:
    """
    Normalize parser records into the shape expected by
    FormContext / FAJBrain.

    No missing value is replaced by zero.
    """
    normalized: List[Dict[str, Any]] = []

    for record in records:
        if isinstance(record, dict):
            item = dict(record)
        else:
            item = as_dict(record)

        if not item:
            continue

        normalized.append(item)

    return normalized


def record_date(record: Dict[str, Any]) -> Optional[date]:
    return parse_date(
        first_not_none(
            record.get("date"),
            record.get("match_date"),
            record.get("game_date"),
        )
    )


def collect_team_history(
    parser: Soccer365Parser,
    team_name: str,
    forecast_date: Optional[date],
) -> List[Dict[str, Any]]:
    """
    Get team history from Soccer365/parser.

    The final six matches are kept in chronological order:
    oldest -> newest.
    """
    methods = (
        "get_team_last_matches",
        "get_last_matches",
        "get_team_history",
        "get_team_matches",
        "parse_team_results",
    )

    raw_records = None

    for method_name in methods:
        method = getattr(parser, method_name, None)

        if not callable(method):
            continue

        attempts = (
            {"team_name": team_name, "limit": HISTORY_SIZE},
            {"team": team_name, "limit": HISTORY_SIZE},
            {"team_name": team_name},
            {"team": team_name},
        )

        for kwargs in attempts:
            try:
                result = method(**kwargs)

                if isinstance(result, dict):
                    for key in (
                        "matches",
                        "results",
                        "history",
                        "data",
                    ):
                        if isinstance(result.get(key), list):
                            result = result[key]
                            break

                if isinstance(result, (list, tuple)):
                    raw_records = list(result)
                    break

            except TypeError:
                continue
            except Exception:
                continue

        if raw_records is not None:
            break

    if raw_records is None:
        return []

    records = normalize_records(raw_records)

    if forecast_date is not None:
        filtered = []

        for record in records:
            match_date = record_date(record)

            if match_date is None:
                filtered.append(record)
                continue

            if match_date < forecast_date:
                filtered.append(record)

        records = filtered

    records.sort(
        key=lambda item: (
            record_date(item) is None,
            record_date(item) or date.min,
        )
    )

    return records[-HISTORY_SIZE:]


# ============================================================
# FORM CONTEXT
# ============================================================

def make_form_context(
    team_name: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Current FormContext v1.7 contract.
    """
    return build_form_context(
        team_name,
        records,
        limit=HISTORY_SIZE,
    )


# ============================================================
# FACTUAL HISTORY STATISTICS
# ============================================================

def numeric_values(
    records: List[Dict[str, Any]],
    *keys: str,
) -> List[float]:
    values: List[float] = []

    for record in records:
        value = get_field(record, *keys)
        number_value = safe_float(value)

        if number_value is not None:
            values.append(number_value)

    return values


def average(
    records: List[Dict[str, Any]],
    *keys: str,
) -> Optional[float]:
    values = numeric_values(records, *keys)

    if not values:
        return None

    return sum(values) / len(values)


def render_average_metric(
    label: str,
    records: List[Dict[str, Any]],
    *keys: str,
) -> None:
    value = average(records, *keys)
    st.metric(label, number(value))


def render_history_summary(
    team_name: str,
    records: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> None:
    st.markdown(f"#### {team_name} — последние {len(records)} матчей")

    if not records:
        st.warning("История матчей не собрана.")
        return

    columns = st.columns(4)

    with columns[0]:
        render_average_metric(
            "Голы забито",
            records,
            "goals_for",
            "gf",
            "home_goals",
        )

    with columns[1]:
        render_average_metric(
            "Голы пропущено",
            records,
            "goals_against",
            "ga",
            "away_goals",
        )

    with columns[2]:
        xg = first_not_none(
            context.get("xg"),
            context.get("recent_xg"),
        )
        st.metric("xG среднее", number(xg))

    with columns[3]:
        xga = first_not_none(
            context.get("xga"),
            context.get("recent_xga"),
        )
        st.metric("xGA среднее", number(xga))

    columns = st.columns(4)

    with columns[0]:
        st.metric(
            "Угловые за",
            number(context.get("corners_for_avg")),
        )

    with columns[1]:
        st.metric(
            "Угловые против",
            number(context.get("corners_against_avg")),
        )

    with columns[2]:
        st.metric(
            "Карточки команды",
            number(context.get("team_cards_avg")),
        )

    with columns[3]:
        st.metric(
            "Карточки соперника",
            number(context.get("opponent_cards_avg")),
        )


# ============================================================
# FORM CONTEXT DISPLAY
# ============================================================

def render_form_context(
    team_name: str,
    context: Optional[Dict[str, Any]],
) -> None:
    if not context:
        st.warning(f"FormContext для {team_name} отсутствует.")
        return

    form = context.get("form")

    st.markdown(f"#### FormContext — {team_name}")

    columns = st.columns(4)

    with columns[0]:
        st.metric(
            "Матчей",
            value_or_dash(context.get("matches_count")),
        )

    with columns[1]:
        st.metric(
            "Форма",
            value_or_dash(form),
        )

    with columns[2]:
        st.metric(
            "xG",
            number(
                first_not_none(
                    context.get("xg"),
                    context.get("recent_xg"),
                )
            ),
        )

    with columns[3]:
        st.metric(
            "xGA",
            number(
                first_not_none(
                    context.get("xga"),
                    context.get("recent_xga"),
                )
            ),
        )

    columns = st.columns(4)

    with columns[0]:
        st.metric(
            "Угловые за",
            number(context.get("corners_for_avg")),
        )

    with columns[1]:
        st.metric(
            "Угловые против",
            number(context.get("corners_against_avg")),
        )

    with columns[2]:
        st.metric(
            "Карточки",
            number(context.get("team_cards_avg")),
        )

    with columns[3]:
        st.metric(
            "Карточки соперника",
            number(context.get("opponent_cards_avg")),
        )

    with st.expander("История FormContext"):
        history = {
            "M1 → M6 результаты": context.get("results_history"),
            "Голы за": context.get("goals_for_history"),
            "Голы против": context.get("goals_against_history"),
            "xG": context.get("team_xg_history"),
            "xGA соперника": context.get("opponent_xg_history"),
            "Угловые за": context.get("corners_for_history"),
            "Угловые против": context.get("corners_against_history"),
            "Карточки команды": context.get("team_cards_history"),
            "Карточки соперника": context.get("opponent_cards_history"),
            "Сложность": context.get("difficulty_history"),
            "Площадка": context.get("venue_history"),
        }

        st.json(history)


# ============================================================
# BRAIN
# ============================================================

def build_prediction(
    home_team: str,
    away_team: str,
    home_records: List[Dict[str, Any]],
    away_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    The only mathematical call in the UI.

    No Pair Rating.
    No Winner Synthesis.
    No UI-side formulas.
    """
    brain = get_brain()

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_records,
        away_matches=away_records,
    )

    prediction = as_dict(result)

    if not prediction:
        raise RuntimeError("FAJBrain returned an empty result.")

    return prediction


# ============================================================
# PROBABILITY DISPLAY
# ============================================================

def render_1x2(prediction: Dict[str, Any]) -> None:
    st.markdown("### 1X2")

    columns = st.columns(3)

    with columns[0]:
        st.metric(
            "Победа хозяев",
            pct01(prediction.get("home_win_probability")),
        )

    with columns[1]:
        st.metric(
            "Ничья",
            pct01(prediction.get("draw_probability")),
        )

    with columns[2]:
        st.metric(
            "Победа гостей",
            pct01(prediction.get("away_win_probability")),
        )


def render_goals_probabilities(
    prediction: Dict[str, Any],
) -> None:
    st.markdown("### Голы")

    columns = st.columns(4)

    with columns[0]:
        st.metric(
            "BTTS",
            pct01(prediction.get("btts_probability")),
        )

    with columns[1]:
        st.metric(
            "ТБ 1.5",
            pct01(prediction.get("over15_probability")),
        )

    with columns[2]:
        st.metric(
            "ТБ 2.5",
            pct01(prediction.get("over25_probability")),
        )

    with columns[3]:
        st.metric(
            "ТБ 3.5",
            pct01(prediction.get("over35_probability")),
        )


# ============================================================
# SCORE DISPLAY
# ============================================================

def render_scores(prediction: Dict[str, Any]) -> None:
    st.markdown("### Прогноз счёта")

    primary = first_not_none(
        prediction.get("predicted_score"),
        prediction.get("most_likely_score"),
    )

    second = prediction.get("second_score")
    third = prediction.get("third_score")

    columns = st.columns(3)

    with columns[0]:
        st.markdown("**Основной счёт**")
        st.markdown(f"## {value_or_dash(primary)}")

    with columns[1]:
        st.markdown("**Второй вариант**")
        st.markdown(f"## {value_or_dash(second)}")

    with columns[2]:
        st.markdown("**Третий вариант**")
        st.markdown(f"## {value_or_dash(third)}")

    top_scores = prediction.get("top_scores")

    if top_scores:
        with st.expander("Все top scores"):
            st.write(top_scores)


# ============================================================
# XG DISPLAY
# ============================================================

def render_xg(prediction: Dict[str, Any]) -> None:
    st.markdown("### Ожидаемые голы")

    columns = st.columns(2)

    with columns[0]:
        st.metric(
            "Хозяева xG",
            number(prediction.get("home_xg")),
        )

    with columns[1]:
        st.metric(
            "Гости xG",
            number(prediction.get("away_xg")),
        )


# ============================================================
# CORNERS / CARDS
# ============================================================

def render_corners(prediction: Dict[str, Any]) -> None:
    st.markdown("### Угловые")

    columns = st.columns(3)

    with columns[0]:
        st.metric(
            "Хозяева",
            number(prediction.get("home_corners_expected")),
        )

    with columns[1]:
        st.metric(
            "Гости",
            number(prediction.get("away_corners_expected")),
        )

    with columns[2]:
        st.metric(
            "Всего",
            number(prediction.get("corners_expected")),
        )


def render_cards(prediction: Dict[str, Any]) -> None:
    st.markdown("### Карточки")

    columns = st.columns(3)

    with columns[0]:
        st.metric(
            "Хозяева",
            number(prediction.get("home_cards_expected")),
        )

    with columns[1]:
        st.metric(
            "Гости",
            number(prediction.get("away_cards_expected")),
        )

    with columns[2]:
        st.metric(
            "Всего",
            number(prediction.get("cards_expected")),
        )


# ============================================================
# CONFIDENCE / RISK
# ============================================================

def render_confidence(prediction: Dict[str, Any]) -> None:
    st.markdown("### Уверенность")

    columns = st.columns(2)

    with columns[0]:
        st.metric(
            "Confidence",
            pct01(prediction.get("confidence")),
        )

    with columns[1]:
        risk = prediction.get("risk")

        if risk is None or risk == "":
            risk_text = "—"
        else:
            risk_text = str(risk)

        st.metric(
            "Risk",
            risk_text,
        )


# ============================================================
# DIAGNOSTICS
# ============================================================

def render_diagnostics(prediction: Dict[str, Any]) -> None:
    with st.expander("Диагностика FAJ Brain"):
        diagnostics = prediction.get("diagnostics")

        if diagnostics:
            st.json(diagnostics)
        else:
            st.write("Диагностика отсутствует.")

        data_quality = prediction.get("data_quality")

        st.markdown("#### Data Quality")

        if isinstance(data_quality, dict):
            st.json(data_quality)
        elif data_quality is None:
            st.write("—")
        else:
            st.write(data_quality)

    brain_result = prediction.get("brain_result")

    if brain_result:
        with st.expander("Полный результат органов FAJ Brain"):
            st.json(as_dict(brain_result))


# ============================================================
# GOAL MODEL DIAGNOSTICS
# ============================================================

def render_goal_model(prediction: Dict[str, Any]) -> None:
    brain_result = prediction.get("brain_result")

    if not isinstance(brain_result, dict):
        return

    goal_model = brain_result.get("goal_model")

    if not goal_model:
        return

    with st.expander("GoalModel"):
        st.json(as_dict(goal_model))


# ============================================================
# MATCH HISTORY TABLE
# ============================================================

def render_match_history(
    title: str,
    records: List[Dict[str, Any]],
) -> None:
    st.markdown(f"#### {title}")

    if not records:
        st.write("Нет данных.")
        return

    rows = []

    for index, record in enumerate(records, start=1):
        rows.append(
            {
                "M": f"M{index}",
                "Дата": display_date(
                    first_not_none(
                        record.get("date"),
                        record.get("match_date"),
                    )
                ),
                "Матч": (
                    f"{value_or_dash(record.get('home'))} — "
                    f"{value_or_dash(record.get('away'))}"
                ),
                "Счёт": value_or_dash(
                    first_not_none(
                        record.get("score"),
                        record.get("result"),
                    )
                ),
                "xG": number(
                    first_not_none(
                        record.get("xg"),
                        record.get("team_xg"),
                        record.get("external_xg"),
                    )
                ),
                "Угл.": number(
                    first_not_none(
                        record.get("corners"),
                        record.get("corners_for"),
                    ),
                    digits=1,
                ),
                "Карты": number(
                    first_not_none(
                        record.get("cards"),
                        record.get("team_cards"),
                    ),
                    digits=1,
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# MAIN UI
# ============================================================

def main() -> None:
    init_state()

    st.title("⚽ FAJ Brain")
    st.caption(
        f"FAJ Platform v12.1 · Standalone Streamlit · {APP_VERSION}"
    )

    st.info(
        "Математический источник результата — FAJBrain. "
        "UI не пересчитывает прогноз и не использует Pair Rating "
        "или Winner Synthesis."
    )

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:
        st.header("Матч")

        teams = load_teams()

        if not teams:
            st.warning(
                "Список команд не удалось получить из Soccer365Parser."
            )
            st.write(
                "Можно продолжить только если список команд "
                "доступен через текущий parser."
            )
            return

        home_default = (
            st.session_state.get("faj_home_team")
            if st.session_state.get("faj_home_team") in teams
            else teams[0]
        )

        away_default = (
            st.session_state.get("faj_away_team")
            if st.session_state.get("faj_away_team") in teams
            else teams[1] if len(teams) > 1 else teams[0]
        )

        home_team = st.selectbox(
            "Хозяева",
            teams,
            index=teams.index(home_default),
            key="faj_home_team_select",
        )

        away_team = st.selectbox(
            "Гости",
            teams,
            index=teams.index(away_default),
            key="faj_away_team_select",
        )

        forecast_date = st.date_input(
            "Дата матча",
            value=st.session_state.get(
                "faj_forecast_date",
                date.today(),
            ),
            key="faj_forecast_date",
        )

        competition = st.text_input(
            "Турнир",
            value=st.session_state.get(
                "faj_competition",
                "",
            ),
            key="faj_competition_input",
        )

        st.markdown("---")

        if st.button(
            "📥 Загрузить последние 6 матчей",
            use_container_width=True,
        ):
            st.session_state.faj_error = None

            try:
                parser = get_parser()

                home_records = collect_team_history(
                    parser,
                    home_team,
                    forecast_date,
                )

                away_records = collect_team_history(
                    parser,
                    away_team,
                    forecast_date,
                )

                if not home_records:
                    raise RuntimeError(
                        f"Не удалось получить историю для {home_team}."
                    )

                if not away_records:
                    raise RuntimeError(
                        f"Не удалось получить историю для {away_team}."
                    )

                st.session_state.faj_home_team = home_team
                st.session_state.faj_away_team = away_team
                st.session_state.faj_forecast_date = forecast_date
                st.session_state.faj_competition = competition

                st.session_state.faj_home_matches = home_records
                st.session_state.faj_away_matches = away_records

                st.session_state.faj_home_context = make_form_context(
                    home_team,
                    home_records,
                )

                st.session_state.faj_away_context = make_form_context(
                    away_team,
                    away_records,
                )

                st.session_state.faj_prediction = None

                st.success(
                    f"Загружено: "
                    f"{len(home_records)} + {len(away_records)} матчей."
                )

            except Exception as exc:
                st.session_state.faj_error = str(exc)

        if st.button(
            "🧠 Рассчитать прогноз",
            use_container_width=True,
        ):
            st.session_state.faj_error = None

            home_records = st.session_state.get(
                "faj_home_matches",
                [],
            )

            away_records = st.session_state.get(
                "faj_away_matches",
                [],
            )

            if not home_records or not away_records:
                st.session_state.faj_error = (
                    "Сначала загрузите последние 6 матчей обеих команд."
                )
            else:
                try:
                    prediction = build_prediction(
                        home_team,
                        away_team,
                        home_records,
                        away_records,
                    )

                    st.session_state.faj_prediction = prediction

                except Exception as exc:
                    st.session_state.faj_error = str(exc)

        st.markdown("---")

        st.caption("Архитектура")
        st.code(
            "6 HOME + 6 AWAY\n"
            "      ↓\n"
            "FormContext\n"
            "      ↓\n"
            "FormModel / FormWin / Defence\n"
            "      ↓\n"
            "GoalModel\n"
            "      ↓\n"
            "λH / λA\n"
            "      ↓\n"
            "ProbabilityModel\n"
            "      ↓\n"
            "ScorePredictor\n"
            "      ↓\n"
            "FAJBrain FINAL",
            language="text",
        )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    if st.session_state.get("faj_error"):
        st.error(st.session_state.faj_error)

    # --------------------------------------------------------
    # CURRENT DATA
    # --------------------------------------------------------

    home_team = st.session_state.get("faj_home_team") or home_team
    away_team = st.session_state.get("faj_away_team") or away_team

    home_records = st.session_state.get(
        "faj_home_matches",
        [],
    )

    away_records = st.session_state.get(
        "faj_away_matches",
        [],
    )

    home_context = st.session_state.get(
        "faj_home_context"
    )

    away_context = st.session_state.get(
        "faj_away_context"
    )

    prediction = st.session_state.get(
        "faj_prediction"
    )

    # --------------------------------------------------------
    # MATCH HEADER
    # --------------------------------------------------------

    st.markdown("---")

    columns = st.columns([2, 1, 2])

    with columns[0]:
        st.markdown(f"# {home_team}")

    with columns[1]:
        st.markdown(
            "<div style='text-align:center;font-size:28px;"
            "padding-top:10px;'>VS</div>",
            unsafe_allow_html=True,
        )

    with columns[2]:
        st.markdown(
            f"<div style='text-align:right'>"
            f"<h1>{away_team}</h1>"
            f"</div>",
            unsafe_allow_html=True,
        )

    competition = st.session_state.get(
        "faj_competition",
        "",
    )

    forecast_date = st.session_state.get(
        "faj_forecast_date"
    )

    caption_parts = []

    if competition:
        caption_parts.append(str(competition))

    if forecast_date:
        caption_parts.append(display_date(forecast_date))

    if caption_parts:
        st.caption(" · ".join(caption_parts))

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    if home_records or away_records:
        st.markdown("---")
        st.header("📚 Фактическая база")

        tab_home, tab_away = st.tabs(
            [
                f"{home_team} — 6 матчей",
                f"{away_team} — 6 матчей",
            ]
        )

        with tab_home:
            if home_context:
                render_history_summary(
                    home_team,
                    home_records,
                    home_context,
                )

                render_form_context(
                    home_team,
                    home_context,
                )

            render_match_history(
                home_team,
                home_records,
            )

        with tab_away:
            if away_context:
                render_history_summary(
                    away_team,
                    away_records,
                    away_context,
                )

                render_form_context(
                    away_team,
                    away_context,
                )

            render_match_history(
                away_team,
                away_records,
            )

    # --------------------------------------------------------
    # PREDICTION
    # --------------------------------------------------------

    if prediction:
        st.markdown("---")
        st.header("🧠 FAJ Brain — прогноз")

        render_confidence(prediction)

        st.markdown("---")

        render_xg(prediction)

        st.markdown("---")

        render_1x2(prediction)

        st.markdown("---")

        render_goals_probabilities(prediction)

        st.markdown("---")

        render_scores(prediction)

        st.markdown("---")

        render_corners(prediction)

        st.markdown("---")

        render_cards(prediction)

        # ----------------------------------------------------
        # CONCLUSION
        # ----------------------------------------------------

        conclusion = prediction.get("conclusion")

        if conclusion:
            st.markdown("---")
            st.markdown("### Аналитический вывод")
            st.info(str(conclusion))

        # ----------------------------------------------------
        # DIAGNOSTICS
        # ----------------------------------------------------

        st.markdown("---")

        render_goal_model(prediction)
        render_diagnostics(prediction)

    else:
        st.markdown("---")
        st.info(
            "Загрузите последние 6 матчей обеих команд, "
            "затем нажмите «Рассчитать прогноз»."
        )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.markdown("---")

    st.caption(
        "FAJ Platform v12.1 · "
        "Missing ≠ 0 · "
        "Prediction ≠ Fact · "
        "FAJBrain является единственным источником математического прогноза."
    )


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
