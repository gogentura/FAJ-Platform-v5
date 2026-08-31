#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED 🔒
Database Engine — ЕДИНЫЙ ФАЙЛ БАЗЫ ДАННЫХ

Схема: v12.1-memory-hardened
Контракт: FAJ MEMORY CONTRACT v1.0
"""

import sqlite3
import os
import uuid
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# ПУТЬ К БАЗЕ ДАННЫХ — АБСОЛЮТНЫЙ
# ============================================================

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "faj.db")
DB_SCHEMA_VERSION = "12.1-memory-hardened"

os.makedirs(DATA_DIR, exist_ok=True)

logger.info(f"📁 Database path: {DB_FILE}")


def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def ensure_table(table_name: str, create_sql: str) -> None:
    """Создаёт таблицу, если её нет"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if not cursor.fetchone():
            cursor.execute(create_sql)
            logger.info(f"✅ Создана таблица: {table_name}")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Не удалось создать таблицу {table_name}: {e}")


def ensure_column(table_name: str, column_name: str, column_type: str) -> None:
    """Добавляет колонку в таблицу, если её нет"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            logger.info(f"✅ Добавлена колонка {column_name} в таблицу {table_name}")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Не удалось добавить колонку {column_name}: {e}")


def ensure_index(table_name: str, index_name: str, columns: str) -> None:
    """Создаёт индекс, если его нет"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
        if not cursor.fetchone():
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
            logger.info(f"✅ Создан индекс: {index_name}")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Не удалось создать индекс {index_name}: {e}")


def ensure_index_if_table_exists(table_name: str, index_name: str, columns: str) -> None:
    """Создаёт индекс только если таблица существует."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
        """, (table_name,))
        if not cursor.fetchone():
            conn.close()
            logger.warning(
                f"⚠️ Таблица {table_name} отсутствует. "
                f"Индекс {index_name} пропущен."
            )
            return
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name = ?
        """, (index_name,))
        if not cursor.fetchone():
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {table_name} ({columns})"
            )
            logger.info(
                f"✅ Создан индекс: {index_name}"
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(
            f"Не удалось создать индекс {index_name}: {e}"
        )


def get_schema_version():
    """Возвращает последнюю успешно применённую версию схемы."""
    if not os.path.exists(DB_FILE):
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'schema_migrations'
        """)
        if not cursor.fetchone():
            conn.close()
            return None
        cursor.execute("""
            SELECT version
            FROM schema_migrations
            WHERE success = 1
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return row["version"] if row else None
    except Exception as e:
        logger.warning(f"Не удалось определить версию схемы: {e}")
        return None


def run_migrations():
    """Безопасное выполнение миграций FAJ Database v12.1 Memory Hardened."""
    logger.info("🚀 Запуск миграций FAJ Memory Hardened...")
    
    ensure_table("schema_migrations", """
        CREATE TABLE schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            description TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1
        )
    """)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'matches'
    """)
    matches_exists = cursor.fetchone() is not None
    conn.close()
    
    if matches_exists:
        ensure_column("matches", "home_xg", "REAL")
        ensure_column("matches", "away_xg", "REAL")
        ensure_column("matches", "home_possession", "INTEGER")
        ensure_column("matches", "away_possession", "INTEGER")
        ensure_column("matches", "home_shots", "INTEGER")
        ensure_column("matches", "away_shots", "INTEGER")
        ensure_column("matches", "home_shots_on_target", "INTEGER")
        ensure_column("matches", "away_shots_on_target", "INTEGER")
        ensure_column("matches", "parser_source", "TEXT")
        ensure_column("matches", "parser_version", "TEXT")
        ensure_column("matches", "updated_at", "TEXT")
        ensure_column("matches", "data_quality", "REAL DEFAULT 1.0")
        ensure_column("matches", "match_uuid", "TEXT")
        ensure_column("matches", "fact_status", "TEXT DEFAULT 'scheduled'")
        ensure_index("matches", "idx_matches_status", "status")
        ensure_index("matches", "idx_matches_date", "date")
        ensure_index("matches", "idx_matches_home_away", "home_team_id, away_team_id")
        ensure_index("matches", "idx_matches_uuid", "match_uuid")
        ensure_index("matches", "idx_matches_natural_key", "round_id, home_team_id, away_team_id, date")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'team_dynamic'
    """)
    dynamic_exists = cursor.fetchone() is not None
    conn.close()
    if dynamic_exists:
        ensure_column("team_dynamic", "last_sync", "TEXT")
    
    # ============================================================
    # ДОБАВЛЕНИЕ НОВЫХ ТАБЛИЦ ДЛЯ MEMORY HARDENING
    # ============================================================
    
    # P1.3: Parameter history table
    ensure_table("parameter_history", """
        CREATE TABLE IF NOT EXISTS parameter_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parameter_name TEXT NOT NULL,
            group_name TEXT,
            model_version TEXT,
            old_value REAL,
            new_value REAL,
            delta REAL,
            reason TEXT,
            confidence REAL,
            reference_event_id INTEGER,
            reference_match_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ensure_index("parameter_history", "idx_param_history_name", "parameter_name")
    ensure_index("parameter_history", "idx_param_history_version", "model_version")
    ensure_index("parameter_history", "idx_param_history_match", "reference_match_id")
    
    # P1.4: Team History API
    ensure_column("team_history", "source", "TEXT")
    ensure_column("team_history", "reference_match_id", "INTEGER")
    ensure_column("team_history", "reference_event_id", "INTEGER")
    ensure_index_if_table_exists("team_history", "idx_team_history_match", "reference_match_id")
    ensure_index_if_table_exists("team_history", "idx_team_history_event", "reference_event_id")
    
    # P0.8: Locked facts protection - add fact_status to match_results
    ensure_column("match_results", "fact_status", "TEXT DEFAULT 'pending'")
    ensure_column("match_results", "locked_at", "TEXT")
    ensure_column("match_results", "locked_by", "TEXT")
    
    # P0.5: Add prediction_id to validation
    ensure_column("prediction_validation", "prediction_id", "INTEGER")
    ensure_column("prediction_validation", "match_prediction_id", "INTEGER")
    ensure_column("prediction_validation", "validation_hash", "TEXT")
    
    # P1.2: Add passport identity to snapshots
    ensure_column("match_snapshots", "passport_id", "INTEGER")
    ensure_column("match_snapshots", "passport_version", "TEXT")
    ensure_column("match_snapshots", "dynamic_id", "INTEGER")
    ensure_column("match_snapshots", "memory_state_id", "TEXT")
    
    # P1.1: Add memory_state_id to predictions
    ensure_column("predictions", "memory_state_id", "TEXT")
    ensure_column("predictions", "snapshot_id", "INTEGER")
    ensure_column("predictions", "passport_revision", "TEXT")
    ensure_column("predictions", "parameter_revision", "TEXT")
    
    # ============================================================
    # ДОБАВЛЕНИЕ prediction_revision И memory_state_id В match_predictions
    # ============================================================
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'match_predictions'
    """)
    if cursor.fetchone():
        ensure_column("match_predictions", "prediction_revision", "INTEGER DEFAULT 1")
        ensure_column("match_predictions", "memory_state_id", "TEXT")
        logger.info("✅ Добавлены колонки prediction_revision и memory_state_id в match_predictions")
    conn.close()
    
    # P1.9: Make prediction_hash UNIQUE
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'index' AND name = 'idx_predictions_hash'
    """)
    if not cursor.fetchone():
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_hash ON predictions(prediction_hash)")
            logger.info("✅ Создан UNIQUE индекс idx_predictions_hash")
        except Exception as e:
            logger.warning(f"Не удалось создать UNIQUE индекс для prediction_hash: {e} (возможно, есть дубли)")
    conn.close()
    
    # P0.6: Passport versioning - add UNIQUE constraint for versioned passports
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'index' AND name = 'idx_passports_unique_version'
    """)
    if not cursor.fetchone():
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_passports_unique_version 
                ON team_passports(team_id, season_id, version, created_at)
            """)
            logger.info("✅ Создан UNIQUE индекс idx_passports_unique_version")
        except Exception as e:
            logger.warning(f"Не удалось создать UNIQUE индекс для паспортов: {e}")
    conn.close()
    
    # P1.8: Gold immutable after completed - add lock mechanism
    ensure_column("gold_dataset", "locked", "INTEGER DEFAULT 0")
    ensure_column("gold_dataset", "locked_at", "TEXT")
    
    # ============================================================
    # СУЩЕСТВУЮЩИЕ МИГРАЦИИ (сохраняем)
    # ============================================================
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'team_passports'
    """)
    passport_exists = cursor.fetchone() is not None
    conn.close()
    
    if passport_exists:
        ensure_column("team_passports", "mental", "REAL DEFAULT 50")
        ensure_column("team_passports", "home_strength", "REAL DEFAULT 50")
        ensure_column("team_passports", "away_strength", "REAL DEFAULT 50")
        ensure_column("team_passports", "injury_factor", "REAL DEFAULT 50")
        ensure_column("team_passports", "key_player_loss", "REAL DEFAULT 50")
        ensure_column("team_passports", "league_adaptation", "REAL DEFAULT 80")
        ensure_column("team_passports", "form", "REAL DEFAULT 50")
        ensure_column("team_passports", "passport_confidence", "REAL DEFAULT 0.5")
        ensure_column("team_passports", "faj_rating", "REAL DEFAULT 0.0")
        ensure_column("team_passports", "source", "TEXT DEFAULT 'manual'")
        ensure_column("team_passports", "updated_at", "TEXT")
        ensure_column("team_passports", "results_strength", "REAL")
        ensure_column("team_passports", "opponent_strength", "REAL")
        ensure_column("team_passports", "matches_count", "INTEGER DEFAULT 0")
        ensure_column("team_passports", "passport_uuid", "TEXT")
        logger.info("✅ Проверены колонки team_passports (включая v2.1 + Memory Hardened)")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'team_passport_meta'
    """)
    meta_exists = cursor.fetchone() is not None
    conn.close()
    
    if meta_exists:
        ensure_column("team_passport_meta", "style", "TEXT")
        ensure_column("team_passport_meta", "dna", "TEXT")
        ensure_column("team_passport_meta", "strengths", "TEXT")
        ensure_column("team_passport_meta", "weaknesses", "TEXT")
        ensure_column("team_passport_meta", "class", "TEXT")
        ensure_column("team_passport_meta", "version", "TEXT DEFAULT '1.0'")
        ensure_column("team_passport_meta", "source", "TEXT DEFAULT 'FAJ Expert Layer'")
        logger.info("✅ Проверены колонки team_passport_meta")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'predictions'
    """)
    predictions_exists = cursor.fetchone() is not None
    conn.close()
    
    if predictions_exists:
        ensure_column("predictions", "prediction_status", "TEXT DEFAULT 'active'")
        ensure_column("predictions", "prediction_version", "INTEGER DEFAULT 1")
        logger.info("✅ Проверена колонка prediction_status и prediction_version в predictions")
    
    # ============================================================
    # 🆕 FAJ FINAL SCORE — НОВЫЕ ПОЛЯ
    # ============================================================
    
    # Добавляем колонки в predictions
    ensure_column("predictions", "faj_final_score", "TEXT")
    ensure_column("predictions", "faj_confidence", "INTEGER")
    ensure_column("predictions", "decision_factors", "TEXT")
    
    # Добавляем колонку в prediction_scores
    ensure_column("prediction_scores", "score_type", "TEXT DEFAULT 'math'")
    
    logger.info("✅ Добавлены колонки FAJ Final Score в predictions и prediction_scores")
    
    ensure_index_if_table_exists("prediction_validation", "idx_validation_match", "match_id")
    ensure_index_if_table_exists("prediction_validation", "idx_validation_predicted", "predicted_score")
    
    ensure_index_if_table_exists("team_form_history", "idx_form_team_season", "team_id, season_id")
    ensure_index_if_table_exists("team_form_history", "idx_form_team_date", "team_id, created_at")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO schema_migrations
        (version, description, success)
        VALUES (?, ?, ?)
    """, (DB_SCHEMA_VERSION, "FAJ Platform v12.1 Memory Hardened", 1))
    conn.commit()
    conn.close()
    
    logger.info(f"✅ Миграции завершены. Schema: {DB_SCHEMA_VERSION}")


