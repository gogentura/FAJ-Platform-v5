#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Reset Calendar & Facts — ОЧИСТКА КАЛЕНДАРЯ И ФАКТОВ

Оставляет нетронутым:
    - teams
    - seasons
    - team_passports
    - team_base, team_dynamic, team_identity, tactical_matchup
    - model_parameters, learning_memory, xg_memory
    - schema_migrations, diagnostic_history
    - все вспомогательные таблицы (players, team_events, ...)

Очищает:
    - rounds, matches, match_results, match_statistics
    - predictions, expert_predictions, journal, prediction_validation
    - match_predictions, match_snapshots
    - team_form_history, team_dynamics, standings
    - gold_dataset, learning_records, learning_events, audit_log

Порядок очистки соблюдает внешние ключи.
Перед удалением создаётся резервная копия faj.db.
"""

import sqlite3
import os
import shutil
from datetime import datetime

from app.database import DB_FILE, get_connection

def reset_calendar():
    print("=" * 70)
    print("FAJ RESET CALENDAR & FACTS v12.1")
    print("=" * 70)

    if not os.path.exists(DB_FILE):
        print(f"❌ Файл БД не найден: {DB_FILE}")
        return

    # 1. Создаём резервную копию
    backup_path = DB_FILE + ".backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"📦 Создание резервной копии: {backup_path}")
    shutil.copy2(DB_FILE, backup_path)
    print("✅ Резервная копия создана")

    # 2. Подключаемся
    conn = get_connection()
    cursor = conn.cursor()

    # 3. Отключаем проверку внешних ключей (чтобы удалять в любом порядке)
    cursor.execute("PRAGMA foreign_keys = OFF")
    print("🔓 Внешние ключи временно отключены")

    # 4. Список таблиц для очистки (в порядке, обратном зависимостям)
    tables_to_clear = [
        "prediction_validation",
        "journal",
        "expert_predictions",
        "predictions",
        "match_predictions",
        "match_snapshots",
        "match_statistics",
        "match_results",
        "team_form_history",
        "team_dynamics",
        "standings",
        "gold_dataset",
        "learning_records",
        "learning_events",
        "audit_log",
        "matches",
        "rounds",
    ]

    # 5. Очищаем каждую таблицу
    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"   🗑️  Очищена таблица: {table}")
        except sqlite3.OperationalError as e:
            print(f"   ⚠️  Не удалось очистить {table}: {e}")

    # 6. Включаем внешние ключи обратно
    cursor.execute("PRAGMA foreign_keys = ON")
    print("🔒 Внешние ключи включены")

    # 7. Фиксируем изменения
    conn.commit()
    conn.close()

    print("✅ Очистка завершена.")
    print(f"📁 Резервная копия сохранена: {backup_path}")
    print("=" * 70)

if __name__ == "__main__":
    reset_calendar()
