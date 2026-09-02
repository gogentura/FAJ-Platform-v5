#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Brain — Form Model

Вычислительная модель текущей формы команды.

Архитектурная роль:
    history records
        ↓
    form_context
        ↓
    FormModel
        ↓
    числовая характеристика формы
        ↓
    Goal Model / Brain

ВАЖНО:
- не собирает данные;
- не обращается к Soccer365;
- не работает с БД;
- не изменяет records;
- не принимает решения о прогнозе самостоятельно;
- не обучается;
- не изменяет параметры FAJ.

Модель является чистым вычислительным слоем.

Все коэффициенты вынесены в FORM_MODEL_CONFIG,
чтобы позднее их можно было заменить результатами
отдельного математического тестирования.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# CONFIGURATION
# ============================================================

FORM_MODEL_CONFIG: Dict[str, float] = {

    # Результат матча
    "win_weight": 1.00,
    "draw_weight": 0.50,
    "loss_weight": 0.00,

    # Свежесть результата.
    # Первый матч получает максимальный вес.
    "recency_decay": 0.90,

    # Влияние сложности соперника.
    "easy_match_factor": 0.90,
    "medium_match_factor": 1.00,
    "hard_match_factor": 1.10,
    "very_hard_match_factor": 1.15,

    # Домашний / гостевой контекст.
    "home_weight": 1.00,
    "away_weight": 1.00,

    # xG / xGA пока используются как отдельные показатели.
    "xg_weight": 1.00,
    "xga_weight": 1.00,
}


# ============================================================
# RESULT
# ============================================================

