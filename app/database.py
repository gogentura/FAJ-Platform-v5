#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11.2.1 + Learning Layer
Database Engine — ЕДИНЫЙ ФАЙЛ БАЗЫ ДАННЫХ 🔒

Таблицы (25 основных + 5 Learning Layer):
- teams, seasons, rounds, matches, match_predictions
- match_events, players, player_events
- team_base, team_dynamic, team_identity, tactical_matchup, player_impact
- team_competition_profile, team_events, team_history
- predictions, prediction_scores, prediction_distributions
- expert_predictions, journal, learning_memory
- model_parameters, xg_memory, match_snapshots
- gold_dataset, learning_records, learning_events, audit_log, migrations

БАЗА: SQLite
СТАТУС: 🔒 ЗАМОРОЖЕНА + Learning Layer
"""

import sqlite3
import os
from datetime import datetime


DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "faj.db")


def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # ===============================
    # 1. TEAMS
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

    # ===============================
    # 2. SEASONS
    # ===============================
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

    # ===============================
    # 3. ROUNDS
    # ===============================
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

    # ===============================
    # 4. MATCHES
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            date TEXT,
            competition TEXT,
            status TEXT DEFAULT 'scheduled',
            actual_home INTEGER,
            actual_away INTEGER,
            created_at TEXT,
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_round ON matches(round_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id)")

    # ===============================
    # 5. MATCH PREDICTIONS
    # ===============================
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

    # ===============================
    # 6. MATCH EVENTS
    # ===============================
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

    # ===============================
    # 7. PLAYERS
    # ===============================
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

    # ===============================
    # 8. PLAYER EVENTS
    # ===============================
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

    # ===============================
    # 9. TEAM BASE
    # ===============================
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
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ===============================
    # 10. TEAM DYNAMIC
    # ===============================
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
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ===============================
    # 11. TEAM IDENTITY
    # ===============================
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

    # ===============================
    # 12. TACTICAL MATCHUP
    # ===============================
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

    # ===============================
    # 13. PLAYER IMPACT
    # ===============================
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

    # ===============================
    # 14. TEAM COMPETITION PROFILE
    # ===============================
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

    # ===============================
    # 15. TEAM EVENTS
    # ===============================
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

    # ===============================
    # 16. TEAM HISTORY
    # ===============================
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

    # ===============================
    # 17. PREDICTIONS
    # ===============================
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
            prediction_status TEXT DEFAULT 'active',
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # 18. PREDICTION SCORES
    # ===============================
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

    # ===============================
    # 19. PREDICTION DISTRIBUTIONS
    # ===============================
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

    # ===============================
    # 20. EXPERT PREDICTIONS
    # ===============================
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

    # ===============================
    # 21. JOURNAL
    # ===============================
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

    # ===============================
    # 22. LEARNING MEMORY
    # ===============================
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

    # ===============================
    # 23. MODEL PARAMETERS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT,
            category TEXT,
            parameter TEXT,
            value REAL,
            description TEXT,
            updated_at TEXT,
            UNIQUE(model_version, parameter)
        )
    """)

    # ===============================
    # 24. XG MEMORY
    # ===============================
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

    # ===============================
    # 25. MATCH SNAPSHOTS
    # ===============================
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
    # LEARNING LAYER TABLES (v12)
    # ============================================================

    # 26. MIGRATIONS — журнал миграций
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

    # 27. GOLD_DATASET — эталонная база
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_match ON gold_dataset(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_status ON gold_dataset(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gold_version ON gold_dataset(model_version)")

    # 28. LEARNING_RECORDS — память ошибок
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_gold ON learning_records(gold_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_type ON learning_records(error_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_cause ON learning_records(cause_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learning_status ON learning_records(status)")

    # 29. LEARNING_EVENTS — события обучения
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_match ON learning_events(match_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_team ON learning_events(home_team_id, away_team_id)")

    # 30. AUDIT_LOG — журнал аудита
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

    # 31. MODEL_PARAMETERS_LEARNING — параметры для обучения
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_params_version ON model_parameters_learning(model_version)")

    conn.commit()
    conn.close()


class FAJDatabase:

    def __init__(self):
        init_database()

    def _get_connection(self):
        return get_connection()

    # =================================
    # СТАТУС
    # =================================
    def get_status(self):
        conn = get_connection()
        cursor = conn.cursor()
        tables = [
            "teams", "seasons", "rounds", "matches", "match_predictions",
            "match_events", "players", "player_events", "team_base",
            "team_dynamic", "team_identity", "tactical_matchup", "player_impact",
            "team_competition_profile", "team_events", "team_history",
            "predictions", "prediction_scores", "prediction_distributions",
            "expert_predictions", "journal", "learning_memory",
            "model_parameters", "xg_memory", "match_snapshots",
            "migrations", "gold_dataset", "learning_records", "learning_events",
            "audit_log", "model_parameters_learning"
        ]
        result = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                result[table] = cursor.fetchone()[0]
            except:
                result[table] = 0
        conn.close()
        return {
            "database": "SQLite",
            "file": DB_FILE,
            "status": "ACTIVE",
            "tables": result
        }

    # =================================
    # TEAMS
    # =================================
    def add_team(self, name, league, country="", api_id=None,
                 team_type="club", competition_group=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO teams
            (name, league, country, api_id, team_type, competition_group, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (name, league, country, api_id, team_type, competition_group,
              datetime.now().isoformat()))
        conn.commit()
        team_id = cursor.lastrowid
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

    # =================================
    # SEASONS
    # =================================
    def create_season(self, name, league, year, competition_type="league", status="active"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seasons (name, league, year, competition_type, status, created_at)
            VALUES (?,?,?,?,?,?)
        """, (name, league, year, competition_type, status, datetime.now().isoformat()))
        conn.commit()
        season_id = cursor.lastrowid
        conn.close()
        return season_id

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

    # =================================
    # ROUNDS
    # =================================
    def create_round(self, season_id, number, date_start="", date_end=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rounds (season_id, round_number, date_start, date_end, created_at)
            VALUES (?,?,?,?,?)
        """, (season_id, number, date_start, date_end, datetime.now().isoformat()))
        conn.commit()
        round_id = cursor.lastrowid
        conn.close()
        return round_id

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

    # =================================
    # MATCHES
    # =================================
    def add_match(self, round_id, home_team_id, away_team_id,
                  date="", competition="RPL"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO matches (round_id, home_team_id, away_team_id, date, competition, created_at)
            VALUES (?,?,?,?,?,?)
        """, (round_id, home_team_id, away_team_id, date, competition,
              datetime.now().isoformat()))
        conn.commit()
        match_id = cursor.lastrowid
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

    # =================================
    # MATCH PREDICTIONS
    # =================================
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

    # =================================
    # TEAM BASE
    # =================================
    def get_base(self, team_id, season_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM team_base
            WHERE team_id = ? AND season_id = ?
            ORDER BY passport_version DESC LIMIT 1
        """, (team_id, season_id))
        row = cursor.fetchone()
        conn.close()
        return row

    def update_base(self, team_id, season_id, **kwargs):
        allowed = [
            'attack', 'defense', 'control', 'press', 'tempo',
            'transition', 'set_pieces', 'counter_attack', 'build_up',
            'finishing', 'goalkeeper', 'discipline', 'coach_factor',
            'squad_quality', 'bench_quality', 'home_advantage'
        ]
        existing = self.get_base(team_id, season_id)
        conn = get_connection()
        cursor = conn.cursor()

        if existing:
            fields = []
            values = []
            for key in allowed:
                if key in kwargs:
                    fields.append(f"{key} = ?")
                    values.append(kwargs[key])
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            cursor.execute(f"""
                UPDATE team_base
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """, values)
        else:
            cursor.execute("""
                INSERT INTO team_base (team_id, season_id, attack, defense, control,
                    press, tempo, transition, set_pieces, counter_attack, build_up,
                    finishing, goalkeeper, discipline, coach_factor, squad_quality,
                    bench_quality, home_advantage, passport_version, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)
            """, (
                team_id, season_id,
                kwargs.get('attack', 50),
                kwargs.get('defense', 50),
                kwargs.get('control', 50),
                kwargs.get('press', 50),
                kwargs.get('tempo', 50),
                kwargs.get('transition', 50),
                kwargs.get('set_pieces', 50),
                kwargs.get('counter_attack', 50),
                kwargs.get('build_up', 50),
                kwargs.get('finishing', 50),
                kwargs.get('goalkeeper', 50),
                kwargs.get('discipline', 50),
                kwargs.get('coach_factor', 50),
                kwargs.get('squad_quality', 50),
                kwargs.get('bench_quality', 50),
                kwargs.get('home_advantage', 1.0),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # =================================
    # TEAM DYNAMIC
    # =================================
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
        existing = self.get_dynamic(team_id, season_id)
        conn = get_connection()
        cursor = conn.cursor()

        if existing:
            fields = []
            values = []
            for key in allowed:
                if key in kwargs:
                    fields.append(f"{key} = ?")
                    values.append(kwargs[key])
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            cursor.execute(f"""
                UPDATE team_dynamic
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """, values)
        else:
            cursor.execute("""
                INSERT INTO team_dynamic (team_id, season_id, form, fitness, morale,
                    fatigue, injury_index, coach_confidence, last5_points,
                    last5_strength_points, last5_results, last5_strength_results,
                    last5_xg, last5_xga, last5_goals, last5_conceded,
                    last5_performance, average_performance, current_streak,
                    days_rest, travel_distance, rotation_index,
                    last_base_correction_match, passport_confidence, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # =================================
    # TEAM IDENTITY
    # =================================
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
        conn = get_connection()
        cursor = conn.cursor()
        existing = self.get_identity(team_id, season_id)

        if existing:
            fields = []
            values = []
            for key in allowed:
                if key in kwargs:
                    fields.append(f"{key} = ?")
                    values.append(kwargs[key])
            values.append(team_id)
            values.append(season_id)
            cursor.execute(f"""
                UPDATE team_identity
                SET {', '.join(fields)}
                WHERE team_id = ? AND season_id = ?
            """, values)
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

    # =================================
    # TACTICAL MATCHUP
    # =================================
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
        conn = get_connection()
        cursor = conn.cursor()
        existing = self.get_tactical_matchup(team_id, season_id)

        if existing:
            fields = []
            values = []
            for key in allowed:
                if key in kwargs:
                    fields.append(f"{key} = ?")
                    values.append(kwargs[key])
            values.append(datetime.now().isoformat())
            values.append(team_id)
            values.append(season_id)
            cursor.execute(f"""
                UPDATE tactical_matchup
                SET {', '.join(fields)}, updated_at = ?
                WHERE team_id = ? AND season_id = ?
            """, values)
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

    # =================================
    # PREDICTIONS
    # =================================
    def save_prediction(self, match_id, model_version, algorithm,
                        home_win, draw, away_win,
                        over25=0.0, over35=0.0, btts=0.0,
                        confidence=50):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions
            (match_id, model_version, algorithm, home_win, draw, away_win,
             over25, over35, btts, confidence, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (match_id, model_version, algorithm, home_win, draw, away_win,
              over25, over35, btts, confidence, datetime.now().isoformat()))
        conn.commit()
        pred_id = cursor.lastrowid
        conn.close()
        return pred_id

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

    # =================================
    # EXPERT PREDICTIONS
    # =================================
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

    # =================================
    # JOURNAL
    # =================================
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

    # =================================
    # MODEL PARAMETERS
    # =================================
    def get_model_parameters(self, model_version=None):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if model_version:
            cursor.execute("""
                SELECT * FROM model_parameters
                WHERE model_version = ?
                ORDER BY category, parameter
            """, (model_version,))
        else:
            cursor.execute("SELECT * FROM model_parameters ORDER BY model_version, category, parameter")
        data = cursor.fetchall()
        conn.close()
        return data

    def set_model_parameter(self, model_version, category, parameter, value, description=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO model_parameters
            (model_version, category, parameter, value, description, updated_at)
            VALUES (?,?,?,?,?,?)
        """, (model_version, category, parameter, value, description,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # =================================
    # GOLD DATASET — LEARNING LAYER
    # =================================

    def add_to_gold(self, data):
        """
        Добавляет запись в gold_dataset

        data = {
            'match_id': 1,
            'home_team': 'Краснодар',
            'away_team': 'Зенит',
            'match_date': '30.07.2026',
            'model_version': '1.0',
            'faj_score': '1:2',
            'faj_xg_home': 1.25,
            'faj_xg_away': 1.65,
            'faj_btts': 1,
            'faj_total_25': 1,
            'faj_total_35': 0,
            'faj_confidence': 68,
            'faj_rating_home': 90.0,
            'faj_rating_away': 91.5,
            'faj_pir_home': 7.8,
            'faj_pir_away': 8.3,
            'faj_style_home': 'владение, высокий прессинг',
            'faj_style_away': 'контроль центра, быстрые переходы',
            'expert_score': '1:2',
            'expert_reasoning': 'разница качества состава',
            'status': 'pending'
        }
        """
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
        """
        Обновляет фактические данные в gold_dataset

        actual_data = {
            'actual_score': '2:2',
            'actual_xg_home': 1.80,
            'actual_xg_away': 1.90,
            'actual_btts': 1,
            'actual_total_25': 1,
            'actual_total_35': 1,
            'actual_home_goals': 2,
            'actual_away_goals': 2
        }
        """
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
        """Получает запись gold_dataset по match_id"""
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
        """Получает все записи со статусом pending или completed (не аудированные)"""
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM gold_dataset
            WHERE status IN ('pending', 'completed')
            ORDER BY match_date DESC
        """)

        results = cursor.fetchall()
        conn.close()
        return results

    def get_gold_all(self):
        """Получает все записи gold_dataset"""
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM gold_dataset ORDER BY id DESC")
        results = cursor.fetchall()
        conn.close()
        return results

    def get_gold_count(self):
        """Количество записей в gold_dataset"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gold_dataset")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # =================================
    # LEARNING RECORDS — LEARNING LAYER
    # =================================

    def add_learning_record(self, data):
        """Добавляет запись в learning_records"""
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
        """Получает записи learning_records"""
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
        """Количество записей в learning_records"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM learning_records")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def update_learning_status(self, record_id, status, recommendation=None):
        """Обновляет статус и рекомендацию"""
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

    # =================================
    # LEARNING EVENTS — LEARNING LAYER
    # =================================

    def add_learning_event(self, data):
        """Добавляет событие обучения"""
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

    # =================================
    # LEARNING LAYER — СТАТИСТИКА
    # =================================

    def get_learning_status(self):
        """Получает статус Learning Layer"""
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


if __name__ == "__main__":
    db = FAJDatabase()
    status = db.get_status()
    print(f"✅ FAJ Database: {status['status']}")
    print(f"   📊 Всего таблиц: {len(status['tables'])}")
    print(f"   📁 Файл: {status['file']}")
