#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Database Migrations
=====================================================

НАЗНАЧЕНИЕ:
    Безопасное обновление существующей SQLite БД.

ВАЖНО:
    database.py является ЕДИНЫМ ИСТОЧНИКОМ
    актуальной схемы FAJ.

    migrations.py НЕ создаёт альтернативные
    версии существующих таблиц.

ПРИНЦИПЫ:
    - SQLite only
    - никаких DROP TABLE
    - никаких DELETE
    - никаких очисток данных
    - никаких пересозданий таблиц
    - только безопасные ALTER TABLE ADD COLUMN
    - каждая миграция регистрируется
      в schema_migrations
=====================================================
"""

import logging
from datetime import datetime
from typing import Optional

from app.database import get_connection


logger = logging.getLogger(__name__)


# ============================================================
# VERSION
# ============================================================

MIGRATION_VERSION = "12.1.0"


# ============================================================
# CONNECTION HELPERS
# ============================================================

def _table_exists(cursor, table_name: str) -> bool:
    """
    Проверяет существование таблицы.
    """
    cursor.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,)
    )

    return cursor.fetchone() is not None


def _column_exists(cursor, table_name: str, column_name: str) -> bool:
    """
    Проверяет существование колонки в таблице.
    """
    if not _table_exists(cursor, table_name):
        return False

    cursor.execute(
        f'PRAGMA table_info("{table_name}")'
    )

    columns = cursor.fetchall()

    for column in columns:
        if column["name"] == column_name:
            return True

    return False


def _migration_exists(cursor, version: str) -> bool:
    """
    Проверяет, была ли миграция уже применена.
    """

    if not _table_exists(cursor, "schema_migrations"):
        return False

    cursor.execute(
        """
        SELECT 1
        FROM schema_migrations
        WHERE version = ?
          AND success = 1
        LIMIT 1
        """,
        (version,)
    )

    return cursor.fetchone() is not None


def _register_migration(
    cursor,
    version: str,
    description: str,
    success: int = 1
):
    """
    Регистрирует результат миграции.
    """

    cursor.execute(
        """
        INSERT OR REPLACE INTO schema_migrations (
            version,
            description,
            applied_at,
            success
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            version,
            description,
            datetime.now().isoformat(),
            success
        )
    )


# ============================================================
# SAFE COLUMN ADD
# ============================================================

def _add_column_if_missing(
    cursor,
    table_name: str,
    column_name: str,
    column_definition: str
) -> bool:
    """
    Безопасно добавляет колонку, если её ещё нет.

    НИКОГДА не удаляет существующие данные.

    Возвращает:
        True  - колонка была добавлена
        False - колонка уже существовала
                  или таблица отсутствует
    """

    if not _table_exists(cursor, table_name):
        logger.warning(
            "Migration skipped: table does not exist: %s",
            table_name
        )
        return False

    if _column_exists(cursor, table_name, column_name):
        return False

    sql = (
        f'ALTER TABLE "{table_name}" '
        f'ADD COLUMN "{column_name}" {column_definition}'
    )

    cursor.execute(sql)

    logger.info(
        "Migration: added column %s.%s",
        table_name,
        column_name
    )

    return True


# ============================================================
# MIGRATION v12.1.0
# ============================================================

