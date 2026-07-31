#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Database Layer (SQLite)
Память FAJ: команды, матчи, паспорта, прогнозы, журнал
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.config import Config


class FAJDatabase:
    """SQLite база данных FAJ — локальная память"""
    
    def __init__(self, db_path: str = "data/faj.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()
    
    def _get_connection(self):
        """Получить подключение к БД"""
        return sqlite3.connect(self.db_path)
    
    def init_tables(self):
        """Создать все таблицы"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # =========================================================
            # 1. КОМАНДЫ
            # =========================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    league TEXT,
                    country TEXT,
                    api_football_id INTEGER,
                    football_data_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # =========================================================
            # 2. ПАСПОРТЫ КОМАНД (FAJ Rating)
            # =========================================================
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
                    FOREIGN KEY (team_id) REFERENCES teams(id),
                    UNIQUE(team_id, version)
                )
            """)
            
            # =========================================================
            # 3. МАТЧИ
            # =========================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    home_team_id INTEGER NOT NULL,
                    away_team_id INTEGER NOT NULL,
                    league TEXT,
                    season INTEGER,
                    matchday INTEGER,
                    date TIMESTAMP,
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
            
            # =========================================================
            # 4. ПРОГНОЗЫ
            # =========================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    home_win_prob REAL,
                    draw_prob REAL,
                    away_win_prob REAL,
                    predicted_score TEXT,
                    confidence INTEGER,
                    model_version TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id)
                )
            """)
            
            # =========================================================
            # 5. ЖУРНАЛ ОШИБОК (Journal / Learning Memory)
            # =========================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER,
                    prediction_id INTEGER,
                    event_type TEXT NOT NULL,
                    category TEXT,
                    observation TEXT,
                    conclusion TEXT,
                    action TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches(id),
                    FOREIGN KEY (prediction_id) REFERENCES predictions(id)
                )
            """)
            
            # =========================================================
            # 6. ИСТОРИЯ ВЕСОВ
            # =========================================================
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
            
            # =========================================================
            # 7. API КЭШ
            # =========================================================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    params TEXT,
                    response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            
            # =========================================================
            # 8. СТАТИСТИКА ЗАПРОСОВ API
            # =========================================================
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
    
    # =========================================================
    # РАБОТА С КОМАНДАМИ
    # =========================================================
    
    def add_team(self, name: str, league: str = "RPL", 
                 api_football_id: int = None, football_data_id: int = None) -> int:
        """Добавить команду в БД"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO teams (name, league, api_football_id, football_data_id)
                VALUES (?, ?, ?, ?)
            """, (name, league, api_football_id, football_data_id))
            conn.commit()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_team_id(self, name: str) -> Optional[int]:
        """Получить ID команды по названию"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM teams WHERE name = ?", (name,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_all_teams(self, league: str = None) -> List[Dict]:
        """Получить все команды"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if league:
                cursor.execute("SELECT * FROM teams WHERE league = ?", (league,))
            else:
                cursor.execute("SELECT * FROM teams")
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # =========================================================
    # РАБОТА С ПАСПОРТАМИ
    # =========================================================
    
    def save_passport(self, team_name: str, passport_data: Dict, version: str = "10.0"):
        """Сохранить паспорт команды"""
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
                passport_data.get("attack", 50),
                passport_data.get("defense", 50),
                passport_data.get("control", 50),
                passport_data.get("efficiency", 50),
                passport_data.get("mentality", 50),
                passport_data.get("tempo", 50),
                passport_data.get("press", 50),
                passport_data.get("transition", 50),
                passport_data.get("flexibility", 50),
                passport_data.get("coach", 50),
                passport_data.get("form", 50),
                passport_data.get("depth", 50),
                passport_data.get("home_rating", 50),
                passport_data.get("away_rating", 50),
                passport_data.get("faj_rating", 50.0),
                version
            ))
            conn.commit()
    
    def get_passport(self, team_name: str, version: str = "10.0") -> Optional[Dict]:
        """Получить паспорт команды"""
        team_id = self.get_team_id(team_name)
        if not team_id:
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM passports WHERE team_id = ? AND version = ?
            """, (team_id, version))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    # =========================================================
    # РАБОТА С МАТЧАМИ
    # =========================================================
    
    def save_match(self, match_data: Dict) -> int:
        """Сохранить матч"""
        home_team_id = self.get_team_id(match_data.get("home_team"))
        if not home_team_id:
            home_team_id = self.add_team(match_data.get("home_team"))
        
        away_team_id = self.get_team_id(match_data.get("away_team"))
        if not away_team_id:
            away_team_id = self.add_team(match_data.get("away_team"))
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO matches (
                    home_team_id, away_team_id, league, season, matchday,
                    date, status, home_goals, away_goals, xg_home, xg_away
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                home_team_id, away_team_id,
                match_data.get("league"),
                match_data.get("season"),
                match_data.get("matchday"),
                match_data.get("date"),
                match_data.get("status"),
                match_data.get("home_goals"),
                match_data.get("away_goals"),
                match_data.get("xg_home"),
                match_data.get("xg_away")
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_matches(self, limit: int = 50) -> List[Dict]:
        """Получить последние матчи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, 
                       t1.name as home_team_name, 
                       t2.name as away_team_name
                FROM matches m
                LEFT JOIN teams t1 ON m.home_team_id = t1.id
                LEFT JOIN teams t2 ON m.away_team_id = t2.id
                ORDER BY m.date DESC
                LIMIT ?
            """, (limit,))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # =========================================================
    # РАБОТА С ПРОГНОЗАМИ
    # =========================================================
    
    def save_prediction(self, match_id: int, prediction_data: Dict) -> int:
        """Сохранить прогноз"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions (
                    match_id, home_win_prob, draw_prob, away_win_prob,
                    predicted_score, confidence, model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id,
                prediction_data.get("home_win", 0),
                prediction_data.get("draw", 0),
                prediction_data.get("away_win", 0),
                prediction_data.get("predicted_score"),
                prediction_data.get("confidence"),
                prediction_data.get("model_version", "10.0")
            ))
            conn.commit()
            return cursor.lastrowid
    
    # =========================================================
    # РАБОТА С ЖУРНАЛОМ
    # =========================================================
    
    def add_journal_entry(self, entry: Dict) -> int:
        """Добавить запись в журнал"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO journal (
                    match_id, prediction_id, event_type, category,
                    observation, conclusion, action, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.get("match_id"),
                entry.get("prediction_id"),
                entry.get("event_type"),
                entry.get("category"),
                entry.get("observation"),
                entry.get("conclusion"),
                entry.get("action"),
                entry.get("confidence")
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_journal(self, limit: int = 50) -> List[Dict]:
        """Получить последние записи журнала"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM journal
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # =========================================================
    # РАБОТА С ВЕСАМИ
    # =========================================================
    
    def save_weights(self, weights: Dict, version: str = "10.0", reason: str = None):
        """Сохранить историю весов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO weights_history (
                    version, attack, defense, control, efficiency,
                    mentality, tempo, press, transition, flexibility,
                    coach, form, depth, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version,
                weights.get("attack", 0.18),
                weights.get("defense", 0.18),
                weights.get("control", 0.15),
                weights.get("efficiency", 0.12),
                weights.get("mentality", 0.10),
                weights.get("tempo", 0.07),
                weights.get("press", 0.05),
                weights.get("transition", 0.05),
                weights.get("flexibility", 0.05),
                weights.get("coach", 0.05),
                weights.get("form", 0.03),
                weights.get("depth", 0.02),
                reason
            ))
            conn.commit()
    
    def get_weights_history(self) -> List[Dict]:
        """Получить историю весов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM weights_history ORDER BY created_at DESC")
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # =========================================================
    # РАБОТА С API КЭШЕМ
    # =========================================================
    
    def cache_api_response(self, endpoint: str, params: Dict, response: Dict, expires_in_hours: int = 24):
        """Сохранить ответ API в кэш"""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO api_cache (
                    endpoint, params, response, expires_at
                ) VALUES (?, ?, ?, datetime('now', ?))
            """, (
                endpoint,
                json.dumps(params),
                json.dumps(response),
                f'+{expires_in_hours} hours'
            ))
            conn.commit()
    
    def get_cached_api_response(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Получить ответ API из кэша"""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT response FROM api_cache
                WHERE endpoint = ? AND params = ? AND expires_at > datetime('now')
                ORDER BY created_at DESC LIMIT 1
            """, (endpoint, json.dumps(params)))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    # =========================================================
    # РАБОТА СО СТАТИСТИКОЙ API
    # =========================================================
    
    def increment_api_stats(self, source: str):
        """Увеличить счётчик запросов к API"""
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
        """Получить статистику запросов за сегодня"""
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT football_api_requests, football_data_requests
                FROM api_stats WHERE date = ?
            """, (today,))
            row = cursor.fetchone()
            if row:
                return {
                    "football_api": row[0],
                    "football_data": row[1]
                }
            return {"football_api": 0, "football_data": 0}
    
    # =========================================================
    # СТАТУС БАЗЫ ДАННЫХ
    # =========================================================
    
    def get_status(self) -> Dict:
        """Получить статус БД"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM teams")
            teams_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM matches")
            matches_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM journal")
            journal_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM passports")
            passports_count = cursor.fetchone()[0]
            
            return {
                "teams": teams_count,
                "matches": matches_count,
                "journal": journal_count,
                "passports": passports_count,
                "db_path": self.db_path
            }
