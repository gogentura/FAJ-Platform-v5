#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ PROBABILITY MODEL v1.1
============================================================

Назначение
----------
ProbabilityModel преобразует home_xG / away_xG,
полученные от GoalModel, в единое вероятностное
распределение футбольного матча.

Архитектура:

    FormContext
         ↓
    FormModel
         ↓
    FormWin / Defence
         ↓
    GoalModel
         ↓
    home_xG / away_xG
         ↓
    FAJ ProbabilityModel
         ↓
    ┌─────────────────────┐
    │ FAJ SCORE MATRIX    │
    └──────────┬──────────┘
               ↓
       ┌───────┼────────┐
       ↓       ↓        ↓
      1X2     BTTS     O/U
               ↓
        ScorePredictor

ProbabilityModel НЕ:
    - рассчитывает xG;
    - изменяет xG;
    - анализирует форму;
    - использует bookmaker odds;
    - обучается;
    - меняет параметры;
    - выбирает человеческий exact score;
    - обращается к SQLite;
    - обращается к parser;
    - использует будущие результаты.

Главный принцип:

    GoalModel = EXPECTED GOALS

    ProbabilityModel = PROBABILITY DISTRIBUTION

    ScorePredictor = EXACT SCORE DECISION

============================================================
MATHEMATICAL MODEL
============================================================

Base:

    H ~ Poisson(lambda_home)

    A ~ Poisson(lambda_away)

    P(H=i) =
        lambda_home^i * exp(-lambda_home) / i!

    P(A=j) =
        lambda_away^j * exp(-lambda_away) / j!

FAJ low-score correction (v1.1: ОТКЛЮЧЕНА):

    rho = 0.0

    tau(i,j) = 1 for all scores

Raw joint probability:

    P(i,j) =
        P(H=i) * P(A=j) * tau(i,j)

The complete matrix is normalized:

    P'(i,j) =
        P(i,j) / sum(P(i,j))

All outputs are derived from THIS SAME matrix.

============================================================
FORMULA STATUS
============================================================

POISSON_BASELINE

Dixon-Coles prior отключён до калибровки.
ProbabilityModel использует чистую независимую Poisson-модель
без искусственного усиления 0:0 / 1:0 / 0:1 / 1:1.

============================================================
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# VERSION
# ============================================================

PROBABILITY_MODEL_VERSION = "1.1"
FORMULA_STATUS = "POISSON_BASELINE"


# ============================================================
# RESEARCH PARAMETERS
# ============================================================

# Dixon-Coles prior отключён до калибровки.
# ProbabilityModel не должен искусственно усиливать 0:0.
LOW_SCORE_RHO = 0.0


# ------------------------------------------------------------
# Numerical parameters
# ------------------------------------------------------------

EPSILON = 1e-15

# Tail probability target.
#
# Расчёт продолжается до тех пор, пока хвост Poisson
# практически не влияет на результат.
POISSON_TAIL_EPSILON = 1e-12

# Минимальный диапазон голов.
MIN_GOALS = 10

# Максимальная защита от патологически большого xG.
#
# Это не футбольный prior.
# Это numerical safety boundary.
MAX_XG = 20.0

