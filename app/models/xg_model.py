#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ XG Model v1.7
=====================================================

РОЛЬ:
    Расчёт ожидаемых голов (xG) на основе паспортов команд.

АРХИТЕКТУРА:

    Team Passport (плоская структура)
          ↓
    FAJ XG Model v1.7
          ↓
    home_xg
    away_xg

ФОРМУЛА:

    Home xG = 1.35
            × Home Attack Factor
            × Away Defense Factor
            × Away GK Factor
            × Home Control Factor
            × Home Form Factor
            × 1.12 (Home Advantage)

    Away xG = 1.35
            × Away Attack Factor
            × Home Defense Factor
            × Home GK Factor
            × Away Control Factor
            × Away Form Factor

ГДЕ:

    Attack Factor = attack / 70 (0.85–1.15)
    Defense Factor = 70 / defense (0.85–1.15)
    GK Factor = 70 / goalkeeper (0.85–1.15)
    Form Factor = form / 50 (0.85–1.15)
    Control Factor: разница контроля распределяется между командами

ИСПРАВЛЕНИЯ v1.7:
    1. Версия обновлена до v1.7 (соответствует комментарию)
    2. В components добавлены home_rating, away_rating, rating_used_for_xg
    3. Model Version обновлена до FAJ_XG_v1.7

ВАЖНО:
    - FAJ Rating НЕ участвует в расчёте xG (только диагностика)
    - Home Advantage = 1.12 (только для хозяев)
    - Диапазон xG: 0.10 – 4.00
    - Паспорт — плоская структура (v1.7)
    - Форма — абсолютное значение 0–100
    - Rating передаётся только для диагностики
