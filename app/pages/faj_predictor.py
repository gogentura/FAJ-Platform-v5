#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PERSONAL PREDICTOR
======================

Единая главная страница персональной аналитической платформы FAJ.

Поток:

    ТУРНИР
       ↓
    МАТЧИ
       ↓
    ИСТОРИЯ
       ↓
    SOCCER365
       ↓
    АНАЛИТИЧЕСКИЕ ДАННЫЕ
       ↓
    FAJ BRAIN
       ↓
    ПРОГНОЗ
       ↓
    КАРТОЧКА

ВАЖНО:

Страница НЕ содержит:
    - Tour Manager
    - Import Facts
    - ETC
    - Learning
    - Rating Evolution
    - старую систему туров
    - bookmaker integration

История может быть собрана из любых турниров.

Минимум для расширенного анализа:
    3 матча.

Допускается:
    1-2 матча — ограниченный анализ.

Максимум:
    6 исторических матчей на команду
    6 прогнозируемых матчей одновременно.

Прогнозный мозг находится отдельно от UI.
Текущий встроенный brain является временным baseline.
Позже его можно заменить новой математической моделью
без переделки страницы.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.database import FAJDatabase
from app.parsers.soccer365_parser import Soccer365Parser
from app.core.faj_brain import FAJBrain
from app.faj_club_ratings import (
    get_all_tournaments,
    get_all_teams,
    get_team_rating,
)

# ============================================================
# FORM CONTEXT
# ============================================================

from app.core.form_context import build_form_context


# ============================================================
# CONFIG
# ============================================================

PAGE_TITLE = "FAJ — Персональный прогноз"

MODEL_VERSION = "FAJ-PERSONAL-BRAIN-0.1"

MIN_EXTENDED_MATCHES = 3
MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6
MAX_RECENT_HISTORY = 5

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE / PARSER
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()


@st.cache_resource
def get_soccer365_parser() -> Soccer365Parser:
    return Soccer365Parser()


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, value))


def pct(value: Optional[float]) -> str:
    if value is None:
        return "—"

    return f"{value * 100:.1f}%"


def num(
    value: Optional[float],
    digits: int = 2,
) -> str:
    if value is None:
        return "—"

    return f"{value:.{digits}f}"


def normalize_name(value: Any) -> str:
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("ё", "е")
    )


def parse_score(
    score: Any,
) -> Tuple[Optional[int], Optional[int]]:

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


def average(
    values: List[float],
) -> Optional[float]:

    if not values:
        return None

    return mean(values)


def weighted_average(
    values: List[float],
) -> Optional[float]:

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    weights = list(range(1, len(values) + 1))

    return sum(
        value * weight
        for value, weight in zip(values, weights)
    ) / sum(weights)


# ============================================================
# SESSION STATE
# ============================================================

def init_state() -> None:

    defaults = {
        "faj_session_id": None,
        "faj_competition": None,
        "faj_matches": [],
        "faj_collected": {},
        "faj_predictions": {},
        "faj_team_cache": {},
        "faj_form_context": {},  # NEW: храним form_context
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


def reset_workspace() -> None:

    st.session_state.faj_session_id = None
    st.session_state.faj_competition = None
    st.session_state.faj_matches = []
    st.session_state.faj_collected = {}
    st.session_state.faj_predictions = {}
    st.session_state.faj_team_cache = {}
    st.session_state.faj_form_context = {}


# ============================================================
# TEAM DATA (UPDATED: источник — FAJ_CLUB_RATINGS)
# ============================================================

def load_teams(
    db: FAJDatabase,
    league: Optional[str] = None,
) -> List[str]:
    """
    Источник команд для FAJ Predictor — единый реестр
    FAJ Club Ratings.
    database.py здесь НЕ используется для формирования
    списка команд UI.
    """
    try:
        teams = get_all_teams(league)
        if not teams:
            logger.warning(
                "FAJ Predictor: для турнира '%s' "
                "нет команд в FAJ_CLUB_RATINGS",
                league,
            )
            return []
        return list(teams)
    except Exception:
        logger.exception(
            "FAJ Predictor: ошибка загрузки команд "
            "из FAJ_CLUB_RATINGS для '%s'",
            league,
        )
        return []


def team_label(
    team_name: str,
    league: Optional[str] = None,
) -> str:

    if league:
        return f"{team_name} · {league}"

    return team_name


def find_team_by_name(
    team_names: List[str],
    team_name: Optional[str],
) -> Optional[str]:

    if team_name is None:
        return None

    for name in team_names:

        if name == team_name:
            return name

    return None


# ============================================================
# MATCH SLOTS (UPDATED: added match_date)
# ============================================================

def create_match_slot() -> Dict[str, Any]:

    return {
        "home_name": None,
        "away_name": None,
        "match_date": None,  # ISO format: YYYY-MM-DD
        "urls_home": [""] * MAX_HISTORY_MATCHES,
        "urls_away": [""] * MAX_HISTORY_MATCHES,
    }


def add_match() -> None:

    matches = st.session_state.faj_matches

    if len(matches) >= MAX_ANALYSIS_MATCHES:

        st.warning(
            f"Можно добавить максимум "
            f"{MAX_ANALYSIS_MATCHES} матчей."
        )

        return

    matches.append(
        create_match_slot()
    )


def remove_match(
    index: int,
) -> None:

    matches = st.session_state.faj_matches

    if not (
        0 <= index < len(matches)
    ):
        return

    matches.pop(index)

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
# SESSION
# ============================================================

def ensure_session(
    db: FAJDatabase,
    competition_name: str,
) -> Optional[int]:

    current = (
        st.session_state.faj_session_id
    )

    if current is not None:

        return current

    try:

        competitions = (
            db.get_competitions()
        )

        competition_id = None

        for competition in competitions:

            if normalize_name(
                competition.get("name")
            ) == normalize_name(
                competition_name
            ):

                competition_id = (
                    competition.get("id")
                )

                break

        session_id = (
            db.create_analysis_session(
                competition_id=competition_id,
                title=(
                    f"FAJ | "
                    f"{competition_name}"
                ),
                notes=(
                    "Персональная "
                    "аналитическая сессия FAJ."
                ),
            )
        )

        st.session_state.faj_session_id = (
            session_id
        )

        return session_id

    except Exception as exc:

        logger.exception(
            "Ошибка создания сессии: %s",
            exc,
        )

        st.error(
            f"Не удалось создать аналитическую сессию: {exc}"
        )

        return None


# ============================================================
# PARSING
# ============================================================

def parse_soccer365(
    url: str,
) -> Dict[str, Any]:

    parser = get_soccer365_parser()

    return parser.parse(
        url.strip()
    )


def validate_parsed_match(
    parsed: Dict[str, Any],
    selected_team: str,
) -> Tuple[bool, str]:

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
            (
                f"Матч {home} — {away} "
                f"не содержит выбранную команду "
                f"{selected_team}."
            ),
        )

    return (
        True,
        f"{home} — {away}",
    )


