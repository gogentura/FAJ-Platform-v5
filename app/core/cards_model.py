#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM v12.1
CARDS MODEL v1.0
============================================================

Назначение
----------

CardsModel анализирует фактическую историю карточек команды.

Модель НЕ:

    - изменяет xG;
    - изменяет вероятность;
    - изменяет счёт;
    - создаёт vulnerability multiplier;
    - превращает карточки напрямую в aggression;
    - штрафует команду автоматически;
    - использует bookmaker odds;
    - изменяет FormContext.

Карточки являются наблюдаемым фактом.

Интерпретация:

    много карточек
    +
    плохой результат
    +
    другие признаки

может стать OBSERVED PATTERN CANDIDATE
на уровне Pattern/Analysis.

Но CardsModel v1.0 не создаёт
математического штрафа.

============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional
import math


CARDS_MODEL_VERSION = "1.0"

MAX_HISTORY_MATCHES = 6


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> Optional[float]:

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:

        text = str(value).strip()

        if not text:
            return None

        text = text.replace(",", ".")

        result = float(text)

        if not math.isfinite(result):
            return None

        return result

    except (TypeError, ValueError):

        return None


def _numeric_values(
    values: Iterable[Any],
) -> List[float]:

    result = []

    for value in values:

        number = _safe_float(value)

        if number is not None:
            result.append(number)

    return result


def _average(
    values: Iterable[Any],
) -> Optional[float]:

    numeric = _numeric_values(
        values
    )

    if not numeric:
        return None

    return sum(numeric) / len(numeric)


def _chronological_history(
    values: Iterable[Any],
) -> List[Optional[float]]:
    """
    FormContext:

        newest → oldest

    Model:

        oldest → newest
    """

    result = [
        _safe_float(value)
        for value in values
    ]

    return list(
        reversed(result)
    )


def _recent_mean(
    chronological_values: Iterable[Any],
) -> Optional[float]:

    values = [
        _safe_float(value)
        for value in chronological_values
    ]

    available = [
        value
        for value in values
        if value is not None
    ]

    if not available:
        return None

    return sum(available) / len(
        available
    )


def _ols_slope(
    values: Iterable[Any],
) -> Optional[float]:
    """
    OLS:

        x = 1..N

    None-наблюдения исключаются.
    """

    points = []

    for index, value in enumerate(
        values,
        start=1,
    ):

        number = _safe_float(
            value
        )

        if number is not None:

            points.append(
                (
                    float(index),
                    number,
                )
            )

    if len(points) < 2:
        return None

    n = float(
        len(points)
    )

    sum_x = sum(
        x
        for x, _ in points
    )

    sum_y = sum(
        y
        for _, y in points
    )

    sum_xy = sum(
        x * y
        for x, y in points
    )

    sum_x2 = sum(
        x * x
        for x, _ in points
    )

    denominator = (
        n * sum_x2
        - sum_x * sum_x
    )

    if denominator == 0:
        return None

    numerator = (
        n * sum_xy
        - sum_x * sum_y
    )

    return (
        numerator
        / denominator
    )


def _points_rate(
    results: Iterable[Any],
) -> Optional[float]:

    points = 0
    count = 0

    for result in results:

        if result is None:
            continue

        normalized = (
            str(result)
            .strip()
            .upper()
        )

        if normalized == "W":

            points += 3
            count += 1

        elif normalized == "D":

            points += 1
            count += 1

        elif normalized == "L":

            points += 0
            count += 1

    if count == 0:
        return None

    return points / (
        3.0 * count
    )


def _recent_points_rate(
    results_chronological: Iterable[Any],
) -> Optional[float]:
    """
    RecentPointsRate:

        Σ(i × points_i)
        ----------------
        3 × Σi

    i = 1..N

    N — самый свежий матч.
    """

    weighted_points = 0.0
    weight_sum = 0.0

    for index, result in enumerate(
        results_chronological,
        start=1,
    ):

        if result is None:
            continue

        normalized = (
            str(result)
            .strip()
            .upper()
        )

        if normalized == "W":
            points = 3.0

        elif normalized == "D":
            points = 1.0

        elif normalized == "L":
            points = 0.0

        else:
            continue

        weighted_points += (
            index * points
        )

        weight_sum += index

    if weight_sum == 0:
        return None

    return weighted_points / (
        3.0 * weight_sum
    )


# ============================================================
# RESULT
# ============================================================

