#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PREDICTOR — Streamlit Interface

Multi-match interface for FAJ Personal Prediction Brain.

Архитектура:

    Streamlit UI
        ↓
    Soccer365Parser
        ↓
    factual history
        ↓
    FAJBrain.predict()
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

Всё приходит из FAJBrain через calculation_meta.

Pair Rating:
    ручной исследовательский сигнал конкретной пары.
    НЕ меняет xG / λ / Poisson / ScorePredictor.
    Используется ТОЛЬКО в Winner Synthesis
    как структурный сигнал.

    Контракт:
        - оба поля заданы вручную (60..100)
            → source = "manual"
        - оба поля None
            → source = "club_rating_fallback"
        - не удалось ни то, ни другое
            → source = None

    В UI Pair Rating — только display + manual input.
"""

from __future__ import annotations

import logging
import re
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
    if value is None:
        return "—"

    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


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


def parse_date_value(value: Any) -> Optional[date]:
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
        # Ручной Pair Rating для конкретной пары
        # ------------------------------------------------
        "home_pair_rating": PAIR_RATING_DEFAULT,
        "away_pair_rating": PAIR_RATING_DEFAULT,

        "urls_home": [""] * MAX_HISTORY_MATCHES,
        "urls_away": [""] * MAX_HISTORY_MATCHES,
    }


def add_match() -> None:

    if (
        len(st.session_state.faj_matches)
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


def remove_match(index: int) -> None:

    if (
        0 <= index
        < len(st.session_state.faj_matches)
    ):

        st.session_state.faj_matches.pop(index)

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

        teams = get_all_teams(league)

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

    if not isinstance(stats, dict):
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
                stats.get("home_crosses"),
            "away":
                stats.get("away_crosses"),
        },

        "throw_ins": {
            "home":
                stats.get("home_throw_ins"),
            "away":
                stats.get("away_throw_ins"),
        },

        "fouls": {
            "home":
                stats.get("home_fouls"),
            "away":
                stats.get("away_fouls"),
        },

        "offsides": {
            "home":
                stats.get("home_offsides"),
            "away":
                stats.get("away_offsides"),
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
                stats.get("home_corners"),
            "away":
                stats.get("away_corners"),
        },

        # Compatibility fields

        "home_corners":
            stats.get("home_corners"),

        "away_corners":
            stats.get("away_corners"),

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
            parsed.get("source_url"),

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

    # oldest → newest

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
            limit=MAX_HISTORY_MATCHES,
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
    Единственная математическая точка страницы.

    Streamlit НЕ считает:
    - xG
    - Poisson
    - 1X2
    - BTTS
    - totals
    - exact scores
    - Pair Rating
    - Winner Synthesis
    - confidence
    - risk
    - corners
    - cards

    Всё приходит из FAJBrain.

    Pair Rating прокидывается как входные параметры:
        - если оба заданы → manual;
        - если оба None   → club_rating_fallback.
    """

    brain = get_faj_brain()

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=history_home,
        away_matches=history_away,
        home_pair_rating=home_pair_rating,
        away_pair_rating=away_pair_rating,
    )

    if hasattr(result, "to_dict"):
        prediction = result.to_dict()

    elif isinstance(result, dict):
        prediction = dict(result)

    else:
        raise TypeError(
            "FAJBrain.predict() "
            "вернул неподдерживаемый тип."
        )

    if not isinstance(
        prediction.get("calculation_meta"),
        dict,
    ):
        raise ValueError(
            "FAJBrain не вернул calculation_meta."
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

    home_pair_rating = match.get(
        "home_pair_rating"
    )

    away_pair_rating = match.get(
        "away_pair_rating"
    )

    with st.spinner(
        "FAJ Brain анализирует матч..."
    ):

        try:

            prediction = build_prediction(
                home_team=home_team,
                away_team=away_team,
                history_home=history_home,
                history_away=history_away,
                home_pair_rating=home_pair_rating,
                away_pair_rating=away_pair_rating,
            )

        except Exception as exc:

            logger.exception(
                "Ошибка FAJ Brain"
            )

            st.error(
                f"Ошибка получения прогноза: "
                f"{exc}"
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
# FORM CONTEXT CARD
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

    if not home_context and not away_context:
        return

    st.markdown(
        "### 📊 Форма перед матчем"
    )

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
            f"Форма: "
            f"{format_form(home_context)}"
        )

        if isinstance(
            home_context,
            dict,
        ):

            st.write(
                "xG: "
                +
                num(
                    safe_float(
                        home_context.get(
                            "xg_avg"
                        )
                    )
                )
            )

            st.write(
                "xGA: "
                +
                num(
                    safe_float(
                        home_context.get(
                            "xga_avg"
                        )
                    )
                )
            )

    with c2:

        st.markdown(
            f"**✈️ {away_team}**"
        )

        st.write(
            f"Форма: "
            f"{format_form(away_context)}"
        )

        if isinstance(
            away_context,
            dict,
        ):

            st.write(
                "xG: "
                +
                num(
                    safe_float(
                        away_context.get(
                            "xg_avg"
                        )
                    )
                )
            )

            st.write(
                "xGA: "
                +
                num(
                    safe_float(
                        away_context.get(
                            "xga_avg"
                        )
                    )
                )
            )


# ============================================================
# WINNER SYNTHESIS — DETAILED BREAKDOWN
# ============================================================

def _render_winner_synthesis_breakdown(
    winner_synthesis: Dict[str, Any],
    pair_rating: Dict[str, Any],
    pair_rating_source: Optional[str],
    winner_probability_map: Dict[str, Optional[float]],
) -> None:
    """
    Разложение Winner Synthesis по источникам сигналов.

    Только отображение уже посчитанных полей:
        - PRIMARY (Poisson)
        - PAIR RATING
        - FORMWIN
        - DEFENCE
        - agreements / conflicts

    Никакой математики.
    """

    poisson_winner = (
        winner_synthesis.get("poisson_winner")
        or "—"
    )

    primary_prob = winner_probability_map.get(
        poisson_winner
    )

    primary_text = (
        f"{poisson_winner}"
        + (
            f" ({primary_prob:.1f}%)"
            if primary_prob is not None
            else ""
        )
    )

    # --------------------------------------------------------
    # PAIR RATING
    # --------------------------------------------------------

    pr_direction = (
        winner_synthesis.get("pair_rating_direction")
        or "—"
    )

    pr_strength = (
        winner_synthesis.get("pair_rating_strength")
        or "—"
    )

    pr_home = pair_rating.get("home_rating")
    pr_away = pair_rating.get("away_rating")
    pr_gap = pair_rating.get("rating_gap")

    pr_numbers_text = "—"

    if pr_home is not None and pr_away is not None:

        gap_text = "—"

        if pr_gap is not None:

            try:
                gap_text = f"{int(pr_gap):+d}"
            except (TypeError, ValueError):
                gap_text = "—"

        pr_numbers_text = (
            f"{pr_home} vs {pr_away} — {pr_strength} — gap {gap_text}"
        )

        if pair_rating_source:
            pr_numbers_text += f" — source: {pair_rating_source}"

    # --------------------------------------------------------
    # FORMWIN
    # --------------------------------------------------------

    form_direction = (
        winner_synthesis.get("form_direction")
        or "—"
    )

    form_advantage = winner_synthesis.get(
        "form_advantage"
    )

    form_text = form_direction

    if form_advantage is not None:

        try:
            form_text = (
                f"{form_direction} "
                f"({float(form_advantage):+.3f})"
            )
        except (TypeError, ValueError):
            pass

    # --------------------------------------------------------
    # DEFENCE
    # --------------------------------------------------------

    defence_direction = (
        winner_synthesis.get("defence_direction")
        or "—"
    )

    defence_home = winner_synthesis.get("defence_home")
    defence_away = winner_synthesis.get("defence_away")

    defence_text = defence_direction

    if (
        defence_home is not None
        and defence_away is not None
    ):

        try:
            defence_text = (
                f"{defence_direction} "
                f"({float(defence_home):.3f} / "
                f"{float(defence_away):.3f})"
            )
        except (TypeError, ValueError):
            pass

    # --------------------------------------------------------
    # AGREEMENTS / CONFLICTS
    # --------------------------------------------------------

    agreements = winner_synthesis.get("agreements", 0)
    conflicts = winner_synthesis.get("conflicts", 0)

    st.markdown(
        f"""
**Winner Synthesis: {winner_synthesis.get("synthesis", "—")}**

- PRIMARY MODEL: `{primary_text}`
- PAIR RATING: `{pr_direction}` — `{pr_numbers_text}`
- FORMWIN: `{form_text}`
- DEFENCE: `{defence_text}`

`{agreements} agreement(s) / {conflicts} conflict(s)`
""",
        unsafe_allow_html=False,
    )


# ============================================================
# CONFIDENCE BREAKDOWN
# ============================================================

def _render_confidence_breakdown(
    winner_synthesis: Dict[str, Any],
    winner_probability_map: Dict[str, Optional[float]],
) -> None:
    """
    Разложение confidence.

    Base — вероятность poisson_winner.
    Final — winner_synthesis["confidence"] (0..1).
    Penalty — final − base (в %).

    Все значения — уже существующие в winner_synthesis.
    Никаких новых полей не создаём.
    """

    poisson_winner = winner_synthesis.get(
        "poisson_winner"
    )

    base_prob = winner_probability_map.get(
        poisson_winner
    )

    final_conf_raw = safe_float(
        winner_synthesis.get("confidence")
    )

    base_pct = (
        base_prob * 100.0
        if base_prob is not None
        else None
    )

    final_pct = (
        final_conf_raw * 100.0
        if final_conf_raw is not None
        else None
    )

    delta_pct = None

    if base_pct is not None and final_pct is not None:

        delta_pct = final_pct - base_pct

    c1, c2, c3 = st.columns(3, gap="small")

    with c1:
        st.metric(
            "Base confidence",
            pct(base_pct),
        )

    with c2:
        st.metric(
            "Synthesis penalty",
            (
                f"{delta_pct:+.1f}%"
                if delta_pct is not None
                else "—"
            ),
        )

    with c3:
        st.metric(
            "Final confidence",
            pct(final_pct),
        )


# ============================================================
# PREDICTION CARD
# ============================================================

def render_prediction_card(
    prediction: Dict[str, Any],
) -> None:

    home = prediction.get(
        "home_team",
        "Хозяева",
    )

    away = prediction.get(
        "away_team",
        "Гости",
    )

    st.markdown("---")

    st.markdown(
        f"## ⚽ {home} — {away}"
    )

    # ========================================================
    # META — ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ
    # ========================================================

    meta = prediction.get(
        "calculation_meta",
        {},
    ) or {}

    winner_synthesis = (
        meta.get("winner_synthesis")
        or {}
    )

    pair_rating = (
        meta.get("pair_rating")
        or {}
    )

    pair_rating_source = meta.get(
        "pair_rating_source"
    )

    score_forecast = (
        meta.get("score_forecast")
        or {}
    )

    # ========================================================
    # WINNER PROBABILITY MAP — для отображения PRIMARY и Base confidence
    # ========================================================

    winner_probability_map = {
        "HOME": safe_float(
            winner_synthesis.get("home_probability")
        ),
        "DRAW": safe_float(
            winner_synthesis.get("draw_probability")
        ),
        "AWAY": safe_float(
            winner_synthesis.get("away_probability")
        ),
    }

    winner_probability_map_pct = {
        key: (
            value * 100.0
            if value is not None
            else None
        )
        for key, value in winner_probability_map.items()
    }

    # ========================================================
    # WINNER SYNTHESIS
    # ========================================================

    st.subheader(
        "🧠 Winner Synthesis"
    )

    model_favorite = (
        winner_synthesis.get(
            "winner",
            "—",
        )
    )

    pair_direction = (
        winner_synthesis.get(
            "pair_rating_direction",
            "—",
        )
    )

    pair_strength = (
        winner_synthesis.get(
            "pair_rating_strength",
            "—",
        )
    )

    synthesis = (
        winner_synthesis.get(
            "synthesis",
            "—",
        )
    )

    agreements = (
        winner_synthesis.get(
            "agreements",
            0,
        )
    )

    conflicts = (
        winner_synthesis.get(
            "conflicts",
            0,
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Model favorite",
            model_favorite,
        )

    with c2:

        st.metric(
            "Pair direction",
            pair_direction,
        )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Pair strength",
            pair_strength,
        )

    with c2:

        st.metric(
            "Synthesis",
            synthesis,
        )

    st.caption(
        f"agreements: {agreements} · "
        f"conflicts: {conflicts}"
    )

    # --------------------------------------------------------
    # Pair Rating caption (как было)
    # --------------------------------------------------------

    if pair_rating:

        home_rating = pair_rating.get(
            "home_rating"
        )

        away_rating = pair_rating.get(
            "away_rating"
        )

        gap = pair_rating.get(
            "rating_gap"
        )

        if gap is not None:

            try:

                gap_text = (
                    f"{int(gap):+d}"
                )

            except (
                TypeError,
                ValueError,
            ):

                gap_text = "—"

        else:

            gap_text = "—"

        source_text = (
            pair_rating_source
            if pair_rating_source is not None
            else "—"
        )

        st.caption(
            f"Pair Rating: "
            f"🏠 {home_rating} — "
            f"✈️ {away_rating} "
            f"(gap {gap_text}) "
            f"· source: {source_text}"
        )

    # --------------------------------------------------------
    # Синтез: цветовая плашка + разложение
    # --------------------------------------------------------

    if synthesis == "STRONG_CONSENSUS":

        st.success(
            "Winner Synthesis: "
            "STRONG_CONSENSUS — "
            "все сигналы согласованы."
        )

    elif synthesis == "CONSENSUS":

        st.success(
            "Winner Synthesis: "
            "CONSENSUS."
        )

    elif synthesis == "CONFLICT":

        st.error(
            "⚠️ Winner Synthesis: CONFLICT"
        )

    elif synthesis == "WEAK_CONSENSUS":

        st.info(
            "Winner Synthesis: "
            "WEAK_CONSENSUS."
        )

    elif synthesis == "DRAW_PRIMARY":

        st.info(
            "Winner Synthesis: "
            "DRAW_PRIMARY."
        )

    # --------------------------------------------------------
    # Разложение Winner Synthesis
    # --------------------------------------------------------

    _render_winner_synthesis_breakdown(
        winner_synthesis=winner_synthesis,
        pair_rating=pair_rating,
        pair_rating_source=pair_rating_source,
        winner_probability_map=winner_probability_map_pct,
    )

    # --------------------------------------------------------
    # Разложение confidence
    # --------------------------------------------------------

    st.markdown("**Confidence breakdown**")

    _render_confidence_breakdown(
        winner_synthesis=winner_synthesis,
        winner_probability_map=winner_probability_map_pct,
    )

    st.markdown(
        f"### Итоговое направление: "
        f"{winner_synthesis.get('winner', model_favorite)}"
    )

    # ========================================================
    # 1. MAIN OUTCOME
    # ========================================================

    st.subheader(
        "1. Главный исход"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            f"🏠 {home}",
            pct(
                prediction.get(
                    "home_win_probability"
                )
            ),
        )

    with c2:

        st.metric(
            "🤝 Ничья",
            pct(
                prediction.get(
                    "draw_probability"
                )
            ),
        )

    with c3:

        st.metric(
            f"✈️ {away}",
            pct(
                prediction.get(
                    "away_win_probability"
                )
            ),
        )

    c1, c2 = st.columns(2)

    with c1:

        confidence_raw = safe_float(
            prediction.get("confidence")
        )

        confidence_pct = (
            confidence_raw * 100.0
            if confidence_raw is not None
            else None
        )

        st.metric(
            "Уверенность FAJ",
            pct(confidence_pct),
        )

    with c2:

        st.metric(
            "Риск",
            prediction.get(
                "risk",
                "—",
            ),
        )

    # ========================================================
    # 2. GOALS
    # ========================================================

    st.subheader(
        "2. Голы"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            f"🏠 {home} xG",
            num(
                prediction.get(
                    "home_xg"
                )
            ),
        )

    with c2:

        st.metric(
            f"✈️ {away} xG",
            num(
                prediction.get(
                    "away_xg"
                )
            ),
        )

    btts = prediction.get(
        "btts_probability"
    )

    over25 = prediction.get(
        "over25_probability"
    )

    over35 = prediction.get(
        "over35_probability"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Обе забьют",
            (
                "ДА"
                if (
                    btts is not None
                    and btts >= 50
                )
                else "НЕТ"
            ),
        )

        st.caption(
            f"Вероятность: "
            f"{pct(btts)}"
        )

    with c2:

        st.metric(
            "ТБ 2.5",
            (
                "ДА"
                if (
                    over25 is not None
                    and over25 >= 50
                )
                else "НЕТ"
            ),
        )

        st.caption(
            f"Вероятность: "
            f"{pct(over25)}"
        )

    with c3:

        st.metric(
            "ТБ 3.5",
            (
                "ДА"
                if (
                    over35 is not None
                    and over35 >= 50
                )
                else "НЕТ"
            ),
        )

        st.caption(
            f"Вероятность: "
            f"{pct(over35)}"
        )

    # ========================================================
    # 3. SCORES
    # ========================================================

    st.subheader(
        "3. Наиболее вероятные "
        "точные счета"
    )

    top_scores = (
        score_forecast.get(
            "top_scores",
            [],
        )
        or []
    )

    if top_scores:

        cols = st.columns(
            len(top_scores[:3])
        )

        for idx, item in enumerate(
            top_scores[:3]
        ):

            score_value = (
                item.get("score")
                if isinstance(item, dict)
                else None
            )

            st.markdown(
                f"### "
                f"{score_value or '—'}"
            )

    else:

        st.write("—")

    # ========================================================
    # 4. CORNERS
    # ========================================================

    st.subheader(
        "4. Угловые"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Всего",
            num(
                prediction.get(
                    "corners_expected"
                )
            ),
        )

    with c2:

        st.metric(
            home,
            num(
                prediction.get(
                    "home_corners_expected"
                )
            ),
        )

    with c3:

        st.metric(
            away,
            num(
                prediction.get(
                    "away_corners_expected"
                )
            ),
        )

    corner_lines = [
        (
            "7.5",
            prediction.get(
                "over75_corners_probability"
            ),
        ),
        (
            "8.5",
            prediction.get(
                "over85_corners_probability"
            ),
        ),
        (
            "9.5",
            prediction.get(
                "over95_corners_probability"
            ),
        ),
        (
            "10.5",
            prediction.get(
                "over105_corners_probability"
            ),
        ),
    ]

    cols = st.columns(4)

    for col, (
        line,
        prob,
    ) in zip(
        cols,
        corner_lines,
    ):

        with col:

            st.metric(
                f"ТБ {line}",
                pct(prob),
            )

    # ========================================================
    # 5. CARDS
    # ========================================================

    st.subheader(
        "5. Карточки"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Всего",
            num(
                prediction.get(
                    "cards_expected"
                )
            ),
        )

    with c2:

        st.metric(
            home,
            num(
                prediction.get(
                    "home_cards_expected"
                )
            ),
        )

    with c3:

        st.metric(
            away,
            num(
                prediction.get(
                    "away_cards_expected"
                )
            ),
        )

    card_lines = [
        (
            "2.5",
            prediction.get(
                "over25_cards_probability"
            ),
        ),
        (
            "3.5",
            prediction.get(
                "over35_cards_probability"
            ),
        ),
        (
            "4.5",
            prediction.get(
                "over45_cards_probability"
            ),
        ),
    ]

    cols = st.columns(3)

    for col, (
        line,
        prob,
    ) in zip(
        cols,
        card_lines,
    ):

        with col:

            st.metric(
                f"ТБ {line}",
                pct(prob),
            )

    # ========================================================
    # 6. ANALYSIS
    # ========================================================

    st.subheader(
        "6. Аналитический вывод FAJ"
    )

    st.info(
        prediction.get(
            "conclusion",
            "Аналитический вывод "
            "пока недоступен.",
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

        selected_home = (
            st.selectbox(
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
        )

    with c2:

        available_away = [
            name
            for name in team_names
            if name != selected_home
        ]

        selected_away = (
            st.selectbox(
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
        )

    match[
        "home_name"
    ] = selected_home

    match[
        "away_name"
    ] = selected_away

    # ========================================================
    # CLUB RATING (display only)
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
    # FAJ PAIR RATING (manual)
    # ========================================================

    st.markdown(
        "#### 🧠 FAJ Pair Rating"
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
        min(PAIR_RATING_MAX, _home_pr_default),
    )

    _away_pr_default = max(
        PAIR_RATING_MIN,
        min(PAIR_RATING_MAX, _away_pr_default),
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

    match["home_pair_rating"] = int(home_pair_rating)
    match["away_pair_rating"] = int(away_pair_rating)

    _gap = int(home_pair_rating) - int(away_pair_rating)

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
        f"· source: manual"
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

        errors = collected.get(
            "errors",
            [],
        )

        if errors:

            with st.expander(
                "⚠️ Сообщения сбора"
            ):

                for error in errors:

                    st.warning(
                        error
                    )

    # ========================================================
    # FORM CONTEXT
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

            remove_match(index)

            st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
    )

    init_state()

    st.title(
        "⚽ FAJ Personal Prediction Brain"
    )

    st.caption(
        "FAJ Brain — математический "
        "анализ футбольной пары."
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
            != st.session_state.faj_competition
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
    # MATCHES
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

    if len(
        st.session_state.faj_matches
    ) < MAX_ANALYSIS_MATCHES:

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


if __name__ == "__main__":
    main()
