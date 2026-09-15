#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PREDICTOR — NEW ANALYTICAL INTERFACE
============================================================

Новая независимая страница прогнозирования FAJ.

АРХИТЕКТУРА:

    Soccer365
        ↓
    FACT COLLECTION
        ↓
    FAJBrain.predict()
        ↓
    BrainPrediction
        ↓
    ТОЛЬКО ОТОБРАЖЕНИЕ

Страница НЕ рассчитывает ничего математически:

    ❌ Poisson
    ❌ score_distribution
    ❌ result_probabilities
    ❌ total_probabilities
    ❌ over_probability
    ❌ GoalModel
    ❌ FormModel
    ❌ FormWin
    ❌ Defence
    ❌ CornersModel
    ❌ CardsModel
    ❌ PairRating calculation
    ❌ Winner Signal calculation
    ❌ confidence calculation
    ❌ risk calculation
    ❌ Football Data API

Единственный источник математического результата —
FAJ Brain.

НЕ ИСПОЛЬЗУЕТ:

    ETC
    Learning
    LearningEngine
    LearningMemory
    PredictionErrorAnalyzer
    old FAJ Core
    bookmaker odds
    predictions.save_prediction()
    старые prediction-поля SQLite

SQLite здесь вообще не нужен.

============================================================
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# PARSER
# ============================================================

from app.parsers.soccer365_parser import Soccer365Parser

# ============================================================
# FAJ BRAIN — единственный источник математики
# ============================================================

from app.core.faj_brain import FAJBrain

# ============================================================
# CLUB RATING (display only)
# ============================================================

from app.faj_club_ratings import get_team_rating


# ============================================================
# VERSION
# ============================================================

PREDICTOR_VERSION = "FAJ-PREDICTOR-1.1"

HISTORY_SIZE = 6


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FAJ Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# MOBILE CSS
# ============================================================

