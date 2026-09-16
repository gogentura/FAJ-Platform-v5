#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PREDICTOR — STREAMLIT APP
============================================================

ИНТЕРФЕЙС:
    Лига / турнир
    ↓
    Хозяева / гости
    ↓
    6 URL HOME + 6 URL AWAY
    ↓
    Soccer365Parser
    ↓
    FACT RECORDS
    ↓
    FAJBrain.predict()
    ↓
    FINAL FAJ BRAIN RESULT
    ↓
    DISPLAY ONLY

ВАЖНО:
- UI НЕ считает Poisson.
- UI НЕ считает 1X2.
- UI НЕ считает BTTS.
- UI НЕ считает totals.
- UI НЕ считает score distribution.
- UI НЕ рассчитывает xG.
- UI НЕ рассчитывает GoalModel.
- UI НЕ рассчитывает ProbabilityModel.
- UI НЕ рассчитывает ScorePredictor.
- UI НЕ использует Winner Synthesis.
- UI НЕ использует Pair Rating в математике.
- UI НЕ использует ETC / Learning.
- database.py НЕ изменяется.
- Missing != 0.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

from app.parsers.soccer365_parser import Soccer365Parser
from app.core.faj_brain import FAJBrain
from app.faj_club_ratings import (
    get_all_tournaments,
    get_all_teams,
    get_team_rating,
)


# ============================================================
# VERSION
# ============================================================

PREDICTOR_VERSION = "FAJ-PREDICTOR-1.4"
HISTORY_SIZE = 6
MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6


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
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    max-width: 1150px;
    padding-top: 1rem;
    padding-left: .75rem;
    padding-right: .75rem;
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

.faj-header {
    padding: 15px 17px;
    margin-bottom: 12px;
    border-radius: 18px;
    border: 1px solid rgba(128,128,128,.18);
    background: rgba(128,128,128,.06);
}

.faj-title {
    font-size: 27px;
    font-weight: 850;
    line-height: 1.1;
}

.faj-subtitle {
    font-size: 12px;
    opacity: .60;
    margin-top: 5px;
}

.section-title {
    font-size: 16px;
    font-weight: 800;
    margin-top: 15px;
    margin-bottom: 8px;
}

.team-card {
    border-radius: 18px;
    padding: 14px;
    border: 1px solid rgba(128,128,128,.18);
    background: rgba(128,128,128,.045);
    margin-bottom: 8px;
}

.team-name {
    font-size: 18px;
    font-weight: 800;
}

.team-meta {
    font-size: 11px;
    opacity: .55;
    margin-top: 3px;
}

.result-card {
    border-radius: 20px;
    padding: 15px;
    border: 1px solid rgba(128,128,128,.20);
    background: rgba(128,128,128,.055);
    margin: 7px 0;
}

.result-main {
    font-size: 31px;
    font-weight: 850;
    text-align: center;
}

.result-caption {
    text-align: center;
    font-size: 11px;
    opacity: .55;
    margin-top: 3px;
}

.metric {
    border-radius: 14px;
    padding: 10px 8px;
    border: 1px solid rgba(128,128,128,.16);
    background: rgba(128,128,128,.035);
    text-align: center;
    margin-bottom: 7px;
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

.history-card {
    border-radius: 14px;
    padding: 10px 12px;
    margin-bottom: 7px;
    border: 1px solid rgba(128,128,128,.15);
    background: rgba(128,128,128,.035);
}

.history-title {
    font-weight: 800;
    font-size: 13px;
}

.history-meta {
    font-size: 10px;
    opacity: .55;
    margin-top: 3px;
}

.history-score {
    font-size: 18px;
    font-weight: 850;
}

.conclusion {
    border-radius: 18px;
    padding: 14px;
    border: 1px solid rgba(128,128,128,.18);
    background: rgba(128,128,128,.06);
    font-size: 14px;
    line-height: 1.45;
}

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

.link-box {
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid rgba(128,128,128,.15);
    background: rgba(128,128,128,.03);
    margin-bottom: 5px;
}

@media (max-width: 700px) {

    .block-container {
        padding-left: .45rem;
        padding-right: .45rem;
        padding-top: .4rem;
    }

    .faj-title {
        font-size: 22px;
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
        result = float(value)

        if math.isfinite(result):
            return result

    except (TypeError, ValueError):
        pass

    return None


def safe_int(value: Any) -> Optional[int]:
    number = safe_float(value)

    if number is None:
        return None

    return int(round(number))


def probability(value: Any) -> Optional[float]:
    number = safe_float(value)

    if number is None:
        return None

    number = max(0.0, min(1.0, number))

    return round(number * 100.0, 1)


def display_probability(value: Any) -> str:
    result = probability(value)

    if result is None:
        return "—"

    return f"{result:.1f}%"


def display_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"

    number = safe_float(value)

    if number is None:
        return str(value)

    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number))}{suffix}"

    return f"{number:.2f}{suffix}"