# ============================================================
# NORMALIZATION OF SOCCER365 RECORD (UPDATED: added match_date)
# ============================================================

def build_history_record(
    parsed: Dict[str, Any],
) -> Dict[str, Any]:

    stats = parsed.get(
        "stats",
        {},
    )

    home = parsed.get(
        "home_team"
    )

    away = parsed.get(
        "away_team"
    )

    score = parsed.get(
        "score"
    )

    home_goals, away_goals = (
        parse_score(score)
    )

    return {

        "home_team": home,
        "away_team": away,

        "match_date": parsed.get(
            "match_date"
        ),

        "score": score,

        "home_goals": home_goals,
        "away_goals": away_goals,

        "xg": {
            "home": stats.get(
                "home_xg"
            ),
            "away": stats.get(
                "away_xg"
            ),
        },

        "shots": {
            "home": stats.get(
                "home_shots"
            ),
            "away": stats.get(
                "away_shots"
            ),
        },

        "shots_on_target": {
            "home": stats.get(
                "home_shots_on_target"
            ),
            "away": stats.get(
                "away_shots_on_target"
            ),
        },

        "possession": {
            "home": stats.get(
                "home_possession"
            ),
            "away": stats.get(
                "away_possession"
            ),
        },

        "corners": {
            "home": stats.get(
                "home_corners"
            ),
            "away": stats.get(
                "away_corners"
            ),
        },

        "cards": {
            "home": stats.get(
                "home_yellow_cards"
            ),
            "away": stats.get(
                "away_yellow_cards"
            ),
        },

        "fouls": {
            "home": stats.get(
                "home_fouls"
            ),
            "away": stats.get(
                "away_fouls"
            ),
        },

        "big_chances": {
            "home": stats.get(
                "home_big_chances"
            ),
            "away": stats.get(
                "away_big_chances"
            ),
        },

        "passes": {
            "home": stats.get(
                "home_total_passes"
            ),
            "away": stats.get(
                "away_total_passes"
            ),
        },

        "pass_accuracy": {
            "home": stats.get(
                "home_pass_accuracy"
            ),
            "away": stats.get(
                "away_pass_accuracy"
            ),
        },

        "tackles": {
            "home": stats.get(
                "home_tackles"
            ),
            "away": stats.get(
                "away_tackles"
            ),
        },

        "quality": parsed.get(
            "quality",
            parsed.get(
                "data_quality",
                0.0,
            ),
        ),

        "source": "Soccer365",

        "source_url": parsed.get(
            "source_url"
        ),

        "parser_version": parsed.get(
            "parser_version"
        ),

        "error": parsed.get(
            "error"
        ),
    }


# ============================================================
# TEAM-SPECIFIC DATA
# ============================================================

def team_side(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[str]:

    target = normalize_name(
        team_name
    )

    if target == normalize_name(
        record.get("home_team")
    ):
        return "home"

    if target == normalize_name(
        record.get("away_team")
    ):
        return "away"

    return None


def team_metric_values(
    records: List[Dict[str, Any]],
    team_name: str,
    metric: str,
) -> List[float]:

    result = []

    for record in records:

        side = team_side(
            record,
            team_name,
        )

        if side is None:
            continue

        values = record.get(
            metric,
            {},
        )

        value = safe_float(
            values.get(side)
        )

        if value is not None:
            result.append(value)

    return result


def team_goals(
    records: List[Dict[str, Any]],
    team_name: str,
) -> Tuple[
    List[int],
    List[int],
]:

    scored = []
    conceded = []

    for record in records:

        side = team_side(
            record,
            team_name,
        )

        if side == "home":

            gf = record.get(
                "home_goals"
            )

            ga = record.get(
                "away_goals"
            )

        elif side == "away":

            gf = record.get(
                "away_goals"
            )

            ga = record.get(
                "home_goals"
            )

        else:
            continue

        if gf is not None:
            scored.append(gf)

        if ga is not None:
            conceded.append(ga)

    return (
        scored,
        conceded,
    )


# ============================================================
# HISTORY SUMMARY
# ============================================================

def build_team_summary(
    records: List[Dict[str, Any]],
    team_name: str,
) -> Dict[str, Any]:

    scored, conceded = team_goals(
        records,
        team_name,
    )

    wins = 0
    draws = 0
    losses = 0

    for gf, ga in zip(
        scored,
        conceded,
    ):

        if gf > ga:
            wins += 1

        elif gf == ga:
            draws += 1

        else:
            losses += 1

    corners = team_metric_values(
        records,
        team_name,
        "corners",
    )

    cards = team_metric_values(
        records,
        team_name,
        "cards",
    )

    xg = team_metric_values(
        records,
        team_name,
        "xg",
    )

    shots = team_metric_values(
        records,
        team_name,
        "shots",
    )

    shots_on_target = team_metric_values(
        records,
        team_name,
        "shots_on_target",
    )

    possession = team_metric_values(
        records,
        team_name,
        "possession",
    )

    big_chances = team_metric_values(
        records,
        team_name,
        "big_chances",
    )

    return {

        "matches": len(records),

        "wins": wins,
        "draws": draws,
        "losses": losses,

        "goals_for_avg": average(
            scored
        ),

        "goals_against_avg": average(
            conceded
        ),

        "goals_for_recent": weighted_average(
            scored
        ),

        "goals_against_recent": weighted_average(
            conceded
        ),

        "xg_avg": average(xg),

        "corners_avg": average(
            corners
        ),

        "cards_avg": average(
            cards
        ),

        "shots_avg": average(
            shots
        ),

        "shots_on_target_avg": average(
            shots_on_target
        ),

        "possession_avg": average(
            possession
        ),

        "big_chances_avg": average(
            big_chances
        ),
    }


# ============================================================
# FAJ REVOLUTION BRAIN
# ============================================================

@st.cache_resource
def get_faj_brain() -> FAJBrain:
    return FAJBrain()


def _percent_to_fraction(
    value: Optional[float],
) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value) / 100.0
    except (TypeError, ValueError):
        return None


