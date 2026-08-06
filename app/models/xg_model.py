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
    # ПУБЛИЧНЫЙ МЕТОД — НОВАЯ СИГНАТУРА
    # ============================================================

    def calculate(
        self,
        home_passport: Dict,
        away_passport: Dict,
        home_rating: float = 70.0,
        away_rating: float = 70.0
    ) -> Dict:
        """
        Рассчитывает xG для матча на основе паспортов команд

        Аргументы (как ожидает Prediction Pipeline):
            home_passport: паспорт команды хозяев
            away_passport: паспорт команды гостей
            home_rating: рейтинг хозяев (0-100)
            away_rating: рейтинг гостей (0-100)

        В паспорте ожидается структура:
            {
                "BASE": {
                    "attack": 82,
                    "defense": 78,
                    "control": 80,
                    "goalkeeper": 75,
                    "tempo": 50,
                    "press": 50,
                    ...
                },
                "IDENTITY": {...},
                "DYNAMIC_INITIAL": {
                    "form": 50,
                    "fitness": 50,
                    "morale": 50,
                    ...
                },
                "EXPERT": {...}
            }
        """
        # 1. Извлекаем BASE и DYNAMIC_INITIAL из паспортов
        home_base = home_passport.get("BASE", {})
        away_base = away_passport.get("BASE", {})
        home_dynamic = home_passport.get("DYNAMIC_INITIAL", {})
        away_dynamic = away_passport.get("DYNAMIC_INITIAL", {})

        # 2. Извлекаем показатели с ограничением
        home_attack = self._clamp_value(home_base.get("attack", 70), 40, 100)
        home_defense = self._clamp_value(home_base.get("defense", 70), 40, 100)
        home_control = self._clamp_value(home_base.get("control", 70), 40, 100)
        home_goalkeeper = self._clamp_value(home_base.get("goalkeeper", 70), 40, 100)

        away_attack = self._clamp_value(away_base.get("attack", 70), 40, 100)
        away_defense = self._clamp_value(away_base.get("defense", 70), 40, 100)
        away_control = self._clamp_value(away_base.get("control", 70), 40, 100)
        away_goalkeeper = self._clamp_value(away_base.get("goalkeeper", 70), 40, 100)

        # 3. Учитываем форму из DYNAMIC_INITIAL
        home_form = home_dynamic.get("form", 50) / 50.0
        away_form = away_dynamic.get("form", 50) / 50.0

        # 4. Расчёт компонентов
        home_attack_factor = self._attack_factor(home_attack) * home_form
        away_attack_factor = self._attack_factor(away_attack) * away_form

        home_defense_factor = self._defense_factor(home_defense) / home_form
        away_defense_factor = self._defense_factor(away_defense) / away_form

        home_keeper_factor = self._keeper_factor(home_goalkeeper)
        away_keeper_factor = self._keeper_factor(away_goalkeeper)

        control_factor = self._control_factor(home_control, away_control)

        home_bonus = self.HOME_ADVANTAGE

        # 5. Расчёт xG
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

        # 6. Ограничения
        home_xg = self._clamp(home_xg_raw)
        away_xg = self._clamp(away_xg_raw)

        # 7. Компоненты для объяснения
        components = {
            "home_attack_factor": round(home_attack_factor, 3),
            "away_attack_factor": round(away_attack_factor, 3),
            "home_defense_factor": round(home_defense_factor, 3),
            "away_defense_factor": round(away_defense_factor, 3),
            "home_keeper_factor": round(home_keeper_factor, 3),
            "away_keeper_factor": round(away_keeper_factor, 3),
            "control_factor": round(control_factor, 3),
            "home_bonus": round(home_bonus, 3),
            "home_form": round(home_form, 2),
            "away_form": round(away_form, 2)
        }

        # 8. Человеческое объяснение
        explanation = self._build_explanation(
            home_attack, home_defense, home_control, home_goalkeeper,
            away_attack, away_defense, away_control, away_goalkeeper,
            home_attack_factor, away_attack_factor,
            home_defense_factor, away_defense_factor,
            home_keeper_factor, away_keeper_factor,
            control_factor,
            home_xg, away_xg,
            home_form, away_form
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
        home_xg, away_xg,
        home_form=1.0, away_form=1.0
    ) -> List[str]:
        """Строит человеческое объяснение расчёта xG"""
        explanation = []

        # Форма команд
        if home_form > 1.05:
            explanation.append(f"Отличная форма хозяев (+{((home_form-1)*100):.0f}%)")
        elif home_form < 0.95:
            explanation.append(f"Плохая форма хозяев ({((home_form-1)*100):.0f}%)")

        if away_form > 1.05:
            explanation.append(f"Отличная форма гостей (+{((away_form-1)*100):.0f}%)")
        elif away_form < 0.95:
            explanation.append(f"Плохая форма гостей ({((away_form-1)*100):.0f}%)")

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

    # Тест 1: стандартный матч с полными паспортами
    home_passport = {
        "BASE": {
            "attack": 82,
            "defense": 78,
            "control": 80,
            "goalkeeper": 75,
            "tempo": 50,
            "press": 50,
            "transition": 50,
            "finishing": 50
        },
        "DYNAMIC_INITIAL": {
            "form": 50,
            "fitness": 50,
            "morale": 50,
            "fatigue": 20,
            "injury_index": 0,
            "passport_confidence": 0.4
        }
    }

    away_passport = {
        "BASE": {
            "attack": 74,
            "defense": 81,
            "control": 76,
            "goalkeeper": 79,
            "tempo": 50,
            "press": 50,
            "transition": 50,
            "finishing": 50
        },
        "DYNAMIC_INITIAL": {
            "form": 50,
            "fitness": 50,
            "morale": 50,
            "fatigue": 20,
            "injury_index": 0,
            "passport_confidence": 0.4
        }
    }

    result = model.calculate(home_passport, away_passport, home_rating=75.0, away_rating=70.0)

    print("\n⚽ FAJ XG Model v1.3 — Тест с паспортами")
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