def first_not_none(*values: Any) -> Any:
    for item in values:
        if item is not None:
            return item

    return None


def pretty_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        return str(value)


def value(obj: Any, *names: str) -> Any:
    if obj is None:
        return None

    for name in names:

        if isinstance(obj, dict) and name in obj:
            return obj[name]

        try:
            if name in obj.keys():
                return obj[name]
        except (AttributeError, TypeError):
            pass

        try:
            return getattr(obj, name)
        except AttributeError:
            pass

    return None


def nested(obj: Any, *names: str) -> Any:
    current = obj

    for name in names:
        current = value(current, name)

        if current is None:
            return None

    return current


# ============================================================
# TEAM / TOURNAMENT HELPERS
# ============================================================

def safe_tournaments() -> List[str]:
    try:
        result = get_all_tournaments()

        if not isinstance(result, list):
            result = list(result or [])

        return [
            str(item)
            for item in result
            if str(item).strip()
        ]

    except Exception:
        return []


def safe_teams(tournament: str) -> List[str]:
    if not tournament:
        return []

    try:
        result = get_all_teams(tournament)

        if not isinstance(result, list):
            result = list(result or [])

        return [
            str(item)
            for item in result
            if str(item).strip()
        ]

    except Exception:
        return []


# ============================================================
# PARSER
# ============================================================

def parse_match(
    parser: Soccer365Parser,
    url: str,
) -> Dict[str, Any]:

    url = (url or "").strip()

    if not url:
        raise ValueError("Пустой URL.")

    result = parser.parse(url)

    if not isinstance(result, dict):
        raise ValueError(
            "Парсер вернул не словарь."
        )

    if result.get("error"):
        raise ValueError(
            str(result["error"])
        )

    stats = result.get("stats")

    if not isinstance(stats, dict):
        stats = {}

    result["stats"] = stats

    return result


# ============================================================
# BUILD TEAM RECORD
# ============================================================

