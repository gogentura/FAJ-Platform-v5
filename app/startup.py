#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Startup — Безопасная инициализация
Проверяет наличие таблиц Learning Layer при запуске
"""

import os
import sqlite3

from app.database import DB_FILE
from app.migrations.learning import apply_learning_layer


REQUIRED_TABLES = [
    'gold_dataset',
    'learning_records',
    'learning_events',
    'audit_log',
    'migrations'
]


def check_tables_exist(cursor, tables):
    """Проверяет наличие всех таблиц"""
    for table in tables:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if not cursor.fetchone():
            return False, table
    return True, None


def run_startup_checks():
    """Запуск проверок при старте"""
    print("🚀 FAJ — проверка системы...")

    if not os.path.exists(DB_FILE):
        print("⚠️ База данных не найдена. Сначала запустите основную систему.")
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    all_exist, missing = check_tables_exist(cursor, REQUIRED_TABLES)

    if not all_exist:
        print(f"📦 Отсутствует таблица: {missing}. Применяем Learning Layer...")
        conn.close()
        return apply_learning_layer()

    # Проверяем запись в migrations
    cursor.execute("""
        SELECT id, applied_at FROM migrations
        WHERE name = 'learning_layer' AND status = 'completed'
    """)
    migration = cursor.fetchone()

    if migration:
        print(f"✅ Learning Layer уже применён ({migration[1]})")
    else:
        print("⚠️ Таблицы есть, но миграция не зарегистрирована. Исправляем...")
        cursor.execute("""
            INSERT OR IGNORE INTO migrations (name, version, applied_at, status, details)
            VALUES ('learning_layer', '1.0', datetime('now'), 'completed', 'Восстановлена')
        """)
        conn.commit()

    cursor.execute("SELECT COUNT(*) FROM gold_dataset")
    gold_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM learning_records")
    learning_count = cursor.fetchone()[0]

    conn.close()

    print(f"   📊 gold_dataset: {gold_count} записей")
    print(f"   📊 learning_records: {learning_count} записей")
    return True


if __name__ == "__main__":
    run_startup_checks()
