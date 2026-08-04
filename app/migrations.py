#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Database Migrations

Добавляет новые таблицы без изменения существующих:
- gold_dataset (эталонная база прогнозов и фактов)
- learning_records (память обучения)

Совместима с текущим database.py (использует get_connection)
"""

from app.database import get_connection


def migrate_v12():
    """Миграция для FAJ v12.0"""
    print("🔄 Запуск миграции FAJ v12...")
    
    conn = get_connection()
    cursor = conn.cursor()

    # ===============================
    # GOLD DATASET (расширенная версия)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_dataset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            prediction_id INTEGER,
            season TEXT,
            round INTEGER,
            home_team TEXT,
            away_team TEXT,
            model_version TEXT,
            xg_home_pred REAL,
            xg_away_pred REAL,
            faj_score TEXT,
            expert_score TEXT,
            confidence REAL,
            actual_score TEXT,
            actual_xg_home REAL,
            actual_xg_away REAL,
            result TEXT,
            correct_result INTEGER DEFAULT 0,
            correct_score INTEGER DEFAULT 0,
            goal_error REAL DEFAULT 0,
            created_at TEXT
        )
    """)
    print("✅ Таблица gold_dataset создана")

    # ===============================
    # LEARNING RECORDS (расширенная версия)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            round INTEGER,
            model_version TEXT,
            category TEXT,
            error_type TEXT,
            error_severity INTEGER DEFAULT 0,
            faj_prediction TEXT,
            actual_score TEXT,
            description TEXT,
            recommendation TEXT,
            created_at TEXT
        )
    """)
    print("✅ Таблица learning_records создана")

    conn.commit()
    conn.close()
    
    print("✅ Миграция FAJ v12 завершена успешно!")


if __name__ == "__main__":
    migrate_v12()
