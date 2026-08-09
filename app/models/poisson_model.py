#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
FAJ Poisson Model v7.4
=====================================================

РОЛЬ:
    Аналитический расчёт вероятностей футбольного
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
    вероятности:
        1X2
        Double Chance
        BTTS
        Over / Under
        точные счета
        распределение голов
        entropy
        stability
          ↓
    Monte Carlo Model v1.3

ВАЖНО:
    Poisson Model НЕ использует bookmaker odds.

ВХОД:
    home_xg: float
    away_xg: float

ВЫХОД:
    {
        "status": "success",
        "result_probability": {
            "home": float,
            "draw": float,
            "away": float
        },
        "double_chance": {
            "home_or_draw": float,
            "draw_or_away": float,
            "home_or_away": float
        },
        "btts_probability": float,
        "btts_no_probability": float,
        "over_2_5": float,
        "under_2_5": float,
        "most_likely_score": str,
        "score_probability": float,
        "top_scores": [...],
        "expected_total": float,
        "tail_probability": float,
        "model_stability": float,
        "score_entropy": float,
        "matrix_sum": float,
        "goals_home": [...],
        "goals_away": [...]
    }

ИЗМЕНЕНИЯ v7.4:

    1. Единый диапазон xG с FAJ XG Model:
           MIN_XG = 0.15
           MAX_XG = 4.00

    2. MAX_GOALS = 8.

    3. Матрица строится как независимое
       произведение Poisson(home) × Poisson(away).

    4. Усечённая матрица нормализуется.
       Поэтому сумма вероятностей всегда = 1.0.

    5. tail_probability рассчитывается ДО нормализации
       и показывает потерю хвоста за пределами 0..MAX_GOALS.

    6. model_stability = 1 - tail_probability.

    7. Добавлены распределения голов хозяев и гостей.

    8. Добавлена полная диагностика.

    9. Результаты 1X2, BTTS и тоталов рассчитываются
       непосредственно из единой нормализованной матрицы.

   10. Добавлена защита от некорректного xG.

   11. Добавлен status = success/error.

   12. Сохранён совместимый публичный API calculate().

