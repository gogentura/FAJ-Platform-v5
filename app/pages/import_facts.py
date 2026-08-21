#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
IMPORT FACTS v4.4
============================================================

НАЗНАЧЕНИЕ:
    Импорт фактических данных сыгранного матча/тура.

============================================================
ИСТОЧНИКИ ФАКТОВ
============================================================

РПЛ:
    ⚽ Счёт:
        ручной ввод

    📊 Статистика + 🎯 xG:
        Soccer365 (полный сборщик)

АПЛ / ЛА ЛИГА / ЛИГА ЧЕМПИОНОВ:
    🤖 Data Football API:
        автоматический источник, если API отдаёт данные

    При отсутствии отдельных данных API:
        ⚽ Счёт       → ручной ввод
        📊 Статистика → Soccer365
        🎯 xG         → Soccer365

============================================================
АРХИТЕКТУРНЫЙ ПРИНЦИП
============================================================

database.py
    ↓
import_facts.py
    ↓
SOURCE LAYER
    ├── Data Football API
    └── Soccer365
    ↓
FACT NORMALIZER
    ↓
SQLite
    ↓
GITHUB SYNC (автоматически после сохранения)
    ↓
VALIDATION
    ↓
GOLD
    ↓
LOCK
    ↓
LEARNING (на странице "Тур сыгран" или ETC)

============================================================
ИЗМЕНЕНИЯ V4.4
============================================================

