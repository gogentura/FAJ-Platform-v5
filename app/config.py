#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Config
Единый источник конфигурации из Streamlit Secrets
"""

import streamlit as st
import os


class Config:
    """Конфигурация FAJ Platform v10.0 — всё из Secrets"""
    
    # =========================================================
    # API НАСТРОЙКИ (из Streamlit Secrets)
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
    
    @staticmethod
    def get_api_football_url():
        try:
            return st.secrets["API_FOOTBALL_URL"]
        except:
            return os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
    
    @staticmethod
    def get_football_data_url():
        try:
            return st.secrets["FOOTBALL_DATA_URL"]
        except:
            return os.getenv("FOOTBALL_DATA_URL", "https://api.football-data.org/v4")
    
    @staticmethod
    def get_current_season():
        try:
            return int(st.secrets["CURRENT_SEASON"])
        except:
            return int(os.getenv("CURRENT_SEASON", 2026))
    
    @staticmethod
    def get_cache_days():
        try:
            return int(st.secrets["CACHE_DAYS"])
        except:
            return int(os.getenv("CACHE_DAYS", 7))
    
    @staticmethod
    def get_model_version():
        try:
            return st.secrets["MODEL_VERSION"]
        except:
            return os.getenv("MODEL_VERSION", "10.0")
    
    @staticmethod
    def get_max_requests_per_day():
        try:
            return int(st.secrets["MAX_REQUESTS_PER_DAY"])
        except:
            return int(os.getenv("MAX_REQUESTS_PER_DAY", 100))
    
    # =========================================================
    # ПРОВЕРКА ГОТОВНОСТИ
    # =========================================================
    
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
            "api_football_url": Config.get_api_football_url(),
            "football_data_url": Config.get_football_data_url(),
            "current_season": Config.get_current_season(),
            "cache_days": Config.get_cache_days(),
            "model_version": Config.get_model_version(),
            "max_requests_per_day": Config.get_max_requests_per_day(),
            "ready": Config.is_ready()
        }
