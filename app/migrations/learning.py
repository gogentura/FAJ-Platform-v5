#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ — Learning Layer Migration
Создаёт таблицы обучения поверх существующей БД

НЕ ТРОГАЕТ существующие таблицы!
Только добавляет новые:
- migrations
- gold_dataset
- learning_records
- learning_events
- audit_log
- model_parameters_learning
"""

import sqlite3
import os
from datetime import datetime

from app.database import DB_FILE


def apply_learning_layer():
    """Применяет Learning Layer"""
    print("🧠 FAJ — Применение Learning Layer...")

    if not os.path.exists(DB_FILE):
        print("❌ База данных не найдена!")
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # ============================================================
    # 1. MIGRATIONS — журнал миграций
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'completed',
            details TEXT,
            UNIQUE(name, version)
        )
    """)
    print("   ✅ migrations создана")

    # ============================================================
    # 2. GOLD_DATASET — эталонная база
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_dataset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,

            -- Прогноз FAJ
            model_version TEXT,
            faj_score TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            faj_btts INTEGER,
            faj_total_25 INTEGER,
            faj_total_35 INTEGER,
            faj_confidence REAL,
            faj_rating_home REAL,
            faj_rating_away REAL,
            faj_pir_home REAL,
            faj_pir_away REAL,
            faj_style_home TEXT,
            faj_style_away TEXT,

            -- Эксперт
            expert_score TEXT,
            expert_reasoning TEXT,

            -- Факт (после матча)
            actual_score TEXT,
            actual_xg_home REAL,
            actual_xg_away REAL,
            actual_btts INTEGER,
            actual_total_25 INTEGER,
            actual_total_35 INTEGER,
            actual_home_goals INTEGER,
            actual_away_goals INTEGER,

            -- Статус
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    print("   ✅ gold_dataset создана")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_match ON gold_dataset(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_status ON gold_dataset(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_version ON gold_dataset(model_version)")

    # ============================================================
    # 3. LEARNING_RECORDS — память ошибок
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gold_id INTEGER,
            match_id INTEGER,
            home_team TEXT,
            away_team TEXT,

            -- Прогноз и факт
            faj_score TEXT,
            actual_score TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            actual_xg_home REAL,
            actual_xg_away REAL,

            -- Ошибки
            error_score INTEGER,
            error_xg REAL,
            error_btts INTEGER,
            error_total_25 INTEGER,
            error_total_35 INTEGER,

            -- Классификация
            error_type TEXT,
            cause_type TEXT,
            error_severity INTEGER,
            error_detail TEXT,

            -- Рекомендации
            recommendation TEXT,
            corrected_weights TEXT,

            -- Статус
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (gold_id) REFERENCES gold_dataset(id),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    print("   ✅ learning_records создана")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_gold ON learning_records(gold_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_type ON learning_records(error_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_cause ON learning_records(cause_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_status ON learning_records(status)")

    # ============================================================
    # 4. LEARNING_EVENTS — события обучения
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            season_id INTEGER,
            round_number INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_team TEXT,
            away_team TEXT,

            -- Данные
            faj_score TEXT,
            actual_score TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            actual_xg_home REAL,
            actual_xg_away REAL,

            -- Ошибка
            error_magnitude REAL,
            error_type TEXT,
            cause_type TEXT,
            error_severity INTEGER,

            -- Обучение
            learning_action TEXT,
            delta TEXT,
            confidence REAL,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (season_id) REFERENCES seasons(id),
            FOREIGN KEY (home_team_id) REFERENCES teams(id),
            FOREIGN KEY (away_team_id) REFERENCES teams(id)
        )
    """)
    print("   ✅ learning_events создана")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_match ON learning_events(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_team ON learning_events(home_team_id, away_team_id)")

    # ============================================================
    # 5. AUDIT_LOG — журнал аудита
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            gold_id INTEGER,
            audit_date TEXT DEFAULT CURRENT_TIMESTAMP,
            total_errors INTEGER,
            critical_errors INTEGER,
            summary TEXT,
            recommendations TEXT,
            status TEXT DEFAULT 'pending',

            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (gold_id) REFERENCES gold_dataset(id)
        )
    """)
    print("   ✅ audit_log создана")

    # ============================================================
    # 6. MODEL_PARAMETERS_LEARNING — параметры для обучения
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_parameters_learning (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT NOT NULL,
            parameter_group TEXT,
            parameter_name TEXT NOT NULL,
            parameter_value REAL,
            min_value REAL,
            max_value REAL,
            description TEXT,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_version, parameter_name)
        )
    """)
    print("   ✅ model_parameters_learning создана")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_params_version ON model_parameters_learning(model_version)")

    # ============================================================
    # 7. ЗАПИСЬ В MIGRATIONS
    # ============================================================
    cursor.execute("""
        INSERT OR IGNORE INTO migrations (name, version, applied_at, status, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        'learning_layer',
        '1.0',
        datetime.now().isoformat(),
        'completed',
        'Добавлены таблицы: gold_dataset, learning_records, learning_events, audit_log, model_parameters_learning'
    ))

    conn.commit()
    conn.close()

    print("✅ FAJ Learning Layer применён успешно!")
    print("📊 Добавлены таблицы:")
    print("   • gold_dataset — эталонная база")
    print("   • learning_records — память ошибок с причинами")
    print("   • learning_events — события обучения")
    print("   • audit_log — журнал аудита")
    print("   • migrations — журнал миграций")
    print("   • model_parameters_learning — параметры модели")
    return True


def check_migration_applied():
    """Проверяет, применена ли миграция Learning Layer"""
    if not os.path.exists(DB_FILE):
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='migrations'")
    if not cursor.fetchone():
        conn.close()
        return False

    cursor.execute("""
        SELECT id FROM migrations
        WHERE name = 'learning_layer' AND status = 'completed'
    """)
    result = cursor.fetchone()
    conn.close()

    return result is not None


def ensure_learning_layer():
    """Гарантирует применение Learning Layer"""
    if check_migration_applied():
        print("✅ Learning Layer уже применён")
        return True
    else:
        print("📦 Применяем Learning Layer...")
        return apply_learning_layer()


if __name__ == "__main__":
    ensure_learning_layer()