=====================================================
"""

import math
import logging
from typing import Dict, List, Tuple, Optional, Any


logger = logging.getLogger(__name__)


class FAJPoissonModel:
    """
    FAJ Poisson Model v7.4

    Аналитический математический слой FAJ.

    Получает xG от FAJ XG Model и рассчитывает
    вероятностное распределение исходов матча.
    """

    VERSION = "7.4"

    # ============================================================
    # MODEL CONSTANTS
    # ============================================================

    MAX_GOALS = 8

    XG_MIN = 0.15
    XG_MAX = 4.00

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, max_goals: int = MAX_GOALS):
        try:
            max_goals = int(max_goals)
        except (TypeError, ValueError):
            max_goals = self.MAX_GOALS

        if max_goals < 3:
            max_goals = 3

        self.MAX_GOALS = max_goals

        # Кэш Poisson probability.
        self._poisson_cache: Dict[Tuple[float, int], float] = {}

        logger.info(
            "FAJ Poisson Model v%s initialized | max_goals=%s | xg=%s-%s",
            self.VERSION,
            self.MAX_GOALS,
            self.XG_MIN,
            self.XG_MAX
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def calculate(
        self,
        home_xg: float,
        away_xg: float,
        include_matrix: bool = False
    ) -> Dict[str, Any]:
        """
        Основной расчёт.

        Args:
            home_xg:
                ожидаемые голы хозяев.

            away_xg:
                ожидаемые голы гостей.

            include_matrix:
                если True — вернуть полную матрицу
                точных счетов.

        Returns:
            Словарь с вероятностями и диагностикой.
        """

        try:
            # ====================================================
            # 1. VALIDATE XG
            # ====================================================

            home_lambda = self._sanitize_xg(home_xg)
            away_lambda = self._sanitize_xg(away_xg)

            logger.info(
                "POISSON INPUT | home_xg=%.4f | away_xg=%.4f",
                home_lambda,
                away_lambda
            )

            # ====================================================
            # 2. BUILD RAW MATRIX
            # ====================================================

            raw_matrix, raw_sum = self._build_raw_score_matrix(
                home_lambda,
                away_lambda
            )

            # ====================================================
            # 3. TAIL PROBABILITY
            # ====================================================

            tail_probability = self._calculate_tail_probability(
                raw_sum
            )

            # ====================================================
            # 4. NORMALIZE MATRIX
            # ====================================================

            score_matrix = self._normalize_matrix(
                raw_matrix,
                raw_sum
            )

            # ====================================================
            # 5. MARKETS
            # ====================================================

            result = self._calculate_markets(
                score_matrix
            )

            # ====================================================
            # 6. GOAL DISTRIBUTIONS
            # ====================================================

            goals_home = self._calculate_home_goal_distribution(
                score_matrix
            )

            goals_away = self._calculate_away_goal_distribution(
                score_matrix
            )

            # ====================================================
            # 7. MODEL DIAGNOSTICS
            # ====================================================

            expected_total = (
                home_lambda +
                away_lambda
            )

            matrix_sum = sum(
                score_matrix.values()
            )

            model_stability = max(
                0.0,
                min(
                    1.0,
                    1.0 - tail_probability
                )
            )

            score_entropy = self._calculate_entropy(
                score_matrix
            )

            # ====================================================
            # 8. RESULT
            # ====================================================

            result.update({
                "status": "success",

                "home_xg": round(
                    home_lambda,
                    3
                ),

                "away_xg": round(
                    away_lambda,
                    3
                ),

                "expected_total": round(
                    expected_total,
                    3
                ),

                "tail_probability": round(
                    tail_probability,
                    6
                ),

                "model_stability": round(
                    model_stability,
                    6
                ),

                "score_entropy": round(
                    score_entropy,
                    3
                ),

                "matrix_sum": round(
                    matrix_sum,
                    6
                ),

                "goals_home": goals_home,

                "goals_away": goals_away,

                "model_version": self.VERSION
            })

            if include_matrix:
                result["score_matrix"] = {
                    f"{home}:{away}": round(
                        probability,
                        8
                    )
                    for (home, away), probability
                    in score_matrix.items()
                }

            logger.info(
                "POISSON RESULT | "
                "xG %.3f:%.3f | "
                "1X2 %.3f/%.3f/%.3f | "
                "score=%s | stability=%.4f",
                home_lambda,
                away_lambda,
                result["result_probability"]["home"],
                result["result_probability"]["draw"],
                result["result_probability"]["away"],
                result["most_likely_score"],
                model_stability
            )

            return result

        except Exception as exc:

            logger.exception(
                "FAJ Poisson calculation error"
            )

            return {
                "status": "error",
                "message": str(exc),
                "home_xg": 0.0,
                "away_xg": 0.0,
                "result_probability": {
                    "home": 0.0,
                    "draw": 0.0,
                    "away": 0.0
                },
                "double_chance": {
                    "home_or_draw": 0.0,
                    "draw_or_away": 0.0,
                    "home_or_away": 0.0
                },
                "btts_probability": 0.0,
                "btts_no_probability": 1.0,
                "over_2_5": 0.0,
                "under_2_5": 0.0,
                "most_likely_score": "0:0",
                "score_probability": 0.0,
                "top_scores": [],
                "expected_total": 0.0,
                "tail_probability": 1.0,
                "model_stability": 0.0,
                "score_entropy": 0.0,
                "matrix_sum": 0.0,
                "goals_home": [],
                "goals_away": [],
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
        Безопасная обработка xG.

        Неверное значение вызывает ошибку,
        а не молча превращается в 0 или 70.
        """

        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid xG value: {value}"
            )

        if not math.isfinite(value):
            raise ValueError(
                f"xG must be finite: {value}"
            )

        return max(
            self.XG_MIN,
            min(
                self.XG_MAX,
                value
            )
        )

    # ============================================================
    # POISSON
    # ============================================================

    def _poisson(
        self,
        lam: float,
        k: int
    ) -> float:
        """
        Вероятность ровно k голов:

            P(k) = e^-λ × λ^k / k!
        """

        if k < 0:
            return 0.0

        if lam <= 0:
            return (
                1.0
                if k == 0
                else 0.0
            )

        cache_key = (
            round(lam, 8),
            int(k)
        )

        cached = self._poisson_cache.get(
            cache_key
        )

        if cached is not None:
            return cached

        probability = (
            math.exp(-lam)
            * (lam ** k)
            / math.factorial(k)
        )

        self._poisson_cache[
            cache_key
        ] = probability

        return probability

    # ============================================================
    # RAW SCORE MATRIX
    # ============================================================

    def _build_raw_score_matrix(
        self,
        home_lambda: float,
        away_lambda: float
    ) -> Tuple[
        Dict[Tuple[int, int], float],
        float
    ]:
        """
        Строит матрицу:

            P(Home=h, Away=a)
            =
            P(Home=h) × P(Away=a)

        Матрица ограничена диапазоном
        0..MAX_GOALS.

        Возвращает:

            raw_matrix
            raw_sum
        """

        matrix: Dict[
            Tuple[int, int],
            float
        ] = {}

        total = 0.0

        home_probabilities = [
            self._poisson(
                home_lambda,
                goals
            )
            for goals in range(
                self.MAX_GOALS + 1
            )
        ]

        away_probabilities = [
            self._poisson(
                away_lambda,
                goals
            )
            for goals in range(
                self.MAX_GOALS + 1
            )
        ]

        for home_goals in range(
            self.MAX_GOALS + 1
        ):

            for away_goals in range(
                self.MAX_GOALS + 1
            ):

                probability = (
                    home_probabilities[
                        home_goals
                    ]
                    *
                    away_probabilities[
                        away_goals
                    ]
                )

                matrix[
                    (
                        home_goals,
                        away_goals
                    )
                ] = probability

                total += probability

        return matrix, total

    # ============================================================
    # TAIL
    # ============================================================

    def _calculate_tail_probability(
        self,
        raw_sum: float
    ) -> float:
        """
        Вероятность хвоста:

            1 - P(0..MAX_GOALS)

        Это вероятность того, что
        хотя бы одна команда забьёт
        больше MAX_GOALS.
        """

        if raw_sum >= 1.0:
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                1.0 - raw_sum
            )
        )

    # ============================================================
    # NORMALIZATION
    # ============================================================

    def _normalize_matrix(
        self,
        matrix: Dict[Tuple[int, int], float],
        total: float
    ) -> Dict[Tuple[int, int], float]:
        """
        Нормализация усечённой матрицы.

        После нормализации:

            sum(matrix) = 1.0
        """

        if total <= 0:
            raise RuntimeError(
                "Cannot normalize Poisson matrix: "
                f"sum={total:.12f}"
            )

        return {
            key: probability / total
            for key, probability
            in matrix.items()
        }

    # ============================================================
    # MARKETS
    # ============================================================

    def _calculate_markets(
        self,
        matrix: Dict[Tuple[int, int], float]
    ) -> Dict[str, Any]:
        """
        Расчёт всех основных рынков
        непосредственно из матрицы.
        """

        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        btts = 0.0

        over_2_5 = 0.0
        under_2_5 = 0.0

        most_likely_score = "0:0"
        max_probability = 0.0

        scores: List[
            Dict[str, Any]
        ] = []

        for (
            home_goals,
            away_goals
        ), probability in matrix.items():

            total_goals = (
                home_goals +
                away_goals
            )

            # ----------------------------------------------------
            # 1X2
            # ----------------------------------------------------

            if home_goals > away_goals:

                home_win += probability

            elif home_goals == away_goals:

                draw += probability

            else:

                away_win += probability

            # ----------------------------------------------------
            # BTTS
            # ----------------------------------------------------

            if (
                home_goals > 0
                and away_goals > 0
            ):
                btts += probability

            # ----------------------------------------------------
            # TOTAL
            # ----------------------------------------------------

            if total_goals >= 3:

                over_2_5 += probability

            else:

                under_2_5 += probability

            # ----------------------------------------------------
            # MOST LIKELY SCORE
            # ----------------------------------------------------

            if probability > max_probability:

                max_probability = probability

                most_likely_score = (
                    f"{home_goals}:{away_goals}"
                )

            # ----------------------------------------------------
            # SCORE LIST
            # ----------------------------------------------------

            scores.append({
                "score": (
                    f"{home_goals}:{away_goals}"
                ),
                "probability": round(
                    probability,
                    6
                )
            })

        # --------------------------------------------------------
        # TOP SCORES
        # --------------------------------------------------------

        scores.sort(
            key=lambda item: item["probability"],
            reverse=True
        )

        top_scores = scores[:5]

        # --------------------------------------------------------
        # DOUBLE CHANCE
        # --------------------------------------------------------

        home_or_draw = (
            home_win +
            draw
        )

        draw_or_away = (
            draw +
            away_win
        )

        home_or_away = (
            home_win +
            away_win
        )

        return {
            "result_probability": {
                "home": round(
                    home_win,
                    4
                ),
                "draw": round(
                    draw,
                    4
                ),
                "away": round(
                    away_win,
                    4
                )
            },

            "double_chance": {
                "home_or_draw": round(
                    home_or_draw,
                    4
                ),
                "draw_or_away": round(
                    draw_or_away,
                    4
                ),
                "home_or_away": round(
                    home_or_away,
                    4
                )
            },

            "btts_probability": round(
                btts,
                4
            ),

            "btts_no_probability": round(
                1.0 - btts,
                4
            ),

            "over_2_5": round(
                over_2_5,
                4
            ),

            "under_2_5": round(
                under_2_5,
                4
            ),

            "most_likely_score": (
                most_likely_score
            ),

            "score_probability": round(
                max_probability,
                4
            ),

            "top_scores": top_scores
        }

    # ============================================================
    # GOAL DISTRIBUTIONS
    # ============================================================

    def _calculate_home_goal_distribution(
        self,
        matrix: Dict[Tuple[int, int], float]
    ) -> List[float]:
        """
        Распределение количества голов хозяев.
        """

        distribution = [
            0.0
            for _ in range(
                self.MAX_GOALS + 1
            )
        ]

        for (
            home_goals,
            away_goals
        ), probability in matrix.items():

            distribution[
                home_goals
            ] += probability

        return [
            round(
                probability,
                6
            )
            for probability in distribution
        ]

    # ------------------------------------------------------------

    def _calculate_away_goal_distribution(
        self,
        matrix: Dict[Tuple[int, int], float]
    ) -> List[float]:
        """
        Распределение количества голов гостей.
        """

        distribution = [
            0.0
            for _ in range(
                self.MAX_GOALS + 1
            )
        ]

        for (
            home_goals,
            away_goals
        ), probability in matrix.items():

            distribution[
                away_goals
            ] += probability

        return [
            round(
                probability,
                6
            )
            for probability in distribution
        ]

    # ============================================================
    # ENTROPY
    # ============================================================

    def _calculate_entropy(
        self,
        matrix: Dict[Tuple[int, int], float]
    ) -> float:
        """
        Энтропия распределения точных счетов.

        Чем выше entropy:
            тем больше неопределённость.

        Чем ниже entropy:
            тем сильнее распределение
            концентрировано вокруг нескольких
            счетов.
        """

        entropy = 0.0

        for probability in matrix.values():

            if probability > 0:

                entropy -= (
                    probability
                    *
                    math.log2(
                        probability
                    )
                )

        return entropy

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        """
        Диагностический статус модели.
        """

        return {
            "model": "FAJ Poisson Model",
            "version": self.VERSION,
            "max_goals": self.MAX_GOALS,
            "xg_range": [
                self.XG_MIN,
                self.XG_MAX
            ],
            "status": "READY"
        }

    # ============================================================
    # TEST
    # ============================================================

    def test(
        self,
        home_xg: float = 1.72,
        away_xg: float = 0.95
    ) -> Dict[str, Any]:
        """
        Стандартный самотест.
        """

        return self.calculate(
            home_xg=home_xg,
            away_xg=away_xg,
            include_matrix=True
        )


