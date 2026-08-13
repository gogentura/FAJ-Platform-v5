#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL HISTORICAL IMPORTER
===========================================================

Назначение:
    Однократный/повторяемый импорт проверенных исторических
    результатов РПЛ 2026/27 в SQLite.

ВАЖНО:
    - НЕ является парсером.
    - НЕ использует NB-Bet как постоянный источник.
    - НЕ делает DELETE.
    - НЕ удаляет существующие матчи.
    - НЕ создаёт прогнозы.
    - НЕ запускает обучение.
    - НЕ изменяет календарь.
    - Идемпотентен.

Цепочка:
    VERIFIED HISTORICAL DATA
              ↓
    round + home + away
              ↓
       existing match
              ↓
       match_results
              +
       matches.actual_home
       matches.actual_away
       matches.status
              ↓
          FAJ DATABASE

Источник:
    historical/manual_import
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
IMPORT_VERSION = "1.0"
EXPECTED_MATCHES = 24


# ============================================================
# DATABASE PATH
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "faj.db"


# ============================================================
# VERIFIED HISTORICAL DATA
# ============================================================
#
# ВАЖНО:
#     Здесь находятся ТОЛЬКО фактические результаты.
#     Никаких прогнозов. Никаких коэффициентов. Никакого xG.
#     Никакого NB-Bet.
#
# Формат:
#     (
#         round,
#         date,
#         home_team,
#         away_team,
#         home_goals,
#         away_goals,
#     )
#
# Все 24 результата подтверждены.
#

HISTORICAL_MATCHES: List[Tuple[int, str, str, str, int, int]] = [

    # ========================================================
    # TOUR 1 (8 матчей)
    # ========================================================
    (
        1,
        "2026-07-24",
        "ЦСКА",
        "Балтика",
        2,
        1,
    ),
    (
        1,
        "2026-07-25",
        "Динамо Москва",
        "Крылья Советов",
        0,
        0,
    ),
    (
        1,
        "2026-07-25",
        "Акрон",
        "Зенит",
        0,
        5,
    ),
    (
        1,
        "2026-07-25",
        "Факел",
        "Динамо Махачкала",
        1,
        2,
    ),
    (
        1,
        "2026-07-25",
        "Спартак",
        "Родина",
        3,
        0,
    ),
    (
        1,
        "2026-07-26",
        "Оренбург",
        "Ростов",
        2,
        1,
    ),
    (
        1,
        "2026-07-26",
        "Локомотив",
        "Ахмат",
        1,
        1,
    ),
    (
        1,
        "2026-07-26",
        "Рубин",
        "Краснодар",
        1,
        3,
    ),

    # ========================================================
    # TOUR 2 (8 матчей)
    # ========================================================
    (
        2,
        "2026-07-31",
        "Родина",
        "Ростов",
        2,
        4,
    ),
    (
        2,
        "2026-08-01",
        "Акрон",
        "Рубин",
        1,
        2,
    ),
    (
        2,
        "2026-08-01",
        "ЦСКА",
        "Крылья Советов",
        1,
        1,
    ),
    (
        2,
        "2026-08-01",
        "Динамо Махачкала",
        "Локомотив",
        2,
        1,
    ),
    (
        2,
        "2026-08-01",
        "Балтика",
        "Динамо Москва",
        2,
        1,
    ),
    (
        2,
        "2026-08-02",
        "Оренбург",
        "Зенит",
        0,
        3,
    ),
    (
        2,
        "2026-08-02",
        "Краснодар",
        "Факел",
        3,
        2,
    ),
    (
        2,
        "2026-08-02",
        "Ахмат",
        "Спартак",
        1,
        2,
    ),

    # ========================================================
    # TOUR 3 (8 матчей) — ВСЕ ПОДТВЕРЖДЕНЫ
    # ========================================================
    (
        3,
        "2026-08-08",
        "Крылья Советов",
        "Балтика",
        0,
        2,
    ),
    (
        3,
        "2026-08-08",
        "Локомотив",
        "Акрон",
        0,
        0,
    ),
    (
        3,
        "2026-08-08",
        "Ростов",
        "ЦСКА",
        0,
        0,
    ),
    (
        3,
        "2026-08-09",
        "Динамо Москва",
        "Динамо Махачкала",
        3,
        1,          # ✅ ИСПРАВЛЕНО: 0:0 → 3:1
    ),
    (
        3,
        "2026-08-09",
        "Зенит",
        "Родина",
        1,
        2,
    ),
    (
        3,
        "2026-08-09",
        "Спартак",
        "Краснодар",
        1,
        2,
    ),
    (
        3,
        "2026-08-09",
        "Рубин",
        "Оренburg",     # Оренбург
        1,
        1,
    ),
    (
        3,
        "2026-08-10",
        "Факел",
        "Ахмат",
        0,
        0,
    ),
]


# ============================================================
# TEAM ALIASES
# ============================================================

