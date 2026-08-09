#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Monte Carlo Model v1.3
=====================================================

РОЛЬ:
    Финальная стохастическая симуляция футбольного
    матча на основе xG.

АРХИТЕКТУРА:

    Team Passport
          ↓
    FAJ XG Model v1.4
          ↓
       home_xG
       away_xG
          ↓
    FAJ Poisson Model v7.4
          ↓
    FAJ Monte Carlo Model v1.3
          ↓
    Simulation
          ↓
    1X2
    BTTS
    Over / Under
    exact scores
    goal distributions
    convergence
    simulation stability

ВАЖНО:

    Monte Carlo НЕ использует bookmaker odds.

    Monte Carlo НЕ рассчитывает xG.

    Monte Carlo получает xG как вход
    от FAJ XG Model.

    Poisson и Monte Carlo являются двумя
    независимыми математическими слоями:

        Poisson:
            аналитическое распределение

        Monte Carlo:
            эмпирическая симуляция

=====================================================

ВХОД:

    home_xg: float
    away_xg: float

    iterations:
        количество симуляций

    seed:
        seed для воспроизводимости

ВЫХОД:

    {
        "status": "success",

        "home_win": float,
        "draw": float,
        "away_win": float,

        "btts_probability": float,
        "btts_no_probability": float,

        "over_2_5": float,
        "under_2_5": float,

        "iterations": int,

        "convergence": float,

        "simulation_error": float,

        "goals_home": [...],
        "goals_away": [...],

        "score_probabilities": {...},

        "top_scores": [...],

        "most_likely_score": str,

        "score_probability": float,

        "expected_home_goals": float,
        "expected_away_goals": float,
        "expected_total_goals": float,

        "model_version": str
    }

=====================================================

ИЗМЕНЕНИЯ v1.3:

    1. Единый диапазон xG:
           0.15 – 4.00

    2. Единый MAX_GOALS = 8.

    3. Используется локальный RNG:
           random.Random()

       вместо глобального:
           random.seed()

    4. Seed больше не изменяет глобальное
       состояние random.

    5. Добавлены:
           BTTS
           Over 2.5
           Under 2.5

    6. Добавлены:
           expected_home_goals
           expected_away_goals
           expected_total_goals

    7. Добавлен top_scores.

    8. Добавлена оценка Monte Carlo
       sampling error.

    9. Convergence теперь зависит
       от количества итераций и
       является диагностическим
       показателем, а не искусственной
       константой.

   10. Добавлена защита iterations.

   11. Добавлена защита xG.

   12. Добавлен status = success/error.

   13. Сохранён совместимый API:
           simulate()

