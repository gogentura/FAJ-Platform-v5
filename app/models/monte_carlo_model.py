#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Monte Carlo Model v1.2

РОЛЬ:
    Симуляция матчей методом Монте-Карло.
=====================================================
"""

import math
import random
import logging
from typing import Dict, Any, Optional

from app.config import config

logger = logging.getLogger(__name__)


class MonteCarloModel:
    """
    Monte Carlo Model v1.2
    """

    VERSION = "1.2"

    DEFAULT_ITERATIONS = config.MONTE_CARLO_ITERATIONS

    def __init__(self):
        self.version = self.VERSION
        self._rng = None
        logger.info(f"Monte Carlo Model v{self.VERSION} initialized")

    def simulate(
        self,
        home_xg: float,
        away_xg: float,
        iterations: int = DEFAULT_ITERATIONS,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Симуляция матча методом Монте-Карло
        
        Args:
            home_xg: ожидаемые голы хозяев
            away_xg: ожидаемые голы гостей
            iterations: количество симуляций
            seed: seed для воспроизводимости
            
        Returns:
            Dict с результатами симуляции
        """
        # Ограничиваем xG для стабильности
        home_xg = max(config.MONTE_CARLO_XG_MIN, min(config.MONTE_CARLO_XG_MAX, home_xg))
        away_xg = max(config.MONTE_CARLO_XG_MIN, min(config.MONTE_CARLO_XG_MAX, away_xg))

        # Устанавливаем seed для воспроизводимости
        if seed is not None:
            random.seed(seed)

        home_wins = 0
        draws = 0
        away_wins = 0
        
        # Для распределения голов
        max_goals = config.MAX_GOALS
        goals_home = [0] * (max_goals + 1)
        goals_away = [0] * (max_goals + 1)
        
        total_goals_distribution = {}

        for _ in range(iterations):
            # Генерируем голы по распределению Пуассона
            home_goals = self._sample_poisson(home_xg)
            away_goals = self._sample_poisson(away_xg)

            # Ограничиваем максимальное количество голов
            if home_goals > max_goals:
                home_goals = max_goals
            if away_goals > max_goals:
                away_goals = max_goals

            goals_home[home_goals] += 1
            goals_away[away_goals] += 1
            
            score_key = f"{home_goals}-{away_goals}"
            total_goals_distribution[score_key] = total_goals_distribution.get(score_key, 0) + 1

            if home_goals > away_goals:
                home_wins += 1
            elif home_goals == away_goals:
                draws += 1
            else:
                away_wins += 1

        total = iterations
        
        # Рассчитываем вероятности
        home_prob = home_wins / total
        draw_prob = draws / total
        away_prob = away_wins / total
        
        # Рассчитываем сходимость (стабильность результатов)
        convergence = self._calculate_convergence(iterations)

        # Возвращаем результат
        return {
            "home_win": round(home_prob, 4),
            "draw": round(draw_prob, 4),
            "away_win": round(away_prob, 4),
            "iterations": iterations,
            "convergence": round(convergence, 4),
            "goals_home": [round(count / total, 4) for count in goals_home],
            "goals_away": [round(count / total, 4) for count in goals_away],
            "score_probabilities": {k: round(v / total, 4) for k, v in total_goals_distribution.items()},
            "most_likely_score": max(total_goals_distribution.items(), key=lambda x: x[1])[0] if total_goals_distribution else "0-0"
        }

    def _sample_poisson(self, lam: float) -> int:
        """
        Генерация одного значения из распределения Пуассона
        Используется метод обратного преобразования
        """
        if lam <= 0:
            return 0
            
        L = math.exp(-lam)
        k = 0
        p = 1.0
        
        while p > L:
            k += 1
            p *= random.random()
            
        return k - 1

    def _calculate_convergence(self, total: int) -> float:
        """
        Расчёт сходимости Монте-Карло
        Оценка стабильности результатов на основе количества итераций
        """
        if total < 1000:
            return 0.85 + (total / 10000)
        elif total < 5000:
            return 0.95 + ((total - 1000) / 80000)
        else:
            return 0.99


def get_monte_carlo_model() -> MonteCarloModel:
    """Синглтон для MonteCarloModel"""
    global _mc_instance
    if '_mc_instance' not in globals():
        _mc_instance = MonteCarloModel()
    return _mc_instance


_mc_instance: Optional[MonteCarloModel] = None


if __name__ == "__main__":
    # Тест модели
    model = MonteCarloModel()
    
    print("=" * 60)
    print("Monte Carlo Model v1.2 — Тест")
    print("=" * 60)
    
    result = model.simulate(home_xg=1.8, away_xg=1.2, iterations=10000, seed=42)
    
    print(f"\nИтераций: {result['iterations']}")
    print(f"Сходимость: {result['convergence']:.2%}")
    print("\nВероятности:")
    print(f"  Победа хозяев: {result['home_win']:.1%}")
    print(f"  Ничья:         {result['draw']:.1%}")
    print(f"  Победа гостей: {result['away_win']:.1%}")
    print(f"\nСамый вероятный счёт: {result['most_likely_score']}")