1. Использование db.get_round_matches_by_number() вместо прямого SQL
2. Удалён FALLBACK SQL блок
3. Удалён _call_first() для поиска несуществующих методов
4. Архитектурная чистота: database.py — единственный источник работы с БД
============================================================
"""

from __future__ import annotations

import importlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from app.database import FAJDatabase
from app.parsers.soccer365_parser import Soccer365Parser
from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
IMPORT_FACTS_VERSION = "4.4"
MODEL_VERSION = "v12.1"

DEFAULT_DB_PATH = "data/faj.db"


LEAGUES = {
    "РПЛ": "РПЛ",
    "АПЛ": "АПЛ",
    "Ла Лига": "Ла Лига",
    "Лига чемпионов": "Лига чемпионов",
}


# ============================================================
# SOURCE CONFIGURATION
# ============================================================

SOURCE_CONFIG = {

    "РПЛ": {
        "api": False,
        "score": "manual",
        "stats": "soccer365",
        "xg": "soccer365",
    },

    "АПЛ": {
        "api": True,
        "score": "api_or_manual",
        "stats": "api_or_soccer365",
        "xg": "api_or_soccer365",
    },

    "Ла Лига": {
        "api": True,
        "score": "api_or_manual",
        "stats": "api_or_soccer365",
        "xg": "api_or_soccer365",
    },

    "Лига чемпионов": {
        "api": True,
        "score": "api_or_manual",
        "stats": "api_or_soccer365",
        "xg": "api_or_soccer365",
    },
}


# ============================================================
# DATABASE
# ============================================================

@st.cache_resource
def get_database() -> FAJDatabase:
    return FAJDatabase()


# ============================================================
# GITHUB SYNC
# ============================================================

def sync_to_github() -> Dict[str, Any]:
    """Синхронизирует текущую БД с GitHub."""
    try:
        from app.github_db_sync import save_database_to_github
        result = save_database_to_github()
        logger.info(
            "GITHUB SYNC | size=%s bytes",
            result.get('size', 0)
        )
        return result
    except Exception as exc:
        logger.exception("GitHub sync failed")
        return {"error": str(exc), "size": 0}


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


def object_to_dict(value: Any) -> Dict[str, Any]:

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
# MATCH ACCESS — ЧЕРЕЗ DATABASE.PY
# ============================================================

def get_round_matches(
    db: FAJDatabase,
    round_number: int,
    league: str,
) -> List[Dict[str, Any]]:

    """
    Получает матчи тура через database.py.

    ВАЖНО:
        round_number не уникален между лигами.
        database.get_round_matches_by_number() фильтрует по league.
    """

    return db.get_round_matches_by_number(
        round_number,
        league,
    )


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
# SOURCE NORMALIZATION
# ============================================================

def normalize_source_stats(
    stats: Any,
) -> Dict[str, Any]:
    """
    Нормализует статистику из любого источника.
    ВАЖНО: None и 0 — разные вещи.
    """
    if not isinstance(stats, dict):
        return {}
    
    allowed = [
        # ----------------------------------------------------
        # XG
        # ----------------------------------------------------
        "home_xg",
        "away_xg",
        # ----------------------------------------------------
        # POSSESSION
        # ----------------------------------------------------
        "home_possession",
        "away_possession",
        # ----------------------------------------------------
        # SHOTS
        # ----------------------------------------------------
        "home_shots",
        "away_shots",
        "home_shots_on_target",
        "away_shots_on_target",
        # ----------------------------------------------------
        # CORNERS
        # ----------------------------------------------------
        "home_corners",
        "away_corners",
        # ----------------------------------------------------
        # PASSES
        # ----------------------------------------------------
        "home_total_passes",
        "away_total_passes",
        "home_pass_accuracy",
        "away_pass_accuracy",
        "home_accurate_passes",
        "away_accurate_passes",
        # ----------------------------------------------------
        # DEFENCE
        # ----------------------------------------------------
        "home_tackles",
        "away_tackles",
        # ----------------------------------------------------
        # FOULS
        # ----------------------------------------------------
        "home_fouls",
        "away_fouls",
        # ----------------------------------------------------
        # CARDS
        # ----------------------------------------------------
        "home_yellow_cards",
        "away_yellow_cards",
        "home_red_cards",
        "away_red_cards",
    ]
    
    return {
        key: stats.get(key)
        for key in allowed
        if stats.get(key) is not None
    }


# ============================================================
# API ADAPTER
# ============================================================

def get_api_provider() -> Optional[Any]:
    """
    Ленивое подключение Data Football API.

    ВАЖНО:

    import_facts.py не должен падать,
    если API-модуль пока отсутствует.

    Это позволяет сначала работать
    полностью через ручной/Soccer365 режим.
    """

    candidates = [
        (
            "app.parsers.data_football_api",
            "DataFootballAPI",
        ),
        (
            "app.parsers.data_football_parser",
            "DataFootballParser",
        ),
        (
            "app.data_football_client",
            "DataFootballClient",
        ),
        (
            "app.football_data_client",
            "FootballDataClient",
        ),
    ]

    for module_name, class_name in candidates:

        try:

            module = importlib.import_module(
                module_name
            )

            cls = getattr(
                module,
                class_name,
                None,
            )

            if cls is None:
                continue

            return cls()

        except Exception as exc:

            logger.debug(
                "API provider %s.%s unavailable: %s",
                module_name,
                class_name,
                exc,
            )

    return None


def parse_api_fact(
    league: str,
    match: Dict[str, Any],
) -> Dict[str, Any]:

    """
    Получает автоматические факты из Data Football API.

    API может вернуть:
        score
        statistics
        xG

    Но отсутствие одного поля НЕ является ошибкой.

    Возвращаются только реально полученные данные.
    """

    empty = {
        "home_goals": None,
        "away_goals": None,
        "stats": {},
        "api_score": False,
        "api_stats": False,
        "api_xg": False,
        "api_available": False,
        "api_source": "data-football",
        "api_error": None,
        "parsed_at": datetime.now().isoformat(),
    }

    if league == "РПЛ":
        return empty

    provider = get_api_provider()

    if provider is None:
        return empty

    try:

        match_id = get_match_id(match)

        # Универсальный поиск метода.
        result = None
        for method_name in [
            "get_match_facts",
            "get_match",
            "fetch_match",
            "get_fixture",
            "fetch_fixture",
        ]:
            method = getattr(provider, method_name, None)
            if callable(method):
                try:
                    result = method(match_id)
                    if result is not None:
                        break
                except Exception:
                    continue

        if result is None:
            return empty

        data = object_to_dict(result)

        empty["api_available"] = True

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        score = clean_score(
            data.get("score")
            or data.get("final_score")
            or data.get("full_time_score")
        )

        if score:

            home, away = score_to_tuple(score)

            empty["home_goals"] = home
            empty["away_goals"] = away
            empty["api_score"] = True

        else:

            home = safe_int(
                data.get("home_goals")
            )

            away = safe_int(
                data.get("away_goals")
            )

            if home is not None and away is not None:

                empty["home_goals"] = home
                empty["away_goals"] = away
                empty["api_score"] = True

        # ----------------------------------------------------
        # STATISTICS
        # ----------------------------------------------------

        api_stats = data.get(
            "stats",
            data.get(
                "statistics",
                {},
            ),
        )

        api_stats = normalize_source_stats(
            api_stats
        )

        if any(
            value is not None
            for value in api_stats.values()
        ):

            empty["stats"].update(
                api_stats
            )

            empty["api_stats"] = True

        # ----------------------------------------------------
        # XG
        # ----------------------------------------------------

        home_xg = (
            data.get("home_xg")
            or data.get("xg_home")
        )

        away_xg = (
            data.get("away_xg")
            or data.get("xg_away")
        )

        if home_xg is not None:

            empty["stats"]["home_xg"] = safe_float(
                home_xg
            )

        if away_xg is not None:

            empty["stats"]["away_xg"] = safe_float(
                away_xg
            )

        if (
            empty["stats"].get("home_xg") is not None
            or empty["stats"].get("away_xg") is not None
        ):
            empty["api_xg"] = True

        return empty

    except Exception as exc:

        logger.exception(
            "Data Football API error"
        )

        empty["api_error"] = str(exc)

        return empty


# ============================================================
# SOCCER365 — ПОЛНЫЙ СБОРЩИК
# ============================================================

def parse_soccer365(
    url: str,
) -> Dict[str, Any]:
    """
    Полный сборщик фактов Soccer365.
    
    Soccer365 теперь является источником:
        SCORE       — НЕ берём (остаётся ручным вводом)
        STATISTICS  — берём
        XG          — берём
    
    Счёт остаётся отдельным фактом,
    который вводит директор.
    
    Parser должен вернуть нормализованные поля:
        home_xg, away_xg
        home_possession, away_possession
        home_shots, away_shots
        home_shots_on_target, away_shots_on_target
        home_corners, away_corners
        home_total_passes, away_total_passes
        home_pass_accuracy, away_pass_accuracy
        home_accurate_passes, away_accurate_passes
        home_tackles, away_tackles
        home_fouls, away_fouls
        home_yellow_cards, away_yellow_cards
        home_red_cards, away_red_cards
    """
    result = {
        "stats": {},
        "source": "soccer365",
        "source_url": url,
        "quality": 0.0,
        "error": None,
        "parser": "Soccer365Parser",
        "parser_version": IMPORT_FACTS_VERSION,
    }

    if not url or not url.strip():
        return result

    try:
        parser = Soccer365Parser()

        # ----------------------------------------------------
        # НОВЫЙ ПОЛНЫЙ PARSER
        # ----------------------------------------------------
        parsed = None
        parse_match = getattr(
            parser,
            "parse_match",
            None,
        )

        if callable(parse_match):
            parsed = parse_match(
                url.strip()
            )
        else:
            # ------------------------------------------------
            # ВРЕМЕННАЯ ОБРАТНАЯ СОВМЕСТИМОСТЬ
            # ------------------------------------------------
            #
            # Пока новый parser ещё не установлен,
            # старый parse_xg не ломает приложение.
            #
            parse_xg = getattr(
                parser,
                "parse_xg",
                None,
            )
            if callable(parse_xg):
                parsed = parse_xg(
                    url.strip()
                )

        if parsed is None:
            result["error"] = (
                "Soccer365Parser "
                "не вернул данные."
            )
            return result

        data = object_to_dict(
            parsed
        )

        # ----------------------------------------------------
        # ПОЛУЧАЕМ STATS
        # ----------------------------------------------------
        raw_stats = data.get(
            "stats",
            data,
        )

        stats = normalize_source_stats(
            raw_stats
        )

        # ----------------------------------------------------
        # ДОПОЛНИТЕЛЬНО ПОДДЕРЖИВАЕМ
        # ПЛОСКИЙ ФОРМАТ PARSER
        # ----------------------------------------------------
        if not stats:
            stats = normalize_source_stats(
                data
            )

        # ----------------------------------------------------
        # XG (если не пришли через stats)
        # ----------------------------------------------------
        if stats.get(
            "home_xg"
        ) is None:
            home_xg = (
                data.get("home_xg")
                or data.get("xg_home")
            )
            if home_xg is not None:
                stats["home_xg"] = safe_float(
                    home_xg
                )

        if stats.get(
            "away_xg"
        ) is None:
            away_xg = (
                data.get("away_xg")
                or data.get("xg_away")
            )
            if away_xg is not None:
                stats["away_xg"] = safe_float(
                    away_xg
                )

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------
        quality = safe_float(
            data.get(
                "data_quality"
            )
        )

        if quality is None:
            available = sum(
                value is not None
                for value in stats.values()
            )
            
            total = len(
                normalize_source_stats(
                    {
                        key: 1
                        for key in (
                            "home_xg",
                            "away_xg",
                            "home_possession",
                            "away_possession",
                            "home_shots",
                            "away_shots",
                            "home_shots_on_target",
                            "away_shots_on_target",
                            "home_corners",
                            "away_corners",
                            "home_total_passes",
                            "away_total_passes",
                            "home_pass_accuracy",
                            "away_pass_accuracy",
                            "home_accurate_passes",
                            "away_accurate_passes",
                            "home_tackles",
                            "away_tackles",
                            "home_fouls",
                            "away_fouls",
                            "home_yellow_cards",
                            "away_yellow_cards",
                            "home_red_cards",
                            "away_red_cards",
                        )
                    }
                )
            )
            quality = (
                available / total
                if total
                else 0.0
            )

        result["stats"] = stats
        result["quality"] = quality

        return result

    except Exception as exc:

        logger.exception(
            "Soccer365 parser error"
        )

        result["error"] = str(exc)

        return result


# ============================================================
# HYBRID FACT — БЕЗ BOMBARDIR
# ============================================================

def build_hybrid_fact(
    league: str,
    match: Dict[str, Any],
    api_fact: Optional[Dict[str, Any]] = None,
    soccer365_fact: Optional[Dict[str, Any]] = None,
    manual_home_goals: Optional[int] = None,
    manual_away_goals: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Объединяет источники фактов.

    SCORE:
        API → manual

    STATS:
        API → Soccer365, поле за полем

    XG:
        API → Soccer365

    Bombardir:
        НЕ ИСПОЛЬЗУЕТСЯ.
    """
    api_fact = api_fact or {}
    soccer365_fact = soccer365_fact or {}

    api_stats = normalize_source_stats(
        api_fact.get("stats", {})
    )

    soccer365_stats = normalize_source_stats(
        soccer365_fact.get("stats", {})
    )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    home_goals = safe_int(
        api_fact.get("home_goals")
    )

    away_goals = safe_int(
        api_fact.get("away_goals")
    )

    score_source = None

    if (
        home_goals is not None
        and away_goals is not None
    ):

        score_source = "data-football"

    else:

        home_goals = manual_home_goals
        away_goals = manual_away_goals

        if (
            home_goals is not None
            and away_goals is not None
        ):

            score_source = "manual"

    # --------------------------------------------------------
    # STATS — API → SOCCER365 (поле за полем)
    # --------------------------------------------------------

    stats = {}

    stat_keys = [
        # possession
        "home_possession",
        "away_possession",
        # shots
        "home_shots",
        "away_shots",
        "home_shots_on_target",
        "away_shots_on_target",
        # corners
        "home_corners",
        "away_corners",
        # passes
        "home_total_passes",
        "away_total_passes",
        "home_pass_accuracy",
        "away_pass_accuracy",
        "home_accurate_passes",
        "away_accurate_passes",
        # defence
        "home_tackles",
        "away_tackles",
        # fouls
        "home_fouls",
        "away_fouls",
        # cards
        "home_yellow_cards",
        "away_yellow_cards",
        "home_red_cards",
        "away_red_cards",
    ]

    for key in stat_keys:
        value = api_stats.get(key)
        if value is not None:
            stats[key] = value
            continue

        value = soccer365_stats.get(key)
        if value is not None:
            stats[key] = value

    # --------------------------------------------------------
    # XG — API → SOCCER365
    # --------------------------------------------------------

    home_xg = api_stats.get(
        "home_xg"
    )

    away_xg = api_stats.get(
        "away_xg"
    )

    xg_source = None

    if (
        home_xg is not None
        or away_xg is not None
    ):

        xg_source = "data-football"

    else:

        home_xg = soccer365_stats.get(
            "home_xg"
        )

        away_xg = soccer365_stats.get(
            "away_xg"
        )

        if (
            home_xg is not None
            or away_xg is not None
        ):

            xg_source = "soccer365"

    stats["home_xg"] = home_xg
    stats["away_xg"] = away_xg

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    available = 0
    total = 3

    if (
        home_goals is not None
        and away_goals is not None
    ):
        available += 1

    if any(
        value is not None
        for key, value in stats.items()
        if key not in (
            "home_xg",
            "away_xg",
        )
    ):
        available += 1

    if (
        home_xg is not None
        or away_xg is not None
    ):
        available += 1

    quality = available / total

    # --------------------------------------------------------
    # SOURCE OF STATS
    # --------------------------------------------------------

    api_stat_fields = any(
        api_stats.get(key) is not None
        for key in stat_keys
    )

    soccer365_stat_fields = any(
        soccer365_stats.get(key) is not None
        for key in stat_keys
    )

    if api_stat_fields:
        stats_source = "data-football"
    elif soccer365_stat_fields:
        stats_source = "soccer365"
    else:
        stats_source = None

    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "stats": stats,
        "score_source": score_source,
        "stats_source": stats_source,
        "xg_source": xg_source,
        "source_url": (
            soccer365_fact.get("source_url")
        ),
        "parser_source": "hybrid",
        "parser_version": IMPORT_FACTS_VERSION,
        "data_quality": quality,
        "parsed_at": datetime.now().isoformat(),
    }


