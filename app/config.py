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
        """Получить токен API-Football"""
        try:
            return st.secrets["FOOTBALL_API_TOKEN"]
        except:
            # Для локальной разработки
            return os.getenv("FOOTBALL_API_TOKEN", "")
    
    @staticmethod
    def get_football_data_token():
        """Получить токен Football-data.org"""
        try:
            return st.secrets["FOOTBALL_DATA_TOKEN"]
        except:
            # Для локальной разработки
            return os.getenv("FOOTBALL_DATA_TOKEN", "")
    
    # =========================================================
    # НАСТРОЙКИ
    # =========================================================
    
    LEAGUE_RPL = 235  # ID Российской Премьер-Лиги в API-Football
    SEASON_RPL = 2026  # Сезон 2026/27
    COMPETITION_RPL = "RL"  # Код РПЛ в Football-data.org
    
    BASE_URL_FOOTBALL_API = "https://v3.football.api-sports.io"
    BASE_URL_FOOTBALL_DATA = "https://api.football-data.org/v4"
    
    # Лимиты API
    MAX_REQUESTS_PER_DAY = 100
    MAX_REQUESTS_PER_MINUTE = 10
    
    # Пути к данным
    DATA_DIR = "data"
    
    @staticmethod
    def is_ready() -> bool:
        """Проверка, что все токены настроены"""
        return (
            Config.get_football_api_token() != "" and
            Config.get_football_data_token() != ""
        )
    
    @staticmethod
    def get_status() -> dict:
        """Статус конфигурации"""
        return {
            "football_api_token": bool(Config.get_football_api_token()),
            "football_data_token": bool(Config.get_football_data_token()),
            "league_rpl": Config.LEAGUE_RPL,
            "season_rpl": Config.SEASON_RPL,
            "ready": Config.is_ready()
        }
