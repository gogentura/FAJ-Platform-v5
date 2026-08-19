#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
IMPORT FACTS v3.3
============================================================

Назначение:
    Импорт фактических данных сыгранного матча/тура.

Источник:
    NB-BET через NbBetStatsParser.

ЦЕПОЧКА:
    MATCH
      ↓
    NB-BET URL
      ↓
    NbBetStatsParser
      ↓
    RESULT + STATISTICS
      ↓
    FAJ PREDICTION
      ↓
    EXPERT PREDICTION
      ↓
    VALIDATION
      ↓
    GOLD
      ↓
    LOCK
      ↓
    LEARNING

ПРИНЦИПЫ:
    SQLite only
    database.py — единственный источник записи в БД
    Никаких DELETE
    Никаких DROP
    Старые прогнозы не изменяются
    Факт отделён от прогноза
    Expert отделён от FAJ
    None != 0

ВАЖНО:
    Parser может вернуть None.
    None означает отсутствие данных.
    None никогда автоматически не превращается в 0.
============================================================
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.database import FAJDatabase
from app.parsers.nb_bet_stats_parser import NbBetStatsParser
from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
IMPORT_FACTS_VERSION = "3.3"
MODEL_VERSION = "v12.1"
PARSER_VERSION = "nb-bet-v4.0"

DEFAULT_DB_PATH = "data/faj.db"

LEAGUES = {
    "РПЛ": "РПЛ",
    "АПЛ": "АПЛ",
    "Ла Лига": "Ла Лига",
    "Лига чемпионов": "Лига чемпионов",
}


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    """
    Единая точка получения database.py.
    Схема и операции записи находятся только
    в app.database.
    """
    return FAJDatabase()


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(
            str(value)
            .strip()
            .replace(",", ".")
        )
    except (TypeError, ValueError):
        return None


def clean_score(value: Any) -> Optional[str]:
    """
    Приводит счёт к X:Y.
    Никаких предположений.
    """
    if value is None:
        return None

    text = str(value).strip()

    match = re.search(
        r"(?<!\d)(\d{1,2})\s*[:\-]\s*(\d{1,2})(?!\d)",
        text,
    )

    if not match:
        return None

    home = safe_int(match.group(1))
    away = safe_int(match.group(2))

    if home is None or away is None:
        return None

    if home < 0 or away < 0:
        return None

    if home > 15 or away > 15:
        return None

    return f"{home}:{away}"


def score_to_tuple(
    score: Any,
) -> Tuple[Optional[int], Optional[int]]:
    normalized = clean_score(score)
    if normalized is None:
        return None, None

    home, away = normalized.split(":")
    return (
        safe_int(home),
        safe_int(away),
    )


def winner_from_score(
    home_goals: Optional[int],
    away_goals: Optional[int],
) -> Optional[str]:
    if home_goals is None or away_goals is None:
        return None

    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def btts_from_score(
    home_goals: Optional[int],
    away_goals: Optional[int],
) -> Optional[int]:
    if home_goals is None or away_goals is None:
        return None
    return int(
        home_goals > 0
        and away_goals > 0
    )


def over25_from_score(
    home_goals: Optional[int],
    away_goals: Optional[int],
) -> Optional[int]:
    if home_goals is None or away_goals is None:
        return None
    return int(
        home_goals + away_goals > 2
    )


def over35_from_score(
    home_goals: Optional[int],
    away_goals: Optional[int],
) -> Optional[int]:
    if home_goals is None or away_goals is None:
        return None
    return int(
        home_goals + away_goals > 3
    )


def object_to_dict(
    value: Any,
) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        pass
    if hasattr(value, "__dict__"):
        try:
            return dict(value.__dict__)
        except Exception:
            pass
    return {}


# ============================================================
# DATABASE METHOD COMPATIBILITY
# ============================================================

def _call_first(
    obj: Any,
    method_names: List[str],
    *args,
    **kwargs,
) -> Any:
    for name in method_names:
        method = getattr(
            obj,
            name,
            None,
        )
        if not callable(method):
            continue

        try:
            return method(
                *args,
                **kwargs,
            )
        except TypeError:
            continue
        except Exception as exc:
            logger.warning(
                "database method %s failed: %s",
                name,
                exc,
            )
            continue

    return None


