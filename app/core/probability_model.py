#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
FAJ PROBABILITY MODEL v1.0
============================================================

Назначение
----------
ProbabilityModel преобразует home_lambda / away_lambda,
полученные от GoalModel, в вероятностное пространство
матча.

ARCHITECTURE

    FormContext
         ↓
    FormModel
         ↓
    GoalModel
         ↓
    home_lambda / away_lambda
         ↓
    ProbabilityModel
         ↓
    Probability State
         ↓
    ScorePredictor / AnalysisEngine


ProbabilityModel НЕ:

    - рассчитывает xG;
    - изменяет xG;
    - анализирует форму;
    - использует bookmaker odds;
    - обучается;
    - изменяет параметры;
    - выбирает победителя аналитически;
    - выбирает "лучший" exact score;
    - обращается к SQLite;
    - обращается к parser;
    - использует будущие результаты;
    - рассчитывает confidence;
    - рассчитывает risk;
    - применяет Winner Override.


============================================================
MATHEMATICAL CONTRACT v1
============================================================

GoalModel предоставляет:

    lambda_home
    lambda_away

ProbabilityModel:

    H ~ Poisson(lambda_home)
    A ~ Poisson(lambda_away)

    P(H=i) =
        exp(-lambda_home)
        * lambda_home^i / i!

    P(A=j) =
        exp(-lambda_away)
        * lambda_away^j / j!


Joint score probability:

    P(H=i, A=j) =
        P(H=i) * P(A=j)


No low-score correction in v1.

Dixon-Coles / low-score correction:
    RESERVED
    NOT ACTIVE
    NOT CALIBRATED


All football probabilities are derived
from the same normalized score matrix.


============================================================
OUTPUTS
============================================================

Probability State:

    home_win
    draw
    away_win

    btts

    over_15
    under_15

    over_25
    under_25

    over_35
    under_35

    score_distribution


ScorePredictor receives the matrix.

ProbabilityModel does NOT decide the exact score.


============================================================
DATA PRINCIPLE
============================================================

Missing lambda != 0.

If either lambda is unavailable:

    all probabilities = None
    score_distribution = {}

No fallback values.


============================================================
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# VERSION
# ============================================================

PROBABILITY_MODEL_VERSION = "1.0"
FORMULA_STATUS = "POISSON_BASELINE"


# ============================================================
# NUMERICAL PARAMETERS
# ============================================================

EPSILON = 1e-15

POISSON_TAIL_EPSILON = 1e-12

MIN_GOALS = 10

# Numerical safety boundary only.
# This is NOT a football prior.
MAX_LAMBDA = 20.0


# ============================================================
# TYPES
# ============================================================

Score = Tuple[int, int]

ScoreDistribution = Dict[
    Score,
    float,
]


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class ProbabilityResult:
    """
    Probability State v1.

    Все вероятности получены из одной
    normalized score matrix.
    """

    home_win: Optional[float]
    draw: Optional[float]
    away_win: Optional[float]

    btts: Optional[float]

    over_15: Optional[float]
    under_15: Optional[float]

    over_25: Optional[float]
    under_25: Optional[float]

    over_35: Optional[float]
    under_35: Optional[float]

    score_distribution: ScoreDistribution

    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# MODEL
# ============================================================

