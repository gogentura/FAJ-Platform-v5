#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Football Data API Client
"""

import requests
import time

from app.config import Config
from app.api.ids import IDs


class FootballDataAPI:
    
    def __init__(self):
        self.base_url = Config.get_football_data_url()
        self.token = Config.get_football_data_token()
        self.headers = {"X-Auth-Token": self.token}
        self.last_request_time = 0
        self.min_request_interval = 3
    
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
    # ОСНОВНЫЕ МЕТОДЫ
    # =========================================================
    
    def get_matches(self, competition: str, season: int = None,
                    matchday: int = None, date_from: str = None,
                    date_to: str = None) -> dict:
        params = {"season": season}
        if matchday:
            params["matchday"] = matchday
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        return self._request(f"/competitions/{competition}/matches", params)
    
    def get_standings(self, competition: str, season: int = None) -> dict:
        params = {"season": season}
        return self._request(f"/competitions/{competition}/standings", params)
    
    def get_teams(self, competition: str, season: int = None) -> dict:
        params = {"season": season}
        return self._request(f"/competitions/{competition}/teams", params)
    
    def get_competitions(self) -> dict:
        return self._request("/competitions")
    
    def get_match(self, match_id: int) -> dict:
        return self._request(f"/matches/{match_id}")
    
    # =========================================================
    # МЕТОДЫ ПО ЛИГЕ
    # =========================================================
    
    def get_league_matches(self, league_key: str, season: int = None,
                           matchday: int = None, date_from: str = None,
                           date_to: str = None) -> dict:
        code = IDs.get_fd_code(league_key)
        if not season:
            season = Config.get_current_season()
        return self.get_matches(code, season, matchday, date_from, date_to)
    
    def get_league_standings(self, league_key: str, season: int = None) -> dict:
        code = IDs.get_fd_code(league_key)
        if not season:
            season = Config.get_current_season()
        return self.get_standings(code, season)
    
    def get_league_teams(self, league_key: str, season: int = None) -> dict:
        code = IDs.get_fd_code(league_key)
        if not season:
            season = Config.get_current_season()
        return self.get_teams(code, season)
    
    # =========================================================
    # МЕТОДЫ ДЛЯ КОНКРЕТНЫХ ЛИГ
    # =========================================================
    
    def get_rpl_matches(self, season: int = None, matchday: int = None) -> dict:
        return self.get_league_matches("RPL", season, matchday)
    
    def get_rpl_standings(self, season: int = None) -> dict:
        return self.get_league_standings("RPL", season)
    
    def get_rpl_teams(self, season: int = None) -> dict:
        return self.get_league_teams("RPL", season)
    
    def get_epl_matches(self, season: int = None, matchday: int = None) -> dict:
        return self.get_league_matches("EPL", season, matchday)
    
    def get_epl_standings(self, season: int = None) -> dict:
        return self.get_league_standings("EPL", season)
    
    def get_laliga_matches(self, season: int = None, matchday: int = None) -> dict:
        return self.get_league_matches("LALIGA", season, matchday)
    
    def get_laliga_standings(self, season: int = None) -> dict:
        return self.get_league_standings("LALIGA", season)
    
    def get_ucl_matches(self, season: int = None) -> dict:
        return self.get_league_matches("UCL", season)
    
    def is_ready(self) -> bool:
        return self.token is not None and self.token != ""
