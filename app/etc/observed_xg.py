#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Evolution Training Center
Observed xG Engine v1.0
============================================================

НАЗНАЧЕНИЕ:

    Получение и нормализация фактического Observed xG
    после завершения матча.

АРХИТЕКТУРА:

    match
       │
       ├── Predictive xG
       │      └── НЕ изменяем
       │
       └── match_statistics
              └── фактический xG
                       │
                       ▼
                 Observed xG
                       │
                       ▼
                ETC / Calibration

ПРИНЦИПЫ:

    1. SQLite only.
    2. FAJDatabase — единый источник доступа к БД.
    3. Не удаляем данные.
    4. Не изменяем исторические факты.
    5. Не подменяем Observed xG фактическими голами.
    6. Не изменяем Predictive xG.
    7. Не изменяем FAJ Rating.
    8. Не изменяем model_parameters.
    9. Не выполняем обучение.
   10. Если Observed xG отсутствует — возвращаем статус
       missing, а не выдумываем значение.

Observed xG:

    match_statistics.xg

Predictive xG:

    matches.home_xg
    matches.away_xg

    и/или

    match_predictions.xg_home
    match_predictions.xg_away

ВАЖНО:

    Этот модуль является первым слоем ETC.

    Он только отвечает на вопрос:

        "Какой фактический xG был зафиксирован
         для завершённого матча?"

    Сравнение Predictive vs Observed выполняет
    следующий модуль:

        xg_calibration.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


ENGINE_NAME = "FAJ Observed xG Engine"
ENGINE_VERSION = "1.0"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _safe_float(value: Any) -> Optional[float]:
    """
    Безопасное преобразование значения в float.

    None / некорректное значение -> None.
    """
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """
    Безопасное преобразование значения в int.
    """
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# OBSERVED XG ENGINE
# ============================================================