st.markdown(
    """
<style>

    /* --------------------------------------------------------
       GLOBAL
    -------------------------------------------------------- */

    .block-container {
        max-width: 1100px;
        padding-top: 1rem;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-bottom: 2rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    /* --------------------------------------------------------
       HEADER
    -------------------------------------------------------- */

    .faj-header {
        padding: 12px 14px;
        margin-bottom: 10px;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,.18);
        background: rgba(128,128,128,.06);
    }

    .faj-title {
        font-size: 26px;
        font-weight: 800;
        line-height: 1.1;
    }

    .faj-subtitle {
        font-size: 12px;
        opacity: .60;
        margin-top: 4px;
    }

    /* --------------------------------------------------------
       TEAM CARD
    -------------------------------------------------------- */

    .team-card {
        border-radius: 18px;
        padding: 14px;
        border: 1px solid rgba(128,128,128,.18);
        background: rgba(128,128,128,.045);
        margin-bottom: 8px;
    }

    .team-name {
        font-size: 18px;
        font-weight: 750;
    }

    .team-meta {
        font-size: 11px;
        opacity: .55;
        margin-top: 3px;
    }

    /* --------------------------------------------------------
       RESULT CARD
    -------------------------------------------------------- */

    .result-card {
        border-radius: 20px;
        padding: 14px;
        border: 1px solid rgba(128,128,128,.20);
        background: rgba(128,128,128,.055);
        margin: 6px 0;
    }

    .result-main {
        font-size: 30px;
        font-weight: 850;
        text-align: center;
    }

    .result-caption {
        text-align: center;
        font-size: 11px;
        opacity: .55;
        margin-top: 2px;
    }

    /* --------------------------------------------------------
       COMPACT METRIC
    -------------------------------------------------------- */

    .metric {
        border-radius: 14px;
        padding: 10px 8px;
        border: 1px solid rgba(128,128,128,.16);
        background: rgba(128,128,128,.035);
        text-align: center;
        margin-bottom: 6px;
    }

    .metric-value {
        font-size: 19px;
        font-weight: 800;
    }

    .metric-label {
        font-size: 10px;
        opacity: .55;
        margin-top: 2px;
    }

    /* --------------------------------------------------------
       SCORE
    -------------------------------------------------------- */

    .score-card {
        border-radius: 15px;
        padding: 11px;
        text-align: center;
        border: 1px solid rgba(128,128,128,.16);
        background: rgba(128,128,128,.04);
    }

    .score {
        font-size: 22px;
        font-weight: 800;
    }

    .score-label {
        font-size: 9px;
        opacity: .5;
    }

    /* --------------------------------------------------------
       SECTION
    -------------------------------------------------------- */

    .section-title {
        font-size: 16px;
        font-weight: 800;
        margin-top: 12px;
        margin-bottom: 7px;
    }

    /* --------------------------------------------------------
       CONCLUSION
    -------------------------------------------------------- */

    .conclusion {
        border-radius: 18px;
        padding: 14px;
        border: 1px solid rgba(128,128,128,.18);
        background: rgba(128,128,128,.06);
        font-size: 14px;
        line-height: 1.45;
    }

    /* --------------------------------------------------------
       FACT ROW
    -------------------------------------------------------- */

    .fact-row {
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
        border-bottom: 1px solid rgba(128,128,128,.10);
        font-size: 12px;
    }

    .fact-name {
        opacity: .60;
    }

    .fact-value {
        font-weight: 700;
    }

    /* --------------------------------------------------------
       DIAGNOSTICS BLOCK
    -------------------------------------------------------- */

    .diag-block {
        border-radius: 14px;
        padding: 12px 14px;
        border: 1px solid rgba(128,128,128,.20);
        background: rgba(128,128,128,.05);
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
        font-size: 12px;
        line-height: 1.55;
        white-space: pre-wrap;
        word-break: break-word;
    }

    .diag-block .diag-header {
        font-weight: 800;
        font-size: 13px;
        margin-bottom: 8px;
        opacity: .85;
    }

    /* --------------------------------------------------------
       MOBILE
    -------------------------------------------------------- */

    @media (max-width: 700px) {

        .block-container {
            padding-left: 0.45rem;
            padding-right: 0.45rem;
            padding-top: 0.4rem;
        }

        .faj-title {
            font-size: 22px;
        }

        .team-name {
            font-size: 16px;
        }

        .metric-value {
            font-size: 17px;
        }

        .result-main {
            font-size: 27px;
        }

        .section-title {
            font-size: 14px;
        }

        .diag-block {
            font-size: 11px;
        }
    }

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def safe_float(value: Any) -> Optional[float]:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:

        value = float(value)

        if math.isfinite(value):
            return value

    except (TypeError, ValueError):
        pass

    return None


def safe_int(value: Any) -> Optional[int]:

    value = safe_float(value)

    if value is None:
        return None

    return int(round(value))


def probability(value: Optional[float]) -> Optional[float]:
    """
    Клампит значение в [0, 100].

    ВАЖНО:
        BrainPrediction уже отдаёт *проценты* для
        *_probability полей (home_win_probability,
        btts_probability, over25_probability и т.д.),
        поэтому повторное умножение на 100 здесь
        НЕ делается.
    """

    if value is None:
        return None

    return round(
        max(0.0, min(100.0, float(value))),
        1,
    )


def value(obj: Any, *names: str) -> Any:

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


def nested(
    obj: Any,
    *names: str,
) -> Any:

    current = obj

    for name in names:

        current = value(
            current,
            name,
        )

        if current is None:
            return None

    return current


# ============================================================
# PARSER → MATCH FACT
# ============================================================

def parse_match(
    parser: Soccer365Parser,
    url: str,
) -> Dict[str, Any]:

    url = (url or "").strip()

    if not url:
        raise ValueError("Пустой URL.")

    result = parser.parse(url)

    if result.get("error"):
        raise ValueError(
            str(result["error"])
        )

    stats = result.get(
        "stats",
        {},
    )

    if not isinstance(stats, dict):
        stats = {}

    result["stats"] = stats

    return result


# ============================================================
# BUILD TEAM MATCH RECORD
# ============================================================

def build_team_record(
    parsed: Dict[str, Any],
    team_name: str,
) -> Optional[Dict[str, Any]]:

    home_team = parsed.get(
        "home_team"
    )

    away_team = parsed.get(
        "away_team"
    )

    if not home_team or not away_team:
        return None

    team_name_low = team_name.strip().lower()

    home_low = str(
        home_team
    ).strip().lower()

    away_low = str(
        away_team
    ).strip().lower()

    if team_name_low == home_low:

        is_home = True

        team = home_team
        opponent = away_team

        side = "home"

        goals_for = None
        goals_against = None

        score = parsed.get(
            "score"
        )

        if score:

            parts = re.split(
                r"[:\-]",
                score,
            )

            if len(parts) >= 2:

                goals_for = safe_int(
                    parts[0]
                )

                goals_against = safe_int(
                    parts[1]
                )

    elif team_name_low == away_low:

        is_home = False

        team = away_team
        opponent = home_team

        side = "away"

        goals_for = None
        goals_against = None

        score = parsed.get(
            "score"
        )

        if score:

            parts = re.split(
                r"[:\-]",
                score,
            )

            if len(parts) >= 2:

                goals_for = safe_int(
                    parts[1]
                )

                goals_against = safe_int(
                    parts[0]
                )

    else:

        return None

    stats = parsed.get(
        "stats",
        {},
    )

    def stat(name: str) -> Any:

        home_key = (
            f"home_{name}"
        )

        away_key = (
            f"away_{name}"
        )

        if is_home:
            return stats.get(home_key)

        return stats.get(away_key)

    def opponent_stat(name: str) -> Any:

        home_key = (
            f"home_{name}"
        )

        away_key = (
            f"away_{name}"
        )

        if is_home:
            return stats.get(away_key)

        return stats.get(home_key)

    result_code = None

    if (
        goals_for is not None
        and goals_against is not None
    ):

        if goals_for > goals_against:
            result_code = "W"

        elif goals_for < goals_against:
            result_code = "L"

        else:
            result_code = "D"

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    xg = safe_float(
        stat("xg")
    )

    opponent_xg = safe_float(
        opponent_stat("xg")
    )

    # --------------------------------------------------------
    # Extra factual statistics
    # --------------------------------------------------------

    extra = {

        "opponent_xg":
            opponent_xg,

        "shots":
            safe_int(
                stat("shots")
            ),

        "opponent_shots":
            safe_int(
                opponent_stat("shots")
            ),

        "shots_on_target":
            safe_int(
                stat("shots_on_target")
            ),

        "opponent_shots_on_target":
            safe_int(
                opponent_stat(
                    "shots_on_target"
                )
            ),

        "blocked_shots":
            safe_int(
                stat("blocked_shots")
            ),

        "opponent_blocked_shots":
            safe_int(
                opponent_stat(
                    "blocked_shots"
                )
            ),

        "big_chances":
            safe_int(
                stat("big_chances")
            ),

        "opponent_big_chances":
            safe_int(
                opponent_stat(
                    "big_chances"
                )
            ),

        "possession":
            safe_float(
                stat("possession")
            ),

        "opponent_possession":
            safe_float(
                opponent_stat(
                    "possession"
                )
            ),

        "corners":
            safe_int(
                stat("corners")
            ),

        "opponent_corners":
            safe_int(
                opponent_stat(
                    "corners"
                )
            ),

        "passes":
            safe_int(
                stat("total_passes")
            ),

        "opponent_passes":
            safe_int(
                opponent_stat(
                    "total_passes"
                )
            ),

        "pass_accuracy":
            safe_float(
                stat("pass_accuracy")
            ),

        "opponent_pass_accuracy":
            safe_float(
                opponent_stat(
                    "pass_accuracy"
                )
            ),

        "fouls":
            safe_int(
                stat("fouls")
            ),

        "offsides":
            safe_int(
                stat("offsides")
            ),

        "yellow_cards":
            safe_int(
                stat("yellow_cards")
            ),

        "opponent_yellow_cards":
            safe_int(
                opponent_stat(
                    "yellow_cards"
                )
            ),

        "red_cards":
            safe_int(
                stat("red_cards")
            ),

        "crosses":
            safe_int(
                stat("crosses")
            ),

        "opponent_crosses":
            safe_int(
                opponent_stat("crosses")
            ),
    }

    return {

        "team":
            team,

        "team_name":
            team,

        "opponent":
            opponent,

        "is_home":
            is_home,

        "venue":
            "home"
            if is_home
            else "away",

        "goals_for":
            goals_for,

        "goals_against":
            goals_against,

        "result":
            result_code,

        "xg":
            xg,

        "xga":
            opponent_xg,

        "corners":
            extra["corners"],

        "opponent_corners":
            extra["opponent_corners"],

        "yellow_cards":
            extra["yellow_cards"],

        "opponent_yellow_cards":
            extra[
                "opponent_yellow_cards"
            ],

        "match_date":
            parsed.get(
                "match_date"
            ),

        "competition":
            parsed.get(
                "competition"
            ),

        "extra":
            extra,
    }


# ============================================================
# COLLECT HISTORY
# ============================================================

def collect_history(
    parser: Soccer365Parser,
    team_name: str,
    urls: List[str],
) -> Tuple[
    List[Dict[str, Any]],
    List[str],
]:

    records = []

    errors = []

    for index, url in enumerate(
        urls,
        start=1,
    ):

        url = (
            url or ""
        ).strip()

        if not url:
            continue

        try:

            parsed = parse_match(
                parser,
                url,
            )

            record = build_team_record(
                parsed,
                team_name,
            )

            if record is None:

                errors.append(
                    f"Матч {index}: "
                    f"{team_name} не найден "
                    f"на странице."
                )

                continue

            # ====================================================
            # TEAM METADATA
            # ====================================================

            record["team"] = team_name
            record["team_name"] = team_name

            if record.get("is_home") is True:
                record["venue"] = "home"
            elif record.get("is_home") is False:
                record["venue"] = "away"

            records.append(
                record
            )

        except Exception as exc:

            errors.append(
                f"Матч {index}: {exc}"
            )

    # ====================================================
    # CANONICAL HISTORY ORDER
    # ====================================================

    records.sort(
        key=lambda item: (
            item.get(
                "match_date"
            )
            or ""
        )
    )

    records = records[
        -HISTORY_SIZE:
    ]

    return (
        records,
        errors,
    )


# ============================================================
# FAJ BRAIN — CANONICAL PREDICTION
# ============================================================

def calculate_prediction(
    home_team: str,
    away_team: str,
    home_records: List[Dict[str, Any]],
    away_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Единственная точка математического расчёта страницы.

    Все xG / Poisson / 1X2 / BTTS / totals /
    exact scores / Winner Synthesis / Pair Rating /
    Corners / Cards / confidence / risk

    приходят только из FAJBrain.

    Predictor ничего не пересчитывает.
    """

    brain = FAJBrain()

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_records,
        away_matches=away_records,
    )

    if not isinstance(result, dict):
        raise TypeError(
            "FAJBrain.predict() должен вернуть dict."
        )

    return result


