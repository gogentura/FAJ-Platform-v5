#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Pair Rating
===============

Рейтинг конкретной пары перед матчем.

Pair Rating НЕ изменяет:
- xG
- GoalModel
- ProbabilityModel
- Poisson
- BTTS
- totals
- score distribution

Он только определяет направление пары:
HOME / AWAY / NEUTRAL

Диапазон: 60..100
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


MIN_RATING = 60
MAX_RATING = 100


@dataclass(frozen=True)
class PairRating:
    home_rating: int
    away_rating: int

    rating_gap: int

    winner_direction: str
    direction_team: Optional[str]

    direction_strength: str

    def to_dict(self) -> dict:
        return {
            "home_rating": self.home_rating,
            "away_rating": self.away_rating,
            "rating_gap": self.rating_gap,
            "winner_direction": self.winner_direction,
            "direction_team": self.direction_team,
            "direction_strength": self.direction_strength,
        }


def _validate_rating(value: int) -> int:
    value = int(value)

    if value < MIN_RATING:
        raise ValueError(
            f"Pair Rating must be >= {MIN_RATING}"
        )

    if value > MAX_RATING:
        raise ValueError(
            f"Pair Rating must be <= {MAX_RATING}"
        )

    return value


def calculate_pair_rating(
    home_rating: int,
    away_rating: int,
    home_team: str,
    away_team: str,
) -> PairRating:

    home_rating = _validate_rating(home_rating)
    away_rating = _validate_rating(away_rating)

    gap = home_rating - away_rating

    if gap > 0:
        direction = "HOME"
        direction_team = home_team
    elif gap < 0:
        direction = "AWAY"
        direction_team = away_team
    else:
        direction = "NEUTRAL"
        direction_team = None

    absolute_gap = abs(gap)

    if absolute_gap == 0:
        strength = "NEUTRAL"
    elif absolute_gap <= 3:
        strength = "SLIGHT"
    elif absolute_gap <= 7:
        strength = "MODERATE"
    elif absolute_gap <= 12:
        strength = "STRONG"
    else:
        strength = "VERY_STRONG"

    return PairRating(
        home_rating=home_rating,
        away_rating=away_rating,
        rating_gap=gap,
        winner_direction=direction,
        direction_team=direction_team,
        direction_strength=strength,
    )