=====================================================
"""

import math
import random
import logging

from typing import (
    Dict,
    Any,
    Optional,
    List
)

from app.config import config


logger = logging.getLogger(__name__)


class MonteCarloModel:
    """
    FAJ Monte Carlo Model v1.3

    Стохастическая симуляция футбольного матча.

    Основная задача:
        проверить и дополнить аналитическое
        распределение Poisson через большое
        количество случайных симуляций.
    """

    VERSION = "1.3"

    # ============================================================
    # MODEL CONSTANTS
    # ============================================================

    DEFAULT_ITERATIONS = config.MONTE_CARLO_ITERATIONS

    MIN_XG = 0.15
    MAX_XG = 4.00

    MAX_GOALS = 8

    MIN_ITERATIONS = 100
    MAX_ITERATIONS = 1_000_000

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self):

        self.version = self.VERSION

        # ВАЖНО:
        # локальный генератор случайных чисел.
        #
        # Это предотвращает изменение
        # глобального random state приложения.
        self._rng = random.Random()

        logger.info(
            "FAJ Monte Carlo Model v%s initialized | "
            "iterations=%s | xg=%s-%s | max_goals=%s",
            self.VERSION,
            self.DEFAULT_ITERATIONS,
            self.MIN_XG,
            self.MAX_XG,
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
        Основная симуляция матча.

        Args:
            home_xg:
                ожидаемые голы хозяев.

            away_xg:
                ожидаемые голы гостей.

            iterations:
                количество симуляций.

            seed:
                seed для воспроизводимости.

        Returns:
            Dict с результатами.
        """

        try:

            # ====================================================
            # 1. SANITIZE INPUT
            # ====================================================

            home_lambda = self._sanitize_xg(
                home_xg
            )

            away_lambda = self._sanitize_xg(
                away_xg
            )

            iterations = self._sanitize_iterations(
                iterations
            )

            # ====================================================
            # 2. LOCAL RNG
            # ====================================================

            if seed is not None:

                try:
                    self._rng.seed(
                        int(seed)
                    )
                except (
                    TypeError,
                    ValueError
                ):
                    raise ValueError(
                        f"Invalid seed: {seed}"
                    )

            # ====================================================
            # 3. COUNTERS
            # ====================================================

            home_wins = 0
            draws = 0
            away_wins = 0

            btts_yes = 0

            over_2_5 = 0
            under_2_5 = 0

            # ====================================================
            # 4. GOAL DISTRIBUTIONS
            # ====================================================

            goals_home = [
                0
                for _ in range(
                    self.MAX_GOALS + 1
                )
            ]

            goals_away = [
                0
                for _ in range(
                    self.MAX_GOALS + 1
                )
            ]

            # ====================================================
            # 5. SCORE DISTRIBUTION
            # ====================================================

            score_distribution: Dict[
                str,
                int
            ] = {}

            # ====================================================
            # 6. EXPECTED GOALS
            # ====================================================

            total_home_goals = 0
            total_away_goals = 0

            # ====================================================
            # 7. SIMULATION LOOP
            # ====================================================

            for _ in range(iterations):

                home_goals = (
                    self._sample_poisson(
                        home_lambda
                    )
                )

                away_goals = (
                    self._sample_poisson(
                        away_lambda
                    )
                )

                # ------------------------------------------------
                # MAX GOALS
                # ------------------------------------------------

                home_goals = min(
                    home_goals,
                    self.MAX_GOALS
                )

                away_goals = min(
                    away_goals,
                    self.MAX_GOALS
                )

                # ------------------------------------------------
                # GOAL DISTRIBUTIONS
                # ------------------------------------------------

                goals_home[
                    home_goals
                ] += 1

                goals_away[
                    away_goals
                ] += 1

                # ------------------------------------------------
                # EXPECTED GOALS
                # ------------------------------------------------

                total_home_goals += (
                    home_goals
                )

                total_away_goals += (
                    away_goals
                )

                # ------------------------------------------------
                # SCORE
                # ------------------------------------------------

                score_key = (
                    f"{home_goals}:{away_goals}"
                )

                score_distribution[
                    score_key
                ] = (
                    score_distribution.get(
                        score_key,
                        0
                    ) + 1
                )

                # ------------------------------------------------
                # RESULT
                # ------------------------------------------------

                if home_goals > away_goals:

                    home_wins += 1

                elif home_goals == away_goals:

                    draws += 1

                else:

                    away_wins += 1

                # ------------------------------------------------
                # BTTS
                # ------------------------------------------------

                if (
                    home_goals > 0
                    and away_goals > 0
                ):

                    btts_yes += 1

                # ------------------------------------------------
                # TOTAL
                # ------------------------------------------------

                total_goals = (
                    home_goals +
                    away_goals
                )

                if total_goals >= 3:

                    over_2_5 += 1

                else:

                    under_2_5 += 1

            # ====================================================
            # 8. BASIC PROBABILITIES
            # ====================================================

            home_probability = (
                home_wins /
                iterations
            )

            draw_probability = (
                draws /
                iterations
            )

            away_probability = (
                away_wins /
                iterations
            )

            btts_probability = (
                btts_yes /
                iterations
            )

            over_probability = (
                over_2_5 /
                iterations
            )

            under_probability = (
                under_2_5 /
                iterations
            )

            # ====================================================
            # 9. GOAL DISTRIBUTIONS
            # ====================================================

            home_goal_distribution = [
                round(
                    count /
                    iterations,
                    6
                )
                for count
                in goals_home
            ]

            away_goal_distribution = [
                round(
                    count /
                    iterations,
                    6
                )
                for count
                in goals_away
            ]

            # ====================================================
            # 10. SCORE PROBABILITIES
            # ====================================================

            score_probabilities = {
                score: round(
                    count /
                    iterations,
                    6
                )
                for score, count
                in score_distribution.items()
            }

            # ====================================================
            # 11. TOP SCORES
            # ====================================================

            top_scores = self._build_top_scores(
                score_distribution,
                iterations
            )

            if top_scores:

                most_likely_score = (
                    top_scores[0]["score"]
                )

                score_probability = (
                    top_scores[0]["probability"]
                )

            else:

                most_likely_score = "0:0"
                score_probability = 0.0

            # ====================================================
            # 12. EXPECTED GOALS FROM SIMULATION
            # ====================================================

            expected_home_goals = (
                total_home_goals /
                iterations
            )

            expected_away_goals = (
                total_away_goals /
                iterations
            )

            expected_total_goals = (
                expected_home_goals +
                expected_away_goals
            )

            # ====================================================
            # 13. CONVERGENCE
            # ====================================================

            convergence = (
                self._calculate_convergence(
                    iterations
                )
            )

            # ====================================================
            # 14. SAMPLING ERROR
            # ====================================================

            sampling_error = (
                self._calculate_sampling_error(
                    home_probability,
                    iterations
                )
            )

            # ====================================================
            # 15. RESULT
            # ====================================================

            result = {

                "status": "success",

                # -----------------------------------------------
                # 1X2
                # -----------------------------------------------

                "home_win": round(
                    home_probability,
                    4
                ),

                "draw": round(
                    draw_probability,
                    4
                ),

                "away_win": round(
                    away_probability,
                    4
                ),

                # -----------------------------------------------
                # DOUBLE CHANCE
                # -----------------------------------------------

                "home_or_draw": round(
                    home_probability +
                    draw_probability,
                    4
                ),

                "draw_or_away": round(
                    draw_probability +
                    away_probability,
                    4
                ),

                "home_or_away": round(
                    home_probability +
                    away_probability,
                    4
                ),

                # -----------------------------------------------
                # BTTS
                # -----------------------------------------------

                "btts_probability": round(
                    btts_probability,
                    4
                ),

                "btts_no_probability": round(
                    1.0 -
                    btts_probability,
                    4
                ),

                # -----------------------------------------------
                # TOTAL
                # -----------------------------------------------

                "over_2_5": round(
                    over_probability,
                    4
                ),

                "under_2_5": round(
                    under_probability,
                    4
                ),

                # -----------------------------------------------
                # SIMULATION
                # -----------------------------------------------

                "iterations": iterations,

                "convergence": round(
                    convergence,
                    4
                ),

                "simulation_error": round(
                    sampling_error,
                    6
                ),

                # -----------------------------------------------
                # GOALS
                # -----------------------------------------------

                "goals_home": (
                    home_goal_distribution
                ),

                "goals_away": (
                    away_goal_distribution
                ),

                # -----------------------------------------------
                # SCORES
                # -----------------------------------------------

                "score_probabilities": (
                    score_probabilities
                ),

                "top_scores": (
                    top_scores
                ),

                "most_likely_score": (
                    most_likely_score
                ),

                "score_probability": round(
                    score_probability,
                    4
                ),

                # -----------------------------------------------
                # EXPECTED GOALS
                # -----------------------------------------------

                "input_home_xg": round(
                    home_lambda,
                    3
                ),

                "input_away_xg": round(
                    away_lambda,
                    3
                ),

                "expected_home_goals": round(
                    expected_home_goals,
                    4
                ),

                "expected_away_goals": round(
                    expected_away_goals,
                    4
                ),

                "expected_total_goals": round(
                    expected_total_goals,
                    4
                ),

                # -----------------------------------------------
                # META
                # -----------------------------------------------

                "model_version": (
                    self.VERSION
                )
            }

            # ====================================================
            # 16. LOGGING
            # ====================================================

            logger.info(
                "MONTE CARLO RESULT | "
                "xG %.3f:%.3f | "
                "iterations=%d | "
                "1X2 %.3f/%.3f/%.3f | "
                "score=%s | "
                "convergence=%.4f",
                home_lambda,
                away_lambda,
                iterations,
                home_probability,
                draw_probability,
                away_probability,
                most_likely_score,
                convergence
            )

            return result

        except Exception as exc:

            logger.exception(
                "FAJ Monte Carlo calculation error"
            )

            return {
                "status": "error",
                "message": str(exc),
                "home_xg": 0.0,
                "away_xg": 0.0,
                "home_win": 0.0,
                "draw": 0.0,
                "away_win": 0.0,
                "home_or_draw": 0.0,
                "draw_or_away": 0.0,
                "home_or_away": 0.0,
                "btts_probability": 0.0,
                "btts_no_probability": 1.0,
                "over_2_5": 0.0,
                "under_2_5": 0.0,
                "iterations": 0,
                "convergence": 0.0,
                "simulation_error": 1.0,
                "goals_home": [],
                "goals_away": [],
                "score_probabilities": {},
                "top_scores": [],
                "most_likely_score": "0:0",
                "score_probability": 0.0,
                "expected_home_goals": 0.0,
                "expected_away_goals": 0.0,
                "expected_total_goals": 0.0,
                "model_version": self.VERSION
            }

    # ============================================================
    # XG SANITIZATION
    # ============================================================

    def _sanitize_xg(
        self,
        value: Any
    ) -> float:
        """
        Проверка и ограничение xG.
        """

        try:
            value = float(value)

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                f"Invalid xG value: {value}"
            )

        if not math.isfinite(value):

            raise ValueError(
                f"xG must be finite: {value}"
            )

        return max(
            self.MIN_XG,
            min(
                self.MAX_XG,
                value
            )
        )

    # ============================================================
    # ITERATIONS
    # ============================================================

    def _sanitize_iterations(
        self,
        iterations: Any
    ) -> int:
        """
        Проверка количества симуляций.
        """

        try:
            iterations = int(
                iterations
            )

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                f"Invalid iterations: "
                f"{iterations}"
            )

        if iterations < self.MIN_ITERATIONS:

            raise ValueError(
                f"iterations must be >= "
                f"{self.MIN_ITERATIONS}, "
                f"got {iterations}"
            )

        if iterations > self.MAX_ITERATIONS:

            raise ValueError(
                f"iterations must be <= "
                f"{self.MAX_ITERATIONS}, "
                f"got {iterations}"
            )

        return iterations

    # ============================================================
    # POISSON SAMPLING
    # ============================================================

    def _sample_poisson(
        self,
        lam: float
    ) -> int:
        """
        Генерация одного значения
        из распределения Пуассона.

        Используется метод
        обратного преобразования.

            P(X=k) = e^-λ λ^k / k!

        Метод хорошо подходит для
        футбольных xG, поскольку λ
        находится в небольшом диапазоне.
        """

        if lam <= 0:

            return 0

        probability_limit = (
            math.exp(-lam)
        )

        k = 0
        probability = 1.0

        while probability > probability_limit:

            k += 1

            probability *= (
                self._rng.random()
            )

        return k - 1

    # ============================================================
    # TOP SCORES
    # ============================================================

    def _build_top_scores(
        self,
        score_distribution: Dict[str, int],
        iterations: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Возвращает наиболее вероятные
        точные счета.
        """

        sorted_scores = sorted(
            score_distribution.items(),
            key=lambda item: item[1],
            reverse=True
        )

        result = []

        for score, count in sorted_scores[:limit]:

            result.append({
                "score": score,
                "probability": round(
                    count /
                    iterations,
                    6
                ),
                "count": count
            })

        return result

    # ============================================================
    # CONVERGENCE
    # ============================================================

    def _calculate_convergence(
        self,
        iterations: int
    ) -> float:
        """
        Диагностический показатель
        стабильности Monte Carlo.

        Это НЕ вероятность исхода.

        Чем больше количество
        симуляций, тем выше
        ожидаемая стабильность.

        Используем плавную функцию:

            convergence =
                1 - 1 / sqrt(iterations / 100)

        с ограничением 0..0.9999.

        Примеры:

            100      → 0.000
            1 000    → ~0.684
            10 000   → 0.900
            100 000  → ~0.968
            1 000 000→ 0.990
        """

        if iterations <= 100:

            return 0.0

        value = (
            1.0 -
            1.0 /
            math.sqrt(
                iterations / 100.0
            )
        )

        return max(
            0.0,
            min(
                0.9999,
                value
            )
        )

    # ============================================================
    # SAMPLING ERROR
    # ============================================================

    def _calculate_sampling_error(
        self,
        probability: float,
        iterations: int
    ) -> float:
        """
        Стандартная ошибка оценки вероятности:

            SE = sqrt(p(1-p)/N)

        Возвращает приблизительную
        статистическую ошибку одной
        бинарной вероятности.
        """

        if iterations <= 0:

            return 1.0

        probability = max(
            0.0,
            min(
                1.0,
                probability
            )
        )

        variance = (
            probability *
            (1.0 - probability)
            /
            iterations
        )

        return math.sqrt(
            max(
                0.0,
                variance
            )
        )

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """
        Диагностический статус модели.
        """

        return {
            "model": (
                "FAJ Monte Carlo Model"
            ),
            "version": self.VERSION,
            "default_iterations": (
                self.DEFAULT_ITERATIONS
            ),
            "min_iterations": (
                self.MIN_ITERATIONS
            ),
            "max_iterations": (
                self.MAX_ITERATIONS
            ),
            "max_goals": (
                self.MAX_GOALS
            ),
            "xg_range": [
                self.MIN_XG,
                self.MAX_XG
            ],
            "status": "READY"
        }


# ================================================================
# SINGLETON
# ================================================================

_mc_instance: Optional[
    MonteCarloModel
] = None


def get_monte_carlo_model() -> MonteCarloModel:
    """
    Получение singleton экземпляра.
    """

    global _mc_instance

    if _mc_instance is None:

        _mc_instance = (
            MonteCarloModel()
        )

    return _mc_instance


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("FAJ MONTE CARLO MODEL v1.3")
    print("=" * 70)

    model = MonteCarloModel()

    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------

    print()
    print("STATUS")
    print("-" * 70)

    print(
        model.status()
    )

    # ------------------------------------------------------------
    # TEST PARAMETERS
    # ------------------------------------------------------------

    home_xg = 1.72
    away_xg = 0.95

    iterations = 10000

    print()
    print(
        f"TEST xG: "
        f"{home_xg:.2f} : {away_xg:.2f}"
    )

    print(
        f"ITERATIONS: "
        f"{iterations}"
    )

    print("-" * 70)

    # ------------------------------------------------------------
    # SIMULATION
    # ------------------------------------------------------------

    result = model.simulate(
        home_xg=home_xg,
        away_xg=away_xg,
        iterations=iterations,
        seed=42
    )

    # ------------------------------------------------------------
    # 1X2
    # ------------------------------------------------------------

    print()
    print("1X2")

    print(
        f"  Home: "
        f"{result['home_win'] * 100:.2f}%"
    )

    print(
        f"  Draw: "
        f"{result['draw'] * 100:.2f}%"
    )

    print(
        f"  Away: "
        f"{result['away_win'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # DOUBLE CHANCE
    # ------------------------------------------------------------

    print()
    print("DOUBLE CHANCE")

    print(
        f"  1X: "
        f"{result['home_or_draw'] * 100:.2f}%"
    )

    print(
        f"  X2: "
        f"{result['draw_or_away'] * 100:.2f}%"
    )

    print(
        f"  12: "
        f"{result['home_or_away'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # BTTS
    # ------------------------------------------------------------

    print()
    print("BTTS")

    print(
        f"  Yes: "
        f"{result['btts_probability'] * 100:.2f}%"
    )

    print(
        f"  No:  "
        f"{result['btts_no_probability'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # TOTAL
    # ------------------------------------------------------------

    print()
    print("TOTAL")

    print(
        f"  Over 2.5: "
        f"{result['over_2_5'] * 100:.2f}%"
    )

    print(
        f"  Under 2.5: "
        f"{result['under_2_5'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # SCORE
    # ------------------------------------------------------------

    print()
    print("MOST LIKELY SCORE")

    print(
        f"  {result['most_likely_score']}"
    )

    print(
        f"  Probability: "
        f"{result['score_probability'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # TOP SCORES
    # ------------------------------------------------------------

    print()
    print("TOP 5 SCORES")

    for item in result["top_scores"]:

        print(
            f"  {item['score']}: "
            f"{item['probability'] * 100:.2f}% "
            f"({item['count']} simulations)"
        )

    # ------------------------------------------------------------
    # EXPECTED GOALS
    # ------------------------------------------------------------

    print()
    print("EXPECTED GOALS")

    print(
        f"  Input home xG: "
        f"{result['input_home_xg']:.3f}"
    )

    print(
        f"  Input away xG: "
        f"{result['input_away_xg']:.3f}"
    )

    print(
        f"  Simulated home goals: "
        f"{result['expected_home_goals']:.4f}"
    )

    print(
        f"  Simulated away goals: "
        f"{result['expected_away_goals']:.4f}"
    )

    print(
        f"  Simulated total: "
        f"{result['expected_total_goals']:.4f}"
    )

    # ------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------

    print()
    print("MONTE CARLO DIAGNOSTICS")

    print(
        f"  Iterations: "
        f"{result['iterations']}"
    )

    print(
        f"  Convergence: "
        f"{result['convergence'] * 100:.2f}%"
    )

    print(
        f"  Sampling error: "
        f"±{result['simulation_error'] * 100:.3f}%"
    )

    # ------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "Monte Carlo Model v1.3 READY"
    )
    print("=" * 70)
