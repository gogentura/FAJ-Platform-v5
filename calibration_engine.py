#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Calibration Engine v1.3

РОЛЬ:
    Корректировка вероятностей на основе исторических данных.
    Не меняет модель, а исправляет систематические ошибки.

ПРИНЦИП FAJ:
    ✅ Коэффициенты живут в коде (базовые)
    ✅ Обновляются через Learning Layer (БД)
    ❌ НЕТ JSON-конфигов

ИЗМЕНЕНИЯ v1.3:
    - Добавлена валидация коэффициентов (0.5 - 1.5)
    - Безопасное обновление коэффициентов (partial update)
=====================================================
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CalibrationEngine:
    """
    Калибровка вероятностей FAJ
    """

    VERSION = "1.3"

    # Базовые коэффициенты (живут в коде)
    # Обновляются через Learning Layer
    DEFAULT_COEFFICIENTS = {
        "home_bias": 0.97,
        "draw_bias": 1.02,
        "away_bias": 1.01
    }

    # Допустимый диапазон коэффициентов
    COEFFICIENT_MIN = 0.5
    COEFFICIENT_MAX = 1.5

    def __init__(self):
        self.version = self.VERSION
        self.coefficients = self.DEFAULT_COEFFICIENTS.copy()
        logger.info(f"Calibration Engine v{self.VERSION} initialized")

    def adjust(
        self,
        raw_prediction: Dict[str, Any],
        coefficients: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Калибровка вероятностей

        Args:
            raw_prediction: сырой прогноз от Poisson
            coefficients: опциональные коэффициенты (из Learning Layer)

        Returns:
            Dict с скорректированными вероятностями
        """
        # Безопасное обновление коэффициентов
        coeffs = self.coefficients.copy()
        if coefficients:
            # Валидация переданных коэффициентов
            validated = self._validate_coefficients(coefficients)
            coeffs.update(validated)

        raw_probs = raw_prediction.get("probability", {})
        home = raw_probs.get("home", 0.33)
        draw = raw_probs.get("draw", 0.33)
        away = raw_probs.get("away", 0.33)

        # Применяем калибровку
        calibrated_home = home * coeffs.get("home_bias", 1.0)
        calibrated_draw = draw * coeffs.get("draw_bias", 1.0)
        calibrated_away = away * coeffs.get("away_bias", 1.0)

        # Нормализация (сумма должна быть 1.0)
        total = calibrated_home + calibrated_draw + calibrated_away
        if total > 0:
            calibrated_home /= total
            calibrated_draw /= total
            calibrated_away /= total

        return {
            "home": round(calibrated_home, 4),
            "draw": round(calibrated_draw, 4),
            "away": round(calibrated_away, 4),
            "applied": True,
            "coefficients_used": coeffs
        }

    def _validate_coefficients(
        self,
        coefficients: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Валидация коэффициентов

        Args:
            coefficients: словарь коэффициентов для проверки

        Returns:
            Dict с отфильтрованными валидными коэффициентами

        Raises:
            ValueError: если коэффициент вне допустимого диапазона
        """
        valid = {}
        for key, value in coefficients.items():
            if key in self.DEFAULT_COEFFICIENTS:
                if not (self.COEFFICIENT_MIN <= value <= self.COEFFICIENT_MAX):
                    raise ValueError(
                        f"Invalid calibration coefficient '{key}': {value}. "
                        f"Must be between {self.COEFFICIENT_MIN} and {self.COEFFICIENT_MAX}"
                    )
                valid[key] = value
            else:
                logger.warning(f"Unknown calibration coefficient '{key}', ignoring")
        return valid

    def update_coefficients(
        self,
        new_coefficients: Dict[str, float]
    ) -> None:
        """
        Безопасное обновление коэффициентов (вызывается Learning Layer)

        Args:
            new_coefficients: новые коэффициенты (частичные или полные)
        """
        validated = self._validate_coefficients(new_coefficients)
        self.coefficients.update(validated)
        logger.info(f"Calibration coefficients updated: {validated}")

    def get_coefficients(self) -> Dict[str, float]:
        """Получить текущие коэффициенты"""
        return self.coefficients.copy()

    def reset_coefficients(self) -> None:
        """Сброс к базовым коэффициентам"""
        self.coefficients = self.DEFAULT_COEFFICIENTS.copy()
        logger.info("Calibration coefficients reset to default")


if __name__ == "__main__":
    engine = CalibrationEngine()
    print(f"Calibration Engine v{engine.VERSION}")
    print(f"Default coefficients: {engine.DEFAULT_COEFFICIENTS}")
    print(f"Current coefficients: {engine.get_coefficients()}")
    print(f"Range: {engine.COEFFICIENT_MIN} - {engine.COEFFICIENT_MAX}")

    # Тест валидации
    try:
        engine.update_coefficients({"home_bias": 0.5, "draw_bias": 1.0})
        print("✅ Valid coefficients accepted")
    except ValueError as e:
        print(f"❌ {e}")

    try:
        engine.update_coefficients({"home_bias": 2.0})
    except ValueError as e:
        print(f"✅ Invalid coefficient rejected: {e}")
