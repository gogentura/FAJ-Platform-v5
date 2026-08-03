#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v11
Database Engine

SQLite storage:
- seasons
- rounds
- teams
- team_passports
- players
- matches
- predictions
- expert_predictions
- faj_memory
- journal

Единый источник данных FAJ
"""

import sqlite3
import os
from datetime import datetime


# =====================================================
# PATH
# =====================================================

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "faj.db")


# =====================================================
# CONNECTION
# =====================================================

def get_connection():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# INIT DATABASE
# =====================================================

def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # ===============================
    # SEASONS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT NOT NULL,
            year TEXT,
            status TEXT DEFAULT 'active',
            created TEXT
        )
    """)

    # ===============================
    # ROUNDS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season_id INTEGER,
            round_number INTEGER,
            date_start TEXT,
            date_end TEXT,
            status TEXT DEFAULT 'scheduled',
            created TEXT,
            FOREIGN KEY(season_id) REFERENCES seasons(id)
        )
    """)

    # ===============================
    # TEAMS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            league TEXT,
            country TEXT,
            created TEXT
        )
    """)

    # ===============================
    # TEAM PASSPORTS (ДНК команды)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_passports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER,
            attack INTEGER DEFAULT 50,
            defense INTEGER DEFAULT 50,
            control INTEGER DEFAULT 50,
            press INTEGER DEFAULT 50,
            tempo INTEGER DEFAULT 50,
            transition INTEGER DEFAULT 50,
            fitness INTEGER DEFAULT 50,
            mentality INTEGER DEFAULT 50,
            coach_factor INTEGER DEFAULT 50,
            updated_at TEXT,
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)

    # ===============================
    # PLAYERS
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
            FOREIGN KEY(team_id) REFERENCES teams(id)
        )
    """)

    # ===============================
    # MATCHES
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER,
            home_team TEXT,
            away_team TEXT,
            date TEXT,
            faj_xg_home REAL,
            faj_xg_away REAL,
            actual_home INTEGER,
            actual_away INTEGER,
            status TEXT DEFAULT 'scheduled',
            created TEXT,
            FOREIGN KEY(round_id) REFERENCES rounds(id)
        )
    """)

    # ===============================
    # PREDICTIONS (FAJ прогнозы)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            model_version TEXT,
            score_1 TEXT,
            probability_1 REAL,
            score_2 TEXT,
            probability_2 REAL,
            score_3 TEXT,
            probability_3 REAL,
            home_win REAL,
            draw REAL,
            away_win REAL,
            over25 REAL,
            over35 REAL,
            btts REAL,
            confidence INTEGER,
            created TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # EXPERT PREDICTIONS
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expert_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            expert_name TEXT,
            score TEXT,
            comment TEXT,
            confidence INTEGER,
            created TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # JOURNAL (история обучения)
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
            created TEXT,
            FOREIGN KEY(match_id) REFERENCES matches(id)
        )
    """)

    # ===============================
    # FAJ MEMORY (обучающая память)
    # ===============================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faj_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            object TEXT,
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            created TEXT
        )
    """)

    conn.commit()
    conn.close()


# =====================================================
# DATABASE CLASS
# =====================================================

class FAJDatabase:

    def __init__(self):
        init_database()

    # =================================
    # STATUS
    # =================================
    def get_status(self):
        conn = get_connection()
        cursor = conn.cursor()

        tables = [
            "seasons", "rounds", "teams", "team_passports",
            "players", "matches", "predictions",
            "expert_predictions", "journal", "faj_memory"
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
    # SEASONS
    # =================================
    def create_season(self, name, league, year, status="active"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seasons (name, league, year, status, created)
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

    # =================================
    # ROUNDS
    # =================================
    def create_round(self, season_id, number, date_start="", date_end=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rounds (season_id, round_number, date_start, date_end, created)
            VALUES (?,?,?,?,?)
        """, (season_id, number, date_start, date_end, datetime.now().isoformat()))
        conn.commit()
        round_id = cursor.lastrowid
        conn.close()
        return round_id

    # =================================
    # TEAMS
    # =================================
    def add_team(self, name, league, country=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO teams (name, league, country, created)
            VALUES (?,?,?,?)
        """, (name, league, country, datetime.now().isoformat()))
        conn.commit()
        team_id = cursor.lastrowid
        conn.close()
        return team_id

    def get_team_id(self, name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    # =================================
    # TEAM PASSPORTS
    # =================================
    def update_passport(self, team_id, attack=50, defense=50, control=50,
                        press=50, tempo=50, transition=50, fitness=50,
                        mentality=50, coach_factor=50):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO team_passports
            (team_id, attack, defense, control, press, tempo,
             transition, fitness, mentality, coach_factor, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (team_id, attack, defense, control, press, tempo,
              transition, fitness, mentality, coach_factor,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_passport(self, team_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM team_passports WHERE team_id = ?", (team_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # =================================
    # MATCHES
    # =================================
    def add_match(self, round_id, home, away, date="",
                  xg_home=None, xg_away=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO matches (round_id, home_team, away_team, date,
                                 faj_xg_home, faj_xg_away, created)
            VALUES (?,?,?,?,?,?,?)
        """, (round_id, home, away, date, xg_home, xg_away,
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
    # PREDICTIONS
    # =================================
    def save_prediction(self, match_id, model_version, score_1, prob_1,
                        score_2, prob_2, score_3, prob_3,
                        home_win, draw, away_win,
                        over25, over35, btts, confidence):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions
            (match_id, model_version, score_1, probability_1,
             score_2, probability_2, score_3, probability_3,
             home_win, draw, away_win, over25, over35, btts,
             confidence, created)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (match_id, model_version, score_1, prob_1,
              score_2, prob_2, score_3, prob_3,
              home_win, draw, away_win, over25, over35, btts,
              confidence, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # =================================
    # MEMORY
    # =================================
    def add_memory(self, event_type, object_name, old_value, new_value, reason=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO faj_memory (event_type, object, old_value, new_value, reason, created)
            VALUES (?,?,?,?,?,?)
        """, (event_type, object_name, old_value, new_value, reason,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # =================================
    # JOURNAL
    # =================================
    def add_journal(self, match_id, faj_pred, expert_pred, actual, error_type, analysis=""):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal (match_id, faj_prediction, expert_prediction,
                                 actual_result, error_type, analysis, created)
            VALUES (?,?,?,?,?,?,?)
        """, (match_id, faj_pred, expert_pred, actual, error_type, analysis,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # =================================
    # EXPERT
    # =================================
    def add_expert_prediction(self, match_id, expert_name, score, comment, confidence):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expert_predictions (match_id, expert_name, score,
                                            comment, confidence, created)
            VALUES (?,?,?,?,?,?)
        """, (match_id, expert_name, score, comment, confidence,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()


# =====================================================
# AUTO INIT
# =====================================================

init_database()
