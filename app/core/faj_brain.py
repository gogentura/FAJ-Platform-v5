#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Personal Prediction Brain
=============================

Новый независимый прогнозный мозг FAJ.

Назначение:
    Получить исторические данные двух команд и сформировать
    единый прогноз матча.

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

Архитектура:

    historical data
          ↓
    normalize input
          ↓
    FormContext (из faj_predictor или строится здесь)
          ↓
    FormModel (из form_model.py)
          ↓
    FormModelResult
          ↓
    GoalModel (из goal_model.py)
          ↓
    home_xg / away_xg
          ↓
    score distribution
          ↓
    result probabilities
          ↓
    BTTS / totals
          ↓
    corners (из CornersModel)
          ↓
    cards (из CardsModel)
          ↓
    confidence / risk
          ↓
    analytical conclusion

Минимальная выборка:
    1 матч — допустимо, но режим ограниченный.

    2 матча — базовый режим.

    3+ матча — расширенный анализ.

    6 матчей — предпочтительный режим.

    10+ матчей — возможно, но более старые матчи
    должны иметь меньший вес.

Источники матчей могут быть разными:
    АПЛ
    Кубок
    Лига чемпионов
    товарищеский матч
    Ла Лига
    РПЛ
    и т.д.

FAJ анализирует предоставленную выборку, а не требует,
чтобы все матчи были из одного турнира.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

# ============================================================
# FORM MODEL — новый математический слой
# ============================================================

from app.core.form_model import FormModel, FormModelResult
from app.core.brain_contract import FormContext as ContractFormContext

# ============================================================
# GOAL MODEL — синтез ожидаемых голов
# ============================================================

from app.core.goal_model import GoalModel

# ============================================================
# CORNERS MODEL — угловые
# ============================================================

from app.core.corners_model import CornersModel

# ============================================================
# CARDS MODEL — карточки
# ============================================================

from app.core.cards_model import CardsModel


# ============================================================
# VERSION
# ============================================================

BRAIN_VERSION = "FAJ-BRAIN-0.4"

MIN_MATCHES = 1
EXTENDED_ANALYSIS_MATCHES = 3
PREFERRED_MATCHES = 6
MAX_RECOMMENDED_MATCHES = 10


# ============================================================
# HELPERS
# ============================================================

def _float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Безопасное преобразование значения в float.

    None и пустые значения остаются None.
    Мы принципиально НЕ превращаем отсутствие данных в 0.
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


def _int(value: Any, default: Optional[int] = None) -> Optional[int]:
    result = _float(value)

    if result is None:
        return default

    return int(round(result))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:

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
    # Например для 6 матчей:
    # 1, 2, 3, 4, 5, 6
    #
    # где 6 — самый свежий.

    weights = list(range(1, len(clean) + 1))

    return sum(
        value * weight
        for value, weight in zip(clean, weights)
    ) / sum(weights)


