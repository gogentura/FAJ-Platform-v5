#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — ФИНАЛЬНАЯ СХЕМА
Database Engine — ЕДИНЫЙ ФАЙЛ БАЗЫ ДАННЫХ 🔒

Схема: v12.1
Исправления: v12.1-hotfix
"""

import sqlite3
import os
import uuid
from datetime import datetime
import logging
from typing import Dict, Any, List, Optional
import json
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "faj.db")
DB_SCHEMA_VERSION = "12.1"


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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
        # Проверяем существование таблицы
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
    """Безопасное выполнение миграций FAJ Database v12.1."""
    logger.info("🚀 Запуск миграций FAJ...")
    # ------------------------------------------------------------
    # 1. Таблица истории миграций
    # ------------------------------------------------------------
    ensure_table("schema_migrations", """
        CREATE TABLE schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            description TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1
        )
    """)
    # ------------------------------------------------------------
    # 2. Проверяем наличие matches
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'matches'
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
        ensure_index(
            "matches",
            "idx_matches_status",
            "status"
        )
        ensure_index(
            "matches",
            "idx_matches_date",
            "date"
        )
        ensure_index(
            "matches",
            "idx_matches_home_away",
            "home_team_id, away_team_id"
        )
        ensure_index(
            "matches",
            "idx_matches_uuid",
            "match_uuid"
        )
    # ------------------------------------------------------------
    # 3. team_dynamic
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'team_dynamic'
    """)
    dynamic_exists = cursor.fetchone() is not None
    conn.close()
    if dynamic_exists:
        ensure_column(
            "team_dynamic",
            "last_sync",
            "TEXT"
        )
    # ------------------------------------------------------------
    # 4. prediction_validation
    # ------------------------------------------------------------
    ensure_index_if_table_exists(
        "prediction_validation",
        "idx_validation_match",
        "match_id"
    )
    # ------------------------------------------------------------
    # 5. team_form_history
    # ------------------------------------------------------------
    ensure_index_if_table_exists(
        "team_form_history",
        "idx_form_team_season",
        "team_id, season_id"
    )
    ensure_index_if_table_exists(
        "team_form_history",
        "idx_form_team_date",
        "team_id, created_at"
    )
    # ------------------------------------------------------------
    # 6. team_passports — миграция колонок
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'team_passports'
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
        logger.info("✅ Проверены колонки team_passports")
    
    # ------------------------------------------------------------
    # 7. team_passport_meta — миграция колонок
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'team_passport_meta'
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
    
    # ------------------------------------------------------------
    # 8. predictions — проверка prediction_status
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'predictions'
    """)
    predictions_exists = cursor.fetchone() is not None
    conn.close()

    if predictions_exists:
        ensure_column("predictions", "prediction_status", "TEXT DEFAULT 'active'")
        logger.info("✅ Проверена колонка prediction_status в predictions")

    # ------------------------------------------------------------
    # 9. Записываем версию
    # ------------------------------------------------------------
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO schema_migrations
        (version, description, success)
        VALUES (?, ?, ?)
    """, (
        DB_SCHEMA_VERSION,
        "FAJ Platform v12.1 database schema",
        1
    ))
    conn.commit()
    conn.close()
    logger.info(
        f"✅ Миграции завершены. Schema: {DB_SCHEMA_VERSION}"
    )


def init_database():
    """Инициализация базы данных с финальной схемой v12.1"""
    conn = get_connection()
    cursor = conn.cursor()

    logger.info("🚀 Инициализация базы данных FAJ v12.1...")

    # ===============================
    # OSNOVNYE TABLICY
    # ===============================

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
            created_at TEXT
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
            FOREIGN KEY(season_id) REFERENCES seasons(id)
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
            updated_at TEXT,
            created_at TEXT,
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_round ON matches(round_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id)")

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
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id),
            UNIQUE(team_id, season_id, version)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_passports_team_season
        ON team_passports(team_id, season_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_passports_version
        ON team_passports(version)
    """)

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
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_passport_meta_team
        ON team_passport_meta(team_id, season_id)
    """)

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
            created_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ============================================================
    # PREDICTIONS
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
            prediction_hash TEXT,
            prediction_status TEXT DEFAULT 'active',
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            model_version TEXT,
            category TEXT,
            parameter_name TEXT NOT NULL,
            parameter_value REAL,
            description TEXT,
            updated_at TEXT,
            UNIQUE(model_version, parameter_name)
        )
    """)

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
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id),
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)

    # ============================================================
    # PREDICTION VALIDATION
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
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
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_match ON prediction_validation(match_id)")

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

    # ============================================================
    # DIAGNOSTIC HISTORY
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
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_diagnostic_timestamp
        ON diagnostic_history(timestamp)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_diagnostic_status
        ON diagnostic_history(status)
    """)

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
    # MATCH RESULTS
    # ============================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER UNIQUE,
            home_goals INTEGER,
            away_goals INTEGER,
            home_penalty_goals INTEGER DEFAULT 0,
            away_penalty_goals INTEGER DEFAULT 0,
            FOREIGN KEY (match_id) REFERENCES matches(id)
        )
    """)
    
    # ============================================================
    # MATCH STATISTICS
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
            pass_accuracy REAL,
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (team_id) REFERENCES teams(id),
            UNIQUE(match_id, team_id)
        )
    """)
    
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

    # ============================================================
    # LEARNING LAYER
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            description TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()

    # ============================================================
    # ЗАПУСК МИГРАЦИЙ
    # ============================================================
    run_migrations()

    logger.info(f"✅ База данных инициализирована. Версия: {DB_SCHEMA_VERSION}")


