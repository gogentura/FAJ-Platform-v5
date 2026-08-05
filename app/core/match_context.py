#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Match Context

РОЛЬ:
    Единый объект контекста матча для всех модулей.
    Предотвращает хаос с разными названиями полей.

ИСПОЛЬЗОВАНИЕ:
    context = MatchContext(
        injuries=0.1,
        fatigue=0.2,
        motivation=0.8,
        coach_factor=0.75,
        squad_stability=0.85,
        cup_match=False
    )

    confidence_engine.calculate(raw, calibrated, context)
    risk_engine.calculate(raw, calibrated, confidence, context)
=====================================================
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MatchContext:
    """
    Контекст матча для Confidence и Risk Engine

    Все значения нормализованы от 0.0 до 1.0, кроме cup_match (bool)
    """

    # Травмы (0.0 = нет, 1.0 = максимальные)
    injuries: float = 0.0

    # Усталость (0.0 = нет, 1.0 = максимальная)
    fatigue: float = 0.0

    # Мотивация (0.0 = низкая, 1.0 = высокая)
    motivation: float = 0.7

    # Фактор тренера (0.0 = слабый, 1.0 = сильный)
    coach_factor: float = 0.7

    # Стабильность состава (0.0 = хаос, 1.0 = стабилен)
    squad_stability: float = 0.8

    # Кубковый матч (влияет на риск сенсации)
    cup_match: bool = False

    # Дополнительные поля (для расширения)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            "injuries": self.injuries,
            "fatigue": self.fatigue,
            "motivation": self.motivation,
            "coach_factor": self.coach_factor,
            "squad_stability": self.squad_stability,
            "cup_match": self.cup_match,
            **self.extra
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchContext":
        """Создание из словаря"""
        return cls(
            injuries=data.get("injuries", 0.0),
            fatigue=data.get("fatigue", 0.0),
            motivation=data.get("motivation", 0.7),
            coach_factor=data.get("coach_factor", 0.7),
            squad_stability=data.get("squad_stability", 0.8),
            cup_match=data.get("cup_match", False),
            extra=data.get("extra", {})
        )

    def __post_init__(self):
        """Нормализация значений после создания"""
        self.injuries = max(0.0, min(1.0, self.injuries))
        self.fatigue = max(0.0, min(1.0, self.fatigue))
        self.motivation = max(0.0, min(1.0, self.motivation))
        self.coach_factor = max(0.0, min(1.0, self.coach_factor))
        self.squad_stability = max(0.0, min(1.0, self.squad_stability))


if __name__ == "__main__":
    # Пример использования
    context = MatchContext(
        injuries=0.1,
        fatigue=0.2,
        motivation=0.85,
        coach_factor=0.8,
        squad_stability=0.9,
        cup_match=True
    )

    print("Match Context:")
    print(context)
    print("\nAs dict:")
    print(context.to_dict())
