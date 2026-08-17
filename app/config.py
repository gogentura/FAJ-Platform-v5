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
    PIPELINE_VERSION = "1.9"
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

    MONTE_CARLO_XG_MIN = 0.1
    MONTE_CARLO_XG_MAX = 6.0
    MONTE_CARLO_ITERATIONS = 10000
    MONTE_CARLO_REPRODUCIBLE = True

    # ============================================================
    # SAVE OPTIONS
    # ============================================================

    SAVE_TO_GOLD_DATASET = True     # ← ИЗМЕНЕНО НА True

    # ============================================================
    # MODEL WEIGHTS (FAJ RATING)
    # ============================================================

    ATTACK_WEIGHT = 0.18
    DEFENSE_WEIGHT = 0.18
    CONTROL_WEIGHT = 0.15
    EFFICIENCY_WEIGHT = 0.12
    MENTALITY_WEIGHT = 0.10
    TEMPO_WEIGHT = 0.07
    PRESS_WEIGHT = 0.05
    TRANSITION_WEIGHT = 0.05
    COACH_WEIGHT = 0.05
    FORM_WEIGHT = 0.05

    # Словарь для удобного доступа
    RATING_WEIGHTS = {
        "attack": ATTACK_WEIGHT,
        "defense": DEFENSE_WEIGHT,
        "control": CONTROL_WEIGHT,
        "efficiency": EFFICIENCY_WEIGHT,
        "mentality": MENTALITY_WEIGHT,
        "tempo": TEMPO_WEIGHT,
        "press": PRESS_WEIGHT,
        "transition": TRANSITION_WEIGHT,
        "coach": COACH_WEIGHT,
        "form": FORM_WEIGHT
    }

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
    # DIAGNOSTIC
    # ============================================================

    # Веса компонентов при расчёте Health Score
    DIAGNOSTIC_WEIGHTS = {
        "Database": 3,
        "Prediction": 3,
        "Pipeline": 2,
        "Passports": 2,
        "Learning": 1,
        "Performance": 1,
        "Versions": 1,
    }

    # Матчи для проверки Prediction Pipeline
    DIAGNOSTIC_TEST_MATCHES = [
        ("Зенит", "Спартак"),
        ("Краснодар", "ЦСКА"),
        ("Динамо", "Ростов"),
    ]

    # Максимальное количество записей истории диагностики
    DIAGNOSTIC_HISTORY_LIMIT = 1000

    # Каждые сколько сохранений выполнять очистку истории
    DIAGNOSTIC_CLEANUP_EVERY = 100

    # ============================================================
    # METHODS
    # ============================================================

    @classmethod
    def get_season_start(cls) -> datetime:
        return datetime.strptime(cls.SEASON_START, "%Y-%m-%d")

    @classmethod
    def get_season_factor(cls, days: int) -> float:
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
        return cls.TOURNAMENT_FACTORS.get(league, cls.TOURNAMENT_FACTORS["RPL"])

    @classmethod
    def get_rating_weights(cls) -> dict:
        return cls.RATING_WEIGHTS


config = Config()
