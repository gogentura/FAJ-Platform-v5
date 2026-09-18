#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PREDICTOR — Streamlit Interface (Brain v4.0 adapter)

Архитектура:

    Streamlit UI
        ↓
    Soccer365Parser
        ↓
    factual history
        ↓
    FAJBrain v4.0 .predict()
        ↓
    BrainPrediction
        ↓
    ТОЛЬКО ОТОБРАЖЕНИЕ

Streamlit НЕ считает:

    ❌ xG
    ❌ Poisson
    ❌ 1X2
    ❌ BTTS
    ❌ totals
    ❌ exact scores
    ❌ Pair Rating (расчёт)
    ❌ Winner Signal / Synthesis
    ❌ confidence
    ❌ risk
    ❌ corners
    ❌ cards

Всё приходит из FAJBrain v4.0 как BrainPrediction.

Pair Rating:
    ручной исследовательский сигнал / display only.
    В Brain v4.0 НЕ передаётся.
    В математическом ядре НЕ участвует.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from app.parsers.soccer365_parser import Soccer365Parser
from app.core.faj_brain import FAJBrain
from app.core.form_context import build_form_context
from app.faj_club_ratings import (
    get_all_tournaments,
    get_all_teams,
    get_team_rating,
)


# ============================================================
# CONFIG
# ============================================================

PAGE_TITLE = "FAJ — Персональный прогноз"
PAGE_ICON = "⚽"
LAYOUT = "wide"

MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6

PAIR_RATING_MIN = 60
PAIR_RATING_MAX = 100
PAIR_RATING_DEFAULT = 80

logger = logging.getLogger(__name__)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state="collapsed",
)


# ============================================================
# UI STYLE
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1200px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    .faj-match-title {
        text-align: center;
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0.4rem 0 1.2rem 0;
    }

    .faj-section {
        font-size: 1.15rem;
        font-weight: 650;
        margin-top: 1rem;
        margin-bottom: 0.65rem;
    }

    .faj-score-main {
        text-align: center;
        font-size: 2.15rem;
        font-weight: 800;
        margin: 0.2rem 0;
    }

    .faj-score-prob {
        text-align: center;
        opacity: 0.72;
        font-size: 0.9rem;
    }

    .faj-prob-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.55rem 0.2rem;
        border-bottom: 1px solid rgba(128,128,128,0.14);
    }

    .faj-prob-name {
        font-size: 1rem;
    }

    .faj-prob-value {
        font-size: 1rem;
        font-weight: 700;
    }

    .faj-history-row {
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.10);
    }

    .faj-muted {
        opacity: 0.68;
        font-size: 0.88rem;
    }

    .faj-main-result {
        border: 1px solid rgba(128,128,128,0.20);
        border-radius: 14px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SERVICES
# ============================================================

@st.cache_resource
def get_soccer365_parser() -> Soccer365Parser:
    return Soccer365Parser()


@st.cache_resource
def get_faj_brain() -> FAJBrain:
    return FAJBrain()


# ============================================================
# HELPERS
# ============================================================

def normalize_name(value: Any) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("ё", "е")
    )


def pct(value: Optional[float]) -> str:
    """
    UI formatter for probabilities.

    Brain:
        0..1

    UI:
        0..100%

    None:
        —
    """

    if value is None:
        return "—"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"

    if 0.0 <= value <= 1.0:
        value *= 100.0

    return f"{value:.1f}%"


def num(
    value: Optional[float],
    digits: int = 2,
) -> str:

    if value is None:
        return "—"

    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def safe_float(value: Any) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_not_none(
    *values: Any,
) -> Any:

    for value in values:
        if value is not None:
            return value

    return None


def parse_score(
    score: Any,
) -> tuple[Optional[int], Optional[int]]:

    if not score:
        return None, None

    text = (
        str(score)
        .strip()
        .replace("–", "-")
        .replace(":", "-")
    )

    parts = text.split("-")

    if len(parts) != 2:
        return None, None

    try:
        return (
            int(parts[0].strip()),
            int(parts[1].strip()),
        )
    except ValueError:
        return None, None


def parse_date_value(
    value: Any,
) -> Optional[date]:

    if value is None:
        return None

    text = str(value).strip()

    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        text,
    )

    if match:

        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            return None

    match = re.search(
        r"(\d{2})\.(\d{2})\.(\d{4})",
        text,
    )

    if match:

        try:
            return date(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
            )
        except ValueError:
            return None

    return None


# ============================================================
# JSON / TECHNICAL DISPLAY ONLY
# ============================================================

def json_safe(value: Any) -> Any:
    """
    Convert internal structures to JSON-safe structures
    ONLY for Streamlit technical display.

    IMPORTANT:
        This does not modify Brain data.
        Tuple keys are converted to strings only here.
    """

    if isinstance(value, dict):

        result = {}

        for key, item in value.items():

            if isinstance(
                key,
                (str, int, float, bool),
            ) or key is None:

                safe_key = key

            else:

                safe_key = str(key)

            result[safe_key] = json_safe(
                item
            )

        return result

    if isinstance(
        value,
        (list, tuple),
    ):

        return [
            json_safe(item)
            for item in value
        ]

    if isinstance(value, set):

        return [
            json_safe(item)
            for item in value
        ]

    if hasattr(
        value,
        "__dataclass_fields__",
    ):

        return json_safe(
            asdict(value)
        )

    try:

        json.dumps(value)

        return value

    except Exception:

        return str(value)


# ============================================================
# SESSION STATE
# ============================================================

