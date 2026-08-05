#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Config

Единый центр управления всей платформой.

СОДЕРЖИТ:
    - Версии платформы и ядра
    - Параметры xG
    - Параметры Poisson
    - Параметры Monte Carlo
    - Настройки Learning Layer
    - Настройки логирования

ПРИНЦИП:
    Все константы вынесены из движка.
    Изменение config.py = изменение поведения платформы.
=====================================================
"""

from datetime import datetime


class Config:
    """Центральная конфигурация FAJ Platform v12.0"""

    # ============================================================
    # VERSIONS
    # ============================================================

    PLATFORM_VERSION = "12.0"
    CORE_VERSION = "7.2"
    PIPELINE_VERSION = "1.1"
    MODEL_VERSION = "12.0"

    # ============================================================
    # XG ENGINE
    # ============================================================

    XG_MIN = 0.10
    XG_MAX = 4.00
    XG_LEAGUE_MEAN = 1.35
    HOME_ADVANTAGE = 1.08

    # Фазы сезона
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
        """Возвращает дату начала сезона как объект datetime"""
        return datetime.strptime(cls.SEASON_START, "%Y-%m-%d")

    @classmethod
    def get_season_phase(cls, days: int) -> float:
        """
        Возвращает коэффициент фазы сезона по количеству дней от начала

        Args:
            days: количество дней от начала сезона

        Returns:
            float: коэффициент фазы сезона
        """
        if days < 30:
            return cls.SEASON_PHASE_START
        elif days < 90:
            return cls.SEASON_PHASE_EARLY
        elif days < 210:
            return cls.SEASON_PHASE_MID
        else:
            return cls.SEASON_PHASE_END


# Создаём экземпляр для удобного импорта
config = Config()


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ FAJ Platform v12.0 — Config")
    print("=" * 60)

    print(f"\n📌 VERSIONS:")
    print(f"  Platform: {config.PLATFORM_VERSION}")
    print(f"  Core: {config.CORE_VERSION}")
    print(f"  Pipeline: {config.PIPELINE_VERSION}")
    print(f"  Model: {config.MODEL_VERSION}")

    print(f"\n📌 XG ENGINE:")
    print(f"  XG Range: {config.XG_MIN} - {config.XG_MAX}")
    print(f"  League Mean: {config.XG_LEAGUE_MEAN}")
    print(f"  Home Advantage: {config.HOME_ADVANTAGE}")

    print(f"\n📌 POISSON:")
    print(f"  Max Goals: {config.MAX_GOALS}")

    print(f"\n📌 MONTE CARLO:")
    print(f"  Iterations: {config.MONTE_CARLO_ITERATIONS}")
    print(f"  Reproducible: {config.MONTE_CARLO_REPRODUCIBLE}")

    print(f"\n📌 LEARNING LAYER:")
    print(f"  Save to Gold Dataset: {config.SAVE_TO_GOLD_DATASET}")
    print(f"  Save Learning Records: {config.SAVE_LEARNING_RECORDS}")

    print(f"\n📌 LOGGING:")
    print(f"  Level: {config.LOG_LEVEL}")
    print(f"  Debug: {config.DEBUG}")

    print(f"\n📌 SEASON:")
    print(f"  Start: {config.SEASON_START}")
    print(f"  Season Start Date: {config.get_season_start()}")

    print("\n" + "=" * 60)
    print("✅ Config готов к работе.")
    print("=" * 60)
