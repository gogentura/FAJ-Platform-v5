#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=============================================================
FAJ Platform v12.1 — MEMORY HARDENED
FAJ Final Score Engine v1.2
=============================================================

РОЛЬ
----
Определяет FAJ Final Score на основании:

    Math Distribution
            +
    Team Rating
            +
    Team Passport
            +
    Current Form
            +
    Last Match
            +
    Home Advantage
            ↓
    FAJ Score Ranking
            ↓
    FAJ Final Score
            +
    FAJ Confidence

АРХИТЕКТУРНЫЕ ПРАВИЛА
---------------------

1. Engine НЕ работает с БД.
2. Engine НЕ знает SQLite.
3. Engine НЕ загружает команды.
4. Engine НЕ изменяет Rating.
5. Engine НЕ изменяет Passport.
6. Engine НЕ собирает статистику.
7. Engine НЕ знает фактический результат матча.
8. Engine НЕ использует GOLD / FACT.
9. Engine НЕ использует будущие данные.
10. Engine НЕ обучает модель.
11. Engine НЕ изменяет Math Distribution.
12. Engine только ранжирует уже рассчитанные математические
    кандидаты.
13. Одинаковый вход → одинаковый выход.
14. Отсутствие контекста НЕ превращается в выдуманные данные.
15. Все корректирующие факторы ограничены по амплитуде.
16. После применения факторов итоговые веса нормализуются.

ВАЖНЫЙ ПРИНЦИП
--------------
Math Most Likely Score и FAJ Final Score — разные сущности.

Math:
    чистый результат математической модели.

FAJ:
    решение FAJ после применения доступного контекста.

FAJ НЕ переписывает Math.

Версия:
    1.2
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union


logger = logging.getLogger(__name__)


