#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD ALL — RPL DATA & PREDICTION CENTER
============================================================

Назначение:
    Единая точка управления данными РПЛ.

Функции:
    1. Создание/получение сезона
    2. Создание команд
    3. Создание туров (исправлено — идемпотентное)
    4. Загрузка календаря (исправлено — проверка после upsert)
    5. Загрузка результатов исторических туров
    6. Загрузка статистики прошедших матчей (через update_match_stats)
    7. Идемпотентное обновление
    8. Persistent state
    9. Центр прогнозов по турам
   10. Хранение прогнозов по каждому туру
   11. Хранение экспертных прогнозов директора (по турам)
   12. Восстановление состояния после Streamlit rerun

ИСПРАВЛЕНИЯ v12.1:
    - ensure_rounds() — идемпотентная, без зависимости от create_round()
    - Удалена write_match_statistics()
    - Статистика только через db.update_match_stats()
    - get_database_status() — использует matches, а не match_results/match_statistics
    - import_fixtures() — проверка матча после upsert_match()
    - fixtures_loaded — по реально записанным матчам
    - Исторический импорт — обновление только при наличии результата
    - expert_predictions — структура по турам

ВАЖНО:
    database.py НЕ изменяется.
    Нет DELETE/DROP.
    Идемпотентность всех операций.
============================================================
"""

import os
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Optional, Any

import streamlit as st

from app.database import FAJDatabase
from app.passports.passport_manager import get_passport_manager
from app.core.prediction_manager import get_prediction_manager

from app.parsers.rpl_fixtures_parser import RPLFixturesParser

try:
    from app.parsers.rpl_results_parser import RPLResultsParser
except ImportError:
    RPLResultsParser = None


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"

SEASON_NAME = "РПЛ 2026-2027"
SEASON_YEAR = "2026-2027"
LEAGUE = "РПЛ"

TOTAL_ROUNDS = 30

DATA_DIR = "data"
STATE_FILE = os.path.join(
    DATA_DIR,
    "import_state.json",
)

FIXTURES_SOURCE = (
    "championat.com / smart-tables.ru / soccerland.ru"
)

RESULTS_SOURCE = (
    "smart-tables.ru / soccerland.ru"
)

# Исторические туры, которые сейчас загружаем
HISTORICAL_ROUNDS = [1, 2, 3]


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# RPL TEAMS
# ============================================================

RPL_TEAMS = [
    "Зенит",
    "Спартак",
    "ЦСКА",
    "Динамо Москва",
    "Локомотив",
    "Краснодар",
    "Ростов",
    "Ахмат",
    "Рубин",
    "Крылья Советов",
    "Оренбург",
    "Факел",
    "Акрон",
    "Балтика",
    "Родина",
    "Динамо Махачкала",
]


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection(db):
    """
    Единая точка получения SQLite connection.

    ВАЖНО:
        Текущий FAJDatabase имеет публичный метод
        get_connection().

    Не используем приватный _get_connection().
    """

    return db.get_connection()


# ============================================================
# STATE
# ============================================================

def ensure_data_dir():
    os.makedirs(
        DATA_DIR,
        exist_ok=True,
    )


def default_state() -> Dict:
    """
    Persistent состояние FAJ.

    predictions хранится ПО ТУРАМ:

        predictions = {
            "4": {...},
            "5": {...}
        }

    Поэтому прогноз одного тура не уничтожает
    прогноз другого.

    expert_predictions также хранится ПО ТУРАМ:

        expert_predictions = {
            "4": {
                "match_id": {...}
            }
        }
    """

    return {
        "version": APP_VERSION,

        "season": SEASON_NAME,
        "season_id": None,

        "last_import": None,
        "last_import_status": "never",
        "last_import_summary": {},

        "historical_rounds_loaded": [],

        "fixtures_loaded": False,
        "fixtures_last_update": None,

        "predictions": {},

        "last_prediction_round": None,
        "last_prediction_time": None,

        "expert_predictions": {},

        "last_selected_round": 4,
    }


def load_state() -> Dict:
    """
    Загружает persistent state.

    State находится отдельно от st.session_state,
    поэтому Streamlit rerun его не уничтожает.
    """

    ensure_data_dir()

    if not os.path.exists(
        STATE_FILE
    ):
        return default_state()

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        base = default_state()

        if isinstance(
            state,
            dict,
        ):
            base.update(state)

        # ----------------------------------------------------
        # Безопасная нормализация
        # ----------------------------------------------------

        if not isinstance(
            base.get("predictions"),
            dict,
        ):
            base["predictions"] = {}

        if not isinstance(
            base.get("expert_predictions"),
            dict,
        ):
            base["expert_predictions"] = {}

        if not isinstance(
            base.get("historical_rounds_loaded"),
            list,
        ):
            base["historical_rounds_loaded"] = []

        return base

    except Exception as e:

        logger.error(
            "Ошибка чтения state: %s",
            e,
        )

        return default_state()


def save_state(
    state: Dict,
):
    """
    Атомарная запись persistent state.
    """

    ensure_data_dir()

    temp_file = (
        STATE_FILE + ".tmp"
    )

    try:

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_file,
            STATE_FILE,
        )

    except Exception as e:

        logger.error(
            "Ошибка сохранения state: %s",
            e,
        )


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    return FAJDatabase()


def get_or_create_season(
    db,
):

    return db.create_season(
        name=SEASON_NAME,
        league=LEAGUE,
        year=SEASON_YEAR,
    )


def ensure_teams(
    db,
) -> Dict[str, int]:

    team_ids = {}

    for name in RPL_TEAMS:

        try:

            team_id = db.get_team_id(
                name,
                LEAGUE,
            )

            if not team_id:

                db.add_team(
                    name,
                    LEAGUE,
                )

                team_id = db.get_team_id(
                    name,
                    LEAGUE,
                )

            if team_id:

                team_ids[name] = team_id

        except Exception as e:

            logger.error(
                "Ошибка команды %s: %s",
                name,
                e,
            )

    return team_ids


# ============================================================
# ENSURE ROUNDS (ИСПРАВЛЕНО — идемпотентное)
# ============================================================

def ensure_rounds(
    db,
    season_id,
) -> Dict[int, int]:
    """
    Идемпотентное создание туров.

    ИСПРАВЛЕНО: не зависит от create_round(),
    явно проверяет существование каждого тура.
    """

    round_ids = {}

    conn = get_connection(db)

    try:

        cursor = conn.cursor()

        for round_number in range(
            1,
            TOTAL_ROUNDS + 1,
        ):

            try:

                # ----------------------------------------------------
                # Проверяем существование тура
                # ----------------------------------------------------

                cursor.execute(
                    """
                    SELECT id
                    FROM rounds
                    WHERE season_id = ?
                      AND round_number = ?
                    LIMIT 1
                    """,
                    (
                        season_id,
                        round_number,
                    ),
                )

                row = cursor.fetchone()

                if row:

                    round_ids[round_number] = row[0]

                    continue

                # ----------------------------------------------------
                # Создаём тур, если его нет
                # ----------------------------------------------------

                cursor.execute(
                    """
                    INSERT INTO rounds
                    (
                        season_id,
                        round_number
                    )
                    VALUES (?, ?)
                    """,
                    (
                        season_id,
                        round_number,
                    ),
                )

                round_ids[round_number] = cursor.lastrowid

            except Exception as e:

                logger.warning(
                    "Ошибка тура %s: %s",
                    round_number,
                    e,
                )

        conn.commit()

    finally:

        conn.close()

    return round_ids


# ============================================================
# MATCH LOOKUP
# ============================================================

def find_match(
    db,
    season_id,
    round_number,
    home_team_id,
    away_team_id,
):
    """
    Единый lookup матча по календарю.

    НЕ создаёт матч, если он не найден.
    """

    conn = get_connection(db)

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT m.id
            FROM matches m
            JOIN rounds r
                ON r.id = m.round_id
            WHERE r.season_id = ?
              AND r.round_number = ?
              AND m.home_team_id = ?
              AND m.away_team_id = ?
            ORDER BY m.id
            LIMIT 1
            """,
            (
                season_id,
                round_number,
                home_team_id,
                away_team_id,
            ),
        )

        row = cursor.fetchone()

        return row[0] if row else None

    finally:

        conn.close()


