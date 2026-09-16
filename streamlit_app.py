#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PREDICTOR — STREAMLIT APP
============================================================

SOCCER365
    ↓
FACT COLLECTION
    ↓
6 HOME + 6 AWAY
    ↓
FAJBrain.predict()
    ↓
FINAL BRAIN RESULT
    ↓
DISPLAY ONLY

ВАЖНО:

- UI не считает Poisson.
- UI не считает 1X2.
- UI не считает BTTS.
- UI не считает totals.
- UI не считает score distribution.
- UI не считает xG.
- UI не пересчитывает GoalModel.
- UI не пересчитывает ProbabilityModel.
- UI не пересчитывает ScorePredictor.
- UI не использует Winner Synthesis.
- UI не использует Pair Rating в математике.
- UI не использует ETC / Learning.
- UI не изменяет database.py.
- Missing != 0.
- Все фактические данные собираются через Soccer365Parser.
- Финальная математика принадлежит FAJBrain.

============================================================
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
from app.faj_club_ratings import get_team_rating


# ============================================================
# VERSION
# ============================================================

PREDICTOR_VERSION = "FAJ-PREDICTOR-1.3"
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
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    max-width: 1100px;
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
    padding: 14px 16px;
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

.section-title {
    font-size: 16px;
    font-weight: 800;
    margin-top: 14px;
    margin-bottom: 7px;
}

.conclusion {
    border-radius: 18px;
    padding: 14px;
    border: 1px solid rgba(128,128,128,.18);
    background: rgba(128,128,128,.06);
    font-size: 14px;
    line-height: 1.45;
}

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