# Количество top exact scores.
TOP_SCORES_COUNT = 10


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class ProbabilityResult:
    """
    Полный результат FAJ ProbabilityModel.
    """

    home_win: Optional[float]
    draw: Optional[float]
    away_win: Optional[float]

    btts: Optional[float]

    over_15: Optional[float]
    over_25: Optional[float]
    over_35: Optional[float]

    under_15: Optional[float]
    under_25: Optional[float]
    under_35: Optional[float]

    score_distribution: Dict[
        Tuple[int, int],
        float,
    ]

    top_scores: List[
        Dict[str, Any]
    ]

    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializable representation.
        """
        return asdict(self)


# ============================================================
# PROBABILITY MODEL
# ============================================================

class ProbabilityModel:
    """
    FAJ ProbabilityModel v1.1.

    Converts GoalModel xG into a complete football
    probability distribution.

    Stateless model.
    """

    VERSION = PROBABILITY_MODEL_VERSION
    FORMULA_STATUS = FORMULA_STATUS

    # ========================================================
    # PUBLIC API
    # ========================================================

    def calculate(
        self,
        home_xg: Optional[float],
        away_xg: Optional[float],
    ) -> ProbabilityResult:
        """
        Calculate complete FAJ probability distribution.

        Parameters
        ----------
        home_xg:
            Expected goals for home team.

        away_xg:
            Expected goals for away team.

        Returns
        -------
        ProbabilityResult
        """

        # ----------------------------------------------------
        # 1. Validate inputs
        # ----------------------------------------------------

        home = self._validate_xg(
            home_xg
        )

        away = self._validate_xg(
            away_xg
        )

        if home is None or away is None:

            reason = []

            if home_xg is None:
                reason.append(
                    "home_xg_missing"
                )

            elif not self._is_valid_xg(
                home_xg
            ):
                reason.append(
                    "home_xg_invalid"
                )

            if away_xg is None:
                reason.append(
                    "away_xg_missing"
                )

            elif not self._is_valid_xg(
                away_xg
            ):
                reason.append(
                    "away_xg_invalid"
                )

            return self._unavailable_result(
                reason=reason
            )

        # ----------------------------------------------------
        # 2. Build Poisson marginal distributions
        # ----------------------------------------------------

        home_distribution = (
            self._poisson_distribution(
                home
            )
        )

        away_distribution = (
            self._poisson_distribution(
                away
            )
        )

        # ----------------------------------------------------
        # 3. Build raw FAJ joint matrix
        # ----------------------------------------------------

        raw_matrix = (
            self._build_joint_matrix(
                home_distribution,
                away_distribution,
                home,
                away,
            )
        )

        # ----------------------------------------------------
        # 4. Normalize matrix
        # ----------------------------------------------------

        score_distribution = (
            self._normalize_matrix(
                raw_matrix
            )
        )

        # ----------------------------------------------------
        # 5. 1X2
        # ----------------------------------------------------

        home_win, draw, away_win = (
            self._calculate_1x2(
                score_distribution
            )
        )

        # ----------------------------------------------------
        # 6. BTTS
        # ----------------------------------------------------

        btts = self._calculate_btts(
            score_distribution
        )

        # ----------------------------------------------------
        # 7. Totals
        # ----------------------------------------------------

        (
            over_15,
            under_15,
            over_25,
            under_25,
            over_35,
            under_35,
        ) = self._calculate_totals(
            score_distribution
        )

        # ----------------------------------------------------
        # 8. Top exact scores
        # ----------------------------------------------------

        top_scores = (
            self._top_scores(
                score_distribution
            )
        )

        # ----------------------------------------------------
        # 9. Diagnostics
        # ----------------------------------------------------

        matrix_mass = sum(
            score_distribution.values()
        )

        diagnostics = {
            "version": self.VERSION,
            "formula_status": self.FORMULA_STATUS,

            "model": (
                "independent Poisson + "
                "normalized score matrix"
            ),

            "home_xg": home,
            "away_xg": away,

            "rho": LOW_SCORE_RHO,

            "home_distribution_size":
                len(home_distribution),

            "away_distribution_size":
                len(away_distribution),

            "score_matrix_size":
                len(score_distribution),

            "matrix_probability_mass":
                matrix_mass,

            "probability_mass_error":
                abs(
                    1.0 - matrix_mass
                ),

            "one_x_two_sum":
                home_win
                + draw
                + away_win,

            "ou_15_sum":
                over_15
                + under_15,

            "ou_25_sum":
                over_25
                + under_25,

            "ou_35_sum":
                over_35
                + under_35,

            "low_score_correction":
                {
                    "rho": LOW_SCORE_RHO,
                    "enabled": False,
                    "reason": (
                        "uncalibrated research prior "
                        "disabled in v1.1"
                    ),
                    "cells": [
                        "0:0",
                        "0:1",
                        "1:0",
                        "1:1",
                    ],
                },

            "uses_bookmaker_odds":
                False,

            "uses_future_results":
                False,

            "changes_xg":
                False,

            "calibration_status":
                "NOT_CALIBRATED",

            "research_parameters":
                [
                    "LOW_SCORE_RHO",
                    "POISSON_TAIL_EPSILON",
                ],
        }

        return ProbabilityResult(
            home_win=home_win,
            draw=draw,
            away_win=away_win,

            btts=btts,

            over_15=over_15,
            over_25=over_25,
            over_35=over_35,

            under_15=under_15,
            under_25=under_25,
            under_35=under_35,

            score_distribution=
                score_distribution,

            top_scores=top_scores,

            diagnostics=diagnostics,
        )

    # ========================================================
    # POISSON
    # ========================================================

    @staticmethod
    def _poisson_probability(
        lam: float,
        goals: int,
    ) -> float:
        """
        P(X=k) =
            lambda^k * exp(-lambda) / k!

        Рекурсивный способ используется в
        _poisson_distribution(), поэтому этот
        метод остаётся как прозрачная reference formula.
        """

        if goals < 0:
            return 0.0

        if lam < 0:
            return 0.0

        if lam == 0.0:

            return (
                1.0
                if goals == 0
                else 0.0
            )

        log_probability = (
            goals * math.log(lam)
            - lam
            - math.lgamma(
                goals + 1
            )
        )

        return math.exp(
            log_probability
        )

    @classmethod
    def _poisson_distribution(
        cls,
        lam: float,
    ) -> Dict[int, float]:
        """
        Build adaptive Poisson distribution.

        Не используем жёсткий cutoff 10 для математики.

        Последовательность:

            P(0) = exp(-lambda)

            P(k) =
                P(k-1) * lambda / k

        Останавливаемся, когда:
            - достигнут минимум 10;
            - хвост достаточно мал;
            - probability уже прошла максимум
              и продолжает убывать.
        """

        if lam < 0:
            return {}

        # λ = 0
        if lam == 0.0:
            return {
                0: 1.0
            }

        probabilities: Dict[
            int,
            float,
        ] = {}

        p = math.exp(
            -lam
        )

        probabilities[0] = p

        cumulative = p

        k = 0

        # Safety boundary.
        max_iterations = max(
            MIN_GOALS + 20,
            int(
                lam
                + 20.0
                * math.sqrt(
                    max(lam, 1.0)
                )
                + 20
            ),
        )

        while k < max_iterations:

            k += 1

            p = (
                p
                * lam
                / k
            )

            probabilities[k] = p

            cumulative += p

            # После моды Poisson probability
            # начинает убывать.
            #
            # При достижении минимального диапазона
            # проверяем остаточный хвост.
            if (
                k >= MIN_GOALS
                and p < POISSON_TAIL_EPSILON
                and cumulative > 1.0
                    - POISSON_TAIL_EPSILON
            ):
                break

        # Нормализация marginal distribution.
        #
        # Это убирает микроскопическую numerical
        # ошибку и гарантирует сумму 1.
        total = sum(
            probabilities.values()
        )

        if total <= 0:
            return {}

        return {
            goals: probability / total
            for goals, probability
            in probabilities.items()
        }

    # ========================================================
    # JOINT MATRIX
    # ========================================================

    @staticmethod
    def _low_score_tau(
        home_goals: int,
        away_goals: int,
        home_xg: float,
        away_xg: float,
    ) -> float:
        """
        Compatibility hook for the former Dixon-Coles layer.

        v1.1:
        low-score correction отключён.

        ProbabilityModel использует чистую независимую
        Poisson-модель без искусственного усиления
        0:0 / 1:0 / 0:1 / 1:1.
        """
        return 1.0

    @classmethod
    def _build_joint_matrix(
        cls,
        home_distribution: Dict[
            int,
            float,
        ],
        away_distribution: Dict[
            int,
            float,
        ],
        home_xg: float,
        away_xg: float,
    ) -> Dict[
        Tuple[int, int],
        float,
    ]:
        """
        Build raw corrected joint distribution.
        """

        matrix: Dict[
            Tuple[int, int],
            float,
        ] = {}

        for home_goals, p_home in (
            home_distribution.items()
        ):

            for away_goals, p_away in (
                away_distribution.items()
            ):

                independent_probability = (
                    p_home
                    * p_away
                )

                tau = (
                    cls._low_score_tau(
                        home_goals,
                        away_goals,
                        home_xg,
                        away_xg,
                    )
                )

                probability = (
                    independent_probability
                    * tau
                )

                if probability < 0:
                    probability = 0.0

                matrix[
                    (
                        home_goals,
                        away_goals,
                    )
                ] = probability

        return matrix

    @staticmethod
    def _normalize_matrix(
        matrix: Dict[
            Tuple[int, int],
            float,
        ],
    ) -> Dict[
        Tuple[int, int],
        float,
    ]:
        """
        Normalize complete score matrix to exactly 1.
        """

        total = sum(
            max(
                0.0,
                float(probability),
            )
            for probability
            in matrix.values()
        )

        if total <= EPSILON:
            return {}

        return {
            score: (
                max(
                    0.0,
                    float(probability),
                )
                / total
            )
            for score, probability
            in matrix.items()
        }

    # ========================================================
    # 1X2
    # ========================================================

    @staticmethod
    def _calculate_1x2(
        matrix: Dict[
            Tuple[int, int],
            float,
        ],
    ) -> Tuple[
        float,
        float,
        float,
    ]:
        """
        Calculate 1X2 directly from the SAME
        corrected score matrix.
        """

        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for (
            home_goals,
            away_goals,
        ), probability in matrix.items():

            if home_goals > away_goals:

                home_win += probability

            elif home_goals == away_goals:

                draw += probability

            else:

                away_win += probability

        total = (
            home_win
            + draw
            + away_win
        )

        if total <= EPSILON:

            return (
                0.0,
                0.0,
                0.0,
            )

        return (
            home_win / total,
            draw / total,
            away_win / total,
        )

    # ========================================================
    # BTTS
    # ========================================================

    @staticmethod
    def _calculate_btts(
        matrix: Dict[
            Tuple[int, int],
            float,
        ],
    ) -> float:
        """
        BTTS is derived from the complete FAJ matrix.

        This keeps BTTS mathematically consistent
        with 1X2 and exact-score probabilities.
        """

        probability = 0.0

        for (
            home_goals,
            away_goals,
        ), value in matrix.items():

            if (
                home_goals > 0
                and away_goals > 0
            ):
                probability += value

        return min(
            1.0,
            max(
                0.0,
                probability,
            ),
        )

    # ========================================================
    # TOTALS
    # ========================================================

    @staticmethod
    def _calculate_totals(
        matrix: Dict[
            Tuple[int, int],
            float,
        ],
    ) -> Tuple[
        float,
        float,
        float,
        float,
        float,
        float,
    ]:
        """
        Calculate all O/U probabilities from
        the SAME FAJ score matrix.
        """

        over_15 = 0.0
        over_25 = 0.0
        over_35 = 0.0

        for (
            home_goals,
            away_goals,
        ), probability in matrix.items():

            total_goals = (
                home_goals
                + away_goals
            )

            if total_goals >= 2:
                over_15 += probability

            if total_goals >= 3:
                over_25 += probability

            if total_goals >= 4:
                over_35 += probability

        over_15 = min(
            1.0,
            max(
                0.0,
                over_15,
            ),
        )

        over_25 = min(
            1.0,
            max(
                0.0,
                over_25,
            ),
        )

        over_35 = min(
            1.0,
            max(
                0.0,
                over_35,
            ),
        )

        under_15 = (
            1.0 - over_15
        )

        under_25 = (
            1.0 - over_25
        )

        under_35 = (
            1.0 - over_35
        )

        return (
            over_15,
            under_15,
            over_25,
            under_25,
            over_35,
            under_35,
        )

    # ========================================================
    # TOP SCORES
    # ========================================================

    @staticmethod
    def _top_scores(
        matrix: Dict[
            Tuple[int, int],
            float,
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Return top exact-score scenarios.

        These probabilities are raw probabilities,
        NOT confidence scores.
        """

        ordered = sorted(
            matrix.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        result: List[
            Dict[str, Any]
        ] = []

        for rank, (
            (home_goals, away_goals),
            probability,
        ) in enumerate(
            ordered[
                :TOP_SCORES_COUNT
            ],
            start=1,
        ):

            result.append(
                {
                    "rank": rank,

                    "home_goals":
                        home_goals,

                    "away_goals":
                        away_goals,

                    "score":
                        f"{home_goals}:"
                        f"{away_goals}",

                    "probability":
                        probability,
                }
            )

        return result

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _is_valid_xg(
        value: Any,
    ) -> bool:
        """
        Validate xG.

        None is missing.
        Negative xG is invalid.
        Infinite / NaN is invalid.
        """

        if value is None:
            return False

        if isinstance(
            value,
            bool,
        ):
            return False

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return False

        if not math.isfinite(
            number
        ):
            return False

        if number < 0:
            return False

        if number > MAX_XG:
            return False

        return True

    @classmethod
    def _validate_xg(
        cls,
        value: Any,
    ) -> Optional[float]:
        """
        Convert valid xG to float.

        Invalid values remain None.
        """

        if not cls._is_valid_xg(
            value
        ):
            return None

        return float(value)

    # ========================================================
    # UNAVAILABLE
    # ========================================================

    def _unavailable_result(
        self,
        reason: List[str],
    ) -> ProbabilityResult:
        """
        Transparent unavailable result.

        Missing is never converted to zero.
        """

        return ProbabilityResult(
            home_win=None,
            draw=None,
            away_win=None,

            btts=None,

            over_15=None,
            over_25=None,
            over_35=None,

            under_15=None,
            under_25=None,
            under_35=None,

            score_distribution={},

            top_scores=[],

            diagnostics={
                "version":
                    self.VERSION,

                "formula_status":
                    self.FORMULA_STATUS,

                "available":
                    False,

                "reason":
                    reason,

                "uses_bookmaker_odds":
                    False,

                "changes_xg":
                    False,

                "calibration_status":
                    "NOT_CALIBRATED",
            },
        )


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def calculate_probabilities(
    home_xg: Optional[float],
    away_xg: Optional[float],
) -> ProbabilityResult:
    """
    Convenience wrapper.

    Example:

        result = calculate_probabilities(
            home_xg=1.85,
            away_xg=0.72,
        )
    """

    model = ProbabilityModel()

    return model.calculate(
        home_xg=home_xg,
        away_xg=away_xg,
    )


__all__ = [
    "ProbabilityModel",
    "ProbabilityResult",
    "calculate_probabilities",
    "PROBABILITY_MODEL_VERSION",
    "FORMULA_STATUS",
]