@dataclass
class CardsModelResult:

    version: str
    team: Optional[str]

    matches_available: int

    team_cards_history: List[
        Optional[float]
    ]

    opponent_cards_history: List[
        Optional[float]
    ]

    team_cards_avg: Optional[float]
    opponent_cards_avg: Optional[float]

    team_cards_recent: Optional[float]
    opponent_cards_recent: Optional[float]

    team_cards_trend: Optional[float]
    opponent_cards_trend: Optional[float]

    points_rate: Optional[float]
    recent_points_rate: Optional[float]

    home_cards_expected: Optional[float]
    away_cards_expected: Optional[float]

    total_expected_cards: Optional[float]

    data_coverage: Optional[float]

    formula_status: str

    diagnostics: Dict[str, Any]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(self)


# ============================================================
# CARDS MODEL
# ============================================================

class CardsModel:
    """
    Чистая математическая модель карточек.

    Baseline:

        HomeBaseCards =
            (
                HomeTeamCardsAvg
                +
                AwayOpponentCardsAvg
            ) / 2

        AwayBaseCards =
            (
                AwayTeamCardsAvg
                +
                HomeOpponentCardsAvg
            ) / 2

    """

    VERSION = CARDS_MODEL_VERSION

    def __init__(
        self,
        max_history: int = MAX_HISTORY_MATCHES,
    ) -> None:

        self.max_history = max(
            1,
            int(max_history),
        )

    # ========================================================
    # EXTRACT
    # ========================================================

    def _extract_history(
        self,
        context: Dict[str, Any],
    ) -> tuple[
        List[Optional[float]],
        List[Optional[float]],
    ]:

        team_cards = context.get(
            "team_cards_history",
            [],
        )

        opponent_cards = context.get(
            "opponent_cards_history",
            [],
        )

        team_cards = list(
            team_cards or []
        )

        opponent_cards = list(
            opponent_cards or []
        )

        team_cards = team_cards[
            : self.max_history
        ]

        opponent_cards = opponent_cards[
            : self.max_history
        ]

        return (
            [
                _safe_float(value)
                for value in team_cards
            ],
            [
                _safe_float(value)
                for value in opponent_cards
            ],
        )

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze(
        self,
        context: Dict[str, Any],
    ) -> CardsModelResult:

        team = context.get(
            "team"
        )

        team_cards_raw, opponent_cards_raw = (
            self._extract_history(
                context
            )
        )

        # ----------------------------------------------------
        # Context history:
        #
        # newest → oldest
        #
        # Internal model:
        #
        # oldest → newest
        # ----------------------------------------------------

        team_cards_chronological = (
            _chronological_history(
                team_cards_raw
            )
        )

        opponent_cards_chronological = (
            _chronological_history(
                opponent_cards_raw
            )
        )

        results_raw = context.get(
            "results",
            [],
        )

        results_raw = list(
            results_raw or []
        )[
            : self.max_history
        ]

        results_chronological = list(
            reversed(
                results_raw
            )
        )

        # ----------------------------------------------------
        # Average
        # ----------------------------------------------------

        team_cards_avg = _average(
            team_cards_chronological
        )

        opponent_cards_avg = _average(
            opponent_cards_chronological
        )

        # ----------------------------------------------------
        # Recent
        # ----------------------------------------------------

        team_cards_recent = _recent_mean(
            team_cards_chronological
        )

        opponent_cards_recent = _recent_mean(
            opponent_cards_chronological
        )

        # ----------------------------------------------------
        # Trend
        # ----------------------------------------------------

        team_cards_trend = _ols_slope(
            team_cards_chronological
        )

        opponent_cards_trend = _ols_slope(
            opponent_cards_chronological
        )

        # ----------------------------------------------------
        # Result context
        # ----------------------------------------------------

        points_rate = _points_rate(
            results_chronological
        )

        recent_points_rate = (
            _recent_points_rate(
                results_chronological
            )
        )

        # ----------------------------------------------------
        # Coverage
        # ----------------------------------------------------

        history_length = max(
            len(team_cards_raw),
            len(opponent_cards_raw),
            len(results_raw),
        )

        available_team_cards = sum(
            1
            for value in team_cards_raw
            if value is not None
        )

        if history_length > 0:

            data_coverage = (
                available_team_cards
                / history_length
            )

        else:

            data_coverage = None

        diagnostics = {

            "history_order_input":
                "newest_to_oldest",

            "history_order_internal":
                "oldest_to_newest",

            "max_history":
                self.max_history,

            "team_cards_available":
                len(
                    _numeric_values(
                        team_cards_raw
                    )
                ),

            "opponent_cards_available":
                len(
                    _numeric_values(
                        opponent_cards_raw
                    )
                ),

            "formula":
                "(team_cards_avg + "
                "opponent_cards_avg) / 2",

            "result_context_used":
                True,

            "result_context_changes_cards":
                False,

            "vulnerability_signal":
                None,

            "aggression_signal":
                None,

        }

        return CardsModelResult(

            version=self.VERSION,

            team=team,

            matches_available=history_length,

            team_cards_history=
                team_cards_raw,

            opponent_cards_history=
                opponent_cards_raw,

            team_cards_avg=
                team_cards_avg,

            opponent_cards_avg=
                opponent_cards_avg,

            team_cards_recent=
                team_cards_recent,

            opponent_cards_recent=
                opponent_cards_recent,

            team_cards_trend=
                team_cards_trend,

            opponent_cards_trend=
                opponent_cards_trend,

            points_rate=
                points_rate,

            recent_points_rate=
                recent_points_rate,

            home_cards_expected=None,

            away_cards_expected=None,

            total_expected_cards=None,

            data_coverage=
                data_coverage,

            formula_status=
                "BASELINE_OBSERVATIONAL",

            diagnostics=
                diagnostics,
        )

    # ========================================================
    # MATCH SYNTHESIS
    # ========================================================

    def synthesize_match(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
    ) -> Dict[str, Any]:

        home = self.analyze(
            home_context
        )

        away = self.analyze(
            away_context
        )

        home_expected = None
        away_expected = None

        # ----------------------------------------------------
        # HOME
        #
        # Home team cards
        # +
        # Away opponent cards
        # ------------------
        # 2
        # ----------------------------------------------------

        if (
            home.team_cards_avg is not None
            and away.opponent_cards_avg is not None
        ):

            home_expected = (
                home.team_cards_avg
                + away.opponent_cards_avg
            ) / 2.0

        # ----------------------------------------------------
        # AWAY
        #
        # Away team cards
        # +
        # Home opponent cards
        # ------------------
        # 2
        # ----------------------------------------------------

        if (
            away.team_cards_avg is not None
            and home.opponent_cards_avg is not None
        ):

            away_expected = (
                away.team_cards_avg
                + home.opponent_cards_avg
            ) / 2.0

        total_expected = None

        if (
            home_expected is not None
            and away_expected is not None
        ):

            total_expected = (
                home_expected
                + away_expected
            )

        return {

            "version":
                self.VERSION,

            "home": {

                **home.to_dict(),

                "home_cards_expected":
                    home_expected,

                "formula_status":
                    (
                        "BASELINE_SYNTHESIS"
                        if home_expected is not None
                        else
                        "UNDEFINED_WITHOUT_BASELINE"
                    ),
            },

            "away": {

                **away.to_dict(),

                "away_cards_expected":
                    away_expected,

                "formula_status":
                    (
                        "BASELINE_SYNTHESIS"
                        if away_expected is not None
                        else
                        "UNDEFINED_WITHOUT_BASELINE"
                    ),
            },

            "home_cards_expected":
                home_expected,

            "away_cards_expected":
                away_expected,

            "total_expected_cards":
                total_expected,

            "formula_status":
                (
                    "BASELINE_SYNTHESIS"
                    if total_expected is not None
                    else
                    "UNDEFINED_WITHOUT_BASELINE"
                ),

            # ------------------------------------------------
            # HARD ARCHITECTURAL BOUNDARIES
            # ------------------------------------------------

            "affects_goal_model":
                False,

            "affects_probability_model":
                False,

            "affects_score_model":
                False,

            "creates_vulnerability_penalty":
                False,

            "creates_aggression_multiplier":
                False,

            "referee_adjustment":
                None,
        }


# ============================================================
# PUBLIC HELPERS
# ============================================================

def analyze_cards(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Анализ одной команды.
    """

    return CardsModel().analyze(
        context
    ).to_dict()


def synthesize_cards_match(
    home_context: Dict[str, Any],
    away_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Baseline synthesis карточек матча.
    """

    return CardsModel().synthesize_match(
        home_context,
        away_context,
    )
