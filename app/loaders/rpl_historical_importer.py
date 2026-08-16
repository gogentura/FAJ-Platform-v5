#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL Historical Importer
===========================================================

НАЗНАЧЕНИЕ
----------
Импорт проверенных исторических результатов РПЛ 2026/27
за 1-4 туры в существующий календарь SQLite.

ВАЖНО
-----
Этот модуль НЕ является FAJ Cycle.

RPL Historical Importer отвечает ТОЛЬКО за:
    verified historical results
            ↓
    existing calendar match
            ↓
    match_results
            +
    actual result fields in matches

НЕ ДЕЛАЕТ:
    - создание сезонов
    - создание туров
    - создание команд
    - создание матчей
    - создание прогнозов
    - создание паспортов
    - обучение
    - пересчёт модели
    - запуск FAJ Cycle
    - DELETE

ПРИНЦИПЫ:
    - SQLite only
    - существующий календарь является источником матчей
    - DELETE отсутствует
    - отсутствующий матч считается ошибкой
    - отсутствующая команда считается ошибкой
    - отсутствующий тур считается ошибкой
    - конфликт результата считается ошибкой
    - существующий идентичный результат не перезаписывается
    - импорт идемпотентен
    - вся операция атомарна
    - при любой ошибке выполняется rollback
    - исторические результаты не зависят от NB-Bet
    - исторические результаты не запускают обучение

Источник: historical / manual_import
Версия: 1.3
===========================================================
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

SEASON_YEAR = "2026-2027"
LEAGUE_NAME = "РПЛ"

IMPORT_SOURCE = "historical"
IMPORT_METHOD = "manual_import"
IMPORT_VERSION = "1.3"

EXPECTED_MATCHES = 32
EXPECTED_ROUNDS = (1, 2, 3, 4)


# ============================================================
# DATABASE PATH
# ============================================================

FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = FILE_PATH.parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "faj.db"


# ============================================================
# VERIFIED HISTORICAL RESULTS (1-4 ТУРЫ, 32 МАТЧА)
# ============================================================

HISTORICAL_MATCHES: List[
    Tuple[int, str, str, str, int, int]
] = [

    # ========================================================
    # ТУР 1
    # ========================================================

    (1, "2026-07-24", "ЦСКА", "Балтика", 2, 1),
    (1, "2026-07-25", "Динамо Москва", "Крылья Советов", 0, 0),
    (1, "2026-07-25", "Акрон", "Зенит", 0, 5),
    (1, "2026-07-25", "Факел", "Динамо Махачкала", 1, 2),
    (1, "2026-07-25", "Спартак", "Родина", 3, 0),
    (1, "2026-07-26", "Оренбург", "Ростов", 2, 1),
    (1, "2026-07-26", "Локомотив", "Ахмат", 1, 1),
    (1, "2026-07-26", "Рубин", "Краснодар", 1, 3),

    # ========================================================
    # ТУР 2
    # ========================================================

    (2, "2026-07-31", "Родина", "Ростов", 2, 4),
    (2, "2026-08-01", "Акрон", "Рубин", 1, 2),
    (2, "2026-08-01", "ЦСКА", "Крылья Советов", 1, 1),
    (2, "2026-08-01", "Динамо Махачкала", "Локомотив", 2, 1),
    (2, "2026-08-01", "Балтика", "Динамо Москва", 2, 1),
    (2, "2026-08-02", "Оренбург", "Зенит", 0, 3),
    (2, "2026-08-02", "Краснодар", "Факел", 3, 2),
    (2, "2026-08-02", "Ахмат", "Спартак", 1, 2),

    # ========================================================
    # ТУР 3
    # ========================================================

    (3, "2026-08-08", "Крылья Советов", "Балтика", 0, 2),
    (3, "2026-08-08", "Локомотив", "Акрон", 0, 0),
    (3, "2026-08-09", "Ростов", "ЦСКА", 0, 0),
    (3, "2026-08-09", "Динамо Москва", "Динамо Махачкала", 3, 1),
    (3, "2026-08-09", "Зенит", "Родина", 1, 2),
    (3, "2026-08-10", "Спартак", "Краснодар", 1, 2),
    (3, "2026-08-10", "Рубин", "Оренбург", 1, 1),
    (3, "2026-08-11", "Факел", "Ахмат", 0, 0),

    # ========================================================
    # ТУР 4
    # ========================================================

    (4, "2026-08-14", "Оренбург", "Локомотив", 1, 1),
    (4, "2026-08-15", "Родина", "Акрон", 3, 3),
    (4, "2026-08-15", "Краснодар", "Ахмат", 1, 0),
    (4, "2026-08-15", "Ростов", "Рубин", 1, 1),
    (4, "2026-08-15", "ЦСКА", "Факел", 1, 0),
    (4, "2026-08-16", "Балтика", "Спартак", 1, 2),
    (4, "2026-08-16", "Крылья Советов", "Динамо Махачкала", 1, 4),
    (4, "2026-08-16", "Зенит", "Динамо Москва", 3, 0),
]