# ============================================================
# MATCH ACCESS
# ============================================================

def get_round_matches(
    db: FAJDatabase,
    round_number: int,
) -> List[Dict[str, Any]]:
    """
    Получает матчи тура.
    Сначала используем API database.py.
    SQL fallback только READ-ONLY.
    """
    result = _call_first(
        db,
        [
            "get_matches_by_round",
            "get_round_matches",
            "get_matches_for_round",
            "get_matches_by_round_number",
        ],
        round_number,
    )

    if result is not None:
        matches: List[Dict[str, Any]] = []
        for item in result:
            data = object_to_dict(item)
            if data:
                matches.append(data)
        return matches

    conn = None
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM rounds
            WHERE round_number = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (round_number,),
        )

        round_row = cursor.fetchone()
        if not round_row:
            return []

        round_data = object_to_dict(
            round_row
        )

        round_id = (
            round_data.get("id")
            or round_data.get("round_id")
        )

        if round_id is None:
            return []

        cursor.execute(
            """
            SELECT
                m.*,
                th.name AS home_team_name,
                ta.name AS away_team_name
            FROM matches m
            LEFT JOIN teams th
                ON th.id = m.home_team_id
            LEFT JOIN teams ta
                ON ta.id = m.away_team_id
            WHERE m.round_id = ?
            ORDER BY m.id
            """,
            (round_id,),
        )

        rows = cursor.fetchall()
        return [
            object_to_dict(row)
            for row in rows
        ]

    except Exception as exc:
        logger.exception(
            "Ошибка получения матчей тура %s",
            round_number,
        )
        return []

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# MATCH DATA
# ============================================================

def get_match_id(
    match: Dict[str, Any],
) -> Optional[Any]:
    for key in (
        "id",
        "match_id",
        "uuid",
    ):
        value = match.get(key)
        if value is not None:
            return value
    return None


def get_home_team(
    match: Dict[str, Any],
) -> str:
    for key in (
        "home_team_name",
        "home_team",
        "home_name",
    ):
        value = match.get(key)
        if value:
            return str(value)
    return "Неизвестно"


def get_away_team(
    match: Dict[str, Any],
) -> str:
    for key in (
        "away_team_name",
        "away_team",
        "away_name",
    ):
        value = match.get(key)
        if value:
            return str(value)
    return "Неизвестно"


def get_match_date(
    match: Dict[str, Any],
) -> Optional[str]:
    for key in (
        "match_date",
        "date",
        "scheduled_at",
        "kickoff",
    ):
        value = match.get(key)
        if value:
            return str(value)[:10]
    return None


# ============================================================
# PREDICTION
# ============================================================

def extract_prediction_score(
    prediction: Dict[str, Any],
) -> Optional[str]:
    for key in (
        "predicted_score",
        "score",
        "faj_score",
        "most_likely_score",
        "prediction_score",
        "exact_score",
    ):
        score = clean_score(
            prediction.get(key)
        )
        if score:
            return score

    home = None
    away = None

    for key in (
        "predicted_home_goals",
        "expected_home_goals",
        "faj_home_goals",
        "home_xg",
    ):
        if prediction.get(key) is not None:
            home = safe_float(
                prediction.get(key)
            )
            break

    for key in (
        "predicted_away_goals",
        "expected_away_goals",
        "faj_away_goals",
        "away_xg",
    ):
        if prediction.get(key) is not None:
            away = safe_float(
                prediction.get(key)
            )
            break

    if home is None or away is None:
        return None

    if home < 0 or away < 0:
        return None

    return (
        f"{round(home):d}:"
        f"{round(away):d}"
    )


def prediction_probability(
    prediction: Dict[str, Any],
    side: str,
) -> Optional[float]:
    aliases = {
        "home": [
            "home_win",
            "probability_home",
            "home_probability",
            "predicted_probability_home",
        ],
        "draw": [
            "draw",
            "draw_probability",
            "probability_draw",
            "predicted_probability_draw",
        ],
        "away": [
            "away_win",
            "probability_away",
            "away_probability",
            "predicted_probability_away",
        ],
    }

    for key in aliases.get(
        side,
        [],
    ):
        value = prediction.get(key)
        if value is None:
            continue

        value = safe_float(value)
        if value is None:
            continue

        if value > 1:
            value /= 100.0

        if not 0 <= value <= 1:
            return None

        return value

    return None