# ============================================================
# SESSION STATE
# ============================================================

if "faj_prediction" not in st.session_state:
    st.session_state.faj_prediction = None

if "faj_home_records" not in st.session_state:
    st.session_state.faj_home_records = []

if "faj_away_records" not in st.session_state:
    st.session_state.faj_away_records = []

if "faj_collection_errors" not in st.session_state:
    st.session_state.faj_collection_errors = []


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
<div class="faj-header">
    <div class="faj-title">⚽ FAJ Predictor</div>
    <div class="faj-subtitle">
        Единый математический мозг — FAJ Brain · Form · Defence · xG · Score · Corners · Cards
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# MATCH INPUT
# ============================================================

left, right = st.columns(
    2,
    gap="small",
)

with left:

    home_team = st.text_input(
        "Хозяева",
        placeholder="Динамо Махачкала",
        key="faj_home_team",
    )

with right:

    away_team = st.text_input(
        "Гости",
        placeholder="Краснодар",
        key="faj_away_team",
    )


# ============================================================
# FAJ CLUB RATING (display only)
# ============================================================

_home_club_rating = (
    get_team_rating(home_team.strip())
    if home_team.strip()
    else None
)

_away_club_rating = (
    get_team_rating(away_team.strip())
    if away_team.strip()
    else None
)

st.markdown(
    '<div class="section-title">FAJ Club Rating</div>',
    unsafe_allow_html=True,
)

club_c1, club_c2 = st.columns(2, gap="small")