def build_team_record(
    parsed: Dict[str, Any],
    team_name: str,
) -> Optional[Dict[str, Any]]:

    home_team = parsed.get("home_team")
    away_team = parsed.get("away_team")

    if not home_team or not away_team:
        return None

    team_name_low = (
        team_name.strip().lower()
    )

    home_low = (
        str(home_team).strip().lower()
    )

    away_low = (
        str(away_team).strip().lower()
    )

    score = parsed.get("score")

    goals_home = None
    goals_away = None

    if score:
        parts = re.split(
            r"[:\-]",
            str(score),
        )

        if len(parts) >= 2:
            goals_home = safe_int(parts[0])
            goals_away = safe_int(parts[1])

    if team_name_low == home_low:

        is_home = True
        team = home_team
        opponent = away_team

        goals_for = goals_home
        goals_against = goals_away

        venue = "home"

    elif team_name_low == away_low:

        is_home = False
        team = away_team
        opponent = home_team

        goals_for = goals_away
        goals_against = goals_home

        venue = "away"

    else:
        return None

    stats = parsed.get("stats") or {}

    def stat(name: str) -> Any:
        key = (
            f"home_{name}"
            if is_home
            else f"away_{name}"
        )

        return stats.get(key)

    def opponent_stat(name: str) -> Any:
        key = (
            f"away_{name}"
            if is_home
            else f"home_{name}"
        )

        return stats.get(key)

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

    xg = safe_float(
        stat("xg")
    )

    xga = safe_float(
        opponent_stat("xg")
    )

    corners = safe_int(
        stat("corners")
    )

    opponent_corners = safe_int(
        opponent_stat("corners")
    )

    yellow_cards = safe_int(
        stat("yellow_cards")
    )

    opponent_yellow_cards = safe_int(
        opponent_stat("yellow_cards")
    )

    extra = {
        "opponent_xg": xga,

        "shots": safe_int(
            stat("shots")
        ),

        "opponent_shots": safe_int(
            opponent_stat("shots")
        ),

        "shots_on_target": safe_int(
            stat("shots_on_target")
        ),

        "opponent_shots_on_target": safe_int(
            opponent_stat("shots_on_target")
        ),

        "blocked_shots": safe_int(
            stat("blocked_shots")
        ),

        "opponent_blocked_shots": safe_int(
            opponent_stat("blocked_shots")
        ),

        "big_chances": safe_int(
            stat("big_chances")
        ),

        "opponent_big_chances": safe_int(
            opponent_stat("big_chances")
        ),

        "possession": safe_float(
            stat("possession")
        ),

        "opponent_possession": safe_float(
            opponent_stat("possession")
        ),

        "passes": safe_int(
            stat("total_passes")
        ),

        "opponent_passes": safe_int(
            opponent_stat("total_passes")
        ),

        "pass_accuracy": safe_float(
            stat("pass_accuracy")
        ),

        "opponent_pass_accuracy": safe_float(
            opponent_stat("pass_accuracy")
        ),

        "fouls": safe_int(
            stat("fouls")
        ),

        "opponent_fouls": safe_int(
            opponent_stat("fouls")
        ),

        "offsides": safe_int(
            stat("offsides")
        ),

        "opponent_offsides": safe_int(
            opponent_stat("offsides")
        ),

        "red_cards": safe_int(
            stat("red_cards")
        ),

        "opponent_red_cards": safe_int(
            opponent_stat("red_cards")
        ),

        "crosses": safe_int(
            stat("crosses")
        ),

        "opponent_crosses": safe_int(
            opponent_stat("crosses")
        ),
    }

    return {
        "team": team,
        "team_name": team,
        "opponent": opponent,

        "home_team": home_team,
        "away_team": away_team,

        "is_home": is_home,
        "venue": venue,

        "goals_for": goals_for,
        "goals_against": goals_against,

        "result": result_code,
        "score": score,

        "xg": xg,
        "xga": xga,

        "corners": corners,
        "opponent_corners": opponent_corners,

        "yellow_cards": yellow_cards,
        "opponent_yellow_cards": opponent_yellow_cards,

        "match_date": parsed.get(
            "date",
            parsed.get("match_date"),
        ),

        "competition": parsed.get(
            "competition"
        ),

        "url": parsed.get("url"),

        "extra": extra,
    }


# ============================================================
# HISTORY COLLECTION
# ============================================================

def collect_history(
    parser: Soccer365Parser,
    team_name: str,
    urls: List[str],
) -> Tuple[
    List[Dict[str, Any]],
    List[str],
]:

    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    for index, raw_url in enumerate(
        urls,
        start=1,
    ):

        url = (raw_url or "").strip()

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

                home = parsed.get(
                    "home_team",
                    "?",
                )

                away = parsed.get(
                    "away_team",
                    "?",
                )

                raise ValueError(
                    f"Команда «{team_name}» "
                    f"не найдена в матче "
                    f"{home} — {away}."
                )

            record["team"] = team_name
            record["team_name"] = team_name
            record["source_url"] = url

            records.append(record)

        except Exception as exc:

            errors.append(
                f"{index}. {url} — {exc}"
            )

    records.sort(
        key=lambda item: str(
            item.get("match_date") or ""
        )
    )

    return (
        records[-MAX_ANALYSIS_MATCHES:],
        errors,
    )


# ============================================================
# BRAIN
# ============================================================

def calculate_prediction(
    home_team: str,
    away_team: str,
    home_records: List[Dict[str, Any]],
    away_records: List[Dict[str, Any]],
) -> Dict[str, Any]:

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
# SCORE HELPERS
# ============================================================

