#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PERSONAL PREDICTOR
======================

Единая рабочая страница персональной аналитической платформы FAJ.

Назначение:

    1. Выбрать турнир.
    2. Выбрать одну или несколько пар команд.
    3. Для каждой пары собрать историю матчей.
    4. Использовать Soccer365 как основной ручной источник.
    5. В дальнейшем подключить Data Football API.
    6. Передать собранные данные в новые прогнозные мозги FAJ.
    7. Получить красивую карточку прогноза.

ВАЖНО:

Эта страница НЕ содержит старую архитектуру:

    - Tour Manager
    - Import Facts
    - ETC
    - Learning
    - Rating Evolution
    - Round Management
    - Match Manager старой версии

Страница является пользовательским интерфейсом
новой персональной аналитической FAJ.

Минимум для расширенного анализа:
    3 исторических матча.

Допускается:
    1-2 матча — ускоренный / ограниченный анализ.

История может быть собрана из любых турниров:
    - лига
    - кубок
    - еврокубок
    - товарищеский матч

Главный принцип:

    ДАННЫЕ → АНАЛИТИКА → ПРОГНОЗ

Никакого обучения FAJ здесь нет.
"""

from __future__ import annotations

import json
import logging
import math
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.database import FAJDatabase
from app.parsers.soccer365_parser import Soccer365Parser


# ============================================================
# CONFIG
# ============================================================

PAGE_TITLE = "FAJ — Персональный прогноз"

MODEL_VERSION = "FAJ-PERSONAL-0.1"

LEAGUES = [
    "РПЛ",
    "АПЛ",
    "Ла Лига",
    "Лига чемпионов",
]

MIN_EXTENDED_MATCHES = 3
MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6


logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()


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


def pct(value: Optional[float]) -> str:
    if value is None:
        return "—"

    return f"{value * 100:.1f}%"


def number(
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

    text = str(score).replace("-", ":")

    if ":" not in text:
        return None, None

    left, right = text.split(":", 1)

    try:
        return int(left.strip()), int(right.strip())
    except ValueError:
        return None, None


# ============================================================
# TEAM LOADING
# ============================================================

def load_teams(
    db: FAJDatabase,
) -> List[Dict[str, Any]]:

    try:
        teams = db.get_teams()

        if not teams:
            return []

        return teams

    except Exception as exc:

        logger.exception(
            "Cannot load teams: %s",
            exc,
        )

        return []


# ============================================================
# TEAM OPTIONS
# ============================================================

def team_label(
    team: Dict[str, Any],
) -> str:

    name = team.get("name", "Команда")

    league = team.get("league")

    if league:
        return f"{name} · {league}"

    return str(name)


def build_team_map(
    teams: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:

    result = {}

    for team in teams:

        name = str(
            team.get("name", "")
        )

        if not name:
            continue

        result[name] = team

    return result


# ============================================================
# SESSION STATE
# ============================================================

def init_state() -> None:

    defaults = {

        "faj_matches": [],

        "faj_session_id": None,

        "faj_collected": {},

        "faj_predictions": {},

        "faj_last_collection": None,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================
# MATCH MANAGEMENT
# ============================================================

def add_match_slot() -> None:

    if len(
        st.session_state.faj_matches
    ) >= MAX_ANALYSIS_MATCHES:

        return

    st.session_state.faj_matches.append(
        {
            "home_id": None,
            "away_id": None,
            "urls": [],
        }
    )


def remove_match_slot(
    index: int,
) -> None:

    matches = st.session_state.faj_matches

    if 0 <= index < len(matches):

        matches.pop(index)

        st.session_state.faj_collected.pop(
            index,
            None,
        )

        st.session_state.faj_predictions.pop(
            index,
            None,
        )


def ensure_match_slot() -> None:

    if not st.session_state.faj_matches:

        add_match_slot()


# ============================================================
# SESSION CREATION
# ============================================================

def create_session_if_needed(
    db: FAJDatabase,
    competition_name: str,
) -> Optional[int]:

    existing = (
        st.session_state.faj_session_id
    )

    if existing:
        return existing

    try:

        session_id = db.create_analysis_session(
            competition_id=None,
            title=(
                f"FAJ | {competition_name}"
            ),
            notes=(
                "Персональная аналитическая "
                "сессия FAJ."
            ),
        )

        st.session_state.faj_session_id = (
            session_id
        )

        return session_id

    except Exception as exc:

        logger.exception(
            "Cannot create analysis session: %s",
            exc,
        )

        return None


# ============================================================
# SOCCER365
# ============================================================

@st.cache_resource
def get_soccer365_parser() -> Soccer365Parser:

    return Soccer365Parser()


def parse_soccer365_url(
    url: str,
) -> Dict[str, Any]:

    parser = get_soccer365_parser()

    return parser.parse(
        url.strip()
    )


# ============================================================
# MATCH VALIDATION
# ============================================================

def validate_history_match(
    parsed: Dict[str, Any],
    selected_team_name: str,
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
        selected_team_name
    )

    parsed_home = normalize_name(
        home
    )

    parsed_away = normalize_name(
        away
    )

    if (
        target != parsed_home
        and target != parsed_away
    ):

        return (
            False,
            (
                f"Матч {home} — {away} "
                f"не содержит выбранную команду "
                f"{selected_team_name}."
            ),
        )

    return (
        True,
        f"{home} — {away}",
    )


# ============================================================
# PARSED MATCH → ANALYTICAL RECORD
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

        "big_chances": {
            "home": stats.get(
                "home_big_chances"
            ),
            "away": stats.get(
                "away_big_chances"
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
# TEAM-SPECIFIC METRICS
# ============================================================

def team_side_record(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[str]:

    target = normalize_name(
        team_name
    )

    home = normalize_name(
        record.get("home_team")
    )

    away = normalize_name(
        record.get("away_team")
    )

    if target == home:
        return "home"

    if target == away:
        return "away"

    return None


def extract_team_values(
    records: List[Dict[str, Any]],
    team_name: str,
    metric: str,
) -> List[float]:

    values = []

    for record in records:

        side = team_side_record(
            record,
            team_name,
        )

        if side is None:
            continue

        group = record.get(
            metric,
            {},
        )

        value = safe_float(
            group.get(side)
        )

        if value is not None:
            values.append(value)

    return values


def average_or_none(
    values: List[float],
) -> Optional[float]:

    if not values:
        return None

    return mean(values)


# ============================================================
# HISTORY SUMMARY
# ============================================================

def build_history_summary(
    records: List[Dict[str, Any]],
    team_name: str,
) -> Dict[str, Any]:

    goals_for = (
        extract_team_values(
            records,
            team_name,
            "_goals_for_placeholder",
        )
    )

    # Goals are stored separately.
    goals_for = []
    goals_against = []

    wins = 0
    draws = 0
    losses = 0

    for record in records:

        side = team_side_record(
            record,
            team_name,
        )

        if side is None:
            continue

        gf = (
            record.get(
                "home_goals"
            )
            if side == "home"
            else record.get(
                "away_goals"
            )
        )

        ga = (
            record.get(
                "away_goals"
            )
            if side == "home"
            else record.get(
                "home_goals"
            )
        )

        if gf is not None:
            goals_for.append(
                gf
            )

        if ga is not None:
            goals_against.append(
                ga
            )

        if (
            gf is not None
            and ga is not None
        ):

            if gf > ga:
                wins += 1

            elif gf == ga:
                draws += 1

            else:
                losses += 1

    corners = extract_team_values(
        records,
        team_name,
        "corners",
    )

    cards = extract_team_values(
        records,
        team_name,
        "cards",
    )

    xg = extract_team_values(
        records,
        team_name,
        "xg",
    )

    shots = extract_team_values(
        records,
        team_name,
        "shots",
    )

    shots_on_target = (
        extract_team_values(
            records,
            team_name,
            "shots_on_target",
        )
    )

    possession = (
        extract_team_values(
            records,
            team_name,
            "possession",
        )
    )

    big_chances = (
        extract_team_values(
            records,
            team_name,
            "big_chances",
        )
    )

    return {

        "matches": len(records),

        "wins": wins,

        "draws": draws,

        "losses": losses,

        "goals_for_avg": average_or_none(
            goals_for
        ),

        "goals_against_avg": average_or_none(
            goals_against
        ),

        "xg_avg": average_or_none(
            xg
        ),

        "corners_avg": average_or_none(
            corners
        ),

        "cards_avg": average_or_none(
            cards
        ),

        "shots_avg": average_or_none(
            shots
        ),

        "shots_on_target_avg":
            average_or_none(
                shots_on_target
            ),

        "possession_avg":
            average_or_none(
                possession
            ),

        "big_chances_avg":
            average_or_none(
                big_chances
            ),
    }


# ============================================================
# MATCH AGGREGATES
# ============================================================

def match_totals(
    records: List[Dict[str, Any]],
    metric: str,
) -> List[float]:

    result = []

    for record in records:

        group = record.get(
            metric,
            {},
        )

        home = safe_float(
            group.get("home")
        )

        away = safe_float(
            group.get("away")
        )

        if (
            home is not None
            and away is not None
        ):

            result.append(
                home + away
            )

    return result


# ============================================================
# SAVE TO DATABASE
# ============================================================

def save_collected_history(
    db: FAJDatabase,
    session_id: int,
    match_id: int,
    home_team: Dict[str, Any],
    away_team: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> None:

    """
    Сохраняем собранную историю в новой персональной БД.

    Для каждого исторического матча:

        source
             ↓
        historical_match
             ↓
        historical_stats

    Данные сохраняются отдельно для каждой стороны.
    """

    for record in records:

        source_id = db.add_source(
            analysis_match_id=match_id,
            team_id=None,
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

        home_id = (
            home_team.get("id")
            if normalize_name(home_name)
            == normalize_name(
                home_team.get("name")
            )
            else away_team.get("id")
        )

        away_id = (
            away_team.get("id")
            if home_id == home_team.get("id")
            else home_team.get("id")
        )

        home_goals = record.get(
            "home_goals"
        )

        away_goals = record.get(
            "away_goals"
        )

        if (
            home_goals is not None
            and away_goals is not None
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

        stats = record.get(
            "stats",
            {},
        )

        # ----------------------------------------------------
        # HOME PERSPECTIVE
        # ----------------------------------------------------

        historical_id = (
            db.save_historical_match(
                analysis_match_id=match_id,
                team_id=home_id,
                opponent_team_id=away_id,
                source_id=source_id,
                match_date=None,
                is_home=True,
                goals_for=home_goals,
                goals_against=away_goals,
                result=home_result,
                external_match_id=None,
                raw_metadata={
                    "source": "Soccer365",
                    "source_url":
                        record.get(
                            "source_url"
                        ),
                },
            )
        )

        db.save_historical_stats(
            historical_id,
            {
                "possession":
                    record.get(
                        "possession",
                        {},
                    ).get("home"),

                "shots":
                    record.get(
                        "shots",
                        {},
                    ).get("home"),

                "shots_on_target":
                    record.get(
                        "shots_on_target",
                        {},
                    ).get("home"),

                "corners":
                    record.get(
                        "corners",
                        {},
                    ).get("home"),

                "fouls":
                    record.get(
                        "fouls",
                        {},
                    ).get("home"),

                "yellow_cards":
                    record.get(
                        "cards",
                        {},
                    ).get("home"),

                "xg":
                    record.get(
                        "xg",
                        {},
                    ).get("home"),

                "big_chances":
                    record.get(
                        "big_chances",
                        {},
                    ).get("home"),

                "passes":
                    record.get(
                        "passes",
                        {},
                    ).get("home"),

                "pass_accuracy":
                    record.get(
                        "pass_accuracy",
                        {},
                    ).get("home"),

                "tackles":
                    record.get(
                        "tackles",
                        {},
                    ).get("home"),
            },
        )

        # ----------------------------------------------------
        # AWAY PERSPECTIVE
        # ----------------------------------------------------

        historical_id = (
            db.save_historical_match(
                analysis_match_id=match_id,
                team_id=away_id,
                opponent_team_id=home_id,
                source_id=source_id,
                match_date=None,
                is_home=False,
                goals_for=away_goals,
                goals_against=home_goals,
                result=away_result,
                external_match_id=None,
                raw_metadata={
                    "source": "Soccer365",
                    "source_url":
                        record.get(
                            "source_url"
                        ),
                },
            )
        )

        db.save_historical_stats(
            historical_id,
            {
                "possession":
                    record.get(
                        "possession",
                        {},
                    ).get("away"),

                "shots":
                    record.get(
                        "shots",
                        {},
                    ).get("away"),

                "shots_on_target":
                    record.get(
                        "shots_on_target",
                        {},
                    ).get("away"),

                "corners":
                    record.get(
                        "corners",
                        {},
                    ).get("away"),

                "fouls":
                    record.get(
                        "fouls",
                        {},
                    ).get("away"),

                "yellow_cards":
                    record.get(
                        "cards",
                        {},
                    ).get("away"),

                "xg":
                    record.get(
                        "xg",
                        {},
                    ).get("away"),

                "big_chances":
                    record.get(
                        "big_chances",
                        {},
                    ).get("away"),

                "passes":
                    record.get(
                        "passes",
                        {},
                    ).get("away"),

                "pass_accuracy":
                    record.get(
                        "pass_accuracy",
                        {},
                    ).get("away"),

                "tackles":
                    record.get(
                        "tackles",
                        {},
                    ).get("away"),
            },
        )


# ============================================================
# TEMPORARY PREDICTION CONTRACT
# ============================================================

def build_prediction(
    home_team: str,
    away_team: str,
    history_home: List[Dict[str, Any]],
    history_away: List[Dict[str, Any]],
) -> Dict[str, Any]:

    """
    ВРЕМЕННЫЙ КОНТРАК.

    Здесь пока НЕ находится финальная формула FAJ.

    Следующим этапом эта функция будет заменена
    настоящими прогнозными мозгами.

    Важно:

    UI уже сейчас ожидает конечную структуру результата.
    Поэтому заменять интерфейс после создания модели
    не потребуется.
    """

    home_summary = build_history_summary(
        history_home,
        home_team,
    )

    away_summary = build_history_summary(
        history_away,
        away_team,
    )

    home_goals = (
        home_summary["goals_for_avg"]
        or 0.0
    )

    away_goals = (
        away_summary["goals_for_avg"]
        or 0.0
    )

    home_concede = (
        home_summary["goals_against_avg"]
        or 0.0
    )

    away_concede = (
        away_summary["goals_against_avg"]
        or 0.0
    )

    # --------------------------------------------------------
    # VERY SIMPLE PLACEHOLDER
    #
    # НЕ ЯВЛЯЕТСЯ ФИНАЛЬНОЙ МОДЕЛЬЮ FAJ.
    # --------------------------------------------------------

    expected_home = (
        home_goals + away_concede
    ) / 2

    expected_away = (
        away_goals + home_concede
    ) / 2

    total = (
        expected_home
        + expected_away
    )

    if total <= 0:
        total = 1.0

    home_strength = (
        expected_home / total
    )

    away_strength = (
        expected_away / total
    )

    draw_strength = 0.25

    raw_home = (
        home_strength
        + 0.15
    )

    raw_away = (
        away_strength
    )

    raw_draw = draw_strength

    denominator = (
        raw_home
        + raw_draw
        + raw_away
    )

    home_probability = (
        raw_home / denominator
    )

    draw_probability = (
        raw_draw / denominator
    )

    away_probability = (
        raw_away / denominator
    )

    btts_probability = (
        min(
            0.95,
            max(
                0.05,
                (
                    min(
                        expected_home / 1.5,
                        1.0,
                    )
                    *
                    min(
                        expected_away / 1.5,
                        1.0,
                    )
                ),
            ),
        )
    )

    over25_probability = min(
        0.95,
        max(
            0.05,
            total / 4.0,
        ),
    )

    over35_probability = min(
        0.90,
        max(
            0.03,
            (total - 1.5) / 3.0,
        ),
    )

    corners_home = (
        average_or_none(
            extract_team_values(
                history_home,
                home_team,
                "corners",
            )
        )
        or 0.0
    )

    corners_away = (
        average_or_none(
            extract_team_values(
                history_away,
                away_team,
                "corners",
            )
        )
        or 0.0
    )

    cards_home = (
        average_or_none(
            extract_team_values(
                history_home,
                home_team,
                "cards",
            )
        )
        or 0.0
    )

    cards_away = (
        average_or_none(
            extract_team_values(
                history_away,
                away_team,
                "cards",
            )
        )
        or 0.0
    )

    corners_total = (
        corners_home
        + corners_away
    )

    cards_total = (
        cards_home
        + cards_away
    )

    score_home = round(
        expected_home
    )

    score_away = round(
        expected_away
    )

    score = (
        f"{score_home}:{score_away}"
    )

    return {

        "model_version":
            MODEL_VERSION,

        "home_team":
            home_team,

        "away_team":
            away_team,

        "home_win_probability":
            home_probability,

        "draw_probability":
            draw_probability,

        "away_win_probability":
            away_probability,

        "confidence":
            max(
                home_probability,
                draw_probability,
                away_probability,
            ),

        "risk":
            (
                "НИЗКИЙ"
                if max(
                    home_probability,
                    draw_probability,
                    away_probability,
                ) >= 0.60
                else "СРЕДНИЙ"
                if max(
                    home_probability,
                    draw_probability,
                    away_probability,
                ) >= 0.48
                else "ВЫСОКИЙ"
            ),

        "btts":
            (
                "ДА"
                if btts_probability >= 0.50
                else "НЕТ"
            ),

        "btts_probability":
            btts_probability,

        "over25":
            (
                "ДА"
                if over25_probability >= 0.50
                else "НЕТ"
            ),

        "over25_probability":
            over25_probability,

        "over35":
            (
                "ДА"
                if over35_probability >= 0.50
                else "НЕТ"
            ),

        "over35_probability":
            over35_probability,

        "expected_goals":
            total,

        "home_expected_goals":
            expected_home,

        "away_expected_goals":
            expected_away,

        "scores": [
            score,
            f"{max(0, score_home - 1)}:{score_away}",
            f"{score_home}:{max(0, score_away - 1)}",
        ],

        "corners_total":
            corners_total,

        "corners_home":
            corners_home,

        "corners_away":
            corners_away,

        "cards_total":
            cards_total,

        "cards_home":
            cards_home,

        "cards_away":
            cards_away,

        "corners_over": {
            "7.5":
                min(
                    0.95,
                    corners_total / 12,
                ),
            "8.5":
                min(
                    0.95,
                    corners_total / 13,
                ),
            "9.5":
                min(
                    0.95,
                    corners_total / 14,
                ),
            "10.5":
                min(
                    0.95,
                    corners_total / 15,
                ),
        },

        "cards_over": {
            "2.5":
                min(
                    0.95,
                    cards_total / 5,
                ),
            "3.5":
                min(
                    0.95,
                    cards_total / 6,
                ),
            "4.5":
                min(
                    0.95,
                    cards_total / 7,
                ),
        },

        "analysis":
            (
                f"Предварительный расчёт FAJ "
                f"видит сценарий {score}. "
                f"Средняя результативность "
                f"истории: "
                f"{total:.2f} гола за матч."
            ),

        "data_status":
            {
                "home_matches":
                    len(history_home),

                "away_matches":
                    len(history_away),

                "extended":
                    (
                        len(history_home)
                        >= MIN_EXTENDED_MATCHES
                        and
                        len(history_away)
                        >= MIN_EXTENDED_MATCHES
                    ),
            },
    }


# ============================================================
# PREDICTION CARD
# ============================================================

def render_prediction_card(
    prediction: Dict[str, Any],
) -> None:

    st.markdown(
        """
        <div style="
            border:1px solid rgba(128,128,128,.25);
            border-radius:18px;
            padding:24px;
            margin:20px 0;
            background:rgba(128,128,128,.04);
        ">
        """,
        unsafe_allow_html=True,
    )

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
        <h2 style="text-align:center;">
            {home} — {away}
        </h2>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # 1. MAIN OUTCOME
    # ========================================================

    st.markdown(
        "### 1. Главный исход"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "🏠 Победа хозяев",
        pct(
            prediction.get(
                "home_win_probability"
            )
        ),
    )

    c2.metric(
        "🤝 Ничья",
        pct(
            prediction.get(
                "draw_probability"
            )
        ),
    )

    c3.metric(
        "✈️ Победа гостей",
        pct(
            prediction.get(
                "away_win_probability"
            )
        ),
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Уверенность FAJ",
        pct(
            prediction.get(
                "confidence"
            )
        ),
    )

    c2.metric(
        "Риск",
        prediction.get(
            "risk",
            "—",
        ),
    )

    # ========================================================
    # 2. GOALS
    # ========================================================

    st.markdown(
        "### 2. Голы"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Обе забьют",
        prediction.get(
            "btts",
            "—",
        ),
    )

    c2.metric(
        "ТБ 2.5",
        prediction.get(
            "over25",
            "—",
        ),
    )

    c3.metric(
        "ТБ 3.5",
        prediction.get(
            "over35",
            "—",
        ),
    )

    st.markdown(
        "**Три наиболее вероятных счёта**"
    )

    scores = prediction.get(
        "scores",
        [],
    )

    if scores:

        cols = st.columns(
            min(
                len(scores),
                3,
            )
        )

        for index, score in enumerate(
            scores[:3]
        ):

            cols[index].metric(
                f"#{index + 1}",
                score,
            )

    # ========================================================
    # 3. CORNERS
    # ========================================================

    st.markdown(
        "### 3. Угловые"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Всего",
        number(
            prediction.get(
                "corners_total"
            )
        ),
    )

    c2.metric(
        "Хозяева",
        number(
            prediction.get(
                "corners_home"
            )
        ),
    )

    c3.metric(
        "Гости",
        number(
            prediction.get(
                "corners_away"
            )
        ),
    )

    corners = prediction.get(
        "corners_over",
        {},
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "ТБ 7.5",
        pct(
            corners.get("7.5")
        ),
    )

    c2.metric(
        "ТБ 8.5",
        pct(
            corners.get("8.5")
        ),
    )

    c3.metric(
        "ТБ 9.5",
        pct(
            corners.get("9.5")
        ),
    )

    c4.metric(
        "ТБ 10.5",
        pct(
            corners.get("10.5")
        ),
    )

    # ========================================================
    # 4. CARDS
    # ========================================================

    st.markdown(
        "### 4. Карточки"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Всего",
        number(
            prediction.get(
                "cards_total"
            )
        ),
    )

    c2.metric(
        "Хозяева",
        number(
            prediction.get(
                "cards_home"
            )
        ),
    )

    c3.metric(
        "Гости",
        number(
            prediction.get(
                "cards_away"
            )
        ),
    )

    cards = prediction.get(
        "cards_over",
        {},
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "ТБ 2.5",
        pct(
            cards.get("2.5")
        ),
    )

    c2.metric(
        "ТБ 3.5",
        pct(
            cards.get("3.5")
        ),
    )

    c3.metric(
        "ТБ 4.5",
        pct(
            cards.get("4.5")
        ),
    )

    # ========================================================
    # 5. ANALYTICAL CONCLUSION
    # ========================================================

    st.markdown(
        "### 5. Аналитический вывод FAJ"
    )

    st.info(
        prediction.get(
            "analysis",
            "Анализ пока недоступен.",
        )
    )

    # ========================================================
    # DATA SOURCE
    # ========================================================

    status = prediction.get(
        "data_status",
        {},
    )

    st.caption(
        "Данные: "
        f"{status.get('home_matches', 0)} "
        "матчей хозяев + "
        f"{status.get('away_matches', 0)} "
        "матчей гостей. "
        "Расширенный режим: "
        + (
            "ДА"
            if status.get(
                "extended"
            )
            else "НЕТ"
        )
    )

    st.markdown(
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# HISTORY UI
# ============================================================

def render_history_summary(
    records: List[Dict[str, Any]],
    home_team: str,
    away_team: str,
) -> None:

    st.markdown(
        "### Собранная история"
    )

    if not records:

        st.info(
            "Исторические матчи ещё не собраны."
        )

        return

    home_summary = (
        build_history_summary(
            records,
            home_team,
        )
    )

    away_summary = (
        build_history_summary(
            records,
            away_team,
        )
    )

    c1, c2 = st.columns(2)

    with c1:

        st.markdown(
            f"**{home_team}**"
        )

        st.write(
            f"Матчей: {home_summary['matches']}"
        )

        st.write(
            f"Победы: {home_summary['wins']} · "
            f"Ничьи: {home_summary['draws']} · "
            f"Поражения: {home_summary['losses']}"
        )

        st.write(
            "Голы: "
            f"{number(home_summary['goals_for_avg'])} "
            "за матч"
        )

        st.write(
            "Угловые: "
            f"{number(home_summary['corners_avg'])}"
        )

        st.write(
            "Карточки: "
            f"{number(home_summary['cards_avg'])}"
        )

    with c2:

        st.markdown(
            f"**{away_team}**"
        )

        st.write(
            f"Матчей: {away_summary['matches']}"
        )

        st.write(
            f"Победы: {away_summary['wins']} · "
            f"Ничьи: {away_summary['draws']} · "
            f"Поражения: {away_summary['losses']}"
        )

        st.write(
            "Голы: "
            f"{number(away_summary['goals_for_avg'])} "
            "за матч"
        )

        st.write(
            "Угловые: "
            f"{number(away_summary['corners_avg'])}"
        )

        st.write(
            "Карточки: "
            f"{number(away_summary['cards_avg'])}"
        )


# ============================================================
# COLLECTION
# ============================================================

def collect_match_history(
    index: int,
    db: FAJDatabase,
    session_id: Optional[int],
    match_id: int,
    home_team: Dict[str, Any],
    away_team: Dict[str, Any],
    urls: List[str],
) -> None:

    clean_urls = [
        url.strip()
        for url in urls
        if url and url.strip()
    ]

    if not clean_urls:

        st.warning(
            "Добавьте хотя бы одну ссылку Soccer365."
        )

        return

    if len(clean_urls) > MAX_HISTORY_MATCHES:

        clean_urls = clean_urls[
            :MAX_HISTORY_MATCHES
        ]

    home_name = home_team.get(
        "name",
        "",
    )

    away_name = away_team.get(
        "name",
        "",
    )

    records = []

    progress = st.progress(
        0
    )

    status = st.empty()

    for position, url in enumerate(
        clean_urls,
        start=1,
    ):

        status.info(
            f"Обрабатываю матч {position} "
            f"из {len(clean_urls)}..."
        )

        parsed = parse_soccer365_url(
            url
        )

        if parsed.get("error"):

            st.error(
                f"Ошибка Soccer365: "
                f"{parsed.get('error')}"
            )

            progress.progress(
                position / len(clean_urls)
            )

            continue

        parsed_match = build_history_record(
            parsed
        )

        # ----------------------------------------------------
        # URL должен содержать хотя бы одну
        # выбранную команду.
        # ----------------------------------------------------

        valid_home, _ = (
            validate_history_match(
                parsed_match,
                home_name,
            )
        )

        valid_away, _ = (
            validate_history_match(
                parsed_match,
                away_name,
            )
        )

        if not valid_home and not valid_away:

            st.warning(
                "Пропущен матч "
                f"{parsed_match.get('home_team')} — "
                f"{parsed_match.get('away_team')}: "
                "ни одна выбранная команда "
                "не найдена."
            )

            progress.progress(
                position / len(clean_urls)
            )

            continue

        records.append(
            parsed_match
        )

        progress.progress(
            position / len(clean_urls)
        )

    status.empty()

    if not records:

        st.error(
            "Не удалось получить ни одного "
            "корректного исторического матча."
        )

        return

    # --------------------------------------------------------
    # SAVE IN SESSION
    # --------------------------------------------------------

    st.session_state.faj_collected[
        index
    ] = records

    # --------------------------------------------------------
    # SAVE IN DATABASE
    # --------------------------------------------------------

    if session_id and match_id:

        try:

            save_collected_history(
                db=db,
                session_id=session_id,
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                records=records,
            )

        except Exception as exc:

            logger.exception(
                "History save error: %s",
                exc,
            )

            st.warning(
                "Данные собраны, "
                "но не удалось полностью "
                f"сохранить их в БД: {exc}"
            )

    st.success(
        f"Собрано матчей: {len(records)}"
    )


# ============================================================
# MATCH BLOCK
# ============================================================

def render_match_block(
    index: int,
    db: FAJDatabase,
    teams: List[Dict[str, Any]],
    competition_name: str,
) -> None:

    matches = (
        st.session_state.faj_matches
    )

    if index >= len(matches):
        return

    match = matches[index]

    team_names = [
        team.get("name", "")
        for team in teams
        if team.get("name")
    ]

    team_map = build_team_map(
        teams
    )

    current_home = match.get(
        "home_id"
    )

    current_away = match.get(
        "away_id"
    )

    home_name = None
    away_name = None

    if current_home:

        team = db.get_team(
            current_home
        )

        if team:
            home_name = team.get(
                "name"
            )

    if current_away:

        team = db.get_team(
            current_away
        )

        if team:
            away_name = team.get(
                "name"
            )

    title = (
        f"Матч {index + 1}"
    )

    if home_name and away_name:

        title = (
            f"{home_name} — {away_name}"
        )

    with st.expander(
        title,
        expanded=True,
    ):

        c1, c2 = st.columns(2)

        with c1:

            selected_home = st.selectbox(
                "Хозяева",
                team_names,
                index=(
                    team_names.index(
                        home_name
                    )
                    if home_name in team_names
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
                "Гости",
                available_away,
                index=(
                    available_away.index(
                        away_name
                    )
                    if away_name in available_away
                    else 0
                ),
                key=f"away_{index}",
            )

        home_team = team_map[
            selected_home
        ]

        away_team = team_map[
            selected_away
        ]

        match["home_id"] = (
            home_team.get("id")
        )

        match["away_id"] = (
            away_team.get("id")
        )

        st.markdown(
            "---"
        )

        st.markdown(
            "#### История команд"
        )

        st.caption(
            "Можно использовать матчи "
            "из любых турниров. "
            "Для расширенного анализа "
            "рекомендуется минимум 3 матча "
            "на каждую команду."
        )

        url_values = match.get(
            "urls",
            [],
        )

        urls = []

        for position in range(
            MAX_HISTORY_MATCHES
        ):

            default = (
                url_values[position]
                if position < len(
                    url_values
                )
                else ""
            )

            url = st.text_input(
                f"Soccer365 — исторический матч "
                f"{position + 1}",
                value=default,
                placeholder=(
                    "https://soccer365.ru/games/..."
                ),
                key=(
                    f"url_{index}_{position}"
                ),
            )

            urls.append(
                url
            )

        match["urls"] = urls

        session_id = (
            st.session_state.faj_session_id
        )

        # ----------------------------------------------------
        # Create analysis match when both teams chosen.
        # ----------------------------------------------------

        if session_id:

            if not match.get(
                "analysis_match_id"
            ):

                try:

                    match[
                        "analysis_match_id"
                    ] = db.add_analysis_match(
                        session_id=session_id,
                        home_team_id=
                            home_team.get("id"),
                        away_team_id=
                            away_team.get("id"),
                    )

                except Exception as exc:

                    st.error(
                        "Не удалось создать "
                        f"аналитический матч: {exc}"
                    )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "📥 Собрать статистику",
                key=f"collect_{index}",
                use_container_width=True,
            ):

                collect_match_history(
                    index=index,
                    db=db,
                    session_id=session_id,
                    match_id=match.get(
                        "analysis_match_id"
                    ),
                    home_team=home_team,
                    away_team=away_team,
                    urls=urls,
                )

        with c2:

            if st.button(
                "🧠 Получить прогноз",
                key=f"predict_{index}",
                use_container_width=True,
            ):

                records = (
                    st.session_state
                    .faj_collected
                    .get(
                        index,
                        [],
                    )
                )

                if not records:

                    st.warning(
                        "Сначала соберите "
                        "исторические данные."
                    )

                else:

                    home_history = [
                        record
                        for record in records
                        if team_side_record(
                            record,
                            selected_home,
                        )
                        is not None
                    ]

                    away_history = [
                        record
                        for record in records
                        if team_side_record(
                            record,
                            selected_away,
                        )
                        is not None
                    ]

                    prediction = (
                        build_prediction(
                            selected_home,
                            selected_away,
                            home_history,
                            away_history,
                        )
                    )

                    st.session_state\
                        .faj_predictions[
                            index
                        ] = prediction

                    # ------------------------------------------------
                    # SAVE PREDICTION
                    # ------------------------------------------------

                    try:

                        if match.get(
                            "analysis_match_id"
                        ):

                            db.save_prediction(
                                analysis_match_id=
                                    match[
                                        "analysis_match_id"
                                    ],
                                prediction=
                                    prediction,
                                model_version=
                                    MODEL_VERSION,
                            )

                    except Exception as exc:

                        logger.exception(
                            "Prediction save error: %s",
                            exc,
                        )

                        st.warning(
                            "Прогноз рассчитан, "
                            "но не сохранён в БД: "
                            f"{exc}"
                        )

        # ----------------------------------------------------
        # HISTORY
        # ----------------------------------------------------

        records = (
            st.session_state
            .faj_collected
            .get(
                index,
                [],
            )
        )

        if records:

            render_history_summary(
                records,
                selected_home,
                selected_away,
            )

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        prediction = (
            st.session_state
            .faj_predictions
            .get(
                index
            )
        )

        if prediction:

            render_prediction_card(
                prediction
            )

        # ----------------------------------------------------
        # REMOVE
        # ----------------------------------------------------

        if len(
            st.session_state.faj_matches
        ) > 1:

            if st.button(
                "Удалить этот матч",
                key=f"remove_{index}",
            ):

                remove_match_slot(
                    index
                )

                st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    init_state()

    ensure_match_slot()

    db = get_database()

    # ========================================================
    # HEADER
    # ========================================================

    st.title(
        "⚽ FAJ"
    )

    st.subheader(
        "Персональная футбольная аналитика"
    )

    st.caption(
        "Выберите матч → соберите историю → "
        "получите прогноз."
    )

    st.markdown(
        "---"
    )

    # ========================================================
    # COMPETITION
    # ========================================================

    st.markdown(
        "## 1. Турнир"
    )

    competition = st.selectbox(
        "Выберите турнир",
        LEAGUES,
        key="faj_competition",
    )

    st.caption(
        "История матчей может быть собрана "
        "из любого турнира. Выбранный здесь "
        "турнир определяет только текущий "
        "контекст прогноза."
    )

    # ========================================================
    # CREATE SESSION
    # ========================================================

    session_id = create_session_if_needed(
        db,
        competition,
    )

    if session_id:

        st.caption(
            f"Аналитическая сессия №{session_id}"
        )

    # ========================================================
    # MATCHES
    # ========================================================

    st.markdown(
        "## 2. Матчи для анализа"
    )

    st.info(
        "Можно анализировать от 1 до 6 матчей "
        "за один запуск."
    )

    teams = load_teams(
        db
    )

    if not teams:

        st.error(
            "В базе FAJ нет команд."
        )

        st.stop()

    for index in range(
        len(
            st.session_state.faj_matches
        )
    ):

        render_match_block(
            index=index,
            db=db,
            teams=teams,
            competition_name=competition,
        )

    # ========================================================
    # ADD MATCH
    # ========================================================

    if len(
        st.session_state.faj_matches
    ) < MAX_ANALYSIS_MATCHES:

        if st.button(
            "＋ Добавить ещё матч",
            use_container_width=True,
        ):

            add_match_slot()

            st.rerun()

    # ========================================================
    # FOOTER
    # ========================================================

    st.markdown(
        "---"
    )

    st.caption(
        f"FAJ Personal Predictor · "
        f"{MODEL_VERSION}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