class ProbabilityModel:
    """
    FAJ ProbabilityModel v1.0.

    Pure probability layer.

    Input:
        home_lambda
        away_lambda

    Output:
        Probability State
    """

    VERSION = PROBABILITY_MODEL_VERSION
    FORMULA_STATUS = FORMULA_STATUS

    # ========================================================
    # PUBLIC API
    # ========================================================

    def calculate(
        self,
        home_lambda: Optional[float],
        away_lambda: Optional[float],
    ) -> ProbabilityResult:
        """
        Calculate Probability State.

        Parameters
        ----------
        home_lambda:
            Expected goals for home team.

        away_lambda:
            Expected goals for away team.

        Returns
        -------
        ProbabilityResult
        """

        home = self._validate_lambda(
            home_lambda
        )

        away = self._validate_lambda(
            away_lambda
        )

        # ----------------------------------------------------
        # Missing / invalid input
        # ----------------------------------------------------

        if home is None or away is None:

            reason: List[str] = []

            if home_lambda is None:
                reason.append(
                    "home_lambda_missing"
                )
            elif not self._is_valid_lambda(
                home_lambda
            ):
                reason.append(
                    "home_lambda_invalid"
                )

            if away_lambda is None:
                reason.append(
                    "away_lambda_missing"
                )
            elif not self._is_valid_lambda(
                away_lambda
            ):
                reason.append(
                    "away_lambda_invalid"
                )

            return self._unavailable_result(
                reason
            )

        # ----------------------------------------------------
        # Poisson marginals
        # ----------------------------------------------------

        home_distribution = (
            self._poisson_distribution(home)
        )

        away_distribution = (
            self._poisson_distribution(away)
        )

        if (
            not home_distribution
            or not away_distribution
        ):
            return self._unavailable_result(
                ["poisson_distribution_failed"]
            )

        # ----------------------------------------------------
        # Joint score matrix
        # ----------------------------------------------------

        raw_matrix = (
            self._build_joint_matrix(
                home_distribution,
                away_distribution,
            )
        )

        score_distribution = (
            self._normalize_matrix(
                raw_matrix
            )
        )

        if not score_distribution:
            return self._unavailable_result(
                ["score_matrix_failed"]
            )

        # ----------------------------------------------------
        # 1X2
        # ----------------------------------------------------

        (
            home_win,
            draw,
            away_win,
        ) = self._calculate_1x2(
            score_distribution
        )

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        btts = self._calculate_btts(
            score_distribution
        )

        # ----------------------------------------------------
        # Totals
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
        # Diagnostics
        # ----------------------------------------------------

        matrix_mass = sum(
            score_distribution.values()
        )

        diagnostics = {
            "version": self.VERSION,

            "formula_status":
                self.FORMULA_STATUS,

            "model":
                "independent_poisson",

            "home_lambda":
                home,

            "away_lambda":
                away,

            "total_lambda":
                home + away,

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
                (
                    home_win
                    + draw
                    + away_win
                ),

            "btts":
                btts,

            "ou_15_sum":
                over_15 + under_15,

            "ou_25_sum":
                over_25 + under_25,

            "ou_35_sum":
                over_35 + under_35,

            "low_score_correction":
                {
                    "enabled": False,
                    "status": "RESERVED",
                    "reason":
                        "reserved for future "
                        "calibrated research",
                },

            "uses_bookmaker_odds":
                False,

            "uses_future_results":
                False,

            "changes_lambda":
                False,

            "calibration_status":
                "NOT_CALIBRATED",
        }

        return ProbabilityResult(
            home_win=home_win,
            draw=draw,
            away_win=away_win,

            btts=btts,

            over_15=over_15,
            under_15=under_15,

            over_25=over_25,
            under_25=under_25,

            over_35=over_35,
            under_35=under_35,

            score_distribution=
                score_distribution,

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
        Reference Poisson formula:

            P(X=k) =
                exp(-lambda)
                * lambda^k / k!
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
            - math.lgamma(goals + 1)
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

        The temporal football model does not appear here.
        This is pure probability mathematics.
        """

        if lam < 0:
            return {}

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

            if (
                k >= MIN_GOALS
                and p < POISSON_TAIL_EPSILON
                and cumulative
                    > 1.0
                    - POISSON_TAIL_EPSILON
            ):
                break

        total = sum(
            probabilities.values()
        )

        if total <= EPSILON:
            return {}

        return {
            goals:
                probability / total
            for goals, probability
            in probabilities.items()
        }

    # ========================================================
    # JOINT MATRIX
    # ========================================================

    @staticmethod
    def _build_joint_matrix(
        home_distribution: Dict[
            int,
            float,
        ],
        away_distribution: Dict[
            int,
            float,
        ],
    ) -> ScoreDistribution:
        """
        Independent joint distribution:

            P(H=i,A=j)
                =
            P(H=i) * P(A=j)
        """

        matrix: ScoreDistribution = {}

        for (
            home_goals,
            home_probability,
        ) in home_distribution.items():

            for (
                away_goals,
                away_probability,
            ) in away_distribution.items():

                matrix[
                    (
                        home_goals,
                        away_goals,
                    )
                ] = (
                    home_probability
                    * away_probability
                )

        return matrix

    @staticmethod
    def _normalize_matrix(
        matrix: ScoreDistribution,
    ) -> ScoreDistribution:
        """
        Normalize matrix to probability mass 1.
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
            score:
                max(
                    0.0,
                    float(probability),
                ) / total
            for score, probability
            in matrix.items()
        }

    # ========================================================
    # 1X2
    # ========================================================

    @staticmethod
    def _calculate_1x2(
        matrix: ScoreDistribution,
    ) -> Tuple[
        float,
        float,
        float,
    ]:
        """
        1X2 from the same score matrix.
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
        matrix: ScoreDistribution,
    ) -> float:
        """
        BTTS Yes:

            P(H>0 and A>0)

        Derived from the same score matrix.
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
        matrix: ScoreDistribution,
    ) -> Tuple[
        float,
        float,
        float,
        float,
        float,
        float,
    ]:
        """
        O/U probabilities from the same
        score matrix.
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
            max(0.0, over_15),
        )

        over_25 = min(
            1.0,
            max(0.0, over_25),
        )

        over_35 = min(
            1.0,
            max(0.0, over_35),
        )

        return (
            over_15,
            1.0 - over_15,

            over_25,
            1.0 - over_25,

            over_35,
            1.0 - over_35,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _is_valid_lambda(
        value: Any,
    ) -> bool:
        """
        Validate lambda.

        None is missing.
        Negative / NaN / infinity are invalid.
        """

        if value is None:
            return False

        if isinstance(value, bool):
            return False

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return False

        if not math.isfinite(number):
            return False

        if number < 0:
            return False

        if number > MAX_LAMBDA:
            return False

        return True

    @classmethod
    def _validate_lambda(
        cls,
        value: Any,
    ) -> Optional[float]:

        if not cls._is_valid_lambda(value):
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
        Missing is never converted to zero.
        """

        return ProbabilityResult(
            home_win=None,
            draw=None,
            away_win=None,

            btts=None,

            over_15=None,
            under_15=None,

            over_25=None,
            under_25=None,

            over_35=None,
            under_35=None,

            score_distribution={},

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

                "changes_lambda":
                    False,

                "calibration_status":
                    "NOT_CALIBRATED",
            },
        )


# ============================================================
# CONVENIENCE API
# ============================================================

def calculate_probabilities(
    home_lambda: Optional[float],
    away_lambda: Optional[float],
) -> ProbabilityResult:
    """
    Convenience wrapper.
    """

    return ProbabilityModel().calculate(
        home_lambda=home_lambda,
        away_lambda=away_lambda,
    )


__all__ = [
    "ProbabilityModel",
    "ProbabilityResult",
    "calculate_probabilities",
    "PROBABILITY_MODEL_VERSION",
    "FORMULA_STATUS",
]
