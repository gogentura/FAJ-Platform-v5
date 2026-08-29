#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Club Rating Updater v3.1
============================================================

ФАЙЛ:
    app/etc/club_rating_updater.py

НАЗНАЧЕНИЕ:
    Контролируемое пост-матчевое изменение FAJ Club Rating.

АРХИТЕКТУРА:

    MATCH_RESULT
          │
          ├── Actual Score
          ├── Observed xG
          ├── Predicted xG
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
   12. Модуль применяет пост-матчевую ETC
       rating-коррекцию.
   13. Каждое изменение объяснимо.
   14. Запись одной ETC-операции атомарна.
   15. Частичная запись home/away запрещена.
   16. При ошибке транзакция откатывается.
   17. Повторный запуск уже обработанного матча
       не изменяет рейтинг повторно.

ИСПРАВЛЕНИЯ v3.1:
    1. Исправлен вызов приватного метода _is_match_fully_processed()
       на публичный is_match_fully_processed() (MUST FIX #1)
    2. Исправлено поле "object" на "object_type" в memory_data (MUST FIX #2)
    3. Версия обновлена до 3.1

ИСПРАВЛЕНИЯ v3.0:
    1. Интеграция с process_match_with_rating() из database.py
    2. Удалена ручная работа с транзакциями (делегировано в database.py)
    3. Удалён _begin_transaction() (используется process_match_with_rating)
    4. _already_processed() делегирует в _is_match_fully_processed()
    5. _save_rating() заменена на использование process_match_with_rating()
    6. Версия обновлена до 3.0

ВАЖНО:

    Этот модуль не является Prediction Model.

    Он работает ПОСЛЕ MATCH RESULT.

    Prediction:
        XG → Poisson → Monte Carlo → Prediction

    ETC:
        Prediction + Fact
              ↓
        Rating correction
              ↓
        Passport / History / Learning Memory

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple


from app.database import FAJDatabase
from app.etc.learning_memory import LearningMemory


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

UPDATER_VERSION = "3.1"
UPDATER_NAME = "FAJ ETC Club Rating Updater v3.1"


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
    """
    Безопасное преобразование значения в float.
    """

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
    """
    Безопасное преобразование значения в int.
    """

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
    """
    Ограничение значения диапазоном.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def _result_score(
    goals_for: int,
    goals_against: int,
) -> float:
    """
    Результат с точки зрения команды.

    Победа:
        1.0

    Ничья:
        0.5

    Поражение:
        0.0
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
    Исполнитель пост-матчевого изменения FAJ Club Rating.

    ВАЖНО:

        Этот класс не изменяет факты матча.

        Он не изменяет:
            match_results
            predictions

        Он только создаёт новую версию рейтинга
        и связанные исторические записи.

    Расчёт коррекции:

        RESULT
            +
        XG ERROR
            ↓
        Rating Delta
            ↓
        Passport
        Team History
        Learning Memory
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
    # PUBLIC — РАСЧЁТ РЕЙТИНГА БЕЗ СОХРАНЕНИЯ
    # ========================================================

    def calculate_rating_delta(
        self,
        home_rating: float,
        away_rating: float,
        home_goals: int,
        away_goals: int,
        home_observed_xg: Optional[float] = None,
        away_observed_xg: Optional[float] = None,
        home_predicted_xg: Optional[float] = None,
        away_predicted_xg: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Рассчитывает дельту рейтинга для обеих команд.

        Возвращает:
            (home_delta, away_delta)
        """
        home_rating = _clamp(home_rating, MIN_RATING, MAX_RATING)
        away_rating = _clamp(away_rating, MIN_RATING, MAX_RATING)

        # Ожидаемый результат
        expected_home = self._expected_result(home_rating, away_rating)
        expected_away = 1.0 - expected_home

        # Фактический результат
        actual_home = _result_score(home_goals, away_goals)
        actual_away = 1.0 - actual_home

        # Результативная компонента
        home_result_component = actual_home - expected_home
        away_result_component = actual_away - expected_away

        # xG компонента
        home_xg_component = self._calculate_xg_component(
            predicted_xg=home_predicted_xg,
            observed_xg=home_observed_xg,
        )

        away_xg_component = self._calculate_xg_component(
            predicted_xg=away_predicted_xg,
            observed_xg=away_observed_xg,
        )

        # Сырые дельты
        home_raw_delta = (
            home_result_component * K_FACTOR * RESULT_WEIGHT
            + home_xg_component * K_FACTOR * XG_WEIGHT
        )

        away_raw_delta = (
            away_result_component * K_FACTOR * RESULT_WEIGHT
            + away_xg_component * K_FACTOR * XG_WEIGHT
        )

        # Zero-sum нормализация
        rating_delta = (home_raw_delta - away_raw_delta) / 2.0
        rating_delta = _clamp(rating_delta, -MAX_MATCH_DELTA, MAX_MATCH_DELTA)

        return rating_delta, -rating_delta

    # ========================================================
    # PUBLIC — ПОЛНОЕ ОБНОВЛЕНИЕ С СОХРАНЕНИЕМ
    # ========================================================

    def update_after_match(
        self,
        match: Dict[str, Any],
        result: Dict[str, Any],
        home_observed_xg: Optional[float] = None,
        away_observed_xg: Optional[float] = None,
        home_predicted_xg: Optional[float] = None,
        away_predicted_xg: Optional[float] = None,
        analysis_memory_data: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Применяет одну ETC rating-коррекцию к завершённому матчу.

        Использует атомарный process_match_with_rating() из database.py.

        Вся операция выполняется атомарно.

        При любой ошибке:
            Passport, Team History, Learning Memory — ROLLBACK.

        Args:
            match: словарь матча
            result: словарь результата
            home_observed_xg: фактический xG home
            away_observed_xg: фактический xG away
            home_predicted_xg: предсказанный xG home
            away_predicted_xg: предсказанный xG away
            analysis_memory_data: список events для learning_memory

        Returns:
            Dict с результатами
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

            # =================================================
            # 1. VALIDATE MATCH
            # =================================================

            if not isinstance(match, dict):
                raise ValueError("match должен быть dict.")

            if not isinstance(result, dict):
                raise ValueError("result должен быть dict.")

            # =================================================
            # 2. IDENTIFIERS
            # =================================================

            match_id = _safe_int(match.get("id"))
            home_team_id = _safe_int(match.get("home_team_id"))
            away_team_id = _safe_int(match.get("away_team_id"))
            season_id = _safe_int(match.get("season_id"))

            response["match_id"] = match_id

            if not match_id:
                raise ValueError("отсутствует match_id.")

            if not home_team_id:
                raise ValueError("отсутствует home_team_id.")

            if not away_team_id:
                raise ValueError("отсутствует away_team_id.")

            if not season_id:
                raise ValueError("отсутствует season_id.")

            if home_team_id == away_team_id:
                raise ValueError("home_team_id и away_team_id совпадают.")

            # =================================================
            # 3. RESULT
            # =================================================

            home_goals = _safe_int(result.get("home_goals"))
            away_goals = _safe_int(result.get("away_goals"))

            if home_goals < 0:
                raise ValueError("home_goals не может быть отрицательным.")

            if away_goals < 0:
                raise ValueError("away_goals не может быть отрицательным.")

            # =================================================
            # 4. CHECK FULLY PROCESSED
            # =================================================

            # ✅ ИСПРАВЛЕНИЕ MUST FIX #1: использование публичного метода
            if self.db.is_match_fully_processed(match_id):
                response["success"] = True
                response["already_processed"] = True
                response["home"] = {"team_id": home_team_id, "status": "already_processed"}
                response["away"] = {"team_id": away_team_id, "status": "already_processed"}

                logger.info("ETC Club Rating already processed: match=%s", match_id)
                return response

            # =================================================
            # 5. GET CURRENT RATINGS
            # =================================================

            home_passport = self.db.get_team_passport(home_team_id, season_id)
            away_passport = self.db.get_team_passport(away_team_id, season_id)

            if not home_passport:
                raise ValueError(f"Нет паспорта хозяев: team_id={home_team_id}, season_id={season_id}")

            if not away_passport:
                raise ValueError(f"Нет паспорта гостей: team_id={away_team_id}, season_id={season_id}")

            home_old_rating = _clamp(
                _safe_float(home_passport.get("faj_rating"), DEFAULT_RATING),
                MIN_RATING, MAX_RATING,
            )

            away_old_rating = _clamp(
                _safe_float(away_passport.get("faj_rating"), DEFAULT_RATING),
                MIN_RATING, MAX_RATING,
            )

            # =================================================
            # 6. CALCULATE DELTA
            # =================================================

            home_delta, away_delta = self.calculate_rating_delta(
                home_rating=home_old_rating,
                away_rating=away_old_rating,
                home_goals=home_goals,
                away_goals=away_goals,
                home_observed_xg=home_observed_xg,
                away_observed_xg=away_observed_xg,
                home_predicted_xg=home_predicted_xg,
                away_predicted_xg=away_predicted_xg,
            )

            home_new_rating = _clamp(home_old_rating + home_delta, MIN_RATING, MAX_RATING)
            away_new_rating = _clamp(away_old_rating + away_delta, MIN_RATING, MAX_RATING)

            # =================================================
            # 7. BUILD REASONS
            # =================================================

            home_reason = self._build_reason(
                team_id=home_team_id,
                opponent_id=away_team_id,
                goals_for=home_goals,
                goals_against=away_goals,
                observed_xg=home_observed_xg,
                predicted_xg=home_predicted_xg,
                rating_delta=home_delta,
            )

            away_reason = self._build_reason(
                team_id=away_team_id,
                opponent_id=home_team_id,
                goals_for=away_goals,
                goals_against=home_goals,
                observed_xg=away_observed_xg,
                predicted_xg=away_predicted_xg,
                rating_delta=away_delta,
            )

            # =================================================
            # 8. BUILD ANALYSIS MEMORY DATA
            # =================================================

            memory_events = analysis_memory_data or []

            # Добавляем rating update events
            memory_events.append({
                "event_type": "club_rating_update",
                "object_type": f"team:{home_team_id}",  # ✅ ИСПРАВЛЕНИЕ MUST FIX #2
                "feature": "faj_rating",
                "before_value": round(home_old_rating, 4),
                "after_value": round(home_new_rating, 4),
                "delta": round(home_delta, 4),
                "reason": f"Post-match ETC rating correction (match {match_id})",
                "confidence": self._calculate_confidence(home_observed_xg, home_predicted_xg),
                "impact": abs(home_delta),
                "algorithm": UPDATER_NAME,
                "model_version": UPDATER_VERSION,
                "reference_id": match_id,
                "created_at": None,
            })

            memory_events.append({
                "event_type": "club_rating_update",
                "object_type": f"team:{away_team_id}",  # ✅ ИСПРАВЛЕНИЕ MUST FIX #2
                "feature": "faj_rating",
                "before_value": round(away_old_rating, 4),
                "after_value": round(away_new_rating, 4),
                "delta": round(away_delta, 4),
                "reason": f"Post-match ETC rating correction (match {match_id})",
                "confidence": self._calculate_confidence(away_observed_xg, away_predicted_xg),
                "impact": abs(away_delta),
                "algorithm": UPDATER_NAME,
                "model_version": UPDATER_VERSION,
                "reference_id": match_id,
                "created_at": None,
            })

            # =================================================
            # 9. АТОМАРНОЕ СОХРАНЕНИЕ ЧЕРЕЗ DATABASE.PY
            # =================================================

            # Преобразуем memory_events в формат для process_match_with_rating
            memory_data = []
            for event in memory_events:
                memory_data.append({
                    "event_type": event.get("event_type"),
                    "object_type": event.get("object_type"),  # ✅ ИСПРАВЛЕНИЕ MUST FIX #2
                    "feature": event.get("feature"),
                    "before_value": event.get("before_value"),
                    "after_value": event.get("after_value"),
                    "delta": event.get("delta"),
                    "reason": event.get("reason"),
                    "confidence": event.get("confidence", 1.0),
                    "impact": event.get("impact", 0.0),
                    "algorithm": event.get("algorithm", UPDATER_NAME),
                    "model_version": event.get("model_version", UPDATER_VERSION),
                    "reference_id": event.get("reference_id", match_id),
                    "created_at": event.get("created_at"),
                })

            result = self.db.process_match_with_rating(
                match_id=match_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                season_id=season_id,
                home_goals=home_goals,
                away_goals=away_goals,
                home_rating_before=home_old_rating,
                away_rating_before=away_old_rating,
                home_rating_after=home_new_rating,
                away_rating_after=away_new_rating,
                home_delta=home_delta,
                away_delta=away_delta,
                home_reason=home_reason,
                away_reason=away_reason,
                analysis_memory_data=memory_data if memory_data else None,
            )

            # =================================================
            # 10. RESPONSE
            # =================================================

            if result.get("status") == "already_processed":
                response["success"] = True
                response["already_processed"] = True
                response["home"] = {"team_id": home_team_id, "status": "already_processed"}
                response["away"] = {"team_id": away_team_id, "status": "already_processed"}
                return response

            response["success"] = True
            response["home"] = {
                "team_id": home_team_id,
                "rating_old": round(home_old_rating, 4),
                "rating_new": round(home_new_rating, 4),
                "delta": round(home_delta, 4),
                "history_id": result.get("history_ids", [None, None])[0],
            }
            response["away"] = {
                "team_id": away_team_id,
                "rating_old": round(away_old_rating, 4),
                "rating_new": round(away_new_rating, 4),
                "delta": round(away_delta, 4),
                "history_id": result.get("history_ids", [None, None])[1],
            }
            response["marker_id"] = result.get("marker_id")

            logger.info(
                "ETC Club Rating updated: match=%s | home=%s %.4f -> %.4f | away=%s %.4f -> %.4f",
                match_id, home_team_id, home_old_rating, home_new_rating,
                away_team_id, away_old_rating, away_new_rating,
            )

            return response

        except Exception as exc:

            logger.exception("ETC Club Rating update failed: match=%s", response.get("match_id"))
            response["errors"].append(str(exc))
            return response

    # ========================================================
    # ВНУТРЕННИЕ МЕТОДЫ
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

        difference = home_rating - away_rating + HOME_ADVANTAGE
        expected = 1.0 / (1.0 + 10.0 ** (-difference / 10.0))
        return _clamp(expected, 0.05, 0.95)

    @staticmethod
    def _calculate_xg_component(
        predicted_xg: Optional[float],
        observed_xg: Optional[float],
    ) -> float:
        """
        Разница: Observed xG - Predicted xG

        > 0: фактическая атакующая продуктивность выше ожидаемой
        < 0: фактическая продуктивность ниже ожидаемой

        Влияние ограничено диапазоном [-1, +1].
        """
        if predicted_xg is None or observed_xg is None:
            return 0.0

        difference = _safe_float(observed_xg) - _safe_float(predicted_xg)
        return _clamp(difference, -1.0, 1.0)

    @staticmethod
    def _calculate_confidence(
        observed_xg: Optional[float],
        predicted_xg: Optional[float],
    ) -> float:
        """Confidence записи ETC."""
        if observed_xg is not None and predicted_xg is not None:
            return 1.0
        if observed_xg is not None:
            return 0.85
        return 0.70

    @staticmethod
    def _build_reason(
        team_id: int,
        opponent_id: int,
        goals_for: int,
        goals_against: int,
        observed_xg: Optional[float],
        predicted_xg: Optional[float],
        rating_delta: float,
    ) -> str:
        """Формирует читаемое объяснение изменения рейтинга."""
        xg_part = ""
        if observed_xg is not None and predicted_xg is not None:
            xg_diff = observed_xg - predicted_xg
            xg_part = f" | xG diff: {xg_diff:+.2f} (obs: {observed_xg:.2f}, pred: {predicted_xg:.2f})"

        result_text = "win" if goals_for > goals_against else "draw" if goals_for == goals_against else "loss"

        return (
            f"team {team_id} vs {opponent_id}: "
            f"{goals_for}-{goals_against} ({result_text}), "
            f"delta: {rating_delta:+.4f}{xg_part}"
        )


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
    analysis_memory_data: Optional[list] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API ETC Club Rating Updater.
    """
    updater = ClubRatingUpdater(db=db)
    return updater.update_after_match(
        match=match,
        result=result,
        home_observed_xg=home_observed_xg,
        away_observed_xg=away_observed_xg,
        home_predicted_xg=home_predicted_xg,
        away_predicted_xg=away_predicted_xg,
        analysis_memory_data=analysis_memory_data,
    )


def calculate_rating_delta(
    home_rating: float,
    away_rating: float,
    home_goals: int,
    away_goals: int,
    home_observed_xg: Optional[float] = None,
    away_observed_xg: Optional[float] = None,
    home_predicted_xg: Optional[float] = None,
    away_predicted_xg: Optional[float] = None,
) -> Tuple[float, float]:
    """
    Публичный API для расчёта дельты рейтинга без сохранения.
    """
    updater = ClubRatingUpdater()
    return updater.calculate_rating_delta(
        home_rating=home_rating,
        away_rating=away_rating,
        home_goals=home_goals,
        away_goals=away_goals,
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
    print("FAJ ETC — Club Rating Updater")
    print(f"Version: {UPDATER_VERSION}")
    print("=" * 70)

    # Пример расчёта
    home_rating = 70.0
    away_rating = 65.0
    home_goals = 2
    away_goals = 1
    home_obs_xg = 2.1
    away_obs_xg = 1.2
    home_pred_xg = 1.8
    away_pred_xg = 1.1

    home_delta, away_delta = calculate_rating_delta(
        home_rating=home_rating,
        away_rating=away_rating,
        home_goals=home_goals,
        away_goals=away_goals,
        home_observed_xg=home_obs_xg,
        away_observed_xg=away_obs_xg,
        home_predicted_xg=home_pred_xg,
        away_predicted_xg=away_pred_xg,
    )

    print("Пример расчёта:")
    print(f"  Home: {home_rating:.2f} -> {home_rating + home_delta:.2f} (delta: {home_delta:+.4f})")
    print(f"  Away: {away_rating:.2f} -> {away_rating + away_delta:.2f} (delta: {away_delta:+.4f})")
    print("")
    print("Модуль предназначен для применения пост-матчевой коррекции Club Rating.")
    print("Исторические факты не изменяются.")
    print("Learning Memory ведётся append-only.")
    print("Операция Passport + History + Learning Memory выполняется атомарно через database.py.")
    print("=" * 70)
