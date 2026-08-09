#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Monte Carlo Model v1.3
=====================================================

РОЛЬ:
    Финальная стохастическая симуляция матча
    на основе уже рассчитанных xG.

АРХИТЕКТУРА:

    Team Passport
          ↓
    FAJ XG Model
          ↓
    Poisson Model
          ↓
    Monte Carlo Model
          ↓
    Final Prediction

ВАЖНО:
    Monte Carlo НЕ рассчитывает xG.
    Monte Carlo НЕ использует bookmaker odds.
    Monte Carlo НЕ изменяет FAJ Rating.
    Monte Carlo получает готовые xG и моделирует
    распределение возможных результатов матча.

ВХОД:
    home_xg: float
    away_xg: float
    iterations: int
    seed: Optional[int]

ВЫХОД:
    {
        "home_win": float,
        "draw": float,
        "away_win": float,

        "double_chance": {
            "home_or_draw": float,
            "draw_or_away": float,
            "home_or_away": float
        },

        "btts_probability": float,
        "btts_no_probability": float,

        "over_2_5": float,
        "under_2_5": float,

        "expected_total": float,

        "goals_home": [...],
        "goals_away": [...],

        "score_probabilities": {...},
        "top_scores": [...],
        "most_likely_score": str,
        "score_probability": float,

        "iterations": int,
        "convergence": float,

        "model_version": "FAJ_MC_v1.3"
    }