with club_c1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {_home_club_rating if _home_club_rating is not None else "—"}
            </div>
            <div class="metric-label">
                {home_team or "Хозяева"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with club_c2:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {_away_club_rating if _away_club_rating is not None else "—"}
            </div>
            <div class="metric-label">
                {away_team or "Гости"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HISTORY INPUT
# ============================================================

st.markdown(
    '<div class="section-title">История хозяев — последние 6 матчей</div>',
    unsafe_allow_html=True,
)

home_url_text = st.text_area(
    "Soccer365 URL",
    placeholder=(
        "Вставь 6 URL, по одному на строку.\n"
        "Старые сверху, новые снизу."
    ),
    height=125,
    key="faj_home_urls",
    label_visibility="collapsed",
)

st.markdown(
    '<div class="section-title">История гостей — последние 6 матчей</div>',
    unsafe_allow_html=True,
)

away_url_text = st.text_area(
    "Soccer365 URL",
    placeholder=(
        "Вставь 6 URL, по одному на строку.\n"
        "Старые сверху, новые снизу."
    ),
    height=125,
    key="faj_away_urls",
    label_visibility="collapsed",
)


# ============================================================
# ACTION
# ============================================================

predict_clicked = st.button(
    "🔮 СОБРАТЬ ДАННЫЕ И РАССЧИТАТЬ",
    type="primary",
    use_container_width=True,
)


# ============================================================
# PREDICT
# ============================================================

if predict_clicked:

    if not home_team.strip():
        st.error(
            "Укажи команду хозяев."
        )
        st.stop()

    if not away_team.strip():
        st.error(
            "Укажи команду гостей."
        )
        st.stop()

    home_urls = [
        item.strip()
        for item in home_url_text.splitlines()
        if item.strip()
    ]

    away_urls = [
        item.strip()
        for item in away_url_text.splitlines()
        if item.strip()
    ]

    if not home_urls:
        st.error(
            "Нет URL истории хозяев."
        )
        st.stop()

    if not away_urls:
        st.error(
            "Нет URL истории гостей."
        )
        st.stop()

    parser = Soccer365Parser()

    progress = st.progress(
        0,
        text="Собираю факты Soccer365…",
    )

    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    home_records, home_errors = (
        collect_history(
            parser,
            home_team.strip(),
            home_urls,
        )
    )

    progress.progress(
        45,
        text="История хозяев собрана…",
    )

    # --------------------------------------------------------
    # AWAY
    # --------------------------------------------------------

    away_records, away_errors = (
        collect_history(
            parser,
            away_team.strip(),
            away_urls,
        )
    )

    progress.progress(
        75,
        text="История гостей собрана…",
    )

    all_errors = (
        home_errors
        + away_errors
    )

    if not home_records:

        progress.empty()

        st.error(
            "Не удалось собрать историю хозяев."
        )

        if all_errors:

            for error in all_errors:
                st.warning(error)

        st.stop()

    if not away_records:

        progress.empty()

        st.error(
            "Не удалось собрать историю гостей."
        )

        if all_errors:

            for error in all_errors:
                st.warning(error)

        st.stop()

    # --------------------------------------------------------
    # CANONICAL CALCULATION — FAJ BRAIN ONLY
    # --------------------------------------------------------

    try:

        prediction = calculate_prediction(
            home_team.strip(),
            away_team.strip(),
            home_records,
            away_records,
        )

    except Exception as exc:

        progress.empty()

        st.error(
            f"Ошибка расчёта FAJ Brain: {exc}"
        )

        st.exception(exc)

        st.stop()

    progress.progress(
        100,
        text="FAJ Brain расчёт завершён.",
    )

    progress.empty()

    st.session_state.faj_prediction = (
        prediction
    )

    st.session_state.faj_home_records = (
        home_records
    )

    st.session_state.faj_away_records = (
        away_records
    )

    st.session_state.faj_collection_errors = (
        all_errors
    )


# ============================================================
# RESULT
# ============================================================

prediction = (
    st.session_state.faj_prediction
)

if prediction is None:

    st.info(
        "Введи команды и URL последних матчей, "
        "затем запусти расчёт."
    )

    st.stop()


# ============================================================
# ERRORS / WARNINGS
# ============================================================

collection_errors = (
    st.session_state.faj_collection_errors
)

if collection_errors:

    with st.expander(
        "⚠️ Замечания при сборе данных",
        expanded=False,
    ):

        for error in collection_errors:
            st.write(
                f"• {error}"
            )


# ============================================================
# META EXTRACTION
# ============================================================

_meta = prediction.get(
    "calculation_meta",
    {},
) or {}

_winner_synthesis = _meta.get(
    "winner_synthesis",
) or {}

_pair_rating = _meta.get(
    "pair_rating",
) or {}

_score_forecast = _meta.get(
    "score_forecast",
) or {}

_goal_model_meta = _meta.get(
    "goal_model",
) or {}

_top_scores = _score_forecast.get(
    "top_scores",
) or []


# ============================================================
# TOP MATCH CARD
# ============================================================

st.markdown(
    f"""
<div class="result-card">

    <div class="result-main">
        {prediction.get("home_team", "—")}
        &nbsp; — &nbsp;
        {prediction.get("away_team", "—")}
    </div>

    <div class="result-caption">
        {prediction.get("analysis_mode", "—")}
        · история {prediction.get("home_matches", 0)} / {prediction.get("away_matches", 0)}
    </div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# 1X2
# ============================================================

st.markdown(
    '<div class="section-title">Результат</div>',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(
    3,
    gap="small",
)

with c1:

    _hp = probability(prediction.get("home_win_probability"))
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_hp:.1f}%" if _hp is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("home_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:

    _dp = probability(prediction.get("draw_probability"))
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_dp:.1f}%" if _dp is not None else "—"}
            </div>
            <div class="metric-label">
                НИЧЬЯ
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:

    _ap = probability(prediction.get("away_win_probability"))
    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_ap:.1f}%" if _ap is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("away_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# XG
# ============================================================

st.markdown(
    '<div class="section-title">xG</div>',
    unsafe_allow_html=True,
)

x1, x2, x3 = st.columns(
    3,
    gap="small",
)

_hxg = safe_float(prediction.get("home_xg"))
_axg = safe_float(prediction.get("away_xg"))
_total_xg = (
    _hxg + _axg
    if _hxg is not None and _axg is not None
    else None
)

with x1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_hxg:.2f}" if _hxg is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("home_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with x2:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_total_xg:.2f}" if _total_xg is not None else "—"}
            </div>
            <div class="metric-label">
                TOTAL xG
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with x3:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_axg:.2f}" if _axg is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("away_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SCORES
# ============================================================

st.markdown(
    '<div class="section-title">Наиболее вероятные счета</div>',
    unsafe_allow_html=True,
)

score_cols = st.columns(
    3,
    gap="small",
)

# top_scores ожидается в формате:
#     [{"score": "1:0", "probability": 0.123}, ...]
#
# Источник — calculation_meta["score_forecast"]["top_scores"]
# от Brain (ScorePredictor v2.2). Ничего не пересчитываем.

for column, item, index in zip(
    score_cols,
    _top_scores[:3],
    range(1, 4),
):

    with column:

        _score_value = (
            item.get("score")
            if isinstance(item, dict)
            else None
        )

        _score_prob = (
            safe_float(item.get("probability"))
            if isinstance(item, dict)
            else None
        )

        _score_pct = (
            round(_score_prob * 100.0, 1)
            if _score_prob is not None
            else None
        )

        st.markdown(
            f"""
            <div class="score-card">
                <div class="score">
                    {_score_value or "—"}
                </div>
                <div class="score-label">
                    #{index} · {f"{_score_pct:.1f}%" if _score_pct is not None else "—"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# GOALS
# ============================================================

st.markdown(
    '<div class="section-title">Голы</div>',
    unsafe_allow_html=True,
)

g1, g2, g3 = st.columns(
    3,
    gap="small",
)

_btts = probability(prediction.get("btts_probability"))
_o25 = probability(prediction.get("over25_probability"))
_o35 = probability(prediction.get("over35_probability"))

with g1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_btts:.1f}%" if _btts is not None else "—"}
            </div>
            <div class="metric-label">
                BTTS
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with g2:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_o25:.1f}%" if _o25 is not None else "—"}
            </div>
            <div class="metric-label">
                ТБ 2.5
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with g3:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_o35:.1f}%" if _o35 is not None else "—"}
            </div>
            <div class="metric-label">
                ТБ 3.5
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CORNERS
# ============================================================

