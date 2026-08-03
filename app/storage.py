#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11
Storage Layer

Единый слой работы с базой данных.
Все страницы обращаются к storage.py, а не напрямую к database.py.
"""

from app.database import FAJDatabase
from datetime import datetime


class FAJStorage:
    """Единый слой хранения данных FAJ"""

    def __init__(self):
        self.db = FAJDatabase()

    # =========================================================
    # SEASONS
    # =========================================================

    def get_seasons(self):
        """Получить все сезоны"""
        return self.db.get_seasons()

    def create_season(self, name, league, year):
        """Создать новый сезон"""
        return self.db.create_season(name, league, year)

    # =========================================================
    # ROUNDS
    # =========================================================

    def get_rounds(self, season_id=None):
        """Получить туры (по сезону или все)"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        if season_id:
            cursor.execute("SELECT * FROM rounds WHERE season_id = ? ORDER BY round_number", (season_id,))
        else:
            cursor.execute("SELECT * FROM rounds ORDER BY id DESC")
        data = cursor.fetchall()
        conn.close()
        return data

    def create_round(self, season_id, number):
        """Создать новый тур"""
        return self.db.create_round(season_id, number)

    # =========================================================
    # TEAMS
    # =========================================================

    def get_teams(self, league=None):
        """Получить команды (по лиге или все)"""
        conn = self.db._get_connection()
        cursor = conn.cursor()
        if league:
            cursor.execute("SELECT * FROM teams WHERE league = ? ORDER BY name", (league,))
        else:
            cursor.execute("SELECT * FROM teams ORDER BY name")
        data = cursor.fetchall()
        conn.close()
        return data

    def get_team_id(self, name):
        """Получить ID команды по названию"""
        return self.db.get_team_id(name)

    def add_team(self, name, league, country=""):
        """Добавить новую команду"""
        return self.db.add_team(name, league, country)

    # =========================================================
    # TEAM PASSPORTS
    # =========================================================

    def get_passport(self, team_id):
        """Получить паспорт команды"""
        return self.db.get_passport(team_id)

    def update_passport(self, team_id, **kwargs):
        """Обновить паспорт команды"""
        return self.db.update_passport(team_id, **kwargs)

    # =========================================================
    # MATCHES
    # =========================================================

    def get_matches(self, round_id=None):
        """Получить матчи (по туру или все)"""
        return self.db.get_matches(round_id)

    def add_match(self, round_id, home, away, date="", xg_home=None, xg_away=None):
        """Добавить матч"""
        return self.db.add_match(round_id, home, away, date, xg_home, xg_away)

    def update_result(self, match_id, home_score, away_score):
        """Обновить результат матча"""
        return self.db.update_result(match_id, home_score, away_score)

    # =========================================================
    # PREDICTIONS
    # =========================================================

    def save_prediction(self, match_id, prediction_data):
        """Сохранить прогноз FAJ"""
        return self.db.save_prediction(
            match_id,
            prediction_data.get("model_version", "v11"),
            prediction_data.get("score_1", ""),
            prediction_data.get("probability_1", 0),
            prediction_data.get("score_2", ""),
            prediction_data.get("probability_2", 0),
            prediction_data.get("score_3", ""),
            prediction_data.get("probability_3", 0),
            prediction_data.get("home_win", 0),
            prediction_data.get("draw", 0),
            prediction_data.get("away_win", 0),
            prediction_data.get("over25", 0),
            prediction_data.get("over35", 0),
            prediction_data.get("btts", 0),
            prediction_data.get("confidence", 0)
        )

    # =========================================================
    # EXPERT
    # =========================================================

    def save_expert_prediction(self, match_id, expert_name, score, comment, confidence):
        """Сохранить экспертный прогноз"""
        return self.db.add_expert_prediction(match_id, expert_name, score, comment, confidence)

    # =========================================================
    # JOURNAL
    # =========================================================

    def add_journal(self, match_id, faj_pred, expert_pred, actual, error_type, analysis=""):
        """Добавить запись в журнал обучения"""
        return self.db.add_journal(match_id, faj_pred, expert_pred, actual, error_type, analysis)

    # =========================================================
    # MEMORY
    # =========================================================

    def add_memory(self, event_type, object_name, old_value, new_value, reason=""):
        """Добавить запись в память FAJ"""
        return self.db.add_memory(event_type, object_name, old_value, new_value, reason)

    # =========================================================
    # STATUS
    # =========================================================

    def get_status(self):
        """Получить статус системы"""
        return self.db.get_status()


# =========================================================
# SINGLETON
# =========================================================

_storage = None

def get_storage():
    """Получить экземпляр хранилища (Singleton)"""
    global _storage
    if _storage is None:
        _storage = FAJStorage()
    return _storage
