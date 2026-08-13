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
за 1-3 туры непосредственно в SQLite.

Это НЕ парсер.

Исторические результаты являются фиксированным набором
проверенных данных и не зависят от NB-Bet после импорта.

ЦЕПОЧКА
-------
Verified historical data
        ↓
round + home_team + away_team
        ↓
existing match in calendar
        ↓
match_results
        +
matches.actual_home
matches.actual_away
matches.status
        ↓
FAJ database

ПРИНЦИПЫ
--------
- DELETE отсутствует
- существующие матчи не удаляются
- календарь не создаётся
- прогнозы не создаются
- обучение не запускается
- паспорта не создаются
- конфликтующие результаты не перезаписываются
- импорт идемпотентен
- вся операция выполняется одной транзакцией
- при ошибке импорт полностью откатывается

Источник данных:
    historical/manual_import

Версия:
    1.1
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
IMPORT_VERSION = "1.1"

EXPECTED_MATCHES = 24
EXPECTED_ROUNDS = (1, 2, 3)


# ============================================================
# DATABASE
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DB_PATH = ROOT_DIR / "data" / "faj.db"


# ============================================================
# VERIFIED HISTORICAL RESULTS
# ============================================================
#
# Формат:
#
# (
#     round,
#     date,
#     home_team,
#     away_team,
#     home_goals,
#     away_goals,
# )
#
# Всего:
#     24 матча
#     8 матчей в каждом туре
#
# ============================================================

HISTORICAL_MATCHES: List[
    Tuple[int, str, str, str, int, int]
] = [

    # ========================================================
    # ТУР 1
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
    # ТУР 2
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
    # ТУР 3
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
        "2026-08-09",
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
        1,
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
        "2026-08-10",
        "Спартак",
        "Краснодар",
        1,
        2,
    ),

    (
        3,
        "2026-08-10",
        "Рубин",
        "Оренбург",
        1,
        1,
    ),

    (
        3,
        "2026-08-11",
        "Факел",
        "Ахмат",
        0,
        0,
    ),
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
    """
    Приводит название команды к каноническому названию FAJ.
    """

    if team is None:
        return None

    value = str(team).strip()

    if not value:
        return None

    return TEAM_ALIASES.get(value, value)


# ============================================================
# RESULT STRUCTURE
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

        "skipped": 0,

        "errors": [],

        "rounds": [],
        "rounds_imported": [],

        "matches": [],
    }


# ============================================================
# VALIDATION
# ============================================================

def validate_historical_data() -> Dict[str, Any]:
    """
    Проверяет внутренний набор исторических результатов
    до подключения к БД.
    """

    result = _empty_result()

    seen = set()

    for item in HISTORICAL_MATCHES:

        if len(item) != 6:
            result["errors"].append(
                f"Некорректная запись: {item}"
            )
            continue

        (
            round_number,
            date_value,
            home_team,
            away_team,
            home_goals,
            away_goals,
        ) = item

        try:
            round_number = int(round_number)
            home_goals = int(home_goals)
            away_goals = int(away_goals)
        except (TypeError, ValueError):
            result["errors"].append(
                f"Некорректные числовые значения: {item}"
            )
            continue

        home_team = normalize_team(home_team)
        away_team = normalize_team(away_team)

        key = (
            round_number,
            home_team,
            away_team,
        )

        if key in seen:
            result["errors"].append(
                f"Дубликат матча: {key}"
            )
            continue

        seen.add(key)

        if round_number not in EXPECTED_ROUNDS:
            result["errors"].append(
                f"Недопустимый тур: {round_number}"
            )

        if not date_value:
            result["errors"].append(
                f"Нет даты: {key}"
            )

        if home_team is None or away_team is None:
            result["errors"].append(
                f"Не определена команда: {key}"
            )

        if home_team == away_team:
            result["errors"].append(
                f"Одинаковые команды: {key}"
            )

        if home_goals < 0 or away_goals < 0:
            result["errors"].append(
                f"Отрицательный счёт: {key}"
            )

    if len(HISTORICAL_MATCHES) != EXPECTED_MATCHES:
        result["errors"].append(
            "Количество исторических матчей: "
            f"{len(HISTORICAL_MATCHES)}, "
            f"ожидалось {EXPECTED_MATCHES}."
        )

    rounds = sorted(
        {
            int(item[0])
            for item in HISTORICAL_MATCHES
        }
    )

    result["rounds"] = rounds

    for round_number in EXPECTED_ROUNDS:

        count = sum(
            1
            for item in HISTORICAL_MATCHES
            if int(item[0]) == round_number
        )

        if count != 8:
            result["errors"].append(
                f"Тур {round_number}: "
                f"{count}/8 матчей."
            )

    result["success"] = (
        len(result["errors"]) == 0
    )

    return result


