#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Data Brain
Сбор данных из API и обновление паспортов команд
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from app.api.football_api import FootballAPI
from app.api.football_data_api import FootballDataAPI
from app.config import Config


class FAJDataBrain:
    """
    FAJ Data Brain — собирает данные из API, обновляет паспорта команд,
    сохраняет матчи и готовит данные для прогнозов.
    """
    
    def __init__(self):
        self.football_api = FootballAPI()
        self.football_data = FootballDataAPI()
        self.data_dir = Config.DATA_DIR
        
        # Загружаем текущие паспорта
        self.passports = self._load_passports()
        self.matches = self._load_matches()
    
    # =========================================================
    # ЗАГРУЗКА / СОХРАНЕНИЕ ДАННЫХ
    # =========================================================
    
    def _load_passports(self) -> Dict:
        """Загрузить паспорта команд из файла"""
        path = os.path.join(self.data_dir, "passports_2026.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_passports(self):
        """Сохранить паспорта команд"""
        path = os.path.join(self.data_dir, "passports_2026.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.passports, f, ensure_ascii=False, indent=2)
    
    def _load_matches(self) -> List:
        """Загрузить сохранённые матчи"""
        path = os.path.join(self.data_dir, "matches_history.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_matches(self):
        """Сохранить матчи"""
        path = os.path.join(self.data_dir, "matches_history.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.matches, f, ensure_ascii=False, indent=2)
    
    # =========================================================
    # ОБНОВЛЕНИЕ ПАСПОРТОВ
    # =========================================================
    
    def update_passport_from_stats(self, team_name: str, stats: Dict) -> Dict:
        """
        Обновить паспорт команды на основе статистики из API
        """
        if team_name not in self.passports:
            self.passports[team_name] = {}
        
        passport = self.passports[team_name]
        
        # Извлекаем ключевые показатели
        # В реальном API структура может отличаться, адаптируем
        if "attack" in stats:
            passport["attack"] = int(stats.get("attack", 50))
        if "defense" in stats:
            passport["defense"] = int(stats.get("defense", 50))
        if "control" in stats:
            passport["control"] = int(stats.get("control", 50))
        if "form" in stats:
            passport["form"] = int(stats.get("form", 50))
        
        # Добавляем метаданные
        passport["updated_at"] = datetime.now().isoformat()
        passport["source"] = "api-football"
        
        self._save_passports()
        return passport
    
    def calculate_form(self, team_name: str, matches: List) -> float:
        """
        Рассчитать форму команды на основе последних матчей
        """
        if not matches:
            return 50.0
        
        points = 0
        total = 0
        
        # Берём последние 5 матчей
        last_matches = matches[-5:]
        
        for match in last_matches:
            if match.get("home_team") == team_name:
                home_goals = match.get("home_goals", 0)
                away_goals = match.get("away_goals", 0)
                if home_goals > away_goals:
                    points += 3
                elif home_goals == away_goals:
                    points += 1
            elif match.get("away_team") == team_name:
                home_goals = match.get("home_goals", 0)
                away_goals = match.get("away_goals", 0)
                if away_goals > home_goals:
                    points += 3
                elif away_goals == home_goals:
                    points += 1
            total += 1
        
        if total == 0:
            return 50.0
        
        # Нормализуем в диапазон 0-100
        form_score = (points / (total * 3)) * 100
        return round(min(100, max(0, form_score)), 1)
    
    # =========================================================
    # СБОР ДАННЫХ ИЗ API
    # =========================================================
    
    def fetch_league_data(self, league_key: str) -> Dict:
        """
        Собрать данные по лиге из обоих API
        """
        result = {
            "league": league_key,
            "timestamp": datetime.now().isoformat(),
            "fixtures": [],
            "teams": [],
            "standings": []
        }
        
        # Получаем матчи из API-Football
        fixtures = self.football_api.get_league_fixtures(league_key)
        if not fixtures.get("error"):
            result["fixtures"] = fixtures.get("response", [])
        
        # Получаем команды из API-Football
        teams = self.football_api.get_league_teams(league_key)
        if not teams.get("error"):
            result["teams"] = teams.get("response", [])
        
        # Получаем таблицу из API-Football
        standings = self.football_api.get_league_standings(league_key)
        if not standings.get("error"):
            result["standings"] = standings.get("response", [])
        
        return result
    
    def update_team_passports_from_api(self, league_key: str) -> Dict:
        """
        Обновить паспорта всех команд в лиге на основе данных из API
        """
        data = self.fetch_league_data(league_key)
        updated = {}
        
        # Извлекаем команды из ответа API
        teams_data = data.get("teams", [])
        
        for team_data in teams_data:
            team_name = team_data.get("team", {}).get("name", "")
            if not team_name:
                continue
            
            # Получаем ID команды для дальнейших запросов
            team_id = team_data.get("team", {}).get("id")
            
            # Запрашиваем статистику команды
            stats = self.football_api.get_team_stats(
                team_id=team_id,
                league=Config.get_api_id(league_key)
            )
            
            if stats.get("error"):
                continue
            
            # Обновляем паспорт
            passport = self.update_passport_from_stats(team_name, stats)
            updated[team_name] = passport
        
        return updated
    
    def fetch_all_leagues(self) -> Dict:
        """
        Собрать данные по всем поддерживаемым лигам
        """
        results = {}
        for league_key in Config.get_all_leagues():
            try:
                results[league_key] = self.fetch_league_data(league_key)
            except Exception as e:
                results[league_key] = {"error": str(e)}
        return results
    
    # =========================================================
    # ПОЛНЫЙ ЦИКЛ ОБНОВЛЕНИЯ
    # =========================================================
    
    def full_update(self, league_keys: List[str] = None) -> Dict:
        """
        Полное обновление данных: все лиги или выбранные
        """
        if league_keys is None:
            league_keys = Config.get_all_leagues()
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "leagues": {},
            "passports_updated": 0,
            "matches_added": 0
        }
        
        for league_key in league_keys:
            try:
                # 1. Собираем данные
                data = self.fetch_league_data(league_key)
                results["leagues"][league_key] = {"status": "success", "matches": len(data.get("fixtures", []))}
                
                # 2. Обновляем паспорта
                updated = self.update_team_passports_from_api(league_key)
                results["passports_updated"] += len(updated)
                
                # 3. Сохраняем матчи
                fixtures = data.get("fixtures", [])
                for fixture in fixtures:
                    match = {
                        "league": league_key,
                        "home_team": fixture.get("teams", {}).get("home", {}).get("name", ""),
                        "away_team": fixture.get("teams", {}).get("away", {}).get("name", ""),
                        "date": fixture.get("fixture", {}).get("date", ""),
                        "status": fixture.get("fixture", {}).get("status", {}).get("short", ""),
                        "home_goals": fixture.get("goals", {}).get("home"),
                        "away_goals": fixture.get("goals", {}).get("away"),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.matches.append(match)
                
                results["matches_added"] += len(fixtures)
                
            except Exception as e:
                results["leagues"][league_key] = {"status": "error", "message": str(e)}
        
        # Сохраняем все изменения
        self._save_passports()
        self._save_matches()
        
        return results
    
    # =========================================================
    # СТАТУС
    # =========================================================
    
    def get_status(self) -> Dict:
        """Получить статус Data Brain"""
        return {
            "passports_count": len(self.passports),
            "matches_count": len(self.matches),
            "leagues_supported": Config.get_all_leagues(),
            "last_update": self.matches[-1].get("timestamp") if self.matches else None,
            "football_api_ready": self.football_api.is_ready(),
            "football_data_ready": self.football_data.is_ready()
        }


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    brain = FAJDataBrain()
    
    print("=" * 50)
    print("FAJ Data Brain v10.0 - Тест")
    print("=" * 50)
    
    status = brain.get_status()
    print(f"Паспортов: {status['passports_count']}")
    print(f"Матчей: {status['matches_count']}")
    print(f"API-Football готов: {status['football_api_ready']}")
    print(f"Football-data готов: {status['football_data_ready']}")
    
    if status['football_api_ready']:
        print("\nОбновление данных по РПЛ...")
        result = brain.update_team_passports_from_api("RPL")
        print(f"Обновлено команд: {len(result)}")