def build_prediction(
    home_team: str,
    away_team: str,
    history_home: List[Dict[str, Any]],
    history_away: List[Dict[str, Any]],
    home_form_context: Optional[Dict[str, Any]] = None,
    away_form_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Единая точка подключения нового FAJ Brain к UI.
    UI получает старый стабильный формат данных,
    а расчёт полностью выполняет новый faj_brain.py.
    """
    brain = get_faj_brain()
    result = brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=history_home,
        away_matches=history_away,
    )

    # Добавляем form_context в результат
    if home_form_context:
        result["home_form_context"] = home_form_context
    if away_form_context:
        result["away_form_context"] = away_form_context

    return {
        # ----------------------------------------------------
        # META
        # ----------------------------------------------------
        "model_version": result.get(
            "calculation_meta",
            {},
        ).get(
            "brain_version",
            "FAJ-BRAIN",
        ),
        "home_team": result.get(
            "home_team",
            home_team,
        ),
        "away_team": result.get(
            "away_team",
            away_team,
        ),

        # ----------------------------------------------------
        # MAIN OUTCOME
        # UI expects probabilities 0..1
        # Brain returns probabilities 0..100
        # ----------------------------------------------------
        "home_win_probability":
            _percent_to_fraction(
                result.get(
                    "home_win_probability"
                )
            ),
        "draw_probability":
            _percent_to_fraction(
                result.get(
                    "draw_probability"
                )
            ),
        "away_win_probability":
            _percent_to_fraction(
                result.get(
                    "away_win_probability"
                )
            ),
        "confidence":
            _percent_to_fraction(
                result.get(
                    "confidence"
                )
            ),
        "risk": result.get(
            "risk",
            "—",
        ),

        # ----------------------------------------------------
        # GOALS
        # ----------------------------------------------------
        "btts": (
            "ДА"
            if (
                result.get(
                    "btts_probability"
                ) is not None
                and result.get(
                    "btts_probability"
                ) >= 50
            )
            else "НЕТ"
        ),
        "btts_probability":
            _percent_to_fraction(
                result.get(
                    "btts_probability"
                )
            ),
        "over25": (
            "ДА"
            if (
                result.get(
                    "over25_probability"
                ) is not None
                and result.get(
                    "over25_probability"
                ) >= 50
            )
            else "НЕТ"
        ),
        "over25_probability":
            _percent_to_fraction(
                result.get(
                    "over25_probability"
                )
            ),
        "over35": (
            "ДА"
            if (
                result.get(
                    "over35_probability"
                ) is not None
                and result.get(
                    "over35_probability"
                ) >= 50
            )
            else "НЕТ"
        ),
        "over35_probability":
            _percent_to_fraction(
                result.get(
                    "over35_probability"
                )
            ),

        # xG сохраняем для внутренней аналитики.
        # В основной карточке пока не показываем.
        "home_xg_internal":
            result.get(
                "home_xg"
            ),
        "away_xg_internal":
            result.get(
                "away_xg"
            ),

        # ----------------------------------------------------
        # TOP 3 SCORES
        # ----------------------------------------------------
        "scores": [
            {
                "score": result.get(
                    "most_likely_score",
                    "—",
                ),
                "probability": None,
            },
            {
                "score": result.get(
                    "second_likely_score",
                    "—",
                ),
                "probability": None,
            },
            {
                "score": result.get(
                    "third_likely_score",
                    "—",
                ),
                "probability": None,
            },
        ],

        # ----------------------------------------------------
        # CORNERS
        # ----------------------------------------------------
        "corners_expected":
            result.get(
                "corners_expected"
            ),
        "home_corners_expected":
            result.get(
                "home_corners_expected"
            ),
        "away_corners_expected":
            result.get(
                "away_corners_expected"
            ),
        "corners_lines": {
            "7.5":
                _percent_to_fraction(
                    result.get(
                        "over75_corners_probability"
                    )
                ),
            "8.5":
                _percent_to_fraction(
                    result.get(
                        "over85_corners_probability"
                    )
                ),
            "9.5":
                _percent_to_fraction(
                    result.get(
                        "over95_corners_probability"
                    )
                ),
            "10.5":
                _percent_to_fraction(
                    result.get(
                        "over105_corners_probability"
                    )
                ),
        },
        "corners_range": _get_corners_range(
            result.get(
                "corners_expected"
            )
        ),

        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------
        "cards_expected":
            result.get(
                "cards_expected"
            ),
        "home_cards_expected":
            result.get(
                "home_cards_expected"
            ),
        "away_cards_expected":
            result.get(
                "away_cards_expected"
            ),
        "cards_lines": {
            "2.5":
                _percent_to_fraction(
                    result.get(
                        "over25_cards_probability"
                    )
                ),
            "3.5":
                _percent_to_fraction(
                    result.get(
                        "over35_cards_probability"
                    )
                ),
            "4.5":
                _percent_to_fraction(
                    result.get(
                        "over45_cards_probability"
                    )
                ),
        },
        "cards_range": _get_cards_range(
            result.get(
                "cards_expected"
            )
        ),

        # ----------------------------------------------------
        # ANALYSIS
        # ----------------------------------------------------
        "analysis":
            result.get(
                "conclusion",
                "Аналитический вывод FAJ пока недоступен.",
            ),

        # ----------------------------------------------------
        # DATA STATUS
        # ----------------------------------------------------
        "data": {
            "home_summary": None,
            "away_summary": None,
            "home_matches":
                len(history_home),
            "away_matches":
                len(history_away),
        },

        # ----------------------------------------------------
        # FORM CONTEXT
        # ----------------------------------------------------
        "home_form_context": home_form_context,
        "away_form_context": away_form_context,

        # ----------------------------------------------------
        # INTERNAL CALCULATION DATA
        # ----------------------------------------------------
        "brain_result": result,
    }


def _get_corners_range(
    expected: Optional[float],
) -> str:
    if expected is None:
        return "—"
    if expected < 8:
        return "7–9"
    if expected < 10:
        return "8–10"
    if expected < 12:
        return "9–11"
    return "10–12+"


def _get_cards_range(
    expected: Optional[float],
) -> str:
    if expected is None:
        return "—"
    if expected < 3:
        return "2–3"
    if expected < 4:
        return "3–4"
    if expected < 5:
        return "4–5"
    return "5+"


# ============================================================
# DATABASE SAVE
# ============================================================

def save_prediction_to_database(
    db: FAJDatabase,
    session_id: int,
    match_id: int,
    prediction: Dict[str, Any],
) -> Optional[int]:

    try:

        scores = prediction.get(
            "scores",
            [],
        )

        first = (
            scores[0]["score"]
            if len(scores) > 0
            else None
        )

        second = (
            scores[1]["score"]
            if len(scores) > 1
            else None
        )

        third = (
            scores[2]["score"]
            if len(scores) > 2
            else None
        )

        db_prediction = {

            "home_xg": prediction.get(
                "home_xg_internal"
            ),

            "away_xg": prediction.get(
                "away_xg_internal"
            ),

            "home_goals_expected": prediction.get(
                "home_xg_internal"
            ),

            "away_goals_expected": prediction.get(
                "away_xg_internal"
            ),

            "home_win_probability": prediction.get(
                "home_win_probability"
            ),

            "draw_probability": prediction.get(
                "draw_probability"
            ),

            "away_win_probability": prediction.get(
                "away_win_probability"
            ),

            "btts_probability": prediction.get(
                "btts_probability"
            ),

            "over25_probability": prediction.get(
                "over25_probability"
            ),

            "over35_probability": prediction.get(
                "over35_probability"
            ),

            "most_likely_score": first,

            "second_likely_score": second,

            "third_likely_score": third,

            "corners_expected": prediction.get(
                "corners_expected"
            ),

            "home_corners_expected": prediction.get(
                "home_corners_expected"
            ),

            "away_corners_expected": prediction.get(
                "away_corners_expected"
            ),

            "cards_expected": prediction.get(
                "cards_expected"
            ),

            "home_cards_expected": prediction.get(
                "home_cards_expected"
            ),

            "away_cards_expected": prediction.get(
                "away_cards_expected"
            ),

            "confidence": prediction.get(
                "confidence"
            ),

            "risk": prediction.get(
                "risk"
            ),

            "summary": prediction.get(
                "analysis"
            ),

            "analysis_json": prediction,
        }

        return db.save_prediction(
            analysis_match_id=match_id,
            prediction=db_prediction,
            model_version=MODEL_VERSION,
        )

    except Exception as exc:

        logger.exception(
            "Ошибка сохранения прогноза: %s",
            exc,
        )

        return None


# ============================================================
# SAVE HISTORY (UPDATED: сохраняем match_date)
# ============================================================

def save_history(
    db: FAJDatabase,
    analysis_match_id: int,
    selected_team_id: int,
    opponent_team_id: int,
    records: List[Dict[str, Any]],
) -> None:

    for record in records:

        source_id = db.add_source(

            analysis_match_id=(
                analysis_match_id
            ),

            team_id=selected_team_id,

            source_type="soccer365",

            source_name="Soccer365",

            source_url=record.get(
                "source_url"
            ),

            parser_version=record.get(
                "parser_version"
            ),
        )

        home_name = record.get(
            "home_team"
        )

        away_name = record.get(
            "away_team"
        )

        home_goals = record.get(
            "home_goals"
        )

        away_goals = record.get(
            "away_goals"
        )

        if (
            home_goals is not None
            and
            away_goals is not None
        ):

            if home_goals > away_goals:
                home_result = "win"
                away_result = "loss"

            elif home_goals < away_goals:
                home_result = "loss"
                away_result = "win"

            else:
                home_result = "draw"
                away_result = "draw"

        else:

            home_result = None
            away_result = None

        # ----------------------------------------------------
        # HOME SIDE
        # ----------------------------------------------------

        if home_name and away_name:

            home_id = selected_team_id
            away_id = opponent_team_id

            if normalize_name(
                home_name
            ) != normalize_name(
                st.session_state.get(
                    "_current_home_name",
                    home_name,
                )
            ):

                home_id = opponent_team_id
                away_id = selected_team_id

            historical_id = (
                db.save_historical_match(
                    analysis_match_id=(
                        analysis_match_id
                    ),

                    team_id=home_id,

                    opponent_team_id=away_id,

                    source_id=source_id,

                    match_date=record.get(
                        "match_date"
                    ),

                    is_home=True,

                    goals_for=home_goals,

                    goals_against=away_goals,

                    result=home_result,

                    external_match_id=None,

                    raw_metadata={
                        "source": "Soccer365",
                        "source_url": record.get(
                            "source_url"
                        ),
                    },
                )
            )

            save_stats_for_side(
                db,
                historical_id,
                record,
                "home",
            )

        # ----------------------------------------------------
        # AWAY SIDE
        # ----------------------------------------------------

        historical_id = (
            db.save_historical_match(
                analysis_match_id=(
                    analysis_match_id
                ),

                team_id=away_id,

                opponent_team_id=home_id,

                source_id=source_id,

                match_date=record.get(
                    "match_date"
                ),

                is_home=False,

                goals_for=away_goals,

                goals_against=home_goals,

                result=away_result,

                external_match_id=None,

                raw_metadata={
                    "source": "Soccer365",
                    "source_url": record.get(
                        "source_url"
                    ),
                },
            )
        )

        save_stats_for_side(
            db,
            historical_id,
            record,
            "away",
        )


def save_stats_for_side(
    db: FAJDatabase,
    historical_id: int,
    record: Dict[str, Any],
    side: str,
) -> None:

    def get(
        group: str,
        key: str,
    ) -> Any:

        return (
            record.get(
                group,
                {},
            ).get(
                key
            )
        )

    db.save_historical_stats(

        historical_id,

        {

            "possession": get(
                "possession",
                side,
            ),

            "shots": get(
                "shots",
                side,
            ),

            "shots_on_target": get(
                "shots_on_target",
                side,
            ),

            "corners": get(
                "corners",
                side,
            ),

            "fouls": get(
                "fouls",
                side,
            ),

            "yellow_cards": get(
                "cards",
                side,
            ),

            "xg": get(
                "xg",
                side,
            ),

            "big_chances": get(
                "big_chances",
                side,
            ),

            "passes": get(
                "passes",
                side,
            ),

            "pass_accuracy": get(
                "pass_accuracy",
                side,
            ),

            "tackles": get(
                "tackles",
                side,
            ),

            "raw_metadata": {
                "source": "Soccer365",
                "source_url": record.get(
                    "source_url"
                ),
            },
        },
    )


# ============================================================
# COLLECTION (UPDATED: фильтрация по дате)
# ============================================================

def collect_team_history(
    team_name: str,
    urls: List[str],
    forecast_date: Optional[str] = None,
) -> Tuple[
    List[Dict[str, Any]],
    List[str],
]:
    """
    Собирает историю команды из Soccer365 URL.
    Фильтрует по дате прогноза и сортирует по убыванию даты.
    """
    clean_urls = [
        url.strip()
        for url in urls
        if url and url.strip()
    ]

    # Убираем дубликаты URL, сохраняя порядок ввода
    clean_urls = list(
        dict.fromkeys(clean_urls)
    )

    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    # --------------------------------------------------------
    # PARSE ALL PROVIDED MATCHES
    # --------------------------------------------------------
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

        # ----------------------------------------------------
        # DATE REQUIRED FOR ORDERING
        # ----------------------------------------------------
        match_date = record.get(
            "match_date"
        )
        if not match_date:
            errors.append(
                f"{position}. "
                f"{message}: "
                f"не удалось определить дату матча."
            )
            continue

        # ----------------------------------------------------
        # FUTURE MATCH PROTECTION
        # ----------------------------------------------------
        if forecast_date:
            try:
                if (
                    str(match_date)
                    >= str(forecast_date)
                ):
                    errors.append(
                        f"{position}. "
                        f"{message}: "
                        f"матч от {match_date} "
                        f"не является прошлым "
                        f"относительно "
                        f"{forecast_date}."
                    )
                    continue
            except Exception:
                errors.append(
                    f"{position}. "
                    f"{message}: "
                    f"некорректная дата "
                    f"{match_date}."
                )
                continue

        records.append(
            record
        )

    # --------------------------------------------------------
    # SORT: новейший → старый
    # --------------------------------------------------------
    records.sort(
        key=lambda record: str(
            record.get(
                "match_date",
                ""
            )
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # ONLY LAST 5
    # --------------------------------------------------------
    records = records[
        :MAX_RECENT_HISTORY
    ]

    return (
        records,
        errors,
    )


# ============================================================
# DATA QUALITY
# ============================================================

def calculate_collection_quality(
    records: List[Dict[str, Any]],
) -> float:

    if not records:
        return 0.0

    qualities = []

    for record in records:

        quality = safe_float(
            record.get(
                "quality"
            )
        )

        if quality is not None:
            qualities.append(
                quality
            )

    if not qualities:
        return 0.0

    return average(
        qualities
    ) or 0.0


# ============================================================
# UI — HEADER
# ============================================================

def render_header() -> None:

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="⚽",
        layout="wide",
    )

    st.markdown(
        """
        <style>

        .faj-title {
            font-size: 42px;
            font-weight: 800;
            margin-bottom: 0;
        }

        .faj-subtitle {
            color: #777;
            font-size: 17px;
            margin-top: 0;
            margin-bottom: 25px;
        }

        .faj-card {
            border: 1px solid rgba(128,128,128,.25);
            border-radius: 18px;
            padding: 20px;
            margin: 10px 0;
        }

        .faj-score {
            font-size: 28px;
            font-weight: 800;
        }

        .faj-big {
            font-size: 32px;
            font-weight: 800;
        }

        .faj-muted {
            color: #777;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="faj-title">⚽ FAJ</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="faj-subtitle">
        Персональная футбольная аналитическая платформа
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# UI — MATCH CARD
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

    st.markdown(
        f"""
        <div class="faj-card">

        <div style="text-align:center">
        <div class="faj-muted">
        FAJ ПРОГНОЗ
        </div>

        <div class="faj-big">
        {home} — {away}
        </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # MAIN OUTCOME
    # --------------------------------------------------------

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

        st.metric(
            "Уверенность FAJ",
            pct(
                prediction.get(
                    "confidence"
                )
            ),
        )

    with c2:

        st.metric(
            "Риск",
            prediction.get(
                "risk",
                "—",
            ),
        )

    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    st.subheader(
        "2. Голы"
    )

    c1, c2, c3 = st.columns(3)

    btts = prediction.get(
        "btts_probability"
    )

    over25 = prediction.get(
        "over25_probability"
    )

    over35 = prediction.get(
        "over35_probability"
    )

    with c1:

        st.metric(
            "Обе забьют",
            "ДА"
            if btts is not None
            and btts >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(btts)}"
        )

    with c2:

        st.metric(
            "ТБ 2.5",
            "ДА"
            if over25 is not None
            and over25 >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(over25)}"
        )

    with c3:

        st.metric(
            "ТБ 3.5",
            "ДА"
            if over35 is not None
            and over35 >= 0.5
            else "НЕТ",
        )

        st.caption(
            f"Вероятность: {pct(over35)}"
        )

    # --------------------------------------------------------
    # SCORES
    # --------------------------------------------------------

    st.subheader(
        "3. Наиболее вероятные точные счета"
    )

    scores = prediction.get(
        "scores",
        [],
    )

    cols = st.columns(
        max(1, len(scores))
    )

    for index, item in enumerate(
        scores
    ):

        with cols[index]:

            st.markdown(
                f"""
                <div class="faj-card"
                     style="text-align:center">

                <div class="faj-score">
                {item.get("score")}
                </div>

                <div class="faj-muted">
                {pct(item.get("probability")) if item.get("probability") is not None else "—"}
                </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

    # --------------------------------------------------------
    # CORNERS
    # --------------------------------------------------------

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
            f"{home}",
            num(
                prediction.get(
                    "home_corners_expected"
                )
            ),
        )

    with c3:

        st.metric(
            f"{away}",
            num(
                prediction.get(
                    "away_corners_expected"
                )
            ),
        )

    st.write(
        "Наиболее вероятный диапазон: "
        f"**{prediction.get('corners_range', '—')}**"
    )

    corner_lines = prediction.get(
        "corners_lines",
        {},
    )

    c1, c2, c3, c4 = st.columns(4)

    for column, line in zip(
        (c1, c2, c3, c4),
        (
            "7.5",
            "8.5",
            "9.5",
            "10.5",
        ),
    ):

        with column:

            st.metric(
                f"ТБ {line}",
                pct(
                    corner_lines.get(
                        line
                    )
                ),
            )

    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

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
            f"{home}",
            num(
                prediction.get(
                    "home_cards_expected"
                )
            ),
        )

    with c3:

        st.metric(
            f"{away}",
            num(
                prediction.get(
                    "away_cards_expected"
                )
            ),
        )

    st.write(
        "Наиболее вероятный диапазон: "
        f"**{prediction.get('cards_range', '—')}**"
    )

    card_lines = prediction.get(
        "cards_lines",
        {},
    )

    c1, c2, c3 = st.columns(3)

    for column, line in zip(
        (c1, c2, c3),
        (
            "2.5",
            "3.5",
            "4.5",
        ),
    ):

        with column:

            st.metric(
                f"ТБ {line}",
                pct(
                    card_lines.get(
                        line
                    )
                ),
            )

    # --------------------------------------------------------
    # ANALYTICAL CONCLUSION
    # --------------------------------------------------------

    st.subheader(
        "6. Аналитический вывод FAJ"
    )

    st.info(
        prediction.get(
            "analysis",
            "Аналитический вывод пока недоступен.",
        )
    )


# ============================================================
# UI — DATA CARD
# ============================================================

def render_data_summary(
    team_name: str,
    records: List[Dict[str, Any]],
) -> None:

    summary = build_team_summary(
        records,
        team_name,
    )

    quality = calculate_collection_quality(
        records
    )

    st.markdown(
        f"### {team_name}"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Матчей",
            summary["matches"],
        )

    with c2:

        st.metric(
            "Голы за матч",
            num(
                summary[
                    "goals_for_avg"
                ]
            ),
        )

    with c3:

        st.metric(
            "Угловые",
            num(
                summary[
                    "corners_avg"
                ]
            ),
        )

    with c4:

        st.metric(
            "Карточки",
            num(
                summary[
                    "cards_avg"
                ]
            ),
        )

    st.caption(
        f"Качество собранных данных: "
        f"{quality * 100:.0f}%"
    )


# ============================================================
# UI — MATCH SETUP (UPDATED: added date picker)
# ============================================================

def render_match_setup(
    index: int,
    match: Dict[str, Any],
    team_names: List[str],
) -> None:

    st.markdown(
        f"## Матч {index + 1}"
    )

    home_current = match.get("home_name")
    away_current = match.get("away_name")

    # Если нет выбранной команды — берём первую из списка
    if home_current not in team_names:
        home_current = team_names[0] if team_names else ""

    # Исключаем домашнюю команду из списка гостей
    away_options = [
        name
        for name in team_names
        if name != home_current
    ]

    if not away_options:

        st.warning(
            "Для выбора соперника "
            "нужно минимум две команды."
        )

        return

    if away_current not in away_options:
        away_current = away_options[0] if away_options else ""

    c1, c2 = st.columns(2)

    with c1:

        selected_home = st.selectbox(
            "🏠 Хозяева",
            team_names,
            index=(
                team_names.index(home_current)
                if home_current in team_names
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

        if not available_away:
            return

        selected_away = st.selectbox(
            "✈️ Гости",
            available_away,
            index=(
                available_away.index(away_current)
                if away_current in available_away
                else 0
            ),
            key=f"away_{index}",
        )

    match["home_name"] = selected_home
    match["away_name"] = selected_away

    # --------------------------------------------------------
    # FORECAST MATCH DATE
    # --------------------------------------------------------
    current_match_date = match.get("match_date")

    if current_match_date:
        try:
            default_match_date = date.fromisoformat(
                current_match_date
            )
        except (TypeError, ValueError):
            default_match_date = date.today()
    else:
        default_match_date = date.today()

    forecast_date = st.date_input(
        "📅 Дата прогнозируемого матча",
        value=default_match_date,
        key=f"match_date_{index}",
    )

    match["match_date"] = forecast_date.isoformat()

    st.markdown(
        "#### История хозяев"
    )

    home_url_cols = st.columns(3)

    for i in range(3):

        with home_url_cols[i]:

            match[
                "urls_home"
            ][i] = st.text_input(
                f"Soccer365 #{i + 1}",
                value=match[
                    "urls_home"
                ][i],
                key=f"home_url_{index}_{i}",
                placeholder=(
                    "https://soccer365.ru/..."
                ),
            )

    with st.expander(
        "Ещё матчи хозяев"
    ):

        extra_cols = st.columns(3)

        for position, i in enumerate(
            range(3, 6),
            start=4,
        ):

            with extra_cols[position - 4]:

                match[
                    "urls_home"
                ][i] = st.text_input(
                    f"Soccer365 #{position}",
                    value=match[
                        "urls_home"
                    ][i],
                    key=f"home_url_{index}_{i}",
                )

    st.markdown(
        "#### История гостей"
    )

    away_url_cols = st.columns(3)

    for i in range(3):

        with away_url_cols[i]:

            match[
                "urls_away"
            ][i] = st.text_input(
                f"Soccer365 #{i + 1}",
                value=match[
                    "urls_away"
                ][i],
                key=f"away_url_{index}_{i}",
                placeholder=(
                    "https://soccer365.ru/..."
                ),
            )

    with st.expander(
        "Ещё матчи гостей"
    ):

        extra_cols = st.columns(3)

        for position, i in enumerate(
            range(3, 6),
            start=4,
        ):

            with extra_cols[position - 4]:

                match[
                    "urls_away"
                ][i] = st.text_input(
                    f"Soccer365 #{position}",
                    value=match[
                        "urls_away"
                    ][i],
                    key=f"away_url_{index}_{i}",
                )

    c1, c2 = st.columns(2)

    with c1:

        if st.button(
            "📥 Собрать статистику",
            key=f"collect_{index}",
            use_container_width=True,
        ):

            collect_and_store_match(
                index=index,
                match=match,
                db=get_database(),
            )

    with c2:

        if st.button(
            "🧠 Получить прогноз",
            key=f"predict_{index}",
            use_container_width=True,
        ):

            generate_prediction(
                index=index,
                match=match,
                db=get_database(),
            )

    # --------------------------------------------------------
    # DATA STATUS
    # --------------------------------------------------------

    collected = (
        st.session_state
        .faj_collected
        .get(index)
    )

    if collected:

        st.success(
            "Статистика собрана."
        )

        home_records = (
            collected.get(
                "home_records",
                [],
            )
        )

        away_records = (
            collected.get(
                "away_records",
                [],
            )
        )

        c1, c2 = st.columns(2)

        with c1:

            render_data_summary(
                selected_home,
                home_records,
            )

        with c2:

            render_data_summary(
                selected_away,
                away_records,
            )

        errors = collected.get(
            "errors",
            [],
        )

        if errors:

            with st.expander(
                "Показать сообщения сбора"
            ):

                for error in errors:

                    st.warning(
                        error
                    )

    prediction = (
        st.session_state
        .faj_predictions
        .get(index)
    )

    if prediction:

        st.divider()

        render_prediction_card(
            prediction
        )


# ============================================================
# COLLECTION + DATABASE (UPDATED: с датой прогноза)
# ============================================================

def collect_and_store_match(
    index: int,
    match: Dict[str, Any],
    db: FAJDatabase,
) -> None:

    home_name = match.get("home_name")
    away_name = match.get("away_name")
    tournament = st.session_state.faj_competition
    forecast_date = match.get("match_date")

    if not home_name or not away_name:
        st.error(
            "Сначала выберите обе команды."
        )
        return

    if not tournament:
        st.error("Не выбран турнир.")
        return

    if not forecast_date:
        st.error("Укажите дату прогнозируемого матча.")
        return

    # --------------------------------------------------------
    # ПОЛУЧАЕМ ID КОМАНД ИЗ БД (создаём если нет)
    # --------------------------------------------------------

    home_id = get_or_create_team(db, home_name, tournament)
    away_id = get_or_create_team(db, away_name, tournament)

    if home_id is None or away_id is None:
        st.error(
            "Не удалось загрузить выбранные команды."
        )
        return

    session_id = ensure_session(
        db,
        tournament,
    )

    if session_id is None:
        return

    # ========================================================
    # СОЗДАЁМ ANALYSIS MATCH С ДАТОЙ ПРОГНОЗА
    # ========================================================
    try:
        analysis_match_id = db.add_analysis_match(
            session_id=session_id,
            home_team_id=home_id,
            away_team_id=away_id,
            match_date=forecast_date,
        )
    except Exception as exc:
        logger.exception(
            "Ошибка создания analysis match: %s",
            exc,
        )
        st.error(
            f"Не удалось создать матч: {exc}"
        )
        return

    all_errors = []

    with st.status(
        "Собираю данные Soccer365...",
        expanded=True,
    ):

        st.write(
            f"🏠 {home_name}"
        )

        home_records, home_errors = (
            collect_team_history(
                home_name,
                match.get(
                    "urls_home",
                    [],
                ),
                forecast_date=forecast_date,
            )
        )

        all_errors.extend(
            [
                f"{home_name}: {error}"
                for error in home_errors
            ]
        )

        st.write(
            f"Получено матчей: "
            f"{len(home_records)}"
        )

        st.write(
            f"✈️ {away_name}"
        )

        away_records, away_errors = (
            collect_team_history(
                away_name,
                match.get(
                    "urls_away",
                    [],
                ),
                forecast_date=forecast_date,
            )
        )

        all_errors.extend(
            [
                f"{away_name}: {error}"
                for error in away_errors
            ]
        )

        st.write(
            f"Получено матчей: "
            f"{len(away_records)}"
        )

    # --------------------------------------------------------
    # SAVE HOME HISTORY
    # --------------------------------------------------------

    if home_records:

        st.session_state[
            "_current_home_name"
        ] = home_name

        try:

            save_history(
                db=db,
                analysis_match_id=(
                    analysis_match_id
                ),
                selected_team_id=home_id,
                opponent_team_id=away_id,
                records=home_records,
            )

        except Exception as exc:

            logger.exception(
                "Ошибка сохранения истории хозяев: %s",
                exc,
            )

            all_errors.append(
                f"Ошибка БД хозяев: {exc}"
            )

    # --------------------------------------------------------
    # SAVE AWAY HISTORY
    # --------------------------------------------------------

    if away_records:

        st.session_state[
            "_current_home_name"
        ] = away_name

        try:

            save_history(
                db=db,
                analysis_match_id=(
                    analysis_match_id
                ),
                selected_team_id=away_id,
                opponent_team_id=home_id,
                records=away_records,
            )

        except Exception as exc:

            logger.exception(
                "Ошибка сохранения истории гостей: %s",
                exc,
            )

            all_errors.append(
                f"Ошибка БД гостей: {exc}"
            )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    st.session_state.faj_collected[
        index
    ] = {
        "tournament": tournament,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "analysis_match_id": analysis_match_id,
        "home_records": home_records,
        "away_records": away_records,
        "errors": all_errors,
    }

    st.success(
        f"Сбор завершён: "
        f"{len(home_records)} матчей "
        f"для {home_name}, "
        f"{len(away_records)} матчей "
        f"для {away_name}."
    )


# ============================================================
# TEAM MANAGEMENT
# ============================================================

def get_or_create_team(
    db: FAJDatabase,
    team_name: str,
    league: str,
) -> Optional[int]:

    try:
        # Проверяем, есть ли команда в БД
        teams = db.get_teams(league=league)
        for team in teams:
            if team.get("name") == team_name:
                return team.get("id")

        # Если нет — создаём
        from app.faj_club_ratings import get_team_rating
        rating = get_team_rating(team_name, league)

        # Добавляем команду в БД
        with db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO teams (name, league)
                VALUES (?, ?)
                ON CONFLICT(name, league) DO UPDATE SET
                    active = 1
                RETURNING id
            """, (team_name, league))
            row = cursor.fetchone()
            if row:
                return row["id"]

        return None

    except Exception as exc:
        logger.exception(
            "Ошибка получения/создания команды: %s",
            exc,
        )
        return None


# ============================================================
# PREDICTION (UPDATED: добавляем form_context)
# ============================================================

def generate_prediction(
    index: int,
    match: Dict[str, Any],
    db: FAJDatabase,
) -> None:

    collected = (
        st.session_state
        .faj_collected
        .get(index)
    )

    if not collected:

        st.warning(
            "Сначала соберите статистику."
        )

        return

    home_name = match.get("home_name")
    away_name = match.get("away_name")

    if not home_name or not away_name:

        st.error(
            "Не выбраны команды."
        )

        return

    home_records = collected.get(
        "home_records",
        [],
    )

    away_records = collected.get(
        "away_records",
        [],
    )

    total_samples = min(
        len(home_records),
        len(away_records),
    )

    if total_samples < 3:

        st.warning(
            f"Сейчас доступно "
            f"{total_samples} полных наблюдений. "
            f"Для расширенного анализа FAJ "
            f"рекомендует минимум 3 матча."
        )

    # ========================================================
    # FORM CONTEXT
    # ========================================================

    home_form_context = build_form_context(
        team_name=home_name,
        records=home_records,
        limit=5,
    )

    away_form_context = build_form_context(
        team_name=away_name,
        records=away_records,
        limit=5,
    )

    # Сохраняем в session_state для отображения
    st.session_state.faj_form_context[index] = {
        "home": home_form_context,
        "away": away_form_context,
    }

    prediction = build_prediction(
        home_team=home_name,
        away_team=away_name,
        history_home=home_records,
        history_away=away_records,
        home_form_context=home_form_context,
        away_form_context=away_form_context,
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    analysis_match_id = (
        collected.get(
            "analysis_match_id"
        )
    )

    if analysis_match_id:

        prediction_id = (
            save_prediction_to_database(
                db=db,
                session_id=(
                    st.session_state
                    .faj_session_id
                ),
                match_id=(
                    analysis_match_id
                ),
                prediction=prediction,
            )
        )

        prediction[
            "prediction_id"
        ] = prediction_id

    st.session_state.faj_predictions[
        index
    ] = prediction

    st.success(
        "FAJ сформировал прогноз."
    )


# ============================================================
# DATA SOURCE INFO
# ============================================================

def render_source_info() -> None:

    st.divider()

    st.caption(
        "Источники данных"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.markdown(
            "**Soccer365**"
        )

        st.caption(
            "Основной источник статистики "
            "исторических матчей."
        )

    with c2:

        st.markdown(
            "**FAJ Database**"
        )

        st.caption(
            "Локальное хранение истории "
            "анализа и прогнозов."
        )

    with c3:

        st.markdown(
            "**FAJ Brain**"
        )

        st.caption(
            "Отдельный слой математической "
            "модели прогноза."
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    init_state()

    render_header()

    db = get_database()

    # --------------------------------------------------------
    # TOURNAMENT (из FAJ_CLUB_RATINGS)
    # --------------------------------------------------------

    st.subheader(
        "1. Турнир"
    )

    tournaments = get_all_tournaments()

    tournament = st.selectbox(
        "Выберите турнир",
        tournaments,
        index=(
            tournaments.index(
                st.session_state.faj_competition
            )
            if st.session_state.faj_competition
            in tournaments
            else 0
        ),
    )

    if (
        st.session_state.faj_competition
        != tournament
    ):

        st.session_state.faj_competition = (
            tournament
        )

        st.session_state.faj_session_id = None

    st.caption(
        "Турнир определяет список команд. "
        "Исторические матчи можно брать "
        "из любых соревнований."
    )

    # --------------------------------------------------------
    # TEAMS (из FAJ_CLUB_RATINGS, НЕ из БД)
    # --------------------------------------------------------

    team_names = load_teams(db, tournament)

    if not team_names:

        st.warning(
            f"В реестре FAJ пока нет команд "
            f"для турнира «{tournament}»."
        )

        return

    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

    st.subheader(
        "2. Матчи для анализа"
    )

    st.caption(
        "Можно одновременно подготовить "
        f"до {MAX_ANALYSIS_MATCHES} матчей."
    )

    if not st.session_state.faj_matches:

        add_match()

    for index, match in enumerate(
        st.session_state.faj_matches
    ):

        with st.container(
            border=True
        ):

            render_match_setup(
                index=index,
                match=match,
                team_names=team_names,
            )

            if len(
                st.session_state.faj_matches
            ) > 1:

                if st.button(
                    "Удалить этот матч",
                    key=f"remove_{index}",
                ):

                    remove_match(
                        index
                    )

                    st.rerun()

    # --------------------------------------------------------
    # ADD MATCH
    # --------------------------------------------------------

    if len(
        st.session_state.faj_matches
    ) < MAX_ANALYSIS_MATCHES:

        if st.button(
            "＋ Добавить матч",
            use_container_width=True,
        ):

            add_match()

            st.rerun()

    # --------------------------------------------------------
    # WORKFLOW
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "Как работает FAJ"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.markdown(
            "**① Выбор**"
        )

        st.caption(
            "Выбираете турнир и пары команд."
        )

    with c2:

        st.markdown(
            "**② Данные**"
        )

        st.caption(
            "Даете FAJ историю матчей."
        )

    with c3:

        st.markdown(
            "**③ Анализ**"
        )

        st.caption(
            "FAJ обрабатывает факты."
        )

    with c4:

        st.markdown(
            "**④ Прогноз**"
        )

        st.caption(
            "Получаете готовую карточку."
        )

    render_source_info()

    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

    st.divider()

    if st.button(
        "♻️ Начать новый анализ",
        use_container_width=True,
    ):

        reset_workspace()

        st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