=====================================================
"""

import logging
import math
import random

from typing import Dict, Any, Optional, List

from app.config import config


logger = logging.getLogger(__name__)


class MonteCarloModel:
    """
    FAJ Monte Carlo Model v1.3

    Симулирует футбольный матч на основе
    двух независимых распределений Пуассона:

        Home Goals ~ Poisson(home_xg)
        Away Goals ~ Poisson(away_xg)

    xG уже рассчитывается XG Model.

    Monte Carlo отвечает только за:
        - распределение результатов;
        - вероятности 1/X/2;
        - BTTS;
        - тоталы;
        - наиболее вероятные счета;
        - статистическую устойчивость симуляции.
    """

    VERSION = "1.3"
    MODEL_VERSION = "FAJ_MC_v1.3"

    # ============================================================
    # CONFIGURATION
    # ============================================================

    DEFAULT_ITERATIONS = config.MONTE_CARLO_ITERATIONS

    MIN_ITERATIONS = 100
    MAX_ITERATIONS = 1_000_000

    XG_MIN = config.MONTE_CARLO_XG_MIN
    XG_MAX = config.MONTE_CARLO_XG_MAX

    MAX_GOALS = config.MAX_GOALS

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self):
        """
        Создаём собственный генератор случайных чисел.

        Важно:
            НЕ используется глобальный random.seed().

        Это предотвращает побочные эффекты для других
        частей FAJ Platform.
        """

        self.version = self.VERSION
        self._rng = random.Random()

        logger.info(
            "Monte Carlo Model v%s initialized | "
            "iterations=%s | xg_range=[%.2f, %.2f] | max_goals=%s",
            self.VERSION,
            self.DEFAULT_ITERATIONS,
            self.XG_MIN,
            self.XG_MAX,
            self.MAX_GOALS
        )

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
        Симуляция матча методом Монте-Карло.

        Args:
            home_xg:
                xG хозяев.

            away_xg:
                xG гостей.

            iterations:
                Количество симуляций.

            seed:
                Необязательный seed для воспроизводимости.

        Returns:
            Словарь с вероятностями и распределениями.
        """

        # ========================================================
        # 1. VALIDATE INPUT
        # ========================================================

        try:
            home_xg = float(home_xg)
            away_xg = float(away_xg)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"xG must be numeric: "
                f"home_xg={home_xg}, away_xg={away_xg}"
            ) from exc

        try:
            iterations = int(iterations)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"iterations must be integer: {iterations}"
            ) from exc

        if iterations < self.MIN_ITERATIONS:
            raise ValueError(
                f"iterations={iterations} is too small. "
                f"Minimum={self.MIN_ITERATIONS}"
            )

        if iterations > self.MAX_ITERATIONS:
            logger.warning(
                "iterations=%s exceeds MAX_ITERATIONS=%s. "
                "Clamped.",
                iterations,
                self.MAX_ITERATIONS
            )
            iterations = self.MAX_ITERATIONS

        # ========================================================
        # 2. CLAMP XG
        # ========================================================

        original_home_xg = home_xg
        original_away_xg = away_xg

        home_xg = self._clamp_xg(home_xg)
        away_xg = self._clamp_xg(away_xg)

        if (
            original_home_xg != home_xg
            or original_away_xg != away_xg
        ):
            logger.warning(
                "Monte Carlo xG clamped | "
                "input=%.3f:%.3f | used=%.3f:%.3f",
                original_home_xg,
                original_away_xg,
                home_xg,
                away_xg
            )

        # ========================================================
        # 3. LOCAL RNG
        # ========================================================

        if seed is not None:
            rng = random.Random(seed)
        else:
            rng = self._rng

        # ========================================================
        # 4. COUNTERS
        # ========================================================

        home_wins = 0
        draws = 0
        away_wins = 0

        btts_count = 0

        over_2_5_count = 0
        under_2_5_count = 0

        # ========================================================
        # 5. GOAL DISTRIBUTIONS
        # ========================================================

        goals_home = [0] * (self.MAX_GOALS + 1)
        goals_away = [0] * (self.MAX_GOALS + 1)

        # ========================================================
        # 6. SCORE DISTRIBUTION
        # ========================================================

        score_distribution: Dict[str, int] = {}

        # ========================================================
        # 7. TOTAL GOALS
        # ========================================================

        total_goals_sum = 0.0

        # ========================================================
        # 8. SIMULATION
        # ========================================================

        for _ in range(iterations):

            home_goals = self._sample_poisson(
                home_xg,
                rng
            )

            away_goals = self._sample_poisson(
                away_xg,
                rng
            )

            # ----------------------------------------------------
            # MAX GOALS
            # ----------------------------------------------------

            if home_goals > self.MAX_GOALS:
                home_goals = self.MAX_GOALS

            if away_goals > self.MAX_GOALS:
                away_goals = self.MAX_GOALS

            # ----------------------------------------------------
            # GOAL DISTRIBUTIONS
            # ----------------------------------------------------

            goals_home[home_goals] += 1
            goals_away[away_goals] += 1

            # ----------------------------------------------------
            # SCORE
            # ----------------------------------------------------

            score_key = f"{home_goals}:{away_goals}"

            score_distribution[score_key] = (
                score_distribution.get(score_key, 0) + 1
            )

            # ----------------------------------------------------
            # RESULT
            # ----------------------------------------------------

            if home_goals > away_goals:
                home_wins += 1

            elif home_goals == away_goals:
                draws += 1

            else:
                away_wins += 1

            # ----------------------------------------------------
            # BTTS
            # ----------------------------------------------------

            if home_goals > 0 and away_goals > 0:
                btts_count += 1

            # ----------------------------------------------------
            # TOTAL
            # ----------------------------------------------------

            total_goals = home_goals + away_goals

            total_goals_sum += total_goals

            if total_goals > 2:
                over_2_5_count += 1
            else:
                under_2_5_count += 1

        # ========================================================
        # 9. PROBABILITIES
        # ========================================================

        home_probability = home_wins / iterations
        draw_probability = draws / iterations
        away_probability = away_wins / iterations

        btts_probability = btts_count / iterations

        over_2_5_probability = (
            over_2_5_count / iterations
        )

        under_2_5_probability = (
            under_2_5_count / iterations
        )

        # ========================================================
        # 10. SCORE PROBABILITIES
        # ========================================================

        score_probabilities = {
            score: round(
                count / iterations,
                6
            )
            for score, count in score_distribution.items()
        }

        # ========================================================
        # 11. TOP SCORES
        # ========================================================

        sorted_scores = sorted(
            score_distribution.items(),
            key=lambda item: item[1],
            reverse=True
        )

        top_scores = [
            {
                "score": score,
                "probability": round(
                    count / iterations,
                    6
                )
            }
            for score, count in sorted_scores[:5]
        ]

        # ========================================================
        # 12. MOST LIKELY SCORE
        # ========================================================

        if sorted_scores:

            most_likely_score = sorted_scores[0][0]

            most_likely_score_probability = (
                sorted_scores[0][1] / iterations
            )

        else:

            most_likely_score = "0:0"
            most_likely_score_probability = 0.0

        # ========================================================
        # 13. DOUBLE CHANCE
        # ========================================================

        home_or_draw = (
            home_probability
            + draw_probability
        )

        draw_or_away = (
            draw_probability
            + away_probability
        )

        home_or_away = (
            home_probability
            + away_probability
        )

        # ========================================================
        # 14. EXPECTED TOTAL
        # ========================================================

        expected_total = (
            total_goals_sum / iterations
        )

        # ========================================================
        # 15. CONVERGENCE
        # ========================================================

        convergence = self._calculate_convergence(
            iterations
        )

        # ========================================================
        # 16. GOAL DISTRIBUTIONS
        # ========================================================

        goals_home_probability = [
            round(
                count / iterations,
                6
            )
            for count in goals_home
        ]

        goals_away_probability = [
            round(
                count / iterations,
                6
            )
            for count in goals_away
        ]

        # ========================================================
        # 17. RESULT
        # ========================================================

        result = {
            "status": "success",

            "model": "Monte Carlo Model",

            "model_version": self.MODEL_VERSION,
            "version": self.VERSION,

            # ----------------------------------------------------
            # INPUT
            # ----------------------------------------------------

            "home_xg": round(home_xg, 4),
            "away_xg": round(away_xg, 4),

            # ----------------------------------------------------
            # RESULT PROBABILITIES
            # ----------------------------------------------------

            "home_win": round(
                home_probability,
                6
            ),

            "draw": round(
                draw_probability,
                6
            ),

            "away_win": round(
                away_probability,
                6
            ),

            "result_probability": {
                "home": round(
                    home_probability,
                    6
                ),
                "draw": round(
                    draw_probability,
                    6
                ),
                "away": round(
                    away_probability,
                    6
                )
            },

            # ----------------------------------------------------
            # DOUBLE CHANCE
            # ----------------------------------------------------

            "double_chance": {
                "home_or_draw": round(
                    home_or_draw,
                    6
                ),
                "draw_or_away": round(
                    draw_or_away,
                    6
                ),
                "home_or_away": round(
                    home_or_away,
                    6
                )
            },

            # ----------------------------------------------------
            # BTTS
            # ----------------------------------------------------

            "btts_probability": round(
                btts_probability,
                6
            ),

            "btts_no_probability": round(
                1.0 - btts_probability,
                6
            ),

            # ----------------------------------------------------
            # TOTALS
            # ----------------------------------------------------

            "over_2_5": round(
                over_2_5_probability,
                6
            ),

            "under_2_5": round(
                under_2_5_probability,
                6
            ),

            "expected_total": round(
                expected_total,
                4
            ),

            # ----------------------------------------------------
            # GOAL DISTRIBUTION
            # ----------------------------------------------------

            "goals_home": goals_home_probability,

            "goals_away": goals_away_probability,

            # ----------------------------------------------------
            # SCORE DISTRIBUTION
            # ----------------------------------------------------

            "score_probabilities": score_probabilities,

            "top_scores": top_scores,

            "most_likely_score": most_likely_score,

            "score_probability": round(
                most_likely_score_probability,
                6
            ),

            # ----------------------------------------------------
            # SIMULATION
            # ----------------------------------------------------

            "iterations": iterations,

            "convergence": round(
                convergence,
                6
            ),

            # ----------------------------------------------------
            # DIAGNOSTICS
            # ----------------------------------------------------

            "xg_clamped": (
                original_home_xg != home_xg
                or original_away_xg != away_xg
            )
        }

        logger.info(
            "MC RESULT | xG=%.3f:%.3f | "
            "1X2=%.3f/%.3f/%.3f | "
            "score=%s | "
            "iterations=%s | convergence=%.3f",
            home_xg,
            away_xg,
            home_probability,
            draw_probability,
            away_probability,
            most_likely_score,
            iterations,
            convergence
        )

        return result

    # ============================================================
    # POISSON SAMPLER
    # ============================================================

    def _sample_poisson(
        self,
        lam: float,
        rng: random.Random
    ) -> int:
        """
        Генерация одного значения Пуассона.

        Используется метод обратного преобразования.

        Для футбольного xG диапазон небольшой, поэтому
        алгоритм Кнута подходит и остаётся простым
        и прозрачным.
        """

        if lam <= 0:
            return 0

        limit = math.exp(-lam)

        k = 0
        probability = 1.0

        while probability > limit:

            k += 1

            probability *= rng.random()

        return k - 1

    # ============================================================
    # XG CLAMP
    # ============================================================

    def _clamp_xg(
        self,
        value: float
    ) -> float:
        """
        Ограничение xG в диапазоне FAJ Monte Carlo.
        """

        return max(
            self.XG_MIN,
            min(
                self.XG_MAX,
                value
            )
        )

    # ============================================================
    # CONVERGENCE
    # ============================================================

    def _calculate_convergence(
        self,
        total: int
    ) -> float:
        """
        Оценка статистической устойчивости результата.

        Это НЕ вероятность исхода.

        Это диагностический показатель,
        зависящий от количества симуляций.

        Чем больше N, тем выше потенциальная
        стабильность Monte Carlo.

        Используется плавная функция:

            C = 1 - 1 / sqrt(N / 100)

        с ограничениями.

        Приблизительно:

            100    -> 0.000
            1,000  -> 0.684
            5,000  -> 0.859
            10,000 -> 0.900
            100k   -> 0.968

        Значение не следует трактовать как
        математическую вероятность точности.
        """

        if total <= 0:
            return 0.0

        convergence = (
            1.0
            - 1.0 / math.sqrt(total / 100.0)
        )

        return max(
            0.0,
            min(
                0.99,
                convergence
            )
        )

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """
        Технический статус модели.
        """

        return {
            "model": "Monte Carlo Model",
            "version": self.VERSION,
            "model_version": self.MODEL_VERSION,
            "default_iterations": self.DEFAULT_ITERATIONS,
            "min_iterations": self.MIN_ITERATIONS,
            "max_iterations": self.MAX_ITERATIONS,
            "xg_range": [
                self.XG_MIN,
                self.XG_MAX
            ],
            "max_goals": self.MAX_GOALS,
            "status": "READY"
        }

    # ============================================================
    # TEST
    # ============================================================

    def test(self) -> Dict[str, Any]:
        """
        Стандартный self-test.
        """

        return self.simulate(
            home_xg=1.72,
            away_xg=0.95,
            iterations=10_000,
            seed=42
        )