def prediction_confidence(
    prediction: Dict[str, Any],
) -> Optional[float]:
    for key in (
        "confidence",
        "faj_confidence",
        "prediction_confidence",
    ):
        value = safe_float(
            prediction.get(key)
        )
        if value is not None:
            return value
    return None


# ============================================================
# EXPERT
# ============================================================

def get_latest_expert(
    db: FAJDatabase,
    match_id: Any,
) -> Optional[Dict[str, Any]]:
    result = _call_first(
        db,
        [
            "get_expert_predictions",
        ],
        match_id,
    )

    if not result:
        return None

    try:
        first = result[0]
    except Exception:
        return None

    data = object_to_dict(first)

    return data or None


# ============================================================
# NB-BET FACT PARSER
# ============================================================

def parse_fact_url(
    url: str,
) -> Dict[str, Any]:
    """
    Получает факт только через NbBetStatsParser.
    Никакого собственного HTML-парсинга здесь нет.
    """
    if not url or not url.strip():
        return {
            "home_goals": None,
            "away_goals": None,
            "stats": {},
            "home_team": None,
            "away_team": None,
            "source_url": url,
            "parser_source": "nb-bet",
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now().isoformat(),
        }

    parser = NbBetStatsParser()

    parsed = parser.parse_match_page(
        url.strip()
    )

    if not isinstance(
        parsed,
        dict,
    ):
        parsed = {}

    stats = parsed.get(
        "stats",
        {},
    )

    if not isinstance(
        stats,
        dict,
    ):
        stats = {}

    home_goals = safe_int(
        parsed.get("home_goals")
    )

    away_goals = safe_int(
        parsed.get("away_goals")
    )

    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "stats": dict(stats),
        "home_team": parsed.get("home_team"),
        "away_team": parsed.get("away_team"),
        "source_url": url.strip(),
        "parser_source": "nb-bet",
        "parser_version": parsed.get(
            "parser_version",
            PARSER_VERSION,
        ),
        "data_quality": parsed.get(
            "data_quality",
            0.0,
        ),
        "parsed_at": datetime.now().isoformat(),
    }


# ============================================================
# VALIDATION
# ============================================================

def build_validation_data(
    match_id: Any,
    prediction: Dict[str, Any],
    fact: Dict[str, Any],
) -> Dict[str, Any]:

    actual_home = fact.get(
        "home_goals"
    )

    actual_away = fact.get(
        "away_goals"
    )

    predicted_score = extract_prediction_score(
        prediction
    )

    predicted_home, predicted_away = score_to_tuple(
        predicted_score
    )

    stats = fact.get(
        "stats",
        {},
    )

    if not isinstance(
        stats,
        dict,
    ):
        stats = {}

    predicted_winner = None

    if (
        predicted_home is not None
        and predicted_away is not None
    ):
        predicted_winner = winner_from_score(
            predicted_home,
            predicted_away,
        )

    actual_winner = winner_from_score(
        actual_home,
        actual_away,
    )

    return {
        "match_id": match_id,
        "prediction_id": prediction.get(
            "id"
        ),
        "match_prediction_id": prediction.get(
            "match_prediction_id"
        ),
        "predicted_score": predicted_score,
        "actual_score": (
            f"{actual_home}:{actual_away}"
            if (
                actual_home is not None
                and actual_away is not None
            )
            else None
        ),
        "predicted_home_xg": (
            prediction.get("home_xg")
            if prediction.get("home_xg") is not None
            else prediction.get("faj_xg_home")
        ),
        "actual_home_xg": stats.get(
            "home_xg"
        ),
        "predicted_away_xg": (
            prediction.get("away_xg")
            if prediction.get("away_xg") is not None
            else prediction.get("faj_xg_away")
        ),
        "actual_away_xg": stats.get(
            "away_xg"
        ),
        "predicted_winner": predicted_winner,
        "actual_winner": actual_winner,
        "predicted_probability_home":
            prediction_probability(
                prediction,
                "home",
            ),
        "predicted_probability_draw":
            prediction_probability(
                prediction,
                "draw",
            ),
        "predicted_probability_away":
            prediction_probability(
                prediction,
                "away",
            ),
        "score_probability": (
            prediction.get("score_probability")
            if prediction.get("score_probability") is not None
            else prediction.get("exact_score_probability")
        ),
        "confidence":
            prediction_confidence(
                prediction
            ),
        "risk": prediction.get(
            "risk"
        ),
        "predicted_btts": (
            prediction.get("btts")
            if prediction.get("btts") is not None
            else (
                prediction.get(
                    "predicted_btts"
                )
                if prediction.get("predicted_btts") is not None
                else prediction.get(
                    "faj_btts"
                )
            )
        ),
        "actual_btts":
            btts_from_score(
                actual_home,
                actual_away,
            ),
        "predicted_over25": (
            prediction.get("over25")
            if prediction.get("over25") is not None
            else (
                prediction.get(
                    "predicted_over25"
                )
                if prediction.get("predicted_over25") is not None
                else prediction.get(
                    "faj_total_25"
                )
            )
        ),
        "actual_over25":
            over25_from_score(
                actual_home,
                actual_away,
            ),
        "predicted_over35": (
            prediction.get("over35")
            if prediction.get("over35") is not None
            else (
                prediction.get(
                    "predicted_over35"
                )
                if prediction.get("predicted_over35") is not None
                else prediction.get(
                    "faj_total_35"
                )
            )
        ),
        "actual_over35":
            over35_from_score(
                actual_home,
                actual_away,
            ),
        "model_version":
            prediction.get(
                "model_version",
                MODEL_VERSION,
            ),
        "passport_version":
            prediction.get(
                "passport_version",
                "v2.2",
            ),
        "parser_version":
            PARSER_VERSION,
    }