def normalize_top_scores(
    prediction: Dict[str, Any],
) -> List[Dict[str, Any]]:

    scores = prediction.get(
        "top_scores"
    )

    if isinstance(scores, list):
        return scores

    brain_result = prediction.get(
        "brain_result"
    )

    if isinstance(brain_result, dict):

        score_prediction = (
            brain_result.get(
                "score_prediction"
            )
        )

        if isinstance(
            score_prediction,
            dict,
        ):

            scores = score_prediction.get(
                "top_scores"
            )

            if isinstance(scores, list):
                return scores

    return []


def score_text(item: Any) -> str:

    if isinstance(item, str):
        return item

    if not isinstance(item, dict):
        return str(item)

    home = first_not_none(
        item.get("home"),
        item.get("home_goals"),
        item.get("home_score"),
    )

    away = first_not_none(
        item.get("away"),
        item.get("away_goals"),
        item.get("away_score"),
    )

    if (
        home is not None
        and away is not None
    ):
        return f"{home}:{away}"

    score = first_not_none(
        item.get("score"),
        item.get("predicted_score"),
    )

    if score is not None:
        return str(score)

    return "—"


def score_probability(
    item: Any,
) -> Optional[float]:

    if not isinstance(item, dict):
        return None

    return first_not_none(
        item.get("probability"),
        item.get("prob"),
        item.get("value"),
    )


# ============================================================
# GOAL MODEL DIAGNOSTICS
# ============================================================

def get_goal_model_data(
    prediction: Dict[str, Any],
) -> Dict[str, Any]:

    meta = prediction.get(
        "calculation_meta"
    )

    if isinstance(meta, dict):

        goal_model = meta.get(
            "goal_model"
        )

        if isinstance(
            goal_model,
            dict,
        ):
            return goal_model

    brain_result = prediction.get(
        "brain_result"
    )

    if isinstance(
        brain_result,
        dict,
    ):

        goal_model = brain_result.get(
            "goal_model"
        )

        if isinstance(
            goal_model,
            dict,
        ):
            return goal_model

    return {}


# ============================================================
# DATA QUALITY
# ============================================================

def data_quality_summary(
    prediction: Dict[str, Any],
) -> str:

    data_quality = prediction.get(
        "data_quality"
    )

    if not isinstance(
        data_quality,
        dict,
    ):
        return "—"

    if (
        data_quality.get(
            "missing_is_not_zero"
        )
        is True
    ):
        return "FACT / None preserved"

    return "—"


# ============================================================
# CLUB RATING
# ============================================================

def club_rating_value(
    team_name: str,
) -> Any:

    if not team_name.strip():
        return None

    try:
        return get_team_rating(
            team_name.strip()
        )
    except Exception:
        return None


# ============================================================
# HISTORY DISPLAY
# ============================================================

def render_history(
    team_name: str,
    records: List[Dict[str, Any]],
) -> None:

    if not records:
        st.info(
            f"История {team_name}: данных нет."
        )
        return

    for index, record in enumerate(
        records,
        start=1,
    ):

        opponent = record.get(
            "opponent"
        )

        score = record.get(
            "score"
        )

        result = record.get(
            "result"
        )

        date = record.get(
            "match_date"
        )

        venue = record.get(
            "venue"
        )

        venue_text = (
            "Дома"
            if venue == "home"
            else "В гостях"
            if venue == "away"
            else "—"
        )

        url = record.get(
            "source_url"
        ) or record.get(
            "url"
        )

        st.markdown(
            f"""
<div class="history-card">

<div class="history-title">
M{index} · {team_name} — {opponent or "—"}
</div>

<div class="history-score">
{score or "—"} &nbsp; {result or "—"}
</div>

<div class="history-meta">
{date or "Дата —"} · {venue_text}
· xG {display_value(record.get("xg"))}
· xGA {display_value(record.get("xga"))}
· угловые
{display_value(record.get("corners"))}:
{display_value(record.get("opponent_corners"))}
· ЖК
{display_value(record.get("yellow_cards"))}:
{display_value(record.get("opponent_yellow_cards"))}
</div>

</div>
""",
            unsafe_allow_html=True,
        )

        if url:
            st.markdown(
                f"[🔗 Открыть матч Soccer365]({url})"
            )


