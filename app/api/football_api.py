#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - API Football Client
"""

import requests
import time
import streamlit as st
import os

from app.api.ids import IDs


class FootballAPI:
    
    def __init__(self):
        # Прямое получение токена из Secrets
        self.token = self._get_token()
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {"x-apisports-key": self.token}
        self.last_request_time = 0
        self.min_request_interval = 6
    
    def _get_token(self):
        """Получить токен из Secrets или переменных окружения"""
        try:
            return st.secrets["FOOTBALL_API_TOKEN"]
        except:
            return os.getenv("FOOTBALL_API_TOKEN", "")
    
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
    
    def get_fixtures(self, league: int, season: int, team: int = None,
                     date: str = None, from_date: str = None,
                     to_date: str = None, status: str = None,
                     last: int = None) -> dict:
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
        if last:
            params["last"] = last
        return self._request("/fixtures", params)
    
    def get_team_stats(self, team_id: int, league: int = None, season: int = None) -> dict:
        params = {"team": team_id}
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        return self._request("/teams/statistics", params)
    
    def get_team_info(self, team_id: int) -> dict:
        return self._request("/teams", {"id": team_id})
    
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
    
    def get_league_fixtures(self, league_key: str, season: int = None) -> dict:
        league_id = IDs.get_api_id(league_key)
        if not season:
            season = 2026
        return self.get_fixtures(league=league_id, season=season)
    
    def get_league_standings(self, league_key: str, season: int = None) -> dict:
        league_id = IDs.get_api_id(league_key)
        if not season:
            season = 2026
        return self.get_standings(league=league_id, season=season)
    
    def get_league_teams(self, league_key: str, season: int = None) -> dict:
        league_id = IDs.get_api_id(league_key)
        if not season:
            season = 2026
        return self.get_teams(league=league_id, season=season)
    
    def get_team_stats_by_name(self, team_name: str, league_key: str = "RPL", season: int = None) -> dict:
        team_id = IDs.get_team_id(team_name)
        if team_id == 0:
            return {"error": True, "message": f"Команда {team_name} не найдена"}
        league_id = IDs.get_api_id(league_key)
        if not season:
            season = 2026
        return self.get_team_stats(team_id=team_id, league=league_id, season=season)
    
    def get_team_fixtures(self, team_name: str, league_key: str = "RPL", 
                          season: int = None, status: str = None, last: int = 5) -> dict:
        team_id = IDs.get_team_id(team_name)
        if team_id == 0:
            return {"error": True, "message": f"Команда {team_name} не найдена"}
        league_id = IDs.get_api_id(league_key)
        if not season:
            season = 2026
        return self.get_fixtures(league=league_id, season=season, team=team_id, status=status, last=last)
    
    def is_ready(self) -> bool:
        return self.token is not None and self.token != ""
