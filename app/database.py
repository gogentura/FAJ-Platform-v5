#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11.1
Database Engine — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ

Больше никаких изменений в структуре БД.
Все новые модули только используют существующие таблицы.

Таблицы:
- teams (UNIQUE name, league)
- seasons
- rounds
- matches
- match_predictions (с home_advantage)
- match_events
- players
- player_events
- team_base
- team_dynamic
- team_tournament
- team_events
- team_history
- predictions (с algorithm)
- prediction_scores
- prediction_distributions
- expert_predictions
- journal
- learning_memory (с reference_id)
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
    # 1. TEAMS (UNIQUE name, league)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT NOT NULL,
            country TEXT,
            api_id INTEGER,
            created_at TEXT,
            UNIQUE(name, league)
        )
    """)

    # ===============================
    # 2. SEASONS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT NOT NULL,
            year TEXT,
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
            status TEXT DEFAULT 'scheduled',
            actual_home INTEGER,
            actual_away INTEGER,
            created_at TEXT,
            FOREIGN KEY(round_id) REFERENCES rounds(id),
            FOREIGN KEY(home_team_id) REFERENCES teams(id),
            FOREIGN KEY(away_team_id) REFERENCES teams(id)
        )
    """)

    # ===============================
    # 5. MATCH PREDICTIONS (с home_advantage)
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
            last5_points INTEGER DEFAULT 0,
            last5_xg REAL DEFAULT 0,
            last5_xga REAL DEFAULT 0,
            last5_goals INTEGER DEFAULT 0,
            last5_conceded INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            days_rest INTEGER DEFAULT 7,
            travel_distance INTEGER DEFAULT 0,
            rotation_index INTEGER DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ===============================
    # 11. TEAM TOURNAMENT
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_tournament (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            season_id INTEGER,
            league_modifier REAL DEFAULT 1.0,
            cup_modifier REAL DEFAULT 1.0,
            ucl_modifier REAL DEFAULT 1.0,
            supercup_modifier REAL DEFAULT 1.0,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id),
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ===============================
    # 12. TEAM EVENTS
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
    # 13. TEAM HISTORY
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
    # 14. PREDICTIONS (с algorithm)
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
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # 15. PREDICTION SCORES
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
    # 16. PREDICTION DISTRIBUTIONS
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
    # 17. EXPERT PREDICTIONS
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
    # 18. JOURNAL
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            faj_prediction TEXT,
            expert_prediction TEXT,
            actual_result TEXT,
            error_type TEXT,
            analysis TEXT,
            created_at TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # 19. LEARNING MEMORY (с reference_id)
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
            algorithm TEXT,
            model_version TEXT,
            reference_id INTEGER,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