# ============================================================
# MATCH FACT STATUS
# ============================================================

def fact_status(
    fact: Dict[str, Any],
) -> Dict[str, bool]:

    home = fact.get("home_goals")
    away = fact.get("away_goals")

    stats = fact.get(
        "stats",
        {},
    )

    if not isinstance(stats, dict):
        stats = {}

    has_score = (
        home is not None
        and away is not None
    )

    has_stats = any(
        stats.get(key) is not None
        for key in (
            "home_possession",
            "away_possession",
            "home_corners",
            "away_corners",
            "home_shots",
            "away_shots",
            "home_shots_on_target",
            "away_shots_on_target",
            "home_total_passes",
            "away_total_passes",
            "home_pass_accuracy",
            "away_pass_accuracy",
            "home_accurate_passes",
            "away_accurate_passes",
            "home_tackles",
            "away_tackles",
            "home_fouls",
            "away_fouls",
            "home_yellow_cards",
            "away_yellow_cards",
            "home_red_cards",
            "away_red_cards",
        )
    )

    has_xg = (
        stats.get("home_xg") is not None
        or stats.get("away_xg") is not None
    )

    return {
        "score": has_score,
        "stats": has_stats,
        "xg": has_xg,
        "complete": (
            has_score
            and has_stats
            and has_xg
        ),
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

    match_id = get_match_id(match)

    if match_id is None:
        raise ValueError(
            "У матча отсутствует ID."
        )

    if db.is_result_locked(match_id):
        raise ValueError(
            "Результат этого матча уже заблокирован."
        )

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
    # RESULT
    # --------------------------------------------------------

    db.update_result(
        match_id,
        home_goals,
        away_goals,
        lock=False,
    )

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    source_stats = normalize_source_stats(
        fact.get("stats", {})
    )

    stats = {
        key: source_stats.get(key)
        for key in (
            # xG
            "home_xg",
            "away_xg",
            # possession
            "home_possession",
            "away_possession",
            # shots
            "home_shots",
            "away_shots",
            "home_shots_on_target",
            "away_shots_on_target",
            # corners
            "home_corners",
            "away_corners",
            # passes
            "home_total_passes",
            "away_total_passes",
            "home_pass_accuracy",
            "away_pass_accuracy",
            "home_accurate_passes",
            "away_accurate_passes",
            # defence
            "home_tackles",
            "away_tackles",
            # fouls
            "home_fouls",
            "away_fouls",
            # cards
            "home_yellow_cards",
            "away_yellow_cards",
            "home_red_cards",
            "away_red_cards",
        )
    }

    stats["score_source"] = fact.get(
        "score_source"
    )

    stats["stats_source"] = fact.get(
        "stats_source"
    )

    stats["xg_source"] = fact.get(
        "xg_source"
    )

    stats["parser_source"] = fact.get(
        "parser_source",
        "hybrid",
    )

    stats["parser_version"] = fact.get(
        "parser_version",
        IMPORT_FACTS_VERSION,
    )

    stats["data_quality"] = fact.get(
        "data_quality",
        0.0,
    )

    db.update_match_stats(
        match_id,
        stats,
    )

    # --------------------------------------------------------
    # EXPERT
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
    # FAJ PREDICTION
    # --------------------------------------------------------

    prediction = db.get_latest_prediction(
        match_id
    )

    prediction = object_to_dict(
        prediction
    )

    # --------------------------------------------------------
    # EXPERT
    # --------------------------------------------------------

    expert = get_latest_expert(
        db,
        match_id,
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    validation = build_validation_data(
        match_id=match_id,
        prediction=prediction,
        fact=fact,
    )

    validation_id = (
        db.add_prediction_validation(
            validation
        )
    )

    # --------------------------------------------------------
    # GOLD
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
    # LOCK
    # --------------------------------------------------------

    if gold_id is not None:
        db.lock_gold(gold_id)

    db.lock_match_result(
        match_id
    )

    return {
        "match_id": match_id,
        "validation_id": validation_id,
        "gold_id": gold_id,
        "score": (
            f"{home_goals}:{away_goals}"
        ),
    }


# ============================================================
# PREDICTION HELPERS
# ============================================================

def extract_prediction_score(
    prediction: Dict[str, Any],
) -> Optional[str]:

    if not prediction:
        return None

    for key in (
        "predicted_score",
        "score",
        "faj_score",
        "most_likely_score",
        "prediction_score",
        "exact_score",
    ):

        value = prediction.get(key)

        if value is not None:

            score = clean_score(
                value
            )

            if score:
                return score

    prediction_id = prediction.get(
        "id"
    )

    if prediction_id:

        try:

            db = get_database()

            scores = db.get_prediction_scores(
                prediction_id
            )

            if scores:

                for row in scores:

                    row_dict = object_to_dict(
                        row
                    )

                    if (
                        row_dict.get("rank")
                        == 1
                    ):

                        return clean_score(
                            row_dict.get(
                                "score"
                            )
                        )

                first = object_to_dict(
                    scores[0]
                )

                return clean_score(
                    first.get("score")
                )

        except Exception as exc:

            logger.debug(
                "prediction_scores error: %s",
                exc,
            )

    return None


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

        value = prediction.get(
            key
        )

        if value is None:
            continue

        value = safe_float(
            value
        )

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

    try:
        result = db.get_expert_predictions(match_id)
        if not result:
            return None
        first = result[0]
        return object_to_dict(first) if first else None
    except Exception:
        return None


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

    if not isinstance(stats, dict):
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
            else prediction.get(
                "faj_xg_home"
            )
        ),

        "actual_home_xg": stats.get(
            "home_xg"
        ),

        "predicted_away_xg": (
            prediction.get("away_xg")
            if prediction.get("away_xg") is not None
            else prediction.get(
                "faj_xg_away"
            )
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
            prediction.get(
                "score_probability"
            )
            if prediction.get(
                "score_probability"
            ) is not None
            else prediction.get(
                "exact_score_probability"
            )
        ),

        "confidence":
            prediction_confidence(
                prediction
            ),

        "risk":
            prediction.get(
                "risk"
            ),

        "predicted_btts": (
            prediction.get("btts")
            if prediction.get("btts") is not None
            else prediction.get(
                "predicted_btts"
            )
        ),

        "actual_btts":
            btts_from_score(
                actual_home,
                actual_away,
            ),

        "predicted_over25":
            prediction.get(
                "over25"
            ),

        "actual_over25":
            over25_from_score(
                actual_home,
                actual_away,
            ),

        "predicted_over35":
            prediction.get(
                "over35"
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
            IMPORT_FACTS_VERSION,
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

    if not isinstance(stats, dict):
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
            else expert.get(
                "expert_score"
            )
        )

        expert_reasoning = (
            expert.get(
                "comment"
            )
            if expert.get(
                "comment"
            ) is not None
            else expert.get(
                "reasoning",
                "",
            )
        )

    return {
        "match_id": match_id,

        "home_team": home_team,
        "away_team": away_team,

        "match_date":
            get_match_date(
                match
            ),

        "model_version":
            prediction.get(
                "model_version",
                MODEL_VERSION,
            ),

        "faj_score":
            faj_score,

        "faj_xg_home":
            prediction.get(
                "home_xg"
            ),

        "faj_xg_away":
            prediction.get(
                "away_xg"
            ),

        "faj_btts":
            prediction.get(
                "btts"
            ),

        "faj_total_25":
            prediction.get(
                "over25"
            ),

        "faj_total_35":
            prediction.get(
                "over35"
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
            stats.get(
                "home_xg"
            ),

        "actual_xg_away":
            stats.get(
                "away_xg"
            ),

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
# UI — MATCH CARD
# ============================================================

def render_match_card(
    db: FAJDatabase,
    match: Dict[str, Any],
    index: int,
    league: str,
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
        home_team or raw_home
    )

    away_team = (
        away_team or raw_away
    )

    key_prefix = (
        f"fact_{league}_{match_id}_{index}"
    )

    st.markdown(
        f"### ⚽ {home_team} — {away_team}"
    )

    # ========================================================
    # PREDICTION
    # ========================================================

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

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "FAJ",
            extract_prediction_score(
                prediction
            ) or "—",
        )

    with col2:

        expert_score = None

        if expert:

            expert_score = clean_score(
                expert.get(
                    "score"
                )
                or expert.get(
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
            "🔒 LOCKED"
            if locked
            else "⏳ Ожидает",
        )

    # ========================================================
    # EXISTING RESULT
    # ========================================================

    existing_result = db.get_match_result(
        match_id
    )

    existing_result = (
        object_to_dict(
            existing_result
        )
        if existing_result
        else {}
    )

    home_goals = safe_int(
        existing_result.get(
            "home_goals"
        )
    )

    away_goals = safe_int(
        existing_result.get(
            "away_goals"
        )
    )

    score_locked = (
        existing_result.get(
            "fact_status"
        )
        == "locked"
    )

    # ========================================================
    # API FACT
    # ========================================================

    api_fact = st.session_state.get(
        f"{key_prefix}_api_fact"
    )

    if api_fact is None:

        api_fact = parse_api_fact(
            league,
            match,
        )

        st.session_state[
            f"{key_prefix}_api_fact"
        ] = api_fact

    # ========================================================
    # API STATUS
    # ========================================================

    api_status = (
        api_fact.get(
            "api_available"
        )
    )

    api_score = (
        api_fact.get(
            "api_score"
        )
    )

    api_stats = (
        api_fact.get(
            "api_stats"
        )
    )

    api_xg = (
        api_fact.get(
            "api_xg"
        )
    )

    if league != "РПЛ":

        if api_status:

            st.success(
                "🤖 Data Football API подключён"
            )

            st.caption(
                "Полученные API-данные "
                "заполняются автоматически."
            )

        else:

            st.info(
                "🤖 Data Football API "
                "не предоставил данные. "
                "Доступен резервный режим через Soccer365."
            )

    # ========================================================
    # SCORE
    # ========================================================

    st.markdown(
        "#### 🏆 Счёт"
    )

    # Если API дал счёт и БД ещё пустая,
    # показываем его как предложенный факт.
    if (
        home_goals is None
        and away_goals is None
        and api_score
    ):

        home_goals = safe_int(
            api_fact.get(
                "home_goals"
            )
        )

        away_goals = safe_int(
            api_fact.get(
                "away_goals"
            )
        )

    score_col1, score_col2, score_col3 = st.columns(
        [2, 1, 1]
    )

    with score_col1:

        score_input = st.text_input(
            "Счёт (X:Y)",
            value=(
                f"{home_goals}:{away_goals}"
                if (
                    home_goals is not None
                    and away_goals is not None
                )
                else ""
            ),
            key=f"{key_prefix}_score_input",
            disabled=score_locked,
            placeholder="Например: 2:1",
        )

    with score_col2:

        if (
            home_goals is not None
            and away_goals is not None
        ):

            st.success(
                "🟢 Счёт получен"
                if api_score
                else "🟢 Счёт введён"
            )

        else:

            st.error(
                "🔴 Счёт не введён"
            )

    with score_col3:

        if st.button(
            "✅ Зафиксировать счёт",
            key=f"{key_prefix}_fix_score",
            disabled=(
                score_locked
                or not score_input.strip()
            ),
            use_container_width=True,
        ):

            normalized_score = clean_score(
                score_input
            )

            if normalized_score is None:

                st.error(
                    "❌ Неверный формат. "
                    "Используйте X:Y."
                )

            else:

                home, away = score_to_tuple(
                    normalized_score
                )

                try:

                    db.update_result(
                        match_id,
                        home,
                        away,
                        lock=False,
                    )

                    st.success(
                        f"✅ Счёт "
                        f"{home}:{away} сохранён."
                    )

                    st.rerun()

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка: {exc}"
                    )

    # ========================================================
    # STATISTICS — SOCCER365
    # ========================================================

    st.markdown(
        "#### 📊 Статистика матча + xG"
    )

    st.caption(
        "Источник: Soccer365"
    )

    # Если API дал статистику, используем её
    stats_from_api = normalize_source_stats(
        api_fact.get(
            "stats",
            {},
        )
    )

    has_api_stats = any(
        value is not None
        for key, value in stats_from_api.items()
        if key not in (
            "home_xg",
            "away_xg",
        )
    )

    # Если API дал xG
    has_api_xg = (
        stats_from_api.get("home_xg") is not None
        or stats_from_api.get("away_xg") is not None
    )

    if has_api_stats or has_api_xg:
        st.success(
            "🟢 Статистика и/или xG получены через API"
        )

    # ========================================================
    # SOCCER365 URL
    # ========================================================

    soccer365_url = st.text_input(
        "🔗 Soccer365",
        key=f"{key_prefix}_soccer365_url",
        placeholder="https://soccer365.ru/games/...",
        disabled=(
            score_locked
            or (has_api_stats and has_api_xg)
        ),
    )

    # ========================================================
    # SOCCER365 FETCH
    # ========================================================

    if st.button(
        "📥 Загрузить статистику Soccer365",
        key=f"{key_prefix}_soccer365_fetch",
        disabled=(
            score_locked
            or (has_api_stats and has_api_xg)
            or not soccer365_url.strip()
        ),
        use_container_width=True,
    ):

        with st.spinner(
            "Загружаем статистику Soccer365..."
        ):

            parsed = parse_soccer365(
                soccer365_url
            )

            st.session_state[
                f"{key_prefix}_soccer365_fact"
            ] = parsed

            if parsed.get(
                "stats"
            ):

                st.success(
                    "🟢 Статистика Soccer365 получена."
                )

            else:

                st.warning(
                    "Статистика Soccer365 не получена."
                )

            st.rerun()

    # ========================================================
    # BUILD HYBRID FACT — БЕЗ BOMBARDIR
    # ========================================================

    soccer365_fact = st.session_state.get(
        f"{key_prefix}_soccer365_fact",
        {},
    )

    manual_home, manual_away = score_to_tuple(
        score_input
    )

    fact = build_hybrid_fact(
        league=league,
        match=match,
        api_fact=api_fact,
        soccer365_fact=soccer365_fact,
        manual_home_goals=manual_home,
        manual_away_goals=manual_away,
    )

    statuses = fact_status(
        fact
    )

    # ========================================================
    # FACT SUMMARY
    # ========================================================

    st.markdown(
        "#### 📋 Состояние фактов"
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Счёт",
            "🟢"
            if statuses["score"]
            else "🔴",
        )

        if fact.get(
            "score_source"
        ):

            st.caption(
                f"Источник: "
                f"{fact['score_source']}"
            )

    with c2:

        st.metric(
            "Статистика",
            "🟢"
            if statuses["stats"]
            else "⚪",
        )

        if fact.get(
            "stats_source"
        ):

            st.caption(
                f"Источник: "
                f"{fact['stats_source']}"
            )

    with c3:

        st.metric(
            "xG",
            "🟢"
            if statuses["xg"]
            else "⚪",
        )

        if fact.get(
            "xg_source"
        ):

            st.caption(
                f"Источник: "
                f"{fact['xg_source']}"
            )

    # ========================================================
    # DISPLAY STATS
    # ========================================================

    stats = fact.get(
        "stats",
        {},
    )

    filtered_rows = []

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
            stats.get("home_shots_on_target"),
            stats.get("away_shots_on_target"),
        ),
        (
            "Владение",
            stats.get("home_possession"),
            stats.get("away_possession"),
        ),
        (
            "Угловые",
            stats.get("home_corners"),
            stats.get("away_corners"),
        ),
        (
            "Передачи",
            stats.get("home_total_passes"),
            stats.get("away_total_passes"),
        ),
        (
            "Точность передач",
            stats.get("home_pass_accuracy"),
            stats.get("away_pass_accuracy"),
        ),
        (
            "Точные передачи",
            stats.get("home_accurate_passes"),
            stats.get("away_accurate_passes"),
        ),
        (
            "Отборы",
            stats.get("home_tackles"),
            stats.get("away_tackles"),
        ),
        (
            "Фолы",
            stats.get("home_fouls"),
            stats.get("away_fouls"),
        ),
        (
            "Жёлтые карточки",
            stats.get("home_yellow_cards"),
            stats.get("away_yellow_cards"),
        ),
        (
            "Красные карточки",
            stats.get("home_red_cards"),
            stats.get("away_red_cards"),
        ),
    ]

    for name, home_value, away_value in stat_rows:

        if (
            home_value is not None
            or away_value is not None
        ):

            filtered_rows.append(
                (
                    name,
                    home_value,
                    away_value,
                )
            )

    if filtered_rows:

        table_data = []

        for (
            name,
            home_value,
            away_value,
        ) in filtered_rows:

            table_data.append(
                {
                    "Показатель": name,
                    home_team:
                        home_value
                        if home_value is not None
                        else "—",
                    away_team:
                        away_value
                        if away_value is not None
                        else "—",
                }
            )

        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # EXPERT
    # ========================================================

    st.markdown(
        "#### 🧠 Экспертный прогноз директора"
    )

    existing_expert_score = ""

    if expert:

        existing_expert_score = (
            clean_score(
                expert.get("score")
                or expert.get(
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
        disabled=score_locked,
    )

    expert_comment = st.text_area(
        "Комментарий эксперта",
        value=(
            expert.get(
                "comment",
                ""
            )
            if expert
            else ""
        ),
        key=f"{key_prefix}_expert_comment",
        disabled=score_locked,
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
        disabled=score_locked,
    )

    # ========================================================
    # COMPARISON
    # ========================================================

    st.markdown(
        "#### 📊 Сравнение"
    )

    actual_score = None

    if (
        fact.get("home_goals") is not None
        and fact.get("away_goals") is not None
    ):

        actual_score = (
            f"{fact['home_goals']}:"
            f"{fact['away_goals']}"
        )

    comparison = [
        {
            "Источник": "FAJ",
            "Счёт":
                extract_prediction_score(
                    prediction
                )
                or "—",
        },
        {
            "Источник": "Эксперт",
            "Счёт":
                clean_score(
                    expert_score_input
                )
                or "—",
        },
        {
            "Источник": "Факт",
            "Счёт":
                actual_score
                or "—",
        },
    ]

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # SAVE
    # ========================================================

    if st.button(
        "✅ Сохранить факты",
        key=f"{key_prefix}_save",
        type="primary",
        use_container_width=True,
        disabled=(
            score_locked
            or not statuses["complete"]
        ),
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
                expert_confidence=(
                    expert_confidence
                ),
            )

            st.success(
                "✅ Факты сохранены "
                "и защищены."
            )

            st.caption(
                f"Match ID: "
                f"{result['match_id']} | "
                f"Validation ID: "
                f"{result['validation_id']} | "
                f"Gold ID: "
                f"{result['gold_id']}"
            )

            # ========================================================
            # АВТОМАТИЧЕСКАЯ СИНХРОНИЗАЦИЯ С GITHUB
            # ========================================================

            with st.spinner("Синхронизация с GitHub..."):
                sync_result = sync_to_github()

                if sync_result.get("error"):
                    st.warning(
                        f"⚠️ Факты сохранены в БД, "
                        f"но синхронизация с GitHub не удалась: "
                        f"{sync_result['error']}"
                    )
                else:
                    st.success(
                        f"✅ База синхронизирована с GitHub. "
                        f"Размер: {sync_result.get('size', 0):,} байт."
                    )

            st.rerun()

        except Exception as exc:

            logger.exception(
                "Ошибка сохранения факта"
            )

            st.error(
                f"❌ Ошибка сохранения: {exc}"
            )

    st.divider()


# ============================================================
# MAIN
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
        f"FAJ Platform {APP_VERSION} | "
        f"Import Facts {IMPORT_FACTS_VERSION}"
    )

    db = get_database()

    # ========================================================
    # HEADER
    # ========================================================

    col1, col2 = st.columns(2)

    with col1:

        league = st.selectbox(
            "🏆 Лига",
            list(LEAGUES.keys()),
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
    # SOURCE INFO
    # ========================================================

    config = SOURCE_CONFIG[
        league
    ]

    if league == "РПЛ":

        st.info(
            "🇷🇺 РПЛ: "
            "счёт — вручную | "
            "статистика + xG — Soccer365"
        )

    else:

        st.info(
            f"🌍 {league}: "
            "Data Football API используется "
            "автоматически при наличии данных. "
            "Если API не отдаёт отдельный факт, "
            "используется Soccer365."
        )

    # ========================================================
    # MATCHES — ЧЕРЕЗ DATABASE.PY
    # ========================================================

    matches = get_round_matches(
        db,
        int(round_number),
        league,
    )

    st.markdown(
        f"## {league} — "
        f"{round_number}-й тур"
    )

    if not matches:

        st.warning(
            "Матчи выбранного тура "
            "не найдены."
        )

        st.stop()

    st.info(
        f"Найдено матчей: "
        f"{len(matches)}"
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
            league=league,
        )

    # ========================================================
    # ОБУЧЕНИЕ — ВРЕМЕННО ОТКЛЮЧЕНО
    # ========================================================

    st.markdown(
        "## 🧠 Обучение"
    )

    st.info(
        "ℹ️ Обучение запускается на странице **'Тур сыгран'** "
        "после завершения тура.\n\n"
        "Перейдите в меню → **🏁 Тур сыгран** → "
        "**🧠 ЗАПУСТИТЬ ОБУЧЕНИЕ ТУРА**."
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
