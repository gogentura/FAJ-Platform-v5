#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Personal Prediction Brain
=============================

Новый независимый прогнозный мозг FAJ.

Архитектура:

    historical data
          ↓
    normalize input
          ↓
    FormContext
          ↓
    FormModel
          ↓
    FormModelResult
          ↓
    FormWin
          ↓
    Defence
          ↓
    GoalModel
          ↓
    home_xg / away_xg
          ↓
    score distribution
          ↓
    result probabilities
          ↓
    BTTS / totals
          ↓
    corners
          ↓
    cards
          ↓
    confidence / risk
          ↓
    analytical conclusion

ВАЖНО:
    Этот модуль НЕ:
        - работает с SQLite напрямую;
        - получает данные из Soccer365;
        - занимается UI;
        - занимается API;
        - обучается автоматически;
        - изменяет параметры базы;
        - использует букмекерские коэффициенты;
        - зависит от старого FAJ Core.

Принцип:
    отсутствующие данные остаются None.
    None НЕ превращается в 0.

Версия:
    FAJ-BRAIN-0.8
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional


# ============================================================
# IMPORTS
# ============================================================

from app.core.form_context import build_form_context
from app.core.brain_contract import (
    FormContext as BrainFormContext,
    MatchRecord,
)
from app.core.form_model import FormModel
from app.core.form_win import FormWin
from app.core.defence import Defence
from app.core.form_control import FormControl
from app.core.form_anomaly import FormAnomaly
from app.core.special_form import FormSpecial
from app.core.goal_model import GoalModel
from app.core.probability_model import ProbabilityModel
from app.core.score_predictor import ScorePredictor
from app.core.corners_model import CornersModel
from app.core.cards_model import CardsModel


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-0.8"

MIN_MATCHES = 1
EXTENDED_ANALYSIS_MATCHES = 3
PREFERRED_MATCHES = 6
MAX_RECOMMENDED_MATCHES = 10


# ============================================================
# HELPERS
# ============================================================