def init_state() -> None:

    defaults = {
        "faj_competition": None,
        "faj_matches": [],
        "faj_collected": {},
        "faj_predictions": {},
        "faj_form_context": {},
        "faj_session_id": None,
        "faj_selected_match": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:

            st.session_state[key] = value


def reset_workspace() -> None:

    st.session_state.faj_competition = None
    st.session_state.faj_matches = []
    st.session_state.faj_collected = {}
    st.session_state.faj_predictions = {}
    st.session_state.faj_form_context = {}
    st.session_state.faj_session_id = None
    st.session_state.faj_selected_match = None


def create_match_slot() -> Dict[str, Any]:

    return {
        "home_name": None,
        "away_name": None,
        "match_date": date.today().isoformat(),

        # ------------------------------------------------
        # Ручной Pair Rating — display / research only.
        # В Brain v4.0 НЕ передаётся.
        # ------------------------------------------------

        "home_pair_rating":
            PAIR_RATING_DEFAULT,

        "away_pair_rating":
            PAIR_RATING_DEFAULT,

        "urls_home":
            [""] * MAX_HISTORY_MATCHES,

        "urls_away":
            [""] * MAX_HISTORY_MATCHES,
    }


def add_match() -> None:

    if (
        len(
            st.session_state.faj_matches
        )
        >= MAX_ANALYSIS_MATCHES
    ):

        st.warning(
            f"Можно добавить максимум "
            f"{MAX_ANALYSIS_MATCHES} матчей."
        )

        return

    st.session_state.faj_matches.append(
        create_match_slot()
    )


def remove_match(
    index: int,
) -> None:

    if (
        0 <= index
        < len(
            st.session_state.faj_matches
        )
    ):

        st.session_state.faj_matches.pop(
            index
        )

        st.session_state.faj_collected.pop(
            index,
            None,
        )

        st.session_state.faj_predictions.pop(
            index,
            None,
        )

        st.session_state.faj_form_context.pop(
            index,
            None,
        )


# ============================================================
# TEAM SOURCE
# ============================================================

def load_teams(
    league: Optional[str] = None,
) -> List[str]:

    try:

        teams = get_all_teams(
            league
        )

        return (
            list(teams)
            if teams
            else []
        )

    except Exception:

        logger.exception(
            "Ошибка загрузки команд"
        )

        return []


# ============================================================
# PARSER
# ============================================================

def parse_soccer365(
    url: str,
) -> Dict[str, Any]:

    parser = get_soccer365_parser()

    return parser.parse(
        url.strip()
    )


# ============================================================
# FACTUAL HISTORY RECORD
# ============================================================

def build_history_record(
    parsed: Dict[str, Any],
) -> Dict[str, Any]:

    stats = parsed.get(
        "stats",
        {},
    )

    if not isinstance(
        stats,
        dict,
    ):

        stats = {}

    home_goals, away_goals = parse_score(
        parsed.get("score")
    )

    return {

        "home_team":
            parsed.get("home_team"),

        "away_team":
            parsed.get("away_team"),

        "match_date":
            parsed.get("match_date"),

        "score":
            parsed.get("score"),

        "home_goals":
            home_goals,

        "away_goals":
            away_goals,

        "xg": {
            "home":
                stats.get("home_xg"),

            "away":
                stats.get("away_xg"),
        },

        "shots": {
            "home":
                stats.get("home_shots"),

            "away":
                stats.get("away_shots"),
        },

        "shots_on_target": {
            "home":
                stats.get(
                    "home_shots_on_target"
                ),

            "away":
                stats.get(
                    "away_shots_on_target"
                ),
        },

        "blocked_shots": {
            "home":
                stats.get(
                    "home_blocked_shots"
                ),

            "away":
                stats.get(
                    "away_blocked_shots"
                ),
        },

        "big_chances": {
            "home":
                stats.get(
                    "home_big_chances"
                ),

            "away":
                stats.get(
                    "away_big_chances"
                ),
        },

        "possession": {
            "home":
                stats.get(
                    "home_possession"
                ),

            "away":
                stats.get(
                    "away_possession"
                ),
        },

        "passes": {
            "home":
                stats.get(
                    "home_total_passes"
                ),

            "away":
                stats.get(
                    "away_total_passes"
                ),
        },

        "pass_accuracy": {
            "home":
                stats.get(
                    "home_pass_accuracy"
                ),

            "away":
                stats.get(
                    "away_pass_accuracy"
                ),
        },

        "crosses": {
            "home":
                stats.get(
                    "home_crosses"
                ),

            "away":
                stats.get(
                    "away_crosses"
                ),
        },

        "throw_ins": {
            "home":
                stats.get(
                    "home_throw_ins"
                ),

            "away":
                stats.get(
                    "away_throw_ins"
                ),
        },

        "fouls": {
            "home":
                stats.get(
                    "home_fouls"
                ),

            "away":
                stats.get(
                    "away_fouls"
                ),
        },

        "offsides": {
            "home":
                stats.get(
                    "home_offsides"
                ),

            "away":
                stats.get(
                    "away_offsides"
                ),
        },

        "yellow_cards": {
            "home":
                stats.get(
                    "home_yellow_cards"
                ),

            "away":
                stats.get(
                    "away_yellow_cards"
                ),
        },

        "red_cards": {
            "home":
                stats.get(
                    "home_red_cards"
                ),

            "away":
                stats.get(
                    "away_red_cards"
                ),
        },

        "corners": {
            "home":
                stats.get(
                    "home_corners"
                ),

            "away":
                stats.get(
                    "away_corners"
                ),
        },

        "home_corners":
            stats.get(
                "home_corners"
            ),

        "away_corners":
            stats.get(
                "away_corners"
            ),

        "home_yellow_cards":
            stats.get(
                "home_yellow_cards"
            ),

        "away_yellow_cards":
            stats.get(
                "away_yellow_cards"
            ),

        "stats":
            dict(stats),

        "source_url":
            parsed.get(
                "source_url"
            ),

        "quality":
            parsed.get(
                "quality",
                parsed.get(
                    "data_quality"
                ),
            ),

        "source":
            "Soccer365",

        "parser_version":
            parsed.get(
                "parser_version"
            ),
    }


# ============================================================
# MATCH VALIDATION
# ============================================================

def validate_parsed_match(
    parsed: Dict[str, Any],
    selected_team: str,
) -> tuple[bool, str]:

    home = parsed.get(
        "home_team"
    )

    away = parsed.get(
        "away_team"
    )

    if not home or not away:

        return (
            False,
            "Не удалось определить команды.",
        )

    target = normalize_name(
        selected_team
    )

    if (
        target != normalize_name(home)
        and
        target != normalize_name(away)
    ):

        return (
            False,
            f"Матч {home} — {away} "
            f"не содержит {selected_team}.",
        )

    return (
        True,
        f"{home} — {away}",
    )


# ============================================================
# COLLECT TEAM HISTORY
# ============================================================

def collect_team_history(
    team_name: str,
    urls: List[str],
    forecast_date: Optional[str] = None,
) -> tuple[
    List[Dict[str, Any]],
    List[str],
]:

    clean_urls = [
        url.strip()
        for url in urls
        if url and url.strip()
    ]

    clean_urls = list(
        dict.fromkeys(
            clean_urls
        )
    )

    records: List[
        Dict[str, Any]
    ] = []

    errors: List[str] = []

    forecast_date_obj = (
        parse_date_value(
            forecast_date
        )
        if forecast_date
        else None
    )

    if (
        forecast_date
        and not forecast_date_obj
    ):

        errors.append(
            f"Некорректная дата "
            f"прогноза: {forecast_date}"
        )

        return records, errors

    for position, url in enumerate(
        clean_urls,
        start=1,
    ):

        try:

            parsed = parse_soccer365(
                url
            )

        except Exception as exc:

            errors.append(
                f"{position}. {exc}"
            )

            continue

        if parsed.get("error"):

            errors.append(
                f"{position}. "
                f"{parsed.get('error')}"
            )

            continue

        valid, message = (
            validate_parsed_match(
                parsed,
                team_name,
            )
        )

        if not valid:

            errors.append(
                f"{position}. {message}"
            )

            continue

        record = build_history_record(
            parsed
        )

        record["team"] = team_name
        record["team_name"] = team_name

        if (
            normalize_name(
                parsed.get(
                    "home_team"
                )
            )
            ==
            normalize_name(
                team_name
            )
        ):

            record["is_home"] = True
            record["venue"] = "home"

        elif (
            normalize_name(
                parsed.get(
                    "away_team"
                )
            )
            ==
            normalize_name(
                team_name
            )
        ):

            record["is_home"] = False
            record["venue"] = "away"

        else:

            errors.append(
                f"{position}. "
                f"Не удалось определить "
                f"сторону {team_name}."
            )

            continue

        match_date = record.get(
            "match_date"
        )

        if not match_date:

            errors.append(
                f"{position}. "
                f"Не удалось определить "
                f"дату матча."
            )

            continue

        match_date_obj = (
            parse_date_value(
                match_date
            )
        )

        if not match_date_obj:

            errors.append(
                f"{position}. "
                f"Некорректная дата: "
                f"{match_date}"
            )

            continue

        if (
            forecast_date_obj
            and
            match_date_obj
            >= forecast_date_obj
        ):

            errors.append(
                f"{position}. "
                f"Матч от {match_date} "
                f"не является прошлым "
                f"относительно "
                f"{forecast_date}."
            )

            continue

        records.append(
            record
        )

    # Старые → новые

    records.sort(
        key=lambda item: (
            parse_date_value(
                item.get(
                    "match_date"
                )
            )
            or date.min
        )
    )

    records = records[
        -MAX_HISTORY_MATCHES:
    ]

    return records, errors


# ============================================================
# FORM CONTEXT
# ============================================================

def make_form_context(
    team_name: str,
    records: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

    if not records:
        return None

    try:

        context = build_form_context(
            team_name=team_name,
            records=records,
        )

        if isinstance(
            context,
            dict,
        ):

            return context

        if hasattr(
            context,
            "__dict__",
        ):

            return vars(context)

        return context

    except Exception:

        logger.exception(
            "Ошибка построения FormContext"
        )

        return None


# ============================================================
# BUILD PREDICTION
# ============================================================

def build_prediction(
    home_team: str,
    away_team: str,
    history_home: List[Dict[str, Any]],
    history_away: List[Dict[str, Any]],
    home_pair_rating: Optional[int] = None,
    away_pair_rating: Optional[int] = None,
) -> Dict[str, Any]:
    """
    FAJ Brain v4.0 adapter.

    Pair Rating intentionally remains outside Brain.
    """

    brain = get_faj_brain()

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_history=history_home,
        away_history=history_away,
    )

    if hasattr(
        result,
        "__dataclass_fields__",
    ):

        prediction = asdict(
            result
        )

    elif hasattr(
        result,
        "to_dict",
    ):

        prediction = result.to_dict()

    elif isinstance(
        result,
        dict,
    ):

        prediction = dict(result)

    else:

        raise TypeError(
            "FAJBrain.predict() "
            "вернул неподдерживаемый тип: "
            f"{type(result).__name__}"
        )

    return prediction


# ============================================================
# COLLECT MATCH
# ============================================================

def collect_and_store_match(
    index: int,
    match: Dict[str, Any],
) -> None:

    home_team = match.get(
        "home_name"
    )

    away_team = match.get(
        "away_name"
    )

    if not home_team or not away_team:

        st.error(
            "Сначала выберите обе команды."
        )

        return

    forecast_date = match.get(
        "match_date"
    )

    with st.spinner(
        "Собираю историю матчей..."
    ):

        home_records, home_errors = (
            collect_team_history(
                team_name=home_team,
                urls=match.get(
                    "urls_home",
                    [],
                ),
                forecast_date=forecast_date,
            )
        )

        away_records, away_errors = (
            collect_team_history(
                team_name=away_team,
                urls=match.get(
                    "urls_away",
                    [],
                ),
                forecast_date=forecast_date,
            )
        )

    errors = []

    errors.extend(
        [
            f"{home_team}: {error}"
            for error in home_errors
        ]
    )

    errors.extend(
        [
            f"{away_team}: {error}"
            for error in away_errors
        ]
    )

    if len(home_records) == 0:

        st.error(
            f"Не собрано ни одного "
            f"матча для {home_team}."
        )

    if len(away_records) == 0:

        st.error(
            f"Не собрано ни одного "
            f"матча для {away_team}."
        )

    st.session_state.faj_collected[
        index
    ] = {

        "home_records":
            home_records,

        "away_records":
            away_records,

        "errors":
            errors,
    }

    home_context = make_form_context(
        home_team,
        home_records,
    )

    away_context = make_form_context(
        away_team,
        away_records,
    )

    st.session_state.faj_form_context[
        index
    ] = {

        "home":
            home_context,

        "away":
            away_context,
    }

    if not errors:

        st.success(
            "История успешно собрана."
        )

    else:

        st.warning(
            f"История собрана с "
            f"{len(errors)} сообщениями."
        )


# ============================================================
# GENERATE PREDICTION
# ============================================================

def generate_prediction(
    index: int,
    match: Dict[str, Any],
) -> None:

    home_team = match.get(
        "home_name"
    )

    away_team = match.get(
        "away_name"
    )

    if not home_team or not away_team:

        st.error(
            "Сначала выберите обе команды."
        )

        return

    collected = (
        st.session_state
        .faj_collected
        .get(index)
    )

    if not collected:

        collect_and_store_match(
            index,
            match,
        )

        collected = (
            st.session_state
            .faj_collected
            .get(index)
        )

    if not collected:

        st.error(
            "Не удалось собрать историю."
        )

        return

    history_home = collected.get(
        "home_records",
        [],
    )

    history_away = collected.get(
        "away_records",
        [],
    )

    if not history_home:

        st.error(
            f"Нет истории для "
            f"{home_team}."
        )

        return

    if not history_away:

        st.error(
            f"Нет истории для "
            f"{away_team}."
        )

        return

    with st.spinner(
        "FAJ Brain v4.0 анализирует матч..."
    ):

        try:

            prediction = build_prediction(
                home_team=home_team,
                away_team=away_team,
                history_home=history_home,
                history_away=history_away,
            )

        except Exception:

            logger.exception(
                "FAJ Brain prediction failed"
            )

            st.info(
                "ℹ️ FAJ не смог завершить "
                "расчёт этого матча. "
                "Проверьте техническую диагностику."
            )

            return

    st.session_state.faj_predictions[
        index
    ] = prediction

    st.success(
        "FAJ Brain сформировал прогноз."
    )


# ============================================================
# DATA SUMMARY
# ============================================================

def render_data_summary(
    team_name: str,
    records: List[Dict[str, Any]],
) -> None:

    if not records:
        return

    goals_for = []
    corners = []
    cards = []

    for record in records:

        if (
            normalize_name(
                record.get(
                    "home_team"
                )
            )
            ==
            normalize_name(
                team_name
            )
        ):

            gf = record.get(
                "home_goals"
            )

            corner = record.get(
                "home_corners"
            )

            card = record.get(
                "home_yellow_cards"
            )

        else:

            gf = record.get(
                "away_goals"
            )

            corner = record.get(
                "away_corners"
            )

            card = record.get(
                "away_yellow_cards"
            )

        if gf is not None:
            goals_for.append(gf)

        if corner is not None:
            corners.append(corner)

        if card is not None:
            cards.append(card)

    def avg(
        values: List[Any],
    ) -> Optional[float]:

        if not values:
            return None

        return (
            sum(values)
            / len(values)
        )

    st.markdown(
        f"**{team_name}**"
    )

    c1, c2, c3, c4 = (
        st.columns(4)
    )

    with c1:

        st.metric(
            "Матчей",
            len(records),
        )

    with c2:

        st.metric(
            "Голы за матч",
            num(
                avg(goals_for)
            ),
        )

    with c3:

        st.metric(
            "Угловые",
            num(
                avg(corners)
            ),
        )

    with c4:

        st.metric(
            "Карточки",
            num(
                avg(cards)
            ),
        )


# ============================================================
# HUMAN FORM / HISTORY
# ============================================================

def render_form_context_card(
    home_team: str,
    away_team: str,
    home_context: Optional[
        Dict[str, Any]
    ],
    away_context: Optional[
        Dict[str, Any]
    ],
) -> None:
    """
    Пользовательский вид формы.

    Никаких внутренних signals / raw / contracts.
    """

    if not home_context and not away_context:
        return

    with st.expander(
        "📈 Форма команд",
        expanded=False,
    ):

        c1, c2 = st.columns(2)

        def format_form(
            context: Optional[
                Dict[str, Any]
            ],
        ) -> str:

            if not isinstance(
                context,
                dict,
            ):

                return "—"

            form = context.get(
                "form"
            )

            if isinstance(
                form,
                str,
            ):

                return (
                    form.strip()
                    or "—"
                )

            if isinstance(
                form,
                (list, tuple),
            ):

                mapping = {
                    "W": "В",
                    "WIN": "В",
                    "D": "Н",
                    "DRAW": "Н",
                    "L": "П",
                    "LOSS": "П",
                }

                values = []

                for item in form[:6]:

                    value = (
                        str(item)
                        .strip()
                        .upper()
                    )

                    values.append(
                        mapping.get(
                            value,
                            value,
                        )
                    )

                return (
                    "-".join(values)
                    if values
                    else "—"
                )

            return "—"

        with c1:

            st.markdown(
                f"**🏠 {home_team}**"
            )

            st.write(
                f"Последняя форма: "
                f"**{format_form(home_context)}**"
            )

            if isinstance(
                home_context,
                dict,
            ):

                xg = first_not_none(
                    home_context.get(
                        "xg"
                    ),
                    home_context.get(
                        "xg_avg"
                    ),
                )

                xga = first_not_none(
                    home_context.get(
                        "xga"
                    ),
                    home_context.get(
                        "xga_avg"
                    ),
                )

                st.caption(
                    f"xG {num(xg)} · "
                    f"xGA {num(xga)}"
                )

        with c2:

            st.markdown(
                f"**✈️ {away_team}**"
            )

            st.write(
                f"Последняя форма: "
                f"**{format_form(away_context)}**"
            )

            if isinstance(
                away_context,
                dict,
            ):

                xg = first_not_none(
                    away_context.get(
                        "xg"
                    ),
                    away_context.get(
                        "xg_avg"
                    ),
                )

                xga = first_not_none(
                    away_context.get(
                        "xga"
                    ),
                    away_context.get(
                        "xga_avg"
                    ),
                )

                st.caption(
                    f"xG {num(xg)} · "
                    f"xGA {num(xga)}"
                )


def render_match_history(
    home_team: str,
    away_team: str,
    home_records: List[Dict[str, Any]],
    away_records: List[Dict[str, Any]],
) -> None:

    with st.expander(
        "🗂 Последние матчи",
        expanded=False,
    ):

        c1, c2 = st.columns(2)

        def render_team_history(
            team_name: str,
            records: List[Dict[str, Any]],
        ) -> None:

            st.markdown(
                f"**{team_name}**"
            )

            if not records:

                st.caption(
                    "История отсутствует."
                )

                return

            for record in reversed(
                records
            ):

                home = record.get(
                    "home_team"
                ) or "—"

                away = record.get(
                    "away_team"
                ) or "—"

                score = record.get(
                    "score"
                ) or "—"

                match_date = record.get(
                    "match_date"
                )

                st.markdown(
                    f"""
                    <div class="faj-history-row">
                        <strong>
                            {home} {score} {away}
                        </strong>
                        <br>
                        <span class="faj-muted">
                            {match_date or ""}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                xg = record.get(
                    "xg",
                    {},
                )

                if isinstance(
                    xg,
                    dict,
                ):

                    hxg = xg.get(
                        "home"
                    )

                    axg = xg.get(
                        "away"
                    )

                    if (
                        hxg is not None
                        or
                        axg is not None
                    ):

                        st.caption(
                            f"xG "
                            f"{num(hxg)} : "
                            f"{num(axg)}"
                        )

        with c1:

            render_team_history(
                home_team,
                home_records,
            )

        with c2:

            render_team_history(
                away_team,
                away_records,
            )


# ============================================================
# SCORE EXTRACTION — DISPLAY ONLY
# ============================================================

def normalize_score_display(
    value: Any,
) -> Optional[str]:

    if value is None:
        return None

    if isinstance(
        value,
        str,
    ):

        text = (
            value
            .strip()
            .replace("-", ":")
            .replace("–", ":")
        )

        if ":" in text:

            parts = text.split(":")

            if len(parts) == 2:

                try:

                    return (
                        f"{int(parts[0].strip())}"
                        f" : "
                        f"{int(parts[1].strip())}"
                    )

                except ValueError:
                    pass

        return text

    if isinstance(
        value,
        (tuple, list),
    ) and len(value) >= 2:

        try:

            return (
                f"{int(value[0])}"
                f" : "
                f"{int(value[1])}"
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    if isinstance(
        value,
        dict,
    ):

        home = first_not_none(
            value.get("home"),
            value.get("home_goals"),
            value.get("h"),
            value.get("home_score"),
        )

        away = first_not_none(
            value.get("away"),
            value.get("away_goals"),
            value.get("a"),
            value.get("away_score"),
        )

        if (
            home is not None
            and
            away is not None
        ):

            try:

                return (
                    f"{int(home)}"
                    f" : "
                    f"{int(away)}"
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

        nested = first_not_none(
            value.get(
                "score"
            ),
            value.get(
                "predicted_score"
            ),
        )

        return normalize_score_display(
            nested
        )

    return None


def extract_score_probability(
    item: Any,
) -> Optional[float]:

    if isinstance(
        item,
        dict,
    ):

        return first_not_none(
            item.get(
                "probability"
            ),
            item.get(
                "score_probability"
            ),
            item.get(
                "p"
            ),
        )

    return None


def extract_top_three_scores(
    prediction: Dict[str, Any],
) -> List[
    tuple[
        str,
        Optional[float],
    ]
]:

    result: List[
        tuple[
            str,
            Optional[float],
        ]
    ] = []

    top_scores = prediction.get(
        "top_scores"
    )

    # --------------------------------------------------------
    # Brain may return dict:
    #
    # {
    #     (0, 1): 0.1397,
    #     ...
    # }
    #
    # or:
    #
    # {
    #     "0:1": 0.1397
    # }
    # --------------------------------------------------------

    if isinstance(
        top_scores,
        dict,
    ):

        for score_key, raw_value in (
            top_scores.items()
        ):

            score = (
                normalize_score_display(
                    score_key
                )
            )

            probability = (
                extract_score_probability(
                    raw_value
                )
            )

            if (
                probability is None
                and
                isinstance(
                    raw_value,
                    (int, float),
                )
            ):

                probability = float(
                    raw_value
                )

            if score is not None:

                result.append(
                    (
                        score,
                        probability,
                    )
                )

    # --------------------------------------------------------
    # Brain may return list.
    # --------------------------------------------------------

    elif isinstance(
        top_scores,
        list,
    ):

        for item in top_scores:

            score = (
                normalize_score_display(
                    item
                )
            )

            probability = (
                extract_score_probability(
                    item
                )
            )

            if score is not None:

                result.append(
                    (
                        score,
                        probability,
                    )
                )

    # --------------------------------------------------------
    # Sort ONLY already supplied score probabilities.
    # No mathematical recalculation.
    # --------------------------------------------------------

    if result:

        result.sort(
            key=lambda item: (
                item[1]
                if item[1] is not None
                else -1.0
            ),
            reverse=True,
        )

        return result[:3]

    # --------------------------------------------------------
    # Explicit Brain score fields.
    # --------------------------------------------------------

    explicit = [
        (
            prediction.get(
                "predicted_score"
            ),
            prediction.get(
                "predicted_score_probability"
            ),
        ),
        (
            prediction.get(
                "second_score"
            ),
            prediction.get(
                "second_score_probability"
            ),
        ),
        (
            prediction.get(
                "third_score"
            ),
            prediction.get(
                "third_score_probability"
            ),
        ),
    ]

    for score, probability in explicit:

        normalized = (
            normalize_score_display(
                score
            )
        )

        if normalized is not None:

            result.append(
                (
                    normalized,
                    probability,
                )
            )

    return result[:3]


# ============================================================
# CORNERS / CARDS DISPLAY EXTRACTION
# ============================================================

def extract_expected_value(
    prediction: Dict[str, Any],
    names: tuple[str, ...],
) -> Any:

    for name in names:

        value = prediction.get(
            name
        )

        if value is None:
            continue

        if isinstance(
            value,
            (int, float),
        ):

            return value

        if isinstance(
            value,
            dict,
        ):

            nested = first_not_none(
                value.get(
                    "total"
                ),
                value.get(
                    "expected_total"
                ),
                value.get(
                    "expected"
                ),
                value.get(
                    "prediction"
                ),
            )

            if nested is not None:
                return nested

    return None


def extract_corners_total(
    prediction: Dict[str, Any],
) -> Optional[float]:
    """
    Display-only extraction of expected total corners.

    Priority:
        1. Direct Brain-level fields (if Brain ever exposes them).
        2. corners_state.home/away with per-team expected fields.
        3. Derive total ONLY from already provided per-team
           expected fields (no new mathematics).

    Nothing is recalculated here.
    """

    direct = extract_expected_value(
        prediction,
        (
            "corners",
            "expected_corners",
            "corners_total",
            "corners_expected",
        ),
    )

    if direct is not None:

        value = safe_float(direct)

        if value is not None:
            return value

    corners_state = prediction.get(
        "corners_state"
    )

    if not isinstance(
        corners_state,
        dict,
    ):

        return None

    home_state = corners_state.get(
        "home"
    )

    away_state = corners_state.get(
        "away"
    )

    def _per_team_expected(
        state: Any,
        keys: tuple[str, ...],
    ) -> Optional[float]:

        if not isinstance(
            state,
            dict,
        ):

            return None

        for key in keys:

            value = state.get(
                key
            )

            number = safe_float(
                value
            )

            if number is not None:
                return number

        return None

    home_expected = _per_team_expected(
        home_state,
        (
            "home_corners_expected",
            "corners_expected",
            "expected_corners",
            "expected_total",
            "total_expected_corners",
        ),
    )

    away_expected = _per_team_expected(
        away_state,
        (
            "away_corners_expected",
            "corners_expected",
            "expected_corners",
            "expected_total",
            "total_expected_corners",
        ),
    )

    if (
        home_expected is not None
        and
        away_expected is not None
    ):

        return (
            home_expected
            + away_expected
        )

    if home_expected is not None:
        return home_expected

    if away_expected is not None:
        return away_expected

    # --------------------------------------------------------
    # Fallback: some Brain outputs expose only per-team
    # historical averages. We do not combine them into
    # a new total; we simply return None here.
    # --------------------------------------------------------

    return None


def extract_cards_total(
    prediction: Dict[str, Any],
) -> Optional[float]:
    """
    Display-only extraction of expected total cards.

    Same principle as corners:
        no recalculation, only reading already supplied fields.
    """

    direct = extract_expected_value(
        prediction,
        (
            "cards",
            "expected_cards",
            "cards_total",
            "cards_expected",
        ),
    )

    if direct is not None:

        value = safe_float(direct)

        if value is not None:
            return value

    cards_state = prediction.get(
        "cards_state"
    )

    if not isinstance(
        cards_state,
        dict,
    ):

        return None

    home_state = cards_state.get(
        "home"
    )

    away_state = cards_state.get(
        "away"
    )

    def _per_team_expected(
        state: Any,
        keys: tuple[str, ...],
    ) -> Optional[float]:

        if not isinstance(
            state,
            dict,
        ):

            return None

        for key in keys:

            value = state.get(
                key
            )

            number = safe_float(
                value
            )

            if number is not None:
                return number

        return None

    home_expected = _per_team_expected(
        home_state,
        (
            "home_cards_expected",
            "cards_expected",
            "expected_cards",
            "expected_total",
            "total_expected_cards",
        ),
    )

    away_expected = _per_team_expected(
        away_state,
        (
            "away_cards_expected",
            "cards_expected",
            "expected_cards",
            "expected_total",
            "total_expected_cards",
        ),
    )

    if (
        home_expected is not None
        and
        away_expected is not None
    ):

        return (
            home_expected
            + away_expected
        )

    if home_expected is not None:
        return home_expected

    if away_expected is not None:
        return away_expected

    return None


# ============================================================
# USER-FACING PREDICTION CARD
# ============================================================

def render_prediction_card(
    prediction: Dict[str, Any],
) -> None:
    """
    Main user-facing FAJ prediction.

    IMPORTANT:

        This function does not calculate football predictions.

        It only reads Brain output and formats it.
    """

    if not prediction:

        st.info(
            "ℹ️ Прогноз пока недоступен."
        )

        return

    # ========================================================
    # TEAMS
    # ========================================================

    home_team = (
        prediction.get(
            "home_team"
        )
        or prediction.get(
            "home"
        )
        or "Хозяева"
    )

    away_team = (
        prediction.get(
            "away_team"
        )
        or prediction.get(
            "away"
        )
        or "Гости"
    )

    st.markdown(
        f"""
        <div class="faj-match-title">
            ⚽ {home_team} — {away_team}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # xG
    # ========================================================

    home_xg = first_not_none(
        prediction.get(
            "home_xg"
        ),
        prediction.get(
            "home_lambda"
        ),
    )

    away_xg = first_not_none(
        prediction.get(
            "away_xg"
        ),
        prediction.get(
            "away_lambda"
        ),
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            home_team,
            (
                f"xG {num(home_xg)}"
                if home_xg is not None
                else "xG —"
            ),
        )

    with c2:

        st.metric(
            away_team,
            (
                f"xG {num(away_xg)}"
                if away_xg is not None
                else "xG —"
            ),
        )

    st.divider()

    # ========================================================
    # 1X2
    #
    # REAL BRAIN v4.0 FIELDS
    # ========================================================

    home_win = prediction.get(
        "home_win_probability"
    )

    draw = prediction.get(
        "draw_probability"
    )

    away_win = prediction.get(
        "away_win_probability"
    )

    # Compatibility with possible nested output.

    if (
        home_win is None
        and
        isinstance(
            prediction.get("1x2"),
            dict,
        )
    ):

        one_x_two = prediction.get(
            "1x2"
        )

        home_win = first_not_none(
            one_x_two.get(
                "home"
            ),
            one_x_two.get(
                "home_win"
            ),
        )

        draw = first_not_none(
            one_x_two.get(
                "draw"
            ),
            one_x_two.get(
                "draw_probability"
            ),
        )

        away_win = first_not_none(
            one_x_two.get(
                "away"
            ),
            one_x_two.get(
                "away_win"
            ),
        )

    st.markdown(
        '<div class="faj-section">🏆 Исход</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            home_team,
            pct(home_win),
        )

    with c2:

        st.metric(
            "Ничья",
            pct(draw),
        )

    with c3:

        st.metric(
            away_team,
            pct(away_win),
        )

    # ========================================================
    # TOP 3 SCORES
    # ========================================================

    scores = extract_top_three_scores(
        prediction
    )

    st.markdown(
        '<div class="faj-section">⚽ Наиболее вероятные счета</div>',
        unsafe_allow_html=True,
    )

    if not scores:

        st.caption(
            "Распределение счетов не передано."
        )

    else:

        score_columns = st.columns(
            len(scores)
        )

        for position, (
            score,
            probability,
        ) in enumerate(
            scores
        ):

            with score_columns[
                position
            ]:

                if position == 0:

                    st.markdown(
                        f"""
                        <div class="faj-score-main">
                            {score}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                else:

                    st.markdown(
                        f"""
                        <div class="faj-score-main"
                             style="font-size:1.45rem;">
                            {score}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                if probability is not None:

                    st.markdown(
                        f"""
                        <div class="faj-score-prob">
                            {pct(probability)}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # ========================================================
    # BTTS
    # ========================================================

    btts_probability = prediction.get(
        "btts_probability"
    )

    if btts_probability is None:

        btts = prediction.get(
            "btts"
        )

        if isinstance(
            btts,
            dict,
        ):

            btts_probability = first_not_none(
                btts.get(
                    "yes"
                ),
                btts.get(
                    "btts_yes"
                ),
            )

    if btts_probability is not None:

        st.markdown(
            '<div class="faj-section">🔥 Обе забьют</div>',
            unsafe_allow_html=True,
        )

        btts_no = None

        try:

            value = float(
                btts_probability
            )

            if 0.0 <= value <= 1.0:

                btts_no = (
                    1.0 - value
                )

            elif 0.0 <= value <= 100.0:

                btts_no = (
                    100.0 - value
                )

        except (
            TypeError,
            ValueError,
        ):

            btts_no = None

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Да",
                pct(
                    btts_probability
                ),
            )

        with c2:

            st.metric(
                "Нет",
                pct(
                    btts_no
                ),
            )

    # ========================================================
    # TOTAL 2.5
    # ========================================================

    over25 = prediction.get(
        "over_25_probability"
    )

    under25 = prediction.get(
        "under_25_probability"
    )

    if (
        over25 is not None
        or
        under25 is not None
    ):

        st.markdown(
            '<div class="faj-section">📈 Тотал 2.5</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Больше",
                pct(over25),
            )

        with c2:

            st.metric(
                "Меньше",
                pct(under25),
            )

    # ========================================================
    # TOTAL 3.5
    # ========================================================

    over35 = prediction.get(
        "over_35_probability"
    )

    under35 = prediction.get(
        "under_35_probability"
    )

    if (
        over35 is not None
        or
        under35 is not None
    ):

        st.markdown(
            '<div class="faj-section">📈 Тотал 3.5</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:

            st.metric(
                "Больше",
                pct(over35),
            )

        with c2:

            st.metric(
                "Меньше",
                pct(under35),
            )

    # ========================================================
    # CORNERS
    # ========================================================

    corners_value = extract_corners_total(
        prediction
    )

    # ========================================================
    # CARDS
    # ========================================================

    cards_value = extract_cards_total(
        prediction
    )

    if (
        corners_value is not None
        or
        cards_value is not None
    ):

        st.markdown(
            '<div class="faj-section">Дополнительные показатели</div>',
            unsafe_allow_html=True,
        )

        available = []

        if corners_value is not None:

            available.append(
                (
                    "🚩 Угловые",
                    corners_value,
                )
            )

        if cards_value is not None:

            available.append(
                (
                    "🟨 Карточки",
                    cards_value,
                )
            )

        columns = st.columns(
            len(available)
        )

        for column, (
            label,
            value,
        ) in zip(
            columns,
            available,
        ):

            with column:

                st.metric(
                    label,
                    f"≈ {num(value, 1)}",
                )

    # ========================================================
    # SMALL BRAIN SUMMARY
    # ========================================================

    primary_outcome = prediction.get(
        "primary_outcome"
    )

    primary_scenario = prediction.get(
        "primary_scenario"
    )

    if (
        primary_outcome
        or
        primary_scenario
    ):

        outcome_names = {
            "HOME":
                home_team,

            "DRAW":
                "Ничья",

            "AWAY":
                away_team,
        }

        readable_outcome = (
            outcome_names.get(
                str(
                    primary_outcome
                ).upper(),
                primary_outcome,
            )
            if primary_outcome
            else None
        )

        with st.expander(
            "🧠 Основной сценарий FAJ",
            expanded=False,
        ):

            if readable_outcome:

                st.write(
                    f"Исход: **{readable_outcome}**"
                )

            if primary_scenario:

                scenario = (
                    normalize_score_display(
                        primary_scenario
                    )
                    or str(
                        primary_scenario
                    )
                )

                st.write(
                    f"Сценарий: **{scenario}**"
                )

    # ========================================================
    # TECHNICAL DIAGNOSTICS
    #
    # Everything below is intentionally hidden from the
    # normal user-facing prediction.
    # ========================================================

    diagnostics = prediction.get(
        "diagnostics"
    )

    errors = prediction.get(
        "errors"
    )

    with st.expander(
        "🔧 Техническая диагностика",
        expanded=False,
    ):

        if errors:

            st.warning(
                "Во время расчёта были "
                "технические сообщения."
            )

            for error in errors:

                st.code(
                    str(error)
                )

        else:

            st.success(
                "FAJ Brain завершил расчёт "
                "без зарегистрированных ошибок."
            )

        if diagnostics is not None:

            st.json(
                json_safe(
                    diagnostics
                )
            )

        confidence = prediction.get(
            "confidence"
        )

        risk = prediction.get(
            "risk"
        )

        if confidence is not None:

            st.write(
                f"Confidence: {confidence}"
            )

        if risk is not None:

            st.write(
                f"Risk: {risk}"
            )

        # ----------------------------------------------------
        # Full Brain output.
        #
        # JSON is sanitized ONLY for display.
        # ----------------------------------------------------

        with st.expander(
            "Полный технический вывод Brain",
            expanded=False,
        ):

            st.json(
                json_safe(
                    prediction
                )
            )


# ============================================================
# MATCH SETUP
# ============================================================

def render_match_setup(
    index: int,
    match: Dict[str, Any],
    team_names: List[str],
) -> None:

    st.markdown(
        f"### Матч {index + 1}"
    )

    if len(team_names) < 2:

        st.warning(
            "В выбранном турнире "
            "нужно минимум две команды."
        )

        return

    # ========================================================
    # TEAM SELECTION
    # ========================================================

    home_current = (
        match.get(
            "home_name"
        )
        or team_names[0]
    )

    if home_current not in team_names:

        home_current = team_names[0]

    away_options = [
        name
        for name in team_names
        if name != home_current
    ]

    away_current = (
        match.get(
            "away_name"
        )
        or away_options[0]
    )

    if (
        away_current
        not in away_options
    ):

        away_current = (
            away_options[0]
        )

    c1, c2 = st.columns(2)

    with c1:

        selected_home = st.selectbox(
            "🏠 Хозяева",
            team_names,
            index=(
                team_names.index(
                    home_current
                )
                if home_current
                in team_names
                else 0
            ),
            key=f"home_{index}",
        )

    with c2:

        available_away = [
            name
            for name in team_names
            if name != selected_home
        ]

        selected_away = st.selectbox(
            "✈️ Гости",
            available_away,
            index=(
                available_away.index(
                    away_current
                )
                if away_current
                in available_away
                else 0
            ),
            key=f"away_{index}",
        )

    match[
        "home_name"
    ] = selected_home

    match[
        "away_name"
    ] = selected_away

    # ========================================================
    # CLUB RATING — DISPLAY ONLY
    # ========================================================

    st.markdown(
        "#### ⭐ FAJ Club Rating"
    )

    club_c1, club_c2 = (
        st.columns(2)
    )

    with club_c1:

        rating = get_team_rating(
            selected_home,
            st.session_state.faj_competition,
        )

        st.metric(
            f"🏠 {selected_home}",
            rating
            if rating is not None
            else "—",
        )

    with club_c2:

        rating = get_team_rating(
            selected_away,
            st.session_state.faj_competition,
        )

        st.metric(
            f"✈️ {selected_away}",
            rating
            if rating is not None
            else "—",
        )

    st.caption(
        "Club Rating — справочный "
        "структурный рейтинг FAJ. "
        "Только отображается."
    )

    # ========================================================
    # PAIR RATING — RESEARCH ONLY
    # ========================================================

    st.markdown(
        "#### 🧠 FAJ Pair Rating "
        "(research only)"
    )

    _home_pr_default = int(
        match.get(
            "home_pair_rating",
            PAIR_RATING_DEFAULT,
        )
    )

    _away_pr_default = int(
        match.get(
            "away_pair_rating",
            PAIR_RATING_DEFAULT,
        )
    )

    _home_pr_default = max(
        PAIR_RATING_MIN,
        min(
            PAIR_RATING_MAX,
            _home_pr_default,
        ),
    )

    _away_pr_default = max(
        PAIR_RATING_MIN,
        min(
            PAIR_RATING_MAX,
            _away_pr_default,
        ),
    )

    pair_c1, pair_c2 = st.columns(2)

    with pair_c1:

        home_pair_rating = st.number_input(
            f"🏠 {selected_home} — рейтинг пары",
            min_value=PAIR_RATING_MIN,
            max_value=PAIR_RATING_MAX,
            value=_home_pr_default,
            step=1,
            key=f"home_pair_rating_{index}",
        )

    with pair_c2:

        away_pair_rating = st.number_input(
            f"✈️ {selected_away} — рейтинг пары",
            min_value=PAIR_RATING_MIN,
            max_value=PAIR_RATING_MAX,
            value=_away_pr_default,
            step=1,
            key=f"away_pair_rating_{index}",
        )

    match[
        "home_pair_rating"
    ] = int(home_pair_rating)

    match[
        "away_pair_rating"
    ] = int(away_pair_rating)

    _gap = (
        int(home_pair_rating)
        -
        int(away_pair_rating)
    )

    if _gap > 0:

        _dir = "HOME"
        _team = selected_home

    elif _gap < 0:

        _dir = "AWAY"
        _team = selected_away

    else:

        _dir = "NEUTRAL"
        _team = "—"

    st.caption(
        f"Направление пары: {_team} "
        f"({_dir}, gap {_gap:+d}) "
        f"· source: manual · "
        f"в Brain v4.0 не передаётся."
    )

    # ========================================================
    # DATE
    # ========================================================

    current_date = match.get(
        "match_date"
    )

    try:

        default_date = (
            date.fromisoformat(
                current_date
            )
            if current_date
            else date.today()
        )

    except (
        TypeError,
        ValueError,
    ):

        default_date = date.today()

    forecast_date = st.date_input(
        "📅 Дата матча",
        value=default_date,
        key=f"date_{index}",
    )

    match[
        "match_date"
    ] = forecast_date.isoformat()

    # ========================================================
    # SOCCER365 URLS
    # ========================================================

    st.markdown(
        "#### 🔗 Ссылки на Soccer365"
    )

    col_home, col_away = (
        st.columns(2)
    )

    with col_home:

        st.markdown(
            f"**🏠 {selected_home}**"
        )

        for i in range(
            MAX_HISTORY_MATCHES
        ):

            match[
                "urls_home"
            ][i] = st.text_input(
                f"Матч {i + 1}",
                value=match[
                    "urls_home"
                ][i],
                key=(
                    f"home_url_"
                    f"{index}_{i}"
                ),
                placeholder=(
                    "https://soccer365.ru/..."
                ),
            )

    with col_away:

        st.markdown(
            f"**✈️ {selected_away}**"
        )

        for i in range(
            MAX_HISTORY_MATCHES
        ):

            match[
                "urls_away"
            ][i] = st.text_input(
                f"Матч {i + 1}",
                value=match[
                    "urls_away"
                ][i],
                key=(
                    f"away_url_"
                    f"{index}_{i}"
                ),
                placeholder=(
                    "https://soccer365.ru/..."
                ),
            )

    # ========================================================
    # BUTTONS
    # ========================================================

    c1, c2 = st.columns(2)

    with c1:

        if st.button(
            "📥 Собрать статистику",
            key=f"collect_{index}",
            width="stretch",
        ):

            collect_and_store_match(
                index,
                match,
            )

    with c2:

        if st.button(
            "🧠 Получить прогноз",
            key=f"predict_{index}",
            width="stretch",
        ):

            generate_prediction(
                index,
                match,
            )

    # ========================================================
    # STATUS
    # ========================================================

    collected = (
        st.session_state
        .faj_collected
        .get(index)
    )

    if collected:

        st.success(
            f"Собрано: "
            f"{len(collected.get('home_records', []))} "
            f"матчей {selected_home}; "
            f"{len(collected.get('away_records', []))} "
            f"матчей {selected_away}."
        )

        c1, c2 = st.columns(2)

        with c1:

            render_data_summary(
                selected_home,
                collected.get(
                    "home_records",
                    [],
                ),
            )

        with c2:

            render_data_summary(
                selected_away,
                collected.get(
                    "away_records",
                    [],
                ),
            )

        # ----------------------------------------------------
        # History is now human-readable and hidden by default.
        # ----------------------------------------------------

        render_match_history(
            selected_home,
            selected_away,
            collected.get(
                "home_records",
                [],
            ),
            collected.get(
                "away_records",
                [],
            ),
        )

        errors = collected.get(
            "errors",
            [],
        )

        if errors:

            with st.expander(
                "⚠️ Сообщения сбора",
                expanded=False,
            ):

                for error in errors:

                    st.warning(
                        error
                    )

    # ========================================================
    # FORM CONTEXT
    #
    # Brain food, not main user-facing output.
    # ========================================================

    form_data = (
        st.session_state
        .faj_form_context
        .get(index)
    )

    if form_data:

        render_form_context_card(
            selected_home,
            selected_away,
            form_data.get("home"),
            form_data.get("away"),
        )

    # ========================================================
    # PREDICTION
    # ========================================================

    prediction = (
        st.session_state
        .faj_predictions
        .get(index)
    )

    if prediction:

        render_prediction_card(
            prediction
        )

    # ========================================================
    # REMOVE
    # ========================================================

    if (
        len(
            st.session_state.faj_matches
        )
        > 1
    ):

        if st.button(
            "🗑 Удалить матч",
            key=f"remove_{index}",
        ):

            remove_match(
                index
            )

            st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # IMPORTANT:
    # st.set_page_config() is already called once above.

    init_state()

    st.title(
        "⚽ FAJ Personal Prediction Brain"
    )

    st.caption(
        "FAJ Brain v4.0 — "
        "математический анализ "
        "футбольной пары."
    )

    # ========================================================
    # TOP CONTROLS
    # ========================================================

    c1, c2 = st.columns(
        [3, 1]
    )

    with c1:

        tournaments = (
            get_all_tournaments()
        )

        current_competition = (
            st.session_state
            .faj_competition
        )

        if (
            current_competition
            not in tournaments
        ):

            current_competition = (
                tournaments[0]
                if tournaments
                else None
            )

        selected_competition = (
            st.selectbox(
                "🏆 Турнир",
                tournaments,
                index=(
                    tournaments.index(
                        current_competition
                    )
                    if current_competition
                    in tournaments
                    else 0
                ),
            )
        )

        if (
            selected_competition
            != st.session_state
            .faj_competition
        ):

            st.session_state.faj_competition = (
                selected_competition
            )

            st.session_state.faj_matches = []
            st.session_state.faj_collected = {}
            st.session_state.faj_predictions = {}
            st.session_state.faj_form_context = {}

    with c2:

        if st.button(
            "🔄 Сбросить",
            width="stretch",
        ):

            reset_workspace()

            st.rerun()

    # ========================================================
    # TEAM SOURCE
    # ========================================================

    team_names = load_teams(
        st.session_state.faj_competition
    )

    if not team_names:

        st.error(
            "В выбранном турнире "
            "нет команд в FAJ Club Ratings."
        )

        return

    # ========================================================
    # MATCHES
    # ========================================================

    if not st.session_state.faj_matches:

        st.session_state.faj_matches.append(
            create_match_slot()
        )

    for index, match in enumerate(
        list(
            st.session_state.faj_matches
        )
    ):

        with st.container(
            border=True
        ):

            render_match_setup(
                index=index,
                match=match,
                team_names=team_names,
            )

    # ========================================================
    # ADD MATCH
    # ========================================================

    st.markdown("---")

    if (
        len(
            st.session_state.faj_matches
        )
        < MAX_ANALYSIS_MATCHES
    ):

        if st.button(
            "➕ Добавить матч",
            width="stretch",
        ):

            add_match()

            st.rerun()

    st.caption(
        f"Матчей: "
        f"{len(st.session_state.faj_matches)} / "
        f"{MAX_ANALYSIS_MATCHES}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