# ============================================================
# TEAM NORMALIZATION
# ============================================================

TEAM_ALIASES: Dict[str, str] = {
    "Динамо М": "Динамо Москва",
    "Динамо Москва": "Динамо Москва",
    "Динамо (Москва)": "Динамо Москва",
    "Динамо-Москва": "Динамо Москва",
    "Динамо Мх": "Динамо Махачкала",
    "Динамо Махачкала": "Динамо Махачкала",
    "Динамо (Махачкала)": "Динамо Махачкала",
    "Динамо-Махачкала": "Динамо Махачкала",
    "Спартак Москва": "Спартак",
    "Спартак М": "Спартак",
    "Спартак-Москва": "Спартак",
    "Спартак": "Спартак",
    "ЦСКА Москва": "ЦСКА",
    "ПФК ЦСКА": "ЦСКА",
    "ЦСКА": "ЦСКА",
    "Локомотив Москва": "Локомотив",
    "Локомотив": "Локомотив",
    "Акрон Тольятти": "Акрон",
    "Акрон": "Акрон",
    "Крылья Советов Самара": "Крылья Советов",
    "Крылья Советов": "Крылья Советов",
    "Балтика Калининград": "Балтика",
    "Балтика": "Балтика",
    "Родина Москва": "Родина",
    "Родина": "Родина",
    "Ахмат Грозный": "Ахмат",
    "Ахмат": "Ахмат",
    "Рубин Казань": "Рубин",
    "Рубин": "Рубин",
    "Зенит Санкт-Петербург": "Зенит",
    "Зенит": "Зенит",
    "Факел Воронеж": "Факел",
    "Факел": "Факел",
    "Оренбург": "Оренбург",
    "Оренburg": "Оренбург",
    "Ростов": "Ростов",
    "Краснодар": "Краснодар",
}


def normalize_team(team: Optional[str]) -> Optional[str]:
    if team is None:
        return None
    value = str(team).strip()
    if not value:
        return None
    return TEAM_ALIASES.get(value, value)


# ============================================================
# RESULT
# ============================================================