# ============================================================
# FIXTURES (ИСПРАВЛЕНО)
# ============================================================

def import_fixtures(
    db,
    season_id,
    team_ids,
    round_ids,
    state,
):

    result = {
        "source": FIXTURES_SOURCE,
        "found": 0,
        "added": 0,
        "updated": 0,
        "errors": 0,
        "unknown_teams": [],
    }

    parser = RPLFixturesParser()

    fixtures = parser.parse()

    if not fixtures:

        state[
            "fixtures_loaded"
        ] = False

        result["message"] = (
            "Парсер календаря не вернул матчи."
        )

        return result

    result["found"] = len(
        fixtures
    )

    for match in fixtures:

        try:

            round_number = int(
                match["round"]
            )

            if round_number not in round_ids:

                result["errors"] += 1
                continue

            home_name = match[
                "home_team"
            ]

            away_name = match[
                "away_team"
            ]

            home_id = team_ids.get(
                home_name
            )

            away_id = team_ids.get(
                away_name
            )

            if not home_id:

                result[
                    "unknown_teams"
                ].append(
                    home_name
                )

                result["errors"] += 1
                continue

            if not away_id:

                result[
                    "unknown_teams"
                ].append(
                    away_name
                )

                result["errors"] += 1
                continue

            # ----------------------------------------------------
            # Проверяем существование матча ДО upsert
            # ----------------------------------------------------

            existing_id = find_match(
                db,
                season_id,
                round_number,
                home_id,
                away_id,
            )

            # ----------------------------------------------------
            # Сохраняем матч
            # ----------------------------------------------------

            payload = {
                "round_id": round_ids[
                    round_number
                ],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": match.get(
                    "date"
                ),
                "competition": LEAGUE,
                "status": match.get(
                    "status",
                    "scheduled",
                ),
            }

            db.upsert_match(
                payload
            )

            # ----------------------------------------------------
            # Проверяем наличие матча ПОСЛЕ upsert
            # (ИСПРАВЛЕНО)
            # ----------------------------------------------------

            new_id = find_match(
                db,
                season_id,
                round_number,
                home_id,
                away_id,
            )

            if existing_id:

                result["updated"] += 1

            elif new_id:

                result["added"] += 1

            else:

                result["errors"] += 1

                logger.warning(
                    "Матч не создан: %s - %s, тур %s",
                    home_name,
                    away_name,
                    round_number,
                )

        except Exception as e:

            result["errors"] += 1

            logger.exception(
                "Ошибка импорта календаря: %s",
                e,
            )

    # --------------------------------------------------------
    # fixtures_loaded считаем по реально записанным матчам
    # (ИСПРАВЛЕНО)
    # --------------------------------------------------------

    successful_fixtures = (
        result["added"]
        + result["updated"]
    )

    state["fixtures_loaded"] = (
        result["found"] > 0
        and successful_fixtures > 0
    )

    if state["fixtures_loaded"]:

        state[
            "fixtures_last_update"
        ] = datetime.now().isoformat()

    return result


