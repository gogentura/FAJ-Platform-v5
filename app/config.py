#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11.2.1
Config — Единый файл настроек
"""

class FAJConfig:
    """Конфигурация FAJ Platform"""
    
    # =========================================================
    # XG ENGINE
    # =========================================================
    LEAGUE_MEAN_XG = 1.35
    HOME_ADVANTAGE = 1.12
    XG_MIN = 0.10
    XG_MAX = 4.00
    
    # =========================================================
    # WEIGHTS (для FAJ Rating)
    # =========================================================
    WEIGHTS = {
        "attack": 0.18,
        "defense": 0.18,
        "control": 0.15,
        "efficiency": 0.12,
        "mentality": 0.10,
        "tempo": 0.05,
        "press": 0.05,
        "transition": 0.05,
        "tactical": 0.05,
        "coach": 0.04,
        "form": 0.03
    }
    
    # =========================================================
    # PASSPORT MANAGER
    # =========================================================
    MAX_CHANGE_PER_SEASON = 10
    BASE_CORRECTION_LIMITS = {
        5: 1,   # 5 матчей → ±1
        10: 2,  # 10 матчей → ±2
        15: 3   # 15 матчей → ±3
    }
    CONFIDENCE_FACTORS = {
        5: 0.5,   # 5 матчей → 0.5
        10: 0.7,  # 10 матчей → 0.7
        15: 0.9   # 15 матчей → 0.9
    }
    
    # =========================================================
    # FATIGUE
    # =========================================================
    FATIGUE_BASE = 10
    FATIGUE_RECOVERY_RATE = 1.2
    FATIGUE_RECOVERY_BONUS = 3
    
    # =========================================================
    # PERFORMANCE INDEX
    # =========================================================
    PERFORMANCE_WEIGHTS = {
        "xg": 0.45,
        "points": 0.25,
        "shot_quality": 0.20,
        "control": 0.10
    }
    
    # =========================================================
    # MATCH INTENSITY
    # =========================================================
    MATCH_INTENSITY = {
        "friendly": 0.6,
        "league": 1.0,
        "derby": 1.3,
        "cup": 1.2,
        "europe": 1.5,
        "final": 1.8
    }
    
    # =========================================================
    # TEAM IDENTITY
    # =========================================================
    STYLES = ["possession", "direct", "counter", "mixed"]
    TEMPOS = ["slow", "medium", "fast"]
    PRESSING = ["low", "medium", "high"]
    TRANSITIONS = ["slow", "medium", "fast"]
    RISK_LEVELS = ["low", "medium", "high"]
    
    # =========================================================
    # PASSPORT CONFIDENCE
    # =========================================================
    INITIAL_PASSPORT_CONFIDENCE = 0.4
    MAX_PASSPORT_CONFIDENCE = 0.9
    CONFIDENCE_GROWTH_PER_MATCH = 0.02
    
    # =========================================================
    # POISSON / MONTE CARLO
    # =========================================================
    MAX_GOALS = 8
    SIMULATION_COUNT = 10000
    POISSON_MAX_SCORE = 6