class FAJDatabase:

    def __init__(self):
        init_database()

    def _get_connection(self):
        return get_connection()

    def get_status(self):
        conn = get_connection()
        cursor = conn.cursor()
        tables = [
            "teams", "seasons", "rounds", "matches", "match_predictions",
            "match_events", "players", "player_events", "team_base",
            "team_dynamic", "team_tournament", "team_events", "team_history",
            "predictions", "prediction_scores", "prediction_distributions",
            "expert_predictions", "journal", "learning_memory"
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
    def add_team(self, name, league, country="", api_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO teams (name, league, country, api_id, created_at)
            VALUES (?,?,?,?,?)
        """, (name, league, country, api_id, datetime.now().isoformat()))
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
    def create_season(self, name, league, year, status="active"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seasons (name, league, year, status, created_at)
            VALUES (?,?,?,?,?)
        """, (name, league, year, status, datetime.now().isoformat()))
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
    def add_match(self, round_id, home_team_id, away_team_id, date=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO matches (round_id, home_team_id, away_team_id, date, created_at)
            VALUES (?,?,?,?,?)
        """, (round_id, home_team_id, away_team_id, date, datetime.now().isoformat()))
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
                              home_advantage=1.0, model_version="v11"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO match_predictions
            (match_id, xg_home, xg_away, lambda_home, lambda_away,
             home_advantage, model_version, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (match_id, xg_home, xg_away, lambda_home, lambda_away,
              home_advantage, model_version, datetime.now().isoformat()))
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
            'coach_confidence', 'last5_points', 'last5_xg', 'last5_xga',
            'last5_goals', 'last5_conceded', 'current_streak', 'days_rest',
            'travel_distance', 'rotation_index'
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
                    last5_xg, last5_xga, last5_goals, last5_conceded,
                    current_streak, days_rest, travel_distance, rotation_index,
                    updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                team_id, season_id,
                kwargs.get('form', 50),
                kwargs.get('fitness', 50),
                kwargs.get('morale', 50),
                kwargs.get('fatigue', 50),
                kwargs.get('injury_index', 0),
                kwargs.get('coach_confidence', 50),
                kwargs.get('last5_points', 0),
                kwargs.get('last5_xg', 0.0),
                kwargs.get('last5_xga', 0.0),
                kwargs.get('last5_goals', 0),
                kwargs.get('last5_conceded', 0),
                kwargs.get('current_streak', 0),
                kwargs.get('days_rest', 7),
                kwargs.get('travel_distance', 0),
                kwargs.get('rotation_index', 0),
                datetime.now().isoformat()
            ))
        conn.commit()
        conn.close()

    # =================================
    # TEAM TOURNAMENT
    # =================================
    def update_tournament(self, team_id, season_id, **kwargs):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO team_tournament
            (team_id, season_id, league_modifier, cup_modifier,
             ucl_modifier, supercup_modifier, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            team_id, season_id,
            kwargs.get('league_modifier', 1.0),
            kwargs.get('cup_modifier', 1.0),
            kwargs.get('ucl_modifier', 1.0),
            kwargs.get('supercup_modifier', 1.0),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    # =================================
    # TEAM HISTORY
    # =================================
    def add_history(self, team_id, season_id, field, old_value, new_value,
                    reason="", source="auto"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO team_history (team_id, season_id, field, old_value, new_value, reason, source, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (team_id, season_id, field, str(old_value), str(new_value),
              reason, source, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_history(self, team_id, season_id=None, limit=20):
        conn = get_connection()
        cursor = conn.cursor()
        if season_id:
            cursor.execute("""
                SELECT * FROM team_history
                WHERE team_id = ? AND season_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (team_id, season_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM team_history
                WHERE team_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (team_id, limit))
        data = cursor.fetchall()
        conn.close()
        return data

    # =================================
    # PREDICTIONS
    # =================================
    def save_prediction(self, match_id, model_version, algorithm, home_win, draw, away_win,
                        over25, over35, btts, confidence):
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

    def add_prediction_scores(self, prediction_id, scores):
        conn = get_connection()
        cursor = conn.cursor()
        for rank, (score, prob) in enumerate(scores, 1):
            cursor.execute("""
                INSERT INTO prediction_scores (prediction_id, score, probability, rank)
                VALUES (?,?,?,?)
            """, (prediction_id, score, prob, rank))
        conn.commit()
        conn.close()

    def add_prediction_distribution(self, prediction_id, distribution):
        conn = get_connection()
        cursor = conn.cursor()
        for (home_goals, away_goals), prob in distribution.items():
            cursor.execute("""
                INSERT INTO prediction_distributions (prediction_id, home_goals, away_goals, probability)
                VALUES (?,?,?,?)
            """, (prediction_id, home_goals, away_goals, prob))
        conn.commit()
        conn.close()

    def get_prediction(self, match_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM predictions
            WHERE match_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (match_id,))
        pred = cursor.fetchone()
        if pred:
            cursor.execute("""
                SELECT * FROM prediction_scores
                WHERE prediction_id = ?
                ORDER BY rank
            """, (pred['id'],))
            scores = cursor.fetchall()
            cursor.execute("""
                SELECT * FROM prediction_distributions
                WHERE prediction_id = ?
            """, (pred['id'],))
            dist = cursor.fetchall()
            conn.close()
            return dict(pred), scores, dist
        conn.close()
        return None, [], []

    # =================================
    # JOURNAL
    # =================================
    def add_journal(self, match_id, faj_pred, expert_pred, actual,
                    error_type, analysis=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal (match_id, faj_prediction, expert_prediction,
                                 actual_result, error_type, analysis, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (match_id, faj_pred, expert_pred, actual, error_type,
              analysis, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # =================================
    # LEARNING MEMORY
    # =================================
    def add_memory(self, event_type, object_name, feature="", before="", after="",
                   delta="", reason="", confidence=1.0, algorithm="",
                   model_version="v11", reference_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_memory
            (event_type, object, feature, before_value, after_value,
             delta, reason, confidence, algorithm, model_version,
             reference_id, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (event_type, object_name, feature, str(before), str(after),
              str(delta), reason, confidence, algorithm, model_version,
              reference_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()


# =====================================================
# AUTO INIT
# =====================================================

init_database()
