#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - ID справочник
"""


class IDs:
    """Справочник ID для FAJ v10.0"""
    
    LEAGUES = {
        "RPL": {
            "name": "Российская Премьер-Лига",
            "api_football_id": 235,
            "football_data_code": "RPL",
            "country": "Россия",
            "base_xg": 1.35,
            "home_advantage": 1.12
        },
        "EPL": {
            "name": "Английская Премьер-Лига",
            "api_football_id": 39,
            "football_data_code": "PL",
            "country": "Англия",
            "base_xg": 1.45,
            "home_advantage": 1.15
        },
        "LALIGA": {
            "name": "La Liga",
            "api_football_id": 140,
            "football_data_code": "PD",
            "country": "Испания",
            "base_xg": 1.40,
            "home_advantage": 1.13
        }
    }
    
    # ID команд РПЛ в API-Football
    RPL_TEAMS = {
        "Зенит": 788,
        "Спартак": 780,
        "ЦСКА": 790,
        "Динамо М": 789,
        "Краснодар": 798,
        "Локомотив": 787,
        "Ростов": 795,
        "Рубин": 797,
        "Ахмат": 793,
        "Оренбург": 796,
        "Крылья Советов": 791,
        "Факел": 804,
        "Балтика": 799,
        "Динамо Мх": 803,
        "Акрон": 11386,
        "Родина": 11387
    }
    
    @classmethod
    def get_team_id(cls, team_name: str) -> int:
        return cls.RPL_TEAMS.get(team_name, 0)
    
    @classmethod
    def get_all_teams(cls) -> list:
        return list(cls.RPL_TEAMS.keys())
    
    @classmethod
    def get_api_id(cls, league_key: str) -> int:
        return cls.LEAGUES.get(league_key, {}).get("api_football_id", 235)
    
    @classmethod
    def get_fd_code(cls, league_key: str) -> str:
        return cls.LEAGUES.get(league_key, {}).get("football_data_code", "RPL")
