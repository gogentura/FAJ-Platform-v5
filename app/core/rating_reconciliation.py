#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ PLATFORM v12.1
RATING RECONCILIATION v1.0

Объединяет:

    Club Rating
    Pair Rating

и формирует силовой сигнал для перераспределения
GoalModel scoring mass между Home и Away.

ВАЖНО:

Reconciliation НЕ увеличивает и НЕ уменьшает общий λ.

GoalModel сначала определяет:

    lambda_home
    lambda_away

Reconciliation меняет только их распределение:

    total_lambda = lambda_home + lambda_away

Club Rating:
    сезонная базовая сила клуба.

Pair Rating:
    ручная оценка конкретного матча.

Disagreement:
    pair_gap - club_gap

Это отдельный диагностический сигнал.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import tanh
from typing import Optional


RATING_RECONCILIATION_VERSION = "1.0"

# Вес Pair относительно Club при формировании
# reconciled rating gap.
DEFAULT_PAIR_WEIGHT = 0.50

# Вес Club.
DEFAULT_CLUB_WEIGHT = 0.50

# Нормализация rating gap.
RATING_SCALE = 15.0

# Максимальный сдвиг доли Home.
#
# Например:
# baseline Home share = 0.55
# rating signal = +1
# beta = 0.15
#
# final Home share = 0.70
#
# Общий lambda при этом НЕ изменяется.
LAMBDA_SHARE_ADJUSTMENT = 0.15

# Жёсткие границы распределения scoring mass.
MIN_HOME_SHARE = 0.20
MAX_HOME_SHARE = 0.80


@dataclass(frozen=True)
class RatingReconciliation:
    version: str

    home_team: str
    away_team: str

    club_home_rating: Optional[float]
    club_away_rating: Optional[float]
    club_gap: Optional[float]

    pair_home_rating: Optional[float]
    pair_away_rating: Optional[float]
    pair_gap: Optional[float]

    disagreement: Optional[float]
    high_disagreement: bool

    reconciled_gap: Optional[float]
    reconciled_signal: Optional[float]

    club_weight: float
    pair_weight: float

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "home_team": self.home_team,
            "away_team": self.away_team,

            "club_home_rating": self.club_home_rating,
            "club_away_rating": self.club_away_rating,
            "club_gap": self.club_gap,

            "pair_home_rating": self.pair_home_rating,
            "pair_away_rating": self.pair_away_rating,
            "pair_gap": self.pair_gap,

            "disagreement": self.disagreement,
            "high_disagreement": self.high_disagreement,

            "reconciled_gap": self.reconciled_gap,
            "reconciled_signal": self.reconciled_signal,

            "club_weight": self.club_weight,
            "pair_weight": self.pair_weight,
        }


@dataclass(frozen=True)
class LambdaReconciliation:
    version: str

    lambda_home_before: float
    lambda_away_before: float

    total_lambda: float

    baseline_home_share: float
    final_home_share: float

    lambda_home_after: float
    lambda_away_after: float

    share_shift: float

    reconciled_signal: Optional[float]

    def to_dict(self) -> dict:
        return {
            "version": self.version,

            "lambda_home_before": self.lambda_home_before,
            "lambda_away_before": self.lambda_away_before,

            "total_lambda": self.total_lambda,

            "baseline_home_share": self.baseline_home_share,
            "final_home_share": self.final_home_share,

            "lambda_home_after": self.lambda_home_after,
            "lambda_away_after": self.lambda_away_after,

            "share_shift": self.share_shift,

            "reconciled_signal": self.reconciled_signal,
        }


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, value))


