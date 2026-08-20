#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Club Rating Updater
============================================================

НАЗНАЧЕНИЕ:

    Динамическое обновление FAJ Club Rating после
    завершённых матчей.

ЦЕПОЧКА:

    MATCH RESULT
         │
         ├── Actual Result
         ├── Observed xG
         ├── Opponent Strength
         └── Prediction Error
                │
                ▼
        Club Rating Updater
                │
                ├── New FAJ Rating
                ├── Passport Revision
                └── Team History
                │
                ▼
        Следующий FAJ Prediction

ПРИНЦИП:

    Рейтинг изменяется постепенно.

    ETC НЕ:
        - удаляет старый паспорт
        - переписывает историю
        - меняет match_results
        - меняет predictions
        - обучает model_parameters

    ETC:
        - читает текущий рейтинг
        - рассчитывает delta
        - создаёт новую версию паспорта
        - записывает изменение в team_history

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


UPDATER_VERSION = "1.0"
UPDATER_NAME = "FAJ ETC Club Rating Updater"


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_RATING = 50.0

MIN_RATING = 1.0
MAX_RATING = 99.0

# Максимальное изменение рейтинга за один матч.
MAX_MATCH_DELTA = 2.50

# Базовая скорость изменения.
K_FACTOR = 0.35

# Вес фактического xG.
XG_WEIGHT = 0.35

# Вес результата.
RESULT_WEIGHT = 0.65


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _result_score(home_goals: int, away_goals: int) -> float:
    """
    Результат с точки зрения команды.

    Победа = 1.0
    Ничья = 0.5
    Поражение = 0.0
    """

    if home_goals > away_goals:
        return 1.0

    if home_goals < away_goals:
        return 0.0

    return 0.5


# ============================================================
# CLUB RATING UPDATER
# ============================================================

