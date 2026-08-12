#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ Bootstrap
============================================================

РОЛЬ:
    Автоматическая инициализация FAJ.

ОТВЕТСТВЕННОСТЬ:
    - проверить наличие БД;
    - проверить команды;
    - при отсутствии команд запустить SyncEngine;
    - проверить паспорта;
    - при отсутствии паспортов загрузить их;
    - проверить сезон;
    - проверить матчи;
    - вернуть итоговый статус.

АРХИТЕКТУРА:

    Bootstrap
        ↓
    SyncEngine
        ↓
    FAJDatabase
        ↓
    SQLite

ВАЖНО:
    Bootstrap НЕ работает с SQLite напрямую.

    Никаких:
        sqlite3.connect()
        _get_connection()
        SQL-запросов

    Все операции с БД выполняются через FAJDatabase.

    Bootstrap не удаляет данные.
    Bootstrap не обучает модель.
    Bootstrap не изменяет существующие динамические данные.
"""

import os
import logging

from app.database import FAJDatabase, DB_FILE
from app.sync_engine import SyncEngine


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_LEAGUE = "РПЛ"
DEFAULT_SEASON = "2026-2027"


# ============================================================
# BOOTSTRAP
# ============================================================

def bootstrap_faj() -> dict:
    """
    Автоматическая проверка и подготовка системы.

    Возвращает:

        ready
        teams
        passports
        season
        db_exists
        matches
        messages
    """

    result = {
        "ready": False,
        "teams": 0,
        "passports": 0,
        "season": False,
        "matches": 0,
        "db_exists": False,
        "messages": [],
    }

    try:

        # ====================================================
        # DATABASE
        # ====================================================

        logger.info(
            "🚀 Запуск FAJ Bootstrap v12.1..."
        )

        db = FAJDatabase()
        sync = SyncEngine()

        # ----------------------------------------------------
        # Проверка файла БД
        # ----------------------------------------------------

        result["db_exists"] = os.path.exists(
            DB_FILE
        )

        db_message = (
            "📁 База данных: есть"
            if result["db_exists"]
            else "📁 База данных: нет"
        )

        logger.info(db_message)
        result["messages"].append(db_message)

        # ====================================================
        # TEAMS
        # ====================================================

        teams = db.get_teams(
            league=DEFAULT_LEAGUE
        )

        result["teams"] = (
            len(teams)
            if teams
            else 0
        )

        message = (
            f"🏟️ Команды: "
            f"{result['teams']}"
        )

        logger.info(message)
        result["messages"].append(message)

        # ----------------------------------------------------
        # Если команд нет — создаём
        # ----------------------------------------------------

        if result["teams"] == 0:

            logger.info(
                "🔄 Команд нет — "
                "запускаем синхронизацию..."
            )

            result["messages"].append(
                "🔄 Команд нет — "
                "запускаем синхронизацию..."
            )

            sync_result = sync.sync_teams(
                DEFAULT_LEAGUE
            )

            result["teams"] = sync_result.get(
                "total",
                0
            )

            result["passports"] = sync_result.get(
                "passports",
                0
            )

            message = (
                f"✅ Команд после синхронизации: "
                f"{result['teams']}"
            )

            logger.info(message)
            result["messages"].append(message)

            message = (
                f"✅ Паспортов после синхронизации: "
                f"{result['passports']}"
            )

            logger.info(message)
            result["messages"].append(message)

        # ====================================================
        # PASSPORTS
        # ====================================================

        if result["teams"] > 0:

            # ------------------------------------------------
            # ВАЖНО:
            #
            # Не используем db._get_connection().
            #
            # PassportManager владеет team_passports,
            # а SyncEngine владеет синхронизацией.
            #
            # Получаем текущие паспорта через PassportManager.
            # ------------------------------------------------

            passport_count = 0

            try:

                season_id = sync._get_or_create_season(
                    DEFAULT_LEAGUE,
                    DEFAULT_SEASON
                )

                for team in teams:

                    passport = (
                        sync.passport_manager
                        .get_current_passport(
                            team["id"],
                            season_id
                        )
                    )

                    if passport:
                        passport_count += 1

            except Exception as e:

                logger.warning(
                    "Не удалось проверить "
                    "паспорта через PassportManager: %s",
                    e
                )

                passport_count = 0

            # ------------------------------------------------
            # Если паспортов нет — загружаем
            # ------------------------------------------------

            if passport_count == 0:

                logger.info(
                    "🔄 Паспортов нет — "
                    "загружаем..."
                )

                result["messages"].append(
                    "🔄 Паспортов нет — "
                    "загружаем..."
                )

                load_result = sync.load_passports(
                    DEFAULT_LEAGUE
                )

                result["passports"] = load_result.get(
                    "updated",
                    0
                )

                message = (
                    f"✅ Загружено паспортов: "
                    f"{result['passports']}"
                )

                logger.info(message)
                result["messages"].append(message)

            else:

                result["passports"] = passport_count

                message = (
                    f"📋 Паспорта: "
                    f"{result['passports']}"
                )

                logger.info(message)
                result["messages"].append(message)

        # ====================================================
        # SEASON
        # ====================================================

        season_id = sync._get_or_create_season(
            DEFAULT_LEAGUE,
            DEFAULT_SEASON
        )

        if season_id:

            result["season"] = True

            message = (
                f"🏆 Сезон: "
                f"{DEFAULT_SEASON}"
            )

            logger.info(message)
            result["messages"].append(message)

        # ====================================================
        # MATCHES
        # ====================================================

        matches = db.get_matches()

        matches_count = (
            len(matches)
            if matches
            else 0
        )

        result["matches"] = matches_count

        message = (
            f"📋 Матчи: "
            f"{matches_count}"
        )

        logger.info(message)
        result["messages"].append(message)

        # ====================================================
        # FINAL STATUS
        # ====================================================

        result["ready"] = (
            result["db_exists"]
            and result["teams"] > 0
            and result["passports"] > 0
            and result["season"]
        )

        message = (
            f"✅ FAJ готов: "
            f"{result['ready']}"
        )

        logger.info(message)
        result["messages"].append(message)

        return result

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        logger.exception(
            "❌ Ошибка Bootstrap"
        )

        result["messages"].append(
            f"❌ Ошибка: {e}"
        )

        result["ready"] = False

        return result