def init_database():
    """Инициализация базы данных с финальной схемой v12.1 Memory Hardened"""
    conn = get_connection()
    cursor = conn.cursor()
    
    logger.info("🚀 Инициализация базы данных FAJ v12.1 Memory Hardened...")
    
    # ============================================================
    # CORE TABLES (сохраняем существующую структуру)
    # ============================================================
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT NOT NULL,
            country TEXT,
            api_id INTEGER,
            team_type TEXT DEFAULT 'club',
            competition_group TEXT,
            created_at TEXT,
            UNIQUE(name, league)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_lookup ON teams(name, league)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT NOT NULL,
            year TEXT,
            competition_type TEXT DEFAULT 'league',
            status TEXT DEFAULT 'active',
            created_at TEXT,
            UNIQUE(league, year, competition_type)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER,
            round_number INTEGER,
            date_start TEXT,
            date_end TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT,
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(season_id, round_number)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            match_uuid TEXT UNIQUE,
            date TEXT,
            competition TEXT,
            status TEXT DEFAULT 'scheduled',
            actual_home INTEGER,
            actual_away INTEGER,
            home_xg REAL,
            away_xg REAL,
            home_possession INTEGER,
            away_possession INTEGER,
            home_shots INTEGER,
            away_shots INTEGER,
            home_shots_on_target INTEGER,
            away_shots_on_target INTEGER,
            parser_source TEXT,
            parser_version TEXT,
            data_quality REAL DEFAULT 1.0,
            fact_status TEXT DEFAULT 'scheduled',
            updated_at TEXT,
            created_at TEXT,
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_round ON matches(round_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_uuid ON matches(match_uuid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_natural_key ON matches(round_id, home_team_id, away_team_id, date)")
    
    # ============================================================
    # MATCH PREDICTIONS (xG / lambda слой) — append-only
    # prediction_revision и memory_state_id добавляются через миграции
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            xg_home REAL,
            xg_away REAL,
            lambda_home REAL,
            lambda_away REAL,
            home_advantage REAL,
            prediction_type TEXT DEFAULT 'standard',
            model_version TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_predictions_match ON match_predictions(match_id)")
    # Индекс на prediction_revision создаётся ПОСЛЕ миграций
    
    # ============================================================
    # TEAM INTELLIGENCE (сохраняем существующую структуру)
    # ============================================================
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            attack INTEGER DEFAULT 50,
            defense INTEGER DEFAULT 50,
            control INTEGER DEFAULT 50,
            press INTEGER DEFAULT 50,
            tempo INTEGER DEFAULT 50,
            transition INTEGER DEFAULT 50,
            set_pieces INTEGER DEFAULT 50,
            counter_attack INTEGER DEFAULT 50,
            build_up INTEGER DEFAULT 50,
            finishing INTEGER DEFAULT 50,
            goalkeeper INTEGER DEFAULT 50,
            discipline INTEGER DEFAULT 50,
            coach_factor INTEGER DEFAULT 50,
            squad_quality INTEGER DEFAULT 50,
            bench_quality INTEGER DEFAULT 50,
            home_advantage REAL DEFAULT 1.0,
            passport_version INTEGER DEFAULT 1,
            updated_after_round INTEGER,
            updated_after_match INTEGER,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_base_lookup ON team_base(team_id, season_id)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_dynamic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            form INTEGER DEFAULT 50,
            fitness INTEGER DEFAULT 50,
            morale INTEGER DEFAULT 50,
            fatigue INTEGER DEFAULT 50,
            injury_index INTEGER DEFAULT 0,
            coach_confidence INTEGER DEFAULT 50,
            last5_points REAL DEFAULT 0,
            last5_strength_points REAL DEFAULT 0,
            last5_results TEXT DEFAULT '[0,0,0,0,0]',
            last5_strength_results TEXT DEFAULT '[0,0,0,0,0]',
            last5_xg REAL DEFAULT 0,
            last5_xga REAL DEFAULT 0,
            last5_goals INTEGER DEFAULT 0,
            last5_conceded INTEGER DEFAULT 0,
            last5_performance TEXT DEFAULT '[0,0,0,0,0]',
            average_performance REAL DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            days_rest INTEGER DEFAULT 7,
            travel_distance INTEGER DEFAULT 0,
            rotation_index INTEGER DEFAULT 0,
            last_base_correction_match INTEGER DEFAULT 0,
            passport_confidence REAL DEFAULT 0.4,
            last_sync TEXT,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_dynamic_lookup ON team_dynamic(team_id, season_id)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_identity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            style TEXT DEFAULT 'mixed',
            tempo TEXT DEFAULT 'medium',
            pressing TEXT DEFAULT 'medium',
            transition TEXT DEFAULT 'medium',
            risk_level TEXT DEFAULT 'medium',
            created_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tactical_matchup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            vs_high_press REAL DEFAULT 0,
            vs_low_block REAL DEFAULT 0,
            vs_counter_attack REAL DEFAULT 0,
            vs_possession REAL DEFAULT 0,
            vs_direct REAL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    
    # ============================================================
    # TEAM PASSPORTS — ОСНОВНОЙ ПАСПОРТ FAJ v12.x
    # passport_uuid добавляется через миграции (не в CREATE TABLE)
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_passports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            attack REAL DEFAULT 50.0,
            defense REAL DEFAULT 50.0,
            control REAL DEFAULT 50.0,
            tempo REAL DEFAULT 50.0,
            press REAL DEFAULT 50.0,
            transition REAL DEFAULT 50.0,
            finishing REAL DEFAULT 50.0,
            goalkeeper REAL DEFAULT 50.0,
            discipline REAL DEFAULT 50.0,
            squad_quality REAL DEFAULT 50.0,
            bench_quality REAL DEFAULT 50.0,
            coach_factor REAL DEFAULT 50.0,
            mental REAL DEFAULT 50.0,
            home_strength REAL DEFAULT 50.0,
            away_strength REAL DEFAULT 50.0,
            injury_factor REAL DEFAULT 50.0,
            key_player_loss REAL DEFAULT 50.0,
            league_adaptation REAL DEFAULT 80.0,
            form REAL DEFAULT 50.0,
            passport_confidence REAL DEFAULT 0.5,
            faj_rating REAL DEFAULT 0.0,
            version TEXT NOT NULL,
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            results_strength REAL,
            opponent_strength REAL,
            matches_count INTEGER DEFAULT 0,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_passports_team_season ON team_passports(team_id, season_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_passports_version ON team_passports(version)")
    # Индекс idx_passports_uuid создаётся ПОСЛЕ миграций
    
    # ============================================================
    # TEAM PASSPORT META
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_passport_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            style TEXT,
            dna TEXT,
            strengths TEXT,
            weaknesses TEXT,
            class TEXT,
            version TEXT DEFAULT '1.0',
            source TEXT DEFAULT 'FAJ Expert Layer',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_passport_meta_team ON team_passport_meta(team_id, season_id)")
    
    # ============================================================
    # PREDICTIONS — с версионированием и memory_state_id
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            model_version TEXT,
            algorithm TEXT,
            home_win REAL,
            draw REAL,
            away_win REAL,
            over25 REAL,
            over35 REAL,
            btts REAL,
            confidence INTEGER,
            prediction_source TEXT DEFAULT 'FAJ Engine',
            prediction_hash TEXT UNIQUE,
            prediction_status TEXT DEFAULT 'active',
            prediction_version INTEGER DEFAULT 1,
            memory_state_id TEXT,
            snapshot_id INTEGER,
            passport_revision TEXT,
            parameter_revision TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(prediction_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_hash ON predictions(prediction_hash)")
    # Индекс idx_predictions_memory создаётся ПОСЛЕ миграций
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            score TEXT,
            probability REAL,
            rank INTEGER,
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prediction_scores_prediction ON prediction_scores(prediction_id)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_distributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            home_goals INTEGER,
            away_goals INTEGER,
            probability REAL,
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prediction_distributions_prediction ON prediction_distributions(prediction_id)")
    
    # ============================================================
    # PREDICTION VALIDATION — с prediction_id
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            prediction_id INTEGER,
            match_prediction_id INTEGER,
            validation_hash TEXT,
            predicted_score TEXT,
            actual_score TEXT,
            predicted_home_xg REAL,
            actual_home_xg REAL,
            predicted_away_xg REAL,
            actual_away_xg REAL,
            predicted_winner TEXT,
            actual_winner TEXT,
            predicted_probability_home REAL,
            predicted_probability_draw REAL,
            predicted_probability_away REAL,
            score_probability REAL,
            confidence REAL,
            risk REAL,
            predicted_btts INTEGER,
            actual_btts INTEGER,
            predicted_over25 INTEGER,
            actual_over25 INTEGER,
            model_version TEXT,
            passport_version TEXT,
            parser_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_match ON prediction_validation(match_id)")
    # Индексы idx_validation_prediction и idx_validation_hash создаются ПОСЛЕ миграций
    
    # ============================================================
    # EXPERT & JOURNAL
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expert_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            expert_name TEXT,
            score TEXT,
            comment TEXT,
            confidence INTEGER,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_match ON expert_predictions(match_id)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            faj_prediction TEXT,
            expert_prediction TEXT,
            actual_result TEXT,
            error_type TEXT,
            error_score REAL,
            analysis TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_match ON journal(match_id)")
    
    # ============================================================
    # TEAM FORM HISTORY
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_form_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            round INTEGER,
            match_id INTEGER,
            opponent_team_id INTEGER,
            rating_before REAL,
            rating_after REAL,
            form REAL,
            matches_count INTEGER,
            win_rate REAL,
            draw_rate REAL,
            loss_rate REAL,
            last5_points INTEGER,
            last5_xg REAL,
            last5_xga REAL,
            goal_difference INTEGER,
            form_source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(opponent_team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_form_team ON team_form_history(team_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_form_team_season ON team_form_history(team_id, season_id)")
    
    # ============================================================
    # MATCH RESULTS & STATISTICS — с fact_status для защиты
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER UNIQUE,
            home_goals INTEGER,
            away_goals INTEGER,
            home_penalty_goals INTEGER DEFAULT 0,
            away_penalty_goals INTEGER DEFAULT 0,
            fact_status TEXT DEFAULT 'pending',
            locked_at TEXT,
            locked_by TEXT,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_results_match ON match_results(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_results_status ON match_results(fact_status)")
    
    # ============================================================
    # MATCH STATISTICS — РАСШИРЕНА
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            team_id INTEGER,
            possession REAL,
            shots INTEGER,
            shots_on_target INTEGER,
            corners INTEGER,
            fouls INTEGER,
            yellow_cards INTEGER,
            red_cards INTEGER,
            xg REAL,
            big_chances INTEGER,
            saves INTEGER,
            passes INTEGER,
            accurate_passes INTEGER,
            pass_accuracy REAL,
            tackles INTEGER,
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (team_id) REFERENCES teams(id),
            UNIQUE(match_id, team_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_match ON match_statistics(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_stats_team ON match_statistics(team_id)")
    
    # ============================================================
    # TEAM DYNAMICS (ПО ТУРАМ)
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_dynamics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            round_number INTEGER,
            season_id INTEGER,
            matches_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            goals_for INTEGER DEFAULT 0,
            goals_against INTEGER DEFAULT 0,
            goal_difference INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            avg_possession REAL DEFAULT 0,
            avg_shots REAL DEFAULT 0,
            avg_shots_on_target REAL DEFAULT 0,
            avg_corners REAL DEFAULT 0,
            avg_xg REAL DEFAULT 0,
            avg_fouls REAL DEFAULT 0,
            form TEXT,
            form_points REAL DEFAULT 0,
            home_form_points REAL DEFAULT 0,
            away_form_points REAL DEFAULT 0,
            attack_rating REAL DEFAULT 1.0,
            defense_rating REAL DEFAULT 1.0,
            control_rating REAL DEFAULT 1.0,
            FOREIGN KEY (team_id) REFERENCES teams(id),
            FOREIGN KEY (season_id) REFERENCES seasons(id),
            UNIQUE(team_id, round_number, season_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_dynamics_lookup ON team_dynamics(team_id, season_id)")
    
    # ============================================================
    # STANDINGS
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            round INTEGER,
            place INTEGER,
            games INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            goal_diff INTEGER,
            points INTEGER,
            form TEXT,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id, round)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_standings_team ON standings(team_id, season_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_standings_round ON standings(round)")
    
    # ============================================================
    # DIAGNOSTIC
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            elapsed_seconds REAL DEFAULT 0,
            passed INTEGER DEFAULT 0,
            warned INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            critical_fail INTEGER DEFAULT 0,
            status TEXT DEFAULT 'unknown',
            details_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_timestamp ON diagnostic_history(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnostic_status ON diagnostic_history(status)")
    
    # ============================================================
    # LEARNING LAYER
    # ============================================================
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_dataset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            match_date TEXT,
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
            expert_score TEXT,
            expert_reasoning TEXT,
            actual_score TEXT,
            actual_xg_home REAL,
            actual_xg_away REAL,
            actual_btts INTEGER,
            actual_total_25 INTEGER,
            actual_total_35 INTEGER,
            actual_home_goals INTEGER,
            actual_away_goals INTEGER,
            status TEXT DEFAULT 'pending',
            locked INTEGER DEFAULT 0,
            locked_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_match ON gold_dataset(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_status ON gold_dataset(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_version ON gold_dataset(model_version)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_teams ON gold_dataset(home_team, away_team)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_date ON gold_dataset(match_date)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gold_id INTEGER,
            match_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            faj_score TEXT,
            actual_score TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            actual_xg_home REAL,
            actual_xg_away REAL,
            error_score INTEGER,
            error_xg REAL,
            error_btts INTEGER,
            error_total_25 INTEGER,
            error_total_35 INTEGER,
            error_type TEXT,
            cause_type TEXT,
            error_severity INTEGER,
            error_detail TEXT,
            recommendation TEXT,
            corrected_weights TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gold_id) REFERENCES gold_dataset(id),
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_gold ON learning_records(gold_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_type ON learning_records(error_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_cause ON learning_records(cause_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_status ON learning_records(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_match ON learning_records(match_id)")
    
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
            faj_score TEXT,
            actual_score TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            actual_xg_home REAL,
            actual_xg_away REAL,
            error_magnitude REAL,
            error_type TEXT,
            cause_type TEXT,
            error_severity INTEGER,
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_match ON learning_events(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_team ON learning_events(home_team_id, away_team_id)")
    
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_match ON audit_log(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_gold ON audit_log(gold_id)")
    
    # ============================================================
    # MODEL PARAMETERS — с версионированием
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            model_version TEXT,
            category TEXT,
            parameter_name TEXT NOT NULL,
            parameter_value REAL,
            description TEXT,
            revision INTEGER DEFAULT 1,
            is_current INTEGER DEFAULT 1,
            updated_at TEXT,
            UNIQUE(model_version, parameter_name, revision)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_params_lookup ON model_parameters(group_name, model_version, parameter_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_model_params_current ON model_parameters(model_version, parameter_name, is_current)")
    
    # ============================================================
    # PARAMETER HISTORY — для отслеживания изменений
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parameter_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parameter_name TEXT NOT NULL,
            group_name TEXT,
            model_version TEXT,
            old_value REAL,
            new_value REAL,
            delta REAL,
            reason TEXT,
            confidence REAL,
            reference_event_id INTEGER,
            reference_match_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_history_name ON parameter_history(parameter_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_history_version ON parameter_history(model_version)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_param_history_match ON parameter_history(reference_match_id)")
    
    # ============================================================
    # LEARNING MEMORY
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            object TEXT,
            feature TEXT,
            before_value TEXT,
            after_value TEXT,
            delta TEXT,
            reason TEXT,
            confidence REAL,
            impact REAL DEFAULT 1.0,
            algorithm TEXT,
            model_version TEXT,
            reference_id INTEGER,
            created_at TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_memory_object ON learning_memory(object, feature)")
    
    # ============================================================
    # XG MEMORY
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xg_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            attack_xg_deviation REAL,
            defense_xg_deviation REAL,
            matches_count INTEGER,
            last_update TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id)
        )
    """)
    
    # ============================================================
    # MATCH SNAPSHOTS — с passport_id и memory_state_id
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            team_id INTEGER,
            attack INTEGER,
            defense INTEGER,
            control INTEGER,
            press INTEGER,
            tempo INTEGER,
            transition INTEGER,
            finishing INTEGER,
            coach_factor INTEGER,
            squad_quality INTEGER,
            form INTEGER,
            fitness INTEGER,
            fatigue INTEGER,
            morale INTEGER,
            xg_for REAL,
            xg_against REAL,
            opponent_strength REAL,
            confidence_factor REAL,
            passport_id INTEGER,
            passport_version TEXT,
            dynamic_id INTEGER,
            memory_state_id TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_snapshots_match ON match_snapshots(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_snapshots_memory ON match_snapshots(memory_state_id)")
    
    # ============================================================
    # PLAYER IMPACT
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_impact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            player_name TEXT,
            impact_attack INTEGER DEFAULT 0,
            impact_creation INTEGER DEFAULT 0,
            impact_defense INTEGER DEFAULT 0,
            injury_penalty INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_competition_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            competition TEXT,
            modifier REAL DEFAULT 1.0,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id, competition)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            event_type TEXT,
            description TEXT,
            severity INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_at TEXT,
            expires_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            source TEXT,
            reference_match_id INTEGER,
            reference_event_id INTEGER,
            created_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_history_team ON team_history(team_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_history_match ON team_history(reference_match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_history_event ON team_history(reference_event_id)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            event_type TEXT,
            team_id INTEGER,
            player_id INTEGER,
            minute INTEGER,
            description TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            name TEXT NOT NULL,
            position TEXT,
            rating INTEGER DEFAULT 50,
            fitness INTEGER DEFAULT 50,
            importance INTEGER DEFAULT 50,
            created_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            event_type TEXT,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            created_at TEXT,
            FOREIGN KEY(player_id) REFERENCES players(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            description TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1
        )
    """)
    
    # ============================================================
    # ЗАПУСК МИГРАЦИЙ
    # ============================================================
    
    conn.commit()
    conn.close()
    
    run_migrations()
    
    # ============================================================
    # ДОПОЛНИТЕЛЬНЫЕ МИГРАЦИИ ДЛЯ match_statistics
    # ============================================================
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем, существует ли таблица match_statistics
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'match_statistics'
    """)
    if cursor.fetchone():
        # Добавляем колонки если их нет
        ensure_column("match_statistics", "accurate_passes", "INTEGER")
        ensure_column("match_statistics", "tackles", "INTEGER")
        logger.info("✅ Проверены/добавлены колонки match_statistics: accurate_passes, tackles")
    else:
        logger.info("⏳ Таблица match_statistics будет создана при init_database()")
    
    conn.commit()
    conn.close()
    
    # ============================================================
    # ИНДЕКСЫ ПОСЛЕ МИГРАЦИЙ (гарантированно с существующей колонкой)
    # ============================================================
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Индекс на prediction_revision в match_predictions
    cursor.execute("PRAGMA table_info(match_predictions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "prediction_revision" in columns:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_predictions_revision ON match_predictions(match_id, prediction_revision)")
        logger.info("✅ Создан индекс idx_match_predictions_revision")
    
    # Индекс на passport_uuid в team_passports
    cursor.execute("PRAGMA table_info(team_passports)")
    columns = [row[1] for row in cursor.fetchall()]
    if "passport_uuid" in columns:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_passports_uuid ON team_passports(passport_uuid)")
        logger.info("✅ Создан индекс idx_passports_uuid")
    
    # Индекс на memory_state_id в predictions
    cursor.execute("PRAGMA table_info(predictions)")
    columns = [row[1] for row in cursor.fetchall()]
    if "memory_state_id" in columns:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_memory ON predictions(memory_state_id)")
        logger.info("✅ Создан индекс idx_predictions_memory")
    
    # Индекс на prediction_id в prediction_validation
    cursor.execute("PRAGMA table_info(prediction_validation)")
    columns = [row[1] for row in cursor.fetchall()]
    if "prediction_id" in columns:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_prediction ON prediction_validation(prediction_id)")
        logger.info("✅ Создан индекс idx_validation_prediction")
    
    # Индекс на validation_hash в prediction_validation
    cursor.execute("PRAGMA table_info(prediction_validation)")
    columns = [row[1] for row in cursor.fetchall()]
    if "validation_hash" in columns:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_hash ON prediction_validation(validation_hash)")
        logger.info("✅ Создан индекс idx_validation_hash")
    
    conn.commit()
    conn.close()
    
    logger.info(f"✅ База данных инициализирована. Версия: {DB_SCHEMA_VERSION}")


class FAJDatabase:
    def __init__(self):
        init_database()
    
    def get_connection(self):
        return get_connection()
    
    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # STATUS & DIAGNOSTIC
    # ============================================================
    
    def get_status(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row["name"] for row in cursor.fetchall()]
            return {
                "status": "online",
                "file": DB_FILE,
                "tables": tables,
                "schema_version": DB_SCHEMA_VERSION
            }
        except Exception as e:
            logger.error(f"Database status error: {e}")
            return {
                "status": "error",
                "file": DB_FILE,
                "tables": [],
                "schema_version": DB_SCHEMA_VERSION,
                "error": str(e)
            }
        finally:
            conn.close()
    
    def save_diagnostic(self, data: Dict[str, Any]) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnostic_history (
                    timestamp, elapsed_seconds, passed, warned,
                    failed, total, critical_fail, status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("timestamp"),
                data.get("elapsed_seconds"),
                data.get("passed", 0),
                data.get("warned", 0),
                data.get("failed", 0),
                data.get("total", 0),
                data.get("critical_fail", 0),
                data.get("status", "unknown"),
                data.get("details_json", "{}")
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception as e:
            logger.error(f"Save diagnostic error: {e}")
            return 0
        finally:
            conn.close()
    
    def get_diagnostics(self, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM diagnostic_history
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                entry = {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "elapsed_seconds": row["elapsed_seconds"],
                    "summary": {
                        "passed": row["passed"],
                        "warned": row["warned"],
                        "failed": row["failed"],
                        "total": row["total"],
                        "critical_fail": row["critical_fail"],
                        "status": row["status"]
                    }
                }
                if row["details_json"]:
                    try:
                        entry["details"] = json.loads(row["details_json"])
                    except:
                        pass
                result.append(entry)
            return result
        finally:
            conn.close()
    
    # ============================================================
    # TABLE HELPERS
    # ============================================================
    
    def table_exists(self, table_name: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = ?
                LIMIT 1
            """, (table_name,))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def get_table_columns(self, table_name: str):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_table_names(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            return [row["name"] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_table_count(self, table_name: str) -> int:
        if not self.table_exists(table_name):
            return 0
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) AS count FROM "{table_name}"')
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def find_duplicates(self, table_name: str, columns: List[str]):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            column_sql = ", ".join(f'"{col}"' for col in columns)
            cursor.execute(f"""
                SELECT {column_sql}, COUNT(*) AS duplicate_count
                FROM "{table_name}"
                GROUP BY {column_sql}
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC
            """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def prediction_exists(self, prediction_id) -> bool:
        if prediction_id is None:
            return False
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM predictions WHERE id = ? LIMIT 1
            """, (prediction_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    # ============================================================
    # TEAMS
    # ============================================================
    
    def add_team(self, name, league, country="", api_id=None, team_type="club", competition_group=None):
        if not name:
            raise ValueError("Team name is required")
        if not league:
            raise ValueError("League is required")
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO teams (
                    name, league, country, api_id,
                    team_type, competition_group, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, league) DO UPDATE SET
                    country = excluded.country,
                    api_id = excluded.api_id,
                    team_type = excluded.team_type,
                    competition_group = excluded.competition_group
            """, (
                name.strip(), league.strip(), country, api_id,
                team_type, competition_group, datetime.now().isoformat()
            ))
            cursor.execute("""
                SELECT id FROM teams
                WHERE name = ? AND league = ?
                LIMIT 1
            """, (name.strip(), league.strip()))
            row = cursor.fetchone()
            if not row:
                raise RuntimeError(f"Team was not created/found: {name} / {league}")
            conn.commit()
            return row["id"]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_team_id(self, name, league):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM teams
                WHERE name = ? AND league = ?
                LIMIT 1
            """, (name, league))
            row = cursor.fetchone()
            return row["id"] if row else None
        finally:
            conn.close()
    
    def get_teams(self, league=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if league is not None:
                cursor.execute("""
                    SELECT * FROM teams
                    WHERE league = ?
                    ORDER BY name ASC
                """, (league,))
            else:
                cursor.execute("""
                    SELECT * FROM teams
                    ORDER BY name ASC
                """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_team(self, team_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM teams WHERE id = ? LIMIT 1
            """, (team_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    # ============================================================
    # SEASONS
    # ============================================================
    
    def get_season_id(self, league, year, competition_type="league"):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM seasons
                WHERE league = ? AND year = ? AND competition_type = ?
                ORDER BY id DESC LIMIT 1
            """, (league, year, competition_type))
            row = cursor.fetchone()
            return row["id"] if row else None
        finally:
            conn.close()
    
    def create_season(self, name, league, year, competition_type="league", status="active"):
        if league is None or league == "":
            raise ValueError("league is required and cannot be None or empty")
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            existing_id = self.get_season_id(league, year, competition_type)
            if existing_id:
                return existing_id
            
            cursor.execute("""
                INSERT INTO seasons (
                    name, league, year, competition_type, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (name, league, year, competition_type, status, datetime.now().isoformat()))
            season_id = cursor.lastrowid
            conn.commit()
            return season_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_seasons(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM seasons ORDER BY id DESC
            """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # ROUNDS
    # ============================================================
    
    def create_round(self, season_id, number, date_start="", date_end=""):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO rounds (
                    season_id,
                    round_number,
                    date_start,
                    date_end,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    season_id,
                    number,
                    date_start,
                    date_end,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            cursor.execute(
                """
                SELECT id
                FROM rounds
                WHERE season_id = ?
                  AND round_number = ?
                LIMIT 1
                """,
                (
                    season_id,
                    number,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError(
                    f"Не удалось получить round_id "
                    f"для season_id={season_id}, "
                    f"round_number={number}"
                )
            return row["id"]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_rounds(self, season_id=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if season_id is not None:
                cursor.execute("""
                    SELECT * FROM rounds
                    WHERE season_id = ?
                    ORDER BY round_number ASC
                """, (season_id,))
            else:
                cursor.execute("""
                    SELECT * FROM rounds
                    ORDER BY id DESC
                """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # GET ROUND MATCHES BY NUMBER
    # ============================================================
    
    def get_round_matches_by_number(
        self,
        round_number: int,
        league: str,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает матчи указанного тура и лиги.
        
        ВАЖНО:
            round_number сам по себе не уникален между лигами.
            Поиск выполняется через matches + rounds с фильтрацией по competition.
        
        Args:
            round_number: номер тура
            league: название лиги (РПЛ, АПЛ, Ла Лига, Лига чемпионов)
        
        Returns:
            Список матчей с названиями команд
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    m.*,
                    ht.name AS home_team_name,
                    at.name AS away_team_name,
                    r.round_number,
                    r.season_id
                FROM matches m
                LEFT JOIN teams ht
                    ON ht.id = m.home_team_id
                LEFT JOIN teams at
                    ON at.id = m.away_team_id
                INNER JOIN rounds r
                    ON r.id = m.round_id
                WHERE r.round_number = ?
                  AND m.competition = ?
                ORDER BY
                    m.date ASC,
                    m.id ASC
                """,
                (
                    int(round_number),
                    league,
                ),
            )
            rows = cursor.fetchall()
            return [
                dict(row)
                for row in rows
            ]
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET MATCHES
    # ============================================================
    
    def get_matches(self, round_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Возвращает список матчей.
        
        Args:
            round_id: ID тура (если None — все матчи)
        
        Returns:
            Список словарей с полями matches
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if round_id is not None:
                cursor.execute("""
                    SELECT
                        m.*,
                        ht.name AS home_team_name,
                        at.name AS away_team_name,
                        r.round_number
                    FROM matches m
                    LEFT JOIN teams ht ON ht.id = m.home_team_id
                    LEFT JOIN teams at ON at.id = m.away_team_id
                    LEFT JOIN rounds r ON r.id = m.round_id
                    WHERE m.round_id = ?
                    ORDER BY datetime(m.date) ASC, m.id ASC
                """, (round_id,))
            else:
                cursor.execute("""
                    SELECT
                        m.*,
                        ht.name AS home_team_name,
                        at.name AS away_team_name,
                        r.round_number
                    FROM matches m
                    LEFT JOIN teams ht ON ht.id = m.home_team_id
                    LEFT JOIN teams at ON at.id = m.away_team_id
                    LEFT JOIN rounds r ON r.id = m.round_id
                    ORDER BY datetime(m.date) DESC, m.id DESC
                """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET SINGLE MATCH
    # ============================================================
    
    def get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает один матч по ID.
        
        Args:
            match_id: ID матча
        
        Returns:
            Словарь с полями matches или None
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    m.*,
                    ht.name AS home_team_name,
                    at.name AS away_team_name,
                    r.round_number
                FROM matches m
                LEFT JOIN teams ht ON ht.id = m.home_team_id
                LEFT JOIN teams at ON at.id = m.away_team_id
                LEFT JOIN rounds r ON r.id = m.round_id
                WHERE m.id = ?
                LIMIT 1
            """, (match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    # ============================================================
    # MATCHES — с защитой фактических данных
    # ============================================================
    
    def upsert_match(self, data: Dict[str, Any]) -> int:
        """ИДЕМПОТЕНТНОЕ создание/обновление календарного матча.
        НЕ изменяет actual_home/actual_away если они уже установлены."""
        if not data:
            raise ValueError("Match data is required")
        
        home_team_id = data.get("home_team_id")
        away_team_id = data.get("away_team_id")
        round_id = data.get("round_id")
        match_date = data.get("date")
        
        if home_team_id is None:
            raise ValueError("home_team_id is required")
        if away_team_id is None:
            raise ValueError("away_team_id is required")
        if not match_date:
            raise ValueError("date is required")
        
        match_date = str(match_date).strip()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            existing = None
            match_uuid = data.get("match_uuid")
            
            if match_uuid:
                cursor.execute("""
                    SELECT * FROM matches WHERE match_uuid = ? LIMIT 1
                """, (match_uuid,))
                existing = cursor.fetchone()
            
            if existing is None:
                cursor.execute("""
                    SELECT * FROM matches
                    WHERE round_id = ? AND home_team_id = ? AND away_team_id = ? AND date = ?
                    LIMIT 1
                """, (round_id, home_team_id, away_team_id, match_date))
                existing = cursor.fetchone()
            
            now = datetime.now().isoformat()
            
            if existing:
                match_id = existing["id"]
                if not match_uuid:
                    match_uuid = existing["match_uuid"]
                
                # P0.4: Защищаем фактический результат от перезаписи через календарь
                actual_home = data.get("actual_home")
                actual_away = data.get("actual_away")
                
                # Если в существующей записи уже есть результат, не перезаписываем
                if existing["actual_home"] is not None and existing["actual_away"] is not None:
                    actual_home = existing["actual_home"]
                    actual_away = existing["actual_away"]
                
                cursor.execute("""
                    UPDATE matches SET
                        round_id = ?, home_team_id = ?, away_team_id = ?,
                        date = ?, competition = ?, status = ?,
                        actual_home = ?, actual_away = ?,
                        home_xg = ?, away_xg = ?,
                        home_possession = ?, away_possession = ?,
                        home_shots = ?, away_shots = ?,
                        home_shots_on_target = ?, away_shots_on_target = ?,
                        parser_source = ?, parser_version = ?,
                        data_quality = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    round_id, home_team_id, away_team_id,
                    match_date,
                    data.get("competition", "RPL"),
                    data.get("status", "scheduled"),
                    actual_home,
                    actual_away,
                    data.get("home_xg"),
                    data.get("away_xg"),
                    data.get("home_possession"),
                    data.get("away_possession"),
                    data.get("home_shots"),
                    data.get("away_shots"),
                    data.get("home_shots_on_target"),
                    data.get("away_shots_on_target"),
                    data.get("parser_source"),
                    data.get("parser_version"),
                    data.get("data_quality", 1.0),
                    now,
                    match_id
                ))
            else:
                match_uuid = match_uuid or str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO matches (
                        round_id, home_team_id, away_team_id, match_uuid,
                        date, competition, status,
                        actual_home, actual_away,
                        home_xg, away_xg,
                        home_possession, away_possession,
                        home_shots, away_shots,
                        home_shots_on_target, away_shots_on_target,
                        parser_source, parser_version,
                        data_quality, fact_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    round_id, home_team_id, away_team_id, match_uuid,
                    match_date,
                    data.get("competition", "RPL"),
                    data.get("status", "scheduled"),
                    data.get("actual_home"),
                    data.get("actual_away"),
                    data.get("home_xg"),
                    data.get("away_xg"),
                    data.get("home_possession"),
                    data.get("away_possession"),
                    data.get("home_shots"),
                    data.get("away_shots"),
                    data.get("home_shots_on_target"),
                    data.get("away_shots_on_target"),
                    data.get("parser_source"),
                    data.get("parser_version"),
                    data.get("data_quality", 1.0),
                    data.get("fact_status", "scheduled"),
                    now, now
                ))
                match_id = cursor.lastrowid
            
            conn.commit()
            return match_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # UPDATE MATCH RESULT
    # ============================================================
    
    def update_result(self, match_id, home_score, away_score, lock: bool = False):
        """
        Записывает фактический результат матча.
        Основной источник — match_results.
        После lock факт становится неизменяемым.
        
        ⚠️ ВНИМАНИЕ: Этот метод выполняет отдельную транзакцию.
        Для атомарного сохранения всех фактов используйте
        save_complete_match_fact().
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверяем, не locked ли уже результат
            cursor.execute("""
                SELECT fact_status, locked_at FROM match_results
                WHERE match_id = ?
            """, (match_id,))
            existing = cursor.fetchone()
            
            if existing and existing["fact_status"] == "locked":
                raise ValueError(f"Match result {match_id} is LOCKED and cannot be changed")
            
            if existing:
                cursor.execute("""
                    UPDATE match_results
                    SET home_goals = ?, away_goals = ?,
                        fact_status = ?,
                        locked_at = ?,
                        locked_by = ?
                    WHERE match_id = ?
                """, (
                    home_score, away_score,
                    "locked" if lock else "verified",
                    datetime.now().isoformat() if lock else None,
                    "FAJ" if lock else None,
                    match_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO match_results (
                        match_id, home_goals, away_goals,
                        fact_status, locked_at, locked_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    match_id, home_score, away_score,
                    "locked" if lock else "verified",
                    datetime.now().isoformat() if lock else None,
                    "FAJ" if lock else None
                ))
            
            # Обновляем matches для обратной совместимости
            cursor.execute("""
                UPDATE matches
                SET actual_home = ?, actual_away = ?,
                    status = 'finished',
                    fact_status = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                home_score, away_score,
                "locked" if lock else "verified",
                datetime.now().isoformat(),
                match_id
            ))
            
            if cursor.rowcount == 0:
                raise ValueError(f"Match not found: {match_id}")
            
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def lock_match_result(self, match_id):
        """Защищает результат матча от дальнейших изменений."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE match_results
                SET fact_status = 'locked', locked_at = ?, locked_by = ?
                WHERE match_id = ? AND fact_status != 'locked'
            """, (datetime.now().isoformat(), "FAJ", match_id))
            
            cursor.execute("""
                UPDATE matches
                SET fact_status = 'locked', updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), match_id))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def unlock_match_result(self, match_id: int) -> bool:
        """
        Снимает LOCK только с результата матча.
        Используется для восстановления отсутствующих
        фактических данных статистики/xG.
        
        ВАЖНО:
            - счёт не удаляется;
            - матч не удаляется;
            - существующие факты не удаляются;
            - после повторного сохранения факт снова LOCKED.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Снимаем LOCK только с match_results
            # и matches, если они были залочены
            cursor.execute("""
                UPDATE match_results
                SET fact_status = 'pending'
                WHERE match_id = ?
                  AND fact_status = 'locked'
            """, (match_id,))
            
            # Обновляем matches для согласованности
            cursor.execute("""
                UPDATE matches
                SET fact_status = 'pending', updated_at = ?
                WHERE id = ?
                  AND fact_status = 'locked'
            """, (datetime.now().isoformat(), match_id))
            
            conn.commit()
            
            if cursor.rowcount == 0:
                # Если ничего не обновилось — возможно, уже разлочено
                logger.debug(
                    "MATCH RESULT ALREADY UNLOCKED | match_id=%s",
                    match_id
                )
                return True
            
            logger.info(
                "MATCH RESULT UNLOCKED | match_id=%s",
                match_id
            )
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(
                "Unlock match result error: %s",
                e
            )
            return False
        finally:
            conn.close()
    
    def is_result_locked(self, match_id) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fact_status FROM match_results
                WHERE match_id = ?
            """, (match_id,))
            row = cursor.fetchone()
            return row and row["fact_status"] == "locked"
        finally:
            conn.close()
    
    def get_match_result(self, match_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT home_goals, away_goals, fact_status, locked_at
                FROM match_results
                WHERE match_id = ?
            """, (match_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    # ============================================================
    # UPDATE MATCH STATS
    # ============================================================
    
    def update_match_stats(self, match_id: int, stats: Dict[str, Any]) -> bool:
        """
        Сохраняет фактическую статистику матча.
        
        ⚠️ ВНИМАНИЕ: 
        - Этот метод выполняет отдельную транзакцию.
        - Для атомарного сохранения всех фактов используйте save_complete_match_fact()
        - Метод проверяет LOCK и блокирует изменение LOCKED-матча.
        
        Архитектура:
            matches
                └── основные агрегаты/xG
            match_statistics
                ├── домашняя команда
                └── гостевая команда
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # ====================================================
            # 0. ПРОВЕРКА LOCK
            # ====================================================
            cursor.execute("""
                SELECT fact_status FROM match_results
                WHERE match_id = ?
            """, (match_id,))
            row = cursor.fetchone()
            if row and row["fact_status"] == "locked":
                raise ValueError(f"Match {match_id} is LOCKED. Stats cannot be changed.")
            
            # ====================================================
            # 1. ПОЛУЧАЕМ КОМАНДЫ МАТЧА
            # ====================================================
            cursor.execute(
                """
                SELECT
                    home_team_id,
                    away_team_id
                FROM matches
                WHERE id = ?
                """,
                (match_id,)
            )
            match_row = cursor.fetchone()
            if not match_row:
                conn.rollback()
                logger.error(f"Match {match_id} not found")
                return False
            
            home_team_id = match_row["home_team_id"]
            away_team_id = match_row["away_team_id"]
            
            if home_team_id is None or away_team_id is None:
                conn.rollback()
                logger.error(f"Match {match_id} has no team IDs")
                return False
            
            # ====================================================
            # 2. ОБНОВЛЯЕМ ОСНОВНЫЕ ПОЛЯ В matches
            # ====================================================
            cursor.execute(
                """
                UPDATE matches SET
                    home_xg = ?,
                    away_xg = ?,
                    home_possession = ?,
                    away_possession = ?,
                    home_shots = ?,
                    away_shots = ?,
                    home_shots_on_target = ?,
                    away_shots_on_target = ?,
                    parser_source = ?,
                    parser_version = ?,
                    data_quality = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    stats.get("home_xg"),
                    stats.get("away_xg"),
                    stats.get("home_possession"),
                    stats.get("away_possession"),
                    stats.get("home_shots"),
                    stats.get("away_shots"),
                    stats.get("home_shots_on_target"),
                    stats.get("away_shots_on_target"),
                    stats.get("parser_source"),
                    stats.get("parser_version"),
                    stats.get("data_quality", 1.0),
                    datetime.now().isoformat(),
                    match_id
                )
            )
            
            if cursor.rowcount == 0:
                conn.rollback()
                logger.error(f"Match {match_id} not found in matches table")
                return False
            
            # ====================================================
            # 3. СОХРАНЯЕМ ПОДРОБНУЮ СТАТИСТИКУ
            # ====================================================
            def upsert_team_stats(team_id, prefix):
                cursor.execute(
                    """
                    INSERT INTO match_statistics (
                        match_id,
                        team_id,
                        possession,
                        shots,
                        shots_on_target,
                        corners,
                        fouls,
                        yellow_cards,
                        red_cards,
                        xg,
                        passes,
                        accurate_passes,
                        pass_accuracy,
                        tackles
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(match_id, team_id)
                    DO UPDATE SET
                        possession = excluded.possession,
                        shots = excluded.shots,
                        shots_on_target = excluded.shots_on_target,
                        corners = excluded.corners,
                        fouls = excluded.fouls,
                        yellow_cards = excluded.yellow_cards,
                        red_cards = excluded.red_cards,
                        xg = excluded.xg,
                        passes = excluded.passes,
                        accurate_passes = excluded.accurate_passes,
                        pass_accuracy = excluded.pass_accuracy,
                        tackles = excluded.tackles
                    """,
                    (
                        match_id,
                        team_id,
                        stats.get(f"{prefix}_possession"),
                        stats.get(f"{prefix}_shots"),
                        stats.get(f"{prefix}_shots_on_target"),
                        stats.get(f"{prefix}_corners"),
                        stats.get(f"{prefix}_fouls"),
                        stats.get(f"{prefix}_yellow_cards"),
                        stats.get(f"{prefix}_red_cards"),
                        stats.get(f"{prefix}_xg"),
                        stats.get(f"{prefix}_total_passes"),
                        stats.get(f"{prefix}_accurate_passes"),
                        stats.get(f"{prefix}_pass_accuracy"),
                        stats.get(f"{prefix}_tackles"),
                    )
                )
            
            # Домашняя команда
            upsert_team_stats(home_team_id, "home")
            
            # Гостевая команда
            upsert_team_stats(away_team_id, "away")
            
            conn.commit()
            logger.debug(f"Match stats saved for match_id={match_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Update match stats error: {e}")
            return False
        finally:
            conn.close()
    
    # ============================================================
    # GET MATCH STATS
    # ============================================================
    
    def get_match_stats(self, match_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает полную статистику матча.
        
        Источник:
            match_statistics (две строки: home + away)
        
        Возвращает единый словарь,
        совместимый с import_facts.py.
        
        Returns:
            Словарь с полями:
                home_xg, away_xg,
                home_possession, away_possession,
                home_shots, away_shots,
                home_shots_on_target, away_shots_on_target,
                home_corners, away_corners,
                home_fouls, away_fouls,
                home_yellow_cards, away_yellow_cards,
                home_red_cards, away_red_cards,
                home_total_passes, away_total_passes,
                home_accurate_passes, away_accurate_passes,
                home_pass_accuracy, away_pass_accuracy,
                home_tackles, away_tackles
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    m.home_team_id,
                    m.away_team_id,
                    hs.xg AS home_xg,
                    aws.xg AS away_xg,
                    hs.possession AS home_possession,
                    aws.possession AS away_possession,
                    hs.shots AS home_shots,
                    aws.shots AS away_shots,
                    hs.shots_on_target AS home_shots_on_target,
                    aws.shots_on_target AS away_shots_on_target,
                    hs.corners AS home_corners,
                    aws.corners AS away_corners,
                    hs.fouls AS home_fouls,
                    aws.fouls AS away_fouls,
                    hs.yellow_cards AS home_yellow_cards,
                    aws.yellow_cards AS away_yellow_cards,
                    hs.red_cards AS home_red_cards,
                    aws.red_cards AS away_red_cards,
                    hs.passes AS home_total_passes,
                    aws.passes AS away_total_passes,
                    hs.accurate_passes AS home_accurate_passes,
                    aws.accurate_passes AS away_accurate_passes,
                    hs.pass_accuracy AS home_pass_accuracy,
                    aws.pass_accuracy AS away_pass_accuracy,
                    hs.tackles AS home_tackles,
                    aws.tackles AS away_tackles
                FROM matches m
                LEFT JOIN match_statistics hs
                    ON hs.match_id = m.id
                    AND hs.team_id = m.home_team_id
                LEFT JOIN match_statistics aws
                    ON aws.match_id = m.id
                    AND aws.team_id = m.away_team_id
                WHERE m.id = ?
                """,
                (match_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        except Exception as e:
            logger.error(f"Get match stats error: {e}")
            return None
        finally:
            conn.close()
    
    # ============================================================
    # MATCH PREDICTIONS — APPEND-ONLY ВЕРСИЯ
    # ============================================================
    
    def save_match_prediction_versioned(self, match_id, xg_home, xg_away,
                                         lambda_home=None, lambda_away=None,
                                         home_advantage=1.0,
                                         prediction_type="standard",
                                         model_version="v12.1",
                                         memory_state_id=None) -> int:
        """P0.3: Append-only версия — создаёт новую запись, а не перезаписывает."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получаем текущий revision
            cursor.execute("""
                SELECT COALESCE(MAX(prediction_revision), 0) + 1 AS next_rev
                FROM match_predictions
                WHERE match_id = ? AND prediction_type = ?
            """, (match_id, prediction_type))
            row = cursor.fetchone()
            next_rev = row["next_rev"] if row else 1
            
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO match_predictions (
                    match_id, xg_home, xg_away,
                    lambda_home, lambda_away,
                    home_advantage, prediction_type,
                    model_version, prediction_revision,
                    memory_state_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, xg_home, xg_away,
                lambda_home, lambda_away,
                home_advantage, prediction_type,
                model_version, next_rev,
                memory_state_id, now
            ))
            prediction_id = cursor.lastrowid
            conn.commit()
            return prediction_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_match_prediction(self, match_id, xg_home, xg_away,
                               lambda_home=None, lambda_away=None,
                               home_advantage=1.0, prediction_type="standard",
                               model_version="v12.1"):
        """
        Обратная совместимость. Использует append-only версию.
        """
        return self.save_match_prediction_versioned(
            match_id, xg_home, xg_away,
            lambda_home, lambda_away,
            home_advantage, prediction_type,
            model_version
        )
    
    def get_match_predictions(self, match_id, limit=None):
        """Возвращает все версии прогнозов для матча."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if limit:
                cursor.execute("""
                    SELECT * FROM match_predictions
                    WHERE match_id = ?
                    ORDER BY prediction_revision DESC, created_at DESC
                    LIMIT ?
                """, (match_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM match_predictions
                    WHERE match_id = ?
                    ORDER BY prediction_revision DESC, created_at DESC
                """, (match_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_match_prediction(self, match_id):
        """Возвращает последнюю версию прогноза для совместимости."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM match_predictions
                WHERE match_id = ?
                ORDER BY prediction_revision DESC, created_at DESC
                LIMIT 1
            """, (match_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    # ============================================================
    # TEAM BASE
    # ============================================================
    
    def get_base(self, team_id, season_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM team_base
                WHERE team_id = ? AND season_id = ?
                ORDER BY COALESCE(datetime(updated_at), '') DESC, id DESC
                LIMIT 1
            """, (team_id, season_id))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def update_base(self, team_id, season_id, **kwargs):
        allowed = [
            "attack", "defense", "control", "press", "tempo",
            "transition", "set_pieces", "counter_attack", "build_up",
            "finishing", "goalkeeper", "discipline", "coach_factor",
            "squad_quality", "bench_quality", "home_advantage"
        ]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM team_base
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            existing = cursor.fetchone()
            
            # P1.6: Записываем историю изменений
            if existing:
                # Получаем старые значения
                old_values = {}
                for key in update_data:
                    old_values[key] = existing[key]
                
                fields = []
                values = []
                for key, value in update_data.items():
                    fields.append(f"{key} = ?")
                    values.append(value)
                fields.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(existing["id"])
                cursor.execute(f"UPDATE team_base SET {', '.join(fields)} WHERE id = ?", values)
                
                # Записываем историю
                for key, new_value in update_data.items():
                    old_value = old_values.get(key)
                    if old_value != new_value:
                        self.record_team_history(
                            team_id, season_id, key,
                            str(old_value), str(new_value),
                            reason="team_base_update",
                            source="FAJDatabase.update_base"
                        )
            else:
                defaults = {
                    "attack": 50, "defense": 50, "control": 50,
                    "press": 50, "tempo": 50, "transition": 50,
                    "set_pieces": 50, "counter_attack": 50, "build_up": 50,
                    "finishing": 50, "goalkeeper": 50, "discipline": 50,
                    "coach_factor": 50, "squad_quality": 50,
                    "bench_quality": 50, "home_advantage": 1.0
                }
                defaults.update(update_data)
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO team_base (
                        team_id, season_id, attack, defense, control,
                        press, tempo, transition, set_pieces, counter_attack, build_up,
                        finishing, goalkeeper, discipline, coach_factor,
                        squad_quality, bench_quality, home_advantage,
                        passport_version, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    team_id, season_id,
                    defaults["attack"], defaults["defense"], defaults["control"],
                    defaults["press"], defaults["tempo"], defaults["transition"],
                    defaults["set_pieces"], defaults["counter_attack"], defaults["build_up"],
                    defaults["finishing"], defaults["goalkeeper"], defaults["discipline"],
                    defaults["coach_factor"], defaults["squad_quality"],
                    defaults["bench_quality"], defaults["home_advantage"],
                    1, now
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # TEAM DYNAMIC
    # ============================================================
    
    def get_dynamic(self, team_id, season_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM team_dynamic
                WHERE team_id = ? AND season_id = ?
                ORDER BY COALESCE(datetime(updated_at), '') DESC, id DESC
                LIMIT 1
            """, (team_id, season_id))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def update_dynamic(self, team_id, season_id, **kwargs):
        allowed = [
            "form", "fitness", "morale", "fatigue", "injury_index",
            "coach_confidence", "last5_points", "last5_strength_points",
            "last5_results", "last5_strength_results", "last5_xg", "last5_xga",
            "last5_goals", "last5_conceded", "last5_performance",
            "average_performance", "current_streak", "days_rest",
            "travel_distance", "rotation_index", "last_base_correction_match",
            "passport_confidence"
        ]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        
        now = datetime.now().isoformat()
        update_data["last_sync"] = now
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM team_dynamic
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            existing = cursor.fetchone()
            
            if existing:
                # P1.6: Записываем историю изменений
                old_values = {}
                for key in update_data:
                    if key in existing:
                        old_values[key] = existing[key]
                
                fields = []
                values = []
                for key, value in update_data.items():
                    fields.append(f"{key} = ?")
                    values.append(value)
                fields.append("updated_at = ?")
                values.append(now)
                values.append(existing["id"])
                cursor.execute(f"UPDATE team_dynamic SET {', '.join(fields)} WHERE id = ?", values)
                
                # Записываем историю для ключевых полей
                for key in ["form", "fitness", "morale", "injury_index"]:
                    if key in update_data and key in old_values:
                        old_value = old_values.get(key)
                        new_value = update_data.get(key)
                        if old_value != new_value:
                            self.record_team_history(
                                team_id, season_id, key,
                                str(old_value), str(new_value),
                                reason="team_dynamic_update",
                                source="FAJDatabase.update_dynamic"
                            )
            else:
                cursor.execute("""
                    INSERT INTO team_dynamic (
                        team_id, season_id, form, fitness, morale,
                        fatigue, injury_index, coach_confidence, last5_points,
                        last5_strength_points, last5_results, last5_strength_results,
                        last5_xg, last5_xga, last5_goals, last5_conceded,
                        last5_performance, average_performance, current_streak,
                        days_rest, travel_distance, rotation_index,
                        last_base_correction_match, passport_confidence, last_sync,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    team_id, season_id,
                    kwargs.get("form", 50),
                    kwargs.get("fitness", 50),
                    kwargs.get("morale", 50),
                    kwargs.get("fatigue", 50),
                    kwargs.get("injury_index", 0),
                    kwargs.get("coach_confidence", 50),
                    kwargs.get("last5_points", 0.0),
                    kwargs.get("last5_strength_points", 0.0),
                    kwargs.get("last5_results", "[0,0,0,0,0]"),
                    kwargs.get("last5_strength_results", "[0,0,0,0,0]"),
                    kwargs.get("last5_xg", 0.0),
                    kwargs.get("last5_xga", 0.0),
                    kwargs.get("last5_goals", 0),
                    kwargs.get("last5_conceded", 0),
                    kwargs.get("last5_performance", "[0,0,0,0,0]"),
                    kwargs.get("average_performance", 0.0),
                    kwargs.get("current_streak", 0),
                    kwargs.get("days_rest", 7),
                    kwargs.get("travel_distance", 0),
                    kwargs.get("rotation_index", 0),
                    kwargs.get("last_base_correction_match", 0),
                    kwargs.get("passport_confidence", 0.4),
                    now, now
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # TEAM IDENTITY
    # ============================================================
    
    def get_identity(self, team_id, season_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM team_identity
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def update_identity(self, team_id, season_id, **kwargs):
        allowed = ["style", "tempo", "pressing", "transition", "risk_level"]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM team_identity
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            existing = cursor.fetchone()
            
            if existing:
                fields = [f"{key} = ?" for key in update_data]
                values = list(update_data.values())
                values.append(existing["id"])
                cursor.execute(f"UPDATE team_identity SET {', '.join(fields)} WHERE id = ?", values)
            else:
                cursor.execute("""
                    INSERT INTO team_identity (
                        team_id, season_id, style, tempo, pressing, transition, risk_level, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    team_id, season_id,
                    kwargs.get("style", "mixed"),
                    kwargs.get("tempo", "medium"),
                    kwargs.get("pressing", "medium"),
                    kwargs.get("transition", "medium"),
                    kwargs.get("risk_level", "medium"),
                    datetime.now().isoformat()
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # TACTICAL MATCHUP
    # ============================================================
    
    def get_tactical_matchup(self, team_id, season_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tactical_matchup
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def update_tactical_matchup(self, team_id, season_id, **kwargs):
        allowed = ["vs_high_press", "vs_low_block", "vs_counter_attack", "vs_possession", "vs_direct"]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM tactical_matchup
                WHERE team_id = ? AND season_id = ?
                ORDER BY id DESC LIMIT 1
            """, (team_id, season_id))
            existing = cursor.fetchone()
            
            if existing:
                fields = [f"{key} = ?" for key in update_data]
                fields.append("updated_at = ?")
                values = list(update_data.values())
                values.append(datetime.now().isoformat())
                values.append(existing["id"])
                cursor.execute(f"UPDATE tactical_matchup SET {', '.join(fields)} WHERE id = ?", values)
            else:
                now = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO tactical_matchup (
                        team_id, season_id, vs_high_press, vs_low_block, vs_counter_attack,
                        vs_possession, vs_direct, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    team_id, season_id,
                    kwargs.get("vs_high_press", 0.0),
                    kwargs.get("vs_low_block", 0.0),
                    kwargs.get("vs_counter_attack", 0.0),
                    kwargs.get("vs_possession", 0.0),
                    kwargs.get("vs_direct", 0.0),
                    now
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # PREDICTIONS — с версионированием и hash
    # ============================================================
    
    def save_prediction(self, match_id: int, model_version: str, algorithm: str,
                        home_win: float, draw: float, away_win: float,
                        over25: float = 0.0, over35: float = 0.0, btts: float = 0.0,
                        confidence: int = 50, prediction_source: str = "FAJ Engine",
                        prediction_hash: str = None,
                        memory_state_id: str = None,
                        snapshot_id: int = None,
                        passport_revision: str = None,
                        parameter_revision: str = None,
                        faj_final_score: str = None,
                        faj_confidence: int = None,
                        decision_factors: str = None) -> int:
        """Сохраняет прогноз. Если hash совпадает — возвращает существующий."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # P1.9: Проверяем существование по hash
            if prediction_hash:
                cursor.execute("""
                    SELECT id FROM predictions
                    WHERE prediction_hash = ?
                    LIMIT 1
                """, (prediction_hash,))
                existing = cursor.fetchone()
                if existing:
                    # Обновляем FAJ поля если они переданы
                    if faj_final_score is not None or faj_confidence is not None or decision_factors is not None:
                        updates = []
                        params = []
                        if faj_final_score is not None:
                            updates.append("faj_final_score = ?")
                            params.append(faj_final_score)
                        if faj_confidence is not None:
                            updates.append("faj_confidence = ?")
                            params.append(faj_confidence)
                        if decision_factors is not None:
                            updates.append("decision_factors = ?")
                            params.append(decision_factors)
                        if updates:
                            params.append(existing["id"])
                            cursor.execute(f"UPDATE predictions SET {', '.join(updates)} WHERE id = ?", params)
                            conn.commit()
                    return existing["id"]
            
            # Получаем текущую версию для этого матча
            cursor.execute("""
                SELECT COALESCE(MAX(prediction_version), 0) + 1 AS next_ver
                FROM predictions
                WHERE match_id = ?
            """, (match_id,))
            row = cursor.fetchone()
            next_ver = row["next_ver"] if row else 1
            
            cursor.execute("""
                INSERT INTO predictions (
                    match_id, model_version, algorithm,
                    home_win, draw, away_win,
                    over25, over35, btts, confidence,
                    prediction_source, prediction_hash,
                    prediction_status, prediction_version,
                    memory_state_id, snapshot_id,
                    passport_revision, parameter_revision,
                    faj_final_score, faj_confidence, decision_factors,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, model_version, algorithm,
                home_win, draw, away_win,
                over25, over35, btts, confidence,
                prediction_source, prediction_hash,
                "active", next_ver,
                memory_state_id, snapshot_id,
                passport_revision, parameter_revision,
                faj_final_score, faj_confidence, decision_factors,
                datetime.now().isoformat()
            ))
            prediction_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Prediction saved: id={prediction_id}, match_id={match_id}, version={next_ver}")
            return prediction_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_prediction(self, prediction_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM predictions WHERE id = ? LIMIT 1
            """, (prediction_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def get_prediction_by_hash(self, prediction_hash: str):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM predictions WHERE prediction_hash = ? LIMIT 1
            """, (prediction_hash,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def get_predictions_by_match(self, match_id, include_history=True):
        """Возвращает все версии прогнозов для матча."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if include_history:
                cursor.execute("""
                    SELECT * FROM predictions
                    WHERE match_id = ?
                    ORDER BY prediction_version ASC, created_at ASC
                """, (match_id,))
            else:
                cursor.execute("""
                    SELECT * FROM predictions
                    WHERE match_id = ? AND prediction_status = 'active'
                    ORDER BY prediction_version DESC, created_at DESC
                    LIMIT 1
                """, (match_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_latest_prediction(self, match_id):
        """Возвращает последнюю активную версию прогноза."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM predictions
                WHERE match_id = ? AND prediction_status = 'active'
                ORDER BY prediction_version DESC, created_at DESC
                LIMIT 1
            """, (match_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def add_prediction_score(self, prediction_id, score, probability, rank, score_type="math"):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prediction_scores (prediction_id, score, probability, rank, score_type)
                VALUES (?, ?, ?, ?, ?)
            """, (prediction_id, score, probability, rank, score_type))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def add_prediction_distribution(self, prediction_id, home_goals, away_goals, probability):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO prediction_distributions (prediction_id, home_goals, away_goals, probability)
                VALUES (?, ?, ?, ?)
            """, (prediction_id, home_goals, away_goals, probability))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_prediction_scores(self, prediction_id, score_type=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if score_type:
                cursor.execute("""
                    SELECT * FROM prediction_scores
                    WHERE prediction_id = ? AND score_type = ?
                    ORDER BY rank ASC, id ASC
                """, (prediction_id, score_type))
            else:
                cursor.execute("""
                    SELECT * FROM prediction_scores
                    WHERE prediction_id = ?
                    ORDER BY rank ASC, id ASC
                """, (prediction_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: ADD PREDICTION VALIDATION
    # ============================================================
    
    def add_prediction_validation(self, data: Dict[str, Any]) -> int:
        """
        Сохраняет валидацию прогноза с привязкой к prediction_id.
        
        Args:
            data: словарь с полями validation
        
        Returns:
            ID записи validation
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Генерируем validation_hash для защиты от дублей
            validation_hash = data.get('validation_hash')
            if not validation_hash:
                import hashlib
                hash_str = f"{data.get('match_id')}_{data.get('prediction_id')}_{data.get('actual_score')}"
                validation_hash = hashlib.md5(hash_str.encode()).hexdigest()
            
            # Проверяем дубли
            cursor.execute("""
                SELECT id FROM prediction_validation
                WHERE validation_hash = ?
                LIMIT 1
            """, (validation_hash,))
            existing = cursor.fetchone()
            if existing:
                return existing["id"]
            
            cursor.execute("""
                INSERT INTO prediction_validation (
                    match_id, prediction_id, match_prediction_id,
                    validation_hash,
                    predicted_score, actual_score,
                    predicted_home_xg, actual_home_xg,
                    predicted_away_xg, actual_away_xg,
                    predicted_winner, actual_winner,
                    predicted_probability_home,
                    predicted_probability_draw,
                    predicted_probability_away,
                    score_probability, confidence, risk,
                    predicted_btts, actual_btts,
                    predicted_over25, actual_over25,
                    model_version, passport_version, parser_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('match_id'),
                data.get('prediction_id'),
                data.get('match_prediction_id'),
                validation_hash,
                data.get('predicted_score'),
                data.get('actual_score'),
                data.get('predicted_home_xg'),
                data.get('actual_home_xg'),
                data.get('predicted_away_xg'),
                data.get('actual_away_xg'),
                data.get('predicted_winner'),
                data.get('actual_winner'),
                data.get('predicted_probability_home'),
                data.get('predicted_probability_draw'),
                data.get('predicted_probability_away'),
                data.get('score_probability'),
                data.get('confidence'),
                data.get('risk'),
                data.get('predicted_btts'),
                data.get('actual_btts'),
                data.get('predicted_over25'),
                data.get('actual_over25'),
                data.get('model_version'),
                data.get('passport_version'),
                data.get('parser_version')
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Ошибка при добавлении валидации прогноза: {e}")
        finally:
            conn.close()
    
    def get_validation_by_match(self, match_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM prediction_validation
                WHERE match_id = ?
                ORDER BY created_at DESC
            """, (match_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_validation_by_prediction(self, prediction_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM prediction_validation
                WHERE prediction_id = ?
                ORDER BY created_at DESC
            """, (prediction_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # EXPERT PREDICTIONS
    # ============================================================
    
    def save_expert_prediction(self, match_id, expert_name, score,
                               comment="", confidence=50):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expert_predictions (
                    match_id, expert_name, score, comment, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                match_id, expert_name, score, comment, confidence,
                datetime.now().isoformat()
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_expert_predictions(self, match_id: int) -> List[Dict[str, Any]]:
        """Возвращает все прогнозы экспертов для матча."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM expert_predictions
                WHERE match_id = ?
                ORDER BY created_at DESC
            """, (match_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # ============================================================
    # JOURNAL
    # ============================================================
    
    def add_journal_entry(self, match_id, faj_prediction, expert_prediction,
                          actual_result, error_type, error_score, analysis=""):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO journal (
                    match_id, faj_prediction, expert_prediction,
                    actual_result, error_type, error_score, analysis, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, faj_prediction, expert_prediction,
                actual_result, error_type, error_score, analysis,
                datetime.now().isoformat()
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # MODEL PARAMETERS — с версионированием (исправлено)
    # ============================================================
    
    def set_model_parameter(self, model_version, category, parameter, value,
                            description="", group_name=None):
        """P0.2: Версионированное сохранение параметра."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получаем текущее значение и revision
            cursor.execute("""
                SELECT parameter_value, revision, is_current
                FROM model_parameters
                WHERE model_version = ? AND parameter_name = ?
                ORDER BY revision DESC
                LIMIT 1
            """, (model_version, parameter))
            current = cursor.fetchone()
            
            if current and current["is_current"] == 1 and current["parameter_value"] == value:
                # Значение не изменилось
                return
            
            # Получаем новый revision
            cursor.execute("""
                SELECT COALESCE(MAX(revision), 0) + 1 AS next_rev
                FROM model_parameters
                WHERE model_version = ? AND parameter_name = ?
            """, (model_version, parameter))
            row = cursor.fetchone()
            next_rev = row["next_rev"] if row else 1
            
            # Снимаем флаг is_current с предыдущей записи
            cursor.execute("""
                UPDATE model_parameters
                SET is_current = 0
                WHERE model_version = ? AND parameter_name = ? AND is_current = 1
            """, (model_version, parameter))
            
            # Вставляем новую запись
            cursor.execute("""
                INSERT INTO model_parameters (
                    group_name, model_version, category,
                    parameter_name, parameter_value,
                    description, revision, is_current, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                group_name or category,
                model_version,
                category,
                parameter,
                value,
                description,
                next_rev,
                1,
                datetime.now().isoformat()
            ))
            
            # Записываем историю изменения
            if current:
                self.record_parameter_history(
                    parameter_name=parameter,
                    group_name=group_name or category,
                    model_version=model_version,
                    old_value=current["parameter_value"],
                    new_value=value,
                    delta=value - current["parameter_value"],
                    reason="set_model_parameter"
                )
            
            conn.commit()
            logger.info(f"Parameter updated: {parameter} = {value} (rev {next_rev})")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_model_parameters(self, model_version=None, current_only=True):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if model_version and current_only:
                cursor.execute("""
                    SELECT * FROM model_parameters
                    WHERE model_version = ? AND is_current = 1
                    ORDER BY category, parameter_name
                """, (model_version,))
            elif model_version:
                cursor.execute("""
                    SELECT * FROM model_parameters
                    WHERE model_version = ?
                    ORDER BY revision DESC, category, parameter_name
                """, (model_version,))
            elif current_only:
                cursor.execute("""
                    SELECT * FROM model_parameters
                    WHERE is_current = 1
                    ORDER BY model_version, category, parameter_name
                """)
            else:
                cursor.execute("""
                    SELECT * FROM model_parameters
                    ORDER BY model_version, category, parameter_name, revision DESC
                """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_parameter_history(self, parameter_name: str, model_version: str = None,
                              limit: int = 20) -> List[Dict[str, Any]]:
        """Возвращает историю изменений параметра."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if model_version:
                cursor.execute("""
                    SELECT * FROM parameter_history
                    WHERE parameter_name = ? AND model_version = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (parameter_name, model_version, limit))
            else:
                cursor.execute("""
                    SELECT * FROM parameter_history
                    WHERE parameter_name = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (parameter_name, limit))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def record_parameter_history(self, parameter_name: str, group_name: str,
                                 model_version: str, old_value: float,
                                 new_value: float, delta: float,
                                 reason: str = "", confidence: float = 1.0,
                                 reference_event_id: int = None,
                                 reference_match_id: int = None):
        """P1.3: Записывает историю изменения параметра."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO parameter_history (
                    parameter_name, group_name, model_version,
                    old_value, new_value, delta,
                    reason, confidence,
                    reference_event_id, reference_match_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                parameter_name, group_name, model_version,
                old_value, new_value, delta,
                reason, confidence,
                reference_event_id, reference_match_id,
                datetime.now().isoformat()
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_parameter(self, group_name: str, parameter_name: str,
                      version: str = None) -> Optional[float]:
        """Возвращает текущее значение параметра."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if version:
                cursor.execute("""
                    SELECT parameter_value
                    FROM model_parameters
                    WHERE group_name = ?
                      AND parameter_name = ?
                      AND model_version = ?
                      AND is_current = 1
                    LIMIT 1
                """, (group_name, parameter_name, version))
            else:
                cursor.execute("""
                    SELECT parameter_value
                    FROM model_parameters
                    WHERE group_name = ?
                      AND parameter_name = ?
                      AND is_current = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (group_name, parameter_name))
            row = cursor.fetchone()
            if not row:
                return None
            return row["parameter_value"]
        finally:
            conn.close()
    
    def save_parameter(self, group_name: str, parameter_name: str,
                       parameter_value: float, version: str = None,
                       description: str = "") -> bool:
        try:
            self.set_model_parameter(
                model_version=version or DB_SCHEMA_VERSION,
                category=group_name,
                parameter=parameter_name,
                value=parameter_value,
                description=description,
                group_name=group_name
            )
            return True
        except Exception as e:
            logger.error(f"Save parameter error: {e}")
            return False
    
    # ============================================================
    # TEAM HISTORY API (P1.4)
    # ============================================================
    
    def record_team_history(self, team_id: int, season_id: int,
                            field: str, old_value: str, new_value: str,
                            reason: str = "", source: str = "FAJDatabase",
                            reference_match_id: int = None,
                            reference_event_id: int = None) -> int:
        """P1.4: Записывает историю изменения команды."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO team_history (
                    team_id, season_id, field,
                    old_value, new_value,
                    reason, source,
                    reference_match_id, reference_event_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                team_id, season_id, field,
                str(old_value) if old_value is not None else None,
                str(new_value) if new_value is not None else None,
                reason, source,
                reference_match_id, reference_event_id,
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_team_history(self, team_id: int, season_id: int = None,
                         field: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает историю изменений команды."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM team_history WHERE team_id = ?"
            params = [team_id]
            
            if season_id is not None:
                query += " AND season_id = ?"
                params.append(season_id)
            
            if field is not None:
                query += " AND field = ?"
                params.append(field)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # LEARNING LAYER
    # ============================================================
    
    def upsert_gold(self, data: Dict[str, Any]) -> int:
        """
        P0.1: Добавляет или обновляет запись в gold_dataset.
        Исправлен баг с commit().
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверяем, не locked ли запись
            cursor.execute("""
                SELECT id, locked FROM gold_dataset
                WHERE match_id = ?
            """, (data.get('match_id'),))
            existing = cursor.fetchone()
            
            if existing and existing["locked"] == 1:
                raise ValueError(f"Gold record {existing['id']} is LOCKED and cannot be modified")

            if existing:
                gold_id = existing["id"]
                cursor.execute("""
                    UPDATE gold_dataset SET
                        actual_score = COALESCE(?, actual_score),
                        actual_xg_home = COALESCE(?, actual_xg_home),
                        actual_xg_away = COALESCE(?, actual_xg_away),
                        actual_btts = COALESCE(?, actual_btts),
                        actual_total_25 = COALESCE(?, actual_total_25),
                        actual_total_35 = COALESCE(?, actual_total_35),
                        actual_home_goals = COALESCE(?, actual_home_goals),
                        actual_away_goals = COALESCE(?, actual_away_goals),
                        status = COALESCE(?, status),
                        expert_score = COALESCE(?, expert_score),
                        expert_reasoning = COALESCE(?, expert_reasoning),
                        updated_at = ?
                    WHERE id = ?
                """, (
                    data.get('actual_score'),
                    data.get('actual_xg_home'),
                    data.get('actual_xg_away'),
                    data.get('actual_btts'),
                    data.get('actual_total_25'),
                    data.get('actual_total_35'),
                    data.get('actual_home_goals'),
                    data.get('actual_away_goals'),
                    data.get('status'),
                    data.get('expert_score'),
                    data.get('expert_reasoning'),
                    datetime.now().isoformat(),
                    gold_id
                ))
                conn.commit()
                return gold_id
            else:
                cursor.execute("""
                    INSERT INTO gold_dataset (
                        match_id, home_team, away_team, match_date,
                        model_version,
                        faj_score, faj_xg_home, faj_xg_away,
                        faj_btts, faj_total_25, faj_total_35,
                        faj_confidence, faj_rating_home, faj_rating_away,
                        faj_pir_home, faj_pir_away,
                        faj_style_home, faj_style_away,
                        expert_score, expert_reasoning,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('match_id'),
                    data.get('home_team'),
                    data.get('away_team'),
                    data.get('match_date'),
                    data.get('model_version', '1.0'),
                    data.get('faj_score'),
                    data.get('faj_xg_home'),
                    data.get('faj_xg_away'),
                    data.get('faj_btts'),
                    data.get('faj_total_25'),
                    data.get('faj_total_35'),
                    data.get('faj_confidence'),
                    data.get('faj_rating_home'),
                    data.get('faj_rating_away'),
                    data.get('faj_pir_home'),
                    data.get('faj_pir_away'),
                    data.get('faj_style_home'),
                    data.get('faj_style_away'),
                    data.get('expert_score'),
                    data.get('expert_reasoning'),
                    data.get('status', 'pending'),
                    datetime.now().isoformat()
                ))
                gold_id = cursor.lastrowid
                conn.commit()
                return gold_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def lock_gold(self, gold_id: int) -> bool:
        """P1.8: Защищает gold-запись от изменений после completion."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE gold_dataset
                SET locked = 1, locked_at = ?, status = 'completed'
                WHERE id = ? AND locked = 0
            """, (datetime.now().isoformat(), gold_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def update_gold_actual(self, gold_id, actual_data):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE gold_dataset SET
                    actual_score = ?,
                    actual_xg_home = ?,
                    actual_xg_away = ?,
                    actual_btts = ?,
                    actual_total_25 = ?,
                    actual_total_35 = ?,
                    actual_home_goals = ?,
                    actual_away_goals = ?,
                    status = 'completed',
                    updated_at = ?
                WHERE id = ? AND locked = 0
            """, (
                actual_data.get('actual_score'),
                actual_data.get('actual_xg_home'),
                actual_data.get('actual_xg_away'),
                actual_data.get('actual_btts'),
                actual_data.get('actual_total_25'),
                actual_data.get('actual_total_35'),
                actual_data.get('actual_home_goals'),
                actual_data.get('actual_away_goals'),
                datetime.now().isoformat(),
                gold_id
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_gold_by_match(self, match_id):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gold_dataset
                WHERE match_id = ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 1
            """, (match_id,))
            return cursor.fetchone()
        finally:
            conn.close()
    
    def get_gold_pending(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gold_dataset
                WHERE status = 'pending' AND locked = 0
                ORDER BY match_date DESC
            """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_gold_all(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM gold_dataset ORDER BY id DESC
            """)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_gold_count(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM gold_dataset")
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def add_learning_record(self, data):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learning_records (
                    gold_id, match_id, home_team, away_team,
                    faj_score, actual_score,
                    faj_xg_home, faj_xg_away,
                    actual_xg_home, actual_xg_away,
                    error_score, error_xg,
                    error_btts, error_total_25, error_total_35,
                    error_type, cause_type, error_severity, error_detail,
                    recommendation, corrected_weights,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('gold_id'),
                data.get('match_id'),
                data.get('home_team'),
                data.get('away_team'),
                data.get('faj_score'),
                data.get('actual_score'),
                data.get('faj_xg_home'),
                data.get('faj_xg_away'),
                data.get('actual_xg_home'),
                data.get('actual_xg_away'),
                data.get('error_score'),
                data.get('error_xg'),
                data.get('error_btts'),
                data.get('error_total_25'),
                data.get('error_total_35'),
                data.get('error_type'),
                data.get('cause_type'),
                data.get('error_severity'),
                data.get('error_detail'),
                data.get('recommendation'),
                data.get('corrected_weights'),
                data.get('status', 'new'),
                datetime.now().isoformat()
            ))
            record_id = cursor.lastrowid
            conn.commit()
            return record_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
        def get_learning_records(
        self,
        match_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read-only доступ к learning_records.

        Args:
            match_ids:
                Необязательный список match_id.
                Если передан — возвращаются только записи
                указанных матчей.
            limit:
                Необязательное максимальное количество записей.

        Returns:
            Список обычных dict.

        ВАЖНО:
            - только SELECT;
            - ничего не изменяет в БД;
            - схему не меняет;
            - таблицу learning_records не создаёт;
            - отсутствующие match_ids не являются ошибкой.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            sql = """
                SELECT *
                FROM learning_records
            """

            params = []
            conditions = []

            if match_ids:
                normalized_ids = []

                for match_id in match_ids:
                    if match_id is None:
                        continue

                    try:
                        normalized_ids.append(int(match_id))
                    except (TypeError, ValueError):
                        continue

                if normalized_ids:
                    placeholders = ", ".join("?" for _ in normalized_ids)
                    conditions.append(
                        f"match_id IN ({placeholders})"
                    )
                    params.extend(normalized_ids)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            sql += """
                ORDER BY datetime(created_at) DESC, id DESC
            """

            if limit is not None:
                try:
                    limit_value = int(limit)
                except (TypeError, ValueError):
                    limit_value = 0

                if limit_value > 0:
                    sql += " LIMIT ?"
                    params.append(limit_value)

            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()
    
    def get_learning_count(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM learning_records")
            row = cursor.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()
    
    def update_learning_status(self, record_id, status, recommendation=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if recommendation:
                cursor.execute("""
                    UPDATE learning_records
                    SET status = ?, recommendation = ?
                    WHERE id = ?
                """, (status, recommendation, record_id))
            else:
                cursor.execute("""
                    UPDATE learning_records
                    SET status = ?
                    WHERE id = ?
                """, (status, record_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def add_learning_event(self, data):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO learning_events (
                    match_id, season_id, round_number,
                    home_team_id, away_team_id, home_team, away_team,
                    faj_score, actual_score,
                    faj_xg_home, faj_xg_away,
                    actual_xg_home, actual_xg_away,
                    error_magnitude, error_type, cause_type, error_severity,
                    learning_action, delta, confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('match_id'),
                data.get('season_id'),
                data.get('round_number'),
                data.get('home_team_id'),
                data.get('away_team_id'),
                data.get('home_team'),
                data.get('away_team'),
                data.get('faj_score'),
                data.get('actual_score'),
                data.get('faj_xg_home'),
                data.get('faj_xg_away'),
                data.get('actual_xg_home'),
                data.get('actual_xg_away'),
                data.get('error_magnitude'),
                data.get('error_type'),
                data.get('cause_type'),
                data.get('error_severity'),
                data.get('learning_action'),
                data.get('delta'),
                data.get('confidence'),
                datetime.now().isoformat()
            ))
            event_id = cursor.lastrowid
            conn.commit()
            return event_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # PASSPORT — с версионированием (исправлено)
    # ============================================================
    
    def save_passport_meta(self, team_id, season_id, passport_data):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO team_passport_meta (
                    team_id, season_id, style, dna, strengths, weaknesses,
                    class, version, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id, season_id) DO UPDATE SET
                    style = excluded.style,
                    dna = excluded.dna,
                    strengths = excluded.strengths,
                    weaknesses = excluded.weaknesses,
                    class = excluded.class,
                    version = excluded.version,
                    source = excluded.source,
                    updated_at = excluded.updated_at
            """, (
                team_id,
                season_id,
                passport_data.get("style", ""),
                passport_data.get("dna", ""),
                passport_data.get("strengths", ""),
                passport_data.get("weaknesses", ""),
                passport_data.get("class", ""),
                passport_data.get("version", "1.0"),
                passport_data.get("source", "FAJ Expert Layer"),
                datetime.now().isoformat()
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_team_passport(self, team_id: int, season_id: int,
                          version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if version:
                cursor.execute("""
                    SELECT *
                    FROM team_passports
                    WHERE team_id = ? AND season_id = ? AND version = ?
                    ORDER BY id DESC LIMIT 1
                """, (team_id, season_id, version))
            else:
                cursor.execute("""
                    SELECT *
                    FROM team_passports
                    WHERE team_id = ? AND season_id = ?
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT 1
                """, (team_id, season_id))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def save_team_passport(self, team_id: int, season_id: int,
                           data: Dict[str, Any], version: Optional[str] = None,
                           source: str = "manual") -> Optional[int]:
        """P0.6: Версионированное сохранение паспорта."""
        if team_id is None or season_id is None:
            raise ValueError("team_id and season_id are required")
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Генерируем уникальный UUID для этой версии паспорта
            passport_uuid = data.get("passport_uuid") or str(uuid.uuid4())
            
            if version is None:
                cursor.execute("""
                    SELECT version FROM team_passports
                    WHERE team_id = ? AND season_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (team_id, season_id))
                row = cursor.fetchone()
                version = row["version"] if row else "v1.0"
            
            # Проверяем, существует ли уже такая версия
            cursor.execute("""
                SELECT id FROM team_passports
                WHERE team_id = ? AND season_id = ? AND version = ?
                LIMIT 1
            """, (team_id, season_id, version))
            existing = cursor.fetchone()
            
            if existing:
                # Обновляем только если явно разрешено
                if data.get("force_update", False):
                    passport_id = existing["id"]
                    fields = []
                    values = []
                    for key, value in data.items():
                        if key in ("team_id", "season_id", "version", "passport_uuid", "force_update"):
                            continue
                        fields.append(f"{key} = ?")
                        values.append(value)
                    values.append(datetime.now().isoformat())
                    values.append(passport_id)
                    cursor.execute(f"UPDATE team_passports SET {', '.join(fields)}, updated_at = ? WHERE id = ?", values)
                    conn.commit()
                    return passport_id
                else:
                    # Возвращаем существующий ID
                    return existing["id"]
            
            # Создаём новую версию
            passport_data = {
                "team_id": team_id,
                "season_id": season_id,
                "attack": data.get("attack", 50.0),
                "defense": data.get("defense", 50.0),
                "control": data.get("control", 50.0),
                "tempo": data.get("tempo", 50.0),
                "press": data.get("press", 50.0),
                "transition": data.get("transition", 50.0),
                "finishing": data.get("finishing", 50.0),
                "goalkeeper": data.get("goalkeeper", 50.0),
                "discipline": data.get("discipline", 50.0),
                "squad_quality": data.get("squad_quality", 50.0),
                "bench_quality": data.get("bench_quality", 50.0),
                "coach_factor": data.get("coach_factor", 50.0),
                "mental": data.get("mental", 50.0),
                "home_strength": data.get("home_strength", 50.0),
                "away_strength": data.get("away_strength", 50.0),
                "injury_factor": data.get("injury_factor", 50.0),
                "key_player_loss": data.get("key_player_loss", 50.0),
                "league_adaptation": data.get("league_adaptation", 80.0),
                "form": data.get("form", 50.0),
                "passport_confidence": data.get("passport_confidence", 0.5),
                "faj_rating": data.get("faj_rating", 0.0),
                "version": version,
                "passport_uuid": passport_uuid,
                "source": source,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            columns = ", ".join(passport_data.keys())
            placeholders = ", ".join(["?"] * len(passport_data))
            cursor.execute(f"INSERT INTO team_passports ({columns}) VALUES ({placeholders})", list(passport_data.values()))
            passport_id = cursor.lastrowid
            
            conn.commit()
            logger.info(f"Passport saved: team_id={team_id}, version={version}, uuid={passport_uuid}")
            return passport_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Save team passport error: {e}")
            return None
        finally:
            conn.close()
    
    # ============================================================
    # MATCH SNAPSHOTS — с passport_id и memory_state_id
    # ============================================================
    
    def record_match_snapshot(self, match_id: int, team_id: int,
                               data: Dict[str, Any],
                               passport_id: int = None,
                               passport_version: str = None,
                               dynamic_id: int = None,
                               memory_state_id: str = None) -> int:
        """P1.2: Записывает снапшот с идентификаторами происхождения."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO match_snapshots (
                    match_id, team_id,
                    attack, defense, control, press, tempo,
                    transition, finishing, coach_factor,
                    squad_quality, form, fitness, fatigue, morale,
                    xg_for, xg_against, opponent_strength, confidence_factor,
                    passport_id, passport_version, dynamic_id, memory_state_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id, team_id,
                data.get("attack"),
                data.get("defense"),
                data.get("control"),
                data.get("press"),
                data.get("tempo"),
                data.get("transition"),
                data.get("finishing"),
                data.get("coach_factor"),
                data.get("squad_quality"),
                data.get("form"),
                data.get("fitness"),
                data.get("fatigue"),
                data.get("morale"),
                data.get("xg_for"),
                data.get("xg_against"),
                data.get("opponent_strength"),
                data.get("confidence_factor"),
                passport_id,
                passport_version,
                dynamic_id,
                memory_state_id,
                datetime.now().isoformat()
            ))
            snapshot_id = cursor.lastrowid
            conn.commit()
            return snapshot_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_match_snapshots(self, match_id: int, team_id: int = None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if team_id:
                cursor.execute("""
                    SELECT * FROM match_snapshots
                    WHERE match_id = ? AND team_id = ?
                    ORDER BY created_at DESC
                """, (match_id, team_id))
            else:
                cursor.execute("""
                    SELECT * FROM match_snapshots
                    WHERE match_id = ?
                    ORDER BY team_id, created_at DESC
                """, (match_id,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # TEAM FORM HISTORY
    # ============================================================
    
    def save_team_form(self, data: Dict[str, Any]) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO team_form_history (
                    team_id, season_id, round, match_id, opponent_team_id,
                    rating_before, rating_after, form,
                    matches_count, win_rate, draw_rate, loss_rate,
                    last5_points, last5_xg, last5_xga, goal_difference,
                    form_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('team_id'),
                data.get('season_id'),
                data.get('round'),
                data.get('match_id'),
                data.get('opponent_team_id'),
                data.get('rating_before'),
                data.get('rating_after'),
                data.get('form'),
                data.get('matches_count'),
                data.get('win_rate'),
                data.get('draw_rate'),
                data.get('loss_rate'),
                data.get('last5_points'),
                data.get('last5_xg'),
                data.get('last5_xga'),
                data.get('goal_difference'),
                data.get('form_source', 'parser')
            ))
            row_id = cursor.lastrowid
            conn.commit()
            return row_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_team_form_history(self, team_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM team_form_history
                WHERE team_id = ?
                ORDER BY round DESC
                LIMIT ?
            """, (team_id, limit))
            return cursor.fetchall()
        finally:
            conn.close()
    
    # ============================================================
    # DELETE METHODS — ИСПРАВЛЕНА ВЕРСИЯ С PRAGMA
    # ============================================================
    
    def delete_match(self, match_id: int) -> bool:
        """
        Удаляет матч и все связанные с ним данные.
        Использует PRAGMA foreign_keys = OFF для обхода ограничений.
        Возвращает True если матч был удалён, False если не найден.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Временно отключаем проверку внешних ключей
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Все таблицы, которые могут ссылаться на match_id
            related_tables = [
                "match_results",
                "match_statistics",
                "predictions",
                "prediction_scores",
                "prediction_distributions",
                "prediction_validation",
                "gold_dataset",
                "learning_records",
                "learning_events",
                "expert_predictions",
                "match_predictions",
                "match_snapshots",
                "journal",
                "audit_log",
                "team_form_history",
                "match_events",
                "standings",
                "team_dynamics",
                "xg_memory",
                "player_impact",
                "team_competition_profile",
                "team_events",
                "team_history",
                "parameter_history",
            ]
            
            for table in related_tables:
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE match_id = ?", (match_id,))
                except Exception as e:
                    logger.debug(f"Ошибка удаления из {table}: {e}")
            
            # Отдельно для таблиц с reference_match_id
            cursor.execute("DELETE FROM parameter_history WHERE reference_match_id = ?", (match_id,))
            cursor.execute("DELETE FROM team_history WHERE reference_match_id = ?", (match_id,))
            
            # Удаляем сам матч
            cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            deleted = cursor.rowcount > 0
            
            # Включаем проверку обратно
            cursor.execute("PRAGMA foreign_keys = ON")
            
            conn.commit()
            return deleted
            
        except Exception as e:
            conn.rollback()
            try:
                cursor.execute("PRAGMA foreign_keys = ON")
            except:
                pass
            logger.error(f"Delete match error: {e}")
            return False
        finally:
            conn.close()
    
    def delete_round(self, round_id: int) -> bool:
        """
        Удаляет тур и все его матчи.
        Возвращает True если тур был удалён, False если не найден.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получаем все матчи тура
            cursor.execute("""
                SELECT id FROM matches WHERE round_id = ?
            """, (round_id,))
            matches = cursor.fetchall()
            
            # Удаляем каждый матч (через delete_match, чтобы очистить связанные данные)
            for match in matches:
                self.delete_match(match["id"])
            
            # Удаляем сам тур
            cursor.execute("""
                DELETE FROM rounds WHERE id = ?
            """, (round_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    # ============================================================
    # LEARNING STATUS
    # ============================================================
    
    def get_learning_status(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM gold_dataset")
            gold_count = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM learning_records")
            learning_count = cursor.fetchone()["count"]
            cursor.execute("SELECT COUNT(*) AS count FROM learning_events")
            events_count = cursor.fetchone()["count"]
            cursor.execute("""
                SELECT COUNT(*) AS count FROM learning_records
                WHERE status = 'new' AND error_severity >= 4
            """)
            critical = cursor.fetchone()["count"]
            return {
                "gold_dataset": gold_count,
                "learning_records": learning_count,
                "learning_events": events_count,
                "critical_errors": critical
            }
        finally:
            conn.close()

    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET CURRENT PARAMETERS (LEGACY — ОСТАВЛЯЕМ ДЛЯ СОВМЕСТИМОСТИ)
    # ============================================================

    def get_current_parameters(self) -> Optional[Any]:
        """
        [LEGACY] Возвращает текущие параметры модели в формате alpha/beta/gamma/delta.
        
        НЕ ИСПОЛЬЗОВАТЬ для новых модулей.
        Используйте get_current_parameter_state().
        
        Returns:
            SimpleNamespace с полями alpha, beta, gamma, delta, version
            или значения по умолчанию.
        """
        from types import SimpleNamespace
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT parameter_name, parameter_value
                FROM model_parameters
                WHERE is_current = 1
                ORDER BY parameter_name
            """)
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.info("No model parameters found, using defaults")
                return SimpleNamespace(
                    alpha=0.7,
                    beta=1.0,
                    gamma=0.5,
                    delta=0.3,
                    version=1,
                )
            
            params = {}
            version = 1
            
            for row in rows:
                name = row["parameter_name"]
                value = row["parameter_value"]
                
                if name in ("alpha", "beta", "gamma", "delta"):
                    params[name] = float(value)
                elif name == "version":
                    version = int(value)
            
            defaults = {"alpha": 0.7, "beta": 1.0, "gamma": 0.5, "delta": 0.3}
            for key, default_value in defaults.items():
                if key not in params:
                    params[key] = default_value
            
            return SimpleNamespace(
                alpha=params["alpha"],
                beta=params["beta"],
                gamma=params["gamma"],
                delta=params["delta"],
                version=version,
            )
            
        finally:
            conn.close()

    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET CURRENT PARAMETER STATE (КАНОНИЧЕСКИЙ)
    # ============================================================

    def get_current_parameter_state(self, model_version: str = "v12.1") -> Dict[str, Any]:
        """
        Возвращает ТЕКУЩЕЕ СОСТОЯНИЕ ВСЕХ ПАРАМЕТРОВ модели.
        
        ЕДИНСТВЕННЫЙ источник истины для параметров.
        
        Args:
            model_version: версия модели (по умолчанию "v12.1")
        
        Returns:
            {
                "model_version": str,
                "revision": int,           # глобальная ревизия модели
                "parameters": {
                    "attack_sensitivity": float,
                    "defense_sensitivity": float,
                    "control_sensitivity": float,
                    "form_sensitivity": float,
                    "xg_scale": float,     # если присутствует в БД
                    # ... любые другие параметры из БД
                }
            }
        
        Если параметров нет — возвращает default revision=0 и пустой словарь.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получаем все текущие параметры
            cursor.execute("""
                SELECT parameter_name, parameter_value, revision
                FROM model_parameters
                WHERE model_version = ?
                  AND is_current = 1
                ORDER BY parameter_name
            """, (model_version,))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.info("No model parameters found for %s", model_version)
                return {
                    "model_version": model_version,
                    "revision": 0,
                    "parameters": {}
                }
            
            # Собираем параметры
            parameters = {}
            max_revision = 0
            
            for row in rows:
                name = row["parameter_name"]
                value = row["parameter_value"]
                revision = row["revision"] or 0
                
                try:
                    parameters[name] = float(value)
                    if revision > max_revision:
                        max_revision = revision
                except (TypeError, ValueError):
                    logger.warning("Invalid parameter value: %s=%r", name, value)
                    continue
            
            return {
                "model_version": model_version,
                "revision": max_revision,
                "parameters": parameters
            }
            
        finally:
            conn.close()

    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: APPLY PARAMETER CHANGE (АТОМАРНЫЙ)
    # ============================================================

    def apply_parameter_change(
        self,
        parameter_name: str,
        new_value: float,
        reason: str,
        confidence: float = 1.0,
        expected_old_value: Optional[float] = None,
        reference_match_id: Optional[int] = None,
        group_name: str = "learning",
        model_version: str = "v12.1",
        category: str = "etc",
    ) -> Dict[str, Any]:
        """
        АТОМАРНОЕ применение изменения параметра.
        
        ОДНА ТРАНЗАКЦИЯ.
        
        При любой ошибке → ROLLBACK → 0 изменений.
        
        Args:
            parameter_name: имя параметра
            new_value: новое значение
            reason: причина изменения
            confidence: уверенность (0-1)
            expected_old_value: ожидаемое старое значение (защита от stale proposal)
            reference_match_id: ID матча, вызвавшего изменение
            group_name: группа параметров
            model_version: версия модели
            category: категория
        
        Returns:
            {
                "success": bool,
                "status": "applied" | "stale_proposal" | "no_change" | "error",
                "parameter_name": str,
                "old_value": float | None,
                "new_value": float,
                "delta": float | None,
                "revision": int,
                "history_id": int | None,
                "message": str | None,
            }
        """
        # Валидация
        try:
            new_value = float(new_value)
        except (TypeError, ValueError):
            return {
                "success": False,
                "status": "error",
                "parameter_name": parameter_name,
                "new_value": new_value,
                "message": f"Invalid new_value: {new_value}"
            }
        
        if confidence < 0 or confidence > 1:
            return {
                "success": False,
                "status": "error",
                "parameter_name": parameter_name,
                "new_value": new_value,
                "message": f"Confidence must be between 0 and 1: {confidence}"
            }
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # ====================================================
            # 1. ПОЛУЧАЕМ ТЕКУЩЕЕ СОСТОЯНИЕ ПАРАМЕТРА
            # ====================================================
            
            cursor.execute("""
                SELECT parameter_value, revision
                FROM model_parameters
                WHERE model_version = ?
                  AND parameter_name = ?
                  AND is_current = 1
            """, (model_version, parameter_name))
            
            current = cursor.fetchone()
            
            old_value = current["parameter_value"] if current else None
            old_revision = current["revision"] if current else 0
            
            # ====================================================
            # 2. ПРОВЕРКА expected_old_value (защита от stale)
            # ====================================================
            
            if expected_old_value is not None:
                try:
                    expected_old_value = float(expected_old_value)
                except (TypeError, ValueError):
                    return {
                        "success": False,
                        "status": "error",
                        "parameter_name": parameter_name,
                        "new_value": new_value,
                        "message": f"Invalid expected_old_value: {expected_old_value}"
                    }
                
                if old_value is None:
                    return {
                        "success": False,
                        "status": "stale_proposal",
                        "parameter_name": parameter_name,
                        "new_value": new_value,
                        "expected_value": expected_old_value,
                        "current_value": None,
                        "message": f"Parameter '{parameter_name}' does not exist"
                    }
                
                if abs(old_value - expected_old_value) > 0.0001:
                    return {
                        "success": False,
                        "status": "stale_proposal",
                        "parameter_name": parameter_name,
                        "new_value": new_value,
                        "expected_value": expected_old_value,
                        "current_value": old_value,
                        "message": f"Stale proposal: expected {expected_old_value}, current {old_value}"
                    }
            
            # ====================================================
            # 3. ПРОВЕРКА: ИЗМЕНИЛОСЬ ЛИ ЗНАЧЕНИЕ?
            # ====================================================
            
            if old_value is not None and abs(old_value - new_value) < 0.0001:
                return {
                    "success": True,
                    "status": "no_change",
                    "parameter_name": parameter_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "delta": 0.0,
                    "revision": old_revision,
                    "history_id": None,
                    "message": "Value unchanged"
                }
            
            # ====================================================
            # 4. ВЫЧИСЛЯЕМ НОВУЮ РЕВИЗИЮ
            # ====================================================
            
            cursor.execute("""
                SELECT COALESCE(MAX(revision), 0) + 1 AS next_rev
                FROM model_parameters
                WHERE model_version = ?
            """, (model_version,))
            
            row = cursor.fetchone()
            new_revision = row["next_rev"] if row else 1
            
            # ====================================================
            # 5. СНИМАЕМ is_current СО СТАРОЙ ЗАПИСИ
            # ====================================================
            
            if current:
                cursor.execute("""
                    UPDATE model_parameters
                    SET is_current = 0
                    WHERE model_version = ?
                      AND parameter_name = ?
                      AND is_current = 1
                """, (model_version, parameter_name))
            
            # ====================================================
            # 6. ВСТАВЛЯЕМ НОВУЮ ЗАПИСЬ
            # ====================================================
            
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO model_parameters (
                    group_name, model_version, category,
                    parameter_name, parameter_value,
                    description, revision, is_current, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                group_name,
                model_version,
                category,
                parameter_name,
                new_value,
                reason,
                new_revision,
                1,
                now,
            ))
            
            # ====================================================
            # 7. ЗАПИСЫВАЕМ ИСТОРИЮ
            # ====================================================
            
            history_id = None
            
            if old_value is not None:
                cursor.execute("""
                    INSERT INTO parameter_history (
                        parameter_name, group_name, model_version,
                        old_value, new_value, delta,
                        reason, confidence,
                        reference_match_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    parameter_name,
                    group_name,
                    model_version,
                    old_value,
                    new_value,
                    new_value - old_value,
                    reason,
                    confidence,
                    reference_match_id,
                    now,
                ))
                
                history_id = cursor.lastrowid
            
            # ====================================================
            # 8. COMMIT
            # ====================================================
            
            conn.commit()
            
            logger.info(
                "PARAMETER APPLIED | %s: %s → %s | revision=%s | history_id=%s",
                parameter_name,
                old_value,
                new_value,
                new_revision,
                history_id,
            )
            
            return {
                "success": True,
                "status": "applied",
                "parameter_name": parameter_name,
                "old_value": old_value,
                "new_value": new_value,
                "delta": new_value - old_value if old_value is not None else None,
                "revision": new_revision,
                "history_id": history_id,
                "message": None,
            }
            
        except Exception as exc:
            conn.rollback()
            logger.exception("apply_parameter_change failed for %s", parameter_name)
            return {
                "success": False,
                "status": "error",
                "parameter_name": parameter_name,
                "new_value": new_value,
                "message": str(exc),
            }
        finally:
            conn.close()

    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET PARAMETER REVISION
    # ============================================================

    def get_parameter_revision(self, model_version: str = "v12.1") -> int:
        """
        Возвращает текущую глобальную ревизию модели.
        
        Args:
            model_version: версия модели
        
        Returns:
            int: максимальный revision из model_parameters или 0
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(MAX(revision), 0) AS max_rev
                FROM model_parameters
                WHERE model_version = ?
            """, (model_version,))
            row = cursor.fetchone()
            return row["max_rev"] if row else 0
        finally:
            conn.close()

    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET PARAMETER HISTORY
    # ============================================================

    def get_parameter_history(
        self,
        parameter_name: str,
        model_version: str = "v12.1",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает историю изменений параметра.
        
        Args:
            parameter_name: имя параметра
            model_version: версия модели
            limit: максимальное количество записей
        
        Returns:
            List[Dict]: список записей parameter_history
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT *
                FROM parameter_history
                WHERE parameter_name = ?
                  AND model_version = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """, (parameter_name, model_version, limit))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET LEARNING MEMORY (С ФИЛЬТРАЦИЕЙ)
    # ============================================================
    
    def get_learning_memory(
        self,
        event_type: Optional[str] = None,
        object_type: Optional[str] = None,
        feature: Optional[str] = None,
        reference_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Read-only чтение learning_memory с полной фильтрацией.
        
        Единственный владелец SQL-схемы: database.py
        
        APPEND-ONLY: метод ничего не изменяет.
        
        Args:
            event_type: фильтр по типу события
            object_type: фильтр по объекту (например, "match:123")
            feature: фильтр по признаку
            reference_id: фильтр по reference_id
            limit: максимальное количество записей (по умолчанию 100)
        
        Returns:
            Список словарей с полями learning_memory
        """
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        
        if limit <= 0:
            return []
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []
            
            if event_type is not None:
                conditions.append("event_type = ?")
                params.append(event_type)
            
            if object_type is not None:
                conditions.append("object = ?")
                params.append(object_type)
            
            if feature is not None:
                conditions.append("feature = ?")
                params.append(feature)
            
            if reference_id is not None:
                conditions.append("reference_id = ?")
                params.append(int(reference_id))
            
            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT *
                FROM learning_memory
                {where}
                ORDER BY
                    datetime(created_at) DESC,
                    id DESC
                LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД P0: GET LEARNING MEMORY COUNT
    # ============================================================
    
    def get_learning_memory_count(
        self,
        event_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Быстрая read-only проверка количества записей learning_memory.
        
        Используется прежде всего для processed-state / idempotency.
        
        Args:
            event_type: фильтр по типу события
            reference_id: фильтр по reference_id
        
        Returns:
            Количество записей, удовлетворяющих фильтру
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []
            
            if event_type is not None:
                conditions.append("event_type = ?")
                params.append(event_type)
            
            if reference_id is not None:
                conditions.append("reference_id = ?")
                params.append(int(reference_id))
            
            where = ""
            if conditions:
                where = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT COUNT(*) AS count
                FROM learning_memory
                {where}
            """
            
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            if row is None:
                return 0
            return int(row["count"])
        finally:
            conn.close()
    
    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: ADD LEARNING MEMORY — APPEND-ONLY
    # ============================================================
    
    def add_learning_memory(self, data: Dict[str, Any]) -> int:
        """
        APPEND-ONLY запись события ETC в таблицу learning_memory.
        
        ВАЖНО:
            - только INSERT;
            - UPDATE отсутствует;
            - DELETE отсутствует;
            - существующая память не изменяется.
        
        Args:
            data: словарь с полями learning_memory
                - event_type: str
                - object: str
                - feature: str
                - before_value: Any (будет преобразован в TEXT)
                - after_value: Any (будет преобразован в TEXT)
                - delta: Any (будет преобразован в TEXT)
                - reason: str
                - confidence: float
                - impact: float
                - algorithm: str
                - model_version: str
                - reference_id: int
                - created_at: str (ISO формат)
        
        Returns:
            int: ID созданной записи
        
        Raises:
            RuntimeError: при ошибке INSERT
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Преобразуем значения в строки для TEXT полей
            def to_text(value: Any) -> Optional[str]:
                if value is None:
                    return None
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
                return str(value)
            
            cursor.execute(
                """
                INSERT INTO learning_memory (
                    event_type,
                    object,
                    feature,
                    before_value,
                    after_value,
                    delta,
                    reason,
                    confidence,
                    impact,
                    algorithm,
                    model_version,
                    reference_id,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    data.get("event_type"),
                    data.get("object"),
                    data.get("feature"),
                    to_text(data.get("before_value")),
                    to_text(data.get("after_value")),
                    to_text(data.get("delta")),
                    data.get("reason"),
                    data.get("confidence", 1.0),
                    data.get("impact", 1.0),
                    data.get("algorithm", "ETC"),
                    data.get("model_version", "v12.1"),
                    data.get("reference_id"),
                    data.get("created_at"),
                ),
            )
            
            memory_id = cursor.lastrowid
            if memory_id is None:
                raise RuntimeError(
                    "Не удалось получить ID learning_memory."
                )
            
            conn.commit()
            logger.info(
                "LEARNING MEMORY APPEND | id=%s | event=%s | object=%s",
                memory_id,
                data.get("event_type"),
                data.get("object"),
            )
            return int(memory_id)
            
        except Exception as exc:
            conn.rollback()
            logger.error(
                "Ошибка добавления learning_memory: %s",
                exc
            )
            raise RuntimeError(
                f"Ошибка добавления learning_memory: {exc}"
            ) from exc
        finally:
            conn.close()
    
    # ============================================================
    # UNLOCK GOLD FOR MATCH — НОВЫЙ МЕТОД
    # ============================================================
    
    def unlock_gold_for_match(self, match_id: int) -> bool:
        """
        Снимает LOCK с GOLD-записи конкретного матча.
        
        Используется ТОЛЬКО для восстановления/дозаполнения
        фактической статистики и xG.
        
        ВАЖНО:
            - счёт не удаляется;
            - матч не удаляется;
            - существующие факты не удаляются;
            - GOLD запись не удаляется;
            - после повторного сохранения факта GOLD снова блокируется.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Снимаем LOCK с gold_dataset
            cursor.execute("""
                UPDATE gold_dataset
                SET locked = 0, status = 'pending'
                WHERE match_id = ?
                  AND locked = 1
            """, (match_id,))
            
            conn.commit()
            
            if cursor.rowcount == 0:
                logger.debug(
                    "GOLD ALREADY UNLOCKED | match_id=%s",
                    match_id
                )
            else:
                logger.info(
                    "GOLD UNLOCKED | match_id=%s",
                    match_id
                )
            
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(
                "Unlock GOLD error | match_id=%s | %s",
                match_id,
                e
            )
            return False
        finally:
            conn.close()


    # ============================================================
    # 🆕 НОВЫЙ МЕТОД: GET TEAM RECENT CONTEXT (FAJ FINAL SCORE)
    # ============================================================

    def get_team_recent_context(
        self,
        team_id: int,
        season_id: int,
        match_date: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Возвращает контекст команды для FAJ Final Score Engine.

        ВАЖНО:
            - Только матчи ДО match_date (без утечки будущего)
            - ORDER BY match_date DESC
            - Возвращает rating, passport, last_match, recent_matches
            - Отмечает availability каждого компонента

        Args:
            team_id: ID команды
            season_id: ID сезона
            match_date: Дата прогнозируемого матча (ISO формат)
            limit: Максимум матчей в recent_matches

        Returns:
            {
                "team_id": int,
                "season_id": int,
                "rating": float | None,
                "passport": dict | None,
                "base": dict | None,
                "last_match": dict | None,
                "recent_matches": list,
                "form": dict | None,
                "availability": {
                    "rating": bool,
                    "passport": bool,
                    "base": bool,
                    "last_match": bool,
                    "recent_matches": bool,
                }
            }
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            result = {
                "team_id": team_id,
                "season_id": season_id,
                "rating": None,
                "passport": None,
                "base": None,
                "last_match": None,
                "recent_matches": [],
                "form": None,
                "availability": {
                    "rating": False,
                    "passport": False,
                    "base": False,
                    "last_match": False,
                    "recent_matches": False,
                }
            }

            # ====================================================
            # 1. PASSPORT + RATING
            # ====================================================
            passport = self.get_team_passport(team_id, season_id)
            if passport:
                result["passport"] = dict(passport)
                result["availability"]["passport"] = True

                rating = passport.get("faj_rating")
                if rating is not None:
                    try:
                        result["rating"] = float(rating)
                        result["availability"]["rating"] = True
                    except (TypeError, ValueError):
                        pass

            # ====================================================
            # 2. BASE (home_advantage)
            # ====================================================
            base = self.get_base(team_id, season_id)
            if base:
                result["base"] = dict(base)
                result["availability"]["base"] = True

            # ====================================================
            # 3. MATCH HISTORY (только матчи ДО match_date)
            # ====================================================
            cursor.execute("""
                SELECT
                    m.id,
                    m.home_team_id,
                    m.away_team_id,
                    m.date,
                    m.actual_home,
                    m.actual_away,
                    m.home_xg,
                    m.away_xg,
                    m.competition,
                    ht.name AS home_team_name,
                    at.name AS away_team_name
                FROM matches m
                LEFT JOIN teams ht ON ht.id = m.home_team_id
                LEFT JOIN teams at ON at.id = m.away_team_id
                WHERE (
                    m.home_team_id = ? OR m.away_team_id = ?
                )
                AND m.status = 'finished'
                AND m.actual_home IS NOT NULL
                AND m.actual_away IS NOT NULL
                AND datetime(m.date) < datetime(?)
                ORDER BY datetime(m.date) DESC
                LIMIT ?
            """, (team_id, team_id, match_date, limit + 1))

            rows = cursor.fetchall()
            rows = [dict(row) for row in rows]

            # ====================================================
            # 4. LAST MATCH (самый свежий)
            # ====================================================
            if rows:
                first = rows[0]
                is_home = first["home_team_id"] == team_id
                goals_for = first["actual_home"] if is_home else first["actual_away"]
                goals_against = first["actual_away"] if is_home else first["actual_home"]

                if goals_for is not None and goals_against is not None:
                    if goals_for > goals_against:
                        result_type = "WIN"
                    elif goals_for == goals_against:
                        result_type = "DRAW"
                    else:
                        result_type = "LOSS"

                    result["last_match"] = {
                        "match_id": first["id"],
                        "opponent_id": first["away_team_id"] if is_home else first["home_team_id"],
                        "opponent_name": first["away_team_name"] if is_home else first["home_team_name"],
                        "goals_for": goals_for,
                        "goals_against": goals_against,
                        "result": result_type,
                        "match_date": first["date"],
                        "is_home": is_home,
                        "xg_for": first["home_xg"] if is_home else first["away_xg"],
                        "xg_against": first["away_xg"] if is_home else first["home_xg"],
                    }
                    result["availability"]["last_match"] = True

                # ====================================================
                # 5. RECENT MATCHES (до limit)
                # ====================================================
                recent = []
                for row in rows[:limit]:
                    is_home = row["home_team_id"] == team_id
                    goals_for = row["actual_home"] if is_home else row["actual_away"]
                    goals_against = row["actual_away"] if is_home else row["actual_home"]

                    if goals_for is not None and goals_against is not None:
                        if goals_for > goals_against:
                            result_type = "WIN"
                        elif goals_for == goals_against:
                            result_type = "DRAW"
                        else:
                            result_type = "LOSS"

                        recent.append({
                            "match_id": row["id"],
                            "opponent_id": row["away_team_id"] if is_home else row["home_team_id"],
                            "opponent_name": row["away_team_name"] if is_home else row["home_team_name"],
                            "goals_for": goals_for,
                            "goals_against": goals_against,
                            "result": result_type,
                            "match_date": row["date"],
                            "is_home": is_home,
                            "xg_for": row["home_xg"] if is_home else row["away_xg"],
                            "xg_against": row["away_xg"] if is_home else row["home_xg"],
                        })

                result["recent_matches"] = recent
                if recent:
                    result["availability"]["recent_matches"] = True

            # ====================================================
            # 6. FORM (из recent_matches)
            # ====================================================
            if result["availability"]["recent_matches"]:
                recent = result["recent_matches"]
                points = 0
                goals_scored = 0
                goals_conceded = 0
                xg_sum = 0.0
                xga_sum = 0.0

                for match in recent:
                    if match["result"] == "WIN":
                        points += 3
                    elif match["result"] == "DRAW":
                        points += 1
                    goals_scored += match["goals_for"]
                    goals_conceded += match["goals_against"]
                    if match.get("xg_for") is not None:
                        xg_sum += match["xg_for"]
                    if match.get("xg_against") is not None:
                        xga_sum += match["xg_against"]

                result["form"] = {
                    "points": points,
                    "goals_scored": goals_scored,
                    "goals_conceded": goals_conceded,
                    "matches": len(recent),
                    "xg_sum": round(xg_sum, 2),
                    "xga_sum": round(xga_sum, 2),
                    "goal_difference": goals_scored - goals_conceded,
                }

            return result

        except Exception as e:
            logger.error(f"get_team_recent_context error: {e}")
            return {
                "team_id": team_id,
                "season_id": season_id,
                "rating": None,
                "passport": None,
                "base": None,
                "last_match": None,
                "recent_matches": [],
                "form": None,
                "availability": {
                    "rating": False,
                    "passport": False,
                    "base": False,
                    "last_match": False,
                    "recent_matches": False,
                },
                "error": str(e)
            }
        finally:
            conn.close()


# ============================================================
# ════════════════════════════════════════════════════════════
# ЭТАП 2: ТРАНЗАКЦИОННЫЕ МЕТОДЫ (TX)
# ════════════════════════════════════════════════════════════
# ============================================================

    # ============================================================
    # ВНУТРЕННИЕ МЕТОДЫ ДЛЯ ТРАНЗАКЦИЙ (TX)
    # ============================================================

    def _update_result_tx(
        self,
        cursor: sqlite3.Cursor,
        match_id: int,
        home_goals: int,
        away_goals: int,
    ) -> None:
        """
        Внутренний метод для сохранения счёта в транзакции.
        
        ПРЕДУСЛОВИЯ:
            - Проверка LOCK выполнена ДО вызова
            - cursor активен в открытой транзакции
        """
        # Проверяем, существует ли уже запись
        cursor.execute("""
            SELECT id, fact_status FROM match_results
            WHERE match_id = ?
        """, (match_id,))
        existing = cursor.fetchone()
        
        if existing and existing["fact_status"] == "locked":
            raise ValueError(f"Match {match_id} is LOCKED. Cannot update result.")
        
        if existing:
            cursor.execute("""
                UPDATE match_results
                SET home_goals = ?, away_goals = ?,
                    fact_status = 'verified'
                WHERE match_id = ?
            """, (home_goals, away_goals, match_id))
        else:
            cursor.execute("""
                INSERT INTO match_results (
                    match_id, home_goals, away_goals,
                    fact_status
                ) VALUES (?, ?, ?, ?)
            """, (match_id, home_goals, away_goals, "verified"))
        
        # Обновляем matches для обратной совместимости
        cursor.execute("""
            UPDATE matches
            SET actual_home = ?, actual_away = ?,
                status = 'finished',
                fact_status = 'verified',
                updated_at = ?
            WHERE id = ?
        """, (home_goals, away_goals, datetime.now().isoformat(), match_id))
        
        if cursor.rowcount == 0:
            raise ValueError(f"Match {match_id} not found")

    def _update_match_stats_tx(
        self,
        cursor: sqlite3.Cursor,
        match_id: int,
        stats: Dict[str, Any],
    ) -> None:
        """
        Внутренний метод для сохранения статистики в транзакции.
        
        ПРЕДУСЛОВИЯ:
            - Проверка LOCK выполнена ДО вызова
            - cursor активен в открытой транзакции
        """
        # Получаем команды
        cursor.execute("""
            SELECT home_team_id, away_team_id
            FROM matches
            WHERE id = ?
        """, (match_id,))
        match_row = cursor.fetchone()
        if not match_row:
            raise ValueError(f"Match {match_id} not found")
        
        home_team_id = match_row["home_team_id"]
        away_team_id = match_row["away_team_id"]
        
        # Обновляем matches
        cursor.execute("""
            UPDATE matches SET
                home_xg = ?,
                away_xg = ?,
                home_possession = ?,
                away_possession = ?,
                home_shots = ?,
                away_shots = ?,
                home_shots_on_target = ?,
                away_shots_on_target = ?,
                parser_source = ?,
                parser_version = ?,
                data_quality = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            stats.get("home_xg"),
            stats.get("away_xg"),
            stats.get("home_possession"),
            stats.get("away_possession"),
            stats.get("home_shots"),
            stats.get("away_shots"),
            stats.get("home_shots_on_target"),
            stats.get("away_shots_on_target"),
            stats.get("parser_source"),
            stats.get("parser_version"),
            stats.get("data_quality", 1.0),
            datetime.now().isoformat(),
            match_id
        ))
        
        # Сохраняем статистику команд
        def upsert_team_stats(team_id, prefix):
            cursor.execute("""
                INSERT INTO match_statistics (
                    match_id, team_id,
                    possession, shots, shots_on_target,
                    corners, fouls, yellow_cards, red_cards,
                    xg, passes, accurate_passes, pass_accuracy, tackles
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id, team_id)
                DO UPDATE SET
                    possession = excluded.possession,
                    shots = excluded.shots,
                    shots_on_target = excluded.shots_on_target,
                    corners = excluded.corners,
                    fouls = excluded.fouls,
                    yellow_cards = excluded.yellow_cards,
                    red_cards = excluded.red_cards,
                    xg = excluded.xg,
                    passes = excluded.passes,
                    accurate_passes = excluded.accurate_passes,
                    pass_accuracy = excluded.pass_accuracy,
                    tackles = excluded.tackles
            """, (
                match_id, team_id,
                stats.get(f"{prefix}_possession"),
                stats.get(f"{prefix}_shots"),
                stats.get(f"{prefix}_shots_on_target"),
                stats.get(f"{prefix}_corners"),
                stats.get(f"{prefix}_fouls"),
                stats.get(f"{prefix}_yellow_cards"),
                stats.get(f"{prefix}_red_cards"),
                stats.get(f"{prefix}_xg"),
                stats.get(f"{prefix}_total_passes"),
                stats.get(f"{prefix}_accurate_passes"),
                stats.get(f"{prefix}_pass_accuracy"),
                stats.get(f"{prefix}_tackles"),
            ))
        
        upsert_team_stats(home_team_id, "home")
        upsert_team_stats(away_team_id, "away")

    def _save_expert_prediction_tx(
        self,
        cursor: sqlite3.Cursor,
        match_id: int,
        expert_name: str,
        score: str,
        comment: str = "",
        confidence: int = 50,
    ) -> None:
        """Внутренний метод для сохранения экспертного прогноза в транзакции."""
        cursor.execute("""
            INSERT INTO expert_predictions (
                match_id, expert_name, score, comment, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            match_id, expert_name, score, comment, confidence,
            datetime.now().isoformat()
        ))

    def _add_prediction_validation_tx(
        self,
        cursor: sqlite3.Cursor,
        data: Dict[str, Any],
    ) -> Optional[int]:
        """Внутренний метод для сохранения валидации в транзакции."""
        
        validation_hash = data.get('validation_hash')
        if not validation_hash:
            hash_str = f"{data.get('match_id')}_{data.get('prediction_id')}_{data.get('actual_score')}"
            validation_hash = hashlib.md5(hash_str.encode()).hexdigest()
        
        # Проверяем дубли
        cursor.execute("""
            SELECT id FROM prediction_validation
            WHERE validation_hash = ?
            LIMIT 1
        """, (validation_hash,))
        existing = cursor.fetchone()
        if existing:
            return existing["id"]
        
        cursor.execute("""
            INSERT INTO prediction_validation (
                match_id, prediction_id, match_prediction_id,
                validation_hash,
                predicted_score, actual_score,
                predicted_home_xg, actual_home_xg,
                predicted_away_xg, actual_away_xg,
                predicted_winner, actual_winner,
                predicted_probability_home,
                predicted_probability_draw,
                predicted_probability_away,
                score_probability, confidence, risk,
                predicted_btts, actual_btts,
                predicted_over25, actual_over25,
                model_version, passport_version, parser_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('match_id'),
            data.get('prediction_id'),
            data.get('match_prediction_id'),
            validation_hash,
            data.get('predicted_score'),
            data.get('actual_score'),
            data.get('predicted_home_xg'),
            data.get('actual_home_xg'),
            data.get('predicted_away_xg'),
            data.get('actual_away_xg'),
            data.get('predicted_winner'),
            data.get('actual_winner'),
            data.get('predicted_probability_home'),
            data.get('predicted_probability_draw'),
            data.get('predicted_probability_away'),
            data.get('score_probability'),
            data.get('confidence'),
            data.get('risk'),
            data.get('predicted_btts'),
            data.get('actual_btts'),
            data.get('predicted_over25'),
            data.get('actual_over25'),
            data.get('model_version'),
            data.get('passport_version'),
            data.get('parser_version')
        ))
        return cursor.lastrowid

    def _upsert_gold_tx(
        self,
        cursor: sqlite3.Cursor,
        data: Dict[str, Any],
    ) -> int:
        """Внутренний метод для сохранения Gold в транзакции."""
        
        # Проверяем LOCK
        cursor.execute("""
            SELECT id, locked FROM gold_dataset
            WHERE match_id = ?
        """, (data.get('match_id'),))
        existing = cursor.fetchone()
        
        if existing and existing["locked"] == 1:
            raise ValueError(f"Gold record for match {data.get('match_id')} is LOCKED")
        
        if existing:
            gold_id = existing["id"]
            cursor.execute("""
                UPDATE gold_dataset SET
                    actual_score = COALESCE(?, actual_score),
                    actual_xg_home = COALESCE(?, actual_xg_home),
                    actual_xg_away = COALESCE(?, actual_xg_away),
                    actual_btts = COALESCE(?, actual_btts),
                    actual_total_25 = COALESCE(?, actual_total_25),
                    actual_total_35 = COALESCE(?, actual_total_35),
                    actual_home_goals = COALESCE(?, actual_home_goals),
                    actual_away_goals = COALESCE(?, actual_away_goals),
                    status = COALESCE(?, status),
                    expert_score = COALESCE(?, expert_score),
                    expert_reasoning = COALESCE(?, expert_reasoning),
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get('actual_score'),
                data.get('actual_xg_home'),
                data.get('actual_xg_away'),
                data.get('actual_btts'),
                data.get('actual_total_25'),
                data.get('actual_total_35'),
                data.get('actual_home_goals'),
                data.get('actual_away_goals'),
                data.get('status'),
                data.get('expert_score'),
                data.get('expert_reasoning'),
                datetime.now().isoformat(),
                gold_id
            ))
            return gold_id
        else:
            cursor.execute("""
                INSERT INTO gold_dataset (
                    match_id, home_team, away_team, match_date,
                    model_version,
                    faj_score, faj_xg_home, faj_xg_away,
                    faj_btts, faj_total_25, faj_total_35,
                    faj_confidence, faj_rating_home, faj_rating_away,
                    faj_pir_home, faj_pir_away,
                    faj_style_home, faj_style_away,
                    expert_score, expert_reasoning,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('match_id'),
                data.get('home_team'),
                data.get('away_team'),
                data.get('match_date'),
                data.get('model_version', '1.0'),
                data.get('faj_score'),
                data.get('faj_xg_home'),
                data.get('faj_xg_away'),
                data.get('faj_btts'),
                data.get('faj_total_25'),
                data.get('faj_total_35'),
                data.get('faj_confidence'),
                data.get('faj_rating_home'),
                data.get('faj_rating_away'),
                data.get('faj_pir_home'),
                data.get('faj_pir_away'),
                data.get('faj_style_home'),
                data.get('faj_style_away'),
                data.get('expert_score'),
                data.get('expert_reasoning'),
                data.get('status', 'pending'),
                datetime.now().isoformat()
            ))
            return cursor.lastrowid

    def _lock_gold_tx(
        self,
        cursor: sqlite3.Cursor,
        gold_id: int,
    ) -> None:
        """Внутренний метод для блокировки Gold в транзакции."""
        cursor.execute("""
            UPDATE gold_dataset
            SET locked = 1, locked_at = ?, status = 'completed'
            WHERE id = ? AND locked = 0
        """, (datetime.now().isoformat(), gold_id))
        
        if cursor.rowcount == 0:
            # Проверяем, существует ли запись
            cursor.execute("""
                SELECT id, locked FROM gold_dataset
                WHERE id = ?
            """, (gold_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Gold record {gold_id} not found")
            if row["locked"] == 1:
                return  # уже locked
            raise ValueError(f"Gold record {gold_id} could not be locked")

    def _lock_match_result_tx(
        self,
        cursor: sqlite3.Cursor,
        match_id: int,
    ) -> None:
        """
        Внутренний метод для блокировки результата матча в транзакции.
        
        ТРЕБОВАНИЯ:
            - Проверка LOCK выполнена ДО вызова
            - Если запись отсутствует → ошибка
            - Если уже locked → ошибка (нарушение контракта)
            - Если locked успешно → OK
        """
        # Проверяем, что запись существует и не locked
        cursor.execute("""
            SELECT fact_status FROM match_results
            WHERE match_id = ?
        """, (match_id,))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Match result for match_id={match_id} not found")
        
        if row["fact_status"] == "locked":
            raise ValueError(f"Match {match_id} is already LOCKED")
        
        # Устанавливаем LOCK
        cursor.execute("""
            UPDATE match_results
            SET fact_status = 'locked', locked_at = ?, locked_by = ?
            WHERE match_id = ? AND fact_status != 'locked'
        """, (datetime.now().isoformat(), "FAJ", match_id))
        
        if cursor.rowcount == 0:
            raise ValueError(f"Failed to lock match {match_id}")
        
        # Обновляем matches
        cursor.execute("""
            UPDATE matches
            SET fact_status = 'locked', updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), match_id))

    # ============================================================
    # ПУБЛИЧНЫЙ МЕТОД: АТОМАРНОЕ СОХРАНЕНИЕ ФАКТА
    # ============================================================

    def save_complete_match_fact(
        self,
        match_id: int,
        home_goals: int,
        away_goals: int,
        stats: Dict[str, Any],
        expert_data: Optional[Dict[str, Any]] = None,
        validation_data: Optional[Dict[str, Any]] = None,
        gold_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        АТОМАРНОЕ сохранение всех фактов матча.
        
        ОДНА ТРАНЗАКЦИЯ.
        
        При любой ошибке → ROLLBACK → ничего не сохраняется.
        
        КРИТИЧЕСКИЙ ИНВАРИАНТ:
            LOCKED → отказ
            UNLOCKED → save_complete_match_fact()
                ↓
            ┌─────────────────────────────┐
            │ result                      │
            │ statistics                  │
            │ expert                      │
            │ validation                  │
            │ gold                        │
            │ gold LOCK                   │
            │ match LOCK                  │
            └─────────────────────────────┘
                ↓
            COMMIT → всё сохранено
                │
                └─── ошибка на любом шаге → ROLLBACK → 0 изменений
        
        Args:
            match_id: ID матча
            home_goals: голы домашней команды
            away_goals: голы гостевой команды
            stats: статистика матча (словарь с полями)
            expert_data: данные эксперта (опционально)
            validation_data: данные валидации (опционально)
            gold_data: данные Gold (опционально)
        
        Returns:
            Dict с результатами
        
        Raises:
            ValueError: при LOCK-ошибке или отсутствии данных
        """
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # ====================================================
            # 1. ПРОВЕРКА LOCK
            # ====================================================
            cursor.execute("""
                SELECT fact_status FROM match_results
                WHERE match_id = ?
            """, (match_id,))
            row = cursor.fetchone()
            if row and row["fact_status"] == "locked":
                raise ValueError(f"Match {match_id} is LOCKED. Cannot update facts.")
            
            # ====================================================
            # 2. СОХРАНЯЕМ СЧЁТ
            # ====================================================
            self._update_result_tx(cursor, match_id, home_goals, away_goals)
            
            # ====================================================
            # 3. СОХРАНЯЕМ СТАТИСТИКУ
            # ====================================================
            self._update_match_stats_tx(cursor, match_id, stats)
            
            # ====================================================
            # 4. СОХРАНЯЕМ ЭКСПЕРТА
            # ====================================================
            if expert_data:
                self._save_expert_prediction_tx(
                    cursor,
                    match_id,
                    expert_data.get("expert_name", "Директор"),
                    expert_data.get("score", ""),
                    expert_data.get("comment", ""),
                    expert_data.get("confidence", 50),
                )
            
            # ====================================================
            # 5. СОХРАНЯЕМ ВАЛИДАЦИЮ (КОПИЯ ЧТОБЫ НЕ МУТИРОВАТЬ)
            # ====================================================
            validation_id = None
            if validation_data:
                validation_payload = {
                    **validation_data,
                    "match_id": match_id,
                }
                validation_id = self._add_prediction_validation_tx(
                    cursor,
                    validation_payload
                )
            
            # ====================================================
            # 6. СОХРАНЯЕМ GOLD (КОПИЯ ЧТОБЫ НЕ МУТИРОВАТЬ)
            # ====================================================
            gold_id = None
            if gold_data:
                gold_payload = {
                    **gold_data,
                    "match_id": match_id,
                }
                gold_id = self._upsert_gold_tx(cursor, gold_payload)
            
            # ====================================================
            # 7. LOCK GOLD
            # ====================================================
            if gold_id is not None:
                self._lock_gold_tx(cursor, gold_id)
            
            # ====================================================
            # 8. LOCK MATCH
            # ====================================================
            self._lock_match_result_tx(cursor, match_id)
            
            # ====================================================
            # 9. COMMIT
            # ====================================================
            conn.commit()
            
            logger.info(
                "MATCH FACT SAVED ATOMICALLY | "
                "match_id=%s | "
                "home=%s | away=%s | "
                "validation_id=%s | gold_id=%s",
                match_id,
                home_goals,
                away_goals,
                validation_id,
                gold_id,
            )
            
            return {
                "status": "saved",
                "match_id": match_id,
                "validation_id": validation_id,
                "gold_id": gold_id,
            }
            
        except Exception as exc:
            conn.rollback()
            logger.exception(
                "MATCH FACT SAVE FAILED | "
                "match_id=%s | error=%s",
                match_id,
                exc,
            )
            raise
            
        finally:
            conn.close()


# ============================================================
# ════════════════════════════════════════════════════════════
# ЭТАП 3: TX-МЕТОДЫ ДЛЯ РЕЙТИНГА И PROCESSING
# ════════════════════════════════════════════════════════════
# ============================================================

    # ============================================================
    # ВНУТРЕННИЕ TX-МЕТОДЫ ДЛЯ РЕЙТИНГА И PROCESSING
    # ============================================================

    def _add_learning_memory_tx(
        self,
        cursor: sqlite3.Cursor,
        data: Dict[str, Any],
    ) -> int:
        """
        Внутренний TX-метод для вставки learning_memory.
        
        КОПИРУЕТ КОНТРАКТ add_learning_memory():
            - те же поля
            - та же сериализация
            - НО: НЕТ COMMIT
        
        COMMIT принадлежит внешней транзакции.
        """
        def to_text(value: Any) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        
        cursor.execute("""
            INSERT INTO learning_memory (
                event_type,
                object,
                feature,
                before_value,
                after_value,
                delta,
                reason,
                confidence,
                impact,
                algorithm,
                model_version,
                reference_id,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            data.get("event_type"),
            data.get("object"),
            data.get("feature"),
            to_text(data.get("before_value")),
            to_text(data.get("after_value")),
            to_text(data.get("delta")),
            data.get("reason"),
            data.get("confidence", 1.0),
            data.get("impact", 1.0),
            data.get("algorithm", "ETC"),
            data.get("model_version", "v12.1"),
            data.get("reference_id"),
            data.get("created_at"),
        ))
        
        memory_id = cursor.lastrowid
        if memory_id is None:
            raise RuntimeError("Не удалось получить ID learning_memory.")
        
        return int(memory_id)

    def _record_match_processing_tx(
        self,
        cursor: sqlite3.Cursor,
        match_id: int,
        reason: str = "Матч успешно обработан ETC Learning Engine",
        algorithm: str = "ETC.LearningEngine",
        model_version: str = "v12.1",
    ) -> int:
        """
        Внутренний TX-метод для создания batch_learning marker.
        
        КОПИРУЕТ КОНТРАКТ LearningMemory.record_batch_learning():
            event_type = "batch_learning"
            object = "match:<match_id>"
            reference_id = match_id
        
        НО: НЕТ COMMIT
        
        COMMIT принадлежит внешней транзакции.
        """
        safe_match_id = int(match_id)
        if safe_match_id <= 0:
            raise ValueError("match_id должен быть положительным integer")
        
        data = {
            "event_type": "batch_learning",
            "object": f"match:{safe_match_id}",
            "feature": "etc_batch_processed",
            "before_value": None,
            "after_value": "processed",
            "delta": None,
            "reason": reason,
            "confidence": 1.0,
            "impact": 0.0,
            "algorithm": algorithm,
            "model_version": model_version,
            "reference_id": safe_match_id,
            "created_at": datetime.now().isoformat(),
        }
        
        return self._add_learning_memory_tx(cursor, data)

    def _update_team_rating_tx(
        self,
        cursor: sqlite3.Cursor,
        team_id: int,
        season_id: int,
        new_rating: float,
        old_rating: float,
    ) -> None:
        """
        Внутренний TX-метод для обновления faj_rating в team_passports.
        
        ТРЕБОВАНИЯ:
            - паспорт существует
            - team_id + season_id соответствуют записи
            - старый faj_rating соответствует old_rating (защита от конкурентных изменений)
            - UPDATE действительно изменил одну запись
        
        Если rowcount != 1 → ошибка → ROLLBACK.
        """
        cursor.execute("""
            UPDATE team_passports
            SET faj_rating = ?,
                updated_at = ?
            WHERE team_id = ?
              AND season_id = ?
              AND faj_rating = ?
        """, (
            new_rating,
            datetime.now().isoformat(),
            team_id,
            season_id,
            old_rating,
        ))
        
        if cursor.rowcount != 1:
            # Проверяем, существует ли паспорт
            cursor.execute("""
                SELECT id, faj_rating FROM team_passports
                WHERE team_id = ? AND season_id = ?
            """, (team_id, season_id))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Passport not found for team_id={team_id}, season_id={season_id}")
            raise ValueError(
                f"Rating mismatch for team_id={team_id}, season_id={season_id}: "
                f"expected {old_rating}, actual {row['faj_rating']}"
            )

    def _record_team_rating_history_tx(
        self,
        cursor: sqlite3.Cursor,
        team_id: int,
        season_id: int,
        match_id: int,
        old_rating: float,
        new_rating: float,
        delta: float,
        reason: str,
        source: str = "ClubRatingUpdater",
    ) -> int:
        """
        Внутренний TX-метод для записи истории изменения рейтинга.
        
        APPEND-ONLY.
        DELETE/UPDATE существующей истории запрещены.
        """
        cursor.execute("""
            INSERT INTO team_history (
                team_id,
                season_id,
                field,
                old_value,
                new_value,
                reason,
                source,
                reference_match_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            team_id,
            season_id,
            "faj_rating",
            str(old_rating),
            str(new_rating),
            reason,
            source,
            match_id,
            datetime.now().isoformat(),
        ))
        
        return cursor.lastrowid

    def _is_match_fully_processed(
        self,
        match_id: int,
    ) -> bool:
        """
        Проверяет, обработан ли матч полностью.
        
        Условия:
            1. Есть batch_learning marker
            2. Есть rating history для home
            3. Есть rating history для away
        
        Только при наличии ВСЕХ трёх условий матч считается processed.
        
        Используется ДО начала транзакции для быстрой проверки.
        Внутри транзакции дополнительная защита через rowcount.
        """
        safe_match_id = int(match_id)
        if safe_match_id <= 0:
            return False
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Проверяем batch_learning marker
            cursor.execute("""
                SELECT id FROM learning_memory
                WHERE event_type = 'batch_learning'
                  AND reference_id = ?
                LIMIT 1
            """, (safe_match_id,))
            if not cursor.fetchone():
                return False
            
            # 2. Получаем home_team_id и away_team_id
            cursor.execute("""
                SELECT home_team_id, away_team_id, season_id
                FROM matches
                WHERE id = ?
            """, (safe_match_id,))
            match_row = cursor.fetchone()
            if not match_row:
                return False
            
            home_team_id = match_row["home_team_id"]
            away_team_id = match_row["away_team_id"]
            season_id = match_row["season_id"]
            
            # 3. Проверяем rating history для home
            cursor.execute("""
                SELECT id FROM team_history
                WHERE team_id = ?
                  AND season_id = ?
                  AND field = 'faj_rating'
                  AND reference_match_id = ?
                LIMIT 1
            """, (home_team_id, season_id, safe_match_id))
            if not cursor.fetchone():
                return False
            
            # 4. Проверяем rating history для away
            cursor.execute("""
                SELECT id FROM team_history
                WHERE team_id = ?
                  AND season_id = ?
                  AND field = 'faj_rating'
                  AND reference_match_id = ?
                LIMIT 1
            """, (away_team_id, season_id, safe_match_id))
            if not cursor.fetchone():
                return False
            
            return True
            
        finally:
            conn.close()

    # ============================================================
    # ПУБЛИЧНЫЙ МЕТОД: АТОМАРНАЯ ОБРАБОТКА МАТЧА + РЕЙТИНГ
    # ============================================================

    def process_match_with_rating(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        season_id: int,
        home_goals: int,
        away_goals: int,
        home_rating_before: float,
        away_rating_before: float,
        home_rating_after: float,
        away_rating_after: float,
        home_delta: float,
        away_delta: float,
        home_reason: str,
        away_reason: str,
        analysis_memory_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        АТОМАРНАЯ обработка матча ETC + обновление рейтинга.
        
        ОДНА ТРАНЗАКЦИЯ.
        
        При любой ошибке → ROLLBACK → матч не processed.
        
        ПОРЯДОК:
            1. Проверка FULLY PROCESSED (до транзакции)
            2. BEGIN
            3. Проверка processed (внутри транзакции)
            4. Analysis memory (если есть)
            5. Обновление рейтинга home
            6. Обновление рейтинга away
            7. История рейтинга home
            8. История рейтинга away
            9. batch_learning marker
            10. COMMIT
        
        Returns:
            {
                "status": "processed" | "already_processed",
                "match_id": match_id,
                "home": {"old": float, "new": float, "delta": float},
                "away": {"old": float, "new": float, "delta": float},
                "history_ids": [int, int],
                "marker_id": int,
            }
        """
        
        # ====================================================
        # 0. ПРОВЕРКА ДО ТРАНЗАКЦИИ
        # ====================================================
        if self._is_match_fully_processed(match_id):
            logger.info(f"Match {match_id} is already fully processed")
            return {
                "status": "already_processed",
                "match_id": match_id,
            }
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # ====================================================
            # 1. ПРОВЕРКА FULLY PROCESSED ВНУТРИ ТРАНЗАКЦИИ
            # ====================================================
            # Проверяем batch_learning marker
            cursor.execute("""
                SELECT id FROM learning_memory
                WHERE event_type = 'batch_learning'
                  AND reference_id = ?
                LIMIT 1
            """, (match_id,))
            if cursor.fetchone():
                raise RuntimeError(f"Match {match_id} already has batch_learning marker")
            
            # Проверяем rating history для home
            cursor.execute("""
                SELECT id FROM team_history
                WHERE team_id = ?
                  AND season_id = ?
                  AND field = 'faj_rating'
                  AND reference_match_id = ?
                LIMIT 1
            """, (home_team_id, season_id, match_id))
            if cursor.fetchone():
                raise RuntimeError(f"Match {match_id} already has rating history for home")
            
            # Проверяем rating history для away
            cursor.execute("""
                SELECT id FROM team_history
                WHERE team_id = ?
                  AND season_id = ?
                  AND field = 'faj_rating'
                  AND reference_match_id = ?
                LIMIT 1
            """, (away_team_id, season_id, match_id))
            if cursor.fetchone():
                raise RuntimeError(f"Match {match_id} already has rating history for away")
            
            # ====================================================
            # 2. ANALYSIS MEMORY
            # ====================================================
            marker_id = None
            history_ids = []
            
            if analysis_memory_data:
                for event_data in analysis_memory_data:
                    self._add_learning_memory_tx(cursor, event_data)
            
            # ====================================================
            # 3. ОБНОВЛЕНИЕ РЕЙТИНГА HOME
            # ====================================================
            self._update_team_rating_tx(
                cursor,
                home_team_id,
                season_id,
                home_rating_after,
                home_rating_before,
            )
            
            # ====================================================
            # 4. ОБНОВЛЕНИЕ РЕЙТИНГА AWAY
            # ====================================================
            self._update_team_rating_tx(
                cursor,
                away_team_id,
                season_id,
                away_rating_after,
                away_rating_before,
            )
            
            # ====================================================
            # 5. ИСТОРИЯ РЕЙТИНГА HOME
            # ====================================================
            history_id_home = self._record_team_rating_history_tx(
                cursor,
                home_team_id,
                season_id,
                match_id,
                home_rating_before,
                home_rating_after,
                home_delta,
                home_reason,
            )
            history_ids.append(history_id_home)
            
            # ====================================================
            # 6. ИСТОРИЯ РЕЙТИНГА AWAY
            # ====================================================
            history_id_away = self._record_team_rating_history_tx(
                cursor,
                away_team_id,
                season_id,
                match_id,
                away_rating_before,
                away_rating_after,
                away_delta,
                away_reason,
            )
            history_ids.append(history_id_away)
            
            # ====================================================
            # 7. BATCH_LEARNING MARKER
            # ====================================================
            marker_id = self._record_match_processing_tx(
                cursor,
                match_id,
                reason="Матч успешно обработан ETC. Рейтинг обновлён.",
            )
            
            # ====================================================
            # 8. COMMIT
            # ====================================================
            conn.commit()
            
            logger.info(
                "MATCH PROCESSED WITH RATING | "
                "match_id=%s | "
                "home: %.4f → %.4f | "
                "away: %.4f → %.4f | "
                "marker_id=%s",
                match_id,
                home_rating_before,
                home_rating_after,
                away_rating_before,
                away_rating_after,
                marker_id,
            )
            
            return {
                "status": "processed",
                "match_id": match_id,
                "home": {
                    "old": home_rating_before,
                    "new": home_rating_after,
                    "delta": home_delta,
                },
                "away": {
                    "old": away_rating_before,
                    "new": away_rating_after,
                    "delta": away_delta,
                },
                "history_ids": history_ids,
                "marker_id": marker_id,
            }
            
        except Exception as exc:
            conn.rollback()
            logger.exception(
                "MATCH PROCESSING WITH RATING FAILED | "
                "match_id=%s | error=%s",
                match_id,
                exc,
            )
            raise
            
        finally:
            conn.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    db = FAJDatabase()
    status = db.get_status()
    print(f"✅ FAJ Database: {status['status']}")
    print(f"   📊 Всего таблиц: {len(status['tables'])}")
    print(f"   📁 Файл: {status['file']}")
    print(f"   📌 Версия схемы: {status.get('schema_version', 'не определена')}")
    print(f"   🔒 Memory Hardened: v12.1")
    print(f"   🔐 Atomic save_complete_match_fact(): AVAILABLE")
    print(f"   🔐 Atomic process_match_with_rating(): AVAILABLE")
