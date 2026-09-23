#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
RATING RECONCILIATION v1.0
============================================================

НАЗНАЧЕНИЕ
----------

Объединяет FAJ Club Rating (объективный, посезонный) и
FAJ Pair Rating (ручной, per-match) в единый сигнал и
перераспределяет уже существующие λ (от GoalModel) между
Home/Away — БЕЗ изменения их суммы.

Контракт зафиксирован в faj_brain.py v4.2:

    ClubGap = ClubHome - ClubAway
    PairGap = PairHome - PairAway

    Оба источника доступны:
        R = 0.50 * ClubGap + 0.50 * PairGap
    Только Club:
        R = ClubGap
    Только Pair:
        R = PairGap
    Ничего нет:
        R = None (adjustment не применяется)

    S = tanh(R / 15.0)                         # [-1, +1]

    B  = λH0 / (λH0 + λA0)                      # исходная доля Home
    B' = clamp(B + 0.15 * S, 0.20, 0.80)        # скорректированная доля

    T  = λH0 + λA0
    λH = T * B'
    λA = T * (1 - B')

ГАРАНТИЯ: λH + λA == λH0 + λA0 всегда (проверяется самим
Brain через math.isclose после вызова reconcile_lambda —
при расхождении Brain поднимает BrainCoreError).

НЕ считает xG. НЕ владеет GoalModel. НЕ трогает
ProbabilityModel/ScorePredictor напрямую — только
перераспределяет то, что уже посчитал GoalModel.

None != 0. Отсутствие данных не подставляется нулём —
adjustment просто не применяется.
============================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from math import tanh
from typing import Optional


RATING_RECONCILIATION_VERSION = "1.0"

# Веса объединения Club/Pair. Явные, не калиброванные под
# контрольные матчи — 50/50 по умолчанию.
CLUB_WEIGHT_DEFAULT = 0.50
PAIR_WEIGHT_DEFAULT = 0.50

# Шкала нормализации R -> S через tanh. Согласована с той же
# шкалой, что использовалась для club-rating-only сигнала
# в GoalModel ранее.
RATING_SCALE = 15.0

# Насколько сильно сигнал S может сдвинуть долю λ у Home.
# 0.15 = максимум ±15 процентных пунктов доли при S = ±1.
SHARE_ADJUSTMENT_WEIGHT = 0.15

# Жёсткие границы итоговой доли — не даём одной команде
# забрать почти всю λ только из-за рейтинга.
SHARE_MIN = 0.20
SHARE_MAX = 0.80


# ============================================================
# RATING RECONCILIATION (Club + Pair -> signal)
# ============================================================

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

    reconciled_gap: Optional[float]      # R
    reconciled_signal: Optional[float]   # S = tanh(R / RATING_SCALE)

    club_weight: float
    pair_weight: float

    sources_used: str  # "club_and_pair" | "club_only" | "pair_only" | "none"

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
            "reconciled_gap": self.reconciled_gap,
            "reconciled_signal": self.reconciled_signal,
            "club_weight": self.club_weight,
            "pair_weight": self.pair_weight,
            "sources_used": self.sources_used,
        }


def reconcile_ratings(
    home_team: str,
    away_team: str,
    club_home_rating: Optional[float] = None,
    club_away_rating: Optional[float] = None,
    pair_home_rating: Optional[float] = None,
    pair_away_rating: Optional[float] = None,
    club_weight: float = CLUB_WEIGHT_DEFAULT,
    pair_weight: float = PAIR_WEIGHT_DEFAULT,
) -> RatingReconciliation:
    """
    Строит единый reconciled_gap/reconciled_signal из доступных
    источников. Любой источник может отсутствовать целиком —
    тогда используется только другой; если нет обоих — сигнал
    None, и λ дальше по цепочке останется без изменений
    (это решает уже reconcile_lambda, не эта функция).
    """

    club_gap: Optional[float] = None

    if club_home_rating is not None and club_away_rating is not None:
        club_gap = float(club_home_rating) - float(club_away_rating)

    pair_gap: Optional[float] = None

    if pair_home_rating is not None and pair_away_rating is not None:
        pair_gap = float(pair_home_rating) - float(pair_away_rating)

    reconciled_gap: Optional[float] = None
    sources_used = "none"

    if club_gap is not None and pair_gap is not None:

        total_weight = club_weight + pair_weight

        if total_weight <= 0:
            total_weight = 1.0
            club_weight, pair_weight = CLUB_WEIGHT_DEFAULT, PAIR_WEIGHT_DEFAULT

        reconciled_gap = (
            club_weight * club_gap + pair_weight * pair_gap
        ) / total_weight

        sources_used = "club_and_pair"

    elif club_gap is not None:
        reconciled_gap = club_gap
        sources_used = "club_only"

    elif pair_gap is not None:
        reconciled_gap = pair_gap
        sources_used = "pair_only"

    reconciled_signal: Optional[float] = None

    if reconciled_gap is not None:
        reconciled_signal = tanh(reconciled_gap / RATING_SCALE)

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
        reconciled_gap=reconciled_gap,
        reconciled_signal=reconciled_signal,
        club_weight=club_weight,
        pair_weight=pair_weight,
        sources_used=sources_used,
    )


