#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v11.2.1 → v11.3.0
Миграция базы данных — RELEASE CANDIDATE

ДОБАВЛЯЕТСЯ (12 таблиц):
    1. prediction_features    - входные данные матча
    2. pipeline_logs          - аудит расчётов
    3. model_results          - результаты отдельных моделей
    4. model_agreement        - согласованность моделей
    5. confidence_history     - история уверенности
    6. prediction_risk        - риски прогноза
    7. faj_decisions          - решение FAJ
    8. decision_explanations  - почему принято решение
    9. passport_versions      - история паспортов
    10. faj_rating_history    - история рейтингов
    11. monte_carlo_runs      - симуляции
    12. data_quality          - качество данных

ИЗМЕНЕНИЯ:
    - faj_decisions: убраны FOREIGN KEY (кроме match_id)
=====================================================
"""

import sqlite3
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "faj.db")


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def upgrade_to_v11_3_0():
    """Обновление базы данных до v11.3.0"""
    conn = get_connection()
    cursor = conn.cursor()

    logger.info("🚀 Начинаем миграцию v11.2.1 → v11.3.0")

    # ============================================================
    # 1. prediction_features - входные данные матча
    # ============================================================
    logger.info("  📋 Создание prediction_features...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            home_attack REAL,
            home_defense REAL,
            home_form REAL,
            home_rating REAL,
            home_xg REAL,
            home_injury_factor REAL,
            away_attack REAL,
            away_defense REAL,
            away_form REAL,
            away_rating REAL,
            away_xg REAL,
            away_injury_factor REAL,
            tournament_modifier REAL,
            coach_factor REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_features_match ON prediction_features(match_id)")

    # ============================================================
    # 2. pipeline_logs - аудит расчётов
    # ============================================================
    logger.info("  📋 Создание pipeline_logs...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            stage TEXT NOT NULL,
            module TEXT,
            execution_time REAL,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_match ON pipeline_logs(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline_logs(stage)")

    # ============================================================
    # 3. model_results - результаты отдельных моделей
    # ============================================================
    logger.info("  📋 Создание model_results...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            model_name TEXT NOT NULL,
            result_type TEXT DEFAULT 'winner',
            prediction TEXT,
            probability REAL,
            home_goals REAL,
            away_goals REAL,
            home_probability REAL,
            draw_probability REAL,
            away_probability REAL,
            xg_home REAL,
            xg_away REAL,
            model_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_match ON model_results(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_name ON model_results(model_name)")

    # ============================================================
    # 4. model_agreement - согласованность моделей
    # ============================================================
    logger.info("  📋 Создание model_agreement...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_agreement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            xg_result_id INTEGER,
            poisson_result_id INTEGER,
            montecarlo_result_id INTEGER,
            expert_result_id INTEGER,
            agreement_percent REAL,
            conflict_level TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agreement_match ON model_agreement(match_id)")

    # ============================================================
    # 5. confidence_history - история уверенности
    # ============================================================
    logger.info("  📋 Создание confidence_history...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS confidence_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            data_quality REAL,
            passport_quality REAL,
            model_agreement REAL,
            prediction_stability REAL,
            final_confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_confidence_match ON confidence_history(match_id)")

    # ============================================================
    # 6. prediction_risk - риски прогноза
    # ============================================================
    logger.info("  📋 Создание prediction_risk...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_risk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            risk_type TEXT NOT NULL,
            risk_value REAL,
            description TEXT,
            severity INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_match ON prediction_risk(match_id)")

    # ============================================================
    # 7. faj_decisions - решение FAJ (БЕЗ FOREIGN KEY)
    # ============================================================
    logger.info("  📋 Создание faj_decisions...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faj_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            final_score TEXT,
            final_probability REAL,
            confidence REAL,
            risk_level TEXT,
            model_agreement REAL,
            expert_used INTEGER DEFAULT 0,
            expert_weight REAL DEFAULT 0,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_match ON faj_decisions(match_id)")

    # ============================================================
    # 8. decision_explanations - почему принято решение
    # ============================================================
    logger.info("  📋 Создание decision_explanations...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_explanations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER,
            factor TEXT NOT NULL,
            impact REAL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(decision_id) REFERENCES faj_decisions(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_explanations_decision ON decision_explanations(decision_id)")

    # ============================================================
    # 9. passport_versions - история паспортов
    # ============================================================
    logger.info("  📋 Создание passport_versions...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS passport_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            version INTEGER,
            version_type TEXT DEFAULT 'basic',
            attack INTEGER,
            defense INTEGER,
            control INTEGER,
            form INTEGER,
            rating REAL,
            change_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_passport_versions_team ON passport_versions(team_id, season_id)")

    # ============================================================
    # 10. faj_rating_history - история рейтингов
    # ============================================================
    logger.info("  📋 Создание faj_rating_history...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faj_rating_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            rating REAL,
            attack_rating REAL,
            defense_rating REAL,
            form_rating REAL,
            mental_rating REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_team ON faj_rating_history(team_id, season_id)")

    # ============================================================
    # 11. monte_carlo_runs - симуляции
    # ============================================================
    logger.info("  📋 Создание monte_carlo_runs...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monte_carlo_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            simulation_count INTEGER,
            home_win REAL,
            draw REAL,
            away_win REAL,
            mean_home_goals REAL,
            mean_away_goals REAL,
            variance REAL,
            most_likely_score TEXT,
            random_seed INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mc_match ON monte_carlo_runs(match_id)")

    # ============================================================
    # 12. data_quality - качество данных
    # ============================================================
    logger.info("  📋 Создание data_quality...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_quality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            passport_complete REAL,
            missing_fields INTEGER,
            freshness REAL,
            confidence REAL,
            source_count INTEGER DEFAULT 0,
            last_update TEXT,
            status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_match ON data_quality(match_id)")

    # ============================================================
    # Обновляем версию схемы
    # ============================================================
    logger.info("  📋 Обновление версии схемы...")
    cursor.execute("""
        INSERT INTO schema_version (version) VALUES ('11.3.0')
    """)

    conn.commit()
    conn.close()

    logger.info("✅ Миграция v11.2.1 → v11.3.0 завершена!")
    logger.info("   📊 Добавлено 12 новых таблиц")
    logger.info("   📌 Новая версия схемы: 11.3.0")
    logger.info("   🎯 RELEASE CANDIDATE READY")


def rollback_to_v11_2_1():
    """Откат до v11.2.1 (удаление новых таблиц)"""
    conn = get_connection()
    cursor = conn.cursor()

    logger.info("⚠️ Откат к v11.2.1...")

    tables = [
        "prediction_features",
        "pipeline_logs",
        "model_results",
        "model_agreement",
        "confidence_history",
        "prediction_risk",
        "faj_decisions",
        "decision_explanations",
        "passport_versions",
        "faj_rating_history",
        "monte_carlo_runs",
        "data_quality"
    ]

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()
    conn.close()

    logger.info("✅ Откат выполнен. База вернулась к v11.2.1")


def get_schema_version():
    if not os.path.exists(DB_FILE):
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None


def check_migration_status():
    conn = get_connection()
    cursor = conn.cursor()

    tables = [
        "prediction_features",
        "pipeline_logs",
        "model_results",
        "model_agreement",
        "confidence_history",
        "prediction_risk",
        "faj_decisions",
        "decision_explanations",
        "passport_versions",
        "faj_rating_history",
        "monte_carlo_runs",
        "data_quality"
    ]

    status = {}
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            status[table] = cursor.fetchone()[0]
        except:
            status[table] = None

    conn.close()
    return status


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ FAJ Database Migration v11.2.1 → v11.3.0")
    print("   RELEASE CANDIDATE")
    print("=" * 60)

    current = get_schema_version()
    print(f"\n📌 Текущая версия: {current}")

    if current == "11.3.0":
        print("\n⚠️ База уже обновлена до v11.3.0")
        status = check_migration_status()
        print("\n📊 Статус таблиц:")
        for table, count in status.items():
            icon = "✅" if count is not None else "❌"
            print(f"  {icon} {table}: {count if count is not None else 'НЕ СУЩЕСТВУЕТ'}")
    else:
        print("\n🚀 Запуск миграции...")
        upgrade_to_v11_3_0()

    print("\n📋 Новые таблицы (12):")
    tables = [
        "1. prediction_features    - входные данные матча",
        "2. pipeline_logs          - аудит расчётов",
        "3. model_results          - результаты моделей (с result_type)",
        "4. model_agreement        - согласованность моделей",
        "5. confidence_history     - история уверенности",
        "6. prediction_risk        - риски прогноза",
        "7. faj_decisions          - решение FAJ (home_score, away_score)",
        "8. decision_explanations  - почему принято решение",
        "9. passport_versions      - история паспортов",
        "10. faj_rating_history    - история рейтингов",
        "11. monte_carlo_runs      - симуляции",
        "12. data_quality          - качество данных"
    ]
    for t in tables:
        print(f"  {t}")

    print("\n" + "=" * 60)
    print("✅ FAJ Database Schema v11.3.0 Release Candidate")
    print("   Готова к фиксации.")
    print("=" * 60)
