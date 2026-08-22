#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Club Rating Updater v2.0
============================================================

ФАЙЛ:
    app/etc/club_rating_updater.py

НАЗНАЧЕНИЕ:
    Контролируемое изменение FAJ Club Rating после
    завершённого матча.

АРХИТЕКТУРА:

    MATCH_RESULT
          │
          ├── Actual Score
          │
          ├── Observed xG
          │
          ├── Predicted xG
          │
          └── Prediction Error
                  │
                  ▼
        ClubRatingUpdater
                  │
          ┌───────┼────────┐
          ▼       ▼        ▼
       Rating   Passport  History
          │       │        │
          └───────┼────────┘
                  ▼
           LearningMemory
                  │
                  ▼
                 ETC

ПРИНЦИПЫ:
    1. SQLite only.
    2. database.py — единый источник схемы.
    3. match_results НЕ изменяется.
    4. predictions НЕ изменяются.
    5. Старые паспорта НЕ удаляются.
    6. Старые записи team_history НЕ удаляются.
    7. learning_memory — append-only.
    8. Один матч не должен повторно применять
       одну и ту же rating-коррекцию.
    9. Модуль НЕ обучает model_parameters.
   10. Модуль НЕ рассчитывает xG.
   11. Модуль НЕ запускает ETC.
   12. Модуль только применяет уже рассчитанную
       ETC-коррекцию рейтинга.
   13. Каждое изменение должно быть объяснимым.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.database import FAJDatabase
from app.etc.learning_memory import LearningMemory


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

UPDATER_VERSION = "2.0"
UPDATER_NAME = "FAJ ETC Club Rating Updater v2.0"


# ============================================================
# RATING CONFIGURATION
# ============================================================

DEFAULT_RATING = 50.0

MIN_RATING = 1.0
MAX_RATING = 99.0

# Максимальная коррекция рейтинга за один матч.
MAX_MATCH_DELTA = 2.50

# Скорость реакции рейтинга.
K_FACTOR = 0.35

# Вес фактического xG.
XG_WEIGHT = 0.35

# Вес фактического результата.
RESULT_WEIGHT = 0.65

# Домашнее преимущество используется только
# внутри внутреннего rating expectation.
HOME_ADVANTAGE = 3.0


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def _result_score(
    goals_for: int,
    goals_against: int,
) -> float:
    """
    Результат с точки зрения команды.

    Победа  = 1.0
    Ничья   = 0.5
    Поражение = 0.0
    """

    if goals_for > goals_against:
        return 1.0

    if goals_for < goals_against:
        return 0.0

    return 0.5


# ============================================================
# CLUB RATING UPDATER
# ============================================================