# ============================================================
# LAMBDA RECONCILIATION (signal -> λ redistribution)
# ============================================================

@dataclass(frozen=True)
class LambdaReconciliation:

    lambda_home_before: float
    lambda_away_before: float
    total_lambda: float

    base_share_home: Optional[float]
    adjusted_share_home: Optional[float]

    signal_used: Optional[float]
    share_shift: Optional[float]
    weight_used: float

    lambda_home_after: float
    lambda_away_after: float

    def to_dict(self) -> dict:
        return {
            "lambda_home_before": self.lambda_home_before,
            "lambda_away_before": self.lambda_away_before,
            "total_lambda": self.total_lambda,
            "base_share_home": self.base_share_home,
            "adjusted_share_home": self.adjusted_share_home,
            "signal_used": self.signal_used,
            "share_shift": self.share_shift,
            "weight_used": self.weight_used,
            "lambda_home_after": self.lambda_home_after,
            "lambda_away_after": self.lambda_away_after,
        }


def reconcile_lambda(
    lambda_home: float,
    lambda_away: float,
    reconciled_signal: Optional[float],
    weight: float = SHARE_ADJUSTMENT_WEIGHT,
    share_min: float = SHARE_MIN,
    share_max: float = SHARE_MAX,
) -> LambdaReconciliation:
    """
    Перераспределяет λH0/λA0 в λH/λA по формуле:

        B  = λH0 / (λH0 + λA0)
        B' = clamp(B + weight * signal, share_min, share_max)
        T  = λH0 + λA0
        λH = T * B'
        λA = T * (1 - B')

    T всегда сохраняется в точности — Home и Away могут
    только "обменяться" долей внутри одной и той же общей
    массы λ, но не создать и не потерять голы в сумме.

    reconciled_signal is None (нет ни club, ни pair рейтинга)
    -> λ возвращаются без изменений (B' = B).

    total <= 0 (оба λ нулевые) -> нечего перераспределять,
    λ возвращаются без изменений.
    """

    total = lambda_home + lambda_away

    if total <= 0:

        return LambdaReconciliation(
            lambda_home_before=lambda_home,
            lambda_away_before=lambda_away,
            total_lambda=total,
            base_share_home=None,
            adjusted_share_home=None,
            signal_used=reconciled_signal,
            share_shift=None,
            weight_used=weight,
            lambda_home_after=lambda_home,
            lambda_away_after=lambda_away,
        )

    base_share = lambda_home / total

    if reconciled_signal is None:

        return LambdaReconciliation(
            lambda_home_before=lambda_home,
            lambda_away_before=lambda_away,
            total_lambda=total,
            base_share_home=base_share,
            adjusted_share_home=base_share,
            signal_used=None,
            share_shift=0.0,
            weight_used=weight,
            lambda_home_after=lambda_home,
            lambda_away_after=lambda_away,
        )

    adjusted_share = base_share + weight * reconciled_signal
    adjusted_share = max(share_min, min(share_max, adjusted_share))

    share_shift = adjusted_share - base_share

    lambda_home_after = total * adjusted_share
    lambda_away_after = total * (1.0 - adjusted_share)

    return LambdaReconciliation(
        lambda_home_before=lambda_home,
        lambda_away_before=lambda_away,
        total_lambda=total,
        base_share_home=base_share,
        adjusted_share_home=adjusted_share,
        signal_used=reconciled_signal,
        share_shift=share_shift,
        weight_used=weight,
        lambda_home_after=lambda_home_after,
        lambda_away_after=lambda_away_after,
    )


__all__ = [
    "RATING_RECONCILIATION_VERSION",
    "CLUB_WEIGHT_DEFAULT",
    "PAIR_WEIGHT_DEFAULT",
    "RATING_SCALE",
    "SHARE_ADJUSTMENT_WEIGHT",
    "SHARE_MIN",
    "SHARE_MAX",
    "RatingReconciliation",
    "reconcile_ratings",
    "LambdaReconciliation",
    "reconcile_lambda",
]