@dataclass(frozen=True)
class FormModelResult:
    """
    Результат вычисления формы.

    Все значения должны быть пригодны для передачи
    следующим моделям FAJ Brain.
    """

    form_score: float

    attack_strength: Optional[float]

    defense_strength: Optional[float]

    xg_average: Optional[float]

    xga_average: Optional[float]

    goals_average: Optional[float]

    conceded_average: Optional[float]

    home_form_score: Optional[float]

    away_form_score: Optional[float]

    trend: str

    consistency: float

    matches_count: int

    weighted_points: float

    difficulty_score: Optional[float]

    signals: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует результат в обычный dict."""

        return {
            "form_score": self.form_score,
            "attack_strength": self.attack_strength,
            "defense_strength": self.defense_strength,
            "xg_average": self.xg_average,
            "xga_average": self.xga_average,
            "goals_average": self.goals_average,
            "conceded_average": self.conceded_average,
            "home_form_score": self.home_form_score,
            "away_form_score": self.away_form_score,
            "trend": self.trend,
            "consistency": self.consistency,
            "matches_count": self.matches_count,
            "weighted_points": self.weighted_points,
            "difficulty_score": self.difficulty_score,
            "signals": list(self.signals),
        }


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
) -> Optional[float]:
    """Безопасное преобразование значения в float."""

    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _safe_int(
    value: Any,
) -> Optional[int]:
    """Безопасное преобразование значения в int."""

    if value is None:
        return None

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _extract_result(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[str]:
    """
    Определяет результат команды.

    Использует home_team / away_team и home_goals / away_goals.

    Возможные значения:
        W
        D
        L
    """

    home = record.get("home_team")
    away = record.get("away_team")

    home_goals = _safe_int(
        record.get("home_goals")
    )
    away_goals = _safe_int(
        record.get("away_goals")
    )

    if (
        home_goals is None
        or away_goals is None
    ):
        return None

    if team_name == home:

        if home_goals > away_goals:
            return "W"

        if home_goals < away_goals:
            return "L"

        return "D"

    if team_name == away:

        if away_goals > home_goals:
            return "W"

        if away_goals < home_goals:
            return "L"

        return "D"

    return None


def _extract_xg(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[float]:
    """Получает xG команды из record."""

    xg = record.get("xg")

    if not isinstance(xg, dict):
        return None

    if record.get("home_team") == team_name:
        return _safe_float(
            xg.get("home")
        )

    if record.get("away_team") == team_name:
        return _safe_float(
            xg.get("away")
        )

    return None


def _extract_xga(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[float]:
    """Получает xGA команды."""

    xg = record.get("xg")

    if not isinstance(xg, dict):
        return None

    if record.get("home_team") == team_name:
        return _safe_float(
            xg.get("away")
        )

    if record.get("away_team") == team_name:
        return _safe_float(
            xg.get("home")
        )

    return None


def _extract_goals(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[int]:
    """Получает забитые голы команды."""

    home_goals = _safe_int(
        record.get("home_goals")
    )

    away_goals = _safe_int(
        record.get("away_goals")
    )

    if (
        home_goals is None
        or away_goals is None
    ):
        return None

    if record.get("home_team") == team_name:
        return home_goals

    if record.get("away_team") == team_name:
        return away_goals

    return None


def _extract_conceded(
    record: Dict[str, Any],
    team_name: str,
) -> Optional[int]:
    """Получает пропущенные голы команды."""

    home_goals = _safe_int(
        record.get("home_goals")
    )

    away_goals = _safe_int(
        record.get("away_goals")
    )

    if (
        home_goals is None
        or away_goals is None
    ):
        return None

    if record.get("home_team") == team_name:
        return away_goals

    if record.get("away_team") == team_name:
        return home_goals

    return None


def _difficulty_factor(
    difficulty: Optional[str],
) -> float:
    """
    Возвращает коэффициент сложности.

    Пока это НЕ финальная математическая формула.
    Значения являются стартовыми параметрами для тестирования.
    """

    if not difficulty:
        return 1.00

    value = str(
        difficulty
    ).strip().lower()

    if value == "лёгкий":
        return FORM_MODEL_CONFIG[
            "easy_match_factor"
        ]

    if value == "легкий":
        return FORM_MODEL_CONFIG[
            "easy_match_factor"
        ]

    if value == "средний":
        return FORM_MODEL_CONFIG[
            "medium_match_factor"
        ]

    if value == "тяжёлый":
        return FORM_MODEL_CONFIG[
            "hard_match_factor"
        ]

    if value == "тяжелый":
        return FORM_MODEL_CONFIG[
            "hard_match_factor"
        ]

    if value in (
        "очень тяжёлый",
        "очень тяжелый",
    ):
        return FORM_MODEL_CONFIG[
            "very_hard_match_factor"
        ]

    return 1.00


# ============================================================
# FORM MODEL
# ============================================================

class FormModel:
    """
    Модель формы FAJ Brain.

    Это детерминированный вычислительный модуль.

    Один и тот же вход должен давать один и тот же результат.
    """

    def __init__(
        self,
        config: Optional[
            Dict[str, float]
        ] = None,
    ) -> None:

        self.config = dict(
            FORM_MODEL_CONFIG
        )

        if config:
            self.config.update(
                config
            )

    # ========================================================
    # PUBLIC
    # ========================================================

    def analyze(
        self,
        records: List[
            Dict[str, Any]
        ],
        team_name: str,
        form_context: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует текущую форму команды.

        records:
            последние матчи команды.

        team_name:
            название команды.

        form_context:
            существующий контекст формы.

        Возвращает обычный dict,
        чтобы его было удобно передавать Brain.
        """

        if not records:
            return FormModelResult(
                form_score=0.50,
                attack_strength=None,
                defense_strength=None,
                xg_average=None,
                xga_average=None,
                goals_average=None,
                conceded_average=None,
                home_form_score=None,
                away_form_score=None,
                trend="unknown",
                consistency=0.0,
                matches_count=0,
                weighted_points=0.0,
                difficulty_score=None,
                signals=[],
            ).to_dict()

        matches = list(
            records
        )

        results: List[
            Optional[str]
        ] = []

        points: List[
            float
        ] = []

        xg_values: List[
            float
        ] = []

        xga_values: List[
            float
        ] = []

        goals_values: List[
            float
        ] = []

        conceded_values: List[
            float
        ] = []

        home_points: List[
            float
        ] = []

        away_points: List[
            float
        ] = []

        difficulty_values: List[
            float
        ] = []

        # ----------------------------------------------------
        # MATCH PROCESSING
        # ----------------------------------------------------

        for position, record in enumerate(
            matches
        ):

            result = _extract_result(
                record,
                team_name,
            )

            results.append(
                result
            )

            if result == "W":
                base_points = self.config[
                    "win_weight"
                ]

            elif result == "D":
                base_points = self.config[
                    "draw_weight"
                ]

            elif result == "L":
                base_points = self.config[
                    "loss_weight"
                ]

            else:
                continue

            # Новейший матч имеет максимальный вес.
            recency_weight = (
                self.config[
                    "recency_decay"
                ]
                ** position
            )

            difficulty = (
                record.get(
                    "difficulty"
                )
            )

            difficulty_factor = (
                _difficulty_factor(
                    difficulty
                )
            )

            weighted = (
                base_points
                * recency_weight
                * difficulty_factor
            )

            points.append(
                weighted
            )

            difficulty_values.append(
                difficulty_factor
            )

            # ------------------------------------------------
            # HOME / AWAY
            # ------------------------------------------------

            if record.get(
                "home_team"
            ) == team_name:

                home_points.append(
                    weighted
                )

            elif record.get(
                "away_team"
            ) == team_name:

                away_points.append(
                    weighted
                )

            # ------------------------------------------------
            # XG
            # ------------------------------------------------

            xg = _extract_xg(
                record,
                team_name,
            )

            if xg is not None:
                xg_values.append(
                    xg
                )

            xga = _extract_xga(
                record,
                team_name,
            )

            if xga is not None:
                xga_values.append(
                    xga
                )

            # ------------------------------------------------
            # GOALS
            # ------------------------------------------------

            goals = _extract_goals(
                record,
                team_name,
            )

            if goals is not None:
                goals_values.append(
                    float(goals)
                )

            conceded = _extract_conceded(
                record,
                team_name,
            )

            if conceded is not None:
                conceded_values.append(
                    float(conceded)
                )

        # ====================================================
        # FORM SCORE
        # ====================================================

        if points:

            total_possible = 0.0

            for position, result in enumerate(
                results
            ):

                if result is None:
                    continue

                recency_weight = (
                    self.config[
                        "recency_decay"
                    ]
                    ** position
                )

                difficulty = _difficulty_factor(
                    matches[position].get(
                        "difficulty"
                    )
                )

                total_possible += (
                    self.config[
                        "win_weight"
                    ]
                    * recency_weight
                    * difficulty
                )

            if total_possible > 0:

                form_score = (
                    sum(points)
                    / total_possible
                )

            else:
                form_score = 0.50

        else:
            form_score = 0.50

        form_score = max(
            0.0,
            min(
                1.0,
                form_score,
            ),
        )

        # ====================================================
        # AVERAGES
        # ====================================================

        xg_average = (
            sum(xg_values)
            / len(xg_values)
            if xg_values
            else None
        )

        xga_average = (
            sum(xga_values)
            / len(xga_values)
            if xga_values
            else None
        )

        goals_average = (
            sum(goals_values)
            / len(goals_values)
            if goals_values
            else None
        )

        conceded_average = (
            sum(conceded_values)
            / len(conceded_values)
            if conceded_values
            else None
        )

        # ====================================================
        # ATTACK / DEFENSE
        # ====================================================

        attack_strength = (
            xg_average
            if xg_average is not None
            else goals_average
        )

        defense_strength = None

        if xga_average is not None:
            defense_strength = max(
                0.0,
                1.0
                - min(
                    xga_average / 3.0,
                    1.0,
                ),
            )

        elif conceded_average is not None:
            defense_strength = max(
                0.0,
                1.0
                - min(
                    conceded_average / 3.0,
                    1.0,
                ),
            )

        # ====================================================
        # HOME / AWAY FORM
        # ====================================================

        home_form_score = None

        if home_points:

            home_form_score = max(
                0.0,
                min(
                    1.0,
                    sum(home_points)
                    / sum(
                        home_points
                    )
                    if sum(home_points) > 0
                    else 0.50,
                ),
            )

        away_form_score = None

        if away_points:

            away_form_score = max(
                0.0,
                min(
                    1.0,
                    sum(away_points)
                    / sum(
                        away_points
                    )
                    if sum(away_points) > 0
                    else 0.50,
                ),
            )

        # ====================================================
        # TREND
        # ====================================================

        trend = self._calculate_trend(
            results
        )

        # ====================================================
        # CONSISTENCY
        # ====================================================

        consistency = self._calculate_consistency(
            results
        )

        # ====================================================
        # DIFFICULTY
        # ====================================================

        difficulty_score = None

        if difficulty_values:

            difficulty_score = (
                sum(
                    difficulty_values
                )
                / len(
                    difficulty_values
                )
            )

        # ====================================================
        # SIGNALS
        # ====================================================

        signals = self._build_signals(
            results=results,
            xg_average=xg_average,
            xga_average=xga_average,
            goals_average=goals_average,
            conceded_average=conceded_average,
        )

        # ====================================================
        # RESULT
        # ====================================================

        return FormModelResult(
            form_score=round(
                form_score,
                4,
            ),
            attack_strength=(
                round(
                    attack_strength,
                    4,
                )
                if attack_strength is not None
                else None
            ),
            defense_strength=(
                round(
                    defense_strength,
                    4,
                )
                if defense_strength is not None
                else None
            ),
            xg_average=(
                round(
                    xg_average,
                    4,
                )
                if xg_average is not None
                else None
            ),
            xga_average=(
                round(
                    xga_average,
                    4,
                )
                if xga_average is not None
                else None
            ),
            goals_average=(
                round(
                    goals_average,
                    4,
                )
                if goals_average is not None
                else None
            ),
            conceded_average=(
                round(
                    conceded_average,
                    4,
                )
                if conceded_average is not None
                else None
            ),
            home_form_score=home_form_score,
            away_form_score=away_form_score,
            trend=trend,
            consistency=round(
                consistency,
                4,
            ),
            matches_count=len(
                matches
            ),
            weighted_points=round(
                sum(points),
                4,
            ),
            difficulty_score=(
                round(
                    difficulty_score,
                    4,
                )
                if difficulty_score is not None
                else None
            ),
            signals=signals,
        ).to_dict()

    # ========================================================
    # TREND
    # ========================================================

    @staticmethod
    def _calculate_trend(
        results: List[
            Optional[str]
        ],
    ) -> str:
        """
        Определяет направление формы.

        Сравнивает первую половину истории
        со второй.

        records должны идти:
            новый → старый
        """

        valid = [
            result
            for result in results
            if result is not None
        ]

        if len(valid) < 4:
            return "stable"

        midpoint = len(valid) // 2

        recent = valid[
            :midpoint
        ]

        older = valid[
            midpoint:
        ]

        points_map = {
            "W": 1.0,
            "D": 0.5,
            "L": 0.0,
        }

        recent_score = (
            sum(
                points_map[result]
                for result in recent
            )
            / len(recent)
        )

        older_score = (
            sum(
                points_map[result]
                for result in older
            )
            / len(older)
        )

        difference = (
            recent_score
            - older_score
        )

        if difference > 0.15:
            return "improving"

        if difference < -0.15:
            return "declining"

        return "stable"

    # ========================================================
    # CONSISTENCY
    # ========================================================

    @staticmethod
    def _calculate_consistency(
        results: List[
            Optional[str]
        ],
    ) -> float:
        """
        Оценивает стабильность результатов.

        1.0 = очень стабильная форма
        0.0 = очень нестабильная
        """

        valid = [
            result
            for result in results
            if result is not None
        ]

        if len(valid) < 2:
            return 1.0

        transitions = 0

        for previous, current in zip(
            valid,
            valid[1:],
        ):

            if previous != current:
                transitions += 1

        max_transitions = (
            len(valid) - 1
        )

        consistency = (
            1.0
            - (
                transitions
                / max_transitions
            )
        )

        return max(
            0.0,
            min(
                1.0,
                consistency,
            ),
        )

    # ========================================================
    # SIGNALS
    # ========================================================

    @staticmethod
    def _build_signals(
        results: List[
            Optional[str]
        ],
        xg_average: Optional[float],
        xga_average: Optional[float],
        goals_average: Optional[float],
        conceded_average: Optional[float],
    ) -> List[str]:

        signals: List[str] = []

        valid = [
            result
            for result in results
            if result is not None
        ]

        # ----------------------------------------------------
        # WIN STREAK
        # ----------------------------------------------------

        win_streak = 0

        for result in valid:

            if result == "W":
                win_streak += 1
            else:
                break

        if win_streak >= 5:
            signals.append(
                "gladiator_effect"
            )

        # ----------------------------------------------------
        # ATTACK
        # ----------------------------------------------------

        if goals_average is not None:

            if goals_average >= 2.0:
                signals.append(
                    "high_goal_output"
                )

            elif goals_average < 1.0:
                signals.append(
                    "low_goal_output"
                )

        # ----------------------------------------------------
        # DEFENSE
        # ----------------------------------------------------

        if conceded_average is not None:

            if conceded_average >= 2.0:
                signals.append(
                    "high_conceding_rate"
                )

            elif conceded_average <= 0.75:
                signals.append(
                    "strong_defense"
                )

        # ----------------------------------------------------
        # XG
        # ----------------------------------------------------

        if (
            xg_average is not None
            and goals_average is not None
        ):

            if (
                xg_average >= 1.5
                and goals_average < 1.0
            ):
                signals.append(
                    "lukaku_effect"
                )

            if (
                xg_average < 1.0
                and goals_average >= 1.5
            ):
                signals.append(
                    "dark_horse_effect"
                )

        return signals


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def analyze_form(
    records: List[
        Dict[str, Any]
    ],
    team_name: str,
    form_context: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    """
    Удобная функция для FAJ Brain.

    Позволяет использовать модель без явного
    создания FormModel().
    """

    model = FormModel()

    return model.analyze(
        records=records,
        team_name=team_name,
        form_context=form_context,
    )


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "FORM_MODEL_CONFIG",
    "FormModelResult",
    "FormModel",
    "analyze_form",
]