def _empty_result() -> Dict[str, Any]:
    return {
        "success": False,
        "source": IMPORT_SOURCE,
        "method": IMPORT_METHOD,
        "version": IMPORT_VERSION,
        "season": SEASON_YEAR,
        "league": LEAGUE_NAME,
        "expected": EXPECTED_MATCHES,
        "found": len(HISTORICAL_MATCHES),
        "inserted_results": 0,
        "updated_matches": 0,
        "already_present": 0,
        "errors": [],
        "rounds": [],
        "rounds_imported": [],
        "matches": [],
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_historical_data() -> Dict[str, Any]:
    result = _empty_result()
    seen = set()

    for item in HISTORICAL_MATCHES:
        if len(item) != 6:
            result["errors"].append(f"Некорректная запись: {item}")
            continue

        round_number, date_value, home_team, away_team, home_goals, away_goals = item

        try:
            round_number = int(round_number)
            home_goals = int(home_goals)
            away_goals = int(away_goals)
        except (TypeError, ValueError):
            result["errors"].append(f"Некорректные числовые значения: {item}")
            continue

        home_team = normalize_team(home_team)
        away_team = normalize_team(away_team)
        key = (round_number, home_team, away_team)

        if key in seen:
            result["errors"].append(f"Дубликат матча: {key}")
            continue
        seen.add(key)

        if round_number not in EXPECTED_ROUNDS:
            result["errors"].append(f"Недопустимый тур: {round_number}")
        if not date_value:
            result["errors"].append(f"Нет даты: {key}")
        if not home_team or not away_team:
            result["errors"].append(f"Не определена команда: {key}")
        if home_team == away_team:
            result["errors"].append(f"Одинаковые команды: {key}")
        if home_goals < 0 or away_goals < 0:
            result["errors"].append(f"Отрицательный счёт: {key}")

    if len(HISTORICAL_MATCHES) != EXPECTED_MATCHES:
        result["errors"].append(
            f"Количество матчей: {len(HISTORICAL_MATCHES)}, ожидалось {EXPECTED_MATCHES}"
        )

    result["rounds"] = sorted({int(item[0]) for item in HISTORICAL_MATCHES})

    for round_number in EXPECTED_ROUNDS:
        count = sum(1 for item in HISTORICAL_MATCHES if int(item[0]) == round_number)
        if count != 8:
            result["errors"].append(f"Тур {round_number}: {count}/8 матчей")

    result["success"] = not result["errors"]
    return result


# ============================================================
# DB HELPERS
# ============================================================

def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table_name,))
    return cursor.fetchone() is not None


def _table_columns(cursor: sqlite3.Cursor, table_name: str) -> List[str]:
    cursor.execute(f'PRAGMA table_info("{table_name}")')
    return [row[1] for row in cursor.fetchall()]


# ============================================================
# TEAM LOOKUP
# ============================================================

def _find_team_id(cursor: sqlite3.Cursor, team_name: str) -> Optional[int]:
    canonical = normalize_team(team_name)
    if not canonical:
        return None

    cursor.execute("SELECT id FROM teams WHERE name = ? LIMIT 1", (canonical,))
    row = cursor.fetchone()
    if row:
        return int(row[0])

    # Дополнительный поиск через aliases
    aliases = [alias for alias, normalized in TEAM_ALIASES.items() if normalized == canonical]
    for alias in aliases:
        cursor.execute("SELECT id FROM teams WHERE name = ? LIMIT 1", (alias,))
        row = cursor.fetchone()
        if row:
            return int(row[0])
    return None


# ============================================================
# SEASON LOOKUP
# ============================================================

def _find_season_id(cursor: sqlite3.Cursor) -> Optional[int]:
    if not _table_exists(cursor, "seasons"):
        return None

    columns = _table_columns(cursor, "seasons")
    for column in ("name", "season", "season_name", "year"):
        if column not in columns:
            continue
        cursor.execute(f'SELECT id FROM seasons WHERE "{column}" = ? LIMIT 1', (SEASON_YEAR,))
        row = cursor.fetchone()
        if row:
            return int(row[0])
    return None


# ============================================================
# ROUND LOOKUP
# ============================================================

def _find_round_id(cursor: sqlite3.Cursor, round_number: int) -> Optional[int]:
    round_number = int(round_number)

    if not _table_exists(cursor, "rounds"):
        return None

    columns = _table_columns(cursor, "rounds")

    # Season-scoped search
    if "season_id" in columns:
        season_id = _find_season_id(cursor)
        if season_id is not None:
            if "round_number" in columns:
                cursor.execute(
                    "SELECT id FROM rounds WHERE season_id = ? AND round_number = ? LIMIT 1",
                    (season_id, round_number),
                )
                row = cursor.fetchone()
                if row:
                    return int(row[0])
            if "name" in columns:
                for name in (f"Тур {round_number}", f"{round_number} тур", str(round_number), f"Round {round_number}"):
                    cursor.execute(
                        "SELECT id FROM rounds WHERE season_id = ? AND name = ? LIMIT 1",
                        (season_id, name),
                    )
                    row = cursor.fetchone()
                    if row:
                        return int(row[0])

    # Legacy / simple schema
    if "round_number" in columns:
        cursor.execute("SELECT id FROM rounds WHERE round_number = ? LIMIT 1", (round_number,))
        row = cursor.fetchone()
        if row:
            return int(row[0])

    if "name" in columns:
        for name in (f"Тур {round_number}", f"{round_number} тур", str(round_number), f"Round {round_number}"):
            cursor.execute("SELECT id FROM rounds WHERE name = ? LIMIT 1", (name,))
            row = cursor.fetchone()
            if row:
                return int(row[0])

    return None