st.markdown(
    '<div class="section-title">Угловые</div>',
    unsafe_allow_html=True,
)

_hc = safe_float(prediction.get("home_corners_expected"))
_ac = safe_float(prediction.get("away_corners_expected"))
_tc = safe_float(prediction.get("corners_expected"))

c1, c2, c3 = st.columns(
    3,
    gap="small",
)

with c1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_hc:.2f}" if _hc is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("home_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_tc:.2f}" if _tc is not None else "—"}
            </div>
            <div class="metric-label">
                TOTAL
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_ac:.2f}" if _ac is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("away_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

corner_cols = st.columns(
    4,
    gap="small",
)

corner_lines = [
    ("ТБ 7.5", probability(prediction.get("over75_corners_probability"))),
    ("ТБ 8.5", probability(prediction.get("over85_corners_probability"))),
    ("ТБ 9.5", probability(prediction.get("over95_corners_probability"))),
    ("ТБ 10.5", probability(prediction.get("over105_corners_probability"))),
]

for column, (
    label,
    p,
) in zip(
    corner_cols,
    corner_lines,
):

    with column:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-value">
                    {f"{p:.1f}%" if p is not None else "—"}
                </div>
                <div class="metric-label">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# CARDS
# ============================================================

st.markdown(
    '<div class="section-title">Карточки</div>',
    unsafe_allow_html=True,
)

_hcards = safe_float(prediction.get("home_cards_expected"))
_acards = safe_float(prediction.get("away_cards_expected"))
_tcards = safe_float(prediction.get("cards_expected"))

card_cols = st.columns(
    3,
    gap="small",
)

