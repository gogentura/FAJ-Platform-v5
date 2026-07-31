#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Config
Безопасное хранение токенов через Streamlit Secrets
"""

import streamlit as st
import os


class Config:
    """Конфигурация FAJ Platform"""
    
    # =========================================================
    # API TOKENS (из Streamlit Secrets)
    # =========================================================
    
    @staticmethod
    def get_football_api_token():
        try:
            return st.secrets["FOOTBALL_API_TOKEN"]
        except:
            return os.getenv("FOOTBALL_API_TOKEN", "")
    
    @staticmethod
    def get_football_data_token():
        try:
            return st.secrets["FOOTBALL_DATA_TOKEN"]
        except:
            return os.getenv("FOOTBALL_DATA_TOKEN", "")
    
    # =========================================================
    # ТУРНИРЫ (поддерживаемые лиги и турниры)
    # =========================================================
    
    LEAGUES = {
        "RPL": {
            "name": "Российская Премьер-Лига",
            "api_football_id": 235,
            "football_data_code": "RL",
            "country": "Россия",
            "base_xg": 1.35,
            "home_advantage": 1.12,
            "season": 2026
        },
        "EPL": {
            "name": "Английская Премьер-Лига",
            "api_football_id": 39,
            "football_data_code": "PL",
            "country": "Англия",
            "base_xg": 1.45,
            "home_advantage": 1.15,
            "season": 2026
        },
        "LALIGA": {
            "name": "La Liga",
            "api_football_id": 140,
            "football_data_code": "PD",
            "country": "Испания",
            "base_xg": 1.40,
            "home_advantage": 1.13,
            "season": 2026
        },
        "SERIEA": {
            "name": "Серия А",
            "api_football_id": 135,
            "football_data_code": "SA",
            "country": "Италия",
            "base_xg": 1.38,
            "home_advantage": 1.14,
            "season": 2026
        },
        "BUNDESLIGA": {
            "name": "Бундеслига",
            "api_football_id": 78,
            "football_data_code": "BL1",
            "country": "Германия",
            "base_xg": 1.42,
            "home_advantage": 1.16,
            "season": 2026
        },
        "LIGUE1": {
            "name": "Лига 1",
            "api_football_id": 61,
            "football_data_code": "FL1",
            "country": "Франция",
            "base_xg": 1.36,
            "home_advantage": 1.12,
            "season": 2026
        },
        "UCL": {
            "name": "Лига Чемпионов УЕФА",
            "api_football_id": 2,
            "football_data_code": "CL",
            "country": "Европа",
            "base_xg": 1.50,
            "home_advantage": 1.10,
            "season": 2026
        },
        "UEL": {
            "name": "Лига Европы УЕФА",
            "api_football_id": 3,
            "football_data_code": "EL",
            "country": "Европа",
            "base_xg": 1.40,
            "home_advantage": 1.08,
            "season": 2026
        }
    }
    
    # =========================================================
    # ЛИГИ ПО УМОЛЧАНИЮ (для быстрого доступа)
    # =========================================================
    
    @staticmethod
    def get_league(league_key: str) -> dict:
        return Config.LEAGUES.get(league_key, Config.LEAGUES["RPL"])
    
    @staticmethod
    def get_all_leagues() -> list:
        return list(Config.LEAGUES.keys())
    
    @staticmethod
    def get_league_names() -> dict:
        return {key: data["name"] for key, data in Config.LEAGUES.items()}
    
    @staticmethod
    def get_api_id(league_key: str) -> int:
        return Config.LEAGUES.get(league_key, {}).get("api_football_id", 235)
    
    @staticmethod
    def get_fd_code(league_key: str) -> str:
        return Config.LEAGUES.get(league_key, {}).get("football_data_code", "RL")
    
    @staticmethod
    def get_base_xg(league_key: str) -> float:
        return Config.LEAGUES.get(league_key, {}).get("base_xg", 1.35)
    
    @staticmethod
    def get_home_advantage(league_key: str) -> float:
        return Config.LEAGUES.get(league_key, {}).get("home_advantage", 1.12)
    
    @staticmethod
    def get_season(league_key: str) -> int:
        return Config.LEAGUES.get(league_key, {}).get("season", 2026)
    
    # =========================================================
    # БАЗОВЫЕ НАСТРОЙКИ
    # =========================================================
    
    DEFAULT_LEAGUE = "RPL"
    BASE_URL_FOOTBALL_API = "https://v3.football.api-sports.io"
    BASE_URL_FOOTBALL_DATA = "https://api.football-data.org/v4"
    
    MAX_REQUESTS_PER_DAY = 100
    MAX_REQUESTS_PER_MINUTE = 10
    
    DATA_DIR = "data"
    
    @staticmethod
    def is_ready() -> bool:
        return (
            Config.get_football_api_token() != "" and
            Config.get_football_data_token() != ""
        )
    
    @staticmethod
    def get_status() -> dict:
        return {
            "football_api_token": bool(Config.get_football_api_token()),
            "football_data_token": bool(Config.get_football_data_token()),
            "leagues": list(Config.LEAGUES.keys()),
            "ready": Config.is_ready()
        }