@media (max-width: 700px) {

    .block-container {
        padding-left: .45rem;
        padding-right: .45rem;
        padding-top: .4rem;
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
        result = float(value)

        if math.isfinite(result):
            return result

    except (TypeError, ValueError):
        pass

    return None


def safe_int(value: Any) -> Optional[int]:
    value = safe_float(value)

    if value is None:
        return None

    return int(round(value))


def probability(value: Any) -> Optional[float]:
    value = safe_float(value)

    if value is None:
        return None

    value = max(0.0, min(1.0, value))

    return round(value * 100.0, 1)


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


def pretty_json(value_: Any) -> str:
    try:
        return json.dumps(
            value_,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    except Exception:
        return str(value_)


def display_value(value_: Any, suffix: str = "") -> str:
    if value_ is None:
        return "—"

    number = safe_float(value_)

    if number is not None:
        if abs(number - round(number)) < 1e-9:
            return f"{int(round(number))}{suffix}"

        return f"{number:.2f}{suffix}"

    return str(value_)


def display_probability(value_: Any) -> str:
    result = probability(value_)

    if result is None:
        return "—"

    return f"{result:.1f}%"


def first_not_none(*values_: Any) -> Any:
    for item in values_:
        if item is not None:
            return item

    return None


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
        raise ValueError("Парсер вернул не словарь.")

    if result.get("error"):
        raise ValueError(str(result["error"]))

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

    team_name_low = team_name.strip().lower()
    home_low = str(home_team).strip().lower()
    away_low = str(away_team).strip().lower()

    score = parsed.get("score")

    goals_home = None
    goals_away = None

    if score:
        parts = re.split(r"[:\-]", str(score))

        if len(parts) >= 2:
            goals_home = safe_int(parts[0])
            goals_away = safe_int(parts[1])

    if team_name_low == home_low:

        is_home = True
        team = home_team
        opponent = away_team

        goals_for = goals_home
        goals_against = goals_away

        side = "home"

    elif team_name_low == away_low:

        is_home = False
        team = away_team
        opponent = home_team

        goals_for = goals_away
        goals_against = goals_home

        side = "away"

    else:
        return None

    stats = parsed.get("stats") or {}

    def stat(name: str) -> Any:

        key = f"home_{name}" if is_home else f"away_{name}"

        return stats.get(key)

    def opponent_stat(name: str) -> Any:

        key = f"away_{name}" if is_home else f"home_{name}"

        return stats.get(key)

    result_code = None

    if goals_for is not None and goals_against is not None:

        if goals_for > goals_against:
            result_code = "W"

        elif goals_for < goals_against:
            result_code = "L"

        else:
            result_code = "D"

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    xg = safe_float(stat("xg"))
    xga = safe_float(opponent_stat("xg"))

    # --------------------------------------------------------
    # Core factual statistics
    # --------------------------------------------------------

    corners = safe_int(stat("corners"))
    opponent_corners = safe_int(opponent_stat("corners"))

    yellow_cards = safe_int(stat("yellow_cards"))
    opponent_yellow_cards = safe_int(
        opponent_stat("yellow_cards")
    )

    # --------------------------------------------------------
    # Additional facts
    # --------------------------------------------------------

    extra = {
        "opponent_xg": xga,

        "shots": safe_int(stat("shots")),
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
        "venue": side,

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

        "url": parsed.get(
            "url"
        ),

        "extra": extra,
    }


# ============================================================
# HISTORY COLLECTION
# ============================================================

def collect_history(
    parser: Soccer365Parser,
    team_name: str,
    urls: List[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:

    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    for index, url in enumerate(urls, start=1):

        url = (url or "").strip()

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
                    "?"
                )

                away = parsed.get(
                    "away_team",
                    "?"
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

    # --------------------------------------------------------
    # Chronological order
    # --------------------------------------------------------

    def sort_key(item: Dict[str, Any]) -> str:

        date = item.get("match_date")

        if date is None:
            return ""

        return str(date)

    records.sort(
        key=sort_key
    )

    # --------------------------------------------------------
    # Last N
    # --------------------------------------------------------

    records = records[-HISTORY_SIZE:]

    return records, errors


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
# SCORE NORMALIZATION
# ============================================================

def normalize_top_scores(
    prediction: Dict[str, Any],
) -> List[Dict[str, Any]]:

    top_scores = prediction.get(
        "top_scores"
    )

    if isinstance(top_scores, list):
        return top_scores

    brain_result = prediction.get(
        "brain_result"
    )

    if isinstance(brain_result, dict):

        score_prediction = brain_result.get(
            "score_prediction"
        )

        if isinstance(score_prediction, dict):

            nested_scores = score_prediction.get(
                "top_scores"
            )

            if isinstance(nested_scores, list):
                return nested_scores

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

    if home is not None and away is not None:
        return f"{home}:{away}"

    score = first_not_none(
        item.get("score"),
        item.get("predicted_score"),
    )

    if score is not None:
        return str(score)

    return "—"


def score_probability(item: Any) -> Optional[float]:

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

    if not isinstance(meta, dict):
        meta = {}

    goal_model = meta.get(
        "goal_model"
    )

    if isinstance(goal_model, dict):
        return goal_model

    brain_result = prediction.get(
        "brain_result"
    )

    if isinstance(brain_result, dict):

        goal_result = brain_result.get(
            "goal_model"
        )

        if isinstance(goal_result, dict):
            return goal_result

    return {}


# ============================================================
# DATA QUALITY DISPLAY
# ============================================================

def data_quality_summary(
    prediction: Dict[str, Any],
) -> str:

    data_quality = prediction.get(
        "data_quality"
    )

    if not isinstance(data_quality, dict):
        return "—"

    missing_flag = data_quality.get(
        "missing_is_not_zero"
    )

    if missing_flag is True:
        return "FACT / None preserved"

    return "—"


# ============================================================
# CLUB RATING DISPLAY
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


def render_team_rating(
    team_name: str,
) -> None:

    rating = club_rating_value(
        team_name
    )

    if rating is None:
        st.caption(
            "FAJ Club Rating: —"
        )
        return

    if isinstance(rating, dict):

        raw = first_not_none(
            rating.get("rating"),
            rating.get("faj_rating"),
            rating.get("value"),
            rating.get("start_rating"),
        )

        if raw is not None:
            st.caption(
                f"FAJ Club Rating: {raw}"
            )
            return

    st.caption(
        f"FAJ Club Rating: {rating}"
    )


# ============================================================
# HISTORY CARD
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

    st.markdown(
        f"### 📚 История — {team_name}"
    )

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

        xg = record.get(
            "xg"
        )

        xga = record.get(
            "xga"
        )

        corners = record.get(
            "corners"
        )

        opponent_corners = record.get(
            "opponent_corners"
        )

        yellow = record.get(
            "yellow_cards"
        )

        opponent_yellow = record.get(
            "opponent_yellow_cards"
        )

        venue_text = (
            "Дома"
            if venue == "home"
            else "В гостях"
            if venue == "away"
            else "—"
        )

        st.markdown(
            f"""
<div class="history-card">
    <div class="history-title">
        M{index} · {team_name} — {opponent or "—"}
    </div>

    <div class="history-score">
        {score or "—"}
        &nbsp;&nbsp;
        {result or "—"}
    </div>

    <div class="history-meta">
        {date or "Дата —"} · {venue_text}
        · xG {display_value(xg)}
        · xGA {display_value(xga)}
        · угловые {display_value(corners)}:{display_value(opponent_corners)}
        · ЖК {display_value(yellow)}:{display_value(opponent_yellow)}
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# MATCH RESULT CARD
# ============================================================

def render_match_header(
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

    home_xg = prediction.get(
        "home_xg"
    )

    away_xg = prediction.get(
        "away_xg"
    )

    st.markdown(
        """
<div class="result-card">
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
<div class="result-main">
    {predicted_score or "—"}
</div>

<div class="result-caption">
    {home_team} — {away_team}
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {display_value(home_xg)}
    </div>
    <div class="metric-label">
        {home_team} xG
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
        {display_value(away_xg)}
    </div>
    <div class="metric-label">
        {away_team} xG
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with c3:

        confidence = probability(
            prediction.get(
                "confidence"
            )
        )

        confidence_text = (
            f"{confidence:.1f}%"
            if confidence is not None
            else "—"
        )

        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {confidence_text}
    </div>
    <div class="metric-label">
        CONFIDENCE
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# 1X2
# ============================================================

def render_1x2(
    home_team: str,
    away_team: str,
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🎯 1X2</div>',
        unsafe_allow_html=True,
    )

    home = prediction.get(
        "home_win_probability"
    )

    draw = prediction.get(
        "draw_probability"
    )

    away = prediction.get(
        "away_win_probability"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {display_probability(home)}
    </div>
    <div class="metric-label">
        {home_team}
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
        {display_probability(draw)}
    </div>
    <div class="metric-label">
        НИЧЬЯ
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
        {display_probability(away)}
    </div>
    <div class="metric-label">
        {away_team}
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# SCORES
# ============================================================

def render_scores(
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">⚽ Вероятные счета</div>',
        unsafe_allow_html=True,
    )

    scores = normalize_top_scores(
        prediction
    )

    if not scores:

        fallback = [
            prediction.get(
                "predicted_score"
            ),
            prediction.get(
                "second_score"
            ),
            prediction.get(
                "third_score"
            ),
        ]

        scores = [
            {"score": score}
            for score in fallback
            if score
        ]

    if not scores:

        st.info(
            "ScorePredictor не вернул top_scores."
        )

        return

    scores = scores[:3]

    columns = st.columns(
        len(scores)
    )

    labels = [
        "1-й",
        "2-й",
        "3-й",
    ]

    for index, item in enumerate(scores):

        score = score_text(item)
        prob = score_probability(item)

        probability_text = (
            f"{probability(prob):.1f}%"
            if probability(prob) is not None
            else "—"
        )

        with columns[index]:

            st.markdown(
                f"""
<div class="score-card">
    <div class="score">
        {score}
    </div>
    <div class="score-label">
        {labels[index]} · {probability_text}
    </div>
</div>
""",
                unsafe_allow_html=True,
            )


# ============================================================
# GOALS
# ============================================================

def render_goals(
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🥅 Голы</div>',
        unsafe_allow_html=True,
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
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {display_probability(btts)}
    </div>
    <div class="metric-label">
        BTTS
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
        {display_probability(over25)}
    </div>
    <div class="metric-label">
        OVER 2.5
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
        {display_probability(over35)}
    </div>
    <div class="metric-label">
        OVER 3.5
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# CORNERS
# ============================================================

def render_corners(
    home_team: str,
    away_team: str,
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🚩 Угловые</div>',
        unsafe_allow_html=True,
    )

    home = prediction.get(
        "home_corners_expected"
    )

    away = prediction.get(
        "away_corners_expected"
    )

    total = prediction.get(
        "corners_expected"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {display_value(home)}
    </div>
    <div class="metric-label">
        {home_team}
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
        {display_value(away)}
    </div>
    <div class="metric-label">
        {away_team}
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
        {display_value(total)}
    </div>
    <div class="metric-label">
        TOTAL
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.caption(
        "Вероятности тоталов угловых не рассчитываются UI — "
        "показывается только результат CornersModel."
    )


# ============================================================
# CARDS
# ============================================================

def render_cards(
    home_team: str,
    away_team: str,
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🟨 Карточки</div>',
        unsafe_allow_html=True,
    )

    home = prediction.get(
        "home_cards_expected"
    )

    away = prediction.get(
        "away_cards_expected"
    )

    total = prediction.get(
        "cards_expected"
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {display_value(home)}
    </div>
    <div class="metric-label">
        {home_team}
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
        {display_value(away)}
    </div>
    <div class="metric-label">
        {away_team}
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
        {display_value(total)}
    </div>
    <div class="metric-label">
        TOTAL
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.caption(
        "Вероятности тоталов карточек не рассчитываются UI — "
        "показывается только результат CardsModel."
    )


# ============================================================
# CONFIDENCE / QUALITY
# ============================================================

def render_confidence(
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🧠 Confidence / Quality</div>',
        unsafe_allow_html=True,
    )

    confidence = probability(
        prediction.get(
            "confidence"
        )
    )

    risk = prediction.get(
        "risk"
    )

    quality = data_quality_summary(
        prediction
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {confidence:.1f}%
    </div>
    <div class="metric-label">
        CONFIDENCE
    </div>
</div>
""",
            unsafe_allow_html=True,
        ) if confidence is not None else st.markdown(
            """
<div class="metric">
    <div class="metric-value">—</div>
    <div class="metric-label">CONFIDENCE</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
<div class="metric">
    <div class="metric-value">
        {risk or "—"}
    </div>
    <div class="metric-label">
        RISK
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
        {quality}
    </div>
    <div class="metric-label">
        DATA QUALITY
    </div>
</div>
""",
            unsafe_allow_html=True,
        )


# ============================================================
# CONCLUSION
# ============================================================

def render_conclusion(
    prediction: Dict[str, Any],
) -> None:

    conclusion = prediction.get(
        "conclusion"
    )

    if not conclusion:
        return

    st.markdown(
        '<div class="section-title">📌 Аналитический вывод</div>',
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


# ============================================================
# DIAGNOSTICS
# ============================================================

def render_diagnostics(
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="section-title">🔬 Brain Diagnostics</div>',
        unsafe_allow_html=True,
    )

    meta = prediction.get(
        "calculation_meta"
    )

    if not isinstance(meta, dict):
        meta = {}

    goal_model = get_goal_model_data(
        prediction
    )

    diagnostics = goal_model.get(
        "diagnostics"
    )

    if not isinstance(diagnostics, dict):
        diagnostics = {}

    brain_result = prediction.get(
        "brain_result"
    )

    # --------------------------------------------------------
    # Main diagnostic facts
    # --------------------------------------------------------

    home_xg = prediction.get(
        "home_xg"
    )

    away_xg = prediction.get(
        "away_xg"
    )

    confidence = prediction.get(
        "confidence"
    )

    model_version = first_not_none(
        prediction.get(
            "model_version"
        ),
        goal_model.get(
            "model_version"
        ),
    )

    st.markdown(
        f"""
<div class="diag-block">
<div class="diag-header">FAJ BRAIN</div>
λ Home / xG: {display_value(home_xg)}
λ Away / xG: {display_value(away_xg)}
Confidence: {display_probability(confidence)}
Model: {model_version or "—"}
</div>
""",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Score Forecast
    # --------------------------------------------------------

    with st.expander(
        "📊 Score Forecast",
        expanded=False,
    ):

        scores = normalize_top_scores(
            prediction
        )

        if scores:
            st.json(scores)
        else:
            st.write(
                "ScorePredictor не вернул top_scores."
            )

    # --------------------------------------------------------
    # Goal Model
    # --------------------------------------------------------

    with st.expander(
        "⚽ GoalModel diagnostics",
        expanded=False,
    ):

        if diagnostics:

            fields = [
                "home_structural_attack",
                "away_structural_attack",
                "home_recent_attack",
                "away_recent_attack",
                "home_effective_attack",
                "away_effective_attack",
                "home_match_attack",
                "away_match_attack",
                "home_venue_attack_xg",
                "away_venue_attack_xg",
                "home_effective_xga",
                "away_effective_xga",
                "venue_split_used",
                "home_advantage_fallback",
                "home_lambda",
                "away_lambda",
            ]

            lines = []

            for field in fields:

                if field not in diagnostics:
                    continue

                lines.append(
                    f"{field}: "
                    f"{display_value(diagnostics[field])}"
                )

            st.markdown(
                f"""
<div class="diag-block">
{chr(10).join(lines)}
</div>
""",
                unsafe_allow_html=True,
            )

        st.json(
            goal_model
        )

    # --------------------------------------------------------
    # Full Brain Meta
    # --------------------------------------------------------

    with st.expander(
        "🧠 Full calculation_meta",
        expanded=False,
    ):

        st.json(
            meta
        )

    # --------------------------------------------------------
    # Full Brain Result
    # --------------------------------------------------------

    if isinstance(
        brain_result,
        dict,
    ):

        with st.expander(
            "🧠 Full brain_result",
            expanded=False,
        ):

            st.json(
                brain_result
            )

    # --------------------------------------------------------
    # Copy diagnostics
    # --------------------------------------------------------

    report = {
        "predictor_version":
            PREDICTOR_VERSION,

        "home_xg":
            home_xg,

        "away_xg":
            away_xg,

        "confidence":
            confidence,

        "model_version":
            model_version,

        "goal_model":
            goal_model,

        "calculation_meta":
            meta,
    }

    report_text = pretty_json(
        report
    )

    payload = (
        report_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )

    html = f"""
<div style="margin-top:10px;">
<button id="faj-copy-btn"
style="
width:100%;
padding:10px 14px;
border-radius:12px;
border:1px solid rgba(128,128,128,.35);
background:rgba(128,128,128,.10);
color:inherit;
font-size:14px;
font-weight:700;
cursor:pointer;
">
📋 СКОПИРОВАТЬ ДИАГНОСТИКУ
</button>

<div id="faj-copy-status"
style="
margin-top:6px;
font-size:11px;
opacity:.6;
text-align:center;
">
</div>
</div>

<script>
(function() {{
    const text = `{payload}`;

    const btn =
        document.getElementById("faj-copy-btn");

    const status =
        document.getElementById("faj-copy-status");

    if (!btn) return;

    btn.addEventListener(
        "click",
        async function() {{

            try {{

                if (
                    navigator.clipboard &&
                    window.isSecureContext
                ) {{

                    await navigator.clipboard.writeText(
                        text
                    );

                }} else {{

                    const ta =
                        document.createElement(
                            "textarea"
                        );

                    ta.value = text;

                    ta.style.position = "fixed";
                    ta.style.opacity = "0";

                    document.body.appendChild(
                        ta
                    );

                    ta.focus();
                    ta.select();

                    document.execCommand(
                        "copy"
                    );

                    document.body.removeChild(
                        ta
                    );
                }}

                status.innerText =
                    "✅ Скопировано";

                setTimeout(
                    function() {{
                        status.innerText = "";
                    }},
                    2000
                );

            }} catch (e) {{

                status.innerText =
                    "❌ Ошибка копирования";
            }}
        }}
    );
}})();
</script>
"""

    components.html(
        html,
        height=90,
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
        Independent analytical brain ·
        Form · Defence · xG · Score · Corners · Cards
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TEAMS
# ============================================================

st.markdown(
    "### 🏟️ Матч"
)

team_col1, team_col2 = st.columns(2)

with team_col1:

    home_team = st.text_input(
        "Хозяева",
        placeholder="Динамо Махачкала",
        key="faj_home_team",
    )

with team_col2:

    away_team = st.text_input(
        "Гости",
        placeholder="Краснодар",
        key="faj_away_team",
    )


# ============================================================
# CLUB RATINGS
# ============================================================

rating_col1, rating_col2 = st.columns(2)

with rating_col1:

    st.markdown(
        f"""
<div class="team-card">
    <div class="team-name">
        {home_team or "Хозяева"}
    </div>
    <div class="team-meta">
        FAJ Club Rating · display only
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if home_team.strip():
        render_team_rating(
            home_team
        )

with rating_col2:

    st.markdown(
        f"""
<div class="team-card">
    <div class="team-name">
        {away_team or "Гости"}
    </div>
    <div class="team-meta">
        FAJ Club Rating · display only
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if away_team.strip():
        render_team_rating(
            away_team
        )


# ============================================================
# HISTORY INPUT
# ============================================================

st.markdown(
    "### 📚 Последние 6 матчей"
)

st.caption(
    "Вставь ссылки Soccer365 по одной на строку. "
    "Порядок: от старого матча к новому."
)

home_urls_text = st.text_area(
    f"{home_team or 'Хозяева'} — 6 матчей Soccer365",
    height=180,
    placeholder=(
        "https://soccer365.ru/games/1234567/\n"
        "https://soccer365.ru/games/1234568/\n"
        "https://soccer365.ru/games/1234569/\n"
        "https://soccer365.ru/games/1234570/\n"
        "https://soccer365.ru/games/1234571/\n"
        "https://soccer365.ru/games/1234572/"
    ),
    key="faj_home_urls",
)

away_urls_text = st.text_area(
    f"{away_team or 'Гости'} — 6 матчей Soccer365",
    height=180,
    placeholder=(
        "https://soccer365.ru/games/2234567/\n"
        "https://soccer365.ru/games/2234568/\n"
        "https://soccer365.ru/games/2234569/\n"
        "https://soccer365.ru/games/2234570/\n"
        "https://soccer365.ru/games/2234571/\n"
        "https://soccer365.ru/games/2234572/"
    ),
    key="faj_away_urls",
)


# ============================================================
# URL PREPARATION
# ============================================================

home_urls = [
    line.strip()
    for line in home_urls_text.splitlines()
    if line.strip()
]

away_urls = [
    line.strip()
    for line in away_urls_text.splitlines()
    if line.strip()
]


# ============================================================
# CONTROL
# ============================================================

st.markdown("")

predict_clicked = st.button(
    "🚀 СОБРАТЬ FACTS И ЗАПУСТИТЬ FAJ BRAIN",
    type="primary",
    use_container_width=True,
)


# ============================================================
# RUN
# ============================================================

if predict_clicked:

    # --------------------------------------------------------
    # Validate teams
    # --------------------------------------------------------

    if not home_team.strip():
        st.error(
            "Укажи хозяев."
        )
        st.stop()

    if not away_team.strip():
        st.error(
            "Укажи гостей."
        )
        st.stop()

    # --------------------------------------------------------
    # Validate URLs
    # --------------------------------------------------------

    if not home_urls:
        st.error(
            "Добавь ссылки на последние матчи хозяев."
        )
        st.stop()

    if not away_urls:
        st.error(
            "Добавь ссылки на последние матчи гостей."
        )
        st.stop()

    # --------------------------------------------------------
    # Parser
    # --------------------------------------------------------

    parser = Soccer365Parser()

    progress = st.progress(
        0
    )

    status = st.empty()

    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    status.write(
        f"Собираю FACTS: {home_team}..."
    )

    home_records, home_errors = (
        collect_history(
            parser,
            home_team.strip(),
            home_urls,
        )
    )

    progress.progress(
        50
    )

    # --------------------------------------------------------
    # AWAY
    # --------------------------------------------------------

    status.write(
        f"Собираю FACTS: {away_team}..."
    )

    away_records, away_errors = (
        collect_history(
            parser,
            away_team.strip(),
            away_urls,
        )
    )

    progress.progress(
        80
    )

    # --------------------------------------------------------
    # Validate collection
    # --------------------------------------------------------

    all_errors = (
        home_errors
        + away_errors
    )

    if not home_records:
        progress.empty()
        status.empty()

        st.error(
            f"Не удалось собрать историю {home_team}."
        )

        if home_errors:
            st.code(
                "\n".join(home_errors)
            )

        st.stop()

    if not away_records:
        progress.empty()
        status.empty()

        st.error(
            f"Не удалось собрать историю {away_team}."
        )

        if away_errors:
            st.code(
                "\n".join(away_errors)
            )

        st.stop()

    # --------------------------------------------------------
    # Brain
    # --------------------------------------------------------

    status.write(
        "Передаю 6+6 FACTS в FAJ Brain..."
    )

    try:

        prediction = calculate_prediction(
            home_team=home_team.strip(),
            away_team=away_team.strip(),
            home_records=home_records,
            away_records=away_records,
        )

    except Exception as exc:

        progress.empty()
        status.empty()

        st.error(
            "Ошибка FAJ Brain."
        )

        st.exception(
            exc
        )

        st.stop()

    progress.progress(
        100
    )

    status.write(
        "FAJ Brain завершил расчёт."
    )

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


if prediction is not None:

    current_home = home_team.strip()
    current_away = away_team.strip()

    # --------------------------------------------------------
    # Collection errors
    # --------------------------------------------------------

    errors = (
        st.session_state.faj_collection_errors
    )

    if errors:

        with st.expander(
            "⚠️ Ошибки/пропуски при сборе FACTS",
            expanded=False,
        ):

            for error in errors:
                st.write(
                    f"• {error}"
                )

    # --------------------------------------------------------
    # Main
    # --------------------------------------------------------

    st.markdown("---")

    render_match_header(
        current_home,
        current_away,
        prediction,
    )

    render_1x2(
        current_home,
        current_away,
        prediction,
    )

    render_scores(
        prediction
    )

    render_goals(
        prediction
    )

    render_corners(
        current_home,
        current_away,
        prediction,
    )

    render_cards(
        current_home,
        current_away,
        prediction,
    )

    render_confidence(
        prediction
    )

    render_conclusion(
        prediction
    )

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    render_diagnostics(
        prediction
    )

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    with st.expander(
        "📚 Использованная история",
        expanded=False,
    ):

        home_records = (
            st.session_state.faj_home_records
        )

        away_records = (
            st.session_state.faj_away_records
        )

        render_history(
            current_home,
            home_records,
        )

        render_history(
            current_away,
            away_records,
        )

        st.markdown(
            "### Raw history JSON"
        )

        st.json(
            {
                "home": home_records,
                "away": away_records,
            }
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
    FAJ Predictor 1.3 ·
    FAJ Brain ·
    Soccer365 FACTS ·
    No Winner Synthesis ·
    No Pair Rating math ·
    No UI Poisson ·
    Missing ≠ 0
</div>
""",
    unsafe_allow_html=True,
)