TEAM_ALIASES = {
    "Динамо М": "Динамо Москва",
    "Динамо Москва": "Динамо Москва",
    "Динамо Мх": "Динамо Махачкала",
    "Динамо Махачкала": "Динамо Махачкала",
    "Спартак Москва": "Спартак",
    "Спартак М": "Спартак",
    "ЦСКА Москва": "ЦСКА",
    "Локомотив Москва": "Локомотив",
    "Акрон Тольятти": "Акрон",
    "Крылья Советов Самара": "Крылья Советов",
    "Балтика Калининград": "Балтика",
    "Родина Москва": "Родина",
    "Ахмат Грозный": "Ахмат",
    "Рубин Казань": "Рубин",
    "Зенит Санкт-Петербург": "Зенит",
    "Факел Воронеж": "Факел",
    "Оренбург": "Оренбург",
    "Оренburg": "Оренбург",
    "Ростов": "Ростов",
    "Краснодар": "Краснодар",
}


def normalize_team(team: Optional[str]) -> Optional[str]:
    if not team:
        return None
    value = str(team).strip()
    return TEAM_ALIASES.get(value, value)


# ============================================================
# IMPORT RESULT
# ============================================================

def _result() -> Dict[str, Any]:
    return {
        "success": False,
        "source": IMPORT_SOURCE,
        "method": IMPORT_METHOD,
        "version": IMPORT_VERSION,
        "season": SEASON_YEAR,
        "expected": EXPECTED_MATCHES,
        "found": len(HISTORICAL_MATCHES),
        "inserted_results": 0,
        "updated_matches": 0,
        "already_present": 0,
        "skipped": 0,
        "errors": [],
        "rounds": [],
        "matches": [],
    }


# ============================================================
# VALIDATE HISTORICAL DATA
# ============================================================

def validate_historical_data() -> Dict[str, Any]:
    result = _result()
    seen = set()

    for item in HISTORICAL_MATCHES:
        if len(item) != 6:
            result["errors"].append(f"Некорректная запись: {item}")
            continue

        (
            round_number,
            date_value,
            home_team,
            away_team,
            home_goals,
            away_goals,
        ) = item

        home_team = normalize_team(home_team)
        away_team = normalize_team(away_team)

        key = (int(round_number), home_team, away_team)

        if key in seen:
            result["errors"].append(f"Дубликат: {key}")
            continue

        seen.add(key)

        if not (1 <= int(round_number) <= 30):
            result["errors"].append(f"Некорректный тур: {round_number}")

        if home_team == away_team:
            result["errors"].append(f"Одинаковые команды: {key}")

        if int(home_goals) < 0 or int(away_goals) < 0:
            result["errors"].append(f"Отрицательный счёт: {key}")

    if len(HISTORICAL_MATCHES) != EXPECTED_MATCHES:
        result["errors"].append(
            f"Исторический набор содержит {len(HISTORICAL_MATCHES)} матчей "
            f"вместо {EXPECTED_MATCHES}."
        )

    rounds = sorted({int(item[0]) for item in HISTORICAL_MATCHES})
    result["rounds"] = rounds

    for round_number in range(1, 4):
        count = sum(1 for item in HISTORICAL_MATCHES if int(item[0]) == round_number)
        if count != 8:
            result["errors"].append(f"Тур {round_number}: {count}/8 матчей.")

    result["success"] = len(result["errors"]) == 0
    return result


# ============================================================
# DATABASE HELPERS
# ============================================================

