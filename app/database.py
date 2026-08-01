#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Database Layer (SQLite)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class FAJDatabase:
    
    def __init__(self, db_path: str = "data/faj.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    league TEXT,
                    api_football_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS passports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    attack INTEGER DEFAULT 50,
                    defense INTEGER DEFAULT 50,
                    control INTEGER DEFAULT 50,
                    efficiency INTEGER DEFAULT 50,
                    mentality INTEGER DEFAULT 50,
                    tempo INTEGER DEFAULT 50,
                    press INTEGER DEFAULT 50,
                    transition INTEGER DEFAULT 50,
                    flexibility INTEGER DEFAULT 50,
                    coach INTEGER DEFAULT 50,
                    form INTEGER DEFAULT 50,
                    depth INTEGER DEFAULT 50,
                    home_rating INTEGER DEFAULT 50,
                    away_rating INTEGER DEFAULT 50,
                    faj_rating REAL DEFAULT 50.0,
                    version TEXT DEFAULT '10.0',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES teams(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    home_team_id INTEGER NOT NULL,
                    away_team_id INTEGER NOT NULL,
                    league TEXT,
                    season INTEGER,
                    status TEXT,
                    home_goals INTEGER,
                    away_goals INTEGER,
                    xg_home REAL,
                    xg_away REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (home_team_id) REFERENCES teams(id),
                    FOREIGN KEY (away_team_id) REFERENCES teams(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    predicted_score TEXT,
                    confidence INTEGER,
                    model_version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    event_type TEXT NOT NULL,
                    observation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weights_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    attack REAL,
                    defense REAL,
                    control REAL,
                    efficiency REAL,
                    mentality REAL,
                    tempo REAL,
                    press REAL,
                    transition REAL,
                    flexibility REAL,
                    coach REAL,
                    form REAL,
                    depth REAL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    football_api_requests INTEGER DEFAULT 0,
                    football_data_requests INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def add_team(self, name: str, league: str = "RPL") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO teams (name, league) VALUES (?, ?)", (name, league))
            conn.commit()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_team_id(self, name: str) -> Optional[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def save_passport(self, team_name: str, data: Dict, version: str = "10.0"):
        team_id = self.get_team_id(team_name)
        if not team_id:
            team_id = self.add_team(team_name)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO passports (
                    team_id, attack, defense, control, efficiency, mentality,
                    tempo, press, transition, flexibility, coach, form, depth,
                    home_rating, away_rating, faj_rating, version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                team_id,
                data.get("attack", 50),
                data.get("defense", 50),
                data.get("control", 50),
                data.get("efficiency", 50),
                data.get("mentality", 50),
                data.get("tempo", 50),
                data.get("press", 50),
                data.get("transition", 50),
                data.get("flexibility", 50),
                data.get("coach", 50),
                data.get("form", 50),
                data.get("depth", 50),
                data.get("home_rating", 50),
                data.get("away_rating", 50),
                data.get("faj_rating", 50.0),
                version
            ))
            conn.commit()
    
    def save_match(self, match_data: Dict) -> int:
        home_id = self.get_team_id(match_data.get("home_team"))
        if not home_id:
            home_id = self.add_team(match_data.get("home_team"))
        away_id = self.get_team_id(match_data.get("away_team"))
        if not away_id:
            away_id = self.add_team(match_data.get("away_team"))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO matches (home_team_id, away_team_id, league, season, status, home_goals, away_goals, xg_home, xg_away)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                home_id, away_id,
                match_data.get("league"),
                match_data.get("season"),
                match_data.get("status"),
                match_data.get("home_goals"),
                match_data.get("away_goals"),
                match_data.get("xg_home"),
                match_data.get("xg_away")
            ))
            conn.commit()
            return cursor.lastrowid
    
    def save_prediction(self, match_id: int, predicted_score: str, confidence: int = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions (match_id, predicted_score, confidence, model_version)
                VALUES (?, ?, ?, ?)
            """, (match_id, predicted_score, confidence, "10.0"))
            conn.commit()
    
    def get_matches(self, limit: int = 100) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as home_team_name, t2.name as away_team_name
                FROM matches m
                LEFT JOIN teams t1 ON m.home_team_id = t1.id
                LEFT JOIN teams t2 ON m.away_team_id = t2.id
                ORDER BY m.created_at DESC LIMIT ?
            """, (limit,))
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_status(self) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM teams")
            teams = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM matches")
            matches = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM journal")
            journal = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM passports")
            passports = cursor.fetchone()[0]
            return {
                "teams": teams,
                "matches": matches,
                "journal": journal,
                "passports": passports,
                "db_path": self.db_path
            }
    
    def migrate_from_json(self, data_dir: str = "data") -> Dict:
        results = {"passports": 0, "matches": 0, "predictions": 0, "journal": 0, "weights": 0, "errors": []}
        
        passports_path = os.path.join(data_dir, "passports_2026.json")
        if os.path.exists(passports_path):
            try:
                with open(passports_path, 'r', encoding='utf-8') as f:
                    passports = json.load(f)
                for team, data in passports.items():
                    self.save_passport(team, data)
                    results["passports"] += 1
            except Exception as e:
                results["errors"].append(f"passports: {str(e)}")
        
        tour1_path = os.path.join(data_dir, "tour1_results.json")
        if os.path.exists(tour1_path):
            try:
                with open(tour1_path, 'r', encoding='utf-8') as f:
                    tour1 = json.load(f)
                for match_name, data in tour1.items():
                    if '-' in match_name:
                        home, away = match_name.split('-')
                    else:
                        home, away = match_name.split('–')
                    actual = data.get('actual', '')
                    hg, ag = None, None
                    if ':' in actual:
                        try:
                            hg, ag = map(int, actual.split(':'))
                        except:
                            pass
                    match_id = self.save_match({
                        "home_team": home,
                        "away_team": away,
                        "league": "RPL",
                        "season": 2026,
                        "status": "FT",
                        "home_goals": hg,
                        "away_goals": ag,
                        "xg_home": data.get('xg_home'),
                        "xg_away": data.get('xg_away')
                    })
                    results["matches"] += 1
                    faj_pred = data.get('faj', '')
                    if faj_pred:
                        self.save_prediction(match_id, faj_pred)
                        results["predictions"] += 1
            except Exception as e:
                results["errors"].append(f"tour1: {str(e)}")
        
        tour2_path = os.path.join(data_dir, "tour2_predictions.json")
        if os.path.exists(tour2_path):
            try:
                with open(tour2_path, 'r', encoding='utf-8') as f:
                    tour2 = json.load(f)
                for match_name, data in tour2.items():
                    if '-' in match_name:
                        home, away = match_name.split('-')
                    else:
                        home, away = match_name.split('–')
                    match_id = self.save_match({
                        "home_team": home,
                        "away_team": away,
                        "league": "RPL",
                        "season": 2026,
                        "status": "NS",
                        "xg_home": data.get('xg_home'),
                        "xg_away": data.get('xg_away')
                    })
                    results["matches"] += 1
                    faj_pred = data.get('faj', '')
                    if faj_pred:
                        self.save_prediction(match_id, faj_pred)
                        results["predictions"] += 1
            except Exception as e:
                results["errors"].append(f"tour2: {str(e)}")
        
        return results
    
    def increment_api_stats(self, source: str):
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_stats (date, football_api_requests, football_data_requests)
                VALUES (?, 0, 0)
                ON CONFLICT(date) DO UPDATE SET 
                    football_api_requests = football_api_requests + CASE WHEN ? = 'football_api' THEN 1 ELSE 0 END,
                    football_data_requests = football_data_requests + CASE WHEN ? = 'football_data' THEN 1 ELSE 0 END
            """, (today, source, source))
            conn.commit()
    
    def get_api_stats_today(self) -> Dict:
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT football_api_requests, football_data_requests FROM api_stats WHERE date = ?", (today,))
            row = cursor.fetchone()
            if row:
                return {"football_api": row[0], "football_data": row[1]}
            return {"football_api": 0, "football_data": 0}
