#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Config

Единый центр управления всей платформой.
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
    PIPELINE_VERSION = "1.2"
    MODEL_VERSION = "12.0"

    # ============================================================
    # XG ENGINE
    # ============================================================

    XG_MIN = 0.10
    XG_MAX = 4.00
    XG_LEAGUE_MEAN = 1.35
    HOME_ADVANTAGE = 1.08

    SEASON_PHASE_START = 0.90
    SEASON_PHASE_EARLY = 0.95
    SEASON_PHASE_MID = 1.00
    SEASON_PHASE_END = 1.05

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

    SAVE_TO_GOLD_DATASET = True
    SAVE_LEARNING_RECORDS = True

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
    def get_season_phase(cls, days: int) -> float:
        if days < 30:
            return cls.SEASON_PHASE_START
        elif days < 90:
            return cls.SEASON_PHASE_EARLY
        elif days < 210:
            return cls.SEASON_PHASE_MID
        else:
            return cls.SEASON_PHASE_END


config = Config()
