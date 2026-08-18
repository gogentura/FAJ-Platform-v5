#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Bootstrap
============================================================

Назначение:

    Автоматическая проверка и первичная инициализация FAJ.

Принцип:

    GitHub Storage
        ↓
    Local SQLite
        ↓
    Bootstrap
        ↓
    FAJDatabase
        ↓
    SyncEngine
        ↓
    PassportManager

ВАЖНО:

    Bootstrap НЕ обучает модель.
    Bootstrap НЕ удаляет данные.
    Bootstrap НЕ перезаписывает динамику.

    GitHub используется как постоянное хранилище
    файла data/faj.db.

    Если локальной БД нет:
        GitHub → data/faj.db

    Если GitHub ещё не содержит БД:
        database.py создаёт новую БД.

    После успешного Bootstrap:
        data/faj.db → GitHub
"""

import os
import logging

from app.database import FAJDatabase, DB_FILE
from app.sync_engine import SyncEngine
from app.github_db_sync import (
    load_database_from_github,
    save_database_to_github,
)


logger = logging.getLogger(__name__)


DEFAULT_LEAGUE = "РПЛ"
DEFAULT_SEASON = "2026-2027"


# ============================================================
# BOOTSTRAP
# ============================================================

def bootstrap_faj() -> dict:
    """
    Автоматическая проверка и подготовка FAJ.

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

        logger.info("🚀 Запуск FAJ Bootstrap v12.1...")

        # ====================================================
        # 0. GITHUB → LOCAL SQLITE
        # ====================================================

        logger.info("☁️ Проверяем постоянное хранилище GitHub...")

        storage_result = load_database_from_github()

        if storage_result.get("loaded"):
            message = "☁️ База восстановлена из GitHub"
            logger.info(message)
            result["messages"].append(message)

        elif storage_result.get("reason") == "github_database_not_found":
            message = "☁️ Базы в GitHub ещё нет — будет создана новая SQLite БД"
            logger.info(message)
            result["messages"].append(message)

        else:
            message = "💾 Локальная база уже существует"
            logger.info(message)
            result["messages"].append(message)

        # ====================================================
        # DATABASE
        # ====================================================

        db = FAJDatabase()

        # SyncEngine создаётся после БД
        sync = SyncEngine()

        # ====================================================
        # 1. DATABASE FILE
        # ====================================================

        result["db_exists"] = os.path.exists(DB_FILE)

        message = (
            "📁 База данных: есть"
            if result["db_exists"]
            else "📁 База данных: нет"
        )

        logger.info(message)
        result["messages"].append(message)

        # ====================================================
        # 2. TEAMS
        # ====================================================

        teams = db.get_teams(
            league=DEFAULT_LEAGUE
        )

        result["teams"] = len(teams) if teams else 0

        message = f"🏟️ Команды: {result['teams']}"

        logger.info(message)
        result["messages"].append(message)

        # ====================================================
        # 3. TEAM SYNCHRONIZATION
        # ====================================================

        if result["teams"] == 0:

            logger.info(
                "🔄 Команд нет — запускаем синхронизацию..."
            )

            result["messages"].append(
                "🔄 Команд нет — запускаем синхронизацию..."
            )

            sync.sync_teams(
                DEFAULT_LEAGUE
            )

            # После sync_teams() НЕ доверяем
            # счётчику из возвращённого словаря.
            #
            # Источник истины — сама БД.

            teams = db.get_teams(
                league=DEFAULT_LEAGUE
            )

            result["teams"] = (
                len(teams)
                if teams
                else 0
            )

            logger.info(
                f"✅ Команд после синхронизации: "
                f"{result['teams']}"
            )

            result["messages"].append(
                f"✅ Команд после синхронизации: "
                f"{result['teams']}"
            )

        # ====================================================
        # 4. PASSPORTS
        # ====================================================

        # ВАЖНО:
        #
        # Не используем sync_result["updated"].
        #
        # PassportManager v2.0 различает:
        #
        # created
        # updated
        # unchanged
        #
        # Источник истины — количество записей
        # в team_passports.

        try:

            passport_count = db.get_table_count(
                "team_passports"
            )

        except Exception:

            passport_count = 0

        result["passports"] = (
            passport_count
            if passport_count
            else 0
        )

        # ----------------------------------------------------
        # Если паспортов нет — синхронизируем
        # ----------------------------------------------------

        if (
            result["teams"] > 0
            and result["passports"] == 0
        ):

            logger.info(
                "🔄 Паспортов нет — загружаем..."
            )

            result["messages"].append(
                "🔄 Паспортов нет — загружаем..."
            )

            sync.load_passports(
                DEFAULT_LEAGUE
            )

            # Снова читаем фактическое состояние БД

            result["passports"] = (
                db.get_table_count(
                    "team_passports"
                )
                or 0
            )

            logger.info(
                f"✅ Паспортов после загрузки: "
                f"{result['passports']}"
            )

            result["messages"].append(
                f"✅ Паспортов после загрузки: "
                f"{result['passports']}"
            )

        else:

            logger.info(
                f"📋 Паспорта: "
                f"{result['passports']}"
            )

            result["messages"].append(
                f"📋 Паспорта: "
                f"{result['passports']}"
            )

        # ====================================================
        # 5. SEASON
        # ====================================================

        seasons = db.get_seasons()

        # Ищем именно сезон РПЛ 2026-2027

        season_exists = any(
            season["league"] == DEFAULT_LEAGUE
            and season["year"] == DEFAULT_SEASON
            for season in seasons
        ) if seasons else False

        if not season_exists:

            logger.info(
                "🔄 Сезона РПЛ 2026-2027 нет — создаём..."
            )

            result["messages"].append(
                "🔄 Сезона РПЛ 2026-2027 нет — создаём..."
            )

            sync._get_or_create_season(
                DEFAULT_LEAGUE,
                DEFAULT_SEASON
            )

            result["season"] = True

            logger.info(
                "✅ Сезон 2026-2027 создан"
            )

            result["messages"].append(
                "✅ Сезон 2026-2027 создан"
            )

        else:

            result["season"] = True

            logger.info(
                "🏆 Сезон: 2026-2027"
            )

            result["messages"].append(
                "🏆 Сезон: 2026-2027"
            )

        # ====================================================
        # 6. MATCHES
        # ====================================================

        matches = db.get_matches()

        result["matches"] = (
            len(matches)
            if matches
            else 0
        )

        logger.info(
            f"📋 Матчи: {result['matches']}"
        )

        result["messages"].append(
            f"📋 Матчи: {result['matches']}"
        )

        # ====================================================
        # 7. FINAL DATABASE CHECK
        # ====================================================

        # Ещё раз читаем БД как источник истины.

        result["teams"] = len(
            db.get_teams(
                league=DEFAULT_LEAGUE
            )
        )

        result["passports"] = (
            db.get_table_count(
                "team_passports"
            )
            or 0
        )

        # ====================================================
        # 8. READY
        # ====================================================

        result["ready"] = (
            result["db_exists"]
            and result["teams"] >= 16
            and result["passports"] >= 16
            and result["season"]
        )

        logger.info(
            f"📊 Bootstrap final state: "
            f"teams={result['teams']}, "
            f"passports={result['passports']}, "
            f"season={result['season']}, "
            f"matches={result['matches']}"
        )

        logger.info(
            f"✅ FAJ готов: {result['ready']}"
        )

        result["messages"].append(
            f"✅ FAJ готов: {result['ready']}"
        )

        # ====================================================
        # 9. LOCAL SQLITE → GITHUB
        # ====================================================

        if result["ready"]:

            try:

                logger.info(
                    "☁️ Сохраняем базу в GitHub..."
                )

                storage_result = save_database_to_github()

                message = (
                    "☁️ База успешно сохранена "
                    "в GitHub"
                )

                logger.info(message)
                result["messages"].append(message)

            except Exception as storage_error:

                logger.exception(
                    "❌ Не удалось сохранить "
                    "базу в GitHub"
                )

                result["messages"].append(
                    f"⚠️ База создана локально, "
                    f"но не сохранена в GitHub: "
                    f"{storage_error}"
                )

        return result

    except Exception as e:

        logger.exception(
            "❌ Ошибка Bootstrap"
        )

        result["ready"] = False

        result["messages"].append(
            f"❌ Ошибка: {e}"
        )

        return result