# ============================================================
# DATABASE SCHEMA HELPERS
# ============================================================

def _table_exists(
    cursor: sqlite3.Cursor,
    table_name: str,
) -> bool:

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    )

    return cursor.fetchone() is not None


def _table_columns(
    cursor: sqlite3.Cursor,
    table_name: str,
) -> List[str]:

    cursor.execute(
        f'PRAGMA table_info("{table_name}")'
    )

    return [
        row[1]
        for row in cursor.fetchall()
    ]


# ============================================================
# TEAM LOOKUP
# ============================================================

def _find_team_id(
    cursor: sqlite3.Cursor,
    team_name: str,
) -> Optional[int]:

    canonical = normalize_team(team_name)

    if not canonical:
        return None

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

    if row:
        return int(row[0])

    # --------------------------------------------------------
    # Дополнительная попытка через aliases
    # --------------------------------------------------------

    aliases = [
        alias
        for alias, normalized in TEAM_ALIASES.items()
        if normalized == canonical
    ]

    for alias in aliases:

        cursor.execute(
            """
            SELECT id
            FROM teams
            WHERE name = ?
            LIMIT 1
            """,
            (alias,),
        )

        row = cursor.fetchone()

        if row:
            return int(row[0])

    return None


# ============================================================
# ROUND LOOKUP
# ============================================================

def _find_round_id(
    cursor: sqlite3.Cursor,
    round_number: int,
) -> Optional[int]:
    """
    Находит тур максимально безопасно.

    Если в rounds есть season_id, пытаемся сначала
    использовать сезон 2026/27.

    Если season_id отсутствует, работаем со старой
    структурой rounds.

    Никаких изменений таблицы rounds здесь не выполняется.
    """

    round_number = int(round_number)

    columns = _table_columns(
        cursor,
        "rounds",
    )

    # --------------------------------------------------------
    # 1. Есть season_id
    # --------------------------------------------------------

    if "season_id" in columns:

        # Сначала пытаемся найти сезон.
        season_id = None

        if _table_exists(
            cursor,
            "seasons",
        ):

            season_columns = _table_columns(
                cursor,
                "seasons",
            )

            possible_columns = [
                "name",
                "season",
                "season_name",
                "year",
            ]

            for column in possible_columns:

                if column not in season_columns:
                    continue

                cursor.execute(
                    f'''
                    SELECT id
                    FROM seasons
                    WHERE "{column}" = ?
                    LIMIT 1
                    ''',
                    (SEASON_YEAR,),
                )

                row = cursor.fetchone()

                if row:
                    season_id = int(row[0])
                    break

        if season_id is not None:

            if "round_number" in columns:

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
                    return int(row[0])

            if "name" in columns:

                cursor.execute(
                    """
                    SELECT id
                    FROM rounds
                    WHERE season_id = ?
                      AND name = ?
                    LIMIT 1
                    """,
                    (
                        season_id,
                        f"Тур {round_number}",
                    ),
                )

                row = cursor.fetchone()

                if row:
                    return int(row[0])

    # --------------------------------------------------------
    # 2. Обычная структура rounds.round_number
    # --------------------------------------------------------

    if "round_number" in columns:

        cursor.execute(
            """
            SELECT id
            FROM rounds
            WHERE round_number = ?
            LIMIT 1
            """,
            (round_number,),
        )

        row = cursor.fetchone()

        if row:
            return int(row[0])

    # --------------------------------------------------------
    # 3. rounds.name
    # --------------------------------------------------------

    if "name" in columns:

        possible_names = [
            f"Тур {round_number}",
            f"{round_number} тур",
            f"{round_number}",
            f"Round {round_number}",
        ]

        for name in possible_names:

            cursor.execute(
                """
                SELECT id
                FROM rounds
                WHERE name = ?
                LIMIT 1
                """,
                (name,),
            )

            row = cursor.fetchone()

            if row:
                return int(row[0])

    return None


