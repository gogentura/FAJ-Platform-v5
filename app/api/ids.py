#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - ID справочник
ID команд, лиг и турниров
"""


class IDs:
    """Справочник ID для FAJ v10.0"""
    
    # =========================================================
    # ЛИГИ (API-Football ID)
    # =========================================================
    
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
        },
        "SERIEA": {
            "name": "Серия А",
            "api_football_id": 135,
            "football_data_code": "SA",
            "country": "Италия",
            "base_xg": 1.38,
            "home_advantage": 1.14
        },
        "BUNDESLIGA": {
            "name": "Бундеслига",
            "api_football_id": 78,
            "football_data_code": "BL1",
            "country": "Германия",
            "base_xg": 1.42,
            "home_advantage": 1.16
        },
        "LIGUE1": {
            "name": "Лига 1",
            "api_football_id": 61,
            "football_data_code": "FL1",
            "country": "Франция",
            "base_xg": 1.36,
            "home_advantage": 1.12
        },
        "UCL": {
            "name": "Лига Чемпионов УЕФА",
            "api_football_id": 2,
            "football_data_code": "CL",
            "country": "Европа",
            "base_xg": 1.50,
            "home_advantage": 1.10
        },
        "UEL": {
            "name": "Лига Европы УЕФА",
            "api_football_id": 3,
            "football_data_code": "EL",
            "country": "Европа",
            "base_xg": 1.40,
            "home_advantage": 1.08
        }
    }
    
    # =========================================================
    # КОМАНДЫ РПЛ (API-Football ID)
    # =========================================================
    
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
    
    # =========================================================
    # МЕТОДЫ
    # =========================================================
    
    @classmethod
    def get_league(cls, key: str) -> dict:
        return cls.LEAGUES.get(key, cls.LEAGUES["RPL"])
    
    @classmethod
    def get_all_leagues(cls) -> list:
        return list(cls.LEAGUES.keys())
    
    @classmethod
    def get_league_names(cls) -> dict:
        return {key: data["name"] for key, data in cls.LEAGUES.items()}
    
    @classmethod
    def get_api_id(cls, league_key: str) -> int:
        return cls.LEAGUES.get(league_key, {}).get("api_football_id", 235)
    
    @classmethod
    def get_fd_code(cls, league_key: str) -> str:
        return cls.LEAGUES.get(league_key, {}).get("football_data_code", "RPL")
    
    @classmethod
    def get_base_xg(cls, league_key: str) -> float:
        return cls.LEAGUES.get(league_key, {}).get("base_xg", 1.35)
    
    @classmethod
    def get_home_advantage(cls, league_key: str) -> float:
        return cls.LEAGUES.get(league_key, {}).get("home_advantage", 1.12)
    
    @classmethod
    def get_team_id(cls, team_name: str) -> int:
        return cls.RPL_TEAMS.get(team_name, 0)
    
    @classmethod
    def get_all_teams(cls) -> list:
        return list(cls.RPL_TEAMS.keys())