# ============================================================
# GOLD
# ============================================================

def build_gold_data(
    match: Dict[str, Any],
    prediction: Dict[str, Any],
    expert: Optional[Dict[str, Any]],
    fact: Dict[str, Any],
) -> Dict[str, Any]:

    match_id = get_match_id(
        match
    )

    home_team = get_home_team(
        match
    )

    away_team = get_away_team(
        match
    )

    actual_home = fact.get(
        "home_goals"
    )

    actual_away = fact.get(
        "away_goals"
    )

    stats = fact.get(
        "stats",
        {},
    )

    if not isinstance(
        stats,
        dict,
    ):
        stats = {}

    faj_score = extract_prediction_score(
        prediction
    )

    expert_score = None
    expert_reasoning = ""

    if expert:
        expert_score = clean_score(
            expert.get("score")
            if expert.get("score") is not None
            else (
                expert.get("expert_score")
                if expert.get("expert_score") is not None
                else expert.get(
                    "predicted_score"
                )
            )
        )

        expert_reasoning = (
            expert.get("comment")
            if expert.get("comment") is not None
            else (
                expert.get("reasoning")
                if expert.get("reasoning") is not None
                else expert.get(
                    "expert_reasoning",
                    "",
                )
            )
        )

    return {
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "match_date":
            get_match_date(match),
        "model_version":
            prediction.get(
                "model_version",
                MODEL_VERSION,
            ),
        "faj_score":
            faj_score,
        "faj_xg_home": (
            prediction.get("home_xg")
            if prediction.get("home_xg") is not None
            else prediction.get("faj_xg_home")
        ),
        "faj_xg_away": (
            prediction.get("away_xg")
            if prediction.get("away_xg") is not None
            else prediction.get("faj_xg_away")
        ),
        "faj_btts": (
            prediction.get("btts")
            if prediction.get("btts") is not None
            else (
                prediction.get("predicted_btts")
                if prediction.get("predicted_btts") is not None
                else prediction.get("faj_btts")
            )
        ),
        "faj_total_25": (
            prediction.get("over25")
            if prediction.get("over25") is not None
            else (
                prediction.get("predicted_over25")
                if prediction.get("predicted_over25") is not None
                else prediction.get("faj_total_25")
            )
        ),
        "faj_total_35": (
            prediction.get("over35")
            if prediction.get("over35") is not None
            else (
                prediction.get("predicted_over35")
                if prediction.get("predicted_over35") is not None
                else prediction.get("faj_total_35")
            )
        ),
        "faj_confidence":
            prediction.get(
                "confidence"
            ),
        "faj_rating_home":
            prediction.get(
                "faj_rating_home"
            ),
        "faj_rating_away":
            prediction.get(
                "faj_rating_away"
            ),
        "faj_pir_home":
            prediction.get(
                "faj_pir_home"
            ),
        "faj_pir_away":
            prediction.get(
                "faj_pir_away"
            ),
        "faj_style_home":
            prediction.get(
                "faj_style_home"
            ),
        "faj_style_away":
            prediction.get(
                "faj_style_away"
            ),
        "expert_score":
            expert_score,
        "expert_reasoning":
            expert_reasoning,
        "actual_score": (
            f"{actual_home}:{actual_away}"
            if (
                actual_home is not None
                and actual_away is not None
            )
            else None
        ),
        "actual_xg_home":
            stats.get("home_xg"),
        "actual_xg_away":
            stats.get("away_xg"),
        "actual_btts":
            btts_from_score(
                actual_home,
                actual_away,
            ),
        "actual_total_25":
            over25_from_score(
                actual_home,
                actual_away,
            ),
        "actual_total_35":
            over35_from_score(
                actual_home,
                actual_away,
            ),
        "actual_home_goals":
            actual_home,
        "actual_away_goals":
            actual_away,
        "status":
            "completed",
    }