class FAJFinalScoreEngine:
    """
    Чистый детерминированный FAJ Final Score Engine.

    Вход:
        - контекст домашней команды;
        - контекст гостевой команды;
        - математическое распределение счетов.

    Выход:
        - Math Most Likely Score;
        - FAJ Final Score;
        - FAJ Confidence;
        - FAJ Score Ranking;
        - Decision Factors;
        - Context Availability.
    """

    VERSION = "1.2"

    # ==========================================================
    # ВЕСА ФАКТОРОВ
    # ==========================================================

    WEIGHTS = {
        "rating": 0.35,
        "passport": 0.30,
        "form": 0.20,
        "last_match": 0.10,
    }

    # ==========================================================
    # ВЕС ИСТОРИИ
    # ==========================================================

    HISTORY_WEIGHT_MAP = {
        0: 0.00,
        1: 0.30,
        2: 0.50,
        3: 0.70,
        4: 0.90,
        5: 1.00,
    }

    # ==========================================================
    # ОГРАНИЧЕНИЯ ФАКТОРОВ
    # ==========================================================

    FACTOR_MIN = 0.70
    FACTOR_MAX = 1.30

    RATING_MIN = 0.85
    RATING_MAX = 1.15

    FORM_MIN = 0.90
    FORM_MAX = 1.10

    LAST_MATCH_MIN = 0.95
    LAST_MATCH_MAX = 1.05

    HOME_ADV_MIN = 0.97
    HOME_ADV_MAX = 1.08

    # ==========================================================
    # ИНИЦИАЛИЗАЦИЯ
    # ==========================================================

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Создаёт Engine.

        weights:
            Необязательные веса факторов.

        Важно:
            веса не являются обучением.
            Это параметры текущей конфигурации Engine.
        """

        source_weights = weights or self.WEIGHTS

        self.weights = {
            key: float(value)
            for key, value in source_weights.items()
        }

        self._validate_weights()

        logger.info(
            "FAJ Final Score Engine v%s initialized",
            self.VERSION,
        )

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def calculate(
        self,
        home_context: Dict[str, Any],
        away_context: Dict[str, Any],
        math_distribution: Union[
            Dict[str, float],
            List[Dict[str, Any]],
        ],
        home_advantage: float = 1.08,
    ) -> Dict[str, Any]:
        """
        Рассчитывает FAJ Final Score.

        Parameters
        ----------
        home_context:
            Контекст домашней команды.

        away_context:
            Контекст гостевой команды.

        math_distribution:
            Один из форматов:

            {
                "1:1": 0.128,
                "2:1": 0.109
            }

            или:

            [
                {
                    "home": 1,
                    "away": 1,
                    "probability": 0.128
                }
            ]

        home_advantage:
            Коэффициент домашнего преимущества.

        Returns
        -------
        dict
        """

        # ------------------------------------------------------
        # 0. Защита входных данных
        # ------------------------------------------------------

        home_context = (
            home_context
            if isinstance(home_context, dict)
            else {}
        )

        away_context = (
            away_context
            if isinstance(away_context, dict)
            else {}
        )

        # ------------------------------------------------------
        # 1. Нормализация Math Distribution
        # ------------------------------------------------------

        distribution = self._normalize_distribution(
            math_distribution
        )

        if not distribution:
            return self._empty_result(
                error="Math distribution is empty or invalid"
            )

        # ------------------------------------------------------
        # 2. Math Most Likely Score
        # ------------------------------------------------------

        math_score = self._select_math_most_likely(
            distribution
        )

        math_probability = distribution[math_score]

        # ------------------------------------------------------
        # 3. Контекст
        # ------------------------------------------------------

        home_rating = home_context.get("rating")
        away_rating = away_context.get("rating")

        home_passport = self._as_dict(
            home_context.get("passport")
        )

        away_passport = self._as_dict(
            away_context.get("passport")
        )

        home_form = self._as_dict(
            home_context.get("form")
        )

        away_form = self._as_dict(
            away_context.get("form")
        )

        home_last_match = self._as_dict(
            home_context.get("last_match")
        )

        away_last_match = self._as_dict(
            away_context.get("last_match")
        )

        # ------------------------------------------------------
        # 4. Availability
        # ------------------------------------------------------

        availability = {
            "home_rating": home_rating is not None,
            "away_rating": away_rating is not None,

            "home_passport": bool(home_passport),
            "away_passport": bool(away_passport),

            "home_form": bool(home_form),
            "away_form": bool(away_form),

            "home_last_match": bool(home_last_match),
            "away_last_match": bool(away_last_match),
        }

        # ------------------------------------------------------
        # 5. History Weight
        # ------------------------------------------------------

        home_history_count = self._history_count(
            home_context
        )

        away_history_count = self._history_count(
            away_context
        )

        history_count = min(
            home_history_count,
            away_history_count,
        )

        history_weight = self._get_history_weight(
            history_count
        )

        # ------------------------------------------------------
        # 6. Ranking
        # ------------------------------------------------------

        ranking: List[Dict[str, Any]] = []

        for score, probability in distribution.items():

            if probability <= 0.0:
                continue

            home_goals, away_goals = self._parse_score(
                score
            )

            # --------------------------------------------------
            # 6.1 Rating
            # --------------------------------------------------

            rating_factor = (
                self._calculate_rating_factor_for_score(
                    home_rating=home_rating,
                    away_rating=away_rating,
                    home_goals=home_goals,
                    away_goals=away_goals,
                )
            )

            # --------------------------------------------------
            # 6.2 Passport
            # --------------------------------------------------

            passport_factor = (
                self._calculate_passport_factor_for_score(
                    home_passport=home_passport,
                    away_passport=away_passport,
                    home_goals=home_goals,
                    away_goals=away_goals,
                )
            )

            # --------------------------------------------------
            # 6.3 Form
            # --------------------------------------------------

            if history_weight > 0.0:

                form_factor = (
                    self._calculate_form_factor_for_score(
                        home_form=home_form,
                        away_form=away_form,
                        home_goals=home_goals,
                        away_goals=away_goals,
                    )
                )

            else:
                form_factor = 1.0

            # --------------------------------------------------
            # 6.4 Last Match
            # --------------------------------------------------

            if history_weight > 0.0:

                last_match_factor = (
                    self._calculate_last_match_factor_for_score(
                        home_last_match=home_last_match,
                        away_last_match=away_last_match,
                        home_goals=home_goals,
                        away_goals=away_goals,
                    )
                )

            else:
                last_match_factor = 1.0

            # --------------------------------------------------
            # 6.5 Home Advantage
            # --------------------------------------------------

            home_adv_factor = (
                self._calculate_home_advantage_for_score(
                    home_goals=home_goals,
                    away_goals=away_goals,
                    home_advantage=home_advantage,
                )
            )

            # --------------------------------------------------
            # 6.6 Итоговый FAJ Weight
            # --------------------------------------------------

            faj_weight = self._calculate_faj_score(
                math_probability=probability,
                rating_factor=rating_factor,
                passport_factor=passport_factor,
                form_factor=form_factor,
                last_match_factor=last_match_factor,
                home_adv_factor=home_adv_factor,
                history_weight=history_weight,
            )

            ranking.append(
                {
                    "score": score,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "math_probability": round(
                        probability,
                        6,
                    ),
                    "faj_weight": round(
                        faj_weight,
                        6,
                    ),
                    "rating_factor": round(
                        rating_factor,
                        6,
                    ),
                    "passport_factor": round(
                        passport_factor,
                        6,
                    ),
                    "form_factor": round(
                        form_factor,
                        6,
                    ),
                    "last_match_factor": round(
                        last_match_factor,
                        6,
                    ),
                    "home_advantage_factor": round(
                        home_adv_factor,
                        6,
                    ),
                }
            )

        if not ranking:
            return self._empty_result(
                error="No valid score candidates"
            )

        # ------------------------------------------------------
        # 7. Нормализация FAJ weights
        # ------------------------------------------------------

        total_weight = sum(
            item["faj_weight"]
            for item in ranking
        )

        if total_weight <= 0.0:
            return self._empty_result(
                error="FAJ score weights are invalid"
            )

        for item in ranking:
            item["faj_probability"] = round(
                item["faj_weight"] / total_weight,
                6,
            )

        # ------------------------------------------------------
        # 8. Детерминированная сортировка
        # ------------------------------------------------------

        ranking.sort(
            key=lambda item: (
                -item["faj_probability"],
                -item["math_probability"],
                item["home_goals"],
                item["away_goals"],
            )
        )

        # ------------------------------------------------------
        # 9. Rank
        # ------------------------------------------------------

        for rank, item in enumerate(
            ranking,
            start=1,
        ):
            item["rank"] = rank

        # ------------------------------------------------------
        # 10. FAJ Final Score
        # ------------------------------------------------------

        top = ranking[0]

        faj_final_score = top["score"]

        # ------------------------------------------------------
        # 11. Confidence
        # ------------------------------------------------------

        confidence = self._calculate_confidence(
            ranking
        )

        # ------------------------------------------------------
        # 12. Decision Factors
        # ------------------------------------------------------

        decision_factors = (
            self._build_decision_factors(
                home_rating=home_rating,
                away_rating=away_rating,
                home_passport=home_passport,
                away_passport=away_passport,
                home_form=home_form,
                away_form=away_form,
                home_last_match=home_last_match,
                away_last_match=away_last_match,
                history_count=history_count,
                history_weight=history_weight,
                home_advantage=home_advantage,
                top_candidate=top,
            )
        )

        # ------------------------------------------------------
        # 13. Финальный результат
        # ------------------------------------------------------

        return {
            "engine_version": self.VERSION,

            "faj_final_score": faj_final_score,

            "faj_confidence": round(
                confidence,
                6,
            ),

            "math_most_likely_score": math_score,

            "math_probability": round(
                math_probability,
                6,
            ),

            "faj_score_ranking": ranking[:10],

            "decision_factors": decision_factors,

            "context_availability": availability,

            "history_count": history_count,

            "history_weight": round(
                history_weight,
                4,
            ),
        }

    # ==========================================================
    # DISTRIBUTION
    # ==========================================================

    def _normalize_distribution(
        self,
        distribution: Union[
            Dict[str, float],
            List[Dict[str, Any]],
        ],
    ) -> Dict[str, float]:
        """
        Приводит Math Distribution к:

            {
                "home:away": probability
            }

        ВАЖНО:
            Здесь мы не меняем вероятности
            и не нормализуем их повторно.

        Math Distribution должен прийти
        уже как результат математической модели.
        """

        result: Dict[str, float] = {}

        if isinstance(distribution, dict):

            for raw_score, raw_probability in (
                distribution.items()
            ):

                score = self._normalize_score(
                    raw_score
                )

                if score is None:
                    continue

                probability = self._safe_probability(
                    raw_probability
                )

                if probability is None:
                    continue

                result[score] = (
                    result.get(score, 0.0)
                    + probability
                )

        elif isinstance(distribution, list):

            for item in distribution:

                if not isinstance(item, dict):
                    continue

                home = item.get("home")
                away = item.get("away")
                probability = item.get(
                    "probability"
                )

                try:
                    home_goals = int(home)
                    away_goals = int(away)
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                if (
                    home_goals < 0
                    or away_goals < 0
                ):
                    continue

                probability = self._safe_probability(
                    probability
                )

                if probability is None:
                    continue

                score = (
                    f"{home_goals}:{away_goals}"
                )

                result[score] = (
                    result.get(score, 0.0)
                    + probability
                )

        return result

    def _normalize_score(
        self,
        value: Any,
    ) -> Optional[str]:
        """
        Нормализует score.

        Поддерживает:
            1:1
            1-1
        """

        if value is None:
            return None

        text = str(value).strip()

        if ":" in text:
            parts = text.split(":", 1)

        elif "-" in text:
            parts = text.split("-", 1)

        else:
            return None

        if len(parts) != 2:
            return None

        try:
            home = int(parts[0].strip())
            away = int(parts[1].strip())
        except (
            TypeError,
            ValueError,
        ):
            return None

        if home < 0 or away < 0:
            return None

        return f"{home}:{away}"

    def _safe_probability(
        self,
        value: Any,
    ) -> Optional[float]:
        """Проверяет вероятность."""

        try:
            probability = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(probability):
            return None

        if probability <= 0.0:
            return None

        return probability

    # ==========================================================
    # SCORE
    # ==========================================================

    def _parse_score(
        self,
        score: str,
    ) -> Tuple[int, int]:
        """Разбирает score."""

        parts = score.split(":", 1)

        if len(parts) != 2:
            return 0, 0

        try:
            return (
                int(parts[0]),
                int(parts[1]),
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0, 0

    def _select_math_most_likely(
        self,
        distribution: Dict[str, float],
    ) -> str:
        """
        Детерминированный выбор Math Most Likely.
        """

        return max(
            distribution.items(),
            key=lambda item: (
                item[1],
                -self._parse_score(item[0])[0],
                -self._parse_score(item[0])[1],
            ),
        )[0]

    # ==========================================================
    # RATING
    # ==========================================================

    def _calculate_rating_factor_for_score(
        self,
        home_rating: Optional[float],
        away_rating: Optional[float],
        home_goals: int,
        away_goals: int,
    ) -> float:
        """
        Оценивает совместимость конкретного счёта
        с разницей рейтингов.

        Важно:
            рейтинг не создаёт новую вероятность.
            Он только корректирует относительный вес кандидата.
        """

        home_rating = self._optional_float(
            home_rating
        )

        away_rating = self._optional_float(
            away_rating
        )

        if (
            home_rating is None
            or away_rating is None
        ):
            return 1.0

        delta = home_rating - away_rating

        goal_delta = (
            home_goals - away_goals
        )

        # Если рейтинги практически равны —
        # рейтинг не вмешивается.
        if abs(delta) < 1e-9:
            return 1.0

        # Сильная домашняя команда.
        if delta > 0:

            if goal_delta > 0:
                factor = 1.0 + min(
                    0.15,
                    abs(delta) / 100.0 * 0.50,
                )

            elif goal_delta == 0:
                factor = 1.0

            else:
                factor = 1.0 - min(
                    0.15,
                    abs(delta) / 100.0 * 0.35,
                )

        # Сильная гостевая команда.
        else:

            if goal_delta < 0:
                factor = 1.0 + min(
                    0.15,
                    abs(delta) / 100.0 * 0.50,
                )

            elif goal_delta == 0:
                factor = 1.0

            else:
                factor = 1.0 - min(
                    0.15,
                    abs(delta) / 100.0 * 0.35,
                )

        return self._clamp(
            factor,
            self.RATING_MIN,
            self.RATING_MAX,
        )

    # ==========================================================
    # PASSPORT
    # ==========================================================

    def _calculate_passport_factor_for_score(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_goals: int,
        away_goals: int,
    ) -> float:
        """
        Оценивает совместимость конкретного счёта
        с паспортами обеих команд.

        КРИТИЧЕСКОЕ ПРАВИЛО:

            отсутствующий параметр НЕ превращается в 50.

        Если данных недостаточно —
        соответствующая часть фактора просто
        не участвует.
        """

        if (
            not home_passport
            and not away_passport
        ):
            return 1.0

        contributions: List[float] = []

        # ------------------------------------------------------
        # HOME GOALS
        # ------------------------------------------------------

        if home_goals > 0:

            home_attack = self._optional_float(
                home_passport.get("attack")
            )

            away_defense = self._optional_float(
                away_passport.get("defense")
            )

            if (
                home_attack is not None
                and away_defense is not None
            ):

                delta = (
                    home_attack
                    - away_defense
                ) / 100.0

                contributions.append(
                    self._clamp(
                        delta * 0.30,
                        -0.15,
                        0.15,
                    )
                )

            home_finishing = (
                self._optional_float(
                    home_passport.get(
                        "finishing"
                    )
                )
            )

            away_goalkeeper = (
                self._optional_float(
                    away_passport.get(
                        "goalkeeper"
                    )
                )
            )

            if (
                home_finishing is not None
                and away_goalkeeper is not None
            ):

                delta = (
                    home_finishing
                    - away_goalkeeper
                ) / 100.0

                contributions.append(
                    self._clamp(
                        delta * 0.20,
                        -0.10,
                        0.10,
                    )
                )

        # ------------------------------------------------------
        # AWAY GOALS
        # ------------------------------------------------------

        if away_goals > 0:

            away_attack = self._optional_float(
                away_passport.get("attack")
            )

            home_defense = self._optional_float(
                home_passport.get("defense")
            )

            if (
                away_attack is not None
                and home_defense is not None
            ):

                delta = (
                    away_attack
                    - home_defense
                ) / 100.0

                contributions.append(
                    self._clamp(
                        delta * 0.30,
                        -0.15,
                        0.15,
                    )
                )

            away_finishing = (
                self._optional_float(
                    away_passport.get(
                        "finishing"
                    )
                )
            )

            home_goalkeeper = (
                self._optional_float(
                    home_passport.get(
                        "goalkeeper"
                    )
                )
            )

            if (
                away_finishing is not None
                and home_goalkeeper is not None
            ):

                delta = (
                    away_finishing
                    - home_goalkeeper
                ) / 100.0

                contributions.append(
                    self._clamp(
                        delta * 0.20,
                        -0.10,
                        0.10,
                    )
                )

        # ------------------------------------------------------
        # CONTROL
        # ------------------------------------------------------

        home_control = self._optional_float(
            home_passport.get("control")
        )

        away_control = self._optional_float(
            away_passport.get("control")
        )

        if (
            home_control is not None
            and away_control is not None
            and (home_goals + away_goals) > 0
        ):

            control_delta = (
                home_control
                - away_control
            ) / 100.0

            if home_goals > away_goals:
                contributions.append(
                    self._clamp(
                        control_delta * 0.05,
                        -0.05,
                        0.05,
                    )
                )

            elif away_goals > home_goals:
                contributions.append(
                    self._clamp(
                        -control_delta * 0.05,
                        -0.05,
                        0.05,
                    )
                )

        if not contributions:
            return 1.0

        # Средний эффект доступных параметров.
        effect = sum(contributions)

        return self._clamp(
            1.0 + effect,
            self.FACTOR_MIN,
            self.FACTOR_MAX,
        )

    # ==========================================================
    # FORM
    # ==========================================================

    def _calculate_form_factor_for_score(
        self,
        home_form: Dict[str, Any],
        away_form: Dict[str, Any],
        home_goals: int,
        away_goals: int,
    ) -> float:
        """
        Оценивает соответствие счёта текущей форме.

        Использует только реально присутствующие points.
        """

        home_points = self._optional_float(
            home_form.get("points")
        )

        away_points = self._optional_float(
            away_form.get("points")
        )

        if (
            home_points is None
            or away_points is None
        ):
            return 1.0

        # Для последних 5 матчей:
        max_points = 15.0

        home_norm = self._clamp(
            home_points / max_points,
            0.0,
            1.0,
        )

        away_norm = self._clamp(
            away_points / max_points,
            0.0,
            1.0,
        )

        delta = home_norm - away_norm

        total_goals = (
            home_goals + away_goals
        )

        # Нулевой счёт не должен искусственно
        # получать бонус формы.
        if total_goals == 0:
            return 1.0

        if delta > 0 and home_goals > 0:

            share = (
                home_goals
                / total_goals
            )

            effect = (
                delta
                * 0.25
                * share
            )

        elif delta < 0 and away_goals > 0:

            share = (
                away_goals
                / total_goals
            )

            effect = (
                abs(delta)
                * 0.25
                * share
            )

        else:
            effect = 0.0

        return self._clamp(
            1.0 + effect,
            self.FORM_MIN,
            self.FORM_MAX,
        )

    # ==========================================================
    # LAST MATCH
    # ==========================================================

    def _calculate_last_match_factor_for_score(
        self,
        home_last_match: Dict[str, Any],
        away_last_match: Dict[str, Any],
        home_goals: int,
        away_goals: int,
    ) -> float:
        """
        Оценивает влияние последнего матча.

        WIN  → небольшой положительный эффект
        DRAW → нейтрально
        LOSS → небольшой отрицательный эффект
        """

        home_result = (
            home_last_match.get("result")
        )

        away_result = (
            away_last_match.get("result")
        )

        home_effect = self._result_effect(
            home_result
        )

        away_effect = self._result_effect(
            away_result
        )

        total_goals = (
            home_goals + away_goals
        )

        if total_goals == 0:
            return 1.0

        effect = 0.0

        if home_goals > 0:
            effect += (
                home_effect
                * min(home_goals, 2)
                / 2.0
            )

        if away_goals > 0:
            effect += (
                away_effect
                * min(away_goals, 2)
                / 2.0
            )

        return self._clamp(
            1.0 + effect,
            self.LAST_MATCH_MIN,
            self.LAST_MATCH_MAX,
        )

    def _result_effect(
        self,
        result: Any,
    ) -> float:
        """Преобразует результат последнего матча в небольшой эффект."""

        if result == "WIN":
            return 0.05

        if result == "LOSS":
            return -0.05

        if result == "DRAW":
            return 0.0

        return 0.0

    # ==========================================================
    # HOME ADVANTAGE
    # ==========================================================

    def _calculate_home_advantage_for_score(
        self,
        home_goals: int,
        away_goals: int,
        home_advantage: float,
    ) -> float:
        """
        Домашнее преимущество применяется
        только как корректирующий фактор
        конкретного счёта.

        Важно:
            окончательные FAJ probabilities
            нормализуются после применения факторов.
        """

        try:
            advantage = float(
                home_advantage
            )
        except (
            TypeError,
            ValueError,
        ):
            return 1.0

        if not math.isfinite(advantage):
            return 1.0

        # Ограничиваем внешний параметр.
        advantage = self._clamp(
            advantage,
            1.0,
            self.HOME_ADV_MAX,
        )

        bonus = advantage - 1.0

        if home_goals > away_goals:
            factor = 1.0 + bonus

        elif home_goals == away_goals:
            factor = 1.0 + bonus * 0.35

        else:
            factor = 1.0 - bonus * 0.25

        return self._clamp(
            factor,
            self.HOME_ADV_MIN,
            self.HOME_ADV_MAX,
        )

    # ==========================================================
    # FINAL FAJ SCORE
    # ==========================================================

    def _calculate_faj_score(
        self,
        math_probability: float,
        rating_factor: float,
        passport_factor: float,
        form_factor: float,
        last_match_factor: float,
        home_adv_factor: float,
        history_weight: float,
    ) -> float:
        """
        Рассчитывает FAJ weight.

        Это пока НЕ probability.

        Формула:

            FAJ Weight =
                Math Probability
                × Rating Effect
                × Passport Effect
                × Form Effect
                × Last Match Effect
                × Home Advantage

        После расчёта всех кандидатов
        веса нормализуются в faj_probability.
        """

        score = float(
            math_probability
        )

        # ------------------------------------------------------
        # Rating
        # ------------------------------------------------------

        rating_weight = self.weights[
            "rating"
        ]

        score *= (
            1.0
            + (
                rating_factor - 1.0
            ) * rating_weight
        )

        # ------------------------------------------------------
        # Passport
        # ------------------------------------------------------

        passport_weight = self.weights[
            "passport"
        ]

        score *= (
            1.0
            + (
                passport_factor - 1.0
            ) * passport_weight
        )

        # ------------------------------------------------------
        # Form
        # ------------------------------------------------------

        form_weight = self.weights[
            "form"
        ]

        if history_weight > 0.0:

            effective_form_weight = (
                form_weight
                * history_weight
            )

            score *= (
                1.0
                + (
                    form_factor - 1.0
                ) * effective_form_weight
            )

        # ------------------------------------------------------
        # Last Match
        # ------------------------------------------------------

        last_match_weight = self.weights[
            "last_match"
        ]

        if history_weight > 0.0:

            effective_last_weight = (
                last_match_weight
                * history_weight
            )

            score *= (
                1.0
                + (
                    last_match_factor - 1.0
                ) * effective_last_weight
            )

        # ------------------------------------------------------
        # Home Advantage
        # ------------------------------------------------------

        score *= home_adv_factor

        return max(
            0.0,
            score,
        )

    # ==========================================================
    # CONFIDENCE
    # ==========================================================

    def _calculate_confidence(
        self,
        ranking: List[Dict[str, Any]],
    ) -> float:
        """
        Confidence определяется разрывом
        между первым и вторым кандидатом.

        Это не вероятность правильности прогноза.

        Это только внутренняя уверенность Engine
        в выборе первого кандидата относительно второго.
        """

        if not ranking:
            return 0.0

        if len(ranking) == 1:
            return 1.0

        top_probability = float(
            ranking[0]["faj_probability"]
        )

        second_probability = float(
            ranking[1]["faj_probability"]
        )

        if top_probability <= 0.0:
            return 0.0

        if second_probability <= 0.0:
            return 1.0

        ratio = (
            top_probability
            / second_probability
        )

        confidence = (
            ratio - 1.0
        ) * 2.0

        return self._clamp(
            confidence,
            0.0,
            1.0,
        )

    # ==========================================================
    # DECISION FACTORS
    # ==========================================================

    def _build_decision_factors(
        self,
        home_rating: Any,
        away_rating: Any,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_form: Dict[str, Any],
        away_form: Dict[str, Any],
        home_last_match: Dict[str, Any],
        away_last_match: Dict[str, Any],
        history_count: int,
        history_weight: float,
        home_advantage: float,
        top_candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Формирует прозрачный audit trail решения.

        Здесь нет новых расчётов,
        только фиксация использованного контекста.
        """

        rating_delta = None

        home_rating_value = self._optional_float(
            home_rating
        )

        away_rating_value = self._optional_float(
            away_rating
        )

        if (
            home_rating_value is not None
            and away_rating_value is not None
        ):
            rating_delta = (
                home_rating_value
                - away_rating_value
            )

        return {
            "rating": {
                "home": home_rating_value,
                "away": away_rating_value,
                "delta": rating_delta,
                "factor": top_candidate[
                    "rating_factor"
                ],
            },

            "passport": {
                "home_attack": home_passport.get(
                    "attack"
                ),
                "home_defense": home_passport.get(
                    "defense"
                ),
                "away_attack": away_passport.get(
                    "attack"
                ),
                "away_defense": away_passport.get(
                    "defense"
                ),
                "home_finishing": home_passport.get(
                    "finishing"
                ),
                "away_finishing": away_passport.get(
                    "finishing"
                ),
                "home_goalkeeper": home_passport.get(
                    "goalkeeper"
                ),
                "away_goalkeeper": away_passport.get(
                    "goalkeeper"
                ),
                "home_control": home_passport.get(
                    "control"
                ),
                "away_control": away_passport.get(
                    "control"
                ),
                "factor": top_candidate[
                    "passport_factor"
                ],
            },

            "form": {
                "home_points": home_form.get(
                    "points"
                ),
                "away_points": away_form.get(
                    "points"
                ),
                "factor": top_candidate[
                    "form_factor"
                ],
            },

            "last_match": {
                "home_result": home_last_match.get(
                    "result"
                ),
                "away_result": away_last_match.get(
                    "result"
                ),
                "factor": top_candidate[
                    "last_match_factor"
                ],
            },

            "home_advantage": {
                "configured_value": home_advantage,
                "factor": top_candidate[
                    "home_advantage_factor"
                ],
            },

            "history": {
                "count": history_count,
                "weight": round(
                    history_weight,
                    4,
                ),
            },

            "selected_candidate": {
                "score": top_candidate[
                    "score"
                ],
                "math_probability": top_candidate[
                    "math_probability"
                ],
                "faj_probability": top_candidate[
                    "faj_probability"
                ],
            },
        }

    # ==========================================================
    # HISTORY
    # ==========================================================

    def _history_count(
        self,
        context: Dict[str, Any],
    ) -> int:
        """
        Возвращает количество доступных
        recent_matches.
        """

        recent_matches = context.get(
            "recent_matches",
            []
        )

        if not isinstance(
            recent_matches,
            list,
        ):
            return 0

        return len(recent_matches)

    def _get_history_weight(
        self,
        count: int,
    ) -> float:
        """Возвращает вес истории."""

        if count <= 0:
            return 0.0

        if count >= 5:
            return 1.0

        return self.HISTORY_WEIGHT_MAP.get(
            count,
            0.0,
        )

    # ==========================================================
    # UTILITY
    # ==========================================================

    def _optional_float(
        self,
        value: Any,
    ) -> Optional[float]:
        """
        Безопасное преобразование.

        В отличие от _safe_float:
            None остаётся None.

        Это принципиально важно:
            отсутствие данных != 0
            отсутствие данных != 50
        """

        if value is None:
            return None

        try:
            result = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(result):
            return None

        return result

    def _safe_float(
        self,
        value: Any,
        default: float = 0.0,
    ) -> float:
        """Совместимый utility-метод."""

        result = self._optional_float(
            value
        )

        if result is None:
            return default

        return result

    def _as_dict(
        self,
        value: Any,
    ) -> Dict[str, Any]:
        """Возвращает dict или пустой dict."""

        if isinstance(value, dict):
            return value

        return {}

    def _clamp(
        self,
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """Ограничивает значение."""

        return max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

    def _validate_weights(self) -> None:
        """
        Проверяет конфигурацию весов.
        """

        required = {
            "rating",
            "passport",
            "form",
            "last_match",
        }

        missing = required - set(
            self.weights.keys()
        )

        if missing:
            raise ValueError(
                "Missing FAJ factor weights: "
                + ", ".join(sorted(missing))
            )

        for name, value in self.weights.items():

            if not math.isfinite(value):
                raise ValueError(
                    f"Invalid weight: {name}"
                )

            if value < 0.0:
                raise ValueError(
                    f"Negative weight: {name}"
                )

    # ==========================================================
    # EMPTY RESULT
    # ==========================================================

    def _empty_result(
        self,
        error: str,
    ) -> Dict[str, Any]:
        """Безопасный пустой результат."""

        return {
            "engine_version": self.VERSION,

            "faj_final_score": "—",

            "faj_confidence": 0.0,

            "math_most_likely_score": "—",

            "math_probability": 0.0,

            "faj_score_ranking": [],

            "decision_factors": {},

            "context_availability": {},

            "history_count": 0,

            "history_weight": 0.0,

            "error": error,
        }


# =============================================================
# SINGLETON
# =============================================================

_default_engine: Optional[
    FAJFinalScoreEngine
] = None


def get_faj_final_score_engine(
    weights: Optional[Dict[str, float]] = None,
) -> FAJFinalScoreEngine:
    """
    Возвращает singleton Engine.

    Важно:
        singleton не хранит состояние конкретного матча.
        Engine остаётся stateless относительно матчей.
    """

    global _default_engine

    if _default_engine is None:

        _default_engine = (
            FAJFinalScoreEngine(
                weights=weights
            )
        )

    return _default_engine


# =============================================================
# LOCAL TEST
# =============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    engine = FAJFinalScoreEngine()

    home_context = {
        "rating": 92.0,

        "passport": {
            "attack": 85.0,
            "defense": 70.0,
            "control": 78.0,
            "finishing": 82.0,
            "goalkeeper": 75.0,
            "home_strength": 88.0,
            "away_strength": 72.0,
        },

        "last_match": {
            "result": "WIN",
            "goals_for": 3,
            "goals_against": 0,
        },

        "form": {
            "points": 12,
            "goals_scored": 10,
            "goals_conceded": 4,
        },

        "recent_matches": [
            {"result": "WIN"},
            {"result": "WIN"},
            {"result": "DRAW"},
            {"result": "WIN"},
            {"result": "LOSS"},
        ],
    }

    away_context = {
        "rating": 82.0,

        "passport": {
            "attack": 72.0,
            "defense": 78.0,
            "control": 70.0,
            "finishing": 68.0,
            "goalkeeper": 80.0,
            "home_strength": 75.0,
            "away_strength": 78.0,
        },

        "last_match": {
            "result": "LOSS",
            "goals_for": 0,
            "goals_against": 2,
        },

        "form": {
            "points": 8,
            "goals_scored": 6,
            "goals_conceded": 8,
        },

        "recent_matches": [
            {"result": "WIN"},
            {"result": "LOSS"},
            {"result": "LOSS"},
            {"result": "WIN"},
            {"result": "DRAW"},
        ],
    }

    math_distribution = [
        {
            "home": 0,
            "away": 0,
            "probability": 0.043,
        },
        {
            "home": 1,
            "away": 0,
            "probability": 0.097,
        },
        {
            "home": 0,
            "away": 1,
            "probability": 0.072,
        },
        {
            "home": 1,
            "away": 1,
            "probability": 0.128,
        },
        {
            "home": 2,
            "away": 1,
            "probability": 0.109,
        },
        {
            "home": 2,
            "away": 0,
            "probability": 0.078,
        },
        {
            "home": 2,
            "away": 2,
            "probability": 0.064,
        },
        {
            "home": 3,
            "away": 1,
            "probability": 0.051,
        },
        {
            "home": 1,
            "away": 2,
            "probability": 0.049,
        },
        {
            "home": 3,
            "away": 0,
            "probability": 0.038,
        },
    ]

    result = engine.calculate(
        home_context=home_context,
        away_context=away_context,
        math_distribution=math_distribution,
        home_advantage=1.08,
    )

    print()
    print("=" * 64)
    print("FAJ FINAL SCORE ENGINE v1.2")
    print("=" * 64)

    print(
        "Math Most Likely Score:",
        result["math_most_likely_score"],
        f"({result['math_probability']:.2%})",
    )

    print(
        "FAJ Final Score:",
        result["faj_final_score"],
    )

    print(
        "FAJ Confidence:",
        f"{result['faj_confidence']:.2%}",
    )

    print()
    print("FAJ SCORE RANKING")
    print("-" * 64)

    for item in result[
        "faj_score_ranking"
    ][:10]:

        print(
            f"{item['rank']:>2}. "
            f"{item['score']:>5} | "
            f"math={item['math_probability']:.4f} | "
            f"faj={item['faj_probability']:.4f}"
        )

    print()
    print("DECISION FACTORS")
    print("-" * 64)

    factors = result[
        "decision_factors"
    ]

    print(
        "Rating delta:",
        factors["rating"]["delta"],
    )

    print(
        "History count:",
        factors["history"]["count"],
    )

    print(
        "History weight:",
        factors["history"]["weight"],
    )

    print(
        "Home advantage:",
        factors["home_advantage"][
            "configured_value"
        ],
    )