# ================================================================
# SINGLETON
# ================================================================

_mc_instance: Optional[MonteCarloModel] = None


def get_monte_carlo_model() -> MonteCarloModel:
    """
    Singleton Monte Carlo Model.
    """

    global _mc_instance

    if _mc_instance is None:
        _mc_instance = MonteCarloModel()

    return _mc_instance


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("FAJ Platform v12.0")
    print("Monte Carlo Model v1.3")
    print("=" * 70)

    model = MonteCarloModel()

    print()
    print("STATUS")
    print("-" * 70)

    print(model.status())

    print()
    print("TEST")
    print("-" * 70)

    result = model.test()

    print(
        f"xG: "
        f"{result['home_xg']:.3f} : "
        f"{result['away_xg']:.3f}"
    )

    print(
        f"Iterations: "
        f"{result['iterations']}"
    )

    print(
        f"Convergence: "
        f"{result['convergence']:.2%}"
    )

    print()
    print("1X2")
    print("-" * 70)

    print(
        f"Home: "
        f"{result['home_win']:.2%}"
    )

    print(
        f"Draw: "
        f"{result['draw']:.2%}"
    )

    print(
        f"Away: "
        f"{result['away_win']:.2%}"
    )

    print()
    print("DOUBLE CHANCE")
    print("-" * 70)

    dc = result["double_chance"]

    print(
        f"1X: "
        f"{dc['home_or_draw']:.2%}"
    )

    print(
        f"X2: "
        f"{dc['draw_or_away']:.2%}"
    )

    print(
        f"12: "
        f"{dc['home_or_away']:.2%}"
    )

    print()
    print("MARKETS")
    print("-" * 70)

    print(
        f"BTTS: "
        f"{result['btts_probability']:.2%}"
    )

    print(
        f"BTTS No: "
        f"{result['btts_no_probability']:.2%}"
    )

    print(
        f"Over 2.5: "
        f"{result['over_2_5']:.2%}"
    )

    print(
        f"Under 2.5: "
        f"{result['under_2_5']:.2%}"
    )

    print()
    print("SCORE")
    print("-" * 70)

    print(
        f"Most likely: "
        f"{result['most_likely_score']}"
    )

    print(
        f"Probability: "
        f"{result['score_probability']:.2%}"
    )

    print(
        f"Expected total: "
        f"{result['expected_total']:.3f}"
    )

    print()
    print("TOP 5 SCORES")
    print("-" * 70)

    for item in result["top_scores"]:
        print(
            f"{item['score']:>5} "
            f"{item['probability']:.2%}"
        )

    print()
    print("=" * 70)
    print("Monte Carlo Model v1.3 — READY")
    print("=" * 70)