def _float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование значения в float.

    None и пустые значения остаются None.
    Отсутствие данных никогда не превращается в 0.
    """

    if value is None:
        return default

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):

        if math.isfinite(float(value)):
            return float(value)

        return default

    if isinstance(value, str):

        value = value.strip().replace(",", ".")

        if not value:
            return default

        try:

            result = float(value)

            if math.isfinite(result):
                return result

        except (TypeError, ValueError):
            pass

    return default


def _int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:

    result = _float(value)

    if result is None:
        return default

    return int(round(result))


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:

    return max(
        low,
        min(high, value),
    )


def _mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    return sum(clean) / len(clean)


def _weighted_mean(
    values: Iterable[Optional[float]],
) -> Optional[float]:

    clean = [
        float(value)
        for value in values
        if value is not None
    ]

    if not clean:
        return None

    # Последние матчи имеют больший вес.
    #
    # M1 = 1
    # M2 = 2
    # ...
    # M6 = 6

    weights = list(
        range(
            1,
            len(clean) + 1,
        )
    )

    return sum(
        value * weight
        for value, weight in zip(
            clean,
            weights,
        )
    ) / sum(weights)


def _probability(
    value: float,
) -> float:

    return round(
        _clamp(value) * 100.0,
        1,
    )


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class HistoricalMatch:

    team: str
    opponent: Optional[str] = None

    is_home: Optional[bool] = None

    goals_for: Optional[float] = None
    goals_against: Optional[float] = None

    shots: Optional[float] = None
    shots_on_target: Optional[float] = None

    possession: Optional[float] = None

    corners: Optional[float] = None

    yellow_cards: Optional[float] = None
    red_cards: Optional[float] = None

    xg: Optional[float] = None

    big_chances: Optional[float] = None

    competition: Optional[str] = None
    match_date: Optional[str] = None

    extra: Dict[str, Any] = field(
        default_factory=dict
    )

    # ========================================================
    # FROM DICT
    # ========================================================

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        team: Optional[str] = None,
    ) -> "HistoricalMatch":

        # ====================================================
        # BASIC IDENTITY
        # ====================================================

        home_team = data.get("home_team")
        away_team = data.get("away_team")

        current_team = (
            team
            or data.get("team")
            or data.get("team_name")
            or ""
        )

        # ====================================================
        # DETERMINE SIDE
        # ====================================================

        if data.get("is_home") is True:

            is_home = True

        elif data.get("is_home") is False:

            is_home = False

        elif home_team and current_team == home_team:

            is_home = True

        elif away_team and current_team == away_team:

            is_home = False

        else:

            is_home = data.get("is_home")

        # ====================================================
        # OPPONENT
        # ====================================================

        opponent = (
            data.get("opponent")
            or data.get("opponent_name")
        )

        if opponent is None:

            if is_home is True:
                opponent = away_team

            elif is_home is False:
                opponent = home_team

        # ====================================================
        # COPY EXTRA
        # ====================================================

        source_extra = data.get("extra")

        if isinstance(source_extra, dict):

            extra = dict(source_extra)

        else:

            extra = {}

        # ====================================================
        # HELPER:
        # EXTRACT TEAM / OPPONENT VALUES
        # ====================================================

        def extract_pair(
            direct_key: str,
            nested_key: Optional[str] = None,
        ) -> tuple[
            Optional[float],
            Optional[float],
        ]:

            key = nested_key or direct_key

            raw = data.get(key)

            # ----------------------------------------------
            # Nested structure:
            #
            # {
            #     "home": 12,
            #     "away": 8
            # }
            # ----------------------------------------------

            if isinstance(raw, dict):

                home_value = _float(
                    raw.get("home")
                )

                away_value = _float(
                    raw.get("away")
                )

                if is_home is True:

                    return (
                        home_value,
                        away_value,
                    )

                if is_home is False:

                    return (
                        away_value,
                        home_value,
                    )

                return (
                    None,
                    None,
                )

            # ----------------------------------------------
            # Direct team value
            # ----------------------------------------------

            own_value = _float(raw)

            opponent_value = None

            # ----------------------------------------------
            # Explicit opponent value
            # ----------------------------------------------

            opponent_keys = [
                f"opponent_{direct_key}",
                f"opponent_{key}",
            ]

            for opponent_key in opponent_keys:

                if opponent_key in data:

                    opponent_value = _float(
                        data.get(opponent_key)
                    )

                    if opponent_value is not None:
                        break

            return (
                own_value,
                opponent_value,
            )

        # ====================================================
        # XG
        # ====================================================

        raw_xg = data.get("xg")

        own_xg = None
        opponent_xg = None

        if isinstance(raw_xg, dict):

            home_xg = _float(
                raw_xg.get("home")
            )

            away_xg = _float(
                raw_xg.get("away")
            )

            if is_home is True:

                own_xg = home_xg
                opponent_xg = away_xg

            elif is_home is False:

                own_xg = away_xg
                opponent_xg = home_xg

        else:

            own_xg = _float(raw_xg)

            opponent_xg = _float(
                data.get("opponent_xg")
            )

            if opponent_xg is None:

                opponent_xg = _float(
                    extra.get("opponent_xg")
                )

        # ====================================================
        # SHOTS
        # ====================================================

        (
            shots_value,
            opponent_shots_value,
        ) = extract_pair(
            "shots"
        )

        # ====================================================
        # SHOTS ON TARGET
        # ====================================================

        (
            sot_value,
            opponent_sot_value,
        ) = extract_pair(
            "shots_on_target"
        )

        # ====================================================
        # BLOCKED SHOTS
        # ====================================================

        (
            blocked_shots_value,
            opponent_blocked_shots_value,
        ) = extract_pair(
            "blocked_shots"
        )

        # ====================================================
        # BIG CHANCES
        # ====================================================

        (
            big_chances_value,
            opponent_big_chances_value,
        ) = extract_pair(
            "big_chances"
        )

        # ====================================================
        # POSSESSION
        # ====================================================

        (
            possession_value,
            opponent_possession_value,
        ) = extract_pair(
            "possession"
        )

        # ====================================================
        # PASSES
        # ====================================================

        (
            passes_value,
            opponent_passes_value,
        ) = extract_pair(
            "passes"
        )

        # ====================================================
        # PASS ACCURACY
        # ====================================================

        (
            pass_accuracy_value,
            opponent_pass_accuracy_value,
        ) = extract_pair(
            "pass_accuracy"
        )

        # ====================================================
        # CORNERS
        # ====================================================

        (
            corners_value,
            opponent_corners_value,
        ) = extract_pair(
            "corners"
        )

        # ====================================================
        # YELLOW CARDS
        # ====================================================

        (
            yellow_cards_value,
            opponent_yellow_cards_value,
        ) = extract_pair(
            "yellow_cards"
        )

        # Также поддерживаем старую структуру cards.
        if yellow_cards_value is None:

            (
                yellow_cards_value,
                opponent_yellow_cards_value,
            ) = extract_pair(
                "yellow_cards",
                "cards",
            )

        # ====================================================
        # RED CARDS
        # ====================================================

        (
            red_cards_value,
            opponent_red_cards_value,
        ) = extract_pair(
            "red_cards"
        )

        # ====================================================
        # FOULS
        # ====================================================

        (
            fouls_value,
            opponent_fouls_value,
        ) = extract_pair(
            "fouls"
        )

        # ====================================================
        # OFFSIDES
        # ====================================================

        (
            offsides_value,
            opponent_offsides_value,
        ) = extract_pair(
            "offsides"
        )

        # ====================================================
        # SAVE OWN VALUES INTO EXTRA
        #
        # Это КЛЮЧЕВАЯ правка.
        #
        # FormWin / Defence получают данные из extra,
        # поэтому собственные факты тоже должны находиться
        # там.
        # ====================================================

        own_extra_values = {

            "xg": own_xg,

            "shots": shots_value,

            "shots_on_target":
                sot_value,

            "blocked_shots":
                blocked_shots_value,

            "big_chances":
                big_chances_value,

            "possession":
                possession_value,

            "passes":
                passes_value,

            "pass_accuracy":
                pass_accuracy_value,

            "corners":
                corners_value,

            "yellow_cards":
                yellow_cards_value,

            "red_cards":
                red_cards_value,

            "fouls":
                fouls_value,

            "offsides":
                offsides_value,
        }

        for key, value in own_extra_values.items():

            if value is not None:

                extra[key] = value

        # ====================================================
        # SAVE OPPONENT VALUES INTO EXTRA
        # ====================================================

        opponent_extra_values = {

            "opponent_xg":
                opponent_xg,

            "opponent_shots":
                opponent_shots_value,

            "opponent_shots_on_target":
                opponent_sot_value,

            "opponent_blocked_shots":
                opponent_blocked_shots_value,

            "opponent_big_chances":
                opponent_big_chances_value,

            "opponent_possession":
                opponent_possession_value,

            "opponent_passes":
                opponent_passes_value,

            "opponent_pass_accuracy":
                opponent_pass_accuracy_value,

            "opponent_corners":
                opponent_corners_value,

            "opponent_yellow_cards":
                opponent_yellow_cards_value,

            "opponent_red_cards":
                opponent_red_cards_value,

            "opponent_fouls":
                opponent_fouls_value,

            "opponent_offsides":
                opponent_offsides_value,
        }

        for key, value in opponent_extra_values.items():

            if value is not None:

                extra[key] = value

        # ====================================================
        # GOALS
        # ====================================================

        goals_for = _float(
            data.get("goals_for")
        )

        if goals_for is None:

            goals_for = _float(
                data.get("goals")
            )

        goals_against = _float(
            data.get("goals_against")
        )

        # Если пришёл общий домашний/гостевой счёт.
        if (
            goals_for is None
            and "home_goals" in data
            and "away_goals" in data
        ):

            home_goals = _float(
                data.get("home_goals")
            )

            away_goals = _float(
                data.get("away_goals")
            )

            if is_home is True:

                goals_for = home_goals
                goals_against = away_goals

            elif is_home is False:

                goals_for = away_goals
                goals_against = home_goals

        # ====================================================
        # RETURN
        # ====================================================

        return cls(

            team=current_team,

            opponent=opponent,

            is_home=is_home,

            goals_for=goals_for,

            goals_against=goals_against,

            shots=shots_value,

            shots_on_target=sot_value,

            possession=possession_value,

            corners=corners_value,

            yellow_cards=yellow_cards_value,

            red_cards=red_cards_value,

            xg=own_xg,

            big_chances=big_chances_value,

            competition=data.get(
                "competition"
            ),

            match_date=data.get(
                "match_date"
            ),

            extra=extra,
        )


# ============================================================
# TEAM PROFILE (LEGACY)
# ============================================================

@dataclass
class TeamProfile:

    name: str

    matches: int

    goals_for: Optional[float]
    goals_against: Optional[float]

    attack: float
    defence: float

    home_attack: Optional[float] = None
    away_attack: Optional[float] = None

    corners: Optional[float] = None
    cards: Optional[float] = None

    shots: Optional[float] = None
    shots_on_target: Optional[float] = None

    xg: Optional[float] = None

    form_points: Optional[float] = None

    data_quality: float = 0.0


# ============================================================
# BRAIN PREDICTION
# ============================================================

@dataclass
class BrainPrediction:

    home_team: str
    away_team: str

    home_win_probability: float
    draw_probability: float
    away_win_probability: float

    btts_probability: float

    over25_probability: float
    over35_probability: float

    home_xg: float
    away_xg: float

    most_likely_score: str
    second_likely_score: str
    third_likely_score: str

    corners_expected: Optional[float]

    home_corners_expected: Optional[float]
    away_corners_expected: Optional[float]

    over75_corners_probability: Optional[float]
    over85_corners_probability: Optional[float]
    over95_corners_probability: Optional[float]
    over105_corners_probability: Optional[float]

    cards_expected: Optional[float]

    home_cards_expected: Optional[float]
    away_cards_expected: Optional[float]

    over25_cards_probability: Optional[float]
    over35_cards_probability: Optional[float]
    over45_cards_probability: Optional[float]

    confidence: float
    risk: str

    analysis_mode: str
    data_quality: float

    conclusion: str

    factors: List[str] = field(
        default_factory=list
    )

    calculation_meta: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        return {

            "brain_version":
                BRAIN_VERSION,

            "home_team":
                self.home_team,

            "away_team":
                self.away_team,

            "home_win_probability":
                self.home_win_probability,

            "draw_probability":
                self.draw_probability,

            "away_win_probability":
                self.away_win_probability,

            "btts_probability":
                self.btts_probability,

            "over25_probability":
                self.over25_probability,

            "over35_probability":
                self.over35_probability,

            "home_xg":
                self.home_xg,

            "away_xg":
                self.away_xg,

            "most_likely_score":
                self.most_likely_score,

            "second_likely_score":
                self.second_likely_score,

            "third_likely_score":
                self.third_likely_score,

            "corners_expected":
                self.corners_expected,

            "home_corners_expected":
                self.home_corners_expected,

            "away_corners_expected":
                self.away_corners_expected,

            "over75_corners_probability":
                self.over75_corners_probability,

            "over85_corners_probability":
                self.over85_corners_probability,

            "over95_corners_probability":
                self.over95_corners_probability,

            "over105_corners_probability":
                self.over105_corners_probability,

            "cards_expected":
                self.cards_expected,

            "home_cards_expected":
                self.home_cards_expected,

            "away_cards_expected":
                self.away_cards_expected,

            "over25_cards_probability":
                self.over25_cards_probability,

            "over35_cards_probability":
                self.over35_cards_probability,

            "over45_cards_probability":
                self.over45_cards_probability,

            "confidence":
                self.confidence,

            "risk":
                self.risk,

            "analysis_mode":
                self.analysis_mode,

            "data_quality":
                self.data_quality,

            "conclusion":
                self.conclusion,

            "factors":
                self.factors,

            "calculation_meta":
                self.calculation_meta,
        }


# ============================================================
# POISSON (LEGACY - сохраняется для совместимости)
# ============================================================

def poisson_probability(
    goals: int,
    expected: float,
) -> float:

    if expected is None or expected < 0:

        return 0.0

    return (
        math.exp(-expected)
        * (expected ** goals)
        / math.factorial(goals)
    )


def score_distribution(
    home_xg: float,
    away_xg: float,
    max_goals: int = 7,
) -> List[Dict[str, Any]]:

    scores = []

    for home_goals in range(
        max_goals + 1
    ):

        home_probability = (
            poisson_probability(
                home_goals,
                home_xg,
            )
        )

        for away_goals in range(
            max_goals + 1
        ):

            away_probability = (
                poisson_probability(
                    away_goals,
                    away_xg,
                )
            )

            probability = (
                home_probability
                * away_probability
            )

            scores.append({

                "home":
                    home_goals,

                "away":
                    away_goals,

                "probability":
                    probability,
            })

    scores.sort(
        key=lambda item:
            item["probability"],
        reverse=True,
    )

    return scores


# ============================================================
# FAJ BRAIN
# ============================================================

class FAJBrain:

    """
    Новый основной математический мозг FAJ.
    """

    def __init__(self):

        # ====================================================
        # ALL MODELS ARE INSTANTIATED ON DEMAND
        # ====================================================

        self.version = BRAIN_VERSION

        # ====================================================
        # DIAGNOSTIC MODELS (Corners/Cards)
        # ====================================================

        self.corners_model = CornersModel()
        self.cards_model = CardsModel()

    # ========================================================
    # NORMALIZATION (LEGACY)
    # ========================================================

    def _normalize_matches(
        self,
        matches: Iterable[Any],
        team_name: str,
    ) -> List[HistoricalMatch]:

        result = []

        for match in matches or []:

            if isinstance(
                match,
                HistoricalMatch,
            ):

                result.append(match)

            elif isinstance(
                match,
                dict,
            ):

                result.append(
                    HistoricalMatch.from_dict(
                        match,
                        team=team_name,
                    )
                )

        return result

    # ========================================================
    # BUILD FORM CONTEXT (LEGACY)
    # ========================================================

    def _build_form_context_for_model(
        self,
        team_name: str,
        matches: List[HistoricalMatch],
    ) -> Dict[str, Any]:

        from app.core.form_context import (
            build_form_context
        )

        records = []

        for match in matches:

            if match.is_home:

                home_team = match.team
                away_team = (
                    match.opponent
                    or ""
                )

                home_goals = (
                    match.goals_for
                )

                away_goals = (
                    match.goals_against
                )

                home_corners = (
                    match.corners
                )

                away_corners = (
                    match.extra.get(
                        "opponent_corners"
                    )
                )

                home_cards = (
                    match.yellow_cards
                )

                away_cards = (
                    match.extra.get(
                        "opponent_yellow_cards"
                    )
                )

            else:

                home_team = (
                    match.opponent
                    or ""
                )

                away_team = match.team

                home_goals = (
                    match.goals_against
                )

                away_goals = (
                    match.goals_for
                )

                home_corners = (
                    match.extra.get(
                        "opponent_corners"
                    )
                )

                away_corners = (
                    match.corners
                )

                home_cards = (
                    match.extra.get(
                        "opponent_yellow_cards"
                    )
                )

                away_cards = (
                    match.yellow_cards
                )

            record = {

                "home_team":
                    home_team,

                "away_team":
                    away_team,

                "home_goals":
                    home_goals,

                "away_goals":
                    away_goals,

                "xg": {

                    "home":
                        (
                            match.xg
                            if match.is_home
                            else match.extra.get(
                                "opponent_xg"
                            )
                        ),

                    "away":
                        (
                            match.xg
                            if not match.is_home
                            else match.extra.get(
                                "opponent_xg"
                            )
                        ),
                },

                "home_corners":
                    home_corners,

                "away_corners":
                    away_corners,

                "home_yellow_cards":
                    home_cards,

                "away_yellow_cards":
                    away_cards,

                "match_date":
                    match.match_date,

                "is_home":
                    match.is_home,

                "opponent":
                    match.opponent,
            }

            records.append(record)

        return build_form_context(
            team_name=team_name,
            records=records,
            limit=PREFERRED_MATCHES,
        )

    # ========================================================
    # ENRICH FORM CONTEXT (LEGACY)
    # ========================================================

    def _enrich_form_context(
        self,
        form_context: Any,
        matches: List[HistoricalMatch],
    ) -> Dict[str, Any]:
        """
        Передаёт все доступные исторические факты
        математическим органам.

        None сохраняется как None.
        """

        # ----------------------------------------------------
        # Base context
        # ----------------------------------------------------

        if isinstance(
            form_context,
            dict,
        ):

            context = dict(
                form_context
            )

        else:

            context = {}

            if hasattr(
                form_context,
                "__dataclass_fields__",
            ):

                context.update(
                    asdict(
                        form_context
                    )
                )

            elif hasattr(
                form_context,
                "__dict__",
            ):

                context.update(
                    vars(
                        form_context
                    )
                )

        # ====================================================
        # XG
        # ====================================================

        context["team_xg_history"] = [
            match.xg
            for match in matches
        ]

        context["opponent_xg_history"] = [
            match.extra.get(
                "opponent_xg"
            )
            for match in matches
        ]

        context["recent_xg"] = [
            match.xg
            for match in matches
        ]

        context["recent_xga"] = [
            match.extra.get(
                "opponent_xg"
            )
            for match in matches
        ]

        # ====================================================
        # SHOTS
        # ====================================================

        context["shots_history"] = [
            match.shots
            for match in matches
        ]

        context["shots_conceded_history"] = [
            match.extra.get(
                "opponent_shots"
            )
            for match in matches
        ]

        # ====================================================
        # SOT
        # ====================================================

        context["shots_on_target_history"] = [
            match.shots_on_target
            for match in matches
        ]

        context["sot_conceded_history"] = [
            match.extra.get(
                "opponent_shots_on_target"
            )
            for match in matches
        ]

        # ====================================================
        # BLOCKED SHOTS
        # ====================================================

        context["blocked_shots_history"] = [
            match.extra.get(
                "blocked_shots"
            )
            for match in matches
        ]

        context["blocked_shots_conceded_history"] = [
            match.extra.get(
                "opponent_blocked_shots"
            )
            for match in matches
        ]

        # ====================================================
        # BIG CHANCES
        # ====================================================

        context["big_chances_history"] = [
            match.big_chances
            for match in matches
        ]

        context["big_chances_against_history"] = [
            match.extra.get(
                "opponent_big_chances"
            )
            for match in matches
        ]

        # ====================================================
        # POSSESSION
        # ====================================================

        context["possession_history"] = [
            match.possession
            for match in matches
        ]

        context["opponent_possession_history"] = [
            match.extra.get(
                "opponent_possession"
            )
            for match in matches
        ]

        # ====================================================
        # CORNERS
        # ====================================================

        context["corners_for_history"] = [
            match.corners
            for match in matches
        ]

        context["corners_against_history"] = [
            match.extra.get(
                "opponent_corners"
            )
            for match in matches
        ]

        # ====================================================
        # GOALS
        # ====================================================

        context["goals_for_history"] = [
            match.goals_for
            for match in matches
        ]

        context["goals_against_history"] = [
            match.goals_against
            for match in matches
        ]

        # ====================================================
        # VENUE
        # ====================================================

        context["venue_history"] = [

            "home"
            if match.is_home is True

            else "away"
            if match.is_home is False

            else None

            for match in matches
        ]

        # ====================================================
        # RESULTS
        # ====================================================

        context["results_history"] = [

            self._historical_result(
                match
            )

            for match in matches
        ]

        # ====================================================
        # PASSES
        # ====================================================

        context["passes_history"] = [

            match.extra.get(
                "passes"
            )

            for match in matches
        ]

        context["opponent_passes_history"] = [

            match.extra.get(
                "opponent_passes"
            )

            for match in matches
        ]

        # ====================================================
        # PASS ACCURACY
        # ====================================================

        context["pass_accuracy_history"] = [

            match.extra.get(
                "pass_accuracy"
            )

            for match in matches
        ]

        context["opponent_pass_accuracy_history"] = [

            match.extra.get(
                "opponent_pass_accuracy"
            )

            for match in matches
        ]

        # ====================================================
        # FOULS
        # ====================================================

        context["fouls_history"] = [

            match.extra.get(
                "fouls"
            )

            for match in matches
        ]

        context["opponent_fouls_history"] = [

            match.extra.get(
                "opponent_fouls"
            )

            for match in matches
        ]

        # ====================================================
        # OFFSIDES
        # ====================================================

        context["offsides_history"] = [

            match.extra.get(
                "offsides"
            )

            for match in matches
        ]

        context["opponent_offsides_history"] = [

            match.extra.get(
                "opponent_offsides"
            )

            for match in matches
        ]

        # ====================================================
        # YELLOW CARDS
        # ====================================================

        context["team_cards_history"] = [

            match.yellow_cards
            for match in matches
        ]

        context["opponent_cards_history"] = [

            match.extra.get(
                "opponent_yellow_cards"
            )

            for match in matches
        ]

        # ====================================================
        # RED CARDS
        # ====================================================

        context["red_cards_history"] = [

            match.red_cards
            for match in matches
        ]

        context["opponent_red_cards_history"] = [

            match.extra.get(
                "opponent_red_cards"
            )

            for match in matches
        ]

        return context

    # ========================================================
    # HISTORICAL RESULT (LEGACY)
    # ========================================================

    @staticmethod
    def _historical_result(
        match: HistoricalMatch,
    ) -> Optional[str]:

        if (
            match.goals_for is None
            or match.goals_against is None
        ):

            return None

        if (
            match.goals_for
            > match.goals_against
        ):

            return "W"

        if (
            match.goals_for
            < match.goals_against
        ):

            return "L"

        return "D"

    # ========================================================
    # OLD PROFILE (LEGACY)
    # ========================================================

    def build_profile(
        self,
        team_name: str,
        matches: Iterable[Any],
    ) -> TeamProfile:

        normalized = (
            self._normalize_matches(
                matches,
                team_name,
            )
        )

        count = len(
            normalized
        )

        if count == 0:

            return TeamProfile(

                name=team_name,

                matches=0,

                goals_for=None,

                goals_against=None,

                attack=1.0,

                defence=1.0,

                data_quality=0.0,
            )

        # ====================================================
        # GOALS
        # ====================================================

        goals_for = _weighted_mean(

            match.goals_for

            for match in normalized
        )

        goals_against = _weighted_mean(

            match.goals_against

            for match in normalized
        )

        # ====================================================
        # CORNERS
        # ====================================================

        corners = _weighted_mean(

            match.corners

            for match in normalized
        )

        # ====================================================
        # CARDS
        # ====================================================

        card_values = []

        for match in normalized:

            if (
                match.yellow_cards
                is not None
                or match.red_cards
                is not None
            ):

                yellow = (
                    match.yellow_cards
                    if match.yellow_cards
                    is not None
                    else 0.0
                )

                red = (
                    match.red_cards
                    if match.red_cards
                    is not None
                    else 0.0
                )

                card_values.append(
                    yellow + red
                )

        cards = _weighted_mean(
            card_values
        )

        # ====================================================
        # SHOTS
        # ====================================================

        shots = _weighted_mean(

            match.shots

            for match in normalized
        )

        # ====================================================
        # SOT
        # ====================================================

        shots_on_target = _weighted_mean(

            match.shots_on_target

            for match in normalized
        )

        # ====================================================
        # XG
        # ====================================================

        xg = _weighted_mean(

            match.xg

            for match in normalized
        )

        # ====================================================
        # ATTACK
        # ====================================================

        attack_components = []

        if goals_for is not None:

            attack_components.append(
                goals_for
            )

        if xg is not None:

            attack_components.append(
                xg
            )

        if shots_on_target is not None:

            attack_components.append(
                shots_on_target * 0.35
            )

        attack = (

            _mean(
                attack_components
            )

            if attack_components

            else 1.0
        )

        # ====================================================
        # DEFENCE
        # ====================================================

        if goals_against is not None:

            defence = 1.0 / (
                1.0
                + max(
                    0.0,
                    goals_against,
                )
            )

        else:

            defence = 0.5

        # ====================================================
        # HOME / AWAY
        # ====================================================

        home_matches = [

            match

            for match in normalized

            if match.is_home is True
        ]

        away_matches = [

            match

            for match in normalized

            if match.is_home is False
        ]

        home_attack = _weighted_mean(

            match.goals_for

            for match in home_matches
        )

        away_attack = _weighted_mean(

            match.goals_for

            for match in away_matches
        )

        # ====================================================
        # FORM
        # ====================================================

        points = []

        for match in normalized:

            if match.goals_for is None:
                continue

            if match.goals_against is None:
                continue

            if (
                match.goals_for
                > match.goals_against
            ):

                points.append(3)

            elif (
                match.goals_for
                == match.goals_against
            ):

                points.append(1)

            else:

                points.append(0)

        form_points = (

            _weighted_mean(
                points
            )

            if points

            else None
        )

        # ====================================================
        # DATA QUALITY
        # ====================================================

        quality = (
            self._calculate_data_quality(
                normalized
            )
        )

        return TeamProfile(

            name=team_name,

            matches=count,

            goals_for=goals_for,

            goals_against=goals_against,

            attack=float(
                attack or 1.0
            ),

            defence=float(
                defence
            ),

            home_attack=home_attack,

            away_attack=away_attack,

            corners=corners,

            cards=cards,

            shots=shots,

            shots_on_target=(
                shots_on_target
            ),

            xg=xg,

            form_points=form_points,

            data_quality=quality,
        )

    # ========================================================
    # DATA QUALITY (LEGACY)
    # ========================================================

    def _calculate_data_quality(
        self,
        matches: List[HistoricalMatch],
    ) -> float:

        if not matches:

            return 0.0

        count_factor = min(

            len(matches)
            / PREFERRED_MATCHES,

            1.0,
        )

        fields = [

            "goals_for",

            "goals_against",

            "shots",

            "shots_on_target",

            "corners",

            "yellow_cards",

        ]

        available = 0

        total = (
            len(matches)
            * len(fields)
        )

        for match in matches:

            for field_name in fields:

                if getattr(
                    match,
                    field_name,
                ) is not None:

                    available += 1

        completeness = (

            available / total

            if total

            else 0.0
        )

        return round(

            100.0
            * (
                0.65 * count_factor
                + 0.35 * completeness
            ),

            1,
        )

    # ========================================================
    # EXPECTED GOALS (UPDATED: v0.8 — только FormModel, без FormWin/Defence)
    # ========================================================

    def _calculate_expected_goals(
        self,
        home_form_result: Any,
        away_form_result: Any,
        home_team: str,
        away_team: str,
    ) -> tuple[
        Optional[float],
        Optional[float],
        Any,
    ]:

        goal_result = self.goal_model.analyze(
            home_form=home_form_result,
            away_form=away_form_result,
            home_team=home_team,
            away_team=away_team,
            venue="HOME",
        )

        return (
            goal_result.home_xg,
            goal_result.away_xg,
            goal_result,
        )

    # ========================================================
    # RESULT PROBABILITIES (LEGACY)
    # ========================================================

    def _result_probabilities(
        self,
        home_xg: float,
        away_xg: float,
    ) -> Dict[str, float]:

        distribution = (
            score_distribution(
                home_xg,
                away_xg,
            )
        )

        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for score in distribution:

            if (
                score["home"]
                > score["away"]
            ):

                home_win += (
                    score["probability"]
                )

            elif (
                score["home"]
                == score["away"]
            ):

                draw += (
                    score["probability"]
                )

            else:

                away_win += (
                    score["probability"]
                )

        total = (
            home_win
            + draw
            + away_win
        )

        if total <= 0:

            return {

                "home":
                    1 / 3,

                "draw":
                    1 / 3,

                "away":
                    1 / 3,
            }

        return {

            "home":
                home_win / total,

            "draw":
                draw / total,

            "away":
                away_win / total,
        }

    # ========================================================
    # TOTALS (LEGACY)
    # ========================================================

    def _totals(
        self,
        home_xg: float,
        away_xg: float,
    ) -> Dict[str, float]:

        distribution = (
            score_distribution(
                home_xg,
                away_xg,
            )
        )

        btts = 0.0

        over25 = 0.0

        over35 = 0.0

        for score in distribution:

            home = score["home"]

            away = score["away"]

            probability = (
                score["probability"]
            )

            if (
                home >= 1
                and away >= 1
            ):

                btts += probability

            if (
                home + away >= 3
            ):

                over25 += probability

            if (
                home + away >= 4
            ):

                over35 += probability

        return {

            "btts":
                _probability(btts),

            "over25":
                _probability(over25),

            "over35":
                _probability(over35),
        }

    # ========================================================
    # SIMPLE POISSON TOTAL (LEGACY)
    # ========================================================

    def _over_probability(
        self,
        expected: Optional[float],
        line: float,
    ) -> Optional[float]:

        if expected is None:

            return None

        probability_under = 0.0

        max_goals = 12

        for goals in range(
            0,
            max_goals + 1,
        ):

            if goals <= math.floor(
                line
            ):

                probability_under += (
                    poisson_probability(
                        goals,
                        expected,
                    )
                )

        return round(

            _clamp(
                1.0
                - probability_under
            )
            * 100.0,

            1,
        )

    # ========================================================
    # CONFIDENCE (LEGACY)
    # ========================================================

    def _confidence(
        self,
        home: TeamProfile,
        away: TeamProfile,
        probabilities: Dict[str, float],
    ) -> float:

        quality = (

            home.data_quality
            + away.data_quality

        ) / 2.0

        ordered = sorted(

            probabilities.values(),

            reverse=True,
        )

        separation = (

            ordered[0]
            - ordered[1]
        )

        separation_score = (
            _clamp(
                separation / 0.45
            )
            * 100.0
        )

        confidence = (

            0.55 * quality
            + 0.45 * separation_score
        )

        return round(

            _clamp(
                confidence / 100.0
            )
            * 100.0,

            1,
        )

    # ========================================================
    # RISK (LEGACY)
    # ========================================================

    def _risk(
        self,
        confidence: float,
        home: TeamProfile,
        away: TeamProfile,
    ) -> str:

        quality = (

            home.data_quality
            + away.data_quality

        ) / 2.0

        if quality < 35:

            return "Высокий"

        if confidence < 45:

            return "Высокий"

        if confidence < 65:

            return "Средний"

        return "Низкий"

    # ========================================================
    # CONCLUSION (LEGACY)
    # ========================================================

    def _conclusion(
        self,
        home: TeamProfile,
        away: TeamProfile,
        probabilities: Dict[str, float],
        totals: Dict[str, float],
    ) -> tuple[
        str,
        List[str],
    ]:

        factors = []

        # ====================================================
        # WINNER
        # ====================================================

        if probabilities["home"] >= max(

            probabilities["draw"],

            probabilities["away"],
        ):

            winner_text = (
                f"преимущество "
                f"{home.name}"
            )

            factors.append(
                "Модель видит "
                "преимущество хозяев."
            )

        elif probabilities["away"] >= max(

            probabilities["home"],

            probabilities["draw"],
        ):

            winner_text = (
                f"преимущество "
                f"{away.name}"
            )

            factors.append(
                "Модель видит "
                "преимущество гостей."
            )

        else:

            winner_text = (
                "равновесие сил"
            )

            factors.append(
                "Модель не видит "
                "явного фаворита."
            )

        # ====================================================
        # BTTS
        # ====================================================

        if totals["btts"] >= 60:

            factors.append(
                "Вероятность обмена "
                "голами повышена."
            )

        elif totals["btts"] <= 40:

            factors.append(
                "Модель не ожидает "
                "высокой вероятности "
                "обмена голами."
            )

        # ====================================================
        # TOTALS
        # ====================================================

        if totals["over25"] >= 60:

            factors.append(
                "Сценарий с 3+ голами "
                "выглядит вероятным."
            )

        elif totals["over25"] <= 40:

            factors.append(
                "Модель скорее склоняется "
                "к умеренной результативности."
            )

        conclusion = (

            f"FAJ: {winner_text}. "
            f"{' '.join(factors)}"
        )

        return (
            conclusion,
            factors,
        )

    # ========================================================
    # JSON SAFE (LEGACY)
    # ========================================================

    def _json_safe(
        self,
        value: Any,
    ) -> Any:

        if value is None:

            return None

        if hasattr(
            value,
            "to_dict",
        ):

            return self._json_safe(
                value.to_dict()
            )

        if hasattr(
            value,
            "__dataclass_fields__",
        ):

            return {

                key:
                    self._json_safe(
                        item
                    )

                for key, item
                in asdict(
                    value
                ).items()
            }

        if isinstance(
            value,
            dict,
        ):

            return {

                key:
                    self._json_safe(
                        item
                    )

                for key, item
                in value.items()
            }

        if isinstance(
            value,
            (list, tuple),
        ):

            return [

                self._json_safe(
                    item
                )

                for item in value
            ]

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):

            return value

        return str(value)

    # ========================================================
    # ========================================================
    # FAJ MATHEMATICAL BRAIN BRIDGE
    # v1.2
    #
    # RAW HISTORY
    #     ↓
    # build_form_context() → runtime dict
    #     ↓
    # ┌──────────────────────────────────┐
    # │ Brain Context Adapter            │
    # ├──────────────────────────────────┤
    # │ - FormModel context              │
    # │ - Control adapter                │
    # │ - BrainContract adapter          │
    # └──────────────┬───────────────────┘
    #                ↓
    #           FormModel
    #                ↓
    #           FormWin
    #                ↓
    #           Defence
    #                ↓
    #           FormControl
    #                ↓
    #           FormAnomaly
    #                ↓
    #           SpecialForm
    #                ↓
    #           GoalModel (v2.0 — только FormModel)
    #                ↓
    #           ProbabilityModel (v1.1)
    #                ↓
    #           ScorePredictor (v2.2)
    #                ↓
    #           CornersModel (v1.2)
    #                ↓
    #           CardsModel (v1.2)
    #                ↓
    #              BRAIN
    # ============================================================

    # ------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------

    def _value(
        self,
        obj: Any,
        *names: str,
    ) -> Any:
        """
        Унифицированное получение значения
        из dict / sqlite3.Row / object.
        """
        if obj is None:
            return None

        for name in names:
            if isinstance(obj, dict):
                if name in obj:
                    return obj[name]

            try:
                keys = obj.keys()
                if name in keys:
                    return obj[name]
            except (AttributeError, TypeError):
                pass

            try:
                return getattr(
                    obj,
                    name,
                )
            except AttributeError:
                pass

        return None

    def _safe_float(
        self,
        value: Any,
    ) -> Optional[float]:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        try:
            value = float(value)
            if value != value:
                return None
            return value
        except (
            TypeError,
            ValueError,
        ):
            return None

    def _safe_int(
        self,
        value: Any,
    ) -> Optional[int]:
        value = self._safe_float(value)
        if value is None:
            return None
        return int(round(value))

    # ------------------------------------------------------------
    # CONTROL CONTEXT ADAPTER
    # ------------------------------------------------------------

    def _build_control_context(
        self,
        matches: List[Any],
    ) -> Dict[str, Any]:
        """
        Создаёт именно тот слой истории,
        который ожидает FormControl v1.1.

        Источник — исходные historical records.
        Никаких новых значений не придумываем.
        None остаётся None.

        Порядок:
            M1 → M6
            старый → новый
        """
        context = {
            "possession_history": [],
            "opponent_possession_history": [],
            "passes_history": [],
            "opponent_passes_history": [],
            "pass_accuracy_history": [],
            "opponent_pass_accuracy_history": [],
            "crosses_history": [],
            "opponent_crosses_history": [],
            "throw_ins_history": [],
            "opponent_throw_ins_history": [],
            "offsides_history": [],
            "opponent_offsides_history": [],
            "shots_history": [],
            "shots_conceded_history": [],
            "big_chances_history": [],
            "big_chances_against_history": [],
            "corners_for_history": [],
            "corners_against_history": [],
        }

        for record in list(matches or [])[:6]:
            stats = self._value(
                record,
                "stats",
                "statistics",
            )

            if not isinstance(
                stats,
                dict,
            ):
                stats = {}

            def stat(
                *names: str,
            ) -> Any:
                value = self._value(
                    record,
                    *names,
                )
                if value is not None:
                    return value
                return self._value(
                    stats,
                    *names,
                )

            # ----------------------------------------------------
            # Определяем сторону
            # ----------------------------------------------------
            home_team = self._value(
                record,
                "home_team",
                "home_name",
                "home",
            )
            away_team = self._value(
                record,
                "away_team",
                "away_name",
                "away",
            )
            team_name = self._value(
                record,
                "team",
                "team_name",
            )

            is_home = (
                team_name is not None
                and home_team is not None
                and str(team_name).strip().lower()
                == str(home_team).strip().lower()
            )

            is_away = (
                team_name is not None
                and away_team is not None
                and str(team_name).strip().lower()
                == str(away_team).strip().lower()
            )

            # ----------------------------------------------------
            # Универсальный side extractor
            # ----------------------------------------------------
            def side_value(
                metric: str,
            ) -> Any:
                if is_home:
                    return stat(
                        f"home_{metric}",
                        f"{metric}_home",
                    )
                if is_away:
                    return stat(
                        f"away_{metric}",
                        f"{metric}_away",
                    )
                return stat(
                    f"team_{metric}",
                    metric,
                )

            def opponent_value(
                metric: str,
            ) -> Any:
                if is_home:
                    return stat(
                        f"away_{metric}",
                        f"{metric}_away",
                    )
                if is_away:
                    return stat(
                        f"home_{metric}",
                        f"{metric}_home",
                    )
                return stat(
                    f"opponent_{metric}",
                )

            # ----------------------------------------------------
            # CONTROL
            # ----------------------------------------------------
            context[
                "possession_history"
            ].append(
                self._safe_float(
                    side_value("possession")
                )
            )

            context[
                "opponent_possession_history"
            ].append(
                self._safe_float(
                    opponent_value("possession")
                )
            )

            context[
                "passes_history"
            ].append(
                self._safe_float(
                    side_value("passes")
                )
            )

            context[
                "opponent_passes_history"
            ].append(
                self._safe_float(
                    opponent_value("passes")
                )
            )

            context[
                "pass_accuracy_history"
            ].append(
                self._safe_float(
                    side_value(
                        "pass_accuracy"
                    )
                )
            )

            context[
                "opponent_pass_accuracy_history"
            ].append(
                self._safe_float(
                    opponent_value(
                        "pass_accuracy"
                    )
                )
            )

            # ----------------------------------------------------
            # PROGRESSION
            # ----------------------------------------------------
            context[
                "crosses_history"
            ].append(
                self._safe_float(
                    side_value("crosses")
                )
            )

            context[
                "opponent_crosses_history"
            ].append(
                self._safe_float(
                    opponent_value("crosses")
                )
            )

            context[
                "throw_ins_history"
            ].append(
                self._safe_float(
                    side_value("throw_ins")
                )
            )

            context[
                "opponent_throw_ins_history"
            ].append(
                self._safe_float(
                    opponent_value("throw_ins")
                )
            )

            context[
                "offsides_history"
            ].append(
                self._safe_float(
                    side_value("offsides")
                )
            )

            context[
                "opponent_offsides_history"
            ].append(
                self._safe_float(
                    opponent_value("offsides")
                )
            )

            # ----------------------------------------------------
            # PRESSURE
            # ----------------------------------------------------
            context[
                "shots_history"
            ].append(
                self._safe_float(
                    side_value("shots")
                )
            )

            context[
                "shots_conceded_history"
            ].append(
                self._safe_float(
                    opponent_value("shots")
                )
            )

            context[
                "big_chances_history"
            ].append(
                self._safe_float(
                    side_value("big_chances")
                )
            )

            context[
                "big_chances_against_history"
            ].append(
                self._safe_float(
                    opponent_value("big_chances")
                )
            )

            # ----------------------------------------------------
            # CORNERS
            # ----------------------------------------------------
            context[
                "corners_for_history"
            ].append(
                self._safe_float(
                    side_value("corners")
                )
            )

            context[
                "corners_against_history"
            ].append(
                self._safe_float(
                    opponent_value("corners")
                )
            )

        return context

    # ------------------------------------------------------------
    # BRAIN CONTRACT ADAPTER
    # ------------------------------------------------------------

    def _build_brain_form_context(
        self,
        team_name: str,
        matches: List[Any],
        runtime_context: Dict[str, Any],
    ) -> BrainFormContext:
        """
        Runtime FormContext
                ↓
        brain_contract.FormContext

        Только адаптация.
        Никаких прогнозов.
        """
        results = []
        for match in runtime_context.get(
            "matches",
            [],
        ):
            result = match.get(
                "result"
            )
            if result in (
                "W",
                "D",
                "L",
            ):
                results.append(result)

        wins = results.count("W")
        draws = results.count("D")
        losses = results.count("L")
        points = (
            wins * 3
            + draws
        )

        # --------------------------------------------------------
        # Goals
        # --------------------------------------------------------
        goals_for = []
        goals_against = []

        for match in runtime_context.get(
            "matches",
            [],
        ):
            gf = self._safe_float(
                match.get("team_goals")
            )
            ga = self._safe_float(
                match.get("opponent_goals")
            )

            if gf is not None:
                goals_for.append(gf)
            if ga is not None:
                goals_against.append(ga)

        goals_for_avg = (
            sum(goals_for) / len(goals_for)
            if goals_for
            else None
        )

        goals_against_avg = (
            sum(goals_against)
            / len(goals_against)
            if goals_against
            else None
        )

        # --------------------------------------------------------
        # xG
        # --------------------------------------------------------
        xg_values = [
            value
            for value in runtime_context.get(
                "recent_xg",
                ()
            )
            if value is not None
        ]

        xga_values = [
            value
            for value in runtime_context.get(
                "recent_xga",
                ()
            )
            if value is not None
        ]

        xg_avg = (
            sum(xg_values)
            / len(xg_values)
            if xg_values
            else None
        )

        xga_avg = (
            sum(xga_values)
            / len(xga_values)
            if xga_values
            else None
        )

        # --------------------------------------------------------
        # Home / Away
        # --------------------------------------------------------
        home = runtime_context.get(
            "home",
            {},
        )
        away = runtime_context.get(
            "away",
            {},
        )

        # --------------------------------------------------------
        # Derived flags
        # --------------------------------------------------------
        consecutive_wins = 0
        for result in reversed(results):
            if result == "W":
                consecutive_wins += 1
            else:
                break

        home_unbeaten = 0
        for match in reversed(
            runtime_context.get(
                "matches",
                [],
            )
        ):
            if match.get("venue") != "дома":
                continue
            if match.get("result") in (
                "W",
                "D",
            ):
                home_unbeaten += 1
            else:
                break

        away_wins_recent = 0
        for match in reversed(
            runtime_context.get(
                "matches",
                [],
            )
        ):
            if match.get("venue") != "гости":
                continue
            if match.get("result") == "W":
                away_wins_recent += 1
            else:
                break

        consecutive_away = 0
        for match in reversed(
            runtime_context.get(
                "matches",
                [],
            )
        ):
            if match.get("venue") == "гости":
                consecutive_away += 1
            else:
                break

        return BrainFormContext(
            team=team_name,
            results=tuple(results),
            wins=wins,
            draws=draws,
            losses=losses,
            points=points,

            home_wins=int(
                home.get("wins", 0)
            ),
            home_draws=int(
                home.get("draws", 0)
            ),
            home_losses=int(
                home.get("losses", 0)
            ),
            away_wins=int(
                away.get("wins", 0)
            ),
            away_draws=int(
                away.get("draws", 0)
            ),
            away_losses=int(
                away.get("losses", 0)
            ),

            goals_for_avg=goals_for_avg,
            goals_against_avg=goals_against_avg,

            xg_avg=xg_avg,
            xga_avg=xga_avg,

            corners_for_avg=None,
            corners_against_avg=None,
            possession_avg=None,
            cards_avg=None,
            fouls_avg=None,

            difficulty=tuple(
                runtime_context.get(
                    "difficulty",
                    []
                )
            ),

            consecutive_away_matches=(
                consecutive_away
            ),
            consecutive_wins=(
                consecutive_wins
            ),
            home_unbeaten_count=(
                home_unbeaten
            ),
            away_wins_recent=(
                away_wins_recent
            ),
        )

    # ------------------------------------------------------------
    # MAIN MATH CONTEXT
    # ------------------------------------------------------------

    def _build_math_context(
        self,
        team_name: str,
        matches: List[Any],
        venue: str,
    ) -> Dict[str, Any]:
        runtime_context = build_form_context(
            team_name,
            matches,
            limit=6,
        )

        if not isinstance(
            runtime_context,
            dict,
        ):
            runtime_context = dict(
                runtime_context
            )

        runtime_context["team_name"] = team_name
        runtime_context["venue"] = venue

        # --------------------------------------------------------
        # FormControl adapter
        # --------------------------------------------------------
        control_context = self._build_control_context(
            matches
        )
        runtime_context.update(
            control_context
        )

        # --------------------------------------------------------
        # Strict Brain Contract
        # --------------------------------------------------------
        runtime_context[
            "brain_contract"
        ] = self._build_brain_form_context(
            team_name=team_name,
            matches=matches,
            runtime_context=runtime_context,
        )

        return runtime_context

    # ------------------------------------------------------------
    # FORM PIPELINE
    # ------------------------------------------------------------

    def _run_form_pipeline(
        self,
        team_name: str,
        opponent_name: str,
        matches: List[Any],
        venue: str,
    ) -> Dict[str, Any]:
        context = self._build_math_context(
            team_name=team_name,
            matches=matches,
            venue=venue,
        )

        # ========================================================
        # 1. FORM MODEL
        # ========================================================
        form_model = FormModel()
        form_result = form_model.analyze(
            context,
            next_venue=venue,
        )

        # ========================================================
        # 2. FORM WIN
        # ========================================================
        form_win = FormWin()
        form_win_result = form_win.analyze(
            context,
            next_venue=venue,
        )

        # ========================================================
        # 3. DEFENCE
        # ========================================================
        defence = Defence()
        defence_result = defence.calculate(
            context,
            team_name=team_name,
        )

        # ========================================================
        # 4. FORM CONTROL
        # ========================================================
        form_control = FormControl()
        control_result = form_control.analyze(
            context=context,
            target_team=team_name,
            opponent_team=opponent_name,
            venue=venue,
        )

        # ========================================================
        # 5. ANOMALY
        # ========================================================
        anomaly = FormAnomaly()
        anomaly_result = anomaly.analyze(
            context
        )

        # ========================================================
        # 6. SPECIAL FORM
        # ========================================================
        special_context = SimpleNamespace(
            **context
        )
        special_form = FormSpecial()
        special_result = special_form.analyze(
            special_context,
            team_name=team_name,
        )

        # ========================================================
        # 7. STRICT BRAIN CONTRACT
        # ========================================================
        brain_context = context.get(
            "brain_contract"
        )

        return {
            "team": team_name,
            "opponent": opponent_name,
            "venue": venue,
            "context": context,
            "brain_context": brain_context,
            "form_model": form_result,
            "form_win": form_win_result,
            "defence": defence_result,
            "form_control": control_result,
            "form_anomaly": anomaly_result,
            "special_form": special_result,
        }

    # ------------------------------------------------------------
    # MATCH PIPELINE
    # ------------------------------------------------------------

    def _run_match_math_pipeline(
        self,
        home_team: str,
        away_team: str,
        home_matches: List[Any],
        away_matches: List[Any],
    ) -> Dict[str, Any]:

        # ========================================================
        # HOME
        # ========================================================
        home_state = self._run_form_pipeline(
            team_name=home_team,
            opponent_name=away_team,
            matches=home_matches,
            venue="home",
        )

        # ========================================================
        # AWAY
        # ========================================================
        away_state = self._run_form_pipeline(
            team_name=away_team,
            opponent_name=home_team,
            matches=away_matches,
            venue="away",
        )

        # ========================================================
        # GOAL MODEL (v2.0 — только FormModel)
        # ========================================================
        goal_model = GoalModel()
        goal_result = goal_model.analyze(
            home_form=home_state["form_model"],
            away_form=away_state["form_model"],
            home_team=home_team,
            away_team=away_team,
            venue="HOME",
        )

        # ========================================================
        # PROBABILITY MODEL (v1.1)
        # ========================================================
        probability_model = ProbabilityModel()
        probability_result = probability_model.calculate(
            home_xg=goal_result.home_xg,
            away_xg=goal_result.away_xg,
        )

        # ========================================================
        # SCORE PREDICTOR (v2.2 — только ProbabilityModel)
        # ========================================================
        score_predictor = ScorePredictor()
        score_result = score_predictor.predict(
            score_probabilities=probability_result.score_distribution,
            home_xg=goal_result.home_xg,
            away_xg=goal_result.away_xg,
            probability_result=probability_result,
        )

        # ========================================================
        # RESULT
        # ========================================================
        return {
            "home": home_state,
            "away": away_state,
            "goal_model": goal_result,
            "probability_model": probability_result,
            "score_predictor": score_result,
            "diagnostics": {
                "home_team": home_team,
                "away_team": away_team,
                "home_matches": len(home_matches or []),
                "away_matches": len(away_matches or []),
                "home_xg": goal_result.home_xg,
                "away_xg": goal_result.away_xg,
            },
        }

    # ========================================================
    # PUBLIC PREDICTION
    # ========================================================

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_matches: Iterable[Any],
        away_matches: Iterable[Any],
        home_form_context: Optional[Any] = None,
        away_form_context: Optional[Any] = None,
    ) -> Dict[str, Any]:

        # ====================================================
        # 1. NORMALIZE (LEGACY - для совместимости)
        # ====================================================

        home_history = self._normalize_matches(
            home_matches,
            home_team,
        )

        away_history = self._normalize_matches(
            away_matches,
            away_team,
        )

        if not home_history:
            raise ValueError(f"Нет исторических данных для {home_team}.")

        if not away_history:
            raise ValueError(f"Нет исторических данных для {away_team}.")

        # ====================================================
        # 2. NEW FAJ MATHEMATICAL BRAIN
        # ====================================================

        math_pipeline = self._run_match_math_pipeline(
            home_team=home_team,
            away_team=away_team,
            home_matches=home_matches,
            away_matches=away_matches,
        )

        home_math = math_pipeline["home"]
        away_math = math_pipeline["away"]
        goal_result = math_pipeline["goal_model"]
        probability_result = math_pipeline["probability_model"]
        score_result = math_pipeline["score_predictor"]

        # ====================================================
        # 3. EXTRACT XG FROM GOAL MODEL
        # ====================================================

        home_xg = goal_result.home_xg
        away_xg = goal_result.away_xg

        # ====================================================
        # 4. NONE PROTECTION
        # ====================================================

        if home_xg is None or away_xg is None:
            raise ValueError(
                "GoalModel не смог рассчитать xG: "
                "для одной или обеих команд отсутствует "
                "необходимый xG/xGA компонент в FormModelResult."
            )

        # ====================================================
        # 5. RESULT PROBABILITIES
        # ====================================================

        probabilities = {
            "home": probability_result.home_win,
            "draw": probability_result.draw,
            "away": probability_result.away_win,
        }

        # ====================================================
        # 6. TOTALS
        # ====================================================

        btts = probability_result.btts
        over25 = probability_result.over_25
        over35 = probability_result.over_35

        totals = {
            "btts": _probability(btts) if btts is not None else None,
            "over25": _probability(over25) if over25 is not None else None,
            "over35": _probability(over35) if over35 is not None else None,
        }

        # ====================================================
        # 7. SCORE DISTRIBUTION
        # ====================================================

        top_scores = score_result.top_scores

        # v2.2 возвращает поле "score", а не "score_string"
        score_strings = [
            item["score"] for item in top_scores[:3]
        ]

        while len(score_strings) < 3:
            score_strings.append("-")

        # ====================================================
        # 8. CORNERS
        # ====================================================

        corners_result = self.corners_model.synthesize_match(
            home_math["context"],
            away_math["context"],
        )

        corner_total = corners_result.get("total_expected_corners")
        home_corners_expected = corners_result.get("home", {}).get("home_corners_expected")
        away_corners_expected = corners_result.get("away", {}).get("away_corners_expected")

        # ====================================================
        # 9. CARDS
        # ====================================================

        cards_result = self.cards_model.synthesize_match(
            home_math["context"],
            away_math["context"],
        )

        card_total = cards_result.get("total_expected_cards")
        home_cards_expected = cards_result.get("home", {}).get("home_cards_expected")
        away_cards_expected = cards_result.get("away", {}).get("away_cards_expected")

        # ====================================================
        # 10. CONFIDENCE (LEGACY - требует доработки)
        # ====================================================

        home_profile = self.build_profile(home_team, home_history)
        away_profile = self.build_profile(away_team, away_history)

        confidence = self._confidence(
            home_profile,
            away_profile,
            probabilities,
        )

        risk = self._risk(
            confidence,
            home_profile,
            away_profile,
        )

        # ====================================================
        # 11. CONCLUSION (LEGACY)
        # ====================================================

        conclusion, factors = self._conclusion(
            home_profile,
            away_profile,
            probabilities,
            totals,
        )

        # ====================================================
        # 12. ANALYSIS MODE
        # ====================================================

        min_matches = min(len(home_history), len(away_history))

        if min_matches >= PREFERRED_MATCHES:
            analysis_mode = "Расширенный"
        elif min_matches >= EXTENDED_ANALYSIS_MATCHES:
            analysis_mode = "Базовый+"
        elif min_matches >= 2:
            analysis_mode = "Базовый"
        else:
            analysis_mode = "Экспресс"

        # ====================================================
        # 13. OUTPUT
        # ====================================================

        result = BrainPrediction(
            home_team=home_team,
            away_team=away_team,
            home_win_probability=(
                _probability(probabilities["home"])
                if probabilities["home"] is not None
                else 0.0
            ),
            draw_probability=(
                _probability(probabilities["draw"])
                if probabilities["draw"] is not None
                else 0.0
            ),
            away_win_probability=(
                _probability(probabilities["away"])
                if probabilities["away"] is not None
                else 0.0
            ),
            btts_probability=totals["btts"] if totals["btts"] is not None else 0.0,
            over25_probability=totals["over25"] if totals["over25"] is not None else 0.0,
            over35_probability=totals["over35"] if totals["over35"] is not None else 0.0,
            home_xg=home_xg,
            away_xg=away_xg,
            most_likely_score=(
                score_result.predicted_score
                if score_result.predicted_score is not None
                else "-"
            ),
            second_likely_score=(
                score_result.second_score
                if score_result.second_score is not None
                else "-"
            ),
            third_likely_score=(
                score_result.third_score
                if score_result.third_score is not None
                else "-"
            ),
            corners_expected=corner_total,
            home_corners_expected=home_corners_expected,
            away_corners_expected=away_corners_expected,
            over75_corners_probability=(
                self._over_probability(corner_total, 7.5)
                if corner_total is not None
                else None
            ),
            over85_corners_probability=(
                self._over_probability(corner_total, 8.5)
                if corner_total is not None
                else None
            ),
            over95_corners_probability=(
                self._over_probability(corner_total, 9.5)
                if corner_total is not None
                else None
            ),
            over105_corners_probability=(
                self._over_probability(corner_total, 10.5)
                if corner_total is not None
                else None
            ),
            cards_expected=card_total,
            home_cards_expected=home_cards_expected,
            away_cards_expected=away_cards_expected,
            over25_cards_probability=(
                self._over_probability(card_total, 2.5)
                if card_total is not None
                else None
            ),
            over35_cards_probability=(
                self._over_probability(card_total, 3.5)
                if card_total is not None
                else None
            ),
            over45_cards_probability=(
                self._over_probability(card_total, 4.5)
                if card_total is not None
                else None
            ),
            confidence=confidence,
            risk=risk,
            analysis_mode=analysis_mode,
            data_quality=round(
                (home_profile.data_quality + away_profile.data_quality) / 2.0,
                1,
            ),
            conclusion=conclusion,
            factors=factors,
            calculation_meta={
                "brain_version": BRAIN_VERSION,
                "home_matches": len(home_history),
                "away_matches": len(away_history),
                "home_profile": home_profile.__dict__,
                "away_profile": away_profile.__dict__,
                "home_form_result": self._json_safe(home_math["form_model"]),
                "away_form_result": self._json_safe(away_math["form_model"]),
                "home_form_win": self._json_safe(home_math["form_win"]),
                "away_form_win": self._json_safe(away_math["form_win"]),
                "home_defence": self._json_safe(home_math["defence"]),
                "away_defence": self._json_safe(away_math["defence"]),
                "home_form_control": self._json_safe(home_math["form_control"]),
                "away_form_control": self._json_safe(away_math["form_control"]),
                "home_form_anomaly": self._json_safe(home_math["form_anomaly"]),
                "away_form_anomaly": self._json_safe(away_math["form_anomaly"]),
                "home_special_form": self._json_safe(home_math["special_form"]),
                "away_special_form": self._json_safe(away_math["special_form"]),
                "goal_model": self._json_safe(goal_result),
                "probability_model": self._json_safe(probability_result),
                "score_predictor": self._json_safe(score_result),
                "corners_result": self._json_safe(corners_result),
                "cards_result": self._json_safe(cards_result),
                "method": (
                    "FormModel v1.1 + "
                    "FormWin v1.2 + "
                    "Defence v1.1 + "
                    "FormControl v1.1 + "
                    "FormAnomaly v1.0 + "
                    "SpecialForm v1.0 + "
                    "GoalModel v2.0 + "
                    "ProbabilityModel v1.1 + "
                    "ScorePredictor v2.2 + "
                    "CornersModel v1.2 + "
                    "CardsModel v1.2"
                ),
                "xg_internal": {"home": home_xg, "away": away_xg},
                "note": (
                    "FAJ-BRAIN-0.8. "
                    "GoalModel v2.0: только FormModel. "
                    "ScorePredictor v2.2: только ProbabilityModel. "
                    "Corners v1.2 и Cards v1.2 с recent3 + trend."
                ),
            },
        )

        return result.to_dict()


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def predict_match(
    home_team: str,
    away_team: str,
    home_matches: Iterable[Any],
    away_matches: Iterable[Any],
    home_form_context: Optional[Any] = None,
    away_form_context: Optional[Any] = None,
) -> Dict[str, Any]:

    brain = FAJBrain()

    return brain.predict(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_matches,
        away_matches=away_matches,
        home_form_context=home_form_context,
        away_form_context=away_form_context,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    home = [
        {
            "goals_for": 3,
            "goals_against": 0,
            "shots": 18,
            "shots_on_target": 8,
            "blocked_shots": 3,
            "big_chances": 4,
            "possession": 61,
            "passes": 520,
            "pass_accuracy": 86,
            "corners": 7,
            "yellow_cards": 1,
            "red_cards": 0,
            "fouls": 8,
            "offsides": 1,
            "xg": 2.2,
            "is_home": True,
        },
        {
            "goals_for": 2,
            "goals_against": 1,
            "shots": 15,
            "shots_on_target": 6,
            "blocked_shots": 2,
            "big_chances": 3,
            "possession": 55,
            "passes": 470,
            "pass_accuracy": 82,
            "corners": 6,
            "yellow_cards": 2,
            "red_cards": 0,
            "fouls": 10,
            "offsides": 2,
            "xg": 1.8,
            "is_home": False,
        },
        {
            "goals_for": 1,
            "goals_against": 1,
            "shots": 13,
            "shots_on_target": 5,
            "blocked_shots": 1,
            "big_chances": 2,
            "possession": 58,
            "passes": 490,
            "pass_accuracy": 84,
            "corners": 5,
            "yellow_cards": 2,
            "red_cards": 0,
            "fouls": 9,
            "offsides": 1,
            "xg": 1.4,
            "is_home": True,
        },
    ]

    away = [
        {
            "goals_for": 1,
            "goals_against": 2,
            "shots": 11,
            "shots_on_target": 4,
            "blocked_shots": 2,
            "big_chances": 1,
            "possession": 48,
            "passes": 390,
            "pass_accuracy": 77,
            "corners": 4,
            "yellow_cards": 3,
            "red_cards": 0,
            "fouls": 12,
            "offsides": 2,
            "xg": 1.1,
            "is_home": False,
        },
        {
            "goals_for": 2,
            "goals_against": 2,
            "shots": 12,
            "shots_on_target": 5,
            "blocked_shots": 3,
            "big_chances": 2,
            "possession": 52,
            "passes": 410,
            "pass_accuracy": 79,
            "corners": 5,
            "yellow_cards": 2,
            "red_cards": 0,
            "fouls": 11,
            "offsides": 1,
            "xg": 1.5,
            "is_home": True,
        },
        {
            "goals_for": 0,
            "goals_against": 1,
            "shots": 9,
            "shots_on_target": 3,
            "blocked_shots": 1,
            "big_chances": 1,
            "possession": 44,
            "passes": 350,
            "pass_accuracy": 74,
            "corners": 3,
            "yellow_cards": 4,
            "red_cards": 0,
            "fouls": 14,
            "offsides": 3,
            "xg": 0.8,
            "is_home": False,
        },
    ]

    prediction = predict_match(
        "Liverpool",
        "Nottingham Forest",
        home,
        away,
    )

    print("=" * 70)
    print("FAJ BRAIN SELF TEST")
    print("=" * 70)

    for key, value in prediction.items():
        print(f"{key}: {value}")