class ClubRatingUpdater:
    """
    Исполнитель изменения FAJ Club Rating.

    ВАЖНО:

        Этот класс НЕ является обучающим движком.

    Он получает уже известные факты матча и рассчитывает
    только допустимую коррекцию Club Rating.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.memory = LearningMemory(
            self.db
        )

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
        Применяет одну ETC rating-коррекцию к матчу.

        Никаких изменений фактов матча не выполняется.
        """

        response: Dict[str, Any] = {
            "success": False,
            "version": UPDATER_VERSION,
            "updater": UPDATER_NAME,

            "match_id": None,

            "already_processed": False,

            "home": {},
            "away": {},

            "errors": [],
        }

        try:

            # ------------------------------------------------
            # IDENTIFIERS
            # ------------------------------------------------

            match_id = _safe_int(
                match.get("id")
            )

            home_team_id = _safe_int(
                match.get("home_team_id")
            )

            away_team_id = _safe_int(
                match.get("away_team_id")
            )

            season_id = match.get(
                "season_id"
            )

            response["match_id"] = match_id

            if not match_id:
                raise ValueError(
                    "ClubRatingUpdater: отсутствует match_id."
                )

            if not home_team_id:
                raise ValueError(
                    "ClubRatingUpdater: отсутствует home_team_id."
                )

            if not away_team_id:
                raise ValueError(
                    "ClubRatingUpdater: отсутствует away_team_id."
                )

            if season_id is None:
                raise ValueError(
                    "ClubRatingUpdater: отсутствует season_id."
                )

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            home_goals = _safe_int(
                result.get("home_goals")
            )

            away_goals = _safe_int(
                result.get("away_goals")
            )

            # ------------------------------------------------
            # IDEMPOTENCY
            # ------------------------------------------------

            if self._already_processed(
                match_id=match_id,
                season_id=season_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
            ):

                response["success"] = True
                response["already_processed"] = True

                response["home"] = {
                    "team_id": home_team_id,
                    "status": "already_processed",
                }

                response["away"] = {
                    "team_id": away_team_id,
                    "status": "already_processed",
                }

                logger.info(
                    "ETC Club Rating already processed: "
                    "match=%s",
                    match_id,
                )

                return response

            # ------------------------------------------------
            # PASSPORTS
            # ------------------------------------------------

            home_passport = (
                self.db.get_team_passport(
                    home_team_id,
                    season_id,
                )
            )

            away_passport = (
                self.db.get_team_passport(
                    away_team_id,
                    season_id,
                )
            )

            if not home_passport:
                raise ValueError(
                    "Нет паспорта хозяев: "
                    f"team_id={home_team_id}, "
                    f"season_id={season_id}"
                )

            if not away_passport:
                raise ValueError(
                    "Нет паспорта гостей: "
                    f"team_id={away_team_id}, "
                    f"season_id={season_id}"
                )

            # ------------------------------------------------
            # CURRENT RATINGS
            # ------------------------------------------------

            home_old_rating = _safe_float(
                home_passport.get("faj_rating"),
                DEFAULT_RATING,
            )

            away_old_rating = _safe_float(
                away_passport.get("faj_rating"),
                DEFAULT_RATING,
            )

            # ------------------------------------------------
            # EXPECTED RESULT
            # ------------------------------------------------

            expected_home = self._expected_result(
                home_old_rating,
                away_old_rating,
            )

            expected_away = (
                1.0 - expected_home
            )

            # ------------------------------------------------
            # ACTUAL RESULT
            # ------------------------------------------------

            actual_home = _result_score(
                home_goals,
                away_goals,
            )

            actual_away = (
                1.0 - actual_home
            )

            # ------------------------------------------------
            # RESULT COMPONENT
            # ------------------------------------------------

            home_result_component = (
                actual_home
                - expected_home
            )

            away_result_component = (
                actual_away
                - expected_away
            )

            # ------------------------------------------------
            # XG COMPONENT
            # ------------------------------------------------

            home_xg_component = (
                self._calculate_xg_component(
                    predicted_xg=home_predicted_xg,
                    observed_xg=home_observed_xg,
                )
            )

            away_xg_component = (
                self._calculate_xg_component(
                    predicted_xg=away_predicted_xg,
                    observed_xg=away_observed_xg,
                )
            )

            # ------------------------------------------------
            # RAW DELTA
            # ------------------------------------------------

            home_raw_delta = (
                home_result_component
                * K_FACTOR
                * RESULT_WEIGHT
            )

            home_raw_delta += (
                home_xg_component
                * K_FACTOR
                * XG_WEIGHT
            )

            away_raw_delta = (
                away_result_component
                * K_FACTOR
                * RESULT_WEIGHT
            )

            away_raw_delta += (
                away_xg_component
                * K_FACTOR
                * XG_WEIGHT
            )

            # ------------------------------------------------
            # ZERO-SUM NORMALIZATION
            # ------------------------------------------------

            rating_delta = (
                home_raw_delta
                - away_raw_delta
            ) / 2.0

            rating_delta = _clamp(
                rating_delta,
                -MAX_MATCH_DELTA,
                MAX_MATCH_DELTA,
            )

            # ------------------------------------------------
            # NEW RATINGS
            # ------------------------------------------------

            home_new_rating = _clamp(
                home_old_rating
                + rating_delta,
                MIN_RATING,
                MAX_RATING,
            )

            away_new_rating = _clamp(
                away_old_rating
                - rating_delta,
                MIN_RATING,
                MAX_RATING,
            )

            home_delta = (
                home_new_rating
                - home_old_rating
            )

            away_delta = (
                away_new_rating
                - away_old_rating
            )

            # ------------------------------------------------
            # SAVE HOME
            # ------------------------------------------------

            self._save_rating(
                team_id=home_team_id,
                season_id=season_id,
                passport=home_passport,
                old_rating=home_old_rating,
                new_rating=home_new_rating,
                match_id=match_id,
                opponent_team_id=away_team_id,
                result=home_goals,
                opponent_result=away_goals,
                observed_xg=home_observed_xg,
                predicted_xg=home_predicted_xg,
                expected_result=expected_home,
                actual_result=actual_home,
            )

            # ------------------------------------------------
            # SAVE AWAY
            # ------------------------------------------------

            self._save_rating(
                team_id=away_team_id,
                season_id=season_id,
                passport=away_passport,
                old_rating=away_old_rating,
                new_rating=away_new_rating,
                match_id=match_id,
                opponent_team_id=home_team_id,
                result=away_goals,
                opponent_result=home_goals,
                observed_xg=away_observed_xg,
                predicted_xg=away_predicted_xg,
                expected_result=expected_away,
                actual_result=actual_away,
            )

            # ------------------------------------------------
            # RESPONSE
            # ------------------------------------------------

            response["home"] = {
                "team_id": home_team_id,

                "rating_old": round(
                    home_old_rating,
                    4,
                ),

                "rating_new": round(
                    home_new_rating,
                    4,
                ),

                "delta": round(
                    home_delta,
                    4,
                ),

                "expected_result": round(
                    expected_home,
                    4,
                ),

                "actual_result": round(
                    actual_home,
                    4,
                ),

                "observed_xg": home_observed_xg,

                "predicted_xg": home_predicted_xg,

                "xg_component": round(
                    home_xg_component,
                    4,
                ),
            }

            response["away"] = {
                "team_id": away_team_id,

                "rating_old": round(
                    away_old_rating,
                    4,
                ),

                "rating_new": round(
                    away_new_rating,
                    4,
                ),

                "delta": round(
                    away_delta,
                    4,
                ),

                "expected_result": round(
                    expected_away,
                    4,
                ),

                "actual_result": round(
                    actual_away,
                    4,
                ),

                "observed_xg": away_observed_xg,

                "predicted_xg": away_predicted_xg,

                "xg_component": round(
                    away_xg_component,
                    4,
                ),
            }

            response["success"] = True

            logger.info(
                "ETC Club Rating updated: "
                "match=%s | "
                "home=%s %.4f -> %.4f | "
                "away=%s %.4f -> %.4f",
                match_id,
                home_team_id,
                home_old_rating,
                home_new_rating,
                away_team_id,
                away_old_rating,
                away_new_rating,
            )

            return response

        except Exception as exc:

            logger.exception(
                "ETC Club Rating update failed: "
                "match=%s",
                response.get("match_id"),
            )

            response["errors"].append(
                str(exc)
            )

            return response

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    def _already_processed(
        self,
        match_id: int,
        season_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> bool:
        """
        Проверяет, применялось ли ETC-изменение рейтинга
        к данному матчу.

        Проверка выполняется через team_history.

        Никаких DELETE/UPDATE истории здесь нет.
        """

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM team_history
                WHERE reference_match_id = ?
                  AND source = 'ETC'
                  AND field = 'faj_rating'
                  AND team_id IN (?, ?)
                """,
                (
                    match_id,
                    home_team_id,
                    away_team_id,
                ),
            )

            row = cursor.fetchone()

            if not row:
                return False

            count = _safe_int(
                row["cnt"]
                if hasattr(row, "keys")
                else row[0]
            )

            return count >= 2

        finally:
            conn.close()

    # ========================================================
    # EXPECTED RESULT
    # ========================================================

    @staticmethod
    def _expected_result(
        home_rating: float,
        away_rating: float,
    ) -> float:
        """
        Внутренняя rating-based оценка ожидаемого результата.

        Это НЕ букмекерская вероятность.

        Используется исключительно для расчёта
        величины изменения Club Rating.
        """

        difference = (
            home_rating
            - away_rating
            + HOME_ADVANTAGE
        )

        expected = (
            1.0
            / (
                1.0
                + 10.0 ** (
                    -difference / 10.0
                )
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
        Разница:

            Observed xG - Predicted xG

        > 0:
            фактическая атакующая продуктивность
            оказалась выше ожидаемой.

        < 0:
            фактическая продуктивность оказалась ниже
            ожидаемой.

        Влияние ограничено диапазоном [-1, +1].
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

        difference = (
            observed - predicted
        )

        return _clamp(
            difference,
            -1.0,
            1.0,
        )

    # ========================================================
    # SAVE RATING
    # ========================================================

    def _save_rating(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any],
        old_rating: float,
        new_rating: float,
        match_id: int,
        opponent_team_id: int,
        result: int,
        opponent_result: int,
        observed_xg: Optional[float],
        predicted_xg: Optional[float],
        expected_result: float,
        actual_result: float,
    ) -> None:
        """
        Сохраняет:

            1. новую версию паспорта;
            2. запись team_history;
            3. запись learning_memory.

        Старые записи не удаляются.
        """

        delta = (
            new_rating
            - old_rating
        )

        # ----------------------------------------------------
        # Нет изменения — ничего не сохраняем.
        # ----------------------------------------------------

        if abs(delta) < 0.000001:
            logger.info(
                "ETC Club Rating unchanged: "
                "team=%s match=%s",
                team_id,
                match_id,
            )
            return

        # ----------------------------------------------------
        # VERSION
        # ----------------------------------------------------

        old_version = passport.get(
            "version",
            "v1.0",
        )

        new_version = self._next_version(
            old_version
        )

        # ----------------------------------------------------
        # PASSPORT
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # TEAM HISTORY
        # ----------------------------------------------------

        self.db.record_team_history(
            team_id=team_id,
            season_id=season_id,
            field="faj_rating",
            old_value=str(
                round(
                    old_rating,
                    6,
                )
            ),
            new_value=str(
                round(
                    new_rating,
                    6,
                )
            ),
            reason=(
                "ETC post-match Club Rating update"
            ),
            source="ETC",
            reference_match_id=match_id,
        )

        # ----------------------------------------------------
        # LEARNING MEMORY
        # ----------------------------------------------------

        self.memory.record(
            event_type="club_rating_update",
            object_type=f"team:{team_id}",
            feature="faj_rating",
            before_value=round(
                old_rating,
                6,
            ),
            after_value=round(
                new_rating,
                6,
            ),
            delta=round(
                delta,
                6,
            ),
            reason=(
                "Post-match ETC rating correction"
            ),
            confidence=self._calculate_confidence(
                observed_xg=observed_xg,
                predicted_xg=predicted_xg,
            ),
            impact=abs(delta),
            algorithm=UPDATER_NAME,
            model_version=UPDATER_VERSION,
            reference_id=match_id,
        )

        logger.info(
            "ETC rating saved: "
            "team=%s | "
            "%.4f -> %.4f | "
            "delta=%+.4f | "
            "match=%s",
            team_id,
            old_rating,
            new_rating,
            delta,
            match_id,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @staticmethod
    def _calculate_confidence(
        observed_xg: Optional[float],
        predicted_xg: Optional[float],
    ) -> float:
        """
        Confidence записи ETC.

        Если есть и predicted xG, и observed xG,
        событие считается более информативным.

        Это НЕ вероятность результата матча.
        """

        if (
            observed_xg is not None
            and predicted_xg is not None
        ):
            return 1.0

        if observed_xg is not None:
            return 0.85

        return 0.70

    # ========================================================
    # VERSION
    # ========================================================

    @staticmethod
    def _next_version(
        version: str,
    ) -> str:
        """
        Версия паспорта:

            v1.0 -> v1.1
            v2.3 -> v2.4

        Если формат неизвестен:
            <version>.etc
        """

        try:

            if not isinstance(
                version,
                str,
            ):
                return "v1.0"

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

        except (
            ValueError,
            AttributeError,
        ):
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

    updater = ClubRatingUpdater(
        db=db
    )

    return updater.update_after_match(
        match=match,
        result=result,
        home_observed_xg=home_observed_xg,
        away_observed_xg=away_observed_xg,
        home_predicted_xg=home_predicted_xg,
        away_predicted_xg=away_predicted_xg,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    print("=" * 70)
    print(
        "FAJ ETC — Club Rating Updater"
    )
    print(
        f"Version: {UPDATER_VERSION}"
    )
    print("=" * 70)
    print(
        "Модуль предназначен для применения "
        "пост-матчевой коррекции Club Rating."
    )
    print(
        "Исторические факты не изменяются."
    )
    print(
        "Learning Memory ведётся append-only."
    )
    print("=" * 70)
