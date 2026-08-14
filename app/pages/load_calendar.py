#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
LOAD CALENDAR — ИДЕМПОТЕНТНАЯ ЗАГРУЗКА КАЛЕНДАРЯ РПЛ
============================================================

Назначение:
    Чистая загрузка календаря РПЛ.

Цепочка:
    Parser
      ↓
    normalize team names
      ↓
    season
      ↓
    rounds (идемпотентные)
      ↓
    find existing match
      ↓
    upsert match
      ↓
    verify match
      ↓
    240 матчей

ВАЖНО:
    - Только календарь (НЕ результаты, НЕ статистика, НЕ паспорта)
    - Идемпотентность — повторный запуск не создаёт дубли
    - НЕ меняет статус finished → scheduled
    - Нормализация названий команд
    - Проверка после upsert_match()
    - Нет DELETE/DROP
    - database.py НЕ изменяется
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
from app.parsers.rpl_fixtures_parser import RPLFixturesParser


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"

SEASON_NAME = "РПЛ 2026-2027"
SEASON_YEAR = "2026-2027"
LEAGUE = "РПЛ"

TOTAL_ROUNDS = 30
TOTAL_TEAMS = 16
EXPECTED_MATCHES = 240

DATA_DIR = "data"
STATE_FILE = os.path.join(
    DATA_DIR,
    "calendar_state.json",
)

FIXTURES_SOURCE = (
    "championat.com / smart-tables.ru / soccerland.ru"
)


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
# TEAM ALIASES (НОВОЕ)
# ============================================================

TEAM_ALIASES = {
    "Динамо М": "Динамо Москва",
    "Динамо Москва": "Динамо Москва",
    "Динамо (Москва)": "Динамо Москва",
    "Динамо-Москва": "Динамо Москва",
    "Динамо Мх": "Динамо Махачкала",
    "Динамо Махачкала": "Динамо Махачкала",
    "Динамо (Махачкала)": "Динамо Махачкала",
    "Динамо-Махачкала": "Динамо Махачкала",
    "Спартак": "Спартак",
    "Спартак М": "Спартак",
    "Спартак Москва": "Спартак",
    "Спартак-Москва": "Спартак",
    "Зенит": "Зенит",
    "Зенит Санкт-Петербург": "Зенит",
    "ЦСКА": "ЦСКА",
    "ПФК ЦСКА": "ЦСКА",
    "ЦСКА Москва": "ЦСКА",
    "Локомотив": "Локомотив",
    "Локомотив М": "Локомотив",
    "Локомотив Москва": "Локомотив",
    "Краснодар": "Краснодар",
    "Ростов": "Ростов",
    "Ростов-на-Дону": "Ростов",
    "Ахмат": "Ахмат",
    "Ахмат Грозный": "Ахмат",
    "Рубин": "Рубин",
    "Рубин Казань": "Рубин",
    "Крылья Советов": "Крылья Советов",
    "Крылья Советов Самара": "Крылья Советов",
    "Оренбург": "Оренбург",
    "Факел": "Факел",
    "Факел Воронеж": "Факел",
    "Акрон": "Акрон",
    "Акрон Тольятти": "Акрон",
    "Балтика": "Балтика",
    "Балтика Калининград": "Балтика",
    "Родина": "Родина",
    "Родина Москва": "Родина",
}


# ============================================================
# DATABASE CONNECTION (ИСПРАВЛЕНО)
# ============================================================

