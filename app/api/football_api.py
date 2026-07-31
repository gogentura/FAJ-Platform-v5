#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - API Football Client
Поддерживает: РПЛ, АПЛ, Ла Лигу, Бундеслигу, Серию А, Лигу 1, ЛЧ, ЛЕ
"""

import requests
import time
from typing import Dict, List, Optional

from app.config import Config


class FootballAPI:
    
    def __init__(self):
        self.base_url = Config.BASE_URL_FOOTBALL_API
        self.token = Config.get_football_api_token()
        self.headers = {"x-apisports-key": self.token}
        self.last_request_time = 0
        self.min_request_interval = 6
    
    def _request(self, endpoint: str, params: dict = None) -> dict:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": True, "status_code": response.status_code, "message": response.text}
        except Exception as e:
            return {"error": True, "message": str(e)}
    
    # =========================================================
    # УНИВЕРСАЛЬНЫЕ МЕТОДЫ
    # =========================================================
    
    def get_fixtures(self, league: int, season: int, team: int = None,
                     date: str = None, from_date: str = None,
                     to_date: str = None, status: str = None) -> dict:
        params = {"league": league, "season": season}
        if team:
            params["team"] = team
        if date:
            params["date"] = date
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status
        return self._request("/fixtures", params)
    
    def get_team_stats(self, team_id: int, league: int = None, season: int = None) -> dict:
        params = {"team": team_id}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        return self._request("/teams/statistics", params)
    
    def get_team_squad(self, team_id: int) -> dict:
        return self._request("/players/squads", {"team": team_id})
    
    def get_injuries(self, league: int = None, team: int = None, season: int = None) -> dict:
        params = {}
        if league:
            params["league"] = league
        if team:
            params["team"] = team
        if season:
            params["season"] = season
        return self._request("/injuries", params)
    
    def get_standings(self, league: int, season: int) -> dict:
        return self._request("/standings", {"league": league, "season": season})
    
    def get_teams(self, league: int, season: int) -> dict:
        return self._request("/teams", {"league": league, "season": season})
    
    # =========================================================
    # МЕТОДЫ ПО ТУРНИРАМ
    # =========================================================
    
    def get_league_fixtures(self, league_key: str, season: int = None) -> dict:
        """Получить матчи лиги по её ключу (RPL, EPL, LALIGA, UCL, и т.д.)"""
        league_id = Config.get_api_id(league_key)
        if not season:
            season = Config.get_season(league_key)
        return self.get_fixtures(league=league_id, season=season)
    
    def get_league_standings(self, league_key: str, season: int = None) -> dict:
        league_id = Config.get_api_id(league_key)
        if not season:
            season = Config.get_season(league_key)
        return self.get_standings(league=league_id, season=season)
    
    def get_league_teams(self, league_key: str, season: int = None) -> dict:
        league_id = Config.get_api_id(league_key)
        if not season:
            season = Config.get_season(league_key)
        return self.get_teams(league=league_id, season=season)
    
    # =========================================================
    # МЕТОДЫ ДЛЯ КОНКРЕТНЫХ ТУРНИРОВ
    # =========================================================
    
    def get_rpl_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("RPL", season)
    
    def get_epl_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("EPL", season)
    
    def get_laliga_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("LALIGA", season)
    
    def get_seriea_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("SERIEA", season)
    
    def get_bundesliga_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("BUNDESLIGA", season)
    
    def get_ligue1_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("LIGUE1", season)
    
    def get_ucl_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("UCL", season)
    
    def get_uel_fixtures(self, season: int = None) -> dict:
        return self.get_league_fixtures("UEL", season)
    
    # =========================================================
    # ОБНОВЛЕНИЕ ВСЕХ ТУРНИРОВ (ОПЦИОНАЛЬНО)
    # =========================================================
    
    def update_all_leagues(self, season: int = None) -> dict:
        """Обновить данные по всем поддерживаемым турнирам"""
        results = {}
        for league_key in Config.get_all_leagues():
            try:
                fixtures = self.get_league_fixtures(league_key, season)
                results[league_key] = {
                    "status": "success",
                    "count": len(fixtures.get("response", []))
                }
            except Exception as e:
                results[league_key] = {
                    "status": "error",
                    "message": str(e)
                }
        return results
    
    def is_ready(self) -> bool:
        return self.token is not None and self.token != ""
