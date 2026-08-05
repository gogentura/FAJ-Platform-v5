#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Monte Carlo Model v1.1

РОЛЬ:
    Симуляция матчей методом Монте-Карло.
    Генерирует распределение результатов на основе xG.

ВХОД:
    home_xg: float — ожидаемые голы хозяев
    away_xg: float — ожидаемые голы гостей
    iterations: int — количество симуляций
    seed: int — для воспроизводимости

ВЫХОД:
    {
        "home_win": float,
        "draw": float,
        "away_win": float,
        "iterations": int,
        "expected_total": float,
        "variance": {"home": float, "draw": float, "away": float},
        "stability": float,
        "top_scores": [...],
        "total_goals_distribution": {...}
    }

ИЗМЕНЕНИЯ v1.1:
    - Локальный RNG (не влияет на глобальный random)
    - Добавлена variance для Confidence Engine
    - Добавлена stability (сходимость симуляции)
=====================================================
"""

import math
import random
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MonteCarloModel:
    """
    Monte Carlo Model v1.1
    Симуляция матчей методом Монте-Карло
    """

    VERSION = "1.1"

    DEFAULT_ITERATIONS = 10000
    MAX_GOALS = 10

    def __init__(self):
        self.version = self.VERSION
        self._rng = None
        logger.info(f"Monte Carlo Model v{self.VERSION} initialized")

    # ============================================================
    # PUBLIC API
    # ============================================================

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
            seed: для воспроизводимости

        Returns:
            Dict с распределением результатов
        """
        # Локальный генератор (не влияет на глобальный random)
        if seed is not None:
            self._rng = random.Random(seed)
        else:
            self._rng = random.Random()

        home_wins = 0
        draws = 0
        away_wins = 0

        total_goals_dist = {}
        score_dist = {}

        # Для расчёта variance
        results = []

        for _ in range(iterations):
            home_goals = self._poisson_random(home_xg)
            away_goals = self._poisson_random(away_xg)

            # Определяем исход
            if home_goals > away_goals:
                result = "home"
                home_wins += 1
            elif home_goals == away_goals:
                result = "draw"
                draws += 1
            else:
                result = "away"
                away_wins += 1

            results.append(result)

            # Распределение тоталов
            total = home_goals + away_goals
            total_goals_dist[total] = total_goals_dist.get(total, 0) + 1

            # Распределение счетов
            key = f"{home_goals}:{away_goals}"
            score_dist[key] = score_dist.get(key, 0) + 1

        # Вероятности
        home_prob = home_wins / iterations
        draw_prob = draws / iterations
        away_prob = away_wins / iterations

        # Дисперсия (variance)
        variance = self._calculate_variance(results)

        # Стабильность (сходимость)
        stability = self._calculate_stability(home_prob, draw_prob, away_prob, iterations)

        # Нормализация распределения тоталов
        total_goals_dist_norm = {
            k: v / iterations for k, v in total_goals_dist.items()
        }

        # Топ-5 счетов
        top_scores = sorted(
            score_dist.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        top_scores_result = [
            {"score": score, "count": count, "probability": count / iterations}
            for score, count in top_scores
        ]

        return {
            "iterations": iterations,
            "home_win": round(home_prob, 4),
            "draw": round(draw_prob, 4),
            "away_win": round(away_prob, 4),
            "expected_total": round(home_xg + away_xg, 3),
            "variance": {
                "home": round(variance.get("home", 0), 4),
                "draw": round(variance.get("draw", 0), 4),
                "away": round(variance.get("away", 0), 4)
            },
            "stability": round(stability, 3),
            "top_scores": top_scores_result,
            "total_goals_distribution": total_goals_dist_norm,
            "seed_used": seed
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _poisson_random(self, lam: float) -> int:
        """Генерация по распределению Пуассона (локальный RNG)"""
        if lam <= 0:
            return 0

        L = math.exp(-lam)
        p = 1.0
        k = 0
        while p > L:
            k += 1
            p *= self._rng.random()
        return k - 1

    def _calculate_variance(self, results: list) -> Dict[str, float]:
        """Расчёт дисперсии результатов"""
        n = len(results)
        if n == 0:
            return {"home": 0, "draw": 0, "away": 0}

        home_count = results.count("home")
        draw_count = results.count("draw")
        away_count = results.count("away")

        home_prob = home_count / n
        draw_prob = draw_count / n
        away_prob = away_count / n

        # Дисперсия Бернулли: p * (1-p)
        return {
            "home": home_prob * (1 - home_prob),
            "draw": draw_prob * (1 - draw_prob),
            "away": away_prob * (1 - away_prob)
        }

    def _calculate_stability(
        self,
        home: float,
        draw: float,
        away: float,
        iterations: int
    ) -> float:
        """
        Расчёт стабильности симуляции

        Основа:
        - Чем больше итераций, тем выше стабильность
        - Чем выше max_prob, тем выше стабильность
        """
        max_prob = max(home, draw, away)

        # Базовый фактор: чем больше итераций, тем лучше
        iter_factor = min(1.0, iterations / self.DEFAULT_ITERATIONS)

        # Фактор уверенности: чем выше max_prob, тем стабильнее
        prob_factor = 0.5 + max_prob * 0.5

        stability = iter_factor * prob_factor
        return max(0.0, min(1.0, stability))

    # ============================================================
    # DIAGNOSTICS
    # ============================================================

    def status(self) -> Dict:
        return {
            "model": "Monte Carlo Model",
            "version": self.VERSION,
            "default_iterations": self.DEFAULT_ITERATIONS,
            "status": "READY"
        }

    def test(self) -> Dict:
        return self.simulate(1.72, 0.95, iterations=1000, seed=42)


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ Monte Carlo Model v1.1 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    model = MonteCarloModel()

    print("\n📊 Status:")
    print(model.status())

    print("\n📋 Тест: xG 1.72 : 0.95, 1000 итераций")
    print("-" * 40)

    result = model.test()

    print(f"\n  📊 Home: {result['home_win']*100:.1f}%")
    print(f"  📊 Draw: {result['draw']*100:.1f}%")
    print(f"  📊 Away: {result['away_win']*100:.1f}%")
    print(f"  📊 Expected total: {result['expected_total']:.2f}")
    print(f"  📊 Iterations: {result['iterations']}")
    print(f"  📊 Stability: {result['stability']*100:.1f}%")

    print(f"\n  📊 Variance:")
    print(f"    Home: {result['variance']['home']:.4f}")
    print(f"    Draw: {result['variance']['draw']:.4f}")
    print(f"    Away: {result['variance']['away']:.4f}")

    print("\n  📋 Топ-5 счетов:")
    for item in result['top_scores'][:5]:
        print(f"    {item['score']}: {item['probability']*100:.2f}%")

    print("\n" + "=" * 60)
    print("✅ Monte Carlo Model v1.1 готов к работе.")
    print("=" * 60)