def reconcile_ratings(
    home_team: str,
    away_team: str,
    club_home_rating: Optional[float] = None,
    club_away_rating: Optional[float] = None,
    pair_home_rating: Optional[float] = None,
    pair_away_rating: Optional[float] = None,
    club_weight: float = DEFAULT_CLUB_WEIGHT,
    pair_weight: float = DEFAULT_PAIR_WEIGHT,
) -> RatingReconciliation:

    club_gap = None

    if (
        club_home_rating is not None
        and club_away_rating is not None
    ):
        club_gap = (
            float(club_home_rating)
            - float(club_away_rating)
        )

    pair_gap = None

    if (
        pair_home_rating is not None
        and pair_away_rating is not None
    ):
        pair_gap = (
            float(pair_home_rating)
            - float(pair_away_rating)
        )

    have_club = club_gap is not None
    have_pair = pair_gap is not None

    reconciled_gap = None

    if have_club and have_pair:
        total_weight = (
            float(club_weight)
            + float(pair_weight)
        )

        if total_weight <= 0:
            total_weight = 1.0
            club_weight = DEFAULT_CLUB_WEIGHT
            pair_weight = DEFAULT_PAIR_WEIGHT

        reconciled_gap = (
            (
                float(club_weight) * club_gap
                + float(pair_weight) * pair_gap
            )
            / total_weight
        )

    elif have_club:
        reconciled_gap = club_gap

    elif have_pair:
        reconciled_gap = pair_gap

    reconciled_signal = None

    if reconciled_gap is not None:
        reconciled_signal = tanh(
            reconciled_gap / RATING_SCALE
        )

    disagreement = None
    high_disagreement = False

    if have_club and have_pair:
        disagreement = pair_gap - club_gap

        # Диагностический порог.
        high_disagreement = (
            abs(disagreement) >= 10.0
        )

    return RatingReconciliation(
        version=RATING_RECONCILIATION_VERSION,

        home_team=home_team,
        away_team=away_team,

        club_home_rating=club_home_rating,
        club_away_rating=club_away_rating,
        club_gap=club_gap,

        pair_home_rating=pair_home_rating,
        pair_away_rating=pair_away_rating,
        pair_gap=pair_gap,

        disagreement=disagreement,
        high_disagreement=high_disagreement,

        reconciled_gap=reconciled_gap,
        reconciled_signal=reconciled_signal,

        club_weight=float(club_weight),
        pair_weight=float(pair_weight),
    )


def reconcile_lambda(
    lambda_home: float,
    lambda_away: float,
    reconciled_signal: Optional[float],
    adjustment: float = LAMBDA_SHARE_ADJUSTMENT,
) -> LambdaReconciliation:
    """
    Перераспределяет scoring mass между Home и Away.

    НЕ изменяет:

        total_lambda

    Изменяется только:

        Home share
        Away share

    Формула:

        baseline_share =
            lambda_home / total_lambda

        final_share =
            clamp(
                baseline_share
                + adjustment * signal,
                0.20,
                0.80
            )

        lambda_home =
            total_lambda * final_share

        lambda_away =
            total_lambda * (1 - final_share)
    """

    lambda_home = float(lambda_home)
    lambda_away = float(lambda_away)

    if lambda_home < 0:
        raise ValueError(
            "lambda_home must be >= 0"
        )

    if lambda_away < 0:
        raise ValueError(
            "lambda_away must be >= 0"
        )

    total_lambda = lambda_home + lambda_away

    if total_lambda <= 0:
        return LambdaReconciliation(
            version=RATING_RECONCILIATION_VERSION,

            lambda_home_before=lambda_home,
            lambda_away_before=lambda_away,

            total_lambda=total_lambda,

            baseline_home_share=0.5,
            final_home_share=0.5,

            lambda_home_after=lambda_home,
            lambda_away_after=lambda_away,

            share_shift=0.0,

            reconciled_signal=reconciled_signal,
        )

    baseline_home_share = (
        lambda_home / total_lambda
    )

    if reconciled_signal is None:
        final_home_share = baseline_home_share
    else:
        signal = _clamp(
            float(reconciled_signal),
            -1.0,
            1.0,
        )

        final_home_share = _clamp(
            baseline_home_share
            + float(adjustment) * signal,
            MIN_HOME_SHARE,
            MAX_HOME_SHARE,
        )

    lambda_home_after = (
        total_lambda * final_home_share
    )

    lambda_away_after = (
        total_lambda * (1.0 - final_home_share)
    )

    share_shift = (
        final_home_share
        - baseline_home_share
    )

    return LambdaReconciliation(
        version=RATING_RECONCILIATION_VERSION,

        lambda_home_before=lambda_home,
        lambda_away_before=lambda_away,

        total_lambda=total_lambda,

        baseline_home_share=baseline_home_share,
        final_home_share=final_home_share,

        lambda_home_after=lambda_home_after,
        lambda_away_after=lambda_away_after,

        share_shift=share_shift,

        reconciled_signal=reconciled_signal,
    )


__all__ = [
    "RATING_RECONCILIATION_VERSION",
    "DEFAULT_CLUB_WEIGHT",
    "DEFAULT_PAIR_WEIGHT",
    "RATING_SCALE",
    "LAMBDA_SHARE_ADJUSTMENT",
    "MIN_HOME_SHARE",
    "MAX_HOME_SHARE",
    "RatingReconciliation",
    "LambdaReconciliation",
    "reconcile_ratings",
    "reconcile_lambda",
  ]
