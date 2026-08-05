#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Config

Единый центр управления всей платформой.
Все параметры модели в одном месте.
=====================================================
"""

from datetime import datetime


class Config:
    """Центральная конфигурация FAJ Platform v12.0"""

    # ============================================================
    # VERSIONS
    # ============================================================

    PLATFORM_VERSION = "12.0"
    CORE_VERSION = "7.3"
    PIPELINE_VERSION = "1.9"           # синхронизировано с prediction_pipeline.py
    MODEL_VERSION = "12.0"
    PASSPORT_VERSION = "1.4"

    # ============================================================
    # XG ENGINE
    # ============================================================

    XG_MIN = 0.10
    XG_MAX = 4.00
    XG_LEAGUE_MEAN = 1.35
    XG_SCALE = 2.5
    HOME_ADVANTAGE = 1.08

    # ============================================================
    # SEASON FACTORS (коэффициенты, а не даты)
    # ============================================================

    SEASON_FACTOR_START = 0.90
    SEASON_FACTOR_EARLY = 0.95
    SEASON_FACTOR_MID = 1.00
    SEASON_FACTOR_END = 1.05

    # ============================================================
    # POISSON
    # ============================================================

    MAX_GOALS = 8

    # ============================================================
    # MONTE CARLO
    # ============================================================

    MONTE_CARLO_ITERATIONS = 10000
    MONTE_CARLO_REPRODUCIBLE = True

    # ============================================================
    # MODEL AGREEMENT
    # ============================================================

    AGREEMENT_WEIGHT_HOME = 0.45
    AGREEMENT_WEIGHT_DRAW = 0.25
    AGREEMENT_WEIGHT_AWAY = 0.30

    # ============================================================
    # FAJ RATING
    # ============================================================

    RATING_MIN = 0
    RATING_MAX = 100
    PLAYER_WEIGHT = 0.20
    TEAM_WEIGHT = 0.80

    # Веса для расчёта FAJ Rating
    RATING_WEIGHTS = {
        "attack": 0.18,
        "defense": 0.18,
        "control": 0.15,
        "efficiency": 0.12,
        "mentality": 0.10,
        "tempo": 0.07,
        "press": 0.05,
        "transition": 0.05,
        "coach": 0.05,
        "form": 0.05
    }

    # ============================================================
    # TOURNAMENT DNA
    # ============================================================

    TOURNAMENT_FACTORS = {
        "RPL": {
            "goal_factor": 0.95,
            "physicality": 1.05,
            "tempo": 0.90
        },
        "EPL": {
            "goal_factor": 1.05,
            "physicality": 1.00,
            "tempo": 1.10
        },
        "La Liga": {
            "goal_factor": 1.00,
            "technical": 1.10,
            "tempo": 0.95
        },
        "UCL": {
            "goal_factor": 1.05,
            "experience": 1.10,
            "tempo": 1.00
        }
    }

    # ============================================================
    # DEFAULTS
    # ============================================================

    DEFAULT_HOME_PROB = 0.33
    DEFAULT_DRAW_PROB = 0.33
    DEFAULT_AWAY_PROB = 0.33

    # ============================================================
    # SEASON
    # ============================================================

    SEASON_START = "2026-07-25"

    # ============================================================
    # LEARNING LAYER
    # ============================================================

    ENABLE_LEARNING_DATASET = True
    ENABLE_ERROR_ANALYSIS = True

    # ============================================================
    # LOGGING
    # ============================================================

    LOG_LEVEL = "INFO"
    DEBUG = False

    # ============================================================
    # METHODS
    # ============================================================

    @classmethod
    def get_season_start(cls) -> datetime:
        return datetime.strptime(cls.SEASON_START, "%Y-%m-%d")

    @classmethod
    def get_season_factor(cls, days: int) -> float:
        """Возвращает коэффициент фазы сезона по количеству дней"""
        if days < 30:
            return cls.SEASON_FACTOR_START
        elif days < 90:
            return cls.SEASON_FACTOR_EARLY
        elif days < 210:
            return cls.SEASON_FACTOR_MID
        else:
            return cls.SEASON_FACTOR_END

    @classmethod
    def get_tournament_factors(cls, league: str) -> dict:
        """Возвращает коэффициенты турнира"""
        return cls.TOURNAMENT_FACTORS.get(league, cls.TOURNAMENT_FACTORS["RPL"])


config = Config()