# ============================================================
# SAVE FACT
# ============================================================

def save_match_fact(
    db: FAJDatabase,
    match: Dict[str, Any],
    fact: Dict[str, Any],
    expert_score: str,
    expert_comment: str,
    expert_confidence: int,
) -> Dict[str, Any]:

    match_id = get_match_id(
        match
    )

    if match_id is None:
        raise ValueError(
            "У матча отсутствует ID."
        )

    # --------------------------------------------------------
    # RESULT LOCK
    # --------------------------------------------------------

    if db.is_result_locked(
        match_id
    ):
        raise ValueError(
            "Результат этого матча уже заблокирован."
        )

    # --------------------------------------------------------
    # FACT SCORE
    # --------------------------------------------------------

    home_goals = safe_int(
        fact.get("home_goals")
    )

    away_goals = safe_int(
        fact.get("away_goals")
    )

    if (
        home_goals is None
        or away_goals is None
    ):
        raise ValueError(
            "Не удалось определить счёт матча."
        )

    # --------------------------------------------------------
    # 1. RESULT
    # --------------------------------------------------------

    db.update_result(
        match_id,
        home_goals,
        away_goals,
        lock=False,
    )

    # --------------------------------------------------------
    # 2. STATISTICS
    # --------------------------------------------------------

    source_stats = fact.get(
        "stats",
        {},
    )

    if not isinstance(
        source_stats,
        dict,
    ):
        source_stats = {}

    stats = {
        "home_xg":
            source_stats.get(
                "home_xg"
            ),
        "away_xg":
            source_stats.get(
                "away_xg"
            ),
        "home_possession":
            source_stats.get(
                "home_possession"
            ),
        "away_possession":
            source_stats.get(
                "away_possession"
            ),
        "home_shots":
            source_stats.get(
                "home_shots"
            ),
        "away_shots":
            source_stats.get(
                "away_shots"
            ),
        "home_shots_on_target":
            source_stats.get(
                "home_shots_on_target"
            ),
        "away_shots_on_target":
            source_stats.get(
                "away_shots_on_target"
            ),
        "home_corners":
            source_stats.get(
                "home_corners"
            ),
        "away_corners":
            source_stats.get(
                "away_corners"
            ),
        "home_yellow_cards":
            source_stats.get(
                "home_yellow_cards"
            ),
        "away_yellow_cards":
            source_stats.get(
                "away_yellow_cards"
            ),
        "home_red_cards":
            source_stats.get(
                "home_red_cards"
            ),
        "away_red_cards":
            source_stats.get(
                "away_red_cards"
            ),
        "home_fouls":
            source_stats.get(
                "home_fouls"
            ),
        "away_fouls":
            source_stats.get(
                "away_fouls"
            ),
        "home_offsides":
            source_stats.get(
                "home_offsides"
            ),
        "away_offsides":
            source_stats.get(
                "away_offsides"
            ),
        "home_pass_accuracy":
            source_stats.get(
                "home_pass_accuracy"
            ),
        "away_pass_accuracy":
            source_stats.get(
                "away_pass_accuracy"
            ),
        "parser_source":
            fact.get(
                "source_url"
            ),
        "parser_version":
            fact.get(
                "parser_version",
                PARSER_VERSION,
            ),
        "data_quality":
            fact.get(
                "data_quality",
                0.0,
            ),
    }

    db.update_match_stats(
        match_id,
        stats,
    )

    # --------------------------------------------------------
    # 3. EXPERT
    # --------------------------------------------------------

    normalized_expert_score = clean_score(
        expert_score
    )

    if normalized_expert_score:
        db.save_expert_prediction(
            match_id=match_id,
            expert_name="Директор",
            score=normalized_expert_score,
            comment=expert_comment,
            confidence=expert_confidence,
        )

    # --------------------------------------------------------
    # 4. EXISTING FAJ PREDICTION
    # --------------------------------------------------------

    prediction = db.get_latest_prediction(
        match_id
    )

    prediction = object_to_dict(
        prediction
    )

    # --------------------------------------------------------
    # 5. EXPERT FROM DB
    # --------------------------------------------------------

    expert = get_latest_expert(
        db,
        match_id,
    )

    # --------------------------------------------------------
    # 6. VALIDATION
    # --------------------------------------------------------

    validation = build_validation_data(
        match_id=match_id,
        prediction=prediction,
        fact=fact,
    )

    validation_id = db.add_prediction_validation(
        validation
    )

    # --------------------------------------------------------
    # 7. GOLD
    # --------------------------------------------------------

    gold = build_gold_data(
        match=match,
        prediction=prediction,
        expert=expert,
        fact=fact,
    )

    gold_id = db.upsert_gold(
        gold
    )

    # --------------------------------------------------------
    # 8. GOLD LOCK
    # --------------------------------------------------------

    if gold_id is not None:
        db.lock_gold(
            gold_id
        )

    # --------------------------------------------------------
    # 9. RESULT LOCK
    # --------------------------------------------------------

    db.lock_match_result(
        match_id
    )

    return {
        "match_id":
            match_id,
        "validation_id":
            validation_id,
        "gold_id":
            gold_id,
        "score":
            f"{home_goals}:{away_goals}",
    }


