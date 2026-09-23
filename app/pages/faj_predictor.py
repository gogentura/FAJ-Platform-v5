#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ PREDICTOR — NEW BRAIN INTERFACE
============================================================

UI / FACT COLLECTION LAYER

Архитектура:

    Soccer365
        ↓
    FACT COLLECTION
        ↓
    historical records
        ↓
    FAJBrain v4.0
        ↓
    BrainPrediction
        ↓
    UI

ВАЖНО:

Predictor НЕ считает:

    - xG
    - lambda
    - Poisson
    - 1X2
    - BTTS
    - totals
    - score probabilities
    - Winner Override
    - confidence
    - risk

Вся математика принадлежит FAJ Brain и его State/Model.

Predictor только:

    1. получает FACTS;
    2. нормализует историю;
    3. получает FAJ Club Rating;
    4. передаёт history + rating в Brain;
    5. отображает BrainPrediction.

FAJ Brain v4.0:

    FACTS
      ↓
    FormContext
      ↓
    FormModel
      ↓
    GoalModel
      ↓
    ProbabilityModel
      ↓
    ScorePredictor
      ↓
    FINAL BRAIN

Rating:

    Club Rating
        ↓
    FAJBrain
        ↓
    Rating Reconciliation
        ↓
    λ Home / λ Away
        ↓
    ProbabilityModel
        ↓
    ScorePredictor

Параллельно:

    FormWin
    Defence
    FormControl
    FormAnomaly
    FormSpecial
    CornersModel
    CardsModel

============================================================
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

import streamlit as st


# ============================================================
# PROJECT IMPORTS
# ============================================================

from app.core.faj_brain import (
    FAJBrain,
    BRAIN_VERSION,
)

from app.parsers.soccer365_parser import Soccer365Parser


# ============================================================
# FAJ CLUB RATING
#
# Rating is now an INPUT to FAJBrain.
#
# Predictor does NOT calculate rating.
# Predictor only reads the existing FAJ Club Rating
# and passes it unchanged to FAJBrain.
# ============================================================

try:
    from app.faj_club_ratings import get_team_rating
except Exception:
    get_team_rating = None


# ============================================================
# CONSTANTS
# ============================================================

HISTORY_SIZE = 6


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="FAJ Predictor",
    page_icon="⚽",
    layout="wide",
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def _get(
    obj: Any,
    *names: str,
) -> Any:
    """
    Universal reader.

    Supports:

        dict
        Mapping
        sqlite3.Row-like
        dataclass
        normal object
    """

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

        except (
            AttributeError,
            TypeError,
        ):
            pass

        try:

            return getattr(
                obj,
                name,
            )

        except AttributeError:
            pass

    return None


def _as_dict(
    obj: Any,
) -> Dict[str, Any]:
    """
    Convert BrainPrediction / State / dataclass
    into a normal dictionary.
    """

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

    to_dict = getattr(
        obj,
        "to_dict",
        None,
    )

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


def _serialize(
    obj: Any,
) -> Any:
    """
    Recursive serialization for diagnostics.
    """

    if obj is None:
        return None

    if isinstance(obj, Mapping):

        return {
            key: _serialize(value)
            for key, value in obj.items()
        }

    if isinstance(obj, (list, tuple)):

        return [
            _serialize(value)
            for value in obj
        ]

    if is_dataclass(obj):

        try:
            return _serialize(
                asdict(obj)
            )

        except Exception:
            pass

    to_dict = getattr(
        obj,
        "to_dict",
        None,
    )

    if callable(to_dict):

        try:
            return _serialize(
                to_dict()
            )

        except Exception:
            pass

    return obj