# ============================================================
# RESULT DISPLAY
# ============================================================

def render_result(
    home_team: str,
    away_team: str,
    prediction: Dict[str, Any],
) -> None:

    predicted_score = first_not_none(
        prediction.get(
            "predicted_score"
        ),
        prediction.get(
            "most_likely_score"
        ),
    )

    st.markdown(
        '<div class="section-title">FAJ Brain — прогноз</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="result-card">

<div class="result-main">
{predicted_score or "—"}
</div>

<div class="result-caption">
{home_team} — {away_team}
</div>

</div>
""",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">1X2</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
<div class="metric-value">
{display_probability(
    prediction.get("home_win_probability")
)}
</div>
<div class="metric-label">
Победа {home_team}
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
{display_probability(
    prediction.get("draw_probability")
)}
</div>
<div class="metric-label">
Ничья
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
{display_probability(
    prediction.get("away_win_probability")
)}
</div>
<div class="metric-label">
Победа {away_team}
</div>
</div>
""",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">xG</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            f"{home_team} xG",
            display_value(
                prediction.get(
                    "home_xg"
                )
            ),
        )

    with c2:
        st.metric(
            f"{away_team} xG",
            display_value(
                prediction.get(
                    "away_xg"
                )
            ),
        )

    # --------------------------------------------------------
    # TOP SCORES
    # --------------------------------------------------------

    top_scores = normalize_top_scores(
        prediction
    )

    if top_scores:

        st.markdown(
            '<div class="section-title">Наиболее вероятные счета</div>',
            unsafe_allow_html=True,
        )

        score_columns = st.columns(
            min(
                3,
                len(top_scores),
            )
        )

        for index, item in enumerate(
            top_scores[:3]
        ):

            score = score_text(item)
            prob = score_probability(item)

            with score_columns[index]:
                st.markdown(
                    f"""
<div class="score-card">

<div class="score">
{score}
</div>

<div class="score-label">
{display_probability(prob)}
</div>

</div>
""",
                    unsafe_allow_html=True,
                )

    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Голы</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "BTTS",
            display_probability(
                prediction.get(
                    "btts_probability"
                )
            ),
        )

    with c2:
        st.metric(
            "Over 2.5",
            display_probability(
                prediction.get(
                    "over25_probability"
                )
            ),
        )

    with c3:
        st.metric(
            "Over 3.5",
            display_probability(
                prediction.get(
                    "over35_probability"
                )
            ),
        )

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Угловые</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            home_team,
            display_value(
                prediction.get(
                    "home_corners_expected"
                )
            ),
        )

    with c2:
        st.metric(
            away_team,
            display_value(
                prediction.get(
                    "away_corners_expected"
                )
            ),
        )

    with c3:
        st.metric(
            "Всего",
            display_value(
                prediction.get(
                    "corners_expected"
                )
            ),
        )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Карточки</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            home_team,
            display_value(
                prediction.get(
                    "home_cards_expected"
                )
            ),
        )

    with c2:
        st.metric(
            away_team,
            display_value(
                prediction.get(
                    "away_cards_expected"
                )
            ),
        )

    with c3:
        st.metric(
            "Всего",
            display_value(
                prediction.get(
                    "cards_expected"
                )
            ),
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title">Confidence / Risk</div>',
        unsafe_allow_html=True,
    )

    confidence = safe_float(
        prediction.get(
            "confidence"
        )
    )

    confidence_text = (
        f"{confidence * 100:.1f}%"
        if confidence is not None
        else "—"
    )

    risk = prediction.get(
        "risk"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Confidence",
            confidence_text,
        )

    with c2:
        st.metric(
            "Risk",
            str(risk)
            if risk is not None
            else "—",
        )

    with c3:
        st.metric(
            "Data quality",
            data_quality_summary(
                prediction
            ),
        )

    # --------------------------------------------------------
    # CONCLUSION
    # --------------------------------------------------------

    conclusion = prediction.get(
        "conclusion"
    )

    if conclusion:

        st.markdown(
            '<div class="section-title">Заключение FAJ Brain</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
<div class="conclusion">
{conclusion}
</div>
""",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # GOAL MODEL DIAGNOSTICS
    # --------------------------------------------------------

    goal_model = get_goal_model_data(
        prediction
    )

    if goal_model:

        with st.expander(
            "🔬 GoalModel diagnostics",
            expanded=False,
        ):

            st.json(
                goal_model
            )

    # --------------------------------------------------------
    # BRAIN DIAGNOSTICS
    # --------------------------------------------------------

    diagnostics = prediction.get(
        "diagnostics"
    )

    with st.expander(
        "🧠 FAJ Brain diagnostics",
        expanded=False,
    ):

        if diagnostics is not None:
            st.json(
                diagnostics
            )
        else:
            st.write(
                "Диагностика отсутствует."
            )

    # --------------------------------------------------------
    # CALCULATION META
    # --------------------------------------------------------

    calculation_meta = prediction.get(
        "calculation_meta"
    )

    with st.expander(
        "⚙️ Calculation meta",
        expanded=False,
    ):

        if isinstance(
            calculation_meta,
            dict,
        ):
            st.json(
                calculation_meta
            )
        else:
            st.write(
                calculation_meta
            )


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

<div class="faj-title">
⚽ FAJ Predictor
</div>

<div class="faj-subtitle">
FAJ Brain · Form · Defence · xG · Probability · Score · Corners · Cards
</div>

</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# COMPETITION / TOURNAMENT
# ============================================================

tournaments = safe_tournaments()

if not tournaments:

    st.error(
        "FAJ Club Rating: список турниров недоступен."
    )

    st.stop()


st.markdown(
    '<div class="section-title">🏆 Лига / турнир</div>',
    unsafe_allow_html=True,
)

competition = st.selectbox(
    "Выберите лигу / турнир",
    tournaments,
    key="faj_tournament",
)

teams = safe_teams(
    competition
)

if not teams:

    st.warning(
        f"Для турнира «{competition}» "
        "список команд недоступен."
    )

    st.stop()


# ============================================================
# MATCH INPUT
# ============================================================

st.markdown(
    '<div class="section-title">⚽ Матч</div>',
    unsafe_allow_html=True,
)

left, right = st.columns(
    2,
    gap="small",
)

with left:

    home_team = st.selectbox(
        "Хозяева",
        [""] + teams,
        key="faj_home_team_select",
    )

with right:

    away_team = st.selectbox(
        "Гости",
        [""] + teams,
        key="faj_away_team_select",
    )


# ============================================================
# CLUB RATING
# ============================================================

rating_left, rating_right = st.columns(
    2,
    gap="small",
)

home_rating = club_rating_value(
    home_team
)

away_rating = club_rating_value(
    away_team
)

with rating_left:

    st.markdown(
        f"""
<div class="metric">
<div class="metric-value">
{home_rating if home_rating is not None else "—"}
</div>
<div class="metric-label">
FAJ Club Rating · {home_team or "Хозяева"}
</div>
</div>
""",
        unsafe_allow_html=True,
    )

with rating_right:

    st.markdown(
        f"""
<div class="metric">
<div class="metric-value">
{away_rating if away_rating is not None else "—"}
</div>
<div class="metric-label">
FAJ Club Rating · {away_team or "Гости"}
</div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# MATCH DATE
# ============================================================

match_date = st.date_input(
    "Дата матча",
    key="faj_match_date",
)


# ============================================================
# HOME HISTORY URLS
# ============================================================

st.markdown(
    '<div class="section-title">🏠 История хозяев — 6 матчей</div>',
    unsafe_allow_html=True,
)

home_urls: List[str] = []

for index in range(
    MAX_HISTORY_MATCHES
):

    value_key = (
        f"faj_home_url_{index + 1}"
    )

    url = st.text_input(
        f"HOME M{index + 1}",
        key=value_key,
        placeholder=(
            "https://soccer365.ru/games/..."
        ),
    )

    home_urls.append(
        url.strip()
    )


# ============================================================
# AWAY HISTORY URLS
# ============================================================

st.markdown(
    '<div class="section-title">✈️ История гостей — 6 матчей</div>',
    unsafe_allow_html=True,
)

away_urls: List[str] = []

for index in range(
    MAX_HISTORY_MATCHES
):

    value_key = (
        f"faj_away_url_{index + 1}"
    )

    url = st.text_input(
        f"AWAY M{index + 1}",
        key=value_key,
        placeholder=(
            "https://soccer365.ru/games/..."
        ),
    )

    away_urls.append(
        url.strip()
    )


# ============================================================
# URL SUMMARY
# ============================================================

home_count = sum(
    bool(url)
    for url in home_urls
)

away_count = sum(
    bool(url)
    for url in away_urls
)

c1, c2 = st.columns(2)

with c1:
    st.caption(
        f"HOME: {home_count}/6 ссылок"
    )

with c2:
    st.caption(
        f"AWAY: {away_count}/6 ссылок"
    )


# ============================================================
# CALCULATE BUTTON
# ============================================================

st.markdown(
    '<div class="section-title">🚀 Расчёт</div>',
    unsafe_allow_html=True,
)

calculate_clicked = st.button(
    "⚽ СОБРАТЬ 12 МАТЧЕЙ И РАССЧИТАТЬ FAJ BRAIN",
    type="primary",
    use_container_width=True,
    key="faj_calculate_button",
)


# ============================================================
# CALCULATION
# ============================================================

if calculate_clicked:

    if not home_team:
        st.error(
            "Выбери хозяев."
        )
        st.stop()

    if not away_team:
        st.error(
            "Выбери гостей."
        )
        st.stop()

    if home_team == away_team:
        st.error(
            "Хозяева и гости не могут быть одной командой."
        )
        st.stop()

    home_urls_clean = [
        url
        for url in home_urls
        if url
    ]

    away_urls_clean = [
        url
        for url in away_urls
        if url
    ]

    if not home_urls_clean:
        st.error(
            "Нет URL истории хозяев."
        )
        st.stop()

    if not away_urls_clean:
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
            home_team,
            home_urls_clean,
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
            away_team,
            away_urls_clean,
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

        for error in all_errors:
            st.warning(error)

        st.stop()

    if not away_records:

        progress.empty()

        st.error(
            "Не удалось собрать историю гостей."
        )

        for error in all_errors:
            st.warning(error)

        st.stop()

    # --------------------------------------------------------
    # FINAL BRAIN
    # --------------------------------------------------------

    try:

        prediction = calculate_prediction(
            home_team=home_team,
            away_team=away_team,
            home_records=home_records,
            away_records=away_records,
        )

    except Exception as exc:

        progress.empty()

        st.error(
            f"Ошибка FAJ Brain: {exc}"
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

    st.success(
        f"Готово: "
        f"{len(home_records)} HOME + "
        f"{len(away_records)} AWAY."
    )


# ============================================================
# RESULT
# ============================================================

prediction = (
    st.session_state.faj_prediction
)


if prediction is None:

    st.info(
        "Выбери турнир и команды, "
        "вставь ссылки 6 последних матчей "
        "для каждой команды и запусти расчёт."
    )

    st.stop()


# ============================================================
# COLLECTION ERRORS
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

            st.warning(
                error
            )


# ============================================================
# MAIN RESULT
# ============================================================

render_result(
    home_team,
    away_team,
    prediction,
)


# ============================================================
# USED HISTORY
# ============================================================

home_records = (
    st.session_state.faj_home_records
)

away_records = (
    st.session_state.faj_away_records
)

with st.expander(
    f"📚 История {home_team} — "
    f"{len(home_records)} матчей",
    expanded=False,
):

    render_history(
        home_team,
        home_records,
    )


with st.expander(
    f"📚 История {away_team} — "
    f"{len(away_records)} матчей",
    expanded=False,
):

    render_history(
        away_team,
        away_records,
    )


# ============================================================
# RAW PREDICTION
# ============================================================

with st.expander(
    "🧾 Полный результат FAJ Brain",
    expanded=False,
):

    st.json(
        prediction
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
    padding-top:18px;
">
    FAJ Predictor 1.4 · FAJ Brain ·
    No Winner Synthesis · No Pair Rating ·
    No local Poisson · Missing ≠ 0
</div>
""",
    unsafe_allow_html=True,
)