# ============================================================
# RESULT PARSER
# ============================================================

def create_results_parser():

    if RPLResultsParser is None:

        return None

    try:

        return RPLResultsParser()

    except TypeError:

        try:

            return RPLResultsParser(
                season=SEASON_YEAR
            )

        except Exception:

            return None


def normalize_result_item(
    item: Dict,
) -> Optional[Dict]:
    """
    Приводит parser output к единому формату.
    """

    if not isinstance(
        item,
        dict,
    ):

        return None

    home = (
        item.get("home_team")
        or item.get("home")
        or item.get("home_name")
    )

    away = (
        item.get("away_team")
        or item.get("away")
        or item.get("away_name")
    )

    if not home or not away:

        return None

    round_number = (
        item.get("round")
        or item.get("round_number")
        or item.get("tour")
    )

    if round_number is None:

        return None

    normalized = dict(
        item
    )

    normalized[
        "round"
    ] = int(
        round_number
    )

    normalized[
        "home_team"
    ] = home

    normalized[
        "away_team"
    ] = away

    return normalized


# ============================================================
# HISTORICAL RESULTS (ИСПРАВЛЕНО)
# ============================================================

def import_historical_results(
    db,
    season_id,
    team_ids,
    rounds=(1, 2, 3),
):

    rounds = [
        int(x)
        for x in rounds
    ]

    result = {
        "source": RESULTS_SOURCE,
        "rounds": rounds,
        "found": 0,
        "updated": 0,
        "errors": 0,
        "skipped": 0,
        "matches_without_db_record": 0,
        "rounds_updated": [],
        "message": "",
    }

    parser = create_results_parser()

    if parser is None:

        result["skipped"] = 1

        result["message"] = (
            "RPLResultsParser недоступен."
        )

        return result

    if not hasattr(
        parser,
        "parse_rounds",
    ):

        result["skipped"] = 1

        result["message"] = (
            "RPLResultsParser не имеет "
            "метода parse_rounds()."
        )

        return result

    try:

        raw_matches = (
            parser.parse_rounds(
                season=SEASON_YEAR,
                rounds=rounds,
            )
        )

    except TypeError:

        try:

            raw_matches = (
                parser.parse_rounds(
                    rounds=rounds
                )
            )

        except Exception as e:

            result["errors"] += 1

            result["message"] = str(
                e
            )

            logger.exception(
                "Ошибка parse_rounds"
            )

            return result

    except Exception as e:

        result["errors"] += 1

        result["message"] = str(
            e
        )

        logger.exception(
            "Ошибка исторического parser"
        )

        return result

    if not raw_matches:

        result["message"] = (
            "Парсер не вернул исторические матчи."
        )

        return result

    result["found"] = len(
        raw_matches
    )

    actually_updated_rounds = set()

    for raw_item in raw_matches:

        try:

            item = normalize_result_item(
                raw_item
            )

            if not item:

                result["errors"] += 1
                continue

            round_number = int(
                item["round"]
            )

            if round_number not in rounds:

                result["skipped"] += 1
                continue

            home_name = item[
                "home_team"
            ]

            away_name = item[
                "away_team"
            ]

            home_id = team_ids.get(
                home_name
            )

            away_id = team_ids.get(
                away_name
            )

            if not home_id or not away_id:

                result["errors"] += 1

                logger.warning(
                    "Неизвестные команды: %s - %s",
                    home_name,
                    away_name,
                )

                continue

            match_id = find_match(
                db=db,
                season_id=season_id,
                round_number=round_number,
                home_team_id=home_id,
                away_team_id=away_id,
            )

            if not match_id:

                result[
                    "matches_without_db_record"
                ] += 1

                logger.warning(
                    "Матч не найден в БД: "
                    "%s - %s, тур %s",
                    home_name,
                    away_name,
                    round_number,
                )

                continue

            # ------------------------------------------------
            # РЕЗУЛЬТАТ (только если есть)
            # (ИСПРАВЛЕНО)
            # ------------------------------------------------

            home_goals = item.get(
                "home_goals"
            )

            away_goals = item.get(
                "away_goals"
            )

            has_result = (
                home_goals is not None
                and away_goals is not None
            )

            if has_result:

                db.update_result(
                    match_id,
                    int(home_goals),
                    int(away_goals),
                )

                result["updated"] += 1

                actually_updated_rounds.add(
                    round_number
                )

            else:

                result["skipped"] += 1

                logger.warning(
                    "Матч %s - %s, тур %s "
                    "не содержит результата.",
                    home_name,
                    away_name,
                    round_number,
                )

            # ------------------------------------------------
            # СТАТИСТИКА (всегда через update_match_stats)
            # (ИСПРАВЛЕНО)
            # ------------------------------------------------

            stats_payload = {
                "home_xg": item.get(
                    "home_xg"
                ),
                "away_xg": item.get(
                    "away_xg"
                ),
                "home_possession": item.get(
                    "home_possession"
                ),
                "away_possession": item.get(
                    "away_possession"
                ),
                "home_shots": item.get(
                    "home_shots"
                ),
                "away_shots": item.get(
                    "away_shots"
                ),
                "home_shots_on_target": item.get(
                    "home_shots_on_target"
                ),
                "away_shots_on_target": item.get(
                    "away_shots_on_target"
                ),
                "home_corners": item.get(
                    "home_corners"
                ),
                "away_corners": item.get(
                    "away_corners"
                ),
                "home_yellow_cards": item.get(
                    "home_yellow_cards"
                ),
                "away_yellow_cards": item.get(
                    "away_yellow_cards"
                ),
                "home_pass_accuracy": item.get(
                    "home_pass_accuracy"
                ),
                "away_pass_accuracy": item.get(
                    "away_pass_accuracy"
                ),
                "parser_source": RESULTS_SOURCE,
                "parser_version": APP_VERSION,
                "data_quality": 1.0,
            }

            try:

                db.update_match_stats(
                    match_id,
                    stats_payload,
                )

            except Exception as e:

                logger.warning(
                    "Не удалось записать статистику "
                    "match_id=%s: %s",
                    match_id,
                    e,
                )

        except Exception as e:

            result["errors"] += 1

            logger.exception(
                "Ошибка исторического матча"
            )

    result[
        "rounds_updated"
    ] = sorted(
        actually_updated_rounds
    )

    return result