# ============================================================
# MATCH LOOKUP
# ============================================================

def _find_match(
    cursor: sqlite3.Cursor,
    round_id: int,
    home_team_id: int,
    away_team_id: int,
    date_value: str,
) -> Optional[Dict[str, Any]]:
    """
    Основной ключ:
        round_id + home_team_id + away_team_id

    Дата НЕ является обязательной частью ключа.

    Это важно, потому что дата в календаре могла быть
    сохранена с другим временем или форматом.
    """

    cursor.execute(
        """
        SELECT *
        FROM matches
        WHERE round_id = ?
          AND home_team_id = ?
          AND away_team_id = ?
        LIMIT 1
        """,
        (
            round_id,
            home_team_id,
            away_team_id,
        ),
    )

    row = cursor.fetchone()

    if not row:
        return None

    columns = [
        description[0]
        for description in cursor.description
    ]

    return dict(
        zip(columns, row)
    )


# ============================================================
# EXISTING RESULT
# ============================================================

def _get_existing_result(
    cursor: sqlite3.Cursor,
    match_id: int,
) -> Optional[Dict[str, Any]]:

    cursor.execute(
        """
        SELECT
            id,
            match_id,
            home_goals,
            away_goals
        FROM match_results
        WHERE match_id = ?
        LIMIT 1
        """,
        (match_id,),
    )

    row = cursor.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "match_id": row[1],
        "home_goals": row[2],
        "away_goals": row[3],
    }


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

    if not home_team or not away_team:
        raise ValueError(
            f"Не удалось нормализовать команды: "
            f"{home_team} — {away_team}"
        )

    # --------------------------------------------------------
    # TEAM IDS
    # --------------------------------------------------------

    home_team_id = _find_team_id(
        cursor,
        home_team,
    )

    away_team_id = _find_team_id(
        cursor,
        away_team,
    )

    if home_team_id is None:
        raise ValueError(
            f"Команда не найдена в БД: {home_team}"
        )

    if away_team_id is None:
        raise ValueError(
            f"Команда не найдена в БД: {away_team}"
        )

    # --------------------------------------------------------
    # ROUND ID
    # --------------------------------------------------------

    round_id = _find_round_id(
        cursor,
        int(round_number),
    )

    if round_id is None:
        raise ValueError(
            f"Тур не найден в БД: {round_number}"
        )

    # --------------------------------------------------------
    # MATCH
    # --------------------------------------------------------

    match = _find_match(
        cursor,
        round_id,
        home_team_id,
        away_team_id,
        date_value,
    )

    if match is None:
        raise ValueError(
            "Матч отсутствует в календаре: "
            f"тур {round_number}, "
            f"{home_team} — {away_team}"
        )

    match_id = int(
        match["id"]
    )

    # --------------------------------------------------------
    # EXISTING RESULT
    # --------------------------------------------------------

    existing = _get_existing_result(
        cursor,
        match_id,
    )

    if existing is not None:

        existing_home = existing["home_goals"]
        existing_away = existing["away_goals"]

        # Полностью совпадает.
        if (
            int(existing_home) == int(home_goals)
            and int(existing_away) == int(away_goals)
        ):

            result["already_present"] += 1

            # Даже если match_results уже существует,
            # гарантируем актуальные поля matches.
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

            return

        # Конфликт — НЕ перезаписываем.
        raise ValueError(
            f"Конфликт результата: "
            f"{home_team} — {away_team}. "
            f"В БД: {existing_home}:{existing_away}; "
            f"исторический: {home_goals}:{away_goals}"
        )

    # --------------------------------------------------------
    # INSERT INTO match_results
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
        (
            match_id,
            int(home_goals),
            int(away_goals),
        ),
    )

    if cursor.rowcount > 0:
        result["inserted_results"] += 1

    # --------------------------------------------------------
    # UPDATE MATCH
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

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    result["matches"].append(
        {
            "match_id": match_id,
            "round": int(round_number),
            "date": date_value,
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": int(home_goals),
            "away_goals": int(away_goals),
            "score": (
                f"{int(home_goals)}:"
                f"{int(away_goals)}"
            ),
            "source": IMPORT_SOURCE,
            "method": IMPORT_METHOD,
        }
    )