def _probability(value: float) -> float:
    return round(_clamp(value) * 100.0, 1)


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

    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        team: Optional[str] = None,
    ) -> "HistoricalMatch":

        # ----------------------------------------------------
        # Извлекаем xG из вложенной структуры
        # ----------------------------------------------------
        xg_value = _float(data.get("xg"))
        if xg_value is None:
            xg_dict = data.get("xg", {})
            if isinstance(xg_dict, dict):
                if team:
                    # Определяем сторону команды
                    home_team = data.get("home_team")
                    if home_team and team == home_team:
                        xg_value = _float(xg_dict.get("home"))
                    else:
                        xg_value = _float(xg_dict.get("away"))

        # ----------------------------------------------------
        # Извлекаем corners из вложенной структуры
        # ----------------------------------------------------
        corners_value = _float(data.get("corners"))
        opponent_corners_value = None

        if corners_value is None:
            corners_dict = data.get("corners", {})
            if isinstance(corners_dict, dict):
                home_team = data.get("home_team")
                if home_team and team == home_team:
                    corners_value = _float(corners_dict.get("home"))
                    opponent_corners_value = _float(corners_dict.get("away"))
                else:
                    corners_value = _float(corners_dict.get("away"))
                    opponent_corners_value = _float(corners_dict.get("home"))

        # ----------------------------------------------------
        # Извлекаем cards из вложенной структуры
        # ----------------------------------------------------
        yellow_cards_value = _float(data.get("yellow_cards"))
        opponent_yellow_cards_value = None

        if yellow_cards_value is None:
            cards_dict = data.get("cards", {})
            if isinstance(cards_dict, dict):
                home_team = data.get("home_team")
                if home_team and team == home_team:
                    yellow_cards_value = _float(cards_dict.get("home"))
                    opponent_yellow_cards_value = _float(cards_dict.get("away"))
                else:
                    yellow_cards_value = _float(cards_dict.get("away"))
                    opponent_yellow_cards_value = _float(cards_dict.get("home"))

        # Собираем extra с opponent значениями
        extra = data.get("extra", {})
        if opponent_corners_value is not None:
            extra["opponent_corners"] = opponent_corners_value
        if opponent_yellow_cards_value is not None:
            extra["opponent_yellow_cards"] = opponent_yellow_cards_value

        return cls(

            team=(
                team
                or data.get("team")
                or data.get("team_name")
                or ""
            ),

            opponent=(
                data.get("opponent")
                or data.get("opponent_name")
            ),

            is_home=data.get("is_home"),

            goals_for=_float(
                data.get("goals_for", data.get("goals"))
            ),

            goals_against=_float(
                data.get("goals_against")
            ),

            shots=_float(data.get("shots")),

            shots_on_target=_float(
                data.get("shots_on_target")
            ),

            possession=_float(
                data.get("possession")
            ),

            corners=corners_value,

            yellow_cards=yellow_cards_value,

            red_cards=_float(data.get("red_cards")),

            xg=xg_value,

            big_chances=_float(
                data.get("big_chances")
            ),

            competition=data.get("competition"),

            match_date=data.get("match_date"),

            extra=extra,
        )


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

    factors: List[str] = field(default_factory=list)

    calculation_meta: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "brain_version": BRAIN_VERSION,

            "home_team": self.home_team,
            "away_team": self.away_team,

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

            "home_xg": self.home_xg,
            "away_xg": self.away_xg,

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

            "confidence": self.confidence,
            "risk": self.risk,

            "analysis_mode": self.analysis_mode,
            "data_quality": self.data_quality,

            "conclusion": self.conclusion,

            "factors": self.factors,

            "calculation_meta":
                self.calculation_meta,
        }


# ============================================================
# POISSON
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

    for home_goals in range(max_goals + 1):

        home_probability = poisson_probability(
            home_goals,
            home_xg,
        )

        for away_goals in range(max_goals + 1):

            away_probability = poisson_probability(
                away_goals,
                away_xg,
            )

            probability = (
                home_probability
                * away_probability
            )

            scores.append({
                "home": home_goals,
                "away": away_goals,
                "probability": probability,
            })

    scores.sort(
        key=lambda item: item["probability"],
        reverse=True,
    )

    return scores


# ============================================================
# TEAM ANALYSIS
# ============================================================