# ============================================================
# MATCH STATISTICS (УДАЛЕНА)
# ============================================================

# write_match_statistics() полностью удалена.
# Статистика теперь пишется только через db.update_match_stats().


# ============================================================
# PASSPORTS
# ============================================================

def ensure_passports(
    db,
    season_id,
):

    result = {
        "created": 0,
        "existing": 0,
        "errors": 0,
    }

    pm = get_passport_manager()

    teams = db.get_teams(
        LEAGUE
    )

    for team in teams:

        try:

            existing = (
                pm.get_current_passport(
                    team["id"],
                    season_id,
                )
            )

            if existing:

                result["existing"] += 1
                continue

            pm.create_passport(
                team_id=team["id"],
                season_id=season_id,
                data={
                    "attack": 50,
                    "defense": 50,
                    "control": 50,
                    "tempo": 50,
                    "press": 50,
                    "transition": 50,
                    "finishing": 50,
                    "goalkeeper": 50,
                    "discipline": 50,
                    "squad_quality": 50,
                    "bench_quality": 50,
                    "coach_factor": 50,
                    "mental": 50,
                    "home_strength": 50,
                    "away_strength": 50,
                    "injury_factor": 50,
                    "key_player_loss": 50,
                    "league_adaptation": 80,
                    "form": 50,
                },
                source="load_all_v12.1",
            )

            result["created"] += 1

        except Exception as e:

            result["errors"] += 1

            logger.exception(
                "Ошибка паспорта %s",
                team.get("name"),
            )

    return result


# ============================================================
# DATABASE STATUS (ИСПРАВЛЕНО)
# ============================================================

def get_database_status(
    db,
):
    """
    Статус БД без match_results и match_statistics.

    ИСПРАВЛЕНО: использует matches как единый источник.
    """

    result = {}

    conn = get_connection(
        db
    )

    try:

        cursor = conn.cursor()

        queries = {
            "matches": """
                SELECT COUNT(*)
                FROM matches
            """,
            "results": """
                SELECT COUNT(*)
                FROM matches
                WHERE actual_home IS NOT NULL
                  AND actual_away IS NOT NULL
            """,
            "statistics": """
                SELECT COUNT(*)
                FROM matches
                WHERE
                    home_xg IS NOT NULL
                    OR away_xg IS NOT NULL
                    OR home_possession IS NOT NULL
                    OR away_possession IS NOT NULL
                    OR home_shots IS NOT NULL
                    OR away_shots IS NOT NULL
            """,
            "passports": """
                SELECT COUNT(*)
                FROM team_passports
            """,
        }

        for key, query in queries.items():

            try:

                cursor.execute(
                    query
                )

                row = cursor.fetchone()

                result[key] = (
                    row[0]
                    if row
                    else 0
                )

            except Exception:

                result[key] = 0

    finally:

        conn.close()

    return result


# ============================================================
# ROUND MATCHES
# ============================================================

