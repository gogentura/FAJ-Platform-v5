#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ XG Model v1.3
Расчёт ожидаемых голов на основе Power Profile команды

Вход: Power Profile (attack_power, defense_power, control_power, goalkeeper_power)
Выход: {
    "home_xg": float,
    "away_xg": float,
    "components": {...},
    "explanation": [...],
    "model_version": "FAJ_XG_v1.3",
    "timestamp": "2026-08-05T..."
}
"""

import math
from datetime import datetime
from typing import Dict, List, Optional


class FAJXGModel:
    """
    Модель расчёта ожидаемых голов (xG) на основе силы команд
    """

    # ============================================================
    # КОНФИГУРАЦИЯ
    # ============================================================

    LEAGUE_MEAN_XG = 1.35
    HOME_ADVANTAGE = 1.12
    POWER_BASE = 70
    MIN_XG = 0.15
    MAX_XG = 4.0

    # Настройки контроля
    CONTROL_WEIGHT = 0.5
    MIN_CONTROL_FACTOR = 0.85
    MAX_CONTROL_FACTOR = 1.30

    # Настройки вратаря
    MIN_KEEPER_FACTOR = 0.85
    MAX_KEEPER_FACTOR = 1.15

    # Настройки атаки/защиты
    MIN_DEFENSE_FACTOR = 0.70
    MAX_DEFENSE_FACTOR = 1.40

    MODEL_VERSION = "FAJ_XG_v1.3"

    # ============================================================
    # ПУБЛИЧНЫЙ МЕТОД
    # ============================================================

    def calculate(self, home_profile: Dict, away_profile: Dict) -> Dict:
        """
        Рассчитывает xG для матча

        home_profile = {
            "attack_power": 82,
            "defense_power": 78,
            "control_power": 80,
            "goalkeeper_power": 75
        }
        """
        # 1. Извлекаем показатели с ограничением
        home_attack = self._clamp_value(home_profile.get("attack_power", 70), 40, 100)
        home_defense = self._clamp_value(home_profile.get("defense_power", 70), 40, 100)
        home_control = self._clamp_value(home_profile.get("control_power", 70), 40, 100)
        home_goalkeeper = self._clamp_value(home_profile.get("goalkeeper_power", 70), 40, 100)

        away_attack = self._clamp_value(away_profile.get("attack_power", 70), 40, 100)
        away_defense = self._clamp_value(away_profile.get("defense_power", 70), 40, 100)
        away_control = self._clamp_value(away_profile.get("control_power", 70), 40, 100)
        away_goalkeeper = self._clamp_value(away_profile.get("goalkeeper_power", 70), 40, 100)

        # 2. Расчёт компонентов
        home_attack_factor = self._attack_factor(home_attack)
        away_attack_factor = self._attack_factor(away_attack)

        home_defense_factor = self._defense_factor(home_defense)
        away_defense_factor = self._defense_factor(away_defense)

        home_keeper_factor = self._keeper_factor(home_goalkeeper)
        away_keeper_factor = self._keeper_factor(away_goalkeeper)

        control_factor = self._control_factor(home_control, away_control)

        home_bonus = self.HOME_ADVANTAGE

        # 3. Расчёт xG
        home_xg_raw = (
            self.LEAGUE_MEAN_XG
            * home_attack_factor
            * away_defense_factor
            * away_keeper_factor
            * control_factor
            * home_bonus
        )

        away_xg_raw = (
            self.LEAGUE_MEAN_XG
            * away_attack_factor
            * home_defense_factor
            * home_keeper_factor
            * control_factor
        )

        # 4. Ограничения
        home_xg = self._clamp(home_xg_raw)
        away_xg = self._clamp(away_xg_raw)

        # 5. Компоненты для объяснения
        components = {
            "home_attack_factor": round(home_attack_factor, 3),
            "away_attack_factor": round(away_attack_factor, 3),
            "home_defense_factor": round(home_defense_factor, 3),
            "away_defense_factor": round(away_defense_factor, 3),
            "home_keeper_factor": round(home_keeper_factor, 3),
            "away_keeper_factor": round(away_keeper_factor, 3),
            "control_factor": round(control_factor, 3),
            "home_bonus": round(home_bonus, 3),
        }

        # 6. Человеческое объяснение
        explanation = self._build_explanation(
            home_attack, home_defense, home_control, home_goalkeeper,
            away_attack, away_defense, away_control, away_goalkeeper,
            home_attack_factor, away_attack_factor,
            home_defense_factor, away_defense_factor,
            home_keeper_factor, away_keeper_factor,
            control_factor,
            home_xg, away_xg
        )

        return {
            "home_xg": round(home_xg, 3),
            "away_xg": round(away_xg, 3),
            "components": components,
            "explanation": explanation,
            "model_version": self.MODEL_VERSION,
            "timestamp": datetime.utcnow().isoformat()
        }

    # ============================================================
    # ВНУТРЕННИЕ МЕТОДЫ
    # ============================================================

    def _clamp_value(self, value: float, min_val: float = 40, max_val: float = 100) -> float:
        """Ограничивает значение в разумных пределах"""
        return max(min_val, min(max_val, value))

    def _attack_factor(self, attack_power: float) -> float:
        """Фактор силы атаки: отношение к базовой силе"""
        return attack_power / self.POWER_BASE

    def _defense_factor(self, defense_power: float) -> float:
        """
        Фактор защиты: чем выше защита, тем меньше xG соперника
        Ограничен: 0.70 – 1.40
        """
        if defense_power <= 0:
            return 1.0
        factor = self.POWER_BASE / defense_power
        return max(self.MIN_DEFENSE_FACTOR, min(self.MAX_DEFENSE_FACTOR, factor))

    def _keeper_factor(self, goalkeeper_power: float) -> float:
        """
        Фактор вратаря: чем сильнее вратарь, тем меньше xG соперника
        Ограничен: 0.85 – 1.15
        """
        if goalkeeper_power <= 0:
            return 1.0
        factor = self.POWER_BASE / goalkeeper_power
        return max(self.MIN_KEEPER_FACTOR, min(self.MAX_KEEPER_FACTOR, factor))

    def _control_factor(self, home_control: float, away_control: float) -> float:
        """
        Фактор контроля: разница в контроле матча
        Контроль влияет на создание моментов:
        - максимальное влияние: +30% при разнице 60 пунктов
        - минимальное влияние: -15% при значительном отставании
        """
        diff = home_control - away_control
        factor = 1 + (diff / 100) * self.CONTROL_WEIGHT
        return max(self.MIN_CONTROL_FACTOR, min(self.MAX_CONTROL_FACTOR, factor))

    def _clamp(self, value: float) -> float:
        """Ограничение xG в разумных пределах"""
        return max(self.MIN_XG, min(self.MAX_XG, value))

    def _build_explanation(
        self,
        home_attack, home_defense, home_control, home_goalkeeper,
        away_attack, away_defense, away_control, away_goalkeeper,
        home_attack_factor, away_attack_factor,
        home_defense_factor, away_defense_factor,
        home_keeper_factor, away_keeper_factor,
        control_factor,
        home_xg, away_xg
    ) -> List[str]:
        """Строит человеческое объяснение расчёта xG"""
        explanation = []

        # Атака хозяев
        if home_attack_factor > 1.1:
            explanation.append(f"Атака хозяев выше средней ({home_attack_factor:.2f}x)")
        elif home_attack_factor < 0.9:
            explanation.append(f"Атака хозяев ниже средней ({home_attack_factor:.2f}x)")

        # Атака гостей
        if away_attack_factor > 1.1:
            explanation.append(f"Атака гостей выше средней ({away_attack_factor:.2f}x)")
        elif away_attack_factor < 0.9:
            explanation.append(f"Атака гостей ниже средней ({away_attack_factor:.2f}x)")

        # Защита хозяев
        if home_defense_factor < 0.85:
            explanation.append(f"Сильная защита хозяев снижает xG гостей ({home_defense_factor:.2f}x)")
        elif home_defense_factor > 1.15:
            explanation.append(f"Слабая защита хозяев повышает xG гостей ({home_defense_factor:.2f}x)")

        # Защита гостей
        if away_defense_factor < 0.85:
            explanation.append(f"Сильная защита гостей снижает xG хозяев ({away_defense_factor:.2f}x)")
        elif away_defense_factor > 1.15:
            explanation.append(f"Слабая защита гостей повышает xG хозяев ({away_defense_factor:.2f}x)")

        # Вратарь хозяев
        if home_keeper_factor < 0.90:
            explanation.append(f"Сильный вратарь хозяев снижает xG гостей ({home_keeper_factor:.2f}x)")
        elif home_keeper_factor > 1.10:
            explanation.append(f"Слабый вратарь хозяев повышает xG гостей ({home_keeper_factor:.2f}x)")

        # Вратарь гостей
        if away_keeper_factor < 0.90:
            explanation.append(f"Сильный вратарь гостей снижает xG хозяев ({away_keeper_factor:.2f}x)")
        elif away_keeper_factor > 1.10:
            explanation.append(f"Слабый вратарь гостей повышает xG хозяев ({away_keeper_factor:.2f}x)")

        # Контроль
        if control_factor > 1.08:
            explanation.append(f"Контроль матча даёт серьёзное преимущество ({control_factor:.2f}x)")
        elif control_factor > 1.02:
            explanation.append(f"Лучший контроль даёт преимущество ({control_factor:.2f}x)")
        elif control_factor < 0.95:
            explanation.append(f"Потеря контроля снижает эффективность ({control_factor:.2f}x)")

        # Итоговый xG
        explanation.append(f"Ожидаемые голы: {home_xg:.2f} : {away_xg:.2f}")

        return explanation


# ============================================================
# АЛИАС ДЛЯ СОВМЕСТИМОСТИ
# ============================================================
XGModel = FAJXGModel


# ============================================================
# СИНГЛТОН
# ============================================================
_xg_model_instance = None


def get_xg_model() -> FAJXGModel:
    global _xg_model_instance
    if _xg_model_instance is None:
        _xg_model_instance = FAJXGModel()
    return _xg_model_instance


if __name__ == "__main__":
    model = FAJXGModel()

    # Тест 1: стандартный матч
    home_profile = {
        "attack_power": 82,
        "defense_power": 78,
        "control_power": 80,
        "goalkeeper_power": 75
    }

    away_profile = {
        "attack_power": 74,
        "defense_power": 81,
        "control_power": 76,
        "goalkeeper_power": 79
    }

    result = model.calculate(home_profile, away_profile)

    print("\n⚽ FAJ XG Model v1.3 — Тест 1 (стандартный)")
    print("=" * 60)
    print(f"xG Дома:  {result['home_xg']}")
    print(f"xG В гостях: {result['away_xg']}")
    print(f"Версия: {result['model_version']}")
    print("\n📊 Компоненты:")
    for key, value in result['components'].items():
        print(f"  {key}: {value}")
    print("\n📝 Объяснение:")
    for line in result['explanation']:
        print(f"  • {line}")

    # Тест 2: доминирующий хозяин
    print("\n" + "=" * 60)
    print("⚽ FAJ XG Model v1.3 — Тест 2 (доминирование хозяев)")

    home_profile2 = {
        "attack_power": 95,
        "defense_power": 85,
        "control_power": 95,
        "goalkeeper_power": 85
    }

    away_profile2 = {
        "attack_power": 55,
        "defense_power": 60,
        "control_power": 50,
        "goalkeeper_power": 60
    }

    result2 = model.calculate(home_profile2, away_profile2)

    print(f"xG Дома:  {result2['home_xg']}")
    print(f"xG В гостях: {result2['away_xg']}")
    print("\n📊 Компоненты:")
    for key, value in result2['components'].items():
        print(f"  {key}: {value}")
    print("\n📝 Объяснение:")
    for line in result2['explanation']:
        print(f"  • {line}")