=====================================================
"""

import logging
from typing import Dict, Any, Optional

from app.config import config

logger = logging.getLogger(__name__)


class XGModel:
    """
    FAJ XG Model v1.7

    Расчёт xG на основе паспортов команд.
    Rating используется ТОЛЬКО для диагностики.
    """

    VERSION = "1.7"  # ИСПРАВЛЕНО: v1.6 → v1.7
    MODEL_VERSION = "FAJ_XG_v1.7"  # ИСПРАВЛЕНО

    # ============================================================
    # MODEL CONSTANTS
    # ============================================================

    LEAGUE_MEAN_XG = 1.35
    HOME_ADVANTAGE = config.HOME_ADVANTAGE  # 1.12

    XG_MIN = 0.10
    XG_MAX = 4.00

    # ============================================================
    # FACTOR LIMITS
    # ============================================================

    FACTOR_MIN = 0.85
    FACTOR_MAX = 1.15

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self):
        self.version = self.VERSION
        self.model_version = self.MODEL_VERSION

        logger.info(
            "FAJ XG Model v%s initialized | "
            "home_advantage=%.2f | xg_range=%.2f-%.2f",
            self.VERSION,
            self.HOME_ADVANTAGE,
            self.XG_MIN,
            self.XG_MAX
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float = 50.0,
        away_rating: float = 50.0
    ) -> Dict[str, Any]:
        """
        Расчёт xG для матча.

        Args:
            home_passport: паспорт домашней команды (плоская структура)
            away_passport: паспорт гостевой команды (плоская структура)
            home_rating: рейтинг хозяев (ТОЛЬКО для диагностики)
            away_rating: рейтинг гостей (ТОЛЬКО для диагностики)

        Returns:
            Dict с home_xg, away_xg, components и diagnostic
        """
        try:
            # ============================================================
            # 1. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ
            # ============================================================

            home_params = self._extract_team_parameters(home_passport, is_home=True)
            away_params = self._extract_team_parameters(away_passport, is_home=False)

            # ============================================================
            # 2. БАЗОВЫЕ ПАРАМЕТРЫ
            # ============================================================

            home_attack = home_params.get("attack", 50.0)
            home_defense = home_params.get("defense", 50.0)
            home_control = home_params.get("control", 50.0)
            home_goalkeeper = home_params.get("goalkeeper", 50.0)
            home_form = home_params.get("form", 50.0)

            away_attack = away_params.get("attack", 50.0)
            away_defense = away_params.get("defense", 50.0)
            away_control = away_params.get("control", 50.0)
            away_goalkeeper = away_params.get("goalkeeper", 50.0)
            away_form = away_params.get("form", 50.0)

            # ============================================================
            # 3. РАСЧЁТ ФАКТОРОВ
            # ============================================================

            # Attack: attack / 70
            home_attack_factor = self._calculate_attack_factor(home_attack)
            away_attack_factor = self._calculate_attack_factor(away_attack)

            # Defense: 70 / defense
            home_defense_factor = self._calculate_defense_factor(home_defense)
            away_defense_factor = self._calculate_defense_factor(away_defense)

            # Goalkeeper: 70 / goalkeeper
            home_keeper_factor = self._calculate_keeper_factor(home_goalkeeper)
            away_keeper_factor = self._calculate_keeper_factor(away_goalkeeper)

            # Form: form / 50
            home_form_factor = self._calculate_form_factor(home_form)
            away_form_factor = self._calculate_form_factor(away_form)

            # Control: разница распределяется между командами
            home_control_factor, away_control_factor = self._calculate_control_factors(
                home_control, away_control
            )

            # ============================================================
            # 4. РАСЧЁТ XG
            # ============================================================

            home_xg = (
                self.LEAGUE_MEAN_XG
                * home_attack_factor
                * away_defense_factor
                * away_keeper_factor
                * home_control_factor
                * home_form_factor
                * self.HOME_ADVANTAGE
            )

            away_xg = (
                self.LEAGUE_MEAN_XG
                * away_attack_factor
                * home_defense_factor
                * home_keeper_factor
                * away_control_factor
                * away_form_factor
            )

            # ============================================================
            # 5. ОГРАНИЧЕНИЕ
            # ============================================================

            home_xg = max(self.XG_MIN, min(self.XG_MAX, home_xg))
            away_xg = max(self.XG_MIN, min(self.XG_MAX, away_xg))

            # ============================================================
            # 6. ДИАГНОСТИКА
            # ============================================================

            logger.debug(
                "XG calculated: home=%.3f, away=%.3f | "
                "home_attack=%.1f, away_defense=%.1f, "
                "home_form=%.1f, away_form=%.1f",
                home_xg, away_xg,
                home_attack, away_defense,
                home_form, away_form
            )

            # ============================================================
            # 7. РЕЗУЛЬТАТ
            # ИСПРАВЛЕНО: добавлены home_rating, away_rating, rating_used_for_xg
            # ============================================================

            return {
                "status": "success",
                "home_xg": round(home_xg, 3),
                "away_xg": round(away_xg, 3),
                "components": {
                    "home_attack_factor": round(home_attack_factor, 3),
                    "away_attack_factor": round(away_attack_factor, 3),
                    "home_defense_factor": round(home_defense_factor, 3),
                    "away_defense_factor": round(away_defense_factor, 3),
                    "home_keeper_factor": round(home_keeper_factor, 3),
                    "away_keeper_factor": round(away_keeper_factor, 3),
                    "home_control_factor": round(home_control_factor, 3),
                    "away_control_factor": round(away_control_factor, 3),
                    "home_form_factor": round(home_form_factor, 3),
                    "away_form_factor": round(away_form_factor, 3),
                    "home_advantage": round(self.HOME_ADVANTAGE, 3),
                    # НОВЫЕ ПОЛЯ v1.7
                    "home_rating": round(float(home_rating), 2),
                    "away_rating": round(float(away_rating), 2),
                    "rating_used_for_xg": False,
                },
                "diagnostic": {
                    "home_attack": round(home_attack, 1),
                    "home_defense": round(home_defense, 1),
                    "home_control": round(home_control, 1),
                    "home_goalkeeper": round(home_goalkeeper, 1),
                    "home_form": round(home_form, 1),
                    "away_attack": round(away_attack, 1),
                    "away_defense": round(away_defense, 1),
                    "away_control": round(away_control, 1),
                    "away_goalkeeper": round(away_goalkeeper, 1),
                    "away_form": round(away_form, 1),
                },
                "model_version": self.MODEL_VERSION
            }

        except Exception as e:
            logger.error(f"XG calculation error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "home_xg": self.LEAGUE_MEAN_XG,
                "away_xg": self.LEAGUE_MEAN_XG * 0.9,
                "components": {},
                "diagnostic": {},
                "model_version": self.MODEL_VERSION
            }

    # ============================================================
    # PARAMETER EXTRACTION
    # ============================================================

    def _extract_team_parameters(
        self,
        passport: Dict[str, Any],
        is_home: bool = False
    ) -> Dict[str, float]:
        """
        Извлечение параметров из паспорта.

        Passport — плоская структура (v1.7).
        Все параметры на верхнем уровне.
        """
        params = {
            "attack": 50.0,
            "defense": 50.0,
            "control": 50.0,
            "goalkeeper": 50.0,
            "form": 50.0,
        }

        if not isinstance(passport, dict):
            logger.warning(f"Passport is not a dict: {type(passport)}")
            return params

        # Извлечение параметров из плоской структуры
        for key in ["attack", "defense", "control", "goalkeeper", "form"]:
            value = passport.get(key)
            if value is not None:
                try:
                    params[key] = float(value)
                except (TypeError, ValueError):
                    logger.warning(f"Invalid {key} value: {value}")

        logger.debug(
            "Extracted params: attack=%.1f, defense=%.1f, "
            "control=%.1f, goalkeeper=%.1f, form=%.1f",
            params["attack"], params["defense"],
            params["control"], params["goalkeeper"],
            params["form"]
        )

        return params

    # ============================================================
    # FACTOR CALCULATIONS
    # ============================================================

    def _calculate_attack_factor(self, attack: float) -> float:
        """Attack Factor = attack / 70 (0.85–1.15)"""
        if attack <= 0:
            return self.FACTOR_MIN
        factor = attack / 70.0
        return max(self.FACTOR_MIN, min(self.FACTOR_MAX, factor))

    def _calculate_defense_factor(self, defense: float) -> float:
        """Defense Factor = 70 / defense (0.85–1.15)"""
        if defense <= 0:
            return self.FACTOR_MAX
        factor = 70.0 / defense
        return max(self.FACTOR_MIN, min(self.FACTOR_MAX, factor))

    def _calculate_keeper_factor(self, goalkeeper: float) -> float:
        """GK Factor = 70 / goalkeeper (0.85–1.15)"""
        if goalkeeper <= 0:
            return self.FACTOR_MAX
        factor = 70.0 / goalkeeper
        return max(self.FACTOR_MIN, min(self.FACTOR_MAX, factor))

    def _calculate_form_factor(self, form: float) -> float:
        """Form Factor = form / 50 (0.85–1.15)"""
        if form <= 0:
            return self.FACTOR_MIN
        factor = form / 50.0
        return max(self.FACTOR_MIN, min(self.FACTOR_MAX, factor))

    def _calculate_control_factors(
        self,
        home_control: float,
        away_control: float
    ) -> tuple:
        """
        Control Factors: разница контроля распределяется между командами.

        Пример:
            home_control = 80, away_control = 60
            diff = 20
            home_factor = 1 + 20/200 = 1.10
            away_factor = 1 - 20/200 = 0.90
        """
        diff = home_control - away_control

        # Ограничиваем разницу
        diff = max(-50, min(50, diff))

        home_factor = 1.0 + (diff / 200.0)
        away_factor = 1.0 - (diff / 200.0)

        # Ограничиваем факторы
        home_factor = max(self.FACTOR_MIN, min(self.FACTOR_MAX, home_factor))
        away_factor = max(self.FACTOR_MIN, min(self.FACTOR_MAX, away_factor))

        return home_factor, away_factor

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """Диагностический статус модели."""
        return {
            "model": self.MODEL_VERSION,
            "version": self.VERSION,
            "league_mean_xg": self.LEAGUE_MEAN_XG,
            "home_advantage": self.HOME_ADVANTAGE,
            "xg_range": [self.XG_MIN, self.XG_MAX],
            "factor_range": [self.FACTOR_MIN, self.FACTOR_MAX],
            "status": "READY"
        }


# ================================================================
# SINGLETON
# ================================================================

_xg_model_instance: Optional[XGModel] = None


def get_xg_model() -> XGModel:
    """Синглтон для XGModel."""
    global _xg_model_instance
    if _xg_model_instance is None:
        _xg_model_instance = XGModel()
    return _xg_model_instance


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FAJ XG Model v1.7 — SELF TEST")  # ИСПРАВЛЕНО: v1.6 → v1.7
    print("=" * 60)

    model = XGModel()

    print("\n📊 Status:")
    print(model.status())

    # Тестовые паспорта
    home_passport = {
        "attack": 75.0,
        "defense": 65.0,
        "control": 70.0,
        "goalkeeper": 68.0,
        "form": 55.0
    }

    away_passport = {
        "attack": 60.0,
        "defense": 72.0,
        "control": 55.0,
        "goalkeeper": 70.0,
        "form": 48.0
    }

    print("\n📋 Тестовые данные:")
    print(f"  Home: attack=75, defense=65, control=70, gk=68, form=55")
    print(f"  Away: attack=60, defense=72, control=55, gk=70, form=48")

    # Тест с рейтингами
    result = model.calculate(
        home_passport,
        away_passport,
        home_rating=85.0,
        away_rating=72.0
    )

    print("\n📊 Результат:")
    print(f"  Home xG: {result['home_xg']:.3f}")
    print(f"  Away xG: {result['away_xg']:.3f}")

    print("\n🔧 Компоненты:")
    for key, value in result.get("components", {}).items():
        print(f"  {key}: {value:.3f}")

    # Проверка новых полей
    print("\n📈 Диагностика рейтингов:")
    components = result.get("components", {})
    print(f"  Home Rating: {components.get('home_rating', 'N/A')}")
    print(f"  Away Rating: {components.get('away_rating', 'N/A')}")
    print(f"  Rating used for xG: {components.get('rating_used_for_xg', 'N/A')}")

    print("\n✅ XG Model v1.7 готов к работе.")
    print("=" * 60)