class FAJBrain:

    """
    Новый основной математический мозг FAJ.

    Использование:

        brain = FAJBrain()

        prediction = brain.predict(
            home_team="Liverpool",
            away_team="Nottingham Forest",
            home_matches=[...],
            away_matches=[...],
        )

    Данные могут быть:
        HistoricalMatch
        dict
    """

    def __init__(self):

        self.version = BRAIN_VERSION

        # ========================================================
        # FormModel — математический слой формы
        # ========================================================

        self.form_model = FormModel()

        # ========================================================
        # GoalModel — синтез ожидаемых голов
        # ========================================================

        self.goal_model = GoalModel()

        # ========================================================
        # CornersModel — угловые
        # ========================================================

        self.corners_model = CornersModel()

        # ========================================================
        # CardsModel — карточки
        # ========================================================

        self.cards_model = CardsModel()

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize_matches(
        self,
        matches: Iterable[Any],
        team_name: str,
    ) -> List[HistoricalMatch]:

        result = []

        for match in matches or []:

            if isinstance(match, HistoricalMatch):

                result.append(match)

            elif isinstance(match, dict):

                result.append(
                    HistoricalMatch.from_dict(
                        match,
                        team=team_name,
                    )
                )

        return result

    # ========================================================
    # BUILD FORM CONTEXT (for FormModel)
    # ========================================================

    def _build_form_context_for_model(
        self,
        team_name: str,
        matches: List[HistoricalMatch],
    ) -> Dict[str, Any]:
        """
        Строит FormContext в формате, ожидаемом FormModel.
        Использует уже существующий build_form_context из form_context.py
        """

        from app.core.form_context import build_form_context

        # Преобразуем HistoricalMatch в dict, который понимает build_form_context
        records = []
        for match in matches:
            # Определяем домашнюю и гостевую команду
            if match.is_home:
                home_team = match.team
                away_team = match.opponent or ""
                home_goals = match.goals_for
                away_goals = match.goals_against
                home_corners = match.corners
                away_corners = match.extra.get("opponent_corners")
                home_cards = match.yellow_cards
                away_cards = match.extra.get("opponent_yellow_cards")
            else:
                home_team = match.opponent or ""
                away_team = match.team
                home_goals = match.goals_against
                away_goals = match.goals_for
                home_corners = match.extra.get("opponent_corners")
                away_corners = match.corners
                home_cards = match.extra.get("opponent_yellow_cards")
                away_cards = match.yellow_cards

            record = {
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "xg": {
                    "home": match.xg if match.is_home else None,
                    "away": match.xg if not match.is_home else None,
                },
                "home_corners": home_corners,
                "away_corners": away_corners,
                "home_yellow_cards": home_cards,
                "away_yellow_cards": away_cards,
                "match_date": match.match_date,
                "is_home": match.is_home,
                "opponent": match.opponent,
            }
            records.append(record)

        # Передаём records в правильном порядке (старый → новый)
        return build_form_context(
            team_name=team_name,
            records=records,
            limit=PREFERRED_MATCHES,
        )

    # ========================================================
    # OLD PROFILE — сохраняется для совместимости
    # ========================================================

    def build_profile(
        self,
        team_name: str,
        matches: Iterable[Any],
    ) -> TeamProfile:

        normalized = self._normalize_matches(
            matches,
            team_name,
        )

        count = len(normalized)

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

        goals_for = _weighted_mean(
            match.goals_for
            for match in normalized
        )

        goals_against = _weighted_mean(
            match.goals_against
            for match in normalized
        )

        corners = _weighted_mean(
            match.corners
            for match in normalized
        )

        cards = _weighted_mean(
            (
                (
                    match.yellow_cards or 0.0
                )
                +
                (
                    match.red_cards or 0.0
                )
            )
            if (
                match.yellow_cards is not None
                or match.red_cards is not None
            )
            else None
            for match in normalized
        )

        shots = _weighted_mean(
            match.shots
            for match in normalized
        )

        shots_on_target = _weighted_mean(
            match.shots_on_target
            for match in normalized
        )

        xg = _weighted_mean(
            match.xg
            for match in normalized
        )

        # ----------------------------------------------------
        # ATTACK
        # ----------------------------------------------------

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
            _mean(attack_components)
            if attack_components
            else 1.0
        )

        # ----------------------------------------------------
        # DEFENCE
        # ----------------------------------------------------

        if goals_against is not None:

            defence = 1.0 / (
                1.0
                + max(0.0, goals_against)
            )

        else:

            defence = 0.5

        # ----------------------------------------------------
        # HOME / AWAY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # FORM
        # ----------------------------------------------------

        points = []

        for match in normalized:

            if match.goals_for is None:
                continue

            if match.goals_against is None:
                continue

            if match.goals_for > match.goals_against:
                points.append(3)

            elif match.goals_for == match.goals_against:
                points.append(1)

            else:
                points.append(0)

        form_points = (
            _weighted_mean(points)
            if points
            else None
        )

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        quality = self._calculate_data_quality(
            normalized
        )

        return TeamProfile(

            name=team_name,

            matches=count,

            goals_for=goals_for,
            goals_against=goals_against,

            attack=float(attack or 1.0),
            defence=float(defence),

            home_attack=home_attack,
            away_attack=away_attack,

            corners=corners,
            cards=cards,

            shots=shots,
            shots_on_target=shots_on_target,

            xg=xg,

            form_points=form_points,

            data_quality=quality,
        )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    def _calculate_data_quality(
        self,
        matches: List[HistoricalMatch],
    ) -> float:

        if not matches:
            return 0.0

        count_factor = min(
            len(matches) / PREFERRED_MATCHES,
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
        total = len(matches) * len(fields)

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
    # EXPECTED GOALS — ИСПОЛЬЗУЕТ GOALMODEL
    # ========================================================

    def _calculate_expected_goals(
        self,
        home_form_result: Any,
        away_form_result: Any,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Рассчитывает ожидаемые голы через GoalModel.

        GoalModel синтезирует:
            Home xG = (home_xg_avg + away_xga_avg) / 2
            Away xG = (away_xg_avg + home_xga_avg) / 2

        Если xG или xGA отсутствует — результат None.
        """
        # Вызываем GoalModel с FormModelResult
        goal_result = self.goal_model.analyze(
            home_form=home_form_result,
            away_form=away_form_result,
        )

        return goal_result.home_xg, goal_result.away_xg

    # ========================================================
    # RESULT PROBABILITIES
    # ========================================================

    def _result_probabilities(
        self,
        home_xg: float,
        away_xg: float,
    ) -> Dict[str, float]:

        distribution = score_distribution(
            home_xg,
            away_xg,
        )

        home_win = 0.0
        draw = 0.0
        away_win = 0.0

        for score in distribution:

            if score["home"] > score["away"]:

                home_win += score["probability"]

            elif score["home"] == score["away"]:

                draw += score["probability"]

            else:

                away_win += score["probability"]

        total = (
            home_win
            + draw
            + away_win
        )

        if total <= 0:

            return {
                "home": 1 / 3,
                "draw": 1 / 3,
                "away": 1 / 3,
            }

        return {
            "home": home_win / total,
            "draw": draw / total,
            "away": away_win / total,
        }

    # ========================================================
    # TOTALS
    # ========================================================

    def _totals(
        self,
        home_xg: float,
        away_xg: float,
    ) -> Dict[str, float]:

        distribution = score_distribution(
            home_xg,
            away_xg,
        )

        btts = 0.0

        over25 = 0.0
        over35 = 0.0

        for score in distribution:

            home = score["home"]
            away = score["away"]

            probability = score["probability"]

            if home >= 1 and away >= 1:
                btts += probability

            if home + away >= 3:
                over25 += probability

            if home + away >= 4:
                over35 += probability

        return {
            "btts": _probability(btts),
            "over25": _probability(over25),
            "over35": _probability(over35),
        }

    # ========================================================
    # CORNERS — УДАЛЕНО (используем CornersModel)
    # ========================================================

    # ========================================================
    # CARDS — УДАЛЕНО (используем CardsModel)
    # ========================================================

    # ========================================================
    # SIMPLE POISSON TOTAL
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

            if goals <= math.floor(line):

                probability_under += (
                    poisson_probability(
                        goals,
                        expected,
                    )
                )

        return round(
            _clamp(
                1.0 - probability_under
            ) * 100.0,
            1,
        )

    # ========================================================
    # CONFIDENCE
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

        separation_score = _clamp(
            separation / 0.45
        ) * 100.0

        confidence = (
            0.55 * quality
            + 0.45 * separation_score
        )

        return round(
            _clamp(
                confidence / 100.0
            ) * 100.0,
            1,
        )

    # ========================================================
    # RISK
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
    # CONCLUSION
    # ========================================================

    def _conclusion(
        self,
        home: TeamProfile,
        away: TeamProfile,
        probabilities: Dict[str, float],
        totals: Dict[str, float],
    ) -> tuple[str, List[str]]:

        factors = []

        if probabilities["home"] >= max(
            probabilities["draw"],
            probabilities["away"],
        ):

            winner_text = (
                f"преимущество {home.name}"
            )

            factors.append(
                "Модель видит преимущество хозяев."
            )

        elif probabilities["away"] >= max(
            probabilities["home"],
            probabilities["draw"],
        ):

            winner_text = (
                f"преимущество {away.name}"
            )

            factors.append(
                "Модель видит преимущество гостей."
            )

        else:

            winner_text = "равновесие сил"

            factors.append(
                "Модель не видит явного фаворита."
            )

        if totals["btts"] >= 60:

            factors.append(
                "Вероятность обмена голами повышена."
            )

        elif totals["btts"] <= 40:

            factors.append(
                "Модель не ожидает высокой вероятности "
                "обмена голами."
            )

        if totals["over25"] >= 60:

            factors.append(
                "Сценарий с 3+ голами выглядит вероятным."
            )

        elif totals["over25"] <= 40:

            factors.append(
                "Модель скорее склоняется к умеренной "
                "результативности."
            )

        conclusion = (
            f"FAJ: {winner_text}. "
            f"{' '.join(factors)}"
        )

        return conclusion, factors

    # ========================================================
    # JSON SAFE HELPER
    # ========================================================

    def _json_safe(self, value: Any) -> Any:
        """
        Рекурсивно преобразует объекты в JSON-безопасный вид.
        """
        if value is None:
            return None

        if hasattr(value, "to_dict"):
            return self._json_safe(value.to_dict())

        if hasattr(value, "__dataclass_fields__"):
            return {
                key: self._json_safe(item)
                for key, item in asdict(value).items()
            }

        if isinstance(value, dict):
            return {
                key: self._json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                self._json_safe(item)
                for item in value
            ]

        if isinstance(value, (str, int, float, bool)):
            return value

        return str(value)

    # ========================================================
    # PUBLIC PREDICTION — ОБНОВЛЁННАЯ ВЕРСИЯ
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

        home_history = self._normalize_matches(
            home_matches,
            home_team,
        )

        away_history = self._normalize_matches(
            away_matches,
            away_team,
        )

        if not home_history:
            raise ValueError(
                f"Нет исторических данных для "
                f"{home_team}."
            )

        if not away_history:
            raise ValueError(
                f"Нет исторических данных для "
                f"{away_team}."
            )

        # ========================================================
        # 1. Строим FormContext для FormModel
        #    Используем переданные контексты, если они есть
        # ========================================================

        if home_form_context is not None:
            home_form_context_data = home_form_context
        else:
            home_form_context_data = self._build_form_context_for_model(
                home_team,
                home_history,
            )

        if away_form_context is not None:
            away_form_context_data = away_form_context
        else:
            away_form_context_data = self._build_form_context_for_model(
                away_team,
                away_history,
            )

        # ========================================================
        # 2. Запускаем FormModel
        # ========================================================

        home_form_result = self.form_model.analyze(home_form_context_data)
        away_form_result = self.form_model.analyze(away_form_context_data)

        # ========================================================
        # 3. Строим старые профили для совместимости (только для confidence)
        # ========================================================

        home_profile = self.build_profile(
            home_team,
            home_history,
        )

        away_profile = self.build_profile(
            away_team,
            away_history,
        )

        # ========================================================
        # 4. ANALYSIS MODE
        # ========================================================

        min_matches = min(
            len(home_history),
            len(away_history),
        )

        if min_matches >= PREFERRED_MATCHES:
            analysis_mode = "Расширенный"
        elif min_matches >= EXTENDED_ANALYSIS_MATCHES:
            analysis_mode = "Базовый+"
        elif min_matches >= 2:
            analysis_mode = "Базовый"
        else:
            analysis_mode = "Экспресс"

        # ========================================================
        # 5. XG — через GoalModel
        # ========================================================

        home_xg, away_xg = self._calculate_expected_goals(
            home_form_result,
            away_form_result,
        )

        # ========================================================
        # 6. ЗАЩИТА ОТ NONE
        # ========================================================

        if home_xg is None or away_xg is None:
            raise ValueError(
                "GoalModel не смог рассчитать xG: "
                "для одной или обеих команд отсутствует "
                "необходимый xG/xGA компонент в FormModelResult."
            )

        # ========================================================
        # 7. RESULT
        # ========================================================

        probabilities = (
            self._result_probabilities(
                home_xg,
                away_xg,
            )
        )

        totals = self._totals(
            home_xg,
            away_xg,
        )

        # ========================================================
        # 8. SCORE
        # ========================================================

        scores = score_distribution(
            home_xg,
            away_xg,
        )

        top_scores = scores[:3]

        score_strings = [
            f"{item['home']}:{item['away']}"
            for item in top_scores
        ]

        while len(score_strings) < 3:
            score_strings.append("-")

        # ========================================================
        # 9. CORNERS — через CornersModel
        # ========================================================

        corners_result = self.corners_model.synthesize_match(
            home_form_context_data,
            away_form_context_data,
        )

        corner_total = corners_result.get("total_expected_corners")
        home_corners_expected = corners_result.get("home", {}).get("home_corners_expected")
        away_corners_expected = corners_result.get("away", {}).get("away_corners_expected")

        # ========================================================
        # 10. CARDS — через CardsModel
        # ========================================================

        cards_result = self.cards_model.synthesize_match(
            home_form_context_data,
            away_form_context_data,
        )

        card_total = cards_result.get("total_expected_cards")
        home_cards_expected = cards_result.get("home", {}).get("home_cards_expected")
        away_cards_expected = cards_result.get("away", {}).get("away_cards_expected")

        # ========================================================
        # 11. CONFIDENCE
        # ========================================================

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

        # ========================================================
        # 12. CONCLUSION
        # ========================================================

        conclusion, factors = (
            self._conclusion(
                home_profile,
                away_profile,
                probabilities,
                totals,
            )
        )

        # ========================================================
        # 13. OUTPUT
        # ========================================================

        result = BrainPrediction(

            home_team=home_team,
            away_team=away_team,

            home_win_probability=_probability(
                probabilities["home"]
            ),

            draw_probability=_probability(
                probabilities["draw"]
            ),

            away_win_probability=_probability(
                probabilities["away"]
            ),

            btts_probability=totals["btts"],

            over25_probability=totals["over25"],

            over35_probability=totals["over35"],

            home_xg=home_xg,
            away_xg=away_xg,

            most_likely_score=score_strings[0],

            second_likely_score=score_strings[1],

            third_likely_score=score_strings[2],

            corners_expected=corner_total,

            home_corners_expected=home_corners_expected,

            away_corners_expected=away_corners_expected,

            over75_corners_probability=(
                self._over_probability(
                    corner_total,
                    7.5,
                )
                if corner_total is not None
                else None
            ),

            over85_corners_probability=(
                self._over_probability(
                    corner_total,
                    8.5,
                )
                if corner_total is not None
                else None
            ),

            over95_corners_probability=(
                self._over_probability(
                    corner_total,
                    9.5,
                )
                if corner_total is not None
                else None
            ),

            over105_corners_probability=(
                self._over_probability(
                    corner_total,
                    10.5,
                )
                if corner_total is not None
                else None
            ),

            cards_expected=card_total,

            home_cards_expected=home_cards_expected,

            away_cards_expected=away_cards_expected,

            over25_cards_probability=(
                self._over_probability(
                    card_total,
                    2.5,
                )
                if card_total is not None
                else None
            ),

            over35_cards_probability=(
                self._over_probability(
                    card_total,
                    3.5,
                )
                if card_total is not None
                else None
            ),

            over45_cards_probability=(
                self._over_probability(
                    card_total,
                    4.5,
                )
                if card_total is not None
                else None
            ),

            confidence=confidence,

            risk=risk,

            analysis_mode=analysis_mode,

            data_quality=round(
                (
                    home_profile.data_quality
                    + away_profile.data_quality
                ) / 2.0,
                1,
            ),

            conclusion=conclusion,

            factors=factors,

            calculation_meta={

                "brain_version": BRAIN_VERSION,

                "home_matches":
                    len(home_history),

                "away_matches":
                    len(away_history),

                "home_profile":
                    home_profile.__dict__,

                "away_profile":
                    away_profile.__dict__,

                "home_form_result":
                    self._json_safe(home_form_result),

                "away_form_result":
                    self._json_safe(away_form_result),

                "corners_result":
                    self._json_safe(corners_result),

                "cards_result":
                    self._json_safe(cards_result),

                "method":
                    "FormModel v1.0 + "
                    "GoalModel v1.0 + "
                    "CornersModel v1.0 + "
                    "CardsModel v1.0 + "
                    "poisson_score_distribution",

                "xg_internal":
                    {
                        "home": home_xg,
                        "away": away_xg,
                    },

                "note":
                    "Версия 0.4. CornersModel и CardsModel подключены. "
                    "Угловые и карточки рассчитываются через отдельные модели. "
                    "Никакого влияния на xG.",
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
            "corners": 7,
            "yellow_cards": 1,
            "xg": 2.2,
            "is_home": True,
        },
        {
            "goals_for": 2,
            "goals_against": 1,
            "shots": 15,
            "shots_on_target": 6,
            "corners": 6,
            "yellow_cards": 2,
            "xg": 1.8,
            "is_home": False,
        },
        {
            "goals_for": 1,
            "goals_against": 1,
            "shots": 13,
            "shots_on_target": 5,
            "corners": 5,
            "yellow_cards": 2,
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
            "corners": 4,
            "yellow_cards": 3,
            "xg": 1.1,
            "is_home": False,
        },
        {
            "goals_for": 2,
            "goals_against": 2,
            "shots": 12,
            "shots_on_target": 5,
            "corners": 5,
            "yellow_cards": 2,
            "xg": 1.5,
            "is_home": True,
        },
        {
            "goals_for": 0,
            "goals_against": 1,
            "shots": 9,
            "shots_on_target": 3,
            "corners": 3,
            "yellow_cards": 4,
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

        print(
            f"{key}: {value}"
        )