class ObservedXGEngine:
    """
    FAJ Observed xG Engine v1.0.

    Отвечает только за получение фактического xG
    из match_statistics.

    Никакого обучения и изменения модели здесь нет.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC API
    # ========================================================

    def get_match_observed_xg(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Получает Observed xG одного матча.

        Возвращает нормализованный словарь:

        {
            "success": True/False,
            "status": "complete"/"missing"/"invalid"/"error",
            "match_id": ...,
            "home_team_id": ...,
            "away_team_id": ...,
            "observed_home_xg": ...,
            "observed_away_xg": ...,
            "source": "match_statistics",
            "quality": ...
        }
        """

        result: Dict[str, Any] = {
            "success": False,
            "status": "missing",
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "match_id": match_id,
            "home_team_id": None,
            "away_team_id": None,
            "observed_home_xg": None,
            "observed_away_xg": None,
            "source": "match_statistics",
            "quality": "unknown",
            "checked_at": _now(),
            "error": None,
        }

        try:
            # ------------------------------------------------
            # 1. Получаем матч
            # ------------------------------------------------

            match = self._get_match(match_id)

            if not match:
                result["status"] = "error"
                result["error"] = f"Матч {match_id} не найден."
                return result

            home_team_id = _safe_int(match.get("home_team_id"))
            away_team_id = _safe_int(match.get("away_team_id"))

            result["home_team_id"] = home_team_id
            result["away_team_id"] = away_team_id

            # ------------------------------------------------
            # 2. Получаем фактическую статистику
            # ------------------------------------------------

            statistics = self._get_match_statistics(match_id)

            if not statistics:
                result["status"] = "missing"
                result["quality"] = "no_statistics"
                return result

            # ------------------------------------------------
            # 3. Ищем xG по командам
            # ------------------------------------------------

            home_xg = None
            away_xg = None

            for row in statistics:
                team_id = _safe_int(row.get("team_id"))
                xg = _safe_float(row.get("xg"))

                if team_id is None or xg is None:
                    continue

                if team_id == home_team_id:
                    home_xg = xg

                elif team_id == away_team_id:
                    away_xg = xg

            result["observed_home_xg"] = home_xg
            result["observed_away_xg"] = away_xg

            # ------------------------------------------------
            # 4. Проверка полноты
            # ------------------------------------------------

            if home_xg is None and away_xg is None:
                result["status"] = "missing"
                result["quality"] = "xg_missing"
                return result

            if home_xg is None or away_xg is None:
                result["status"] = "invalid"
                result["quality"] = "partial_xg"
                return result

            # ------------------------------------------------
            # 5. Проверка диапазона
            # ------------------------------------------------

            if home_xg < 0 or away_xg < 0:
                result["status"] = "invalid"
                result["quality"] = "negative_xg"
                result["error"] = "Observed xG не может быть отрицательным."
                return result

            # ------------------------------------------------
            # 6. Всё хорошо
            # ------------------------------------------------

            result["success"] = True
            result["status"] = "complete"
            result["quality"] = "complete"

            return result

        except Exception as exc:
            logger.exception(
                "Observed xG error for match_id=%s",
                match_id,
            )

            result["status"] = "error"
            result["error"] = str(exc)

            return result

    # ========================================================
    # BATCH
    # ========================================================

    def get_observed_xg_for_matches(
        self,
        match_ids: List[int],
    ) -> List[Dict[str, Any]]:
        """
        Получает Observed xG для списка матчей.

        Никаких изменений БД.
        """

        results: List[Dict[str, Any]] = []

        for match_id in match_ids:
            results.append(
                self.get_match_observed_xg(match_id)
            )

        return results

    # ========================================================
    # COMPLETED MATCHES
    # ========================================================

    def get_completed_matches_with_observed_xg(
        self,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает завершённые матчи, для которых
        удалось получить полный Observed xG.

        ВАЖНО:

        Матч считается подходящим только если:

            home Observed xG != None
            AND
            away Observed xG != None
        """

        matches = self.db.get_matches()

        results: List[Dict[str, Any]] = []

        for match in matches:

            match_id = _safe_int(match.get("id"))

            if match_id is None:
                continue

            # Проверяем наличие фактического результата.
            match_result = self.db.get_match_result(match_id)

            if not match_result:
                continue

            home_goals = match_result.get("home_goals")
            away_goals = match_result.get("away_goals")

            if home_goals is None or away_goals is None:
                continue

            observed = self.get_match_observed_xg(match_id)

            if not observed["success"]:
                continue

            item = dict(match)

            item.update({
                "observed_home_xg": observed["observed_home_xg"],
                "observed_away_xg": observed["observed_away_xg"],
                "observed_xg_status": observed["status"],
                "observed_xg_quality": observed["quality"],
                "observed_xg_source": observed["source"],
            })

            results.append(item)

            if limit is not None and len(results) >= limit:
                break

        return results

    # ========================================================
    # DATABASE READERS
    # ========================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает матч.

        Используем FAJDatabase.get_matches(),
        чтобы не создавать новый DB API.
        """

        matches = self.db.get_matches()

        for match in matches:
            if _safe_int(match.get("id")) == match_id:
                return match

        return None

    def _get_match_statistics(
        self,
        match_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Получает фактическую статистику матча.

        database.py v12.1 не предоставляет отдельного
        публичного метода get_match_statistics().

        Поэтому используем существующий get_connection()
        только для READ.

        Никаких INSERT / UPDATE / DELETE.
        """

        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    match_id,
                    team_id,
                    possession,
                    shots,
                    shots_on_target,
                    corners,
                    fouls,
                    yellow_cards,
                    red_cards,
                    xg,
                    big_chances,
                    saves,
                    passes,
                    pass_accuracy
                FROM match_statistics
                WHERE match_id = ?
                ORDER BY team_id ASC, id ASC
                """,
                (match_id,),
            )

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()


# ============================================================
# PUBLIC FUNCTIONS
# ============================================================

def get_observed_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Удобный публичный API.

    Пример:

        result = get_observed_xg(match_id)

        if result["success"]:
            print(result["observed_home_xg"])
            print(result["observed_away_xg"])
    """

    engine = ObservedXGEngine(db=db)

    return engine.get_match_observed_xg(match_id)


def get_completed_matches_with_observed_xg(
    limit: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[Dict[str, Any]]:
    """
    Удобный публичный API для ETC.
    """

    engine = ObservedXGEngine(db=db)

    return engine.get_completed_matches_with_observed_xg(
        limit=limit
    )


# ============================================================
# SELF TEST / MANUAL EXECUTION
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    engine = ObservedXGEngine()

    print("=" * 70)
    print("FAJ OBSERVED xG ENGINE v1.0")
    print("=" * 70)

    matches = engine.get_completed_matches_with_observed_xg(
        limit=10
    )

    print(f"Матчей с Observed xG: {len(matches)}")

    for match in matches:
        print(
            f"{match.get('home_team_id')} "
            f"vs "
            f"{match.get('away_team_id')} | "
            f"Observed xG: "
            f"{match.get('observed_home_xg')} : "
            f"{match.get('observed_away_xg')}"
        )

    print("=" * 70)