class FAJDatabase:
    def __init__(self):
        init_database()

    # ============================================================
    # PUBLIC CONNECTION
    # ============================================================

    def get_connection(self):
        return get_connection()

    def _get_connection(self):
        return get_connection()

    # ============================================================
    # TRANSACTION
    # ============================================================

    @contextmanager
    def transaction(self):
        """Контекстный менеджер транзакций"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ============================================================
    # STATUS
    # ============================================================

    def get_status(self):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        result = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                result[table] = cursor.fetchone()[0]
            except:
                result[table] = 0

        schema_version = get_schema_version()
        conn.close()

        return {
            "database": "SQLite",
            "file": DB_FILE,
            "status": "ACTIVE",
            "schema_version": schema_version,
            "tables": result
        }

    # ============================================================
    # DIAGNOSTIC
    # ============================================================

    def save_diagnostic(self, data: Dict[str, Any]) -> int:
        try:
            conn = self.get_connection()
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

            conn.commit()
            row_id = cursor.lastrowid
            conn.close()
            return row_id

        except Exception as e:
            logger.error(f"Save diagnostic error: {e}")
            return 0

    def get_diagnostics(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM diagnostic_history
                ORDER BY id DESC LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

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

        except Exception as e:
            logger.error(f"Get diagnostics error: {e}")
            return []

    # ============================================================
    # PREDICTION EXISTS (ИСПРАВЛЕНИЕ №5)
    # ============================================================

    def prediction_exists(self, prediction_id) -> bool:
        """Проверяет существование прогноза в основной таблице predictions."""
        if prediction_id is None:
            return False
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1
                FROM predictions
                WHERE id = ?
                LIMIT 1
            """, (prediction_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(
                f"Prediction exists error: {e}"
            )
            return False

    # ============================================================
    # TEAMS
    # ============================================================

    def add_team(self, name, league, country="", api_id=None,
                 team_type="club", competition_group=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO teams
            (name, league, country, api_id, team_type, competition_group, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, league) DO UPDATE SET
                country = excluded.country,
                api_id = excluded.api_id,
                team_type = excluded.team_type,
                competition_group = excluded.competition_group
        """, (
            name, league, country, api_id, team_type, competition_group,
            datetime.now().isoformat()
        ))
        cursor.execute("SELECT id FROM teams WHERE name = ? AND league = ?", (name, league))
        team_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        return team_id

    def get_team_id(self, name, league):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM teams WHERE name = ? AND league = ?", (name, league))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def get_teams(self, league=None):
        conn = get_connection()
        cursor = conn.cursor()
        if league:
            cursor.execute("SELECT * FROM teams WHERE league = ? ORDER BY name", (league,))
        else:
            cursor.execute("SELECT * FROM teams ORDER BY name")
        data = cursor.fetchall()
        conn.close()
        return data

    def get_team(self, team_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams WHERE id = ?", (team_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    # ============================================================
    # SEASONS (ИСПРАВЛЕНИЕ №8)
    # ============================================================

    def create_season(
        self,
        name,
        league,
        year,
        competition_type="league",
        status="active"
    ):
        """Создаёт сезон или возвращает существующий."""
        if league is None or league == "":
            raise ValueError("league is required and cannot be None or empty")
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id
                FROM seasons
                WHERE league = ?
                  AND year = ?
                  AND competition_type = ?
                LIMIT 1
            """, (
                league,
                year,
                competition_type
            ))
            existing = cursor.fetchone()
            if existing:
                return existing["id"]
            cursor.execute("""
                INSERT INTO seasons (
                    name,
                    league,
                    year,
                    competition_type,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name,
                league,
                year,
                competition_type,
                status,
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            logger.error(
                f"Ошибка создания сезона {league} {year}: {e}"
            )
            raise
        finally:
            conn.close()

    def get_seasons(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM seasons ORDER BY id DESC")
        data = cursor.fetchall()
        conn.close()
        return data

    def get_season_id(self, league, year):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM seasons WHERE league = ? AND year = ?", (league, year))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    # ============================================================
    # ROUNDS (ИСПРАВЛЕНИЕ №7)
    # ============================================================

    def create_round(
        self,
        season_id,
        number,
        date_start="",
        date_end=""
    ):
        """Создаёт тур или возвращает существующий."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id
                FROM rounds
                WHERE season_id = ?
                  AND round_number = ?
                LIMIT 1
            """, (season_id, number))
            existing = cursor.fetchone()
            if existing:
                return existing["id"]
            cursor.execute("""
                INSERT INTO rounds (
                    season_id,
                    round_number,
                    date_start,
                    date_end,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                season_id,
                number,
                date_start,
                date_end,
                datetime.now().isoformat()
            ))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            logger.error(
                f"Ошибка создания тура {number}: {e}"
            )
            raise
        finally:
            conn.close()

    def get_rounds(self, season_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if season_id:
            cursor.execute("SELECT * FROM rounds WHERE season_id = ? ORDER BY round_number", (season_id,))
        else:
            cursor.execute("SELECT * FROM rounds ORDER BY id DESC")
        data = cursor.fetchall()
        conn.close()
        return data

    # ============================================================
    # MATCHES (ИСПРАВЛЕНИЕ №6 - upsert_match)
    # ============================================================

    def upsert_match(self, data: Dict[str, Any]) -> int:
        """
        Создаёт или обновляет матч.
        Приоритет идентификации:
        1. Переданный match_uuid
        2. Существующий матч по:
           round_id + home_team_id + away_team_id + date
        3. Новый UUID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        match_uuid = data.get("match_uuid")
        existing = None
        # ------------------------------------------------------------
        # 1. По UUID
        # ------------------------------------------------------------
        if match_uuid:
            cursor.execute("""
                SELECT id
                FROM matches
                WHERE match_uuid = ?
                LIMIT 1
            """, (match_uuid,))
            existing = cursor.fetchone()
        # ------------------------------------------------------------
        # 2. По естественному ключу матча
        # ------------------------------------------------------------
        if existing is None:
            cursor.execute("""
                SELECT id, match_uuid
                FROM matches
                WHERE round_id = ?
                  AND home_team_id = ?
                  AND away_team_id = ?
                  AND date = ?
                LIMIT 1
            """, (
                data.get("round_id"),
                data.get("home_team_id"),
                data.get("away_team_id"),
                data.get("date")
            ))
            existing = cursor.fetchone()
            if existing:
                match_uuid = existing["match_uuid"]
        # ------------------------------------------------------------
        # 3. Генерация UUID только для действительно нового матча
        # ------------------------------------------------------------
        if not match_uuid:
            match_uuid = str(uuid.uuid4())

        if existing:
            match_id = existing["id"]
            # Обновляем
            cursor.execute("""
                UPDATE matches SET
                    round_id = ?,
                    home_team_id = ?,
                    away_team_id = ?,
                    date = ?,
                    competition = ?,
                    status = ?,
                    actual_home = ?,
                    actual_away = ?,
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
                data.get('round_id'),
                data.get('home_team_id'),
                data.get('away_team_id'),
                data.get('date'),
                data.get('competition', 'RPL'),
                data.get('status', 'scheduled'),
                data.get('actual_home'),
                data.get('actual_away'),
                data.get('home_xg'),
                data.get('away_xg'),
                data.get('home_possession'),
                data.get('away_possession'),
                data.get('home_shots'),
                data.get('away_shots'),
                data.get('home_shots_on_target'),
                data.get('away_shots_on_target'),
                data.get('parser_source'),
                data.get('parser_version'),
                data.get('data_quality', 1.0),
                datetime.now().isoformat(),
                match_id
            ))
        else:
            # Вставляем
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
                    data_quality, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get('round_id'),
                data.get('home_team_id'),
                data.get('away_team_id'),
                match_uuid,
                data.get('date'),
                data.get('competition', 'RPL'),
                data.get('status', 'scheduled'),
                data.get('actual_home'),
                data.get('actual_away'),
                data.get('home_xg'),
                data.get('away_xg'),
                data.get('home_possession'),
                data.get('away_possession'),
                data.get('home_shots'),
                data.get('away_shots'),
                data.get('home_shots_on_target'),
                data.get('away_shots_on_target'),
                data.get('parser_source'),
                data.get('parser_version'),
                data.get('data_quality', 1.0),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            match_id = cursor.lastrowid

        conn.commit()
        conn.close()
        return match_id

    def update_result(self, match_id, home_score, away_score):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE matches
            SET actual_home = ?, actual_away = ?, status = 'finished'
            WHERE id = ?
        """, (home_score, away_score, match_id))
        conn.commit()
        conn.close()

    def update_match_stats(self, match_id: int, stats: Dict[str, Any]) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
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
                stats.get('home_xg'),
                stats.get('away_xg'),
                stats.get('home_possession'),
                stats.get('away_possession'),
                stats.get('home_shots'),
                stats.get('away_shots'),
                stats.get('home_shots_on_target'),
                stats.get('away_shots_on_target'),
                stats.get('parser_source'),
                stats.get('parser_version'),
                stats.get('data_quality', 1.0),
                datetime.now().isoformat(),
                match_id
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Update match stats error: {e}")
            return False

    def get_matches(self, round_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if round_id:
            cursor.execute("SELECT * FROM matches WHERE round_id = ?", (round_id,))
        else:
            cursor.execute("SELECT * FROM matches ORDER BY id DESC")
        data = cursor.fetchall()
        conn.close()
        return data

    def get_match_by_uuid(self, match_uuid: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_uuid = ?", (match_uuid,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ============================================================
    # MATCH PREDICTIONS
    # ============================================================

    def save_match_prediction(self, match_id, xg_home, xg_away,
                              lambda_home=None, lambda_away=None,
                              home_advantage=1.0, prediction_type="standard",
                              model_version="v11"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO match_predictions
            (match_id, xg_home, xg_away, lambda_home, lambda_away,
             home_advantage, prediction_type, model_version, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (match_id, xg_home, xg_away, lambda_home, lambda_away,
              home_advantage, prediction_type, model_version,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_match_prediction(self, match_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM match_predictions
            WHERE match_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (match_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    # ============================================================
    # TEAM BASE (ИСПРАВЛЕНИЕ №9)
    # ============================================================

    def get_base(self, team_id, season_id):
        """
        Возвращает основной team_base.
        ВАЖНО:
        team_base сохраняется для совместимости со старыми
        модулями FAJ. Основным паспортом v12.x является
        team_passports.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT *
                FROM team_base
                WHERE team_id = ?
                  AND season_id = ?
                ORDER BY
                    COALESCE(updated_at, '') DESC,
                    passport_version DESC,
                    id DESC
                LIMIT 1
            """, (
                team_id,
                season_id
            ))
            return cursor.fetchone()
        finally:
            conn.close()

    def update_base(self, team_id, season_id, **kwargs):
        allowed = [
            'attack', 'defense', 'control', 'press', 'tempo',
            'transition', 'set_pieces', 'counter_attack', 'build_up',
            'finishing', 'goalkeeper', 'discipline', 'coach_factor',
            'squad_quality', 'bench_quality', 'home_advantage'
        ]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        existing = self.get_base(team_id, season_id)
        conn = get_connection()
        cursor = conn.cursor()
        if existing:
            fields = []
            values = []
            for key, value in update_data.items():
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            query = f"""
                UPDATE team_base
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """
            cursor.execute(query, values)
        else:
            defaults = {
                'attack': 50, 'defense': 50, 'control': 50,
                'press': 50, 'tempo': 50, 'transition': 50,
                'set_pieces': 50, 'counter_attack': 50, 'build_up': 50,
                'finishing': 50, 'goalkeeper': 50, 'discipline': 50,
                'coach_factor': 50, 'squad_quality': 50, 'bench_quality': 50,
                'home_advantage': 1.0
            }
            defaults.update(update_data)
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
                defaults.get('attack', 50),
                defaults.get('defense', 50),
                defaults.get('control', 50),
                defaults.get('press', 50),
                defaults.get('tempo', 50),
                defaults.get('transition', 50),
                defaults.get('set_pieces', 50),
                defaults.get('counter_attack', 50),
                defaults.get('build_up', 50),
                defaults.get('finishing', 50),
                defaults.get('goalkeeper', 50),
                defaults.get('discipline', 50),
                defaults.get('coach_factor', 50),
                defaults.get('squad_quality', 50),
                defaults.get('bench_quality', 50),
                defaults.get('home_advantage', 1.0),
                1,
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # ============================================================
    # TEAM DYNAMIC — ИСПРАВЛЕН (АВТОМАТИЧЕСКИЙ last_sync)
    # ============================================================

    def get_dynamic(self, team_id, season_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM team_dynamic
            WHERE team_id = ? AND season_id = ?
            ORDER BY id DESC LIMIT 1
        """, (team_id, season_id))
        row = cursor.fetchone()
        conn.close()
        return row

    def update_dynamic(self, team_id, season_id, **kwargs):
        allowed = [
            'form', 'fitness', 'morale', 'fatigue', 'injury_index',
            'coach_confidence', 'last5_points', 'last5_strength_points',
            'last5_results', 'last5_strength_results', 'last5_xg', 'last5_xga',
            'last5_goals', 'last5_conceded', 'last5_performance',
            'average_performance', 'current_streak', 'days_rest',
            'travel_distance', 'rotation_index', 'last_base_correction_match',
            'passport_confidence'
        ]
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        # Автоматически обновляем last_sync
        update_data["last_sync"] = datetime.now().isoformat()
        existing = self.get_dynamic(team_id, season_id)
        conn = get_connection()
        cursor = conn.cursor()
        if existing:
            fields = []
            values = []
            for key, value in update_data.items():
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            query = f"""
                UPDATE team_dynamic
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """
            cursor.execute(query, values)
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
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                team_id, season_id,
                kwargs.get('form', 50),
                kwargs.get('fitness', 50),
                kwargs.get('morale', 50),
                kwargs.get('fatigue', 50),
                kwargs.get('injury_index', 0),
                kwargs.get('coach_confidence', 50),
                kwargs.get('last5_points', 0.0),
                kwargs.get('last5_strength_points', 0.0),
                kwargs.get('last5_results', '[0,0,0,0,0]'),
                kwargs.get('last5_strength_results', '[0,0,0,0,0]'),
                kwargs.get('last5_xg', 0.0),
                kwargs.get('last5_xga', 0.0),
                kwargs.get('last5_goals', 0),
                kwargs.get('last5_conceded', 0),
                kwargs.get('last5_performance', '[0,0,0,0,0]'),
                kwargs.get('average_performance', 0.0),
                kwargs.get('current_streak', 0),
                kwargs.get('days_rest', 7),
                kwargs.get('travel_distance', 0),
                kwargs.get('rotation_index', 0),
                kwargs.get('last_base_correction_match', 0),
                kwargs.get('passport_confidence', 0.4),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # ============================================================
    # TEAM IDENTITY
    # ============================================================

    def get_identity(self, team_id, season_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM team_identity
            WHERE team_id = ? AND season_id = ?
        """, (team_id, season_id))
        row = cursor.fetchone()
        conn.close()
        return row

    def update_identity(self, team_id, season_id, **kwargs):
        allowed = ['style', 'tempo', 'pressing', 'transition', 'risk_level']
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        conn = get_connection()
        cursor = conn.cursor()
        existing = self.get_identity(team_id, season_id)
        if existing:
            fields = []
            values = []
            for key, value in update_data.items():
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(team_id)
            values.append(season_id)
            query = f"""
                UPDATE team_identity
                SET {', '.join(fields)}
                WHERE team_id = ? AND season_id = ?
            """
            cursor.execute(query, values)
        else:
            cursor.execute("""
                INSERT INTO team_identity
                (team_id, season_id, style, tempo, pressing, transition, risk_level, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                team_id, season_id,
                kwargs.get('style', 'mixed'),
                kwargs.get('tempo', 'medium'),
                kwargs.get('pressing', 'medium'),
                kwargs.get('transition', 'medium'),
                kwargs.get('risk_level', 'medium'),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # ============================================================
    # TACTICAL MATCHUP
    # ============================================================

    def get_tactical_matchup(self, team_id, season_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tactical_matchup
            WHERE team_id = ? AND season_id = ?
        """, (team_id, season_id))
        row = cursor.fetchone()
        conn.close()
        return row

    def update_tactical_matchup(self, team_id, season_id, **kwargs):
        allowed = ['vs_high_press', 'vs_low_block', 'vs_counter_attack', 'vs_possession', 'vs_direct']
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return
        conn = get_connection()
        cursor = conn.cursor()
        existing = self.get_tactical_matchup(team_id, season_id)
        if existing:
            fields = []
            values = []
            for key, value in update_data.items():
                fields.append(f"{key} = ?")
                values.append(value)
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            query = f"""
                UPDATE tactical_matchup
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """
            cursor.execute(query, values)
        else:
            cursor.execute("""
                INSERT INTO tactical_matchup
                (team_id, season_id, vs_high_press, vs_low_block, vs_counter_attack, vs_possession, vs_direct, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                team_id, season_id,
                kwargs.get('vs_high_press', 0.0),
                kwargs.get('vs_low_block', 0.0),
                kwargs.get('vs_counter_attack', 0.0),
                kwargs.get('vs_possession', 0.0),
                kwargs.get('vs_direct', 0.0),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # ============================================================
    # PREDICTIONS
    # ============================================================

    def save_prediction(
        self,
        match_id: int,
        model_version: str,
        algorithm: str,
        home_win: float,
        draw: float,
        away_win: float,
        over25: float = 0.0,
        over35: float = 0.0,
        btts: float = 0.0,
        confidence: int = 50,
        prediction_source: str = "FAJ Engine",
        prediction_hash: str = None
    ) -> int:
        """Создаёт запись прогноза и возвращает его ID."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions (
                match_id,
                model_version,
                algorithm,
                home_win,
                draw,
                away_win,
                over25,
                over35,
                btts,
                confidence,
                prediction_source,
                prediction_hash,
                prediction_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match_id,
            model_version,
            algorithm,
            home_win,
            draw,
            away_win,
            over25,
            over35,
            btts,
            confidence,
            prediction_source,
            prediction_hash,
            'active',
            datetime.now().isoformat()
        ))
        conn.commit()
        prediction_id = cursor.lastrowid
        conn.close()
        logger.info(f"Prediction saved: id={prediction_id}, match_id={match_id}")
        return prediction_id

    def add_prediction_score(self, prediction_id, score, probability, rank):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prediction_scores (prediction_id, score, probability, rank)
            VALUES (?,?,?,?)
        """, (prediction_id, score, probability, rank))
        conn.commit()
        conn.close()

    def add_prediction_distribution(self, prediction_id, home_goals, away_goals, probability):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prediction_distributions (prediction_id, home_goals, away_goals, probability)
            VALUES (?,?,?,?)
        """, (prediction_id, home_goals, away_goals, probability))
        conn.commit()
        conn.close()

    def get_predictions_by_match(self, match_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM predictions WHERE match_id = ?
            ORDER BY created_at DESC
        """, (match_id,))
        data = cursor.fetchall()
        conn.close()
        return data

    def get_prediction_scores(self, prediction_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM prediction_scores WHERE prediction_id = ?
            ORDER BY rank
        """, (prediction_id,))
        data = cursor.fetchall()
        conn.close()
        return data

    # ============================================================
    # EXPERT PREDICTIONS
    # ============================================================

    def save_expert_prediction(self, match_id, expert_name, score,
                               comment="", confidence=50):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expert_predictions (match_id, expert_name, score, comment, confidence, created_at)
            VALUES (?,?,?,?,?,?)
        """, (match_id, expert_name, score, comment, confidence,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # ============================================================
    # JOURNAL
    # ============================================================

    def add_journal_entry(self, match_id, faj_prediction, expert_prediction,
                          actual_result, error_type, error_score, analysis=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal
            (match_id, faj_prediction, expert_prediction, actual_result,
             error_type, error_score, analysis, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (match_id, faj_prediction, expert_prediction, actual_result,
              error_type, error_score, analysis, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # ============================================================
    # MODEL PARAMETERS — УНИФИЦИРОВАНЫ
    # ============================================================

    def get_model_parameters(self, model_version=None):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if model_version:
            cursor.execute("""
                SELECT * FROM model_parameters
                WHERE model_version = ?
                ORDER BY category, parameter_name
            """, (model_version,))
        else:
            cursor.execute("SELECT * FROM model_parameters ORDER BY model_version, category, parameter_name")
        data = cursor.fetchall()
        conn.close()
        return data

    def set_model_parameter(self, model_version, category, parameter, value, description="", group_name=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO model_parameters
            (group_name, model_version, category, parameter_name, parameter_value, description, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            group_name or category,
            model_version,
            category,
            parameter,
            value,
            description,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def save_parameter(
        self,
        group_name: str,
        parameter_name: str,
        parameter_value: float,
        version: str = None,
        description: str = ""
    ) -> bool:
        """Сохраняет параметр модели (унифицированная версия)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            model_version = version or DB_SCHEMA_VERSION
            cursor.execute("""
                INSERT OR REPLACE INTO model_parameters (
                    group_name,
                    model_version,
                    category,
                    parameter_name,
                    parameter_value,
                    description,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                group_name,
                model_version,
                group_name,
                parameter_name,
                parameter_value,
                description,
                datetime.now().isoformat()
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Save parameter error: {e}")
            return False

    def get_parameter(
        self,
        group_name: str,
        parameter_name: str,
        version: str = None
    ) -> Optional[float]:
        """Получает параметр модели (унифицированная версия)."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if version:
                cursor.execute("""
                    SELECT parameter_value
                    FROM model_parameters
                    WHERE group_name = ?
                      AND parameter_name = ?
                      AND model_version = ?
                    ORDER BY datetime(updated_at) DESC
                    LIMIT 1
                """, (
                    group_name,
                    parameter_name,
                    version
                ))
            else:
                cursor.execute("""
                    SELECT parameter_value
                    FROM model_parameters
                    WHERE group_name = ?
                      AND parameter_name = ?
                    ORDER BY datetime(updated_at) DESC
                    LIMIT 1
                """, (
                    group_name,
                    parameter_name
                ))
            row = cursor.fetchone()
            conn.close()
            if not row:
                return None
            return row[0]
        except Exception as e:
            logger.error(f"Get parameter error: {e}")
            return None

    # ============================================================
    # LEARNING LAYER
    # ============================================================

    def add_to_gold(self, data):
        conn = get_connection()
        cursor = conn.cursor()
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
        conn.commit()
        gold_id = cursor.lastrowid
        conn.close()
        return gold_id

    def update_gold_actual(self, gold_id, actual_data):
        conn = get_connection()
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
            WHERE id = ?
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
        conn.close()

    def get_gold_by_match(self, match_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM gold_dataset WHERE match_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (match_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_gold_pending(self):
        """Возвращает только записи со статусом 'pending'."""
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM gold_dataset
            WHERE status = 'pending'
            ORDER BY match_date DESC
        """)
        results = cursor.fetchall()
        conn.close()
        return results

    def get_gold_all(self):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gold_dataset ORDER BY id DESC")
        results = cursor.fetchall()
        conn.close()
        return results

    def get_gold_count(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gold_dataset")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def add_learning_record(self, data):
        conn = get_connection()
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
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            data.get('status', 'new'),
            datetime.now().isoformat()
        ))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        return record_id

    def get_learning_records(self, status=None):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if status:
            cursor.execute("""
                SELECT * FROM learning_records
                WHERE status = ?
                ORDER BY created_at DESC
            """, (status,))
        else:
            cursor.execute("SELECT * FROM learning_records ORDER BY created_at DESC")
        results = cursor.fetchall()
        conn.close()
        return results

    def get_learning_count(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM learning_records")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def update_learning_status(self, record_id, status, recommendation=None):
        conn = get_connection()
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
        conn.close()

    def add_learning_event(self, data):
        conn = get_connection()
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
        conn.commit()
        conn.close()

    def save_passport_meta(self, team_id, season_id, passport_data):
        conn = get_connection()
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
        conn.close()

    def get_learning_status(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gold_dataset")
        gold_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM learning_records")
        learning_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM learning_events")
        events_count = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM learning_records
            WHERE status = 'new' AND error_severity >= 4
        """)
        critical = cursor.fetchone()[0]
        conn.close()
        return {
            'gold_dataset': gold_count,
            'learning_records': learning_count,
            'learning_events': events_count,
            'critical_errors': critical
        }

    # ============================================================
    # SAVE PREDICTION RESULT — ИСПРАВЛЕН
    # ============================================================

    def save_prediction_result(
        self,
        prediction_id: int,
        match_id: int,
        home_win: float,
        draw: float,
        away_win: float,
        confidence: float,
        model_version: str
    ) -> bool:
        """
        Сохраняет итоговый результат прогноза в существующую запись predictions.
        Используется для финального обновления прогноза после расчёта.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE predictions
                SET
                    match_id = ?,
                    home_win = ?,
                    draw = ?,
                    away_win = ?,
                    confidence = ?,
                    model_version = ?,
                    prediction_source = 'FAJ Engine',
                    prediction_status = 'active'
                WHERE id = ?
            """, (
                match_id,
                home_win,
                draw,
                away_win,
                confidence,
                model_version,
                prediction_id
            ))

            if cursor.rowcount == 0:
                conn.rollback()
                logger.warning(f"Prediction not found: {prediction_id}")
                conn.close()
                return False

            conn.commit()
            conn.close()
            logger.info(f"Prediction result updated: {prediction_id}, match_id={match_id}")
            return True

        except Exception as e:
            logger.error(f"Save prediction result error: {e}")
            return False

    # ============================================================
    # PREDICTION VALIDATION
    # ============================================================

    def save_prediction_validation(self, data: Dict[str, Any]) -> int:
        """Сохранение результата сравнения прогноза с фактом"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO prediction_validation (
                match_id, predicted_score, actual_score,
                predicted_home_xg, actual_home_xg,
                predicted_away_xg, actual_away_xg,
                predicted_winner, actual_winner,
                predicted_probability_home, predicted_probability_draw, predicted_probability_away,
                score_probability, confidence, risk,
                predicted_btts, actual_btts,
                predicted_over25, actual_over25,
                model_version, passport_version, parser_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('match_id'),
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
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    # ============================================================
    # TEAM FORM HISTORY
    # ============================================================

    def save_team_form(self, data: Dict[str, Any]) -> int:
        """Сохранение истории формы команды"""
        conn = self.get_connection()
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
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        return row_id

    def get_team_form_history(self, team_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории формы команды"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM team_form_history
            WHERE team_id = ?
            ORDER BY round DESC
            LIMIT ?
        """, (team_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ============================================================
    # GET TEAM PASSPORT (ИСПРАВЛЕНИЕ №10 - НОВЫЙ МЕТОД)
    # ============================================================

    def get_team_passport(
        self,
        team_id: int,
        season_id: int,
        version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Возвращает актуальный FAJ Team Passport.
        Приоритет:
        - конкретная version, если передана;
        - иначе последний созданный паспорт.
        team_passports является основным источником
        паспортных параметров FAJ v12.x.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if version:
                cursor.execute("""
                    SELECT *
                    FROM team_passports
                    WHERE team_id = ?
                      AND season_id = ?
                      AND version = ?
                    LIMIT 1
                """, (
                    team_id,
                    season_id,
                    version
                ))
            else:
                cursor.execute("""
                    SELECT *
                    FROM team_passports
                    WHERE team_id = ?
                      AND season_id = ?
                    ORDER BY
                        datetime(created_at) DESC,
                        id DESC
                    LIMIT 1
                """, (
                    team_id,
                    season_id
                ))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)
        except Exception as e:
            logger.error(
                f"Ошибка получения паспорта "
                f"team_id={team_id}, season_id={season_id}: {e}"
            )
            return None
        finally:
            conn.close()

    # ============================================================
    # SAVE TEAM PASSPORT (НОВЫЙ МЕТОД ДЛЯ PASSPORT_MANAGER)
    # ============================================================

    def save_team_passport(
        self,
        team_id: int,
        season_id: int,
        data: Dict[str, Any],
        version: Optional[str] = None,
        source: str = "manual"
    ) -> Optional[int]:
        """
        Сохраняет паспорт команды в team_passports.
        Используется PassportManager.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Определяем версию, если не передана
            if version is None:
                cursor.execute("""
                    SELECT version
                    FROM team_passports
                    WHERE team_id = ? AND season_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (team_id, season_id))
                row = cursor.fetchone()
                if row:
                    v = row[0]
                    if v.startswith("v"):
                        try:
                            num = int(v[1:].split('.')[0])
                            version = f"v{num + 1}.0"
                        except:
                            version = "v1.0"
                    else:
                        version = "v1.0"
                else:
                    version = "v1.0"

            # Проверяем существование
            cursor.execute("""
                SELECT id
                FROM team_passports
                WHERE team_id = ? AND season_id = ? AND version = ?
            """, (team_id, season_id, version))
            
            existing = cursor.fetchone()

            # Подготавливаем данные
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
                "source": source,
                "created_at": datetime.now().isoformat()
            }

            if existing:
                passport_id = existing[0]
                fields = []
                values = []
                for key, value in passport_data.items():
                    if key not in ["team_id", "season_id", "version"]:
                        fields.append(f"{key} = ?")
                        values.append(value)
                values.append(passport_id)
                
                query = f"""
                    UPDATE team_passports
                    SET {', '.join(fields)}
                    WHERE id = ?
                """
                cursor.execute(query, values)
            else:
                columns = ", ".join(passport_data.keys())
                placeholders = ", ".join(["?"] * len(passport_data))
                query = f"""
                    INSERT INTO team_passports ({columns})
                    VALUES ({placeholders})
                """
                cursor.execute(query, list(passport_data.values()))
                passport_id = cursor.lastrowid

            conn.commit()
            conn.close()
            
            logger.info(f"Passport saved: team_id={team_id}, season_id={season_id}, version={version}")
            return passport_id

        except Exception as e:
            logger.error(f"Save team passport error: {e}")
            return None


if __name__ == "__main__":
    db = FAJDatabase()
    status = db.get_status()
    print(f"✅ FAJ Database: {status['status']}")
    print(f"   📊 Всего таблиц: {len(status['tables'])}")
    print(f"   📁 Файл: {status['file']}")
    print(f"   📌 Версия схемы: {status.get('schema_version', 'не определена')}")