# ============================================================
# UI — MATCH CARD
# ============================================================

def render_match_card(
    db: FAJDatabase,
    match: Dict[str, Any],
    index: int,
) -> None:

    match_id = get_match_id(
        match
    )

    if match_id is None:
        st.error(
            "У матча отсутствует ID."
        )
        return

    raw_home = get_home_team(
        match
    )

    raw_away = get_away_team(
        match
    )

    home_team, away_team = normalize_team_names(
        raw_home,
        raw_away,
    )

    home_team = (
        home_team
        or raw_home
    )

    away_team = (
        away_team
        or raw_away
    )

    key_prefix = (
        f"fact_{match_id}_{index}"
    )

    st.markdown(
        f"### ⚽ {home_team} — {away_team}"
    )

    # --------------------------------------------------------
    # PREDICTION
    # --------------------------------------------------------

    prediction = db.get_latest_prediction(
        match_id
    )

    prediction = object_to_dict(
        prediction
    )

    expert = get_latest_expert(
        db,
        match_id,
    )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:
        faj_score = extract_prediction_score(
            prediction
        )

        st.metric(
            "FAJ",
            faj_score or "—",
        )

    with col2:
        expert_score = None

        if expert:
            expert_score = clean_score(
                expert.get("score")
                if expert.get("score") is not None
                else expert.get(
                    "expert_score"
                )
            )

        st.metric(
            "Эксперт",
            expert_score or "—",
        )

    with col3:
        locked = db.is_result_locked(
            match_id
        )

        st.metric(
            "Статус",
            (
                "🔒 LOCKED"
                if locked
                else "⏳ Ожидает"
            ),
        )

    # --------------------------------------------------------
    # SOURCE URL
    # --------------------------------------------------------

    url = st.text_input(
        "🔗 Ссылка на матч (NB-BET)",
        key=f"{key_prefix}_url",
        placeholder=(
            "https://nb-bet.com/Events/..."
        ),
    )

    if st.button(
        "📥 Забрать данные",
        key=f"{key_prefix}_parse",
        width="stretch",
    ):
        if not url.strip():
            st.error(
                "Сначала вставьте ссылку."
            )
        else:
            with st.spinner(
                "Получаем результат и статистику..."
            ):
                try:
                    fact = parse_fact_url(
                        url.strip()
                    )

                    st.session_state[
                        f"{key_prefix}_fact"
                    ] = fact

                    if (
                        fact.get("home_goals")
                        is None
                        or
                        fact.get("away_goals")
                        is None
                    ):
                        st.warning(
                            "Парсер не смог уверенно "
                            "определить счёт. "
                            "Факт НЕ готов к сохранению."
                        )
                    else:
                        st.success(
                            "Факт матча получен."
                        )

                except Exception as exc:
                    logger.exception(
                        "Ошибка NB-BET parser"
                    )
                    st.error(
                        f"Ошибка parser: {exc}"
                    )

    fact = st.session_state.get(
        f"{key_prefix}_fact"
    )

    if fact:

        # ----------------------------------------------------
        # FACT SCORE
        # ----------------------------------------------------

        home_goals = fact.get(
            "home_goals"
        )

        away_goals = fact.get(
            "away_goals"
        )

        st.markdown(
            f"**Факт: "
            f"{home_goals if home_goals is not None else '—'}:"
            f"{away_goals if away_goals is not None else '—'}**"
        )

        stats = fact.get(
            "stats",
            {},
        )

        if not isinstance(
            stats,
            dict,
        ):
            stats = {}

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        stat_rows = [
            (
                "xG",
                stats.get("home_xg"),
                stats.get("away_xg"),
            ),
            (
                "Удары",
                stats.get("home_shots"),
                stats.get("away_shots"),
            ),
            (
                "Удары в створ",
                stats.get(
                    "home_shots_on_target"
                ),
                stats.get(
                    "away_shots_on_target"
                ),
            ),
            (
                "Владение",
                stats.get(
                    "home_possession"
                ),
                stats.get(
                    "away_possession"
                ),
            ),
            (
                "Угловые",
                stats.get(
                    "home_corners"
                ),
                stats.get(
                    "away_corners"
                ),
            ),
            (
                "Фолы",
                stats.get(
                    "home_fouls"
                ),
                stats.get(
                    "away_fouls"
                ),
            ),
            (
                "ЖК",
                stats.get(
                    "home_yellow_cards"
                ),
                stats.get(
                    "away_yellow_cards"
                ),
            ),
            (
                "КК",
                stats.get(
                    "home_red_cards"
                ),
                stats.get(
                    "away_red_cards"
                ),
            ),
        ]

        table_data = []

        for name, home, away in stat_rows:

            table_data.append(
                {
                    "Показатель":
                        name,
                    home_team:
                        (
                            home
                            if home is not None
                            else "—"
                        ),
                    away_team:
                        (
                            away
                            if away is not None
                            else "—"
                        ),
                }
            )

        st.dataframe(
            table_data,
            width="stretch",
            hide_index=True,
        )

        # ----------------------------------------------------
        # EXPERT
        # ----------------------------------------------------

        st.markdown(
            "**🧠 Экспертный прогноз директора**"
        )

        existing_expert_score = ""

        if expert:
            existing_expert_score = (
                clean_score(
                    expert.get("score")
                    if expert.get("score") is not None
                    else expert.get(
                        "expert_score"
                    )
                )
                or ""
            )

        expert_score_input = st.text_input(
            "Счёт эксперта",
            value=existing_expert_score,
            key=f"{key_prefix}_expert_score",
            placeholder="Например: 2:1",
        )

        expert_comment = st.text_area(
            "Комментарий эксперта",
            value=(
                expert.get("comment")
                if (
                    expert
                    and expert.get("comment")
                    is not None
                )
                else (
                    expert.get("reasoning")
                    if (
                        expert
                        and expert.get("reasoning")
                        is not None
                    )
                    else ""
                )
            ),
            key=f"{key_prefix}_expert_comment",
        )

        existing_confidence = 50

        if expert:
            value = safe_int(
                expert.get(
                    "confidence"
                )
            )

            if value is not None:
                existing_confidence = max(
                    0,
                    min(
                        100,
                        value,
                    ),
                )

        expert_confidence = st.slider(
            "Уверенность эксперта",
            min_value=0,
            max_value=100,
            value=existing_confidence,
            key=f"{key_prefix}_expert_confidence",
        )

        # ----------------------------------------------------
        # COMPARISON
        # ----------------------------------------------------

        st.markdown(
            "**📊 Сравнение**"
        )

        actual_score = None

        if (
            home_goals is not None
            and away_goals is not None
        ):
            actual_score = clean_score(
                f"{home_goals}:{away_goals}"
            )

        faj_score = extract_prediction_score(
            prediction
        )

        comparison = [
            {
                "Источник":
                    "FAJ",
                "Счёт":
                    faj_score or "—",
            },
            {
                "Источник":
                    "Эксперт",
                "Счёт":
                    clean_score(
                        expert_score_input
                    )
                    or "—",
            },
            {
                "Источник":
                    "Факт",
                "Счёт":
                    actual_score or "—",
            },
        ]

        st.dataframe(
            comparison,
            width="stretch",
            hide_index=True,
        )

        # ----------------------------------------------------
        # SAVE
        # ----------------------------------------------------

        if st.button(
            "✅ Сохранить факты",
            key=f"{key_prefix}_save",
            type="primary",
            width="stretch",
        ):
            try:

                result = save_match_fact(
                    db=db,
                    match=match,
                    fact=fact,
                    expert_score=(
                        clean_score(
                            expert_score_input
                        )
                        or ""
                    ),
                    expert_comment=expert_comment,
                    expert_confidence=expert_confidence,
                )

                st.success(
                    "Факт сохранён и защищён."
                )

                st.caption(
                    f"Match ID: "
                    f"{result['match_id']} | "
                    f"Validation ID: "
                    f"{result['validation_id']} | "
                    f"Gold ID: "
                    f"{result['gold_id']}"
                )

                st.session_state[
                    f"{key_prefix}_saved"
                ] = True

            except Exception as exc:

                logger.exception(
                    "Ошибка сохранения факта"
                )

                st.error(
                    f"Ошибка сохранения: {exc}"
                )

    st.divider()