with card_cols[0]:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_hcards:.2f}" if _hcards is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("home_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with card_cols[1]:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_tcards:.2f}" if _tcards is not None else "—"}
            </div>
            <div class="metric-label">
                TOTAL
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with card_cols[2]:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_acards:.2f}" if _acards is not None else "—"}
            </div>
            <div class="metric-label">
                {prediction.get("away_team", "—")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

card_lines = [
    ("ТБ 2.5", probability(prediction.get("over25_cards_probability"))),
    ("ТБ 3.5", probability(prediction.get("over35_cards_probability"))),
    ("ТБ 4.5", probability(prediction.get("over45_cards_probability"))),
]

card_probability_cols = st.columns(
    3,
    gap="small",
)

for column, (
    label,
    p,
) in zip(
    card_probability_cols,
    card_lines,
):

    with column:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-value">
                    {f"{p:.1f}%" if p is not None else "—"}
                </div>
                <div class="metric-label">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# CONFIDENCE / RISK
# ============================================================

st.markdown(
    '<div class="section-title">Надёжность анализа</div>',
    unsafe_allow_html=True,
)

_conf_raw = safe_float(prediction.get("confidence"))
_conf_pct = (
    round(_conf_raw * 100.0, 1)
    if _conf_raw is not None
    else None
)

_dq = safe_float(prediction.get("data_quality"))
_risk = prediction.get("risk", "—")

q1, q2, q3 = st.columns(
    3,
    gap="small",
)

with q1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_conf_pct:.1f}%" if _conf_pct is not None else "—"}
            </div>
            <div class="metric-label">
                CONFIDENCE
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with q2:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {f"{_dq:.1f}%" if _dq is not None else "—"}
            </div>
            <div class="metric-label">
                DATA QUALITY
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with q3:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {_risk}
            </div>
            <div class="metric-label">
                RISK
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CONCLUSION
# ============================================================

st.markdown(
    '<div class="section-title">Вывод FAJ</div>',
    unsafe_allow_html=True,
)

_favorite = (
    _winner_synthesis.get("winner")
    or prediction.get("home_team", "—")
)

