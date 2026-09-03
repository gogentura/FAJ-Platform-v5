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
    FormContext
        ↓
    FormModel
        ↓
    FormWin
        ↓
    Defence
        ↓
    GoalModel
        ↓
    Poisson
        ↓
    1X2 / BTTS / TOTALS / SCORE
        ↓
    CornersModel
        ↓
    CardsModel
        ↓
    FINAL ANALYSIS

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

# ============================================================
# PARSER
# ============================================================

from app.parsers.soccer365_parser import Soccer365Parser

# ============================================================
# MATHEMATICAL ORGANS
# ============================================================

from app.core.form_model import FormModel
from app.core.form_win import FormWin
from app.core.defence import Defence
from app.core.goal_model import GoalModel
from app.core.corners_model import CornersModel
from app.core.cards_model import CardsModel


# ============================================================
# VERSION
# ============================================================

PREDICTOR_VERSION = "FAJ-PREDICTOR-1.0"

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

    if value is None:
        return None

    return round(
        max(0.0, min(1.0, float(value))) * 100.0,
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
# SCORE
# ============================================================

def poisson(
    goals: int,
    expected: float,
) -> float:

    if expected is None:
        return 0.0

    if expected < 0:
        return 0.0

    return (
        math.exp(-expected)
        * expected ** goals
        / math.factorial(goals)
    )


def score_distribution(
    home_xg: float,
    away_xg: float,
    max_goals: int = 7,
) -> List[Dict[str, Any]]:

    scores = []

    for home in range(max_goals + 1):

        hp = poisson(
            home,
            home_xg,
        )

        for away in range(max_goals + 1):

            ap = poisson(
                away,
                away_xg,
            )

            scores.append(
                {
                    "home": home,
                    "away": away,
                    "probability": hp * ap,
                }
            )

    scores.sort(
        key=lambda x: x["probability"],
        reverse=True,
    )

    return scores


def result_probabilities(
    home_xg: float,
    away_xg: float,
) -> Dict[str, float]:

    scores = score_distribution(
        home_xg,
        away_xg,
    )

    home = 0.0
    draw = 0.0
    away = 0.0

    for item in scores:

        p = item["probability"]

        if item["home"] > item["away"]:
            home += p

        elif item["home"] == item["away"]:
            draw += p

        else:
            away += p

    total = home + draw + away

    if total <= 0:
        return {
            "home": 1 / 3,
            "draw": 1 / 3,
            "away": 1 / 3,
        }

    return {
        "home": home / total,
        "draw": draw / total,
        "away": away / total,
    }


def total_probabilities(
    home_xg: float,
    away_xg: float,
) -> Dict[str, float]:

    scores = score_distribution(
        home_xg,
        away_xg,
    )

    btts = 0.0
    over25 = 0.0
    over35 = 0.0

    for item in scores:

        p = item["probability"]

        total = (
            item["home"]
            + item["away"]
        )

        if (
            item["home"] >= 1
            and item["away"] >= 1
        ):
            btts += p

        if total >= 3:
            over25 += p

        if total >= 4:
            over35 += p

    return {
        "btts": btts,
        "over25": over25,
        "over35": over35,
    }


def over_probability(
    expected: Optional[float],
    line: float,
) -> Optional[float]:

    if expected is None:
        return None

    under = 0.0

    for goals in range(0, 20):

        if goals <= math.floor(line):

            under += poisson(
                goals,
                expected,
            )

    return max(
        0.0,
        min(
            1.0,
            1.0 - under,
        ),
    )


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
# BUILD FORM CONTEXT
# ============================================================

def build_form_context(
    team_name: str,
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Canonical adapter from collected factual matches
    to FormModel / FormWin / Defence.

    История:
        oldest → newest

    Последний матч находится последним.
    """

    records = list(records)[-HISTORY_SIZE:]

    context: Dict[str, Any] = {

        "team":
            team_name,

        "team_name":
            team_name,

        "matches_count":
            len(records),

        "goals_for_history": [],
        "goals_against_history": [],

        "recent_xg": [],
        "recent_xga": [],

        "team_xg_history": [],
        "opponent_xg_history": [],

        "shots_history": [],
        "shots_conceded_history": [],

        "shots_on_target_history": [],
        "sot_conceded_history": [],

        "blocked_shots_history": [],
        "blocked_shots_conceded_history": [],

        "big_chances_history": [],
        "big_chances_against_history": [],

        "possession_history": [],
        "opponent_possession_history": [],

        "corners_for_history": [],
        "corners_against_history": [],

        "passes_history": [],
        "opponent_passes_history": [],

        "pass_accuracy_history": [],
        "opponent_pass_accuracy_history": [],

        "fouls_history": [],
        "offsides_history": [],

        "team_cards_history": [],
        "opponent_cards_history": [],

        "venue_history": [],
        "results_history": [],
    }

    for record in records:

        extra = record.get(
            "extra",
            {},
        )

        context[
            "goals_for_history"
        ].append(
            record.get(
                "goals_for"
            )
        )

        context[
            "goals_against_history"
        ].append(
            record.get(
                "goals_against"
            )
        )

        context[
            "recent_xg"
        ].append(
            record.get("xg")
        )

        context[
            "recent_xga"
        ].append(
            record.get("xga")
        )

        context[
            "team_xg_history"
        ].append(
            record.get("xg")
        )

        context[
            "opponent_xg_history"
        ].append(
            record.get("xga")
        )

        context[
            "shots_history"
        ].append(
            extra.get("shots")
        )

        context[
            "shots_conceded_history"
        ].append(
            extra.get(
                "opponent_shots"
            )
        )

        context[
            "shots_on_target_history"
        ].append(
            extra.get(
                "shots_on_target"
            )
        )

        context[
            "sot_conceded_history"
        ].append(
            extra.get(
                "opponent_shots_on_target"
            )
        )

        context[
            "blocked_shots_history"
        ].append(
            extra.get(
                "blocked_shots"
            )
        )

        context[
            "blocked_shots_conceded_history"
        ].append(
            extra.get(
                "opponent_blocked_shots"
            )
        )

        context[
            "big_chances_history"
        ].append(
            extra.get(
                "big_chances"
            )
        )

        context[
            "big_chances_against_history"
        ].append(
            extra.get(
                "opponent_big_chances"
            )
        )

        context[
            "possession_history"
        ].append(
            extra.get(
                "possession"
            )
        )

        context[
            "opponent_possession_history"
        ].append(
            extra.get(
                "opponent_possession"
            )
        )

        context[
            "corners_for_history"
        ].append(
            extra.get(
                "corners"
            )
        )

        context[
            "corners_against_history"
        ].append(
            extra.get(
                "opponent_corners"
            )
        )

        context[
            "passes_history"
        ].append(
            extra.get(
                "passes"
            )
        )

        context[
            "opponent_passes_history"
        ].append(
            extra.get(
                "opponent_passes"
            )
        )

        context[
            "pass_accuracy_history"
        ].append(
            extra.get(
                "pass_accuracy"
            )
        )

        context[
            "opponent_pass_accuracy_history"
        ].append(
            extra.get(
                "opponent_pass_accuracy"
            )
        )

        context[
            "fouls_history"
        ].append(
            extra.get(
                "fouls"
            )
        )

        context[
            "offsides_history"
        ].append(
            extra.get(
                "offsides"
            )
        )

        context[
            "team_cards_history"
        ].append(
            extra.get(
                "yellow_cards"
            )
        )

        context[
            "opponent_cards_history"
        ].append(
            extra.get(
                "opponent_yellow_cards"
            )
        )

        context[
            "venue_history"
        ].append(
            record.get(
                "venue"
            )
        )

        context[
            "results_history"
        ].append(
            record.get(
                "result"
            )
        )

    # --------------------------------------------------------
    # Legacy-compatible aliases
    # --------------------------------------------------------

    context[
        "xg_history"
    ] = list(
        context["recent_xg"]
    )

    context[
        "xga_history"
    ] = list(
        context["recent_xga"]
    )

    context[
        "goals_for"
    ] = list(
        context[
            "goals_for_history"
        ]
    )

    context[
        "goals_against"
    ] = list(
        context[
            "goals_against_history"
        ]
    )

    return context


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

            records.append(
                record
            )

        except Exception as exc:

            errors.append(
                f"Матч {index}: {exc}"
            )

    # --------------------------------------------------------
    # Сортировка по дате.
    #
    # Старый → новый.
    # --------------------------------------------------------

    records.sort(
        key=lambda item: (
            item.get(
                "match_date"
            )
            or ""
        )
    )

    return (
        records[-HISTORY_SIZE:],
        errors,
    )


# ============================================================
# MATHEMATICAL ENGINE
# ============================================================

def calculate_prediction(
    home_team: str,
    away_team: str,
    home_records: List[Dict[str, Any]],
    away_records: List[Dict[str, Any]],
) -> Dict[str, Any]:

    home_context = build_form_context(
        home_team,
        home_records,
    )

    away_context = build_form_context(
        away_team,
        away_records,
    )

    # ========================================================
    # FORM MODEL
    # ========================================================

    form_model = FormModel()

    home_form = form_model.analyze(
        home_context,
        next_venue="home",
    )

    away_form = form_model.analyze(
        away_context,
        next_venue="away",
    )

    # ========================================================
    # FORM WIN
    # ========================================================

    form_win = FormWin()

    home_form_win = form_win.analyze(
        home_context,
        next_venue="home",
    )

    away_form_win = form_win.analyze(
        away_context,
        next_venue="away",
    )

    form_win_comparison = form_win.compare(
        home_context,
        away_context,
    )

    # ========================================================
    # DEFENCE
    # ========================================================

    defence = Defence()

    home_defence = defence.calculate(
        home_context,
        team_name=home_team,
    )

    away_defence = defence.calculate(
        away_context,
        team_name=away_team,
    )

    # ========================================================
    # GOAL MODEL
    # ========================================================

    goal_model = GoalModel()

    goal_result = goal_model.analyze(
        home_form,
        away_form,
        home_team=home_team,
        away_team=away_team,
        venue="HOME",
        home_form_win=home_form_win,
        away_form_win=away_form_win,
        home_defence=home_defence,
        away_defence=away_defence,
    )

    home_xg = safe_float(
        value(
            goal_result,
            "home_xg",
        )
    )

    away_xg = safe_float(
        value(
            goal_result,
            "away_xg",
        )
    )

    if home_xg is None:
        raise ValueError(
            "GoalModel не рассчитал home xG. "
            "Проверь наличие xG/xGA."
        )

    if away_xg is None:
        raise ValueError(
            "GoalModel не рассчитал away xG. "
            "Проверь наличие xG/xGA."
        )

    # ========================================================
    # 1X2
    # ========================================================

    probabilities = result_probabilities(
        home_xg,
        away_xg,
    )

    # ========================================================
    # TOTALS
    # ========================================================

    totals = total_probabilities(
        home_xg,
        away_xg,
    )

    # ========================================================
    # SCORE
    # ========================================================

    scores = score_distribution(
        home_xg,
        away_xg,
    )

    top_scores = scores[:3]

    # ========================================================
    # CORNERS
    # ========================================================

    corners_model = CornersModel()

    corners_result = (
        corners_model.synthesize_match(
            home_context,
            away_context,
        )
    )

    home_corners = safe_float(
        nested(
            corners_result,
            "home",
            "home_corners_expected",
        )
    )

    away_corners = safe_float(
        nested(
            corners_result,
            "away",
            "away_corners_expected",
        )
    )

    total_corners = safe_float(
        corners_result.get(
            "total_expected_corners"
        )
        if isinstance(
            corners_result,
            dict,
        )
        else None
    )

    # ========================================================
    # CARDS
    # ========================================================

    cards_model = CardsModel()

    cards_result = (
        cards_model.synthesize_match(
            home_context,
            away_context,
        )
    )

    home_cards = safe_float(
        nested(
            cards_result,
            "home",
            "home_cards_expected",
        )
    )

    away_cards = safe_float(
        nested(
            cards_result,
            "away",
            "away_cards_expected",
        )
    )

    total_cards = safe_float(
        cards_result.get(
            "total_expected_cards"
        )
        if isinstance(
            cards_result,
            dict,
        )
        else None
    )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    def history_quality(
        records: List[Dict[str, Any]],
    ) -> float:

        if not records:
            return 0.0

        fields = [

            "goals_for",
            "goals_against",
            "xg",
            "xga",

        ]

        available = 0
        total = (
            len(records)
            * len(fields)
        )

        for record in records:

            for field in fields:

                if record.get(
                    field
                ) is not None:

                    available += 1

        completeness = (
            available / total
            if total
            else 0.0
        )

        count_factor = min(
            len(records)
            / HISTORY_SIZE,
            1.0,
        )

        return round(
            (
                0.65 * count_factor
                + 0.35 * completeness
            )
            * 100.0,
            1,
        )

    home_quality = history_quality(
        home_records
    )

    away_quality = history_quality(
        away_records
    )

    data_quality = round(
        (
            home_quality
            + away_quality
        ) / 2.0,
        1,
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    ordered = sorted(
        probabilities.values(),
        reverse=True,
    )

    separation = (
        ordered[0]
        - ordered[1]
    )

    separation_score = min(
        100.0,
        max(
            0.0,
            separation / 0.45 * 100.0,
        ),
    )

    confidence = round(
        (
            0.55 * data_quality
            + 0.45 * separation_score
        ),
        1,
    )

    if data_quality < 35:
        risk = "Высокий"

    elif confidence < 45:
        risk = "Высокий"

    elif confidence < 65:
        risk = "Средний"

    else:
        risk = "Низкий"

    # ========================================================
    # ANALYSIS MODE
    # ========================================================

    sample = min(
        len(home_records),
        len(away_records),
    )

    if sample >= 6:
        analysis_mode = "Расширенный"

    elif sample >= 3:
        analysis_mode = "Базовый+"

    elif sample >= 2:
        analysis_mode = "Базовый"

    else:
        analysis_mode = "Экспресс"

    # ========================================================
    # FAVORITE
    # ========================================================

    if (
        probabilities["home"]
        >= probabilities["away"]
        and probabilities["home"]
        >= probabilities["draw"]
    ):

        favorite = home_team

    elif (
        probabilities["away"]
        >= probabilities["home"]
        and probabilities["away"]
        >= probabilities["draw"]
    ):

        favorite = away_team

    else:

        favorite = "Равновесие"

    # ========================================================
    # CONCLUSION
    # ========================================================

    factors = []

    if favorite == home_team:

        factors.append(
            f"Преимущество {home_team}."
        )

    elif favorite == away_team:

        factors.append(
            f"Преимущество {away_team}."
        )

    else:

        factors.append(
            "Явного фаворита нет."
        )

    if totals["btts"] >= 0.60:

        factors.append(
            "Повышенная вероятность BTTS."
        )

    elif totals["btts"] <= 0.40:

        factors.append(
            "BTTS выглядит менее вероятным."
        )

    if totals["over25"] >= 0.60:

        factors.append(
            "Сценарий 3+ голов имеет "
            "повышенную вероятность."
        )

    elif totals["over25"] <= 0.40:

        factors.append(
            "Модель склоняется к умеренной "
            "результативности."
        )

    conclusion = " ".join(
        factors
    )

    return {

        "version":
            PREDICTOR_VERSION,

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_matches":
            len(home_records),

        "away_matches":
            len(away_records),

        "home_xg":
            home_xg,

        "away_xg":
            away_xg,

        "home_win":
            probabilities["home"],

        "draw":
            probabilities["draw"],

        "away_win":
            probabilities["away"],

        "btts":
            totals["btts"],

        "over25":
            totals["over25"],

        "over35":
            totals["over35"],

        "scores":
            top_scores,

        "home_corners":
            home_corners,

        "away_corners":
            away_corners,

        "total_corners":
            total_corners,

        "over75_corners":
            over_probability(
                total_corners,
                7.5,
            ),

        "over85_corners":
            over_probability(
                total_corners,
                8.5,
            ),

        "over95_corners":
            over_probability(
                total_corners,
                9.5,
            ),

        "over105_corners":
            over_probability(
                total_corners,
                10.5,
            ),

        "home_cards":
            home_cards,

        "away_cards":
            away_cards,

        "total_cards":
            total_cards,

        "over25_cards":
            over_probability(
                total_cards,
                2.5,
            ),

        "over35_cards":
            over_probability(
                total_cards,
                3.5,
            ),

        "over45_cards":
            over_probability(
                total_cards,
                4.5,
            ),

        "confidence":
            confidence,

        "risk":
            risk,

        "analysis_mode":
            analysis_mode,

        "data_quality":
            data_quality,

        "favorite":
            favorite,

        "conclusion":
            conclusion,

        "factors":
            factors,

        "home_form":
            home_form,

        "away_form":
            away_form,

        "home_form_win":
            home_form_win,

        "away_form_win":
            away_form_win,

        "form_win_comparison":
            form_win_comparison,

        "home_defence":
            home_defence,

        "away_defence":
            away_defence,

        "goal_result":
            goal_result,

        "corners_result":
            corners_result,

        "cards_result":
            cards_result,

        "home_context":
            home_context,

        "away_context":
            away_context,
    }


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
        Independent analytical brain · Form · Defence · xG · Score · Corners · Cards
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
    # CALCULATION
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
            f"Ошибка математического расчёта: {exc}"
        )

        st.exception(exc)

        st.stop()

    progress.progress(
        100,
        text="FAJ расчёт завершён.",
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
# TOP MATCH CARD
# ============================================================

st.markdown(
    f"""
<div class="result-card">

    <div class="result-main">
        {prediction["home_team"]}
        &nbsp; — &nbsp;
        {prediction["away_team"]}
    </div>

    <div class="result-caption">
        {prediction["analysis_mode"]}
        · история {prediction["home_matches"]} / {prediction["away_matches"]}
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

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {probability(prediction["home_win"]):.1f}%
            </div>
            <div class="metric-label">
                {prediction["home_team"]}
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
                {probability(prediction["draw"]):.1f}%
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
                {probability(prediction["away_win"]):.1f}%
            </div>
            <div class="metric-label">
                {prediction["away_team"]}
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

with x1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {prediction["home_xg"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["home_team"]}
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
                {prediction["home_xg"] + prediction["away_xg"]:.2f}
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
                {prediction["away_xg"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["away_team"]}
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

for column, item, index in zip(
    score_cols,
    prediction["scores"],
    range(1, 4),
):

    with column:

        score = (
            f'{item["home"]}:{item["away"]}'
        )

        p = (
            item["probability"]
            * 100.0
        )

        st.markdown(
            f"""
            <div class="score-card">
                <div class="score">
                    {score}
                </div>
                <div class="score-label">
                    #{index} · {p:.1f}%
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

with g1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {probability(prediction["btts"]):.1f}%
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
                {probability(prediction["over25"]):.1f}%
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
                {probability(prediction["over35"]):.1f}%
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

c1, c2, c3 = st.columns(
    3,
    gap="small",
)

with c1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {prediction["home_corners"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["home_team"]}
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
                {prediction["total_corners"]:.2f}
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
                {prediction["away_corners"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["away_team"]}
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
    (
        "ТБ 7.5",
        prediction["over75_corners"],
    ),
    (
        "ТБ 8.5",
        prediction["over85_corners"],
    ),
    (
        "ТБ 9.5",
        prediction["over95_corners"],
    ),
    (
        "ТБ 10.5",
        prediction["over105_corners"],
    ),
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
                    {probability(p):.1f}%
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

card_cols = st.columns(
    3,
    gap="small",
)

with card_cols[0]:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {prediction["home_cards"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["home_team"]}
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
                {prediction["total_cards"]:.2f}
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
                {prediction["away_cards"]:.2f}
            </div>
            <div class="metric-label">
                {prediction["away_team"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


card_lines = [
    (
        "ТБ 2.5",
        prediction["over25_cards"],
    ),
    (
        "ТБ 3.5",
        prediction["over35_cards"],
    ),
    (
        "ТБ 4.5",
        prediction["over45_cards"],
    ),
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
                    {probability(p):.1f}%
                </div>
                <div class="metric-label">
                    {label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# CONFIDENCE
# ============================================================

st.markdown(
    '<div class="section-title">Надёжность анализа</div>',
    unsafe_allow_html=True,
)

q1, q2, q3 = st.columns(
    3,
    gap="small",
)

with q1:

    st.markdown(
        f"""
        <div class="metric">
            <div class="metric-value">
                {prediction["confidence"]:.1f}%
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
                {prediction["data_quality"]:.1f}%
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
                {prediction["risk"]}
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

st.markdown(
    f"""
<div class="conclusion">

<b>{prediction["favorite"]}</b><br><br>

{prediction["conclusion"]}

</div>
""",
    unsafe_allow_html=True,
)


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
        f"### {prediction['home_team']}"
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
        f"### {prediction['away_team']}"
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
# DIAGNOSTICS
# ============================================================

with st.expander(
    "Математическая диагностика",
    expanded=False,
):

    st.write(
        {
            "predictor_version":
                PREDICTOR_VERSION,

            "goal_model":
                value(
                    prediction["goal_result"],
                    "version",
                ),

            "home_xg":
                prediction["home_xg"],

            "away_xg":
                prediction["away_xg"],

            "home_base_xg":
                value(
                    prediction["goal_result"],
                    "home_base_xg",
                ),

            "away_base_xg":
                value(
                    prediction["goal_result"],
                    "away_base_xg",
                ),

            "home_attack_signal":
                nested(
                    prediction["goal_result"],
                    "diagnostics",
                    "home_attack_signal",
                ),

            "away_attack_signal":
                nested(
                    prediction["goal_result"],
                    "diagnostics",
                    "away_attack_signal",
                ),

            "home_defence_signal":
                nested(
                    prediction["goal_result"],
                    "diagnostics",
                    "home_defence_signal",
                ),

            "away_defence_signal":
                nested(
                    prediction["goal_result"],
                    "diagnostics",
                    "away_defence_signal",
                ),
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
    padding-top:15px;
">
    FAJ Predictor 1.0 · No ETC · No Learning · No bookmaker odds
</div>
""",
    unsafe_allow_html=True,
)