# ================================================================
# ALIAS
# ================================================================

PoissonModel = FAJPoissonModel


# ================================================================
# SINGLETON
# ================================================================

_poisson_model_instance: Optional[
    FAJPoissonModel
] = None


def get_poisson_model() -> FAJPoissonModel:
    """
    Получение singleton экземпляра.
    """

    global _poisson_model_instance

    if _poisson_model_instance is None:

        _poisson_model_instance = (
            FAJPoissonModel()
        )

    return _poisson_model_instance


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("FAJ POISSON MODEL v7.4")
    print("=" * 70)

    model = FAJPoissonModel()

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
    # TEST
    # ------------------------------------------------------------

    home_xg = 1.72
    away_xg = 0.95

    print()
    print(
        f"TEST xG: "
        f"{home_xg:.2f} : {away_xg:.2f}"
    )

    print("-" * 70)

    result = model.calculate(
        home_xg=home_xg,
        away_xg=away_xg,
        include_matrix=False
    )

    # ------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------

    probabilities = result[
        "result_probability"
    ]

    print()
    print("1X2")
    print(
        f"  Home: "
        f"{probabilities['home'] * 100:.2f}%"
    )
    print(
        f"  Draw: "
        f"{probabilities['draw'] * 100:.2f}%"
    )
    print(
        f"  Away: "
        f"{probabilities['away'] * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # DOUBLE CHANCE
    # ------------------------------------------------------------

    double_chance = result[
        "double_chance"
    ]

    print()
    print("DOUBLE CHANCE")

    print(
        f"  1X: "
        f"{double_chance['home_or_draw'] * 100:.2f}%"
    )

    print(
        f"  X2: "
        f"{double_chance['draw_or_away'] * 100:.2f}%"
    )

    print(
        f"  12: "
        f"{double_chance['home_or_away'] * 100:.2f}%"
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
    print("SCORE")

    print(
        f"  Most likely: "
        f"{result['most_likely_score']}"
    )

    print(
        f"  Probability: "
        f"{result['score_probability'] * 100:.2f}%"
    )

    print()
    print("TOP 5 SCORES")

    for item in result["top_scores"]:

        print(
            f"  {item['score']}: "
            f"{item['probability'] * 100:.2f}%"
        )

    # ------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------

    print()
    print("DIAGNOSTICS")

    print(
        f"  Expected total: "
        f"{result['expected_total']:.3f}"
    )

    print(
        f"  Tail probability: "
        f"{result['tail_probability'] * 100:.4f}%"
    )

    print(
        f"  Model stability: "
        f"{result['model_stability'] * 100:.4f}%"
    )

    print(
        f"  Score entropy: "
        f"{result['score_entropy']:.3f}"
    )

    print(
        f"  Matrix sum: "
        f"{result['matrix_sum']:.6f}"
    )

    # ------------------------------------------------------------
    # GOAL DISTRIBUTION
    # ------------------------------------------------------------

    print()
    print("GOAL DISTRIBUTION — HOME")

    for goals, probability in enumerate(
        result["goals_home"]
    ):

        print(
            f"  {goals}: "
            f"{probability * 100:.2f}%"
        )

    print()
    print("GOAL DISTRIBUTION — AWAY")

    for goals, probability in enumerate(
        result["goals_away"]
    ):

        print(
            f"  {goals}: "
            f"{probability * 100:.2f}%"
        )

    # ------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "Poisson Model v7.4 "
        "READY"
    )
    print("=" * 70)