def _find_team_id(cursor: sqlite3.Cursor, team_name: str) -> Optional[int]:
    canonical = normalize_team(team_name)
    cursor.execute(
        """
        SELECT id
        FROM teams
        WHERE name = ?
        LIMIT 1
        """,
        (canonical,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return int(row[0])


def _find_round_id(cursor: sqlite3.Cursor, round_number: int) -> Optional[int]:
    cursor.execute(
        """
        SELECT id
        FROM rounds
        WHERE round_number = ?
        LIMIT 1
        """,
        (int(round_number),),
    )
    row = cursor.fetchone()
    if row:
        return int(row[0])

    cursor.execute(
        """
        SELECT id
        FROM rounds
        WHERE name = ?
        LIMIT 1
        """,
        (f"Тур {int(round_number)}",),
    )
    row = cursor.fetchone()
    if row:
        return int(row[0])

    return None


def _find_match(
    cursor: sqlite3.Cursor,
    round_id: int,
    home_team_id: int,
    away_team_id: int,
    date_value: str,
) -> Optional[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM matches
        WHERE round_id = ?
          AND home_team_id = ?
          AND away_team_id = ?
        LIMIT 1
        """,
        (round_id, home_team_id, away_team_id),
    )
    row = cursor.fetchone()
    if not row:
        return None

    columns = [description[0] for description in cursor.description]
    return dict(zip(columns, row))


# ============================================================
# IMPORT ONE MATCH
# ============================================================

def _import_match(
    cursor: sqlite3.Cursor,
    item: Tuple[int, str, str, str, int, int],
    result: Dict[str, Any],
) -> None:
    (
        round_number,
        date_value,
        home_team,
        away_team,
        home_goals,
        away_goals,
    ) = item

    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    home_team_id = _find_team_id(cursor, home_team)
    away_team_id = _find_team_id(cursor, away_team)

    if home_team_id is None:
        raise ValueError(f"Команда не найдена в БД: {home_team}")

    if away_team_id is None:
        raise ValueError(f"Команда не найдена в БД: {away_team}")

    round_id = _find_round_id(cursor, int(round_number))
    if round_id is None:
        raise ValueError(f"Тур не найден в БД: {round_number}")

    match = _find_match(
        cursor,
        round_id,
        home_team_id,
        away_team_id,
        date_value,
    )

    if match is None:
        raise ValueError(
            f"Матч отсутствует в календаре: тур {round_number}, {home_team} — {away_team}"
        )

    match_id = int(match["id"])

    # --------------------------------------------------------
    # Проверяем существующий результат
    # --------------------------------------------------------
    cursor.execute(
        """
        SELECT id, home_goals, away_goals
        FROM match_results
        WHERE match_id = ?
        LIMIT 1
        """,
        (match_id,),
    )
    existing_result = cursor.fetchone()

    if existing_result:
        existing_home = existing_result[1]
        existing_away = existing_result[2]

        if existing_home == int(home_goals) and existing_away == int(away_goals):
            result["already_present"] += 1
            return

        raise ValueError(
            f"Конфликт результата для {home_team} — {away_team}: "
            f"в БД {existing_home}:{existing_away}, "
            f"исторический {home_goals}:{away_goals}"
        )

    # --------------------------------------------------------
    # INSERT match_results
    # --------------------------------------------------------
    cursor.execute(
        """
        INSERT OR IGNORE INTO match_results (
            match_id,
            home_goals,
            away_goals,
            home_penalty_goals,
            away_penalty_goals
        )
        VALUES (?, ?, ?, 0, 0)
        """,
        (match_id, int(home_goals), int(away_goals)),
    )
    if cursor.rowcount > 0:
        result["inserted_results"] += 1

    # --------------------------------------------------------
    # UPDATE matches
    # --------------------------------------------------------
    cursor.execute(
        """
        UPDATE matches
        SET
            actual_home = ?,
            actual_away = ?,
            status = 'finished',
            updated_at = ?
        WHERE id = ?
        """,
        (
            int(home_goals),
            int(away_goals),
            datetime.now().isoformat(),
            match_id,
        ),
    )
    if cursor.rowcount > 0:
        result["updated_matches"] += 1

    result["matches"].append({
        "match_id": match_id,
        "round": int(round_number),
        "home_team": home_team,
        "away_team": away_team,
        "score": f"{home_goals}:{away_goals}",
        "source": IMPORT_SOURCE,
        "method": IMPORT_METHOD,
    })


# ============================================================
# PUBLIC IMPORT
# ============================================================

def import_historical_results(db_path: Optional[str] = None) -> Dict[str, Any]:
    validation = validate_historical_data()
    if not validation["success"]:
        return validation

    result = _result()
    path = Path(db_path) if db_path else DEFAULT_DB_PATH

    if not path.exists():
        result["errors"].append(f"База данных не найдена: {path}")
        return result

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        for item in HISTORICAL_MATCHES:
            try:
                _import_match(cursor, item, result)
            except Exception as exc:
                result["errors"].append(str(exc))

        # ----------------------------------------------------
        # Если есть хотя бы одна ошибка — откатываем ВСЮ транзакцию.
        # Нельзя получить 23/24 исторических матчей
        # и оставить базу в частично изменённом состоянии.
        # ----------------------------------------------------
        if result["errors"]:
            conn.rollback()
            result["success"] = False
            return result

        conn.commit()
        result["success"] = True

        logger.info(
            "Historical import completed: %s inserted, %s updated, %s already present.",
            result["inserted_results"],
            result["updated_matches"],
            result["already_present"],
        )

        return result

    except Exception as exc:
        conn.rollback()
        result["success"] = False
        result["errors"].append(str(exc))
        return result

    finally:
        conn.close()


# ============================================================
# CONVENIENCE API
# ============================================================

def load_rpl_historical_results(db_path: Optional[str] = None) -> Dict[str, Any]:
    return import_historical_results(db_path=db_path)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print()
    print("=" * 70)
    print("FAJ RPL HISTORICAL IMPORTER v12.1")
    print("=" * 70)

    validation = validate_historical_data()
    print(f"Исторических матчей: {validation['found']}")
    print(f"Туры: {validation['rounds']}")

    if validation["errors"]:
        print()
        print("ОШИБКИ В НАБОРЕ:")
        for error in validation["errors"]:
            print(f"  ❌ {error}")
        raise SystemExit(1)

    result = import_historical_results()

    print()
    print(f"Успех: {result['success']}")
    print(f"Добавлено результатов: {result['inserted_results']}")
    print(f"Обновлено матчей: {result['updated_matches']}")
    print(f"Уже существовало: {result['already_present']}")
    print(f"Ошибок: {len(result['errors'])}")

    if result["errors"]:
        print()
        print("ОШИБКИ:")
        for error in result["errors"]:
            print(f"  ❌ {error}")

    print("=" * 70)