def safe_float(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def safe_int(
    value: Any,
) -> Optional[int]:

    if value is None:
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def probability(
    value: Any,
) -> Optional[float]:
    """
    Convert an already calculated probability
    to percentage for UI.

    Does NOT calculate probability.
    """

    number = safe_float(value)

    if number is None:
        return None

    if number <= 1.0:
        return number * 100.0

    if number <= 100.0:
        return number

    return None


def fmt_probability(
    value: Any,
) -> str:

    p = probability(value)

    if p is None:
        return "—"

    return f"{p:.1f}%"


def fmt_number(
    value: Any,
    digits: int = 2,
) -> str:

    number = safe_float(value)

    if number is None:
        return "—"

    return f"{number:.{digits}f}"


def fmt_int(
    value: Any,
) -> str:

    number = safe_int(value)

    if number is None:
        return "—"

    return str(number)


def value(
    obj: Any,
    *names: str,
) -> Any:

    return _get(
        obj,
        *names,
    )


def nested(
    obj: Any,
    *path: str,
) -> Any:

    current = obj

    for name in path:

        current = _get(
            current,
            name,
        )

        if current is None:
            return None

    return current


# ============================================================
# DATE HELPERS
# ============================================================

def _date_key(
    value: Any,
) -> str:
    """
    Stable chronological key.

    Missing dates go last.
    """

    if value is None:
        return "9999-99-99"

    text = str(value).strip()

    if not text:
        return "9999-99-99"

    return text


# ============================================================
# MATCH PARSER
# ============================================================

def parse_match(
    parser: Soccer365Parser,
    url: str,
) -> Dict[str, Any]:
    """
    Parse one Soccer365 match.

    Parser remains FACT source.

    Predictor does not calculate derived football metrics.
    """

    parsed = parser.parse(url)

    if parsed is None:
        raise ValueError(
            f"Parser returned None: {url}"
        )

    data = _as_dict(parsed)

    if not data:
        raise ValueError(
            f"Empty parsed match: {url}"
        )

    return data


# ============================================================
# TEAM RECORD
# ============================================================

def build_team_record(
    match: Mapping[str, Any],
    team_name: str,
) -> Dict[str, Any]:
    """
    Convert parsed Soccer365 match into the canonical
    team-centric historical record consumed by FormContext.

    IMPORTANT:

        missing -> None

    Never:

        missing -> 0
    """

    home_team = value(
        match,
        "home_team",
        "home",
    )

    away_team = value(
        match,
        "away_team",
        "away",
    )

    home_score = value(
        match,
        "home_score",
        "home_goals",
        "score_home",
    )

    away_score = value(
        match,
        "away_score",
        "away_goals",
        "score_away",
    )

    # --------------------------------------------------------
    # Determine venue
    # --------------------------------------------------------

    is_home = (
        str(home_team).strip()
        == str(team_name).strip()
    )

    opponent = (
        away_team
        if is_home
        else home_team
    )

    # --------------------------------------------------------
    # Goals
    # --------------------------------------------------------

    home_goals = safe_int(
        home_score
    )

    away_goals = safe_int(
        away_score
    )

    goals_for = (
        home_goals
        if is_home
        else away_goals
    )

    goals_against = (
        away_goals
        if is_home
        else home_goals
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = None

    if (
        goals_for is not None
        and goals_against is not None
    ):

        if goals_for > goals_against:
            result = "W"

        elif goals_for < goals_against:
            result = "L"

        else:
            result = "D"

    # --------------------------------------------------------
    # xG
    # --------------------------------------------------------

    home_xg = safe_float(
        value(
            match,
            "home_xg",
            "xg_home",
        )
    )

    away_xg = safe_float(
        value(
            match,
            "away_xg",
            "xg_away",
        )
    )

    xg = (
        home_xg
        if is_home
        else away_xg
    )

    xga = (
        away_xg
        if is_home
        else home_xg
    )

    # --------------------------------------------------------
    # Generic directional helper
    # --------------------------------------------------------

    def side_value(
        home_names: Sequence[str],
        away_names: Sequence[str],
    ) -> Optional[float]:

        home_value = safe_float(
            value(
                match,
                *home_names,
            )
        )

        away_value = safe_float(
            value(
                match,
                *away_names,
            )
        )

        return (
            home_value
            if is_home
            else away_value
        )

    def opponent_value(
        home_names: Sequence[str],
        away_names: Sequence[str],
    ) -> Optional[float]:

        home_value = safe_float(
            value(
                match,
                *home_names,
            )
        )

        away_value = safe_float(
            value(
                match,
                *away_names,
            )
        )

        return (
            away_value
            if is_home
            else home_value
        )

    # --------------------------------------------------------
    # Main statistics
    # --------------------------------------------------------

    shots = side_value(
        (
            "home_shots",
            "shots_home",
        ),
        (
            "away_shots",
            "shots_away",
        ),
    )

    opponent_shots = opponent_value(
        (
            "home_shots",
            "shots_home",
        ),
        (
            "away_shots",
            "shots_away",
        ),
    )

    shots_on_target = side_value(
        (
            "home_shots_on_target",
            "home_sot",
            "sot_home",
        ),
        (
            "away_shots_on_target",
            "away_sot",
            "sot_away",
        ),
    )

    opponent_shots_on_target = opponent_value(
        (
            "home_shots_on_target",
            "home_sot",
            "sot_home",
        ),
        (
            "away_shots_on_target",
            "away_sot",
            "sot_away",
        ),
    )

    blocked_shots = side_value(
        (
            "home_blocked_shots",
            "blocked_home",
        ),
        (
            "away_blocked_shots",
            "blocked_away",
        ),
    )

    opponent_blocked_shots = opponent_value(
        (
            "home_blocked_shots",
            "blocked_home",
        ),
        (
            "away_blocked_shots",
            "blocked_away",
        ),
    )

    big_chances = side_value(
        (
            "home_big_chances",
            "big_chances_home",
        ),
        (
            "away_big_chances",
            "big_chances_away",
        ),
    )

    opponent_big_chances = opponent_value(
        (
            "home_big_chances",
            "big_chances_home",
        ),
        (
            "away_big_chances",
            "big_chances_away",
        ),
    )

    possession = side_value(
        (
            "home_possession",
            "possession_home",
        ),
        (
            "away_possession",
            "possession_away",
        ),
    )

    opponent_possession = opponent_value(
        (
            "home_possession",
            "possession_home",
        ),
        (
            "away_possession",
            "possession_away",
        ),
    )

    passes = side_value(
        (
            "home_passes",
            "passes_home",
        ),
        (
            "away_passes",
            "passes_away",
        ),
    )

    opponent_passes = opponent_value(
        (
            "home_passes",
            "passes_home",
        ),
        (
            "away_passes",
            "passes_away",
        ),
    )

    pass_accuracy = side_value(
        (
            "home_pass_accuracy",
            "pass_accuracy_home",
        ),
        (
            "away_pass_accuracy",
            "pass_accuracy_away",
        ),
    )

    opponent_pass_accuracy = opponent_value(
        (
            "home_pass_accuracy",
            "pass_accuracy_home",
        ),
        (
            "away_pass_accuracy",
            "pass_accuracy_away",
        ),
    )

    corners = side_value(
        (
            "home_corners",
            "corners_home",
        ),
        (
            "away_corners",
            "corners_away",
        ),
    )

    opponent_corners = opponent_value(
        (
            "home_corners",
            "corners_home",
        ),
        (
            "away_corners",
            "corners_away",
        ),
    )

    yellow_cards = side_value(
        (
            "home_yellow_cards",
            "yellow_cards_home",
            "home_yellows",
        ),
        (
            "away_yellow_cards",
            "yellow_cards_away",
            "away_yellows",
        ),
    )

    opponent_yellow_cards = opponent_value(
        (
            "home_yellow_cards",
            "yellow_cards_home",
            "home_yellows",
        ),
        (
            "away_yellow_cards",
            "yellow_cards_away",
            "away_yellows",
        ),
    )

    red_cards = side_value(
        (
            "home_red_cards",
            "red_cards_home",
        ),
        (
            "away_red_cards",
            "red_cards_away",
        ),
    )

    opponent_red_cards = opponent_value(
        (
            "home_red_cards",
            "red_cards_home",
        ),
        (
            "away_red_cards",
            "red_cards_away",
        ),
    )

    fouls = side_value(
        (
            "home_fouls",
            "fouls_home",
        ),
        (
            "away_fouls",
            "fouls_away",
        ),
    )

    opponent_fouls = opponent_value(
        (
            "home_fouls",
            "fouls_home",
        ),
        (
            "away_fouls",
            "fouls_away",
        ),
    )

    offsides = side_value(
        (
            "home_offsides",
            "offsides_home",
        ),
        (
            "away_offsides",
            "offsides_away",
        ),
    )

    opponent_offsides = opponent_value(
        (
            "home_offsides",
            "offsides_home",
        ),
        (
            "away_offsides",
            "offsides_away",
        ),
    )

    crosses = side_value(
        (
            "home_crosses",
            "crosses_home",
        ),
        (
            "away_crosses",
            "crosses_away",
        ),
    )

    opponent_crosses = opponent_value(
        (
            "home_crosses",
            "crosses_home",
        ),
        (
            "away_crosses",
            "crosses_away",
        ),
    )

    # --------------------------------------------------------
    # Date / competition
    # --------------------------------------------------------

    match_date = value(
        match,
        "match_date",
        "date",
        "datetime",
    )

    competition = value(
        match,
        "competition",
        "league",
        "tournament",
    )

    # --------------------------------------------------------
    # Canonical team record
    # --------------------------------------------------------

    record = {

        "team": team_name,
        "team_name": team_name,

        "opponent": opponent,

        "is_home": is_home,

        "venue": (
            "home"
            if is_home
            else "away"
        ),

        # ----------------------------------------------------
        # Result / goals
        # ----------------------------------------------------

        "goals_for": goals_for,
        "goals_against": goals_against,

        "result": result,

        # ----------------------------------------------------
        # xG
        # ----------------------------------------------------

        "xg": xg,
        "xga": xga,

        "opponent_xg": xga,

        # ----------------------------------------------------
        # Shots
        # ----------------------------------------------------

        "shots": shots,
        "opponent_shots": opponent_shots,

        "shots_on_target":
            shots_on_target,

        "opponent_shots_on_target":
            opponent_shots_on_target,

        "blocked_shots":
            blocked_shots,

        "opponent_blocked_shots":
            opponent_blocked_shots,

        "big_chances":
            big_chances,

        "opponent_big_chances":
            opponent_big_chances,

        # ----------------------------------------------------
        # Control
        # ----------------------------------------------------

        "possession":
            possession,

        "opponent_possession":
            opponent_possession,

        "passes":
            passes,

        "opponent_passes":
            opponent_passes,

        "pass_accuracy":
            pass_accuracy,

        "opponent_pass_accuracy":
            opponent_pass_accuracy,

        # ----------------------------------------------------
        # Corners
        # ----------------------------------------------------

        "corners":
            corners,

        "opponent_corners":
            opponent_corners,

        # ----------------------------------------------------
        # Cards
        # ----------------------------------------------------

        "yellow_cards":
            yellow_cards,

        "opponent_yellow_cards":
            opponent_yellow_cards,

        "red_cards":
            red_cards,

        "opponent_red_cards":
            opponent_red_cards,

        # ----------------------------------------------------
        # Other
        # ----------------------------------------------------

        "fouls":
            fouls,

        "opponent_fouls":
            opponent_fouls,

        "offsides":
            offsides,

        "opponent_offsides":
            opponent_offsides,

        "crosses":
            crosses,

        "opponent_crosses":
            opponent_crosses,

        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        "match_date":
            match_date,

        "competition":
            competition,

        # ----------------------------------------------------
        # Raw directional metadata
        # ----------------------------------------------------

        "extra": {
            "opponent_xg":
                xga,

            "shots":
                shots,

            "opponent_shots":
                opponent_shots,

            "shots_on_target":
                shots_on_target,

            "opponent_shots_on_target":
                opponent_shots_on_target,

            "blocked_shots":
                blocked_shots,

            "opponent_blocked_shots":
                opponent_blocked_shots,

            "big_chances":
                big_chances,

            "opponent_big_chances":
                opponent_big_chances,

            "possession":
                possession,

            "opponent_possession":
                opponent_possession,

            "passes":
                passes,

            "opponent_passes":
                opponent_passes,

            "pass_accuracy":
                pass_accuracy,

            "opponent_pass_accuracy":
                opponent_pass_accuracy,

            "corners":
                corners,

            "opponent_corners":
                opponent_corners,

            "yellow_cards":
                yellow_cards,

            "opponent_yellow_cards":
                opponent_yellow_cards,

            "red_cards":
                red_cards,

            "opponent_red_cards":
                opponent_red_cards,

            "fouls":
                fouls,

            "opponent_fouls":
                opponent_fouls,

            "offsides":
                offsides,

            "opponent_offsides":
                opponent_offsides,

            "crosses":
                crosses,

            "opponent_crosses":
                opponent_crosses,
        },
    }

    return record


# ============================================================
# HISTORY COLLECTION
# ============================================================

def collect_history(
    parser: Soccer365Parser,
    team_name: str,
    urls: Sequence[str],
) -> List[Dict[str, Any]]:
    """
    Parse supplied Soccer365 URLs.

    Output:

        oldest -> newest

    Maximum:

        6 matches
    """

    records: List[Dict[str, Any]] = []

    for index, url in enumerate(urls, start=1):

        clean_url = str(url).strip()

        if not clean_url:
            continue

        try:

            match = parse_match(
                parser,
                clean_url,
            )

            record = build_team_record(
                match,
                team_name,
            )

            record["_source_url"] = clean_url

            records.append(
                record
            )

        except Exception as exc:

            st.warning(
                f"{team_name}: матч #{index} "
                f"не удалось разобрать: {exc}"
            )

    # --------------------------------------------------------
    # Canonical chronology
    # --------------------------------------------------------

    records.sort(
        key=lambda row: _date_key(
            row.get("match_date")
        )
    )

    # --------------------------------------------------------
    # Keep latest N after sorting.
    #
    # Result remains oldest -> newest.
    # --------------------------------------------------------

    if len(records) > HISTORY_SIZE:

        records = records[
            -HISTORY_SIZE:
        ]

    return records


# ============================================================
# RATING
# ============================================================

def get_display_rating(
    team_name: str,
) -> Optional[Any]:
    """
    Read the existing FAJ Club Rating.

    This function does NOT calculate or modify rating.

    Missing rating remains None.
    """

    if get_team_rating is None:
        return None

    try:

        return get_team_rating(
            team_name
        )

    except Exception:
        return None


# ============================================================
# BRAIN CALL
# ============================================================

def calculate_prediction(
    home_team: str,
    away_team: str,
    home_records: Sequence[Mapping[str, Any]],
    away_records: Sequence[Mapping[str, Any]],
    home_rating: Optional[float] = None,
    away_rating: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run FAJ Brain v4.0.

    Brain receives:

        home_history
        away_history
        home_rating
        away_rating

    Rating is NOT calculated here.

    Rating reconciliation belongs to FAJ Brain.

    PredictionManager is intentionally NOT used.
    """

    if not home_records:
        raise ValueError(
            f"Нет истории для {home_team}"
        )

    if not away_records:
        raise ValueError(
            f"Нет истории для {away_team}"
        )

    brain = FAJBrain()

    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_history=list(home_records),
        away_history=list(away_records),

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Existing Club Rating is now actually passed
        # into FAJ Brain.
        # ----------------------------------------------------

        home_rating=safe_float(
            home_rating
        ),

        away_rating=safe_float(
            away_rating
        ),
    )

    if result is None:
        raise TypeError(
            "FAJBrain.predict() вернул None."
        )

    result_dict = _as_dict(
        result
    )

    if not result_dict:
        raise TypeError(
            "FAJBrain.predict() "
            "вернул объект, который нельзя "
            "преобразовать в dict."
        )

    return result_dict


# ============================================================
# RESULT ACCESS
# ============================================================

def _goal_state(
    prediction: Mapping[str, Any],
) -> Dict[str, Any]:

    return _as_dict(
        prediction.get(
            "goal_state"
        )
    )


def _probability_state(
    prediction: Mapping[str, Any],
) -> Dict[str, Any]:

    return _as_dict(
        prediction.get(
            "probability_state"
        )
    )


def _score_state(
    prediction: Mapping[str, Any],
) -> Dict[str, Any]:

    return _as_dict(
        prediction.get(
            "score_state"
        )
    )


def _parallel_state(
    prediction: Mapping[str, Any],
    name: str,
) -> Any:

    return prediction.get(
        name
    )


# ============================================================
# SCORE HELPERS
# ============================================================

def _score_rows(
    prediction: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """
    Read ScorePredictor v1.1 output.

    Preferred source:

        prediction["top_scores"]

    Fallback:

        score_state["top_scores"]

    Probability field:

        raw_probability

    Compatibility:

        probability
    """

    rows = prediction.get(
        "top_scores"
    )

    if not isinstance(rows, list):

        score_state = _score_state(
            prediction
        )

        rows = score_state.get(
            "top_scores",
            [],
        )

    if not isinstance(rows, list):
        return []

    result = []

    for row in rows:

        if not isinstance(
            row,
            Mapping,
        ):
            continue

        score = _get(
            row,
            "score",
        )

        raw_probability = _get(
            row,
            "raw_probability",
            "probability",
            "score_probability",
        )

        winner_class = _get(
            row,
            "winner_class",
        )

        total_goals = _get(
            row,
            "total_goals",
        )

        btts = _get(
            row,
            "btts",
        )

        result.append(
            {
                "score":
                    score,

                "raw_probability":
                    raw_probability,

                "winner_class":
                    winner_class,

                "total_goals":
                    total_goals,

                "btts":
                    btts,
            }
        )

    return result


# ============================================================
# STATE QUALITY
# ============================================================

def _state_quality(
    state: Any,
) -> Any:

    data = _as_dict(
        state
    )

    return _get(
        data,
        "data_quality",
        "score_data_quality",
        "quality",
    )


# ============================================================
# OPTIONAL STATE RENDER
# ============================================================

def _render_state_summary(
    title: str,
    state: Any,
) -> None:

    if state is None:

        st.caption(
            f"{title}: нет данных"
        )

        return

    data = _as_dict(
        state
    )

    if not data:

        st.caption(
            f"{title}: нет данных"
        )

        return

    quality = _state_quality(
        state
    )

    if quality is not None:

        st.caption(
            f"{title} · data quality: "
            f"{fmt_number(quality, 2)}"
        )

    with st.expander(
        f"{title} — raw state",
        expanded=False,
    ):

        st.json(
            _serialize(data)
        )


# ============================================================
# PAGE HEADER
# ============================================================

st.title(
    "⚽ FAJ Predictor"
)

st.caption(
    "FAJ Brain v4.0 · CONTRACT_V1 · "
    "FACTS → STATE → PROBABILITIES → SYNTHESIS"
)

st.info(
    "Predictor является интерфейсом сбора FACTS и "
    "отображения BrainPrediction. "
    "Математика выполняется внутри FAJ Brain."
)


# ============================================================
# INPUT
# ============================================================

col_home, col_away = st.columns(2)

with col_home:

    home_team = st.text_input(
        "Хозяева",
        value="",
        key="faj_home_team",
    )

with col_away:

    away_team = st.text_input(
        "Гости",
        value="",
        key="faj_away_team",
    )


# ============================================================
# URL INPUT
# ============================================================

st.subheader(
    "Последние матчи"
)

st.caption(
    f"Для каждой команды можно передать до "
    f"{HISTORY_SIZE} матчей Soccer365. "
    f"Порядок будет нормализован в oldest → newest."
)

home_urls_text = st.text_area(
    "Soccer365 — последние матчи хозяев",
    value="",
    height=180,
    key="faj_home_urls",
    placeholder=(
        "https://soccer365.ru/games/...\n"
        "https://soccer365.ru/games/...\n"
        "..."
    ),
)

away_urls_text = st.text_area(
    "Soccer365 — последние матчи гостей",
    value="",
    height=180,
    key="faj_away_urls",
    placeholder=(
        "https://soccer365.ru/games/...\n"
        "https://soccer365.ru/games/...\n"
        "..."
    ),
)


# ============================================================
# URL PARSER
# ============================================================

def _parse_urls(
    text: str,
) -> List[str]:

    if not text:
        return []

    lines = []

    for line in text.splitlines():

        clean = line.strip()

        if not clean:
            continue

        lines.append(
            clean
        )

    return lines


# ============================================================
# RUN
# ============================================================

run_prediction = st.button(
    "🚀 Рассчитать FAJ Prediction",
    type="primary",
    use_container_width=True,
)


if run_prediction:

    if not home_team.strip():
        st.error(
            "Укажите команду хозяев."
        )
        st.stop()

    if not away_team.strip():
        st.error(
            "Укажите команду гостей."
        )
        st.stop()

    home_urls = _parse_urls(
        home_urls_text
    )

    away_urls = _parse_urls(
        away_urls_text
    )

    if not home_urls:
        st.error(
            f"Нет URL истории для {home_team}."
        )
        st.stop()

    if not away_urls:
        st.error(
            f"Нет URL истории для {away_team}."
        )
        st.stop()

    parser = Soccer365Parser()

    # --------------------------------------------------------
    # FACT COLLECTION
    # --------------------------------------------------------

    with st.spinner(
        "Собираю FACTS Soccer365..."
    ):

        home_records = collect_history(
            parser=parser,
            team_name=home_team,
            urls=home_urls,
        )

        away_records = collect_history(
            parser=parser,
            team_name=away_team,
            urls=away_urls,
        )

    if not home_records:

        st.error(
            f"Не удалось получить историю "
            f"для {home_team}."
        )

        st.stop()

    if not away_records:

        st.error(
            f"Не удалось получить историю "
            f"для {away_team}."
        )

        st.stop()

    # --------------------------------------------------------
    # GET CLUB RATINGS
    #
    # IMPORTANT:
    # Read ratings BEFORE Brain call.
    # They are the existing FAJ Club Ratings.
    # --------------------------------------------------------

    home_rating = safe_float(
        get_display_rating(
            home_team
        )
    )

    away_rating = safe_float(
        get_display_rating(
            away_team
        )
    )

    # --------------------------------------------------------
    # SHOW FACT COLLECTION
    # --------------------------------------------------------

    st.subheader(
        "FACT Collection"
    )

    fact_col1, fact_col2 = st.columns(2)

    with fact_col1:

        st.metric(
            f"{home_team} — matches",
            len(home_records),
        )

    with fact_col2:

        st.metric(
            f"{away_team} — matches",
            len(away_records),
        )

    # --------------------------------------------------------
    # DEBUG HISTORY
    # --------------------------------------------------------

    with st.expander(
        "Проверить историю, переданную Brain",
        expanded=False,
    ):

        st.write(
            f"{home_team} — oldest → newest"
        )

        st.dataframe(
            home_records,
            use_container_width=True,
        )

        st.write(
            f"{away_team} — oldest → newest"
        )

        st.dataframe(
            away_records,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # BRAIN
    # --------------------------------------------------------

    try:

        with st.spinner(
            "FAJ Brain v4.0 считает прогноз..."
        ):

            prediction = calculate_prediction(
                home_team=home_team,
                away_team=away_team,
                home_records=home_records,
                away_records=away_records,

                # ------------------------------------------------
                # CLUB RATING → BRAIN
                # ------------------------------------------------

                home_rating=home_rating,
                away_rating=away_rating,
            )

    except Exception as exc:

        st.error(
            "FAJ Brain не смог завершить расчёт."
        )

        st.exception(
            exc
        )

        st.stop()

    # ========================================================
    # MAIN RESULT
    # ========================================================

    st.divider()

    st.subheader(
        "FAJ Brain Prediction"
    )

    # --------------------------------------------------------
    # CORE VALUES
    # --------------------------------------------------------

    home_lambda = prediction.get(
        "home_lambda"
    )

    away_lambda = prediction.get(
        "away_lambda"
    )

    total_lambda = prediction.get(
        "total_lambda"
    )

    home_win = prediction.get(
        "home_win_probability"
    )

    draw = prediction.get(
        "draw_probability"
    )

    away_win = prediction.get(
        "away_win_probability"
    )

    btts = prediction.get(
        "btts_probability"
    )

    over25 = prediction.get(
        "over_25_probability"
    )

    under25 = prediction.get(
        "under_25_probability"
    )

    over35 = prediction.get(
        "over_35_probability"
    )

    under35 = prediction.get(
        "under_35_probability"
    )

    predicted_score = prediction.get(
        "predicted_score"
    )

    second_score = prediction.get(
        "second_score"
    )

    third_score = prediction.get(
        "third_score"
    )

    score_probability = prediction.get(
        "predicted_score_probability"
    )

    # --------------------------------------------------------
    # XG / LAMBDA
    # --------------------------------------------------------

    st.markdown(
        "### Expected Goals / Lambda"
    )

    xg1, xg2, xg3 = st.columns(3)

    with xg1:

        st.metric(
            home_team,
            fmt_number(
                home_lambda
            ),
        )

    with xg2:

        st.metric(
            "Total λ",
            fmt_number(
                total_lambda
            ),
        )

    with xg3:

        st.metric(
            away_team,
            fmt_number(
                away_lambda
            ),
        )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    st.markdown(
        "### 1X2"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            f"{home_team} — HOME",
            fmt_probability(
                home_win
            ),
        )

    with c2:

        st.metric(
            "DRAW",
            fmt_probability(
                draw
            ),
        )

    with c3:

        st.metric(
            f"{away_team} — AWAY",
            fmt_probability(
                away_win
            ),
        )

    # --------------------------------------------------------
    # PRIMARY OUTCOME
    # --------------------------------------------------------

    primary_outcome = prediction.get(
        "primary_outcome"
    )

    if primary_outcome:

        labels = {
            "HOME": home_team,
            "DRAW": "Ничья",
            "AWAY": away_team,
        }

        st.info(
            f"Primary outcome: "
            f"**{labels.get(primary_outcome, primary_outcome)}**"
        )

    # --------------------------------------------------------
    # BTTS / TOTALS
    # --------------------------------------------------------

    st.markdown(
        "### Goals"
    )

    g1, g2, g3, g4, g5 = st.columns(5)

    with g1:

        st.metric(
            "BTTS",
            fmt_probability(
                btts
            ),
        )

    with g2:

        st.metric(
            "Over 2.5",
            fmt_probability(
                over25
            ),
        )

    with g3:

        st.metric(
            "Under 2.5",
            fmt_probability(
                under25
            ),
        )

    with g4:

        st.metric(
            "Over 3.5",
            fmt_probability(
                over35
            ),
        )

    with g5:

        st.metric(
            "Under 3.5",
            fmt_probability(
                under35
            ),
        )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    st.markdown(
        "### Exact Score"
    )

    s1, s2, s3 = st.columns(3)

    with s1:

        st.metric(
            "Primary",
            predicted_score or "—",
        )

        st.caption(
            f"P = {fmt_probability(score_probability)}"
        )

    with s2:

        st.metric(
            "Second",
            second_score or "—",
        )

    with s3:

        st.metric(
            "Third",
            third_score or "—",
        )

    # --------------------------------------------------------
    # TOP SCORES
    # --------------------------------------------------------

    score_rows = _score_rows(
        prediction
    )

    if score_rows:

        st.markdown(
            "#### Top Score Distribution"
        )

        table_rows = []

        for index, row in enumerate(
            score_rows,
            start=1,
        ):

            table_rows.append(
                {
                    "#":
                        index,

                    "Score":
                        row.get(
                            "score"
                        ) or "—",

                    "Raw probability":
                        fmt_probability(
                            row.get(
                                "raw_probability"
                            )
                        ),

                    "Winner":
                        row.get(
                            "winner_class"
                        ) or "—",

                    "Goals":
                        row.get(
                            "total_goals"
                        ),

                    "BTTS":
                        row.get(
                            "btts"
                        ),
                }
            )

        st.dataframe(
            table_rows,
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # CORNERS
    # ========================================================

    st.divider()

    st.subheader(
        "Corners State"
    )

    corners_state = prediction.get(
        "corners_state"
    )

    if corners_state is None:

        st.info(
            "CornersModel не вернул отдельный state."
        )

    else:

        corners_data = _as_dict(
            corners_state
        )

        home_corners = _get(
            corners_data,
            "home_corners",
            "expected_home_corners",
            "home_mean",
            "home_xg",
        )

        away_corners = _get(
            corners_data,
            "away_corners",
            "expected_away_corners",
            "away_mean",
            "away_xg",
        )

        total_corners = _get(
            corners_data,
            "total_corners",
            "expected_total_corners",
            "total_mean",
        )

        cc1, cc2, cc3 = st.columns(3)

        with cc1:

            st.metric(
                home_team,
                fmt_number(
                    home_corners
                ),
            )

        with cc2:

            st.metric(
                "Total",
                fmt_number(
                    total_corners
                ),
            )

        with cc3:

            st.metric(
                away_team,
                fmt_number(
                    away_corners
                ),
            )

        with st.expander(
            "Corners raw state",
            expanded=False,
        ):

            st.json(
                _serialize(
                    corners_data
                )
            )

    # ========================================================
    # CARDS
    # ========================================================

    st.subheader(
        "Cards State"
    )

    cards_state = prediction.get(
        "cards_state"
    )

    if cards_state is None:

        st.info(
            "CardsModel не вернул отдельный state."
        )

    else:

        cards_data = _as_dict(
            cards_state
        )

        home_yellow = _get(
            cards_data,
            "home_yellow",
            "home_yellows",
            "home_yellow_cards",
            "home_mean_yellow",
        )

        away_yellow = _get(
            cards_data,
            "away_yellow",
            "away_yellows",
            "away_yellow_cards",
            "away_mean_yellow",
        )

        total_yellow = _get(
            cards_data,
            "total_yellow",
            "total_yellows",
            "total_yellow_cards",
            "total_mean_yellow",
        )

        home_red = _get(
            cards_data,
            "home_red",
            "home_red_cards",
        )

        away_red = _get(
            cards_data,
            "away_red",
            "away_red_cards",
        )

        total_red = _get(
            cards_data,
            "total_red",
            "total_red_cards",
        )

        card_cols = st.columns(3)

        with card_cols[0]:

            st.metric(
                f"{home_team} — yellow",
                fmt_number(
                    home_yellow
                ),
            )

        with card_cols[1]:

            st.metric(
                "Yellow total",
                fmt_number(
                    total_yellow
                ),
            )

        with card_cols[2]:

            st.metric(
                f"{away_team} — yellow",
                fmt_number(
                    away_yellow
                ),
            )

        red_cols = st.columns(3)

        with red_cols[0]:

            st.metric(
                f"{home_team} — red",
                fmt_number(
                    home_red
                ),
            )

        with red_cols[1]:

            st.metric(
                "Red total",
                fmt_number(
                    total_red
                ),
            )

        with red_cols[2]:

            st.metric(
                f"{away_team} — red",
                fmt_number(
                    away_red
                ),
            )

        with st.expander(
            "Cards raw state",
            expanded=False,
        ):

            st.json(
                _serialize(
                    cards_data
                )
            )

    # ========================================================
    # DIAGNOSTIC STATES
    # ========================================================

    st.divider()

    st.subheader(
        "Analytical States"
    )

    st.caption(
        "Эти состояния являются диагностическими. "
        "Brain v4.0 не использует их для изменения "
        "lambda, Poisson, вероятностей или ranking score."
    )

    form_col1, form_col2 = st.columns(2)

    with form_col1:

        _render_state_summary(
            f"FormModel — {home_team}",
            prediction.get(
                "home_form"
            ),
        )

    with form_col2:

        _render_state_summary(
            f"FormModel — {away_team}",
            prediction.get(
                "away_form"
            ),
        )

    fw_col1, fw_col2 = st.columns(2)

    form_win = prediction.get(
        "form_win",
        {},
    )

    with fw_col1:

        _render_state_summary(
            f"FormWin — {home_team}",
            _get(
                form_win,
                "home",
            ),
        )

    with fw_col2:

        _render_state_summary(
            f"FormWin — {away_team}",
            _get(
                form_win,
                "away",
            ),
        )

    def_col1, def_col2 = st.columns(2)

    defence = prediction.get(
        "defence",
        {},
    )

    with def_col1:

        _render_state_summary(
            f"Defence — {home_team}",
            _get(
                defence,
                "home",
            ),
        )

    with def_col2:

        _render_state_summary(
            f"Defence — {away_team}",
            _get(
                defence,
                "away",
            ),
        )

    ctrl_col1, ctrl_col2 = st.columns(2)

    control = prediction.get(
        "control",
        {},
    )

    with ctrl_col1:

        _render_state_summary(
            f"Control — {home_team}",
            _get(
                control,
                "home",
            ),
        )

    with ctrl_col2:

        _render_state_summary(
            f"Control — {away_team}",
            _get(
                control,
                "away",
            ),
        )

    an_col1, an_col2 = st.columns(2)

    anomaly = prediction.get(
        "anomaly",
        {},
    )

    with an_col1:

        _render_state_summary(
            f"Anomaly — {home_team}",
            _get(
                anomaly,
                "home",
            ),
        )

    with an_col2:

        _render_state_summary(
            f"Anomaly — {away_team}",
            _get(
                anomaly,
                "away",
            ),
        )

    sf_col1, sf_col2 = st.columns(2)

    special_form = prediction.get(
        "special_form",
        {},
    )

    with sf_col1:

        _render_state_summary(
            f"SpecialForm — {home_team}",
            _get(
                special_form,
                "home",
            ),
        )

    with sf_col2:

        _render_state_summary(
            f"SpecialForm — {away_team}",
            _get(
                special_form,
                "away",
            ),
        )

    # ========================================================
    # GOAL / PROBABILITY / SCORE RAW STATES
    # ========================================================

    st.divider()

    st.subheader(
        "Core Mathematical States"
    )

    _render_state_summary(
        "GoalModel / Goal State",
        prediction.get(
            "goal_state"
        ),
    )

    _render_state_summary(
        "ProbabilityModel / Probability State",
        prediction.get(
            "probability_state"
        ),
    )

    _render_state_summary(
        "ScorePredictor / Score State",
        prediction.get(
            "score_state"
        ),
    )

    # ========================================================
    # CONFIDENCE / RISK
    # ========================================================

    st.divider()

    st.subheader(
        "Confidence / Risk"
    )

    confidence = prediction.get(
        "confidence"
    )

    risk = prediction.get(
        "risk"
    )

    cr1, cr2 = st.columns(2)

    with cr1:

        st.metric(
            "Confidence",
            fmt_probability(
                confidence
            )
            if confidence is not None
            else "—",
        )

    with cr2:

        st.metric(
            "Risk",
            fmt_probability(
                risk
            )
            if risk is not None
            else "—",
        )

    st.caption(
        "Brain v4.0 намеренно возвращает "
        "confidence=None и risk=None. "
        "Они не заменяются искусственными значениями."
    )

    # ========================================================
    # DIAGNOSTICS
    # ========================================================

    st.divider()

    st.subheader(
        "Brain Diagnostics"
    )

    diagnostics = prediction.get(
        "diagnostics",
        {},
    )

    if diagnostics:

        d1, d2, d3 = st.columns(3)

        with d1:

            st.metric(
                "Brain",
                str(
                    diagnostics.get(
                        "brain_version",
                        BRAIN_VERSION,
                    )
                ),
            )

        with d2:

            st.metric(
                "Core quality",
                fmt_number(
                    diagnostics.get(
                        "core_data_quality"
                    ),
                    2,
                ),
            )

        with d3:

            st.metric(
                "History",
                (
                    f"{diagnostics.get('home_history_size', '—')}"
                    f" / "
                    f"{diagnostics.get('away_history_size', '—')}"
                ),
            )

        with st.expander(
            "Full Brain diagnostics",
            expanded=False,
        ):

            st.json(
                _serialize(
                    diagnostics
                )
            )

    # ========================================================
    # ERRORS
    # ========================================================

    errors = prediction.get(
        "errors",
        [],
    )

    if errors:

        st.warning(
            "В диагностических органах "
            "обнаружены ошибки. "
            "Core prediction при этом не изменялась."
        )

        with st.expander(
            "Brain diagnostic errors",
            expanded=False,
        ):

            for error in errors:

                st.write(
                    f"• {error}"
                )

    # ========================================================
    # RATING
    # ========================================================

    st.divider()

    st.subheader(
        "FAJ Club Rating → Brain"
    )

    st.caption(
        "Club Rating является входным сигналом FAJ Brain. "
        "Brain самостоятельно выполняет Rating Reconciliation "
        "и передаёт скорректированные λ в ProbabilityModel "
        "и ScorePredictor."
    )

    rating_col1, rating_col2 = st.columns(2)

    with rating_col1:

        st.metric(
            home_team,
            (
                fmt_number(home_rating)
                if home_rating is not None
                else "—"
            ),
        )

    with rating_col2:

        st.metric(
            away_team,
            (
                fmt_number(away_rating)
                if away_rating is not None
                else "—"
            ),
        )

    # --------------------------------------------------------
    # RATING DEBUG CAPTION
    #
    # Fast diagnostic: показывает, доступна ли функция
    # get_team_rating и какие значения реально ушли в Brain.
    # --------------------------------------------------------

    st.caption(
        f"get_team_rating доступен: {get_team_rating is not None} · "
        f"{home_team} rating: {home_rating} · "
        f"{away_team} rating: {away_rating}"
    )

    # --------------------------------------------------------
    # RATING RECONCILIATION DIAGNOSTIC
    # --------------------------------------------------------

    rating_reconciliation = prediction.get(
        "rating_reconciliation"
    )

    lambda_reconciliation = prediction.get(
        "lambda_reconciliation"
    )

    if (
        rating_reconciliation is not None
        or lambda_reconciliation is not None
    ):

        st.markdown(
            "#### Rating Reconciliation"
        )

        rr_data = _as_dict(
            rating_reconciliation
        )

        lr_data = _as_dict(
            lambda_reconciliation
        )

        rr1, rr2, rr3 = st.columns(3)

        with rr1:

            st.metric(
                "Club Gap",
                fmt_number(
                    rr_data.get(
                        "club_gap"
                    )
                ),
            )

        with rr2:

            st.metric(
                "Reconciled Gap",
                fmt_number(
                    rr_data.get(
                        "reconciled_gap"
                    )
                ),
            )

        with rr3:

            st.metric(
                "Signal",
                fmt_number(
                    rr_data.get(
                        "reconciled_signal"
                    ),
                    3,
                ),
            )

        lr1, lr2, lr3 = st.columns(3)

        with lr1:

            st.metric(
                "λ Home Before",
                fmt_number(
                    lr_data.get(
                        "home_lambda_before"
                    )
                ),
            )

        with lr2:

            st.metric(
                "λ Home After",
                fmt_number(
                    lr_data.get(
                        "home_lambda_after"
                    )
                ),
            )

        with lr3:

            st.metric(
                "Share Shift",
                fmt_number(
                    lr_data.get(
                        "share_shift"
                    ),
                    4,
                ),
            )

        with st.expander(
            "Rating reconciliation raw state",
            expanded=False,
        ):

            st.json(
                {
                    "rating_reconciliation":
                        _serialize(
                            rr_data
                        ),
                    "lambda_reconciliation":
                        _serialize(
                            lr_data
                        ),
                }
            )

    # ========================================================
    # RAW BRAIN PREDICTION
    # ========================================================

    st.divider()

    with st.expander(
        "Full BrainPrediction",
        expanded=False,
    ):

        st.json(
            _serialize(
                prediction
            )
        )

    # ========================================================
    # COPYABLE DIAGNOSTIC REPORT
    # ========================================================

    diagnostics_data = (
        prediction.get(
            "diagnostics",
            {}
        )
    )

    report_lines = [

        "============================================================",
        "FAJ BRAIN PREDICTION",
        "============================================================",
        f"Brain: {prediction.get('version', BRAIN_VERSION)}",
        "",
        f"HOME: {home_team}",
        f"AWAY: {away_team}",
        "",
        "CLUB RATING",
        f"Home: {fmt_number(home_rating)}",
        f"Away: {fmt_number(away_rating)}",
        f"Club Rating supplied: "
        f"{diagnostics_data.get('club_rating_supplied', False)}",
        "",
        "LAMBDA",
        f"Home: {fmt_number(home_lambda)}",
        f"Away: {fmt_number(away_lambda)}",
        f"Total: {fmt_number(total_lambda)}",
        "",
        "RATING RECONCILIATION",
        f"Club gap: "
        f"{fmt_number(diagnostics_data.get('club_gap'))}",
        f"Pair gap: "
        f"{fmt_number(diagnostics_data.get('pair_gap'))}",
        f"Reconciled gap: "
        f"{fmt_number(diagnostics_data.get('reconciled_gap'))}",
        f"Reconciled signal: "
        f"{fmt_number(diagnostics_data.get('reconciled_signal'), 3)}",
        f"Share shift: "
        f"{fmt_number(diagnostics_data.get('lambda_share_shift'), 4)}",
        f"Lambda total preserved: "
        f"{diagnostics_data.get('lambda_total_preserved', '—')}",
        "",
        "1X2",
        f"Home: {fmt_probability(home_win)}",
        f"Draw: {fmt_probability(draw)}",
        f"Away: {fmt_probability(away_win)}",
        "",
        "GOALS",
        f"BTTS: {fmt_probability(btts)}",
        f"Over 2.5: {fmt_probability(over25)}",
        f"Under 2.5: {fmt_probability(under25)}",
        f"Over 3.5: {fmt_probability(over35)}",
        f"Under 3.5: {fmt_probability(under35)}",
        "",
        "EXACT SCORE",
        f"1: {predicted_score or '—'} "
        f"({fmt_probability(score_probability)})",
        f"2: {second_score or '—'}",
        f"3: {third_score or '—'}",
        "",
        f"PRIMARY OUTCOME: "
        f"{prediction.get('primary_outcome') or '—'}",
        f"PRIMARY SCENARIO: "
        f"{prediction.get('primary_scenario') or '—'}",
        "",
        "CONFIDENCE",
        "—",
        "",
        "RISK",
        "—",
        "",
        "IMPORTANT",
        "Club Rating is passed into FAJ Brain.",
        "Rating Reconciliation is performed inside FAJ Brain.",
        "Adjusted lambda is passed to ProbabilityModel.",
        "Adjusted lambda is passed to ScorePredictor.",
        "No rating multiplier.",
        "No form multiplier.",
        "No control multiplier.",
        "No defence multiplier.",
        "No anomaly multiplier.",
        "No special-form multiplier.",
        "No Winner Override.",
        "No future result.",
        "No database write.",
        "PredictionManager is not used.",
        "============================================================",
    ]

    diagnostic_report = "\n".join(
        report_lines
    )

    with st.expander(
        "Copyable FAJ diagnostic report",
        expanded=False,
    ):

        st.code(
            diagnostic_report,
            language="text",
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "FAJ Platform v12.1 · "
    "FAJ Brain v4.0 · CONTRACT_V1 · "
    "SQLite / FACTS / STATE / PROBABILITIES / SYNTHESIS"
)

st.caption(
    "Prediction ≠ Fact · "
    "Missing ≠ 0 · "
    "Brain does not learn · "
    "Brain does not write database · "
    "Club Rating is an input to Brain · "
    "Rating Reconciliation belongs to Brain"
)