# ============================================================
# PUBLIC IMPORT
# ============================================================

def import_historical_results(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Основной импортёр.

    Все 24 матча импортируются в одной транзакции.

    Если хотя бы один матч не найден или обнаружен конфликт,
    вся транзакция откатывается.
    """

    # --------------------------------------------------------
    # VALIDATE STATIC DATA FIRST
    # --------------------------------------------------------

    validation = validate_historical_data()

    if not validation["success"]:
        return validation

    result = _empty_result()

    path = (
        Path(db_path)
        if db_path
        else DEFAULT_DB_PATH
    )

    # --------------------------------------------------------
    # DATABASE EXISTS
    # --------------------------------------------------------

    if not path.exists():

        result["errors"].append(
            f"База данных не найдена: {path}"
        )

        return result

    conn = sqlite3.connect(
        str(path)
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    try:

        # ----------------------------------------------------
        # REQUIRED TABLES
        # ----------------------------------------------------

        required_tables = [
            "teams",
            "rounds",
            "matches",
            "match_results",
        ]

        for table in required_tables:

            if not _table_exists(
                cursor,
                table,
            ):

                raise RuntimeError(
                    f"Отсутствует таблица БД: {table}"
                )

        # ----------------------------------------------------
        # IMPORT ALL 24
        # ----------------------------------------------------

        for item in HISTORICAL_MATCHES:

            try:

                _import_match(
                    cursor,
                    item,
                    result,
                )

            except Exception as exc:

                result["errors"].append(
                    str(exc)
                )

        # ----------------------------------------------------
        # ATOMIC TRANSACTION
        # ----------------------------------------------------

        if result["errors"]:

            conn.rollback()

            result["success"] = False

            return result

        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        conn.commit()

        result["rounds_imported"] = sorted(
            {
                int(match["round"])
                for match in result["matches"]
            }
        )

        result["success"] = True

        logger.info(
            "FAJ historical import completed: "
            "inserted=%s updated=%s already_present=%s",
            result["inserted_results"],
            result["updated_matches"],
            result["already_present"],
        )

        return result

    except Exception as exc:

        conn.rollback()

        result["success"] = False

        result["errors"].append(
            str(exc)
        )

        return result

    finally:

        conn.close()


# ============================================================
# CONVENIENCE API
# ============================================================

def load_rpl_historical_results(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:

    return import_historical_results(
        db_path=db_path
    )


# ============================================================
# SIMPLE STATUS
# ============================================================

def get_historical_import_status(
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Проверяет, сколько из 24 исторических результатов
    уже находятся в БД.

    Ничего не изменяет.
    """

    result = {
        "success": False,
        "expected": EXPECTED_MATCHES,
        "present": 0,
        "missing": 0,
        "conflicts": 0,
        "errors": [],
        "matches": [],
    }

    path = (
        Path(db_path)
        if db_path
        else DEFAULT_DB_PATH
    )

    if not path.exists():

        result["errors"].append(
            f"База данных не найдена: {path}"
        )

        return result

    conn = sqlite3.connect(
        str(path)
    )

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    try:

        for item in HISTORICAL_MATCHES:

            (
                round_number,
                date_value,
                home_team,
                away_team,
                home_goals,
                away_goals,
            ) = item

            home_team = normalize_team(
                home_team
            )

            away_team = normalize_team(
                away_team
            )

            home_team_id = _find_team_id(
                cursor,
                home_team,
            )

            away_team_id = _find_team_id(
                cursor,
                away_team,
            )

            if (
                home_team_id is None
                or away_team_id is None
            ):

                result["missing"] += 1

                continue

            round_id = _find_round_id(
                cursor,
                round_number,
            )

            if round_id is None:

                result["missing"] += 1

                continue

            match = _find_match(
                cursor,
                round_id,
                home_team_id,
                away_team_id,
                date_value,
            )

            if match is None:

                result["missing"] += 1

                continue

            match_id = int(
                match["id"]
            )

            existing = _get_existing_result(
                cursor,
                match_id,
            )

            if existing is None:

                result["missing"] += 1

                continue

            if (
                int(existing["home_goals"])
                == int(home_goals)
                and
                int(existing["away_goals"])
                == int(away_goals)
            ):

                result["present"] += 1

                result["matches"].append(
                    {
                        "round": round_number,
                        "home_team": home_team,
                        "away_team": away_team,
                        "score": (
                            f"{home_goals}:"
                            f"{away_goals}"
                        ),
                        "status": "present",
                    }
                )

            else:

                result["conflicts"] += 1

                result["matches"].append(
                    {
                        "round": round_number,
                        "home_team": home_team,
                        "away_team": away_team,
                        "score": (
                            f"{home_goals}:"
                            f"{away_goals}"
                        ),
                        "db_score": (
                            f"{existing['home_goals']}:"
                            f"{existing['away_goals']}"
                        ),
                        "status": "conflict",
                    }
                )

        result["success"] = (
            len(result["errors"]) == 0
        )

        return result

    except Exception as exc:

        result["errors"].append(
            str(exc)
        )

        return result

    finally:

        conn.close()


# ============================================================
# CLI
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

    print()
    print("=" * 72)
    print(
        "FAJ RPL HISTORICAL IMPORTER v12.1"
    )
    print("=" * 72)

    # --------------------------------------------------------
    # STATIC VALIDATION
    # --------------------------------------------------------

    validation = validate_historical_data()

    print(
        f"Исторических матчей: "
        f"{validation['found']}"
    )

    print(
        f"Туры: "
        f"{validation['rounds']}"
    )

    if validation["errors"]:

        print()
        print(
            "ОШИБКИ В НАБОРЕ ДАННЫХ:"
        )

        for error in validation["errors"]:

            print(
                f"  ❌ {error}"
            )

        raise SystemExit(1)

    print(
        "Проверка набора: OK"
    )

    # --------------------------------------------------------
    # DATABASE STATUS BEFORE IMPORT
    # --------------------------------------------------------

    print()
    print(
        "Проверка текущего состояния БД..."
    )

    status = get_historical_import_status()

    print(
        f"Уже присутствует: "
        f"{status['present']}"
    )

    print(
        f"Отсутствует: "
        f"{status['missing']}"
    )

    print(
        f"Конфликтов: "
        f"{status['conflicts']}"
    )

    # --------------------------------------------------------
    # IMPORT
    # --------------------------------------------------------

    print()
    print(
        "Запуск исторического импорта..."
    )

    result = import_historical_results()

    print()
    print(
        f"Успех: "
        f"{result['success']}"
    )

    print(
        f"Добавлено результатов: "
        f"{result['inserted_results']}"
    )

    print(
        f"Обновлено матчей: "
        f"{result['updated_matches']}"
    )

    print(
        f"Уже существовало: "
        f"{result['already_present']}"
    )

    print(
        f"Ошибок: "
        f"{len(result['errors'])}"
    )

    if result["rounds_imported"]:

        print(
            f"Обработаны туры: "
            f"{result['rounds_imported']}"
        )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    if result["errors"]:

        print()
        print(
            "ОШИБКИ:"
        )

        for error in result["errors"]:

            print(
                f"  ❌ {error}"
            )

    print()
    print("=" * 72)