def migrate_v12_1_0(cursor) -> bool:
    """
    FAJ v12.1.0

    Безопасная структурная миграция старой SQLite БД.

    ВАЖНО:
        Здесь НЕТ CREATE TABLE для основных таблиц.

    Актуальная схема создаётся database.py.

    Эта миграция предназначена только для случаев,
    когда существующая faj.db имеет старую структуру
    и в ней отсутствуют необходимые колонки.

    Все операции идемпотентны.
    """

    logger.info(
        "Starting migration %s",
        MIGRATION_VERSION
    )

    # --------------------------------------------------------
    # TEAM PASSPORTS
    # --------------------------------------------------------
    #
    # Если team_passports отсутствует полностью,
    # database.py должен создать её через init_database().
    #
    # Здесь НЕ создаём таблицу.
    #
    if not _table_exists(cursor, "team_passports"):
        logger.info(
            "team_passports does not exist. "
            "It will be created by database.py."
        )

    # --------------------------------------------------------
    # TEAM PASSPORT META
    # --------------------------------------------------------

    if not _table_exists(cursor, "team_passport_meta"):
        logger.info(
            "team_passport_meta does not exist. "
            "It will be created by database.py."
        )

    # --------------------------------------------------------
    # GOLD DATASET
    # --------------------------------------------------------
    #
    # Не создаём gold_dataset заново.
    #
    # Если старая таблица существует, здесь можно безопасно
    # добавить только отсутствующие поля.
    #
    if _table_exists(cursor, "gold_dataset"):

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "match_date",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_btts",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_total_25",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_total_35",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_confidence",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_rating_home",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_rating_away",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_pir_home",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_pir_away",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_style_home",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "faj_style_away",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "expert_reasoning",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "status",
            "TEXT DEFAULT 'pending'"
        )

        _add_column_if_missing(
            cursor,
            "gold_dataset",
            "updated_at",
            "TEXT"
        )

    # --------------------------------------------------------
    # LEARNING RECORDS
    # --------------------------------------------------------
    #
    # Не создаём таблицу заново.
    #
    # Добавляем только поля, которые появились
    # в канонической схеме database.py.
    #

    if _table_exists(cursor, "learning_records"):

        _add_column_if_missing(
            cursor,
            "learning_records",
            "gold_id",
            "INTEGER"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "faj_score",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "faj_xg_home",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "faj_xg_away",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "actual_xg_home",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "actual_xg_away",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_score",
            "INTEGER"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_xg",
            "REAL"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_btts",
            "INTEGER"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_total_25",
            "INTEGER"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_total_35",
            "INTEGER"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "cause_type",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "error_detail",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "corrected_weights",
            "TEXT"
        )

        _add_column_if_missing(
            cursor,
            "learning_records",
            "status",
            "TEXT DEFAULT 'new'"
        )

    logger.info(
        "Migration %s completed successfully",
        MIGRATION_VERSION
    )

    return True


# ============================================================
# RUN MIGRATIONS
# ============================================================

def run_migrations() -> bool:
    """
    Главная точка запуска миграций.

    Вызывается из database.py после инициализации
    канонической схемы.

    Повторный запуск безопасен:
        если миграция уже применена,
        она повторно не выполняется.
    """

    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ----------------------------------------------------
        # schema_migrations
        # ----------------------------------------------------
        #
        # database.py должен создавать эту таблицу.
        #
        if not _table_exists(cursor, "schema_migrations"):
            logger.warning(
                "schema_migrations does not exist. "
                "Skipping migration registration."
            )

        # ----------------------------------------------------
        # Проверяем текущую миграцию
        # ----------------------------------------------------

        if _migration_exists(cursor, MIGRATION_VERSION):
            logger.info(
                "Migration %s already applied",
                MIGRATION_VERSION
            )
            conn.commit()
            return True

        # ----------------------------------------------------
        # Выполняем миграцию
        # ----------------------------------------------------

        migrate_v12_1_0(cursor)

        # ----------------------------------------------------
        # Регистрируем успешную миграцию
        # ----------------------------------------------------

        if _table_exists(cursor, "schema_migrations"):
            _register_migration(
                cursor,
                MIGRATION_VERSION,
                (
                    "FAJ v12.1 safe database migration: "
                    "legacy schema compatibility"
                ),
                success=1
            )

        conn.commit()

        logger.info(
            "✅ All database migrations completed"
        )

        return True

    except Exception as e:

        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        logger.exception(
            "❌ Database migration failed: %s",
            e
        )

        return False

    finally:

        if conn is not None:
            conn.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    success = run_migrations()

    if success:
        print("✅ FAJ migrations completed")
    else:
        print("❌ FAJ migrations failed")
