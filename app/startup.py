#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Startup — автоматическая проверка и миграция БД
"""

from app.migrations import migrate_v12


def run_startup_checks():
    """Запускается при старте приложения"""
    print("🔄 FAJ Startup: проверка базы данных...")
    
    # Запускаем миграцию (создаёт таблицы если их нет)
    result = migrate_v12()
    
    if result:
        print("✅ База данных в порядке")
    else:
        print("⚠️ Проблемы с миграцией, но приложение продолжает работу")
    
    return result
