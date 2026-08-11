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
    3. Создание туров
    4. Загрузка календаря
    5. Загрузка результатов 1–3 туров
    6. Загрузка статистики прошедших матчей
    7. Идемпотентное обновление
    8. Persistent state
    9. Центр прогнозов по турам
   10. Хранение прогнозов по каждому туру
   11. Хранение экспертных прогнозов директора
   12. Восстановление состояния после Streamlit rerun

ВАЖНО:
    database.py НЕ изменяется.
============================================================
"""

import os
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any

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
STATE_FILE = os.path.join(DATA_DIR, "import_state.json")

FIXTURES_SOURCE = (
    "championat.com / smart-tables.ru / soccerland.ru"
)

RESULTS_SOURCE = (
    "smart-tables.ru / soccerland.ru"
)

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
# STATE
# ============================================================

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def default_state() -> Dict:
    """
    Persistent состояние FAJ.

    Важный момент:
        predictions хранится ПО ТУРАМ.

    Было:
        predictions = {...}

    Теперь:
        predictions = {
            "4": {...},
            "5": {...}
        }

    Поэтому прогноз 5-го тура не уничтожает прогноз 4-го.
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

    Это отдельный файл, а не st.session_state.

    Поэтому обычный Streamlit rerun не обнуляет состояние.
    """

    ensure_data_dir()

    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        base = default_state()
        base.update(state)

        # ----------------------------------------------------
        # Миграция старого формата predictions
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


def save_state(state: Dict):
    """
    Атомарная запись persistent state.
    """

    ensure_data_dir()

    temp_file = STATE_FILE + ".tmp"

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
# DATABASE
# ============================================================

def get_db():
    return FAJDatabase()


def get_or_create_season(db):

    return db.create_season(
        name=SEASON_NAME,
        league=LEAGUE,
        year=SEASON_YEAR,
    )


def ensure_teams(db) -> Dict[str, int]:

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


def ensure_rounds(
    db,
    season_id,
) -> Dict[int, int]:

    round_ids = {}

    for round_number in range(
        1,
        TOTAL_ROUNDS + 1,
    ):

        try:

            round_id = db.create_round(
                season_id,
                round_number,
            )

            if round_id:
                round_ids[
                    round_number
                ] = round_id

        except Exception as e:

            logger.warning(
                "Ошибка тура %s: %s",
                round_number,
                e,
            )

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

    conn = db._get_connection()

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

        if row:
            return row[0]

        return None

    finally:
        conn.close()


# ============================================================
# FIXTURES
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
        state["fixtures_loaded"] = False

        result["message"] = (
            "Парсер календаря не вернул матчи."
        )

        return result

    result["found"] = len(fixtures)

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

            existing_id = find_match(
                db,
                season_id,
                round_number,
                home_id,
                away_id,
            )

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

            db.upsert_match(payload)

            if existing_id:

                result["updated"] += 1

            else:

                result["added"] += 1

        except Exception as e:

            result["errors"] += 1

            logger.exception(
                "Ошибка импорта календаря: %s",
                e,
            )

    if result["found"] > 0:

        state[
            "fixtures_loaded"
        ] = True

        state[
            "fixtures_last_update"
        ] = datetime.now().isoformat()

    return result


# ============================================================
# RESULT PARSER ADAPTER
# ============================================================

def create_results_parser():

    if RPLResultsParser is None:
        return None

    try:
        return RPLResultsParser()

    except TypeError:

        # На случай parser с другим конструктором
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
    Приводит разные варианты parser output
    к единому формату load_all.

    Ожидаемый результат:

    {
        round,
        home_team,
        away_team,
        date,
        home_goals,
        away_goals,
        home_xg,
        away_xg,
        ...
    }
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

    normalized = dict(item)

    normalized[
        "round"
    ] = int(round_number)

    normalized[
        "home_team"
    ] = home

    normalized[
        "away_team"
    ] = away

    return normalized


# ============================================================
# HISTORICAL RESULTS
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

        raw_matches = parser.parse_rounds(
            season=SEASON_YEAR,
            rounds=rounds,
        )

    except TypeError:

        # Совместимость с parser,
        # который принимает только rounds.
        try:

            raw_matches = parser.parse_rounds(
                rounds=rounds
            )

        except Exception as e:

            result["errors"] += 1
            result["message"] = str(e)

            logger.exception(
                "Ошибка parse_rounds"
            )

            return result

    except Exception as e:

        result["errors"] += 1
        result["message"] = str(e)

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
            # РЕЗУЛЬТАТ
            # ------------------------------------------------

            home_goals = item.get(
                "home_goals"
            )

            away_goals = item.get(
                "away_goals"
            )

            if (
                home_goals is not None
                and away_goals is not None
            ):

                db.update_result(
                    match_id,
                    int(home_goals),
                    int(away_goals),
                )

            # ------------------------------------------------
            # СТАТИСТИКА
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
                    "Не удалось записать "
                    "статистику match_id=%s: %s",
                    match_id,
                    e,
                )

            # ------------------------------------------------
            # ДОПОЛНИТЕЛЬНАЯ СТАТИСТИКА
            # ------------------------------------------------

            write_match_statistics(
                db=db,
                match_id=match_id,
                home_team_id=home_id,
                away_team_id=away_id,
                item=item,
            )

            result["updated"] += 1

            actually_updated_rounds.add(
                round_number
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
# MATCH STATISTICS
# ============================================================

def write_match_statistics(
    db,
    match_id,
    home_team_id,
    away_team_id,
    item,
):
    """
    Записывает расширенную статистику,
    если соответствующая таблица существует
    и текущий database.py её поддерживает.

    Ошибка здесь НЕ должна останавливать
    основной импорт результата.
    """

    try:

        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO match_statistics
            (
                match_id,
                team_id,
                possession,
                shots,
                shots_on_target,
                corners,
                yellow_cards,
                xg,
                pass_accuracy
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                home_team_id,
                item.get(
                    "home_possession"
                ),
                item.get(
                    "home_shots"
                ),
                item.get(
                    "home_shots_on_target"
                ),
                item.get(
                    "home_corners"
                ),
                item.get(
                    "home_yellow_cards"
                ),
                item.get(
                    "home_xg"
                ),
                item.get(
                    "home_pass_accuracy"
                ),
            ),
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO match_statistics
            (
                match_id,
                team_id,
                possession,
                shots,
                shots_on_target,
                corners,
                yellow_cards,
                xg,
                pass_accuracy
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                away_team_id,
                item.get(
                    "away_possession"
                ),
                item.get(
                    "away_shots"
                ),
                item.get(
                    "away_shots_on_target"
                ),
                item.get(
                    "away_corners"
                ),
                item.get(
                    "away_yellow_cards"
                ),
                item.get(
                    "away_xg"
                ),
                item.get(
                    "away_pass_accuracy"
                ),
            ),
        )

        conn.commit()
        conn.close()

    except Exception as e:

        logger.warning(
            "Расширенная статистика "
            "не записана: %s",
            e,
        )


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
# DATABASE STATUS
# ============================================================

def get_database_status(db):

    result = {}

    conn = db._get_connection()

    try:

        cursor = conn.cursor()

        queries = {
            "matches": (
                "SELECT COUNT(*) FROM matches"
            ),
            "results": (
                "SELECT COUNT(*) FROM match_results"
            ),
            "statistics": (
                "SELECT COUNT(*) "
                "FROM match_statistics"
            ),
            "passports": (
                "SELECT COUNT(*) "
                "FROM team_passports"
            ),
        }

        for key, query in queries.items():

            try:

                cursor.execute(query)

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

    conn = db._get_connection()

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
    # СОХРАНЯЕМ ИМЕННО ВЫБРАННЫЙ ТУР
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

    save_state(state)

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

def run_full_import(state):

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

        season_id = get_or_create_season(
            db
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
        # 3. ROUNDS
        # ----------------------------------------------------

        round_ids = ensure_rounds(
            db,
            season_id,
        )

        # ----------------------------------------------------
        # 4. FIXTURES
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
        # 5. HISTORICAL
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

        # ----------------------------------------------------
        # ВАЖНО:
        # записываем только реально загруженные туры.
        # ----------------------------------------------------

        loaded_rounds = (
            historical_result.get(
                "rounds_updated",
                [],
            )
        )

        state[
            "historical_rounds_loaded"
        ] = loaded_rounds

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

        save_state(state)

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

        save_state(state)

        raise


# ============================================================
# UI — STATE
# ============================================================

def render_state(state):

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
    log
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

    c1, c2, c3 = st.columns(3)

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
# UI — ROUND PREDICTIONS
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
            "?"
        )

        away = prediction.get(
            "away",
            "?"
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
# UI — EXPERT PREDICTIONS
# ============================================================

def render_expert_predictions(
    state,
    db,
    season_id,
    round_number,
):

    st.subheader(
        "🧠 Экспертский прогноз директора"
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

    for row in matches:

        match_id = row[0]
        home = row[1]
        away = row[2]

        existing = state[
            "expert_predictions"
        ].get(
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

            state[
                "expert_predictions"
            ][str(match_id)] = {
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

            save_state(state)

            st.success(
                "✅ Экспертский прогноз "
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

            state[
                "historical_rounds_loaded"
            ] = loaded_rounds

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
                    "✅ Загружены туры: "
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
    # DATABASE STATUS
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
        прогноз. Уже рассчитанные туры не
        перезаписываются.
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

        if not (
            1
            <= int(default_round)
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
                int(default_round) - 1
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

        loaded_rounds = state.get(
            "historical_rounds_loaded",
            [],
        )

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
    # EXPERT PREDICTION
    # --------------------------------------------------------

    st.divider()

    try:

        expert_round = st.selectbox(
            "🧠 Тур для экспертного прогноза",
            options=list(
                range(
                    1,
                    TOTAL_ROUNDS + 1,
                )
            ),
            index=(
                int(
                    state.get(
                        "last_selected_round",
                        4,
                    )
                )
                - 1
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