class ClubRatingUpdater:
    """
    Обновляет FAJ Club Rating после завершённого матча.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC
    # ========================================================

    def update_after_match(
        self,
        match: Dict[str, Any],
        result: Dict[str, Any],
        home_observed_xg: Optional[float] = None,
        away_observed_xg: Optional[float] = None,
        home_predicted_xg: Optional[float] = None,
        away_predicted_xg: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Обновляет рейтинг обеих команд после матча.

        Вход:

            match:
                данные из matches

            result:
                данные из match_results

            observed_xg:
                фактический xG

            predicted_xg:
                Predictive xG FAJ

        Возвращает:

            {
                home_rating_old,
                home_rating_new,
                home_delta,
                away_rating_old,
                away_rating_new,
                away_delta,
                ...
            }
        """

        match_id = _safe_int(match.get("id"))

        home_team_id = _safe_int(
            match.get("home_team_id")
        )

        away_team_id = _safe_int(
            match.get("away_team_id")
        )

        season_id = match.get("season_id")

        if not home_team_id or not away_team_id:
            raise ValueError(
                "ClubRatingUpdater: отсутствуют team_id"
            )

        if season_id is None:
            raise ValueError(
                "ClubRatingUpdater: отсутствует season_id"
            )

        home_goals = _safe_int(
            result.get("home_goals")
        )

        away_goals = _safe_int(
            result.get("away_goals")
        )

        # ----------------------------------------------------
        # ТЕКУЩИЕ ПАСПОРТА
        # ----------------------------------------------------

        home_passport = self.db.get_team_passport(
            home_team_id,
            season_id,
        )

        away_passport = self.db.get_team_passport(
            away_team_id,
            season_id,
        )

        if not home_passport:
            raise ValueError(
                f"Нет паспорта хозяев: team_id={home_team_id}"
            )

        if not away_passport:
            raise ValueError(
                f"Нет паспорта гостей: team_id={away_team_id}"
            )

        home_old_rating = _safe_float(
            home_passport.get("faj_rating"),
            DEFAULT_RATING,
        )

        away_old_rating = _safe_float(
            away_passport.get("faj_rating"),
            DEFAULT_RATING,
        )

        # ----------------------------------------------------
        # ОЖИДАЕМЫЙ РЕЗУЛЬТАТ
        # ----------------------------------------------------

        expected_home = self._expected_result(
            home_old_rating,
            away_old_rating,
        )

        expected_away = 1.0 - expected_home

        actual_home = _result_score(
            home_goals,
            away_goals,
        )

        actual_away = 1.0 - actual_home

        # ----------------------------------------------------
        # РЕЗУЛЬТАТНАЯ КОРРЕКТИРОВКА
        # ----------------------------------------------------

        home_result_delta = (
            actual_home - expected_home
        ) * K_FACTOR * RESULT_WEIGHT

        away_result_delta = (
            actual_away - expected_away
        ) * K_FACTOR * RESULT_WEIGHT

        # ----------------------------------------------------
        # XG КОРРЕКТИРОВКА
        # ----------------------------------------------------

        home_xg_delta = self._calculate_xg_component(
            predicted_xg=home_predicted_xg,
            observed_xg=home_observed_xg,
        )

        away_xg_delta = self._calculate_xg_component(
            predicted_xg=away_predicted_xg,
            observed_xg=away_observed_xg,
        )

        home_delta = (
            home_result_delta
            + home_xg_delta * XG_WEIGHT
        )

        away_delta = (
            away_result_delta
            + away_xg_delta * XG_WEIGHT
        )

        # ----------------------------------------------------
        # ZERO-SUM BALANCE
        # ----------------------------------------------------

        # Для матча изменения рейтингов должны быть
        # зеркальными по основному результату.

        rating_delta = (
            home_delta - away_delta
        ) / 2.0

        rating_delta = _clamp(
            rating_delta,
            -MAX_MATCH_DELTA,
            MAX_MATCH_DELTA,
        )

        home_new_rating = _clamp(
            home_old_rating + rating_delta,
            MIN_RATING,
            MAX_RATING,
        )

        away_new_rating = _clamp(
            away_old_rating - rating_delta,
            MIN_RATING,
            MAX_RATING,
        )

        # ----------------------------------------------------
        # СОХРАНЕНИЕ
        # ----------------------------------------------------

        self._save_rating(
            team_id=home_team_id,
            season_id=season_id,
            passport=home_passport,
            old_rating=home_old_rating,
            new_rating=home_new_rating,
            match_id=match_id,
            reason="ETC post-match rating update",
        )

        self._save_rating(
            team_id=away_team_id,
            season_id=season_id,
            passport=away_passport,
            old_rating=away_old_rating,
            new_rating=away_new_rating,
            match_id=match_id,
            reason="ETC post-match rating update",
        )

        return {
            "success": True,
            "updater": UPDATER_NAME,
            "version": UPDATER_VERSION,
            "match_id": match_id,

            "home_team_id": home_team_id,
            "away_team_id": away_team_id,

            "home_rating_old": round(
                home_old_rating,
                4,
            ),

            "home_rating_new": round(
                home_new_rating,
                4,
            ),

            "home_delta": round(
                home_new_rating - home_old_rating,
                4,
            ),

            "away_rating_old": round(
                away_old_rating,
                4,
            ),

            "away_rating_new": round(
                away_new_rating,
                4,
            ),

            "away_delta": round(
                away_new_rating - away_old_rating,
                4,
            ),

            "expected_home": round(
                expected_home,
                4,
            ),

            "actual_home": round(
                actual_home,
                4,
            ),

            "observed_home_xg": home_observed_xg,
            "observed_away_xg": away_observed_xg,
        }

    # ========================================================
    # EXPECTED RESULT
    # ========================================================

    @staticmethod
    def _expected_result(
        home_rating: float,
        away_rating: float,
    ) -> float:
        """
        Простейшая rating-based вероятность результата.

        Это НЕ букмекерская вероятность.

        Она используется только как внутренний
        компонент изменения Club Rating.
        """

        difference = (
            home_rating
            - away_rating
        )

        # Домашнее преимущество FAJ.
        difference += 3.0

        expected = (
            1.0
            / (
                1.0
                + 10.0 ** (-difference / 10.0)
            )
        )

        return _clamp(
            expected,
            0.05,
            0.95,
        )

    # ========================================================
    # XG COMPONENT
    # ========================================================

    @staticmethod
    def _calculate_xg_component(
        predicted_xg: Optional[float],
        observed_xg: Optional[float],
    ) -> float:
        """
        Возвращает направление xG-коррекции.

        Если фактический xG выше прогнозного —
        команда была недооценена.

        Если ниже —
        команда была переоценена.
        """

        if predicted_xg is None:
            return 0.0

        if observed_xg is None:
            return 0.0

        predicted = _safe_float(
            predicted_xg
        )

        observed = _safe_float(
            observed_xg
        )

        difference = observed - predicted

        # Ограничиваем влияние одного матча.
        return _clamp(
            difference,
            -1.0,
            1.0,
        )

    # ========================================================
    # SAVE
    # ========================================================

    def _save_rating(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any],
        old_rating: float,
        new_rating: float,
        match_id: int,
        reason: str,
    ) -> None:
        """
        Сохраняет новую версию паспорта
        и историю изменения рейтинга.
        """

        if abs(new_rating - old_rating) < 0.000001:
            return

        old_version = passport.get(
            "version",
            "v1.0",
        )

        new_version = self._next_version(
            old_version
        )

        self.db.save_team_passport(
            team_id=team_id,
            season_id=season_id,
            data={
                "faj_rating": new_rating,
                "force_update": True,
            },
            version=new_version,
            source="ETC",
        )

        self.db.record_team_history(
            team_id=team_id,
            season_id=season_id,
            field="faj_rating",
            old_value=str(
                round(old_rating, 6)
            ),
            new_value=str(
                round(new_rating, 6)
            ),
            reason=reason,
            source="ETC",
            reference_match_id=match_id,
        )

        logger.info(
            "ETC Club Rating: team=%s %.4f -> %.4f",
            team_id,
            old_rating,
            new_rating,
        )

    # ========================================================
    # VERSION
    # ========================================================

    @staticmethod
    def _next_version(
        version: str,
    ) -> str:
        """
        v1.0 → v1.1
        v2.3 → v2.4

        Если формат неизвестен —
        возвращаем исходную версию с .etc.
        """

        try:
            if version.startswith("v"):
                number = version[1:]

                major, minor = number.split(
                    ".",
                    1,
                )

                return (
                    f"v{int(major)}."
                    f"{int(minor) + 1}"
                )

        except (ValueError, AttributeError):
            pass

        return f"{version}.etc"


# ============================================================
# PUBLIC API
# ============================================================

def update_club_rating(
    match: Dict[str, Any],
    result: Dict[str, Any],
    home_observed_xg: Optional[float] = None,
    away_observed_xg: Optional[float] = None,
    home_predicted_xg: Optional[float] = None,
    away_predicted_xg: Optional[float] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API ETC.
    """

    updater = ClubRatingUpdater(db=db)

    return updater.update_after_match(
        match=match,
        result=result,
        home_observed_xg=home_observed_xg,
        away_observed_xg=away_observed_xg,
        home_predicted_xg=home_predicted_xg,
        away_predicted_xg=away_predicted_xg,
    )
