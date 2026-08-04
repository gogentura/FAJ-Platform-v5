#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Database Migrations
"""

from app.database import get_connection


def migrate_v12():
    """Миграция для FAJ v12.0 — создаёт новые таблицы если их нет"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # ===============================
        # GOLD DATASET
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

        # ===============================
        # LEARNING RECORDS
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

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Миграция пропущена: {e}")
        return False