st.markdown(
    f"""
<div class="conclusion">

<b>{_favorite}</b><br><br>

{prediction.get("conclusion", "")}

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# WINNER SYNTHESIS
# ============================================================

if _winner_synthesis:

    st.markdown(
        '<div class="section-title">Winner Synthesis</div>',
        unsafe_allow_html=True,
    )

    _ws1, _ws2 = st.columns(2, gap="small")

    _pair_direction = (
        _winner_synthesis.get("pair_rating_direction")
        or "—"
    )

    _pair_strength = (
        _winner_synthesis.get("pair_rating_strength")
        or "—"
    )

    with _ws1:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-value">
                    {_winner_synthesis.get("winner", "—")}
                </div>
                <div class="metric-label">
                    MODEL FAVORITE
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with _ws2:

        st.markdown(
            f"""
            <div class="metric">
                <div class="metric-value">
                    {_pair_direction}
                </div>
                <div class="metric-label">
                    PAIR DIRECTION ({_pair_strength})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _synthesis = _winner_synthesis.get("synthesis", "—")

    _agreement_color = {
        "STRONG_CONSENSUS": "rgba(46,160,67,.20)",
        "CONSENSUS": "rgba(46,160,67,.12)",
        "WEAK_CONSENSUS": "rgba(128,128,128,.10)",
        "DRAW_PRIMARY": "rgba(128,128,128,.10)",
        "CONFLICT": "rgba(210,80,80,.20)",
    }.get(_synthesis, "rgba(128,128,128,.10)")

    _agreements = _winner_synthesis.get("agreements", 0)
    _conflicts = _winner_synthesis.get("conflicts", 0)

    st.markdown(
        f"""
        <div class="result-card"
             style="background:{_agreement_color};">
            <div class="result-main">
                {_winner_synthesis.get("winner", "—")}
            </div>
            <div class="result-caption">
                SYNTHESIS: {_synthesis}
                · agreements {_agreements} · conflicts {_conflicts}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FAJ BRAIN DIAGNOSTICS
# ============================================================

st.markdown(
    '<div class="section-title">FAJ Brain Diagnostics</div>',
    unsafe_allow_html=True,
)

_b1, _b2, _b3, _b4 = st.columns(
    4,
    gap="small",
)

with _b1:
    st.metric(
        "Brain λ Home",
        f"{_hxg:.3f}" if _hxg is not None else "—",
    )

with _b2:
    st.metric(
        "Brain λ Away",
        f"{_axg:.3f}" if _axg is not None else "—",
    )

with _b3:
    st.metric(
        "Winner",
        str(
            (_winner_synthesis or {}).get(
                "winner",
                "—",
            )
        ),
    )

with _b4:
    st.metric(
        "Confidence",
        (
            f"{_conf_pct:.1f}%"
            if _conf_pct is not None
            else "—"
        ),
    )

with st.expander(
    "Winner Synthesis",
    expanded=False,
):
    st.json(_winner_synthesis or {})

with st.expander(
    "Pair Rating",
    expanded=False,
):
    st.json(_pair_rating or {})

with st.expander(
    "Score Forecast",
    expanded=False,
):
    st.json(_score_forecast or {})

with st.expander(
    "Brain calculation meta (full)",
    expanded=False,
):
    st.json(_meta)


# ============================================================
# FACT HISTORY
# ============================================================

st.markdown(
    '<div class="section-title">Использованная история</div>',
    unsafe_allow_html=True,
)

with st.expander(
    "Показать факты матчей",
    expanded=False,
):

    home_records = (
        st.session_state.faj_home_records
    )

    away_records = (
        st.session_state.faj_away_records
    )

    st.markdown(
        f"### {prediction.get('home_team', '—')}"
    )

    for record in home_records:

        score_text = (
            f"{record.get('goals_for')}:"
            f"{record.get('goals_against')}"
            if (
                record.get("goals_for")
                is not None
                and record.get("goals_against")
                is not None
            )
            else "—"
        )

        xg_text = (
            f"{record.get('xg'):.2f}"
            if record.get("xg") is not None
            else "—"
        )

        st.markdown(
            f"""
            <div class="fact-row">
                <span class="fact-name">
                    {record.get("match_date") or "—"}
                    ·
                    {record.get("opponent") or "—"}
                </span>

                <span class="fact-value">
                    {score_text}
                    · xG {xg_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"### {prediction.get('away_team', '—')}"
    )

    for record in away_records:

        score_text = (
            f"{record.get('goals_for')}:"
            f"{record.get('goals_against')}"
            if (
                record.get("goals_for")
                is not None
                and record.get("goals_against")
                is not None
            )
            else "—"
        )

        xg_text = (
            f"{record.get('xg'):.2f}"
            if record.get("xg") is not None
            else "—"
        )

        st.markdown(
            f"""
            <div class="fact-row">
                <span class="fact-name">
                    {record.get("match_date") or "—"}
                    ·
                    {record.get("opponent") or "—"}
                </span>

                <span class="fact-value">
                    {score_text}
                    · xG {xg_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# 🔬 GOALMODEL v6.0 DIAGNOSTICS
#
# Источник: calculation_meta["goal_model"] (Brain).
# Никакой математики — только чтение готового JSON.
# ============================================================

st.markdown(
    '<div class="section-title">🔬 GoalModel v6.0 Diagnostics</div>',
    unsafe_allow_html=True,
)

_diagnostics = (
    _goal_model_meta.get("diagnostics")
    if isinstance(_goal_model_meta, dict)
    else None
)

if _diagnostics is None or not isinstance(_diagnostics, dict):

    st.info("GoalModel diagnostics недоступны.")

else:

    _version_val = _diagnostics.get("version", "—")
    _status_val = _diagnostics.get("status", "—")

    st.write(
        f"**Version:** {_version_val}  ·  "
        f"**Status:** {_status_val}"
    )

    # ------------------------------------------------
    # HOME
    # ------------------------------------------------

    _home_diag = _diagnostics.get("home", {}) or {}

    if _home_diag:

        st.markdown("**Home**")

        _h1, _h2, _h3 = st.columns(3)

        with _h1:
            st.metric(
                "Structural Attack",
                f"{safe_float(_home_diag.get('structural_attack')):.3f}"
                if safe_float(_home_diag.get("structural_attack")) is not None
                else "—",
            )

        with _h2:
            st.metric(
                "Recent Attack",
                f"{safe_float(_home_diag.get('recent_attack')):.3f}"
                if safe_float(_home_diag.get("recent_attack")) is not None
                else "—",
            )

        with _h3:
            st.metric(
                "Effective Attack",
                f"{safe_float(_home_diag.get('effective_attack')):.3f}"
                if safe_float(_home_diag.get("effective_attack")) is not None
                else "—",
            )

        _h4, _h5, _h6 = st.columns(3)

        with _h4:
            st.metric(
                "Match Attack",
                f"{safe_float(_home_diag.get('match_attack')):.3f}"
                if safe_float(_home_diag.get("match_attack")) is not None
                else "—",
            )

        with _h5:
            st.metric(
                "Venue Attack xG",
                f"{safe_float(_home_diag.get('venue_attack_xg')):.3f}"
                if safe_float(_home_diag.get("venue_attack_xg")) is not None
                else "—",
            )

        with _h6:
            st.metric(
                "Effective xGA",
                f"{safe_float(_home_diag.get('effective_xga')):.3f}"
                if safe_float(_home_diag.get("effective_xga")) is not None
                else "—",
            )

    # ------------------------------------------------
    # AWAY
    # ------------------------------------------------

    _away_diag = _diagnostics.get("away", {}) or {}

    if _away_diag:

        st.markdown("**Away**")

        _a1, _a2, _a3 = st.columns(3)

        with _a1:
            st.metric(
                "Structural Attack",
                f"{safe_float(_away_diag.get('structural_attack')):.3f}"
                if safe_float(_away_diag.get("structural_attack")) is not None
                else "—",
            )

        with _a2:
            st.metric(
                "Recent Attack",
                f"{safe_float(_away_diag.get('recent_attack')):.3f}"
                if safe_float(_away_diag.get("recent_attack")) is not None
                else "—",
            )

        with _a3:
            st.metric(
                "Effective Attack",
                f"{safe_float(_away_diag.get('effective_attack')):.3f}"
                if safe_float(_away_diag.get("effective_attack")) is not None
                else "—",
            )

        _a4, _a5, _a6 = st.columns(3)

        with _a4:
            st.metric(
                "Match Attack",
                f"{safe_float(_away_diag.get('match_attack')):.3f}"
                if safe_float(_away_diag.get("match_attack")) is not None
                else "—",
            )

        with _a5:
            st.metric(
                "Venue Attack xG",
                f"{safe_float(_away_diag.get('venue_attack_xg')):.3f}"
                if safe_float(_away_diag.get("venue_attack_xg")) is not None
                else "—",
            )

        with _a6:
            st.metric(
                "Effective xGA",
                f"{safe_float(_away_diag.get('effective_xga')):.3f}"
                if safe_float(_away_diag.get("effective_xga")) is not None
                else "—",
            )

    # ------------------------------------------------
    # VENUE
    # ------------------------------------------------

    _venue_diag = _diagnostics.get("venue", {}) or {}

    if _venue_diag:

        st.markdown("**Venue**")

        _v1, _v2, _v3 = st.columns(3)

        with _v1:
            st.metric(
                "Split Available",
                "YES" if _venue_diag.get("venue_split_available") else "NO",
            )

        with _v2:
            st.metric(
                "HA Applied",
                "YES" if _venue_diag.get("home_advantage_applied") else "NO",
            )

        with _v3:
            st.metric(
                "HA Fallback",
                f"{safe_float(_venue_diag.get('home_advantage_fallback')):.3f}"
                if safe_float(_venue_diag.get("home_advantage_fallback")) is not None
                else "—",
            )

    # ------------------------------------------------
    # LAMBDA
    # ------------------------------------------------

    _lambda_data = _diagnostics.get("lambda", {}) or {}

    if _lambda_data:

        st.markdown("**Final Lambda**")

        _l1, _l2, _l3 = st.columns(3)

        with _l1:
            st.metric(
                "λ Home",
                f"{safe_float(_lambda_data.get('home')):.3f}"
                if safe_float(_lambda_data.get("home")) is not None
                else "—",
            )

        with _l2:
            st.metric(
                "λ Away",
                f"{safe_float(_lambda_data.get('away')):.3f}"
                if safe_float(_lambda_data.get("away")) is not None
                else "—",
            )

        with _l3:
            st.metric(
                "λ Total",
                f"{safe_float(_lambda_data.get('total')):.3f}"
                if safe_float(_lambda_data.get("total")) is not None
                else "—",
            )

    # ------------------------------------------------
    # FULL JSON
    # ------------------------------------------------

    with st.expander("📋 Полный diagnostics (JSON)", expanded=False):
        st.json(_diagnostics)

    # ------------------------------------------------
    # COPY BUTTON
    # ------------------------------------------------

    _report_lines = []
    _report_lines.append("FAJ GOALMODEL v6.0 DIAGNOSTICS")
    _report_lines.append("================================")
    _report_lines.append(
        f"Match: {prediction.get('home_team', '—')} — {prediction.get('away_team', '—')}"
    )
    _report_lines.append(
        f"Model: GoalModel v{_version_val} ({_status_val})"
    )
    _report_lines.append("")

    _report_lines.append("HOME")
    _report_lines.append(
        f"Structural Attack: {safe_float(_home_diag.get('structural_attack')):.3f}"
        if safe_float(_home_diag.get("structural_attack")) is not None
        else "Structural Attack: —"
    )
    _report_lines.append(
        f"Recent Attack:     {safe_float(_home_diag.get('recent_attack')):.3f}"
        if safe_float(_home_diag.get("recent_attack")) is not None
        else "Recent Attack:     —"
    )
    _report_lines.append(
        f"Effective Attack:  {safe_float(_home_diag.get('effective_attack')):.3f}"
        if safe_float(_home_diag.get("effective_attack")) is not None
        else "Effective Attack:  —"
    )
    _report_lines.append("")

    _report_lines.append("AWAY")
    _report_lines.append(
        f"Structural Attack: {safe_float(_away_diag.get('structural_attack')):.3f}"
        if safe_float(_away_diag.get("structural_attack")) is not None
        else "Structural Attack: —"
    )
    _report_lines.append(
        f"Recent Attack:     {safe_float(_away_diag.get('recent_attack')):.3f}"
        if safe_float(_away_diag.get("recent_attack")) is not None
        else "Recent Attack:     —"
    )
    _report_lines.append(
        f"Effective Attack:  {safe_float(_away_diag.get('effective_attack')):.3f}"
        if safe_float(_away_diag.get("effective_attack")) is not None
        else "Effective Attack:  —"
    )
    _report_lines.append("")

    _report_lines.append("LAMBDA")
    _report_lines.append(
        f"λ Home:  {safe_float(_lambda_data.get('home')):.3f}"
        if safe_float(_lambda_data.get("home")) is not None
        else "λ Home:  —"
    )
    _report_lines.append(
        f"λ Away:  {safe_float(_lambda_data.get('away')):.3f}"
        if safe_float(_lambda_data.get("away")) is not None
        else "λ Away:  —"
    )
    _report_lines.append(
        f"λ Total: {safe_float(_lambda_data.get('total')):.3f}"
        if safe_float(_lambda_data.get("total")) is not None
        else "λ Total: —"
    )

    _report_text = "\n".join(_report_lines)

    _copy_payload = (
        _report_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )

    _copy_html = f"""
<div style="margin-top:8px;">
<button id="faj-copy-btn" style="
    width:100%;
    padding:10px 14px;
    border-radius:12px;
    border:1px solid rgba(128,128,128,.35);
    background:rgba(128,128,128,.10);
    color:inherit;
    font-size:14px;
    font-weight:700;
    cursor:pointer;
">📋 СКОПИРОВАТЬ ДИАГНОСТИКУ</button>
<div id="faj-copy-status" style="
    margin-top:6px;
    font-size:11px;
    opacity:.6;
    text-align:center;
"></div>
</div>
<script>
(function() {{
    const text = `{_copy_payload}`;
    const btn = document.getElementById('faj-copy-btn');
    const status = document.getElementById('faj-copy-status');
    if (!btn) return;
    btn.addEventListener('click', async function() {{
        try {{
            if (navigator.clipboard && window.isSecureContext) {{
                await navigator.clipboard.writeText(text);
            }} else {{
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            }}
            status.innerText = '✅ Скопировано';
            setTimeout(function() {{ status.innerText = ''; }}, 2000);
        }} catch (e) {{
            status.innerText = '❌ Ошибка копирования';
        }}
    }});
}})();
</script>
"""

    components.html(
        _copy_html,
        height=90,
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
<div style="
    text-align:center;
    opacity:.35;
    font-size:10px;
    padding-top:15px;
">
    FAJ Predictor 1.1 · Single source of truth: FAJ Brain ·
    No ETC · No Learning · No bookmaker odds · No Football Data API
</div>
""",
    unsafe_allow_html=True,
)
