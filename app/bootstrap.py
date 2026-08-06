#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Bootstrap — Автоматическая инициализация системы
Личная аналитическая система — без лишней сложности
"""

import os
import logging
from app.database import FAJDatabase, DB_FILE
from app.sync_engine import SyncEngine

logger = logging.getLogger(__name__)


def bootstrap_faj() -> dict:
    """
    Автоматическая проверка и подготовка системы
    Возвращает статус: ready, teams, passports, season
    """
    result = {
        "ready": False,
        "teams": 0,
        "passports": 0,
        "season": False,
        "db_exists": False,
        "messages": []
    }
    
    try:
        db = FAJDatabase()
        sync = SyncEngine()
        
        # 1. Проверка БД
        result["db_exists"] = os.path.exists(DB_FILE)
        logger.info(f"📁 База данных: {'есть' if result['db_exists'] else 'нет'}")
        result["messages"].append(f"📁 База данных: {'есть' if result['db_exists'] else 'нет'}")
        
        # 2. Проверка команд
        teams = db.get_teams(league="РПЛ")
        result["teams"] = len(teams) if teams else 0
        logger.info(f"🏟️ Команды: {result['teams']}")
        result["messages"].append(f"🏟️ Команды: {result['teams']}")
        
        # 3. Если команд нет — создаём
        if result["teams"] == 0:
            logger.info("🔄 Команд нет — запускаем синхронизацию...")
            result["messages"].append("🔄 Команд нет — запускаем синхронизацию...")
            sync_result = sync.sync_teams("РПЛ")
            result["teams"] = sync_result.get("total", 0)
            result["passports"] = sync_result.get("passports", 0)
            logger.info(f"✅ Создано команд: {result['teams']}")
            logger.info(f"✅ Загружено паспортов: {result['passports']}")
            result["messages"].append(f"✅ Создано команд: {result['teams']}")
            result["messages"].append(f"✅ Загружено паспортов: {result['passports']}")
        
        # 4. Проверка паспортов
        if result["teams"] > 0:
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM team_passports")
            passport_count = cursor.fetchone()[0]
            conn.close()
            
            if passport_count == 0:
                logger.info("🔄 Паспортов нет — загружаем...")
                result["messages"].append("🔄 Паспортов нет — загружаем...")
                load_result = sync.load_passports("РПЛ")
                result["passports"] = load_result.get("updated", 0)
                logger.info(f"✅ Загружено паспортов: {result['passports']}")
                result["messages"].append(f"✅ Загружено паспортов: {result['passports']}")
            else:
                result["passports"] = passport_count
                logger.info(f"📋 Паспорта: {result['passports']}")
                result["messages"].append(f"📋 Паспорта: {result['passports']}")
        
        # 5. Проверка сезона
        seasons = db.get_seasons()
        if not seasons:
            logger.info("🔄 Сезона нет — создаём...")
            result["messages"].append("🔄 Сезона нет — создаём...")
            sync._get_or_create_season("РПЛ", "2026/27")
            result["season"] = True
            logger.info("✅ Сезон создан")
            result["messages"].append("✅ Сезон создан")
        else:
            result["season"] = True
            logger.info(f"🏆 Сезон: {len(seasons)} найден")
            result["messages"].append(f"🏆 Сезон: {len(seasons)} найден")
        
        # 6. Проверка матчей
        matches = db.get_matches()
        matches_count = len(matches) if matches else 0
        logger.info(f"📋 Матчи: {matches_count}")
        result["messages"].append(f"📋 Матчи: {matches_count}")
        
        # 7. Итоговый статус
        result["ready"] = (
            result["teams"] > 0 and
            result["passports"] > 0 and
            result["season"]
        )
        
        logger.info(f"✅ FAJ готов: {result['ready']}")
        result["messages"].append(f"✅ FAJ готов: {result['ready']}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке: {e}")
        result["messages"].append(f"❌ Ошибка: {e}")
        result["ready"] = False
        return result
