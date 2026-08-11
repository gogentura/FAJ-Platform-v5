#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD ALL — RPL DATA ORCHESTRATOR
============================================================

Назначение:
    Единая точка загрузки и подготовки данных РПЛ.

Что делает:
    1. Создаёт/получает сезон
    2. Создаёт команды
    3. Создаёт туры
    4. Загружает календарь через RPL fixtures parser
    5. Загружает результаты/статистику прошедших туров
    6. Работает идемпотентно
    7. Ведёт persistent import state
    8. Показывает состояние БД
    9. Позволяет выбрать тур для прогнозирования
   10. Сохраняет последний статус даже после перезапуска Streamlit

ВАЖНО:
    database.py НЕ изменяется этим файлом.
============================================================
"""

import os
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st

from app.database import FAJDatabase
from app.passports.passport_manager import get_passport_manager
from app.core.prediction_manager import get_prediction_manager

from app.parsers.rpl_fixtures_parser import RPLFixturesParser

try:
    from app.parsers.rpl_stats_parser import RPLStatsParser
except ImportError:
    RPLStatsParser = None


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
SEASON_NAME = "РПЛ 2026-2027"
LEAGUE = "РПЛ"
SEASON_YEAR = "2026-2027"

TOTAL_ROUNDS = 30

DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "import_state.json")

SOURCE_FIXTURES = "championat.com"
SOURCE_STATS = "smart-tables.ru / soccerland.ru"

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
    return {
        "version": APP_VERSION,
        "season": SEASON_NAME,
        "last_import": None,
        "last_import_status": "never",
        "last_import_summary": {},
        "historical_rounds_loaded": [],
        "fixtures_loaded": False,
        "last_prediction_round": None,
        "last_prediction_time": None,
        "predictions": {},
        "expert_predictions": {},
    }


def load_state() -> Dict:
    """
    Загружает persistent state.

    Это НЕ session_state.
    Файл остаётся после перезапуска Streamlit.
    """

    ensure_data_dir()

    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        base = default_state()
        base.update(state)

        return base

    except Exception as e:
        logger.error("Ошибка чтения import_state.json: %s", e)
        return default_state()


def save_state(state: Dict):
    """
    Атомарная запись состояния.
    """

    ensure_data_dir()

    temp_file = STATE_FILE + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temp_file, STATE_FILE)

    except Exception as e:
        logger.error("Ошибка сохранения state: %s", e)


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    return FAJDatabase()


def get_or_create_season(db):
    """
    Получаем сезон.

    Если database.py уже умеет создавать/возвращать существующий
    сезон через create_season — используем его.

    Это сохраняет совместимость с текущим load_all.py.
    """

    return db.create_season(
        name=SEASON_NAME,
        league=LEAGUE,
        year=SEASON_YEAR,
    )


def ensure_teams(db) -> Dict[str, int]:
    """
    Гарантирует наличие всех 16 команд.

    Возвращает:
        {
            "Зенит": 1,
            ...
        }
    """

    team_ids = {}

    for name in RPL_TEAMS:

        team_id = db.get_team_id(name, LEAGUE)

        if not team_id:
            db.add_team(name, LEAGUE)
            team_id = db.get_team_id(name, LEAGUE)

        if team_id:
            team_ids[name] = team_id

    return team_ids


def ensure_rounds(db, season_id) -> Dict[int, int]:
    """
    Создаёт/получает туры.

    Используем существующий create_round.
    """

    round_ids = {}

    for round_number in range(1, TOTAL_ROUNDS + 1):
        try:
            round_id = db.create_round(
                season_id,
                round_number,
            )

            round_ids[round_number] = round_id

        except Exception as e:
            logger.warning(
                "Не удалось создать тур %s: %s",
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
    """
    Ищет существующий матч.

    Используется для идемпотентности.
    """

    conn = db._get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT m.id
            FROM matches m
            JOIN rounds r ON r.id = m.round_id
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
# FIXTURES IMPORT
# ============================================================

def import_fixtures(
    db,
    season_id,
    team_ids,
    round_ids,
    state,
):
    """
    Загружает календарь.

    Важный принцип:
        повторный запуск не создаёт второй матч.
    """

    result = {
        "found": 0,
        "added": 0,
        "updated": 0,
        "errors": 0,
        "unknown_teams": [],
    }

    parser = RPLFixturesParser()

    fixtures = parser.parse()

    result["found"] = len(fixtures)

    for match in fixtures:

        try:
            round_number = int(match["round"])

            if round_number not in round_ids:
                result["errors"] += 1
                continue

            home_name = match["home_team"]
            away_name = match["away_team"]

            home_id = team_ids.get(home_name)
            away_id = team_ids.get(away_name)

            if not home_id:
                result["unknown_teams"].append(home_name)
                result["errors"] += 1
                continue

            if not away_id:
                result["unknown_teams"].append(away_name)
                result["errors"] += 1
                continue

            existing_id = find_match(
                db=db,
                season_id=season_id,
                round_number=round_number,
                home_team_id=home_id,
                away_team_id=away_id,
            )

            payload = {
                "round_id": round_ids[round_number],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": match.get("date"),
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
                "Ошибка импорта матча: %s",
                e,
            )

    state["fixtures_loaded"] = True

    return result


# ============================================================
# HISTORICAL RESULTS
# ============================================================

def find_historical_urls():
    """
    Здесь специально НЕ зашиваем старый nb-bet.

    Парсер статистики может использовать источники:
        smart-tables.ru
        soccerland.ru

    Пока URLs не определены самим parser'ом,
    исторический импорт календаря остаётся безопасным.

    Если RPLStatsParser реализован — используем его.
    """

    return []


def import_historical_results(
    db,
    season_id,
    team_ids,
    rounds=(1, 2, 3),
):
    """
    Загружает результаты прошедших туров.

    Возвращает подробный журнал.

    В текущей версии функция не подставляет фиктивные URL.
    Это принципиально важно:
        лучше 0 корректных записей,
        чем 24 неправильных записи.
    """

    result = {
        "rounds": list(rounds),
        "found": 0,
        "updated": 0,
        "errors": 0,
        "skipped": 0,
        "source": SOURCE_STATS,
    }

    if RPLStatsParser is None:
        result["skipped"] = 1
        result["message"] = (
            "RPLStatsParser ещё не подключён."
        )
        return result

    # --------------------------------------------------------
    # Здесь parser должен предоставлять список матчей.
    #
    # Если parser имеет метод parse_rounds(), используем его.
    # Если нет — не ломаем приложение.
    # --------------------------------------------------------

    parser = RPLStatsParser()

    if not hasattr(parser, "parse_rounds"):
        result["skipped"] = 1
        result["message"] = (
            "RPLStatsParser не имеет метода parse_rounds(). "
            "Исторические результаты пока не загружались."
        )
        return result

    try:

        matches = parser.parse_rounds(
            season=SEASON_YEAR,
            rounds=list(rounds),
        )

        if not matches:
            result["message"] = (
                "Парсер не вернул исторические матчи."
            )
            return result

        result["found"] = len(matches)

        for item in matches:

            try:

                round_number = int(item["round"])

                if round_number not in rounds:
                    continue

                home_name = item["home_team"]
                away_name = item["away_team"]

                home_id = team_ids.get(home_name)
                away_id = team_ids.get(away_name)

                if not home_id or not away_id:
                    result["errors"] += 1
                    continue

                match_id = find_match(
                    db,
                    season_id,
                    round_number,
                    home_id,
                    away_id,
                )

                if not match_id:
                    result["errors"] += 1
                    continue

                home_goals = item.get("home_goals")
                away_goals = item.get("away_goals")

                if (
                    home_goals is not None
                    and away_goals is not None
                ):
                    db.update_result(
                        match_id,
                        int(home_goals),
                        int(away_goals),
                    )

                stats_payload = {
                    "home_xg": item.get("home_xg"),
                    "away_xg": item.get("away_xg"),
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
                    "parser_source": SOURCE_STATS,
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
                        "Статистика не обновлена "
                        "для match_id=%s: %s",
                        match_id,
                        e,
                    )

                result["updated"] += 1

            except Exception:
                result["errors"] += 1
                logger.exception(
                    "Ошибка исторического матча"
                )

    except Exception as e:

        result["errors"] += 1
        result["message"] = str(e)

    return result


# ============================================================
# PASSPORTS
# ============================================================

def ensure_passports(
    db,
    season_id,
):
    """
    Создаёт паспорт только если его ещё нет.

    НЕ перезаписывает существующий паспорт.
    """

    result = {
        "created": 0,
        "existing": 0,
        "errors": 0,
    }

    pm = get_passport_manager()

    teams = db.get_teams(LEAGUE)

    for team in teams:

        try:

            existing = pm.get_current_passport(
                team["id"],
                season_id,
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
                "Ошибка паспорта команды %s",
                team.get("name"),
            )

    return result


# ============================================================
# DATABASE STATUS
# ============================================================

def get_database_status(db) -> Dict:

    result = {}

    conn = db._get_connection()

    try:

        cursor = conn.cursor()

        queries = {
            "matches": "SELECT COUNT(*) FROM matches",
            "results": "SELECT COUNT(*) FROM match_results",
            "statistics": (
                "SELECT COUNT(*) FROM match_statistics"
            ),
            "passports": (
                "SELECT COUNT(*) FROM team_passports"
            ),
        }

        for key, query in queries.items():

            try:
                cursor.execute(query)
                result[key] = cursor.fetchone()[0]
            except Exception:
                result[key] = 0

    finally:
        conn.close()

    return result


# ============================================================
# ROUND DATA
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

def run_predictions(
    db,
    season_id,
    round_number,
    state,
):
    """
    Запускает прогнозы выбранного тура.

    Результаты сохраняются в persistent state.

    Сам PredictionManager также должен сохранять
    прогноз в своей таблице БД.
    """

    matches = get_round_matches(
        db,
        season_id,
        round_number,
    )

    if not matches:
        return {
            "status": "error",
            "message": (
                f"Матчи {round_number}-го тура не найдены."
            ),
        }

    pm = get_prediction_manager()

    predictions = {}

    for row in matches:

        match_id = row[0]
        home = row[1]
        away = row[2]
        date = row[3]

        try:

            result = pm.predict(
                home_team=home,
                away_team=away,
                league=LEAGUE,
                season_id=season_id,
            )

            predictions[str(match_id)] = {
                "match_id": match_id,
                "home": home,
                "away": away,
                "date": date,
                "result": result,
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:

            predictions[str(match_id)] = {
                "match_id": match_id,
                "home": home,
                "away": away,
                "date": date,
                "error": str(e),
                "created_at": datetime.now().isoformat(),
            }

    state["predictions"] = predictions
    state["last_prediction_round"] = round_number
    state["last_prediction_time"] = (
        datetime.now().isoformat()
    )

    save_state(state)

    return {
        "status": "ok",
        "count": len(predictions),
        "predictions": predictions,
    }


# ============================================================
# UI
# ============================================================

def render_state(state):

    st.subheader("🧠 Состояние FAJ")

    col1, col2, col3, col4 = st.columns(4)

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
            f"{len(loaded)} тура",
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

        season_id = get_or_create_season(db)

        state["season_id"] = season_id

        # ----------------------------------------------------
        # 2. TEAMS
        # ----------------------------------------------------

        team_ids = ensure_teams(db)

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

            fixture_result = import_fixtures(
                db=db,
                season_id=season_id,
                team_ids=team_ids,
                round_ids=round_ids,
                state=state,
            )

        log["fixtures"] = fixture_result

        # ----------------------------------------------------
        # 5. HISTORICAL 1-3
        # ----------------------------------------------------

        with st.spinner(
            "📊 Загружаем исторические данные "
            "1–3 туров..."
        ):

            historical_result = (
                import_historical_results(
                    db=db,
                    season_id=season_id,
                    team_ids=team_ids,
                    rounds=HISTORICAL_ROUNDS,
                )
            )

        log["historical"] = historical_result

        # ----------------------------------------------------
        # 6. PASSPORTS
        # ----------------------------------------------------

        with st.spinner(
            "📋 Проверяем паспорта команд..."
        ):

            passport_result = ensure_passports(
                db=db,
                season_id=season_id,
            )

        log["passports"] = passport_result

        # ----------------------------------------------------
        # 7. STATE
        # ----------------------------------------------------

        state["last_import"] = (
            datetime.now().isoformat()
        )

        state["last_import_status"] = "success"

        state["last_import_summary"] = log

        state["historical_rounds_loaded"] = (
            HISTORICAL_ROUNDS
        )

        log["status"] = "success"

        save_state(state)

        return log

    except Exception as e:

        log["status"] = "error"
        log["error"] = str(e)
        log["traceback"] = traceback.format_exc()

        state["last_import"] = (
            datetime.now().isoformat()
        )

        state["last_import_status"] = "error"
        state["last_import_summary"] = log

        save_state(state)

        raise


# ============================================================
# MAIN
# ============================================================

def main():

    st.set_page_config(
        page_title="FAJ — Загрузка данных",
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
    # LOAD PERSISTENT STATE
    # --------------------------------------------------------

    state = load_state()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    render_state(state)

    # --------------------------------------------------------
    # MAIN ACTIONS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "⚙️ Управление данными"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        import_clicked = st.button(
            "🔥 СИНХРОНИЗИРОВАТЬ ДАННЫЕ",
            type="primary",
            use_container_width=True,
        )

    with col2:

        historical_clicked = st.button(
            "📊 ЗАГРУЗИТЬ 1–3 ТУРЫ",
            use_container_width=True,
        )

    with col3:

        refresh_clicked = st.button(
            "🔄 ОБНОВИТЬ СОСТОЯНИЕ",
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

            season_id = get_or_create_season(
                db
            )

            team_ids = ensure_teams(db)

            with st.spinner(
                "Загружаем прошедшие 3 тура..."
            ):

                result = import_historical_results(
                    db=db,
                    season_id=season_id,
                    team_ids=team_ids,
                    rounds=HISTORICAL_ROUNDS,
                )

            state[
                "historical_rounds_loaded"
            ] = HISTORICAL_ROUNDS

            state[
                "last_import"
            ] = datetime.now().isoformat()

            state[
                "last_import_summary"
            ] = result

            save_state(state)

            if result.get("status") == "error":
                st.error(
                    result.get(
                        "message",
                        "Ошибка",
                    )
                )
            else:
                st.success(
                    "✅ Исторический импорт завершён."
                )

            st.json(result)

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

        db_status = get_database_status(
            db
        )

        c1, c2, c3, c4 = st.columns(4)

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
            f"Не удалось получить статус БД: {e}"
        )

    # --------------------------------------------------------
    # LAST IMPORT LOG
    # --------------------------------------------------------

    if state.get(
        "last_import_summary"
    ):

        with st.expander(
            "📜 Последний журнал импорта",
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

    st.subheader(
        "🔮 ЦЕНТР ПРОГНОЗОВ"
    )

    st.info(
        """
        Здесь выбирается тур, на который FAJ должен
        построить прогноз.

        Прошедшие туры используются как историческая
        база. Будущий тур не изменяется после построения
        прогноза — прогноз сохраняется отдельно.
        """
    )

    try:

        db = get_db()

        season_id = state.get(
            "season_id"
        )

        if not season_id:
            season_id = get_or_create_season(
                db
            )

            state[
                "season_id"
            ] = season_id

            save_state(state)

        selected_round = st.selectbox(
            "Выберите тур для прогнозирования",
            options=list(
                range(
                    1,
                    TOTAL_ROUNDS + 1,
                )
            ),
            index=3,
        )

        round_matches = get_round_matches(
            db,
            season_id,
            selected_round,
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

                c1, c2, c3 = st.columns(
                    [4, 4, 2]
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
                "Для выбранного тура матчи "
                "в базе не найдены."
            )

        if st.button(
            f"🚀 СОЗДАТЬ ПРОГНОЗЫ НА "
            f"{selected_round}-Й ТУР",
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

            if prediction_result[
                "status"
            ] == "ok":

                st.success(
                    "✅ Прогнозы рассчитаны "
                    "и сохранены."
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
    # SAVED PREDICTIONS
    # --------------------------------------------------------

    predictions = state.get(
        "predictions",
        {},
    )

    if predictions:

        st.divider()

        st.subheader(
            "📚 Сохранённые прогнозы"
        )

        for prediction in predictions.values():

            if "error" in prediction:

                st.error(
                    f"{prediction['home']} "
                    f"— "
                    f"{prediction['away']}: "
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

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.write(
                    f"**{prediction['home']}**"
                )

            with c2:
                st.write(
                    f"**{prediction['away']}**"
                )

            with c3:

                if xg:
                    st.metric(
                        "xG",
                        f"{xg.get('home', 0):.2f} : "
                        f"{xg.get('away', 0):.2f}",
                    )

            with c4:

                score = result.get(
                    "score",
                    "—",
                )

                st.metric(
                    "Прогноз",
                    score,
                )

            if probability:

                st.caption(
                    "Вероятности: "
                    f"П1 "
                    f"{probability.get('home', 0) * 100:.1f}% · "
                    f"X "
                    f"{probability.get('draw', 0) * 100:.1f}% · "
                    f"П2 "
                    f"{probability.get('away', 0) * 100:.1f}%"
                )

    # --------------------------------------------------------
    # EXPERT PREDICTION
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🧠 ЭКСПЕРТСКИЙ ПРОГНОЗ ДИРЕКТОРА"
    )

    st.caption(
        "Здесь позже подключаем сохранение "
        "личного прогноза директора отдельно "
        "от модели FAJ."
    )

    expert_round = st.selectbox(
        "Тур для экспертного прогноза",
        options=list(
            range(
                1,
                TOTAL_ROUNDS + 1,
            )
        ),
        key="expert_round",
    )

    expert_matches = get_round_matches(
        get_db(),
        state.get(
            "season_id",
            1,
        ),
        expert_round,
    )

    if expert_matches:

        for row in expert_matches:

            match_id = row[0]
            home = row[1]
            away = row[2]

            st.markdown(
                f"**{home} — {away}**"
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                expert_result = st.text_input(
                    "Исход",
                    key=f"expert_result_{match_id}",
                    placeholder="П1 / X / П2",
                )

            with c2:
                expert_score = st.text_input(
                    "Точный счёт",
                    key=f"expert_score_{match_id}",
                    placeholder="2:1",
                )

            with c3:
                expert_comment = st.text_input(
                    "Комментарий",
                    key=f"expert_comment_{match_id}",
                )

            if st.button(
                "💾 Сохранить",
                key=f"save_expert_{match_id}",
            ):

                state.setdefault(
                    "expert_predictions",
                    {},
                )

                state[
                    "expert_predictions"
                ][str(match_id)] = {
                    "match_id": match_id,
                    "round": expert_round,
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
                    "Экспертский прогноз сохранён."
                )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.divider()

    st.caption(
        "FAJ Platform v12.1 · "
        "SQLite persistent state · "
        "RPL 2026/27"
    )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()