# ============================================================
# MATCH LOOKUP
# ============================================================

def _find_match(cursor: sqlite3.Cursor, round_id: int, home_team_id: int, away_team_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT * FROM matches WHERE round_id = ? AND home_team_id = ? AND away_team_id = ? LIMIT 1",
        (round_id, home_team_id, away_team_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


# ============================================================
# EXISTING RESULT
# ============================================================

def _get_existing_result(cursor: sqlite3.Cursor, match_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT id, match_id, home_goals, away_goals FROM match_results WHERE match_id = ? LIMIT 1",
        (match_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {"id": row[0], "match_id": row[1], "home_goals": row[2], "away_goals": row[3]}


# ============================================================
# UPDATE MATCH ACTUAL RESULT
# ============================================================

def _update_match_actual(cursor: sqlite3.Cursor, match_id: int, home_goals: int, away_goals: int) -> None:
    columns = _table_columns(cursor, "matches")
    assignments = []
    values = []

    if "actual_home" in columns:
        assignments.append("actual_home = ?")
        values.append(int(home_goals))
    if "actual_away" in columns:
        assignments.append("actual_away = ?")
        values.append(int(away_goals))
    if "status" in columns:
        assignments.append("status = ?")
        values.append("finished")
    if "updated_at" in columns:
        assignments.append("updated_at = ?")
        values.append(datetime.now().isoformat())

    if not assignments:
        return

    values.append(int(match_id))
    cursor.execute(f"UPDATE matches SET {', '.join(assignments)} WHERE id = ?", values)


# ============================================================
# INSERT MATCH RESULT
# ============================================================

def _insert_match_result(cursor: sqlite3.Cursor, match_id: int, home_goals: int, away_goals: int) -> None:
    columns = _table_columns(cursor, "match_results")
    required = {"match_id", "home_goals", "away_goals"}

    if not required.issubset(set(columns)):
        raise RuntimeError(f"match_results не содержит обязательные поля: {required - set(columns)}")

    insert_columns = ["match_id", "home_goals", "away_goals"]
    values = [int(match_id), int(home_goals), int(away_goals)]

    if "home_penalty_goals" in columns:
        insert_columns.append("home_penalty_goals")
        values.append(0)
    if "away_penalty_goals" in columns:
        insert_columns.append("away_penalty_goals")
        values.append(0)

    placeholders = ", ".join("?" for _ in insert_columns)
    cursor.execute(
        f"INSERT INTO match_results ({', '.join(insert_columns)}) VALUES ({placeholders})",
        values,
    )


# ============================================================
# IMPORT ONE MATCH
# ============================================================

def _import_match(cursor: sqlite3.Cursor, item: Tuple[int, str, str, str, int, int], result: Dict[str, Any]) -> None:
    round_number, date_value, home_team, away_team, home_goals, away_goals = item

    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    if not home_team or not away_team:
        raise ValueError(f"Не удалось нормализовать команды: {home_team} — {away_team}")

    home_team_id = _find_team_id(cursor, home_team)
    away_team_id = _find_team_id(cursor, away_team)

    if home_team_id is None:
        raise ValueError(f"Команда не найдена в БД: {home_team}")
    if away_team_id is None:
        raise ValueError(f"Команда не найдена в БД: {away_team}")

    round_id = _find_round_id(cursor, round_number)
    if round_id is None:
        raise ValueError(f"Тур не найден в БД: {round_number}")

    match = _find_match(cursor, round_id, home_team_id, away_team_id)
    if match is None:
        raise ValueError(f"Матч отсутствует в существующем календаре: тур {round_number}, {home_team} — {away_team}")

    match_id = int(match["id"])
    existing = _get_existing_result(cursor, match_id)

    if existing is not None:
        existing_home = existing["home_goals"]
        existing_away = existing["away_goals"]

        if int(existing_home) == int(home_goals) and int(existing_away) == int(away_goals):
            result["already_present"] += 1
            _update_match_actual(cursor, match_id, home_goals, away_goals)
            result["matches"].append({
                "match_id": match_id,
                "round": int(round_number),
                "date": date_value,
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "score": f"{home_goals}:{away_goals}",
                "status": "already_present",
            })
            return

        raise ValueError(
            f"КОНФЛИКТ результата: {home_team} — {away_team}. "
            f"В БД: {existing_home}:{existing_away}; "
            f"исторический: {home_goals}:{away_goals}"
        )

    _insert_match_result(cursor, match_id, home_goals, away_goals)
    result["inserted_results"] += 1
    _update_match_actual(cursor, match_id, home_goals, away_goals)
    result["updated_matches"] += 1

    result["matches"].append({
        "match_id": match_id,
        "round": int(round_number),
        "date": date_value,
        "home_team": home_team,
        "away_team": away_team,
        "home_goals": int(home_goals),
        "away_goals": int(away_goals),
        "score": f"{home_goals}:{away_goals}",
        "status": "imported",
        "source": IMPORT_SOURCE,
        "method": IMPORT_METHOD,
        "version": IMPORT_VERSION,
    })


# ============================================================
# PRE-FLIGHT
# ============================================================

def _preflight(cursor: sqlite3.Cursor) -> List[str]:
    errors = []
    required_tables = ("teams", "rounds", "matches", "match_results")

    for table in required_tables:
        if not _table_exists(cursor, table):
            errors.append(f"Отсутствует таблица БД: {table}")

    if errors:
        return errors

    match_columns = set(_table_columns(cursor, "matches"))
    required_match_columns = {"id", "round_id", "home_team_id", "away_team_id"}
    missing_match = required_match_columns - match_columns
    if missing_match:
        errors.append(f"matches не содержит поля: {missing_match}")

    result_columns = set(_table_columns(cursor, "match_results"))
    required_result_columns = {"match_id", "home_goals", "away_goals"}
    missing_result = required_result_columns - result_columns
    if missing_result:
        errors.append(f"match_results не содержит поля: {missing_result}")

    return errors


# ============================================================
# PUBLIC IMPORT
# ============================================================

def import_historical_results(db_path: Optional[str] = None) -> Dict[str, Any]:
    validation = validate_historical_data()
    if not validation["success"]:
        return validation

    result = _empty_result()
    path = Path(db_path) if db_path else DEFAULT_DB_PATH

    if not path.exists():
        result["errors"].append(f"База данных не найдена: {path}")
        return result

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        preflight_errors = _preflight(cursor)
        if preflight_errors:
            result["errors"].extend(preflight_errors)
            conn.rollback()
            return result

        for item in HISTORICAL_MATCHES:
            _import_match(cursor, item, result)

        total_processed = result["inserted_results"] + result["already_present"]
        if total_processed != EXPECTED_MATCHES:
            raise RuntimeError(f"Количество обработанных результатов: {total_processed}; ожидалось {EXPECTED_MATCHES}")

        conn.commit()
        result["rounds_imported"] = sorted({int(match["round"]) for match in result["matches"]})
        result["success"] = True

        logger.info(
            "FAJ RPL historical import completed: inserted=%s already_present=%s updated_matches=%s",
            result["inserted_results"],
            result["already_present"],
            result["updated_matches"],
        )
        return result

    except Exception as exc:
        conn.rollback()
        result["success"] = False
        result["errors"].append(str(exc))
        logger.exception("FAJ historical import failed")
        return result

    finally:
        conn.close()


# ============================================================
# CONVENIENCE API
# ============================================================

def load_rpl_historical_results(db_path: Optional[str] = None) -> Dict[str, Any]:
    return import_historical_results(db_path)


# ============================================================
# STATUS
# ============================================================

def get_historical_import_status(db_path: Optional[str] = None) -> Dict[str, Any]:
    result = {
        "success": False,
        "expected": EXPECTED_MATCHES,
        "present": 0,
        "missing": 0,
        "conflicts": 0,
        "errors": [],
        "matches": [],
    }

    path = Path(db_path) if db_path else DEFAULT_DB_PATH

    if not path.exists():
        result["errors"].append(f"База данных не найдена: {path}")
        return result

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        preflight_errors = _preflight(cursor)
        if preflight_errors:
            result["errors"].extend(preflight_errors)
            return result

        for item in HISTORICAL_MATCHES:
            round_number, date_value, home_team, away_team, home_goals, away_goals = item

            home_team = normalize_team(home_team)
            away_team = normalize_team(away_team)

            home_team_id = _find_team_id(cursor, home_team)
            away_team_id = _find_team_id(cursor, away_team)

            if home_team_id is None or away_team_id is None:
                result["missing"] += 1
                result["matches"].append({
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "status": "missing_team",
                })
                continue

            round_id = _find_round_id(cursor, round_number)
            if round_id is None:
                result["missing"] += 1
                result["matches"].append({
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "status": "missing_round",
                })
                continue

            match = _find_match(cursor, round_id, home_team_id, away_team_id)
            if match is None:
                result["missing"] += 1
                result["matches"].append({
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "status": "missing_match",
                })
                continue

            match_id = int(match["id"])
            existing = _get_existing_result(cursor, match_id)

            if existing is None:
                result["missing"] += 1
                result["matches"].append({
                    "match_id": match_id,
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "status": "missing_result",
                })
                continue

            existing_home = int(existing["home_goals"])
            existing_away = int(existing["away_goals"])

            if existing_home == int(home_goals) and existing_away == int(away_goals):
                result["present"] += 1
                result["matches"].append({
                    "match_id": match_id,
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "status": "present",
                })
            else:
                result["conflicts"] += 1
                result["matches"].append({
                    "match_id": match_id,
                    "round": round_number,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": f"{home_goals}:{away_goals}",
                    "db_score": f"{existing_home}:{existing_away}",
                    "status": "conflict",
                })

        result["success"] = not result["errors"]
        return result

    except Exception as exc:
        result["errors"].append(str(exc))
        return result

    finally:
        conn.close()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("\n" + "=" * 72)
    print("FAJ RPL HISTORICAL IMPORTER v12.1")
    print("=" * 72)

    validation = validate_historical_data()
    print(f"Исторических матчей: {validation['found']}")
    print(f"Туры: {validation['rounds']}")

    if validation["errors"]:
        print("\n❌ ОШИБКИ В ИСТОРИЧЕСКОМ НАБОРЕ:")
        for error in validation["errors"]:
            print(f"   {error}")
        raise SystemExit(1)

    print("Проверка исторического набора: OK")

    print("\nПроверка текущего состояния БД...")
    status = get_historical_import_status()
    if status["errors"]:
        for error in status["errors"]:
            print(f"❌ {error}")
        raise SystemExit(1)

    print(f"Уже присутствует: {status['present']}")
    print(f"Отсутствует: {status['missing']}")
    print(f"Конфликтов: {status['conflicts']}")

    print("\nЗапуск исторического импорта...")
    result = import_historical_results()

    print(f"\nУспех: {result['success']}")
    print(f"Добавлено результатов: {result['inserted_results']}")
    print(f"Обновлено матчей: {result['updated_matches']}")
    print(f"Уже существовало: {result['already_present']}")
    print(f"Ошибок: {len(result['errors'])}")

    if result["rounds_imported"]:
        print(f"Обработаны туры: {result['rounds_imported']}")

    if result["errors"]:
        print("\n❌ ОШИБКИ:")
        for error in result["errors"]:
            print(f"   {error}")

    print("\n" + "=" * 72)