def get_connection(db):
    """
    Единая точка получения SQLite connection.

    ИСПРАВЛЕНО: использует публичный метод db.get_connection()
    вместо приватного _get_connection().
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
    return {
        "version": APP_VERSION,
        "season": SEASON_NAME,
        "season_id": None,
        "last_import": None,
        "last_import_status": "never",
        "fixtures_loaded": False,
        "fixtures_count": 0,
        "fixtures_expected": EXPECTED_MATCHES,
        "fixtures_last_update": None,
        "messages": [],
    }


def load_state() -> Dict:
    ensure_data_dir()

    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        base = default_state()
        if isinstance(state, dict):
            base.update(state)

        return base

    except Exception as e:
        logger.error("Ошибка чтения state: %s", e)
        return default_state()


def save_state(state: Dict):
    ensure_data_dir()

    temp_file = STATE_FILE + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        os.replace(temp_file, STATE_FILE)

    except Exception as e:
        logger.error("Ошибка сохранения state: %s", e)


# ============================================================
# DATABASE HELPERS
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
            team_id = db.get_team_id(name, LEAGUE)

            if not team_id:
                db.add_team(name, LEAGUE)
                team_id = db.get_team_id(name, LEAGUE)

            if team_id:
                team_ids[name] = team_id

        except Exception as e:
            logger.error("Ошибка команды %s: %s", name, e)

    return team_ids


# ============================================================
# ENSURE ROUNDS (ИСПРАВЛЕНО — идемпотентное)
# ============================================================

def ensure_rounds(db, season_id) -> Dict[int, int]:
    """
    Идемпотентное создание туров.

    ИСПРАВЛЕНО: явно проверяет существование каждого тура.
    """

    round_ids = {}

    conn = get_connection(db)

    try:
        cursor = conn.cursor()

        for round_number in range(1, TOTAL_ROUNDS + 1):
            try:
                # Проверяем существование тура
                cursor.execute(
                    """
                    SELECT id
                    FROM rounds
                    WHERE season_id = ?
                      AND round_number = ?
                    LIMIT 1
                    """,
                    (season_id, round_number),
                )

                row = cursor.fetchone()

                if row:
                    round_ids[round_number] = row[0]
                    continue

                # Создаём тур, если его нет
                cursor.execute(
                    """
                    INSERT INTO rounds (
                        season_id,
                        round_number
                    )
                    VALUES (?, ?)
                    """,
                    (season_id, round_number),
                )

                round_ids[round_number] = cursor.lastrowid

            except Exception as e:
                logger.warning("Ошибка тура %s: %s", round_number, e)

        conn.commit()

    finally:
        conn.close()

    return round_ids


# ============================================================
# MATCH LOOKUP (НОВОЕ)
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
# IMPORT FIXTURES (ИСПРАВЛЕНО)
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
        "message": "",
    }

    parser = RPLFixturesParser()

    fixtures_result = parser.parse()

    if not fixtures_result:
        result["message"] = "Парсер календаря не вернул матчи."
        return result

    fixtures = fixtures_result.get("matches", [])

    if not fixtures:
        result["message"] = "Парсер вернул пустой календарь."
        return result

    result["found"] = len(fixtures)

    for match in fixtures:
        try:
            round_number = int(match["round"])

            if round_number not in round_ids:
                result["errors"] += 1
                continue

            # =====================================================
            # НОРМАЛИЗАЦИЯ НАЗВАНИЙ КОМАНД (НОВОЕ)
            # =====================================================

            raw_home = match["home_team"]
            raw_away = match["away_team"]

            home_name = TEAM_ALIASES.get(raw_home, raw_home)
            away_name = TEAM_ALIASES.get(raw_away, raw_away)

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

            # =====================================================
            # ПРОВЕРКА СУЩЕСТВОВАНИЯ МАТЧА ДО upsert (НОВОЕ)
            # =====================================================

            existing_id = find_match(
                db,
                season_id,
                round_number,
                home_id,
                away_id,
            )

            # =====================================================
            # ФОРМИРУЕМ PAYLOAD (без статуса, если нет данных)
            # =====================================================

            payload = {
                "round_id": round_ids[round_number],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": match.get("date"),
                "competition": LEAGUE,
            }

            # Статус только если parser реально его передал
            status = match.get("status")
            if status:
                payload["status"] = status

            # =====================================================
            # СОХРАНЯЕМ МАТЧ
            # =====================================================

            db.upsert_match(payload)

            # =====================================================
            # ПРОВЕРЯЕМ МАТЧ ПОСЛЕ upsert (НОВОЕ)
            # =====================================================

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
            logger.exception("Ошибка импорта календаря: %s", e)

    # ============================================================
    # ОБНОВЛЯЕМ STATE
    # ============================================================

    successful_fixtures = result["added"] + result["updated"]

    state["fixtures_loaded"] = (
        result["found"] > 0
        and successful_fixtures > 0
    )

    state["fixtures_count"] = successful_fixtures
    state["fixtures_expected"] = EXPECTED_MATCHES

    if state["fixtures_loaded"]:
        state["fixtures_last_update"] = datetime.now().isoformat()

    return result


# ============================================================
# DATABASE STATUS (ИСПРАВЛЕНО)
# ============================================================

def get_database_status(db):
    result = {}

    conn = get_connection(db)

    try:
        cursor = conn.cursor()

        queries = {
            "matches": "SELECT COUNT(*) FROM matches",
            "teams": "SELECT COUNT(*) FROM teams",
            "rounds": "SELECT COUNT(*) FROM rounds",
        }

        for key, query in queries.items():
            try:
                cursor.execute(query)
                row = cursor.fetchone()
                result[key] = row[0] if row else 0
            except Exception:
                result[key] = 0

    finally:
        conn.close()

    return result


# ============================================================
# MAIN
# ============================================================

def main():
    st.set_page_config(
        page_title="FAJ — Загрузка календаря",
        page_icon="📅",
        layout="wide",
    )

    st.title("📅 FAJ — ЗАГРУЗКА КАЛЕНДАРЯ РПЛ")

    st.caption(
        f"FAJ Platform v{APP_VERSION} · {SEASON_NAME}"
    )

    # ============================================================
    # STATE
    # ============================================================

    state = load_state()

    # ============================================================
    # СОСТОЯНИЕ
    # ============================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status = state.get("last_import_status", "never")
        if status == "success":
            st.metric("Импорт", "✅ OK")
        elif status == "error":
            st.metric("Импорт", "❌ ОШИБКА")
        else:
            st.metric("Импорт", "⏳ Не запускался")

    with col2:
        fixtures_count = state.get("fixtures_count", 0)
        fixtures_expected = state.get("fixtures_expected", EXPECTED_MATCHES)
        st.metric(
            "Матчи календаря",
            f"{fixtures_count}/{fixtures_expected}",
        )

    with col3:
        loaded = state.get("fixtures_loaded", False)
        st.metric(
            "Календарь",
            "✅ Загружен" if loaded else "⏳ Не загружен",
        )

    with col4:
        last_update = state.get("fixtures_last_update")
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update)
                value = dt.strftime("%d.%m %H:%M")
            except Exception:
                value = "есть"
        else:
            value = "—"
        st.metric("Последнее обновление", value)

    # ============================================================
    # КНОПКИ
    # ============================================================

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        import_clicked = st.button(
            "🔥 ЗАГРУЗИТЬ КАЛЕНДАРЬ",
            type="primary",
            use_container_width=True,
        )

    with col2:
        refresh_clicked = st.button(
            "🔄 ОБНОВИТЬ",
            use_container_width=True,
        )

    with col3:
        clear_clicked = st.button(
            "🗑️ ОЧИСТИТЬ STATE (НЕ БД)",
            use_container_width=True,
        )

    if refresh_clicked:
        st.rerun()

    if clear_clicked:
        state = default_state()
        save_state(state)
        st.success("✅ State очищен")
        st.rerun()

    # ============================================================
    # ИМПОРТ
    # ============================================================

    if import_clicked:
        db = get_db()

        try:
            with st.spinner("📅 Загружаем календарь РПЛ..."):
                # 1. SEASON
                season_id = get_or_create_season(db)
                state["season_id"] = season_id

                # 2. TEAMS
                team_ids = ensure_teams(db)

                # 3. ROUNDS (исправлено)
                round_ids = ensure_rounds(db, season_id)

                # 4. FIXTURES (исправлено)
                fixture_result = import_fixtures(
                    db=db,
                    season_id=season_id,
                    team_ids=team_ids,
                    round_ids=round_ids,
                    state=state,
                )

                # 5. STATE
                state["last_import"] = datetime.now().isoformat()
                state["last_import_status"] = (
                    "success" if fixture_result.get("added", 0) > 0
                    or fixture_result.get("updated", 0) > 0
                    else "error"
                )

                # Сохраняем результат
                state["last_import_summary"] = fixture_result

                if state.get("messages") is None:
                    state["messages"] = []

                state["messages"].append(
                    f"{datetime.now().isoformat()}: "
                    f"Найдено {fixture_result.get('found', 0)}, "
                    f"добавлено {fixture_result.get('added', 0)}, "
                    f"обновлено {fixture_result.get('updated', 0)}, "
                    f"ошибок {fixture_result.get('errors', 0)}"
                )

                save_state(state)

                # ====================================================
                # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТА
                # ====================================================

                st.success("✅ Загрузка календаря завершена.")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "Найдено матчей",
                        fixture_result.get("found", 0),
                    )

                with col2:
                    st.metric(
                        "Добавлено",
                        fixture_result.get("added", 0),
                    )

                with col3:
                    st.metric(
                        "Обновлено",
                        fixture_result.get("updated", 0),
                    )

                with col4:
                    st.metric(
                        "Ошибок",
                        fixture_result.get("errors", 0),
                    )

                # Проверка полноты календаря (НОВОЕ)
                fixtures_count = state.get("fixtures_count", 0)

                if fixtures_count < EXPECTED_MATCHES:
                    st.warning(
                        f"⚠️ Календарь неполный: "
                        f"{fixtures_count} из {EXPECTED_MATCHES} матчей."
                    )
                elif fixtures_count == EXPECTED_MATCHES:
                    st.success(
                        f"✅ Полный календарь: {EXPECTED_MATCHES} матчей."
                    )

                if fixture_result.get("unknown_teams"):
                    st.warning(
                        "Неизвестные команды: "
                        + ", ".join(fixture_result["unknown_teams"])
                    )

                if fixture_result.get("message"):
                    st.info(fixture_result["message"])

                with st.expander("📊 Детали импорта", expanded=False):
                    st.json(fixture_result)

                st.rerun()

        except Exception as e:
            st.error(f"❌ Ошибка: {e}")
            st.code(traceback.format_exc())

            state["last_import_status"] = "error"
            save_state(state)

    # ============================================================
    # СТАТУС БД
    # ============================================================

    st.divider()
    st.subheader("📊 Состояние базы данных")

    try:
        db = get_db()
        db_status = get_database_status(db)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Матчи", db_status.get("matches", 0))

        with col2:
            st.metric("Команды", db_status.get("teams", 0))

        with col3:
            st.metric("Туры", db_status.get("rounds", 0))

    except Exception as e:
        st.warning(f"Не удалось получить статус БД: {e}")

    # ============================================================
    # ЖУРНАЛ
    # ============================================================

    if state.get("messages"):
        st.divider()
        st.subheader("📜 Журнал")

        for msg in state["messages"][-10:]:
            st.caption(msg)

    # ============================================================
    # FOOTER
    # ============================================================

    st.divider()
    st.caption(
        "FAJ Platform v12.1 · "
        "SQLite · Идемпотентная загрузка · "
        "RPL 2026/27"
    )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()