# ============================================================
# LEARNING
# ============================================================

def run_learning() -> Any:

    from app.learning_engine import (
        run_learning,
    )

    return run_learning(
        db_path=DEFAULT_DB_PATH,
        force=False,
    )


# ============================================================
# MAIN PAGE
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title="FAJ — Импорт фактов",
        page_icon="⚽",
        layout="wide",
    )

    st.title(
        "⚽ FAJ — Импорт фактов"
    )

    st.caption(
        f"FAJ Platform {APP_VERSION} "
        f"| Import Facts {IMPORT_FACTS_VERSION}"
    )

    db = get_database()

    # ========================================================
    # HEADER
    # ========================================================

    col1, col2 = st.columns(
        2
    )

    with col1:

        league = st.selectbox(
            "🏆 Лига",
            list(
                LEAGUES.keys()
            ),
            index=0,
        )

    with col2:

        round_number = st.number_input(
            "🔢 Тур",
            min_value=1,
            max_value=30,
            value=1,
            step=1,
        )

    st.session_state[
        "selected_league"
    ] = league

    st.session_state[
        "selected_round"
    ] = int(round_number)

    # ========================================================
    # MATCHES
    # ========================================================

    matches = get_round_matches(
        db,
        int(round_number),
    )

    st.markdown(
        f"## {league} — "
        f"{round_number}-й тур"
    )

    if not matches:

        st.warning(
            "Матчи выбранного тура не найдены."
        )

        st.stop()

    st.info(
        f"Найдено матчей: {len(matches)}"
    )

    # ========================================================
    # MATCH CARDS
    # ========================================================

    for index, match in enumerate(
        matches
    ):

        render_match_card(
            db=db,
            match=match,
            index=index,
        )

    # ========================================================
    # LEARNING
    # ========================================================

    st.markdown(
        "## 🧠 Обучение"
    )

    st.caption(
        "Обучение запускается после "
        "сохранения фактов тура."
    )

    if st.button(
        "🧠 Обучение",
        type="primary",
        width="stretch",
    ):

        try:

            with st.spinner(
                "FAJ Learning Engine обучается..."
            ):

                result = run_learning()

            st.success(
                "Обучение завершено."
            )

            if result is not None:

                st.write(result)

        except Exception as exc:

            logger.exception(
                "Ошибка Learning Engine"
            )

            st.error(
                f"Ошибка Learning Engine: {exc}"
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    main()