def get_round_matches(
    db,
    season_id,
    round_number,
):

    conn = get_connection(
        db
    )

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                m.id,
                th.name AS home,
                ta.name AS away,
                m.date,
                m.status
            FROM matches m
            JOIN rounds r
                ON r.id = m.round_id
            JOIN teams th
                ON th.id = m.home_team_id
            JOIN teams ta
                ON ta.id = m.away_team_id
            WHERE r.season_id = ?
              AND r.round_number = ?
            ORDER BY m.date, m.id
            """,
            (
                season_id,
                round_number,
            ),
        )

        return cursor.fetchall()

    finally:

        conn.close()


# ============================================================
# PREDICTIONS
# ============================================================

def get_saved_round_prediction(
    state,
    round_number,
):

    predictions = state.get(
        "predictions",
        {},
    )

    return predictions.get(
        str(round_number),
        {},
    )


def run_predictions(
    db,
    season_id,
    round_number,
    state,
):

    matches = get_round_matches(
        db,
        season_id,
        round_number,
    )

    if not matches:

        return {
            "status": "error",
            "message": (
                f"Матчи {round_number}-го "
                f"тура не найдены."
            ),
        }

    pm = get_prediction_manager()

    predictions = {}

    for row in matches:

        match_id = row[0]
        home = row[1]
        away = row[2]
        date = row[3]
        status = row[4]

        try:

            if hasattr(
                pm,
                "predict_by_match_id",
            ):

                prediction = (
                    pm.predict_by_match_id(
                        match_id
                    )
                )

            else:

                prediction = pm.predict(
                    home_team=home,
                    away_team=away,
                    league=LEAGUE,
                    season_id=season_id,
                )

            predictions[
                str(match_id)
            ] = {
                "match_id": match_id,
                "home": home,
                "away": away,
                "date": date,
                "status": status,
                "result": prediction,
                "created_at": (
                    datetime.now()
                    .isoformat()
                ),
            }

        except Exception as e:

            logger.exception(
                "Ошибка прогноза "
                "match_id=%s",
                match_id,
            )

            predictions[
                str(match_id)
            ] = {
                "match_id": match_id,
                "home": home,
                "away": away,
                "date": date,
                "status": status,
                "error": str(e),
                "created_at": (
                    datetime.now()
                    .isoformat()
                ),
            }

    # --------------------------------------------------------
    # Сохраняем именно выбранный тур
    # --------------------------------------------------------

    state.setdefault(
        "predictions",
        {},
    )

    state[
        "predictions"
    ][str(round_number)] = {
        "round": round_number,
        "season": SEASON_NAME,
        "created_at": (
            datetime.now()
            .isoformat()
        ),
        "matches": predictions,
    }

    state[
        "last_prediction_round"
    ] = round_number

    state[
        "last_prediction_time"
    ] = datetime.now().isoformat()

    state[
        "last_selected_round"
    ] = round_number

    save_state(
        state
    )

    return {
        "status": "ok",
        "round": round_number,
        "count": len(
            predictions
        ),
        "predictions": predictions,
    }


# ============================================================
# IMPORT WORKFLOW
# ============================================================

def run_full_import(
    state,
):

    db = get_db()

    log = {
        "started_at": datetime.now().isoformat(),
        "fixtures": {},
        "historical": {},
        "passports": {},
        "status": "running",
    }

    try:

        # ----------------------------------------------------
        # 1. SEASON
        # ----------------------------------------------------

        season_id = (
            get_or_create_season(
                db
            )
        )

        state[
            "season_id"
        ] = season_id

        # ----------------------------------------------------
        # 2. TEAMS
        # ----------------------------------------------------

        team_ids = ensure_teams(
            db
        )

        # ----------------------------------------------------
        # 3. ROUNDS (исправлено)
        # ----------------------------------------------------

        round_ids = ensure_rounds(
            db,
            season_id,
        )

        # ----------------------------------------------------
        # 4. FIXTURES (исправлено)
        # ----------------------------------------------------

        with st.spinner(
            "📅 Загружаем календарь РПЛ..."
        ):

            fixture_result = (
                import_fixtures(
                    db=db,
                    season_id=season_id,
                    team_ids=team_ids,
                    round_ids=round_ids,
                    state=state,
                )
            )

        log[
            "fixtures"
        ] = fixture_result

        # ----------------------------------------------------
        # 5. HISTORICAL (исправлено)
        # ----------------------------------------------------

        with st.spinner(
            "📊 Загружаем результаты "
            "и статистику 1–3 туров..."
        ):

            historical_result = (
                import_historical_results(
                    db=db,
                    season_id=season_id,
                    team_ids=team_ids,
                    rounds=HISTORICAL_ROUNDS,
                )
            )

        log[
            "historical"
        ] = historical_result

        loaded_rounds = (
            historical_result.get(
                "rounds_updated",
                [],
            )
        )

        # ----------------------------------------------------
        # НЕ СТИРАЕМ УЖЕ ЗАГРУЖЕННЫЕ
        # ----------------------------------------------------

        existing_historical = set(
            int(x)
            for x in state.get(
                "historical_rounds_loaded",
                [],
            )
        )

        existing_historical.update(
            int(x)
            for x in loaded_rounds
        )

        state[
            "historical_rounds_loaded"
        ] = sorted(
            existing_historical
        )

        # ----------------------------------------------------
        # 6. PASSPORTS
        # ----------------------------------------------------

        with st.spinner(
            "📋 Проверяем паспорта команд..."
        ):

            passport_result = (
                ensure_passports(
                    db=db,
                    season_id=season_id,
                )
            )

        log[
            "passports"
        ] = passport_result

        # ----------------------------------------------------
        # 7. STATE
        # ----------------------------------------------------

        log["status"] = "success"

        log[
            "finished_at"
        ] = datetime.now().isoformat()

        state[
            "last_import"
        ] = datetime.now().isoformat()

        state[
            "last_import_status"
        ] = "success"

        state[
            "last_import_summary"
        ] = log

        save_state(
            state
        )

        return log

    except Exception as e:

        log[
            "status"
        ] = "error"

        log[
            "error"
        ] = str(e)

        log[
            "traceback"
        ] = traceback.format_exc()

        state[
            "last_import"
        ] = datetime.now().isoformat()

        state[
            "last_import_status"
        ] = "error"

        state[
            "last_import_summary"
        ] = log

        save_state(
            state
        )

        raise


# ============================================================
# UI — STATE
# ============================================================

def render_state(
    state,
):

    st.subheader(
        "🧠 Состояние FAJ"
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        status = state.get(
            "last_import_status",
            "never",
        )

        if status == "success":

            st.metric(
                "Импорт",
                "OK",
            )

        elif status == "error":

            st.metric(
                "Импорт",
                "ОШИБКА",
            )

        else:

            st.metric(
                "Импорт",
                "Не запускался",
            )

    with col2:

        loaded = state.get(
            "historical_rounds_loaded",
            [],
        )

        st.metric(
            "История",
            f"{len(loaded)}/3",
        )

        if loaded:

            st.caption(
                "Загружены: "
                + ", ".join(
                    str(x)
                    for x in loaded
                )
                + " туры"
            )

    with col3:

        last_round = state.get(
            "last_prediction_round"
        )

        st.metric(
            "Последний прогноз",
            (
                f"{last_round}-й тур"
                if last_round
                else "—"
            ),
        )

    with col4:

        last_import = state.get(
            "last_import"
        )

        if last_import:

            try:

                dt = datetime.fromisoformat(
                    last_import
                )

                value = dt.strftime(
                    "%d.%m %H:%M"
                )

            except Exception:

                value = "есть"

        else:

            value = "—"

        st.metric(
            "Последнее обновление",
            value,
        )


# ============================================================
# UI — IMPORT REPORT
# ============================================================

def render_import_report(
    log,
):

    if not log:

        return

    st.divider()

    st.subheader(
        "📋 Результат последней загрузки"
    )

    fixtures = log.get(
        "fixtures",
        {},
    )

    historical = log.get(
        "historical",
        {},
    )

    passports = log.get(
        "passports",
        {},
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "📅 Календарь",
            fixtures.get(
                "found",
                0,
            ),
        )

        st.caption(
            f"➕ {fixtures.get('added', 0)} "
            f"· 🔄 {fixtures.get('updated', 0)} "
            f"· ❌ {fixtures.get('errors', 0)}"
        )

    with c2:

        st.metric(
            "📊 История",
            historical.get(
                "updated",
                0,
            ),
        )

        st.caption(
            f"Найдено: "
            f"{historical.get('found', 0)}"
        )

        rounds = historical.get(
            "rounds_updated",
            [],
        )

        if rounds:

            st.caption(
                "Туры: "
                + ", ".join(
                    str(x)
                    for x in rounds
                )
            )

        elif historical.get(
            "message"
        ):

            st.warning(
                historical[
                    "message"
                ]
            )

    with c3:

        st.metric(
            "📋 Паспорта",
            passports.get(
                "created",
                0,
            )
            + passports.get(
                "existing",
                0,
            ),
        )

        st.caption(
            f"Создано: "
            f"{passports.get('created', 0)} "
            f"· Есть: "
            f"{passports.get('existing', 0)}"
        )


# ============================================================
# UI — SAVED PREDICTION
# ============================================================

def render_saved_prediction_round(
    state,
    round_number,
):

    saved = get_saved_round_prediction(
        state,
        round_number,
    )

    if not saved:

        return

    st.success(
        f"✅ Прогноз {round_number}-го "
        f"тура уже сохранён."
    )

    created_at = saved.get(
        "created_at"
    )

    if created_at:

        try:

            dt = datetime.fromisoformat(
                created_at
            )

            st.caption(
                "Создан: "
                + dt.strftime(
                    "%d.%m.%Y %H:%M"
                )
            )

        except Exception:

            pass

    matches = saved.get(
        "matches",
        {},
    )

    for prediction in matches.values():

        home = prediction.get(
            "home",
            "?",
        )

        away = prediction.get(
            "away",
            "?",
        )

        if "error" in prediction:

            st.error(
                f"{home} — {away}: "
                f"{prediction['error']}"
            )

            continue

        result = prediction.get(
            "result",
            {},
        )

        xg = result.get(
            "xg",
            {},
        )

        probability = result.get(
            "probability",
            {},
        )

        score = result.get(
            "score",
            "—",
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        with c1:

            st.write(
                f"**{home}**"
            )

        with c2:

            st.write(
                f"**{away}**"
            )

        with c3:

            if xg:

                st.metric(
                    "xG",
                    f"{xg.get('home', 0):.2f} : "
                    f"{xg.get('away', 0):.2f}",
                )

        with c4:

            st.metric(
                "Прогноз",
                score,
            )

        if probability:

            st.caption(
                "П1 "
                f"{probability.get('home', 0) * 100:.1f}% "
                "· X "
                f"{probability.get('draw', 0) * 100:.1f}% "
                "· П2 "
                f"{probability.get('away', 0) * 100:.1f}%"
            )


# ============================================================
# UI — EXPERT PREDICTIONS (ИСПРАВЛЕНО — по турам)
# ============================================================

def render_expert_predictions(
    state,
    db,
    season_id,
    round_number,
):

    st.subheader(
        "🧠 Экспертный прогноз директора"
    )

    st.caption(
        "Личный прогноз хранится отдельно "
        "от прогноза модели FAJ."
    )

    matches = get_round_matches(
        db,
        season_id,
        round_number,
    )

    if not matches:

        st.warning(
            "Матчи выбранного тура "
            "не найдены."
        )

        return

    state.setdefault(
        "expert_predictions",
        {},
    )

    # Инициализируем тур в expert_predictions
    state["expert_predictions"].setdefault(
        str(round_number),
        {},
    )

    for row in matches:

        match_id = row[0]
        home = row[1]
        away = row[2]

        # Получаем существующий прогноз для этого матча
        existing = state["expert_predictions"][str(round_number)].get(
            str(match_id),
            {},
        )

        st.markdown(
            f"### {home} — {away}"
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            expert_result = st.text_input(
                "Исход",
                value=existing.get(
                    "result",
                    "",
                ),
                key=(
                    f"expert_result_"
                    f"{round_number}_"
                    f"{match_id}"
                ),
                placeholder="П1 / X / П2",
            )

        with c2:

            expert_score = st.text_input(
                "Точный счёт",
                value=existing.get(
                    "score",
                    "",
                ),
                key=(
                    f"expert_score_"
                    f"{round_number}_"
                    f"{match_id}"
                ),
                placeholder="2:1",
            )

        with c3:

            expert_comment = st.text_input(
                "Комментарий",
                value=existing.get(
                    "comment",
                    "",
                ),
                key=(
                    f"expert_comment_"
                    f"{round_number}_"
                    f"{match_id}"
                ),
            )

        if st.button(
            "💾 Сохранить прогноз",
            key=(
                f"save_expert_"
                f"{round_number}_"
                f"{match_id}"
            ),
        ):

            # Сохраняем по турам (ИСПРАВЛЕНО)
            state["expert_predictions"][str(round_number)][str(match_id)] = {
                "match_id": match_id,
                "round": round_number,
                "home": home,
                "away": away,
                "result": expert_result,
                "score": expert_score,
                "comment": expert_comment,
                "created_at": (
                    datetime.now()
                    .isoformat()
                ),
            }

            save_state(
                state
            )

            st.success(
                "✅ Экспертный прогноз "
                "сохранён."
            )


# ============================================================
# MAIN
# ============================================================

def main():

    st.set_page_config(
        page_title=(
            "FAJ — Центр данных "
            "и прогнозов"
        ),
        page_icon="📥",
        layout="wide",
    )

    st.title(
        "📥 FAJ — ЦЕНТР ДАННЫХ И ПРОГНОЗОВ"
    )

    st.caption(
        f"FAJ Platform v{APP_VERSION} · "
        f"{SEASON_NAME}"
    )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state = load_state()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    render_state(
        state
    )

    # --------------------------------------------------------
    # IMPORT
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "⚙️ Управление данными"
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        import_clicked = st.button(
            "🔥 СИНХРОНИЗИРОВАТЬ ДАННЫЕ",
            type="primary",
            use_container_width=True,
        )

    with c2:

        historical_clicked = st.button(
            "📊 ЗАГРУЗИТЬ 1–3 ТУРА",
            use_container_width=True,
        )

    with c3:

        refresh_clicked = st.button(
            "🔄 ОБНОВИТЬ",
            use_container_width=True,
        )

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    if refresh_clicked:

        st.rerun()

    # --------------------------------------------------------
    # FULL IMPORT
    # --------------------------------------------------------

    if import_clicked:

        try:

            with st.spinner(
                "FAJ выполняет полный цикл..."
            ):

                log = run_full_import(
                    state
                )

            st.success(
                "✅ Синхронизация завершена."
            )

            render_import_report(
                log
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"❌ Ошибка синхронизации: {e}"
            )

            st.code(
                traceback.format_exc()
            )

    # --------------------------------------------------------
    # HISTORICAL ONLY
    # --------------------------------------------------------

    if historical_clicked:

        db = get_db()

        try:

            season_id = (
                get_or_create_season(
                    db
                )
            )

            state[
                "season_id"
            ] = season_id

            team_ids = ensure_teams(
                db
            )

            ensure_rounds(
                db,
                season_id,
            )

            with st.spinner(
                "📊 Загружаем "
                "прошедшие 1–3 туры..."
            ):

                result = (
                    import_historical_results(
                        db=db,
                        season_id=season_id,
                        team_ids=team_ids,
                        rounds=HISTORICAL_ROUNDS,
                    )
                )

            loaded_rounds = result.get(
                "rounds_updated",
                [],
            )

            # Не уничтожаем предыдущие
            # успешно загруженные туры.

            existing_historical = set(
                int(x)
                for x in state.get(
                    "historical_rounds_loaded",
                    [],
                )
            )

            existing_historical.update(
                int(x)
                for x in loaded_rounds
            )

            state[
                "historical_rounds_loaded"
            ] = sorted(
                existing_historical
            )

            state[
                "last_import"
            ] = datetime.now().isoformat()

            state[
                "last_import_status"
            ] = (
                "success"
                if loaded_rounds
                else "error"
            )

            state[
                "last_import_summary"
            ] = {
                "historical": result
            }

            save_state(
                state
            )

            if loaded_rounds:

                st.success(
                    "✅ Загружены/обновлены туры: "
                    + ", ".join(
                        str(x)
                        for x in loaded_rounds
                    )
                )

            else:

                st.warning(
                    "⚠️ Исторические данные "
                    "не были загружены."
                )

            st.json(
                result
            )

        except Exception as e:

            st.error(
                f"❌ Ошибка: {e}"
            )

            st.code(
                traceback.format_exc()
            )

    # --------------------------------------------------------
    # DATABASE STATUS (исправлено)
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "📊 Состояние базы данных"
    )

    try:

        db = get_db()

        db_status = (
            get_database_status(
                db
            )
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        with c1:

            st.metric(
                "Матчи",
                db_status.get(
                    "matches",
                    0,
                ),
            )

        with c2:

            st.metric(
                "Результаты",
                db_status.get(
                    "results",
                    0,
                ),
            )

        with c3:

            st.metric(
                "Статистика",
                db_status.get(
                    "statistics",
                    0,
                ),
            )

        with c4:

            st.metric(
                "Паспорта",
                db_status.get(
                    "passports",
                    0,
                ),
            )

    except Exception as e:

        st.warning(
            "Не удалось получить "
            f"статус БД: {e}"
        )

    # --------------------------------------------------------
    # IMPORT LOG
    # --------------------------------------------------------

    if state.get(
        "last_import_summary"
    ):

        render_import_report(
            state[
                "last_import_summary"
            ]
        )

        with st.expander(
            "📜 Полный журнал",
            expanded=False,
        ):

            st.json(
                state[
                    "last_import_summary"
                ]
            )

    # --------------------------------------------------------
    # PREDICTION CENTER
    # --------------------------------------------------------

    st.divider()

    st.header(
        "🔮 ЦЕНТР ПРОГНОЗОВ"
    )

    st.info(
        """
        Исторические туры используются FAJ
        как фактическая база.

        Для будущего тура создаётся отдельный
        прогноз.

        Уже сохранённые прогнозы по другим
        турам не перезаписываются.
        """
    )

    try:

        db = get_db()

        season_id = state.get(
            "season_id"
        )

        if not season_id:

            season_id = (
                get_or_create_season(
                    db
                )
            )

            state[
                "season_id"
            ] = season_id

            save_state(
                state
            )

        default_round = state.get(
            "last_selected_round",
            4,
        )

        try:

            default_round = int(
                default_round
            )

        except Exception:

            default_round = 4

        if not (
            1
            <= default_round
            <= TOTAL_ROUNDS
        ):

            default_round = 4

        selected_round = st.selectbox(
            "🎯 Выберите тур",
            options=list(
                range(
                    1,
                    TOTAL_ROUNDS + 1,
                )
            ),
            index=(
                default_round - 1
            ),
            key="prediction_round",
        )

        state[
            "last_selected_round"
        ] = selected_round

        save_state(
            state
        )

        # ----------------------------------------------------
        # HISTORY STATUS
        # ----------------------------------------------------

        loaded_rounds = [
            int(x)
            for x in state.get(
                "historical_rounds_loaded",
                [],
            )
        ]

        if selected_round in loaded_rounds:

            st.success(
                f"📚 {selected_round}-й тур "
                "есть в исторической базе."
            )

        elif selected_round <= 3:

            st.warning(
                f"⚠️ {selected_round}-й тур "
                "ещё не отмечен как загруженный."
            )

        else:

            st.info(
                f"🔮 {selected_round}-й тур "
                "рассматривается как будущий."
            )

        # ----------------------------------------------------
        # MATCH LIST
        # ----------------------------------------------------

        round_matches = (
            get_round_matches(
                db,
                season_id,
                selected_round,
            )
        )

        st.write(
            f"Матчей в {selected_round}-м туре: "
            f"**{len(round_matches)}**"
        )

        if round_matches:

            for row in round_matches:

                match_id = row[0]
                home = row[1]
                away = row[2]
                date = row[3]
                status = row[4]

                c1, c2, c3 = (
                    st.columns(
                        [4, 4, 2]
                    )
                )

                with c1:

                    st.write(
                        f"**{home}**"
                    )

                with c2:

                    st.write(
                        f"**{away}**"
                    )

                with c3:

                    st.caption(
                        f"{date or ''}"
                    )

        else:

            st.warning(
                "Матчи выбранного тура "
                "в базе не найдены."
            )

        # ----------------------------------------------------
        # EXISTING PREDICTION
        # ----------------------------------------------------

        saved_round = (
            get_saved_round_prediction(
                state,
                selected_round,
            )
        )

        if saved_round:

            with st.expander(
                "📚 Уже сохранённый прогноз",
                expanded=True,
            ):

                render_saved_prediction_round(
                    state,
                    selected_round,
                )

        # ----------------------------------------------------
        # RUN
        # ----------------------------------------------------

        button_label = (
            f"🚀 "
            f"{'ПЕРЕСЧИТАТЬ' if saved_round else 'СОЗДАТЬ'} "
            f"ПРОГНОЗЫ НА "
            f"{selected_round}-Й ТУР"
        )

        if st.button(
            button_label,
            type="primary",
            use_container_width=True,
        ):

            with st.spinner(
                f"FAJ рассчитывает "
                f"{selected_round}-й тур..."
            ):

                prediction_result = (
                    run_predictions(
                        db=db,
                        season_id=season_id,
                        round_number=selected_round,
                        state=state,
                    )
                )

            if (
                prediction_result[
                    "status"
                ]
                == "ok"
            ):

                st.success(
                    "✅ Прогноз рассчитан "
                    "и сохранён."
                )

                st.rerun()

            else:

                st.error(
                    prediction_result[
                        "message"
                    ]
                )

    except Exception as e:

        st.error(
            f"❌ Prediction Center: {e}"
        )

        st.code(
            traceback.format_exc()
        )

    # --------------------------------------------------------
    # EXPERT PREDICTION (исправлено)
    # --------------------------------------------------------

    st.divider()

    try:

        current_round = state.get(
            "last_selected_round",
            4,
        )

        try:

            current_round = int(
                current_round
            )

        except Exception:

            current_round = 4

        if not (
            1
            <= current_round
            <= TOTAL_ROUNDS
        ):

            current_round = 4

        expert_round = st.selectbox(
            "🧠 Тур для экспертного прогноза",
            options=list(
                range(
                    1,
                    TOTAL_ROUNDS + 1,
                )
            ),
            index=(
                current_round - 1
            ),
            key="expert_round",
        )

        render_expert_predictions(
            state=state,
            db=get_db(),
            season_id=state.get(
                "season_id"
            ),
            round_number=expert_round,
        )

    except Exception as e:

        st.error(
            f"❌ Expert Center: {e}"
        )

    # --------------------------------------------------------
    # SAVED ROUNDS
    # --------------------------------------------------------

    predictions = state.get(
        "predictions",
        {},
    )

    if predictions:

        st.divider()

        st.subheader(
            "📚 Архив прогнозов"
        )

        saved_round_numbers = sorted(
            [
                int(x)
                for x in predictions.keys()
                if str(x).isdigit()
            ]
        )

        st.write(
            "Сохранённые туры: "
            + ", ".join(
                str(x)
                for x in saved_round_numbers
            )
        )

        archive_round = st.selectbox(
            "Открыть сохранённый прогноз",
            options=saved_round_numbers,
            key="archive_round",
        )

        render_saved_prediction_round(
            state,
            archive_round,
        )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.divider()

    st.caption(
        "FAJ Platform v12.1 · "
        "SQLite · Persistent State · "
        "RPL 2026/27"
    )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    main()
