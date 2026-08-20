#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Evolution Training Center
Observed xG v1.0
============================================================

НАЗНАЧЕНИЕ:

    Получение и нормализация фактического xG матча
    для Evolution Training Center (ETC).

ВАЖНО:

    Predictive xG:
        matches.home_xg
        matches.away_xg

    Observed xG:
        match_statistics.xg

Observed xG — это ФАКТ после завершения матча.

МОДУЛЬ НЕ:

    - изменяет прогнозы;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - запускает обучение;
    - создаёт новые прогнозы;
    - удаляет данные;
    - изменяет match_results;
    - изменяет gold_dataset.

МОДУЛЬ:

    1. получает матч;
    2. получает фактическую статистику;
    3. извлекает xG, если он предоставлен источником;
    4. проверяет качество данных;
    5. при отсутствии xG может рассчитать fallback-оценку;
    6. возвращает унифицированный результат ETC.

SQLite only.
FAJDatabase — единственный источник доступа к БД.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


OBSERVED_XG_VERSION = "1.0"
MODULE_NAME = "FAJ ETC Observed xG v1.0"


# ============================================================
# SAFE CONVERSION
# ============================================================

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Безопасно преобразует значение в float.
    """
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """
    Безопасно преобразует значение в int.
    """
    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """
    Ограничивает значение диапазоном.
    """
    return max(minimum, min(maximum, value))


# ============================================================
# OBSERVED XG
# ============================================================

class ObservedXG:
    """
    FAJ ETC — Observed xG Engine.

    Отвечает только за фактический xG.

    Источник №1:
        match_statistics.xg

    Источник №2:
        fallback-расчёт из фактической статистики,
        если источник не предоставил xG.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC
    # ========================================================

    def get_match(self, match_id: int) -> Dict[str, Any]:
        """
        Получает Observed xG для одного завершённого матча.

        Возвращает унифицированную структуру.
        """

        result = {
            "success": False,
            "module": MODULE_NAME,
            "version": OBSERVED_XG_VERSION,
            "match_id": match_id,

            "home_team_id": None,
            "away_team_id": None,

            "home_xg": None,
            "away_xg": None,

            "home_xg_source": None,
            "away_xg_source": None,

            "home_statistics": {},
            "away_statistics": {},

            "quality": "unknown",
            "errors": [],
        }

        try:
            match = self._get_match(match_id)

            if not match:
                result["errors"].append(
                    f"Матч {match_id} не найден."
                )
                return result

            result["home_team_id"] = match.get("home_team_id")
            result["away_team_id"] = match.get("away_team_id")

            statistics = self._get_match_statistics(match_id)

            if not statistics:
                result["errors"].append(
                    f"Фактическая статистика для матча "
                    f"{match_id} отсутствует."
                )
                return result

            home_stats = self._find_team_stats(
                statistics,
                match.get("home_team_id")
            )

            away_stats = self._find_team_stats(
                statistics,
                match.get("away_team_id")
            )

            result["home_statistics"] = home_stats or {}
            result["away_statistics"] = away_stats or {}

            # ------------------------------------------------
            # PRIMARY SOURCE
            # ------------------------------------------------

            home_xg = _safe_float(
                home_stats.get("xg") if home_stats else None
            )

            away_xg = _safe_float(
                away_stats.get("xg") if away_stats else None
            )

            if home_xg is not None:
                result["home_xg"] = _clamp(home_xg, 0.0, 10.0)
                result["home_xg_source"] = "match_statistics"

            if away_xg is not None:
                result["away_xg"] = _clamp(away_xg, 0.0, 10.0)
                result["away_xg_source"] = "match_statistics"

            # ------------------------------------------------
            # FALLBACK
            # ------------------------------------------------

            if result["home_xg"] is None and home_stats:
                fallback = self._estimate_xg(home_stats)

                if fallback is not None:
                    result["home_xg"] = fallback
                    result["home_xg_source"] = "statistical_fallback"

            if result["away_xg"] is None and away_stats:
                fallback = self._estimate_xg(away_stats)

                if fallback is not None:
                    result["away_xg"] = fallback
                    result["away_xg_source"] = "statistical_fallback"

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            result["quality"] = self._calculate_quality(
                result["home_xg"],
                result["away_xg"],
                result["home_xg_source"],
                result["away_xg_source"],
            )

            if result["home_xg"] is None:
                result["errors"].append(
                    "Home Observed xG отсутствует."
                )

            if result["away_xg"] is None:
                result["errors"].append(
                    "Away Observed xG отсутствует."
                )

            result["success"] = (
                result["home_xg"] is not None
                and result["away_xg"] is not None
            )

            return result

        except Exception as exc:
            logger.exception(
                "Observed xG error for match %s",
                match_id
            )

            result["errors"].append(str(exc))
            return result

    # ========================================================
    # MATCH
    # ========================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает матч через FAJDatabase.
        """

        matches = self.db.get_matches()

        for match in matches:
            if int(match.get("id", -1)) == int(match_id):
                return dict(match)

        return None

    # ========================================================
    # MATCH STATISTICS
    # ========================================================

    def _get_match_statistics(
        self,
        match_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получает фактическую статистику матча.

        database.py v12.1 не предоставляет отдельного
        get_match_statistics(), поэтому используем
        существующее соединение FAJDatabase.

        Только SELECT.
        """

        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM match_statistics
                WHERE match_id = ?
                ORDER BY team_id ASC
                """,
                (match_id,)
            )

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    # ========================================================
    # TEAM STATISTICS
    # ========================================================

    @staticmethod
    def _find_team_stats(
        statistics: List[Dict[str, Any]],
        team_id: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """
        Находит статистику конкретной команды.
        """

        if team_id is None:
            return None

        for row in statistics:
            if row.get("team_id") == team_id:
                return row

        return None

    # ========================================================
    # FALLBACK XG
    # ========================================================

    def _estimate_xg(
        self,
        stats: Dict[str, Any]
    ) -> Optional[float]:
        """
        Fallback-оценка Observed xG.

        ВАЖНО:

        Это НЕ основная формула FAJ xG.

        Это только временная оценка фактического
        качества атакующих действий, если источник
        не предоставил xG.

        Приоритет:

            shots_on_target
            shots
            big_chances

        Не используем голы — Observed xG должен быть
        независим от фактического счёта.

        Формула:

            xG ≈
                shots * 0.04
                + shots_on_target * 0.10
                + big_chances * 0.20

        Затем ограничиваем диапазон [0.05, 5.0].
        """

        shots = _safe_int(stats.get("shots"), 0)
        shots_on_target = _safe_int(
            stats.get("shots_on_target"),
            0
        )
        big_chances = _safe_int(
            stats.get("big_chances"),
            0
        )

        if (
            shots <= 0
            and shots_on_target <= 0
            and big_chances <= 0
        ):
            return None

        estimate = (
            shots * 0.04
            + shots_on_target * 0.10
            + big_chances * 0.20
        )

        return round(
            _clamp(estimate, 0.05, 5.0),
            4
        )

    # ========================================================
    # QUALITY
    # ========================================================

    @staticmethod
    def _calculate_quality(
        home_xg: Optional[float],
        away_xg: Optional[float],
        home_source: Optional[str],
        away_source: Optional[str],
    ) -> str:
        """
        Определяет качество Observed xG.
        """

        if home_xg is None or away_xg is None:
            return "insufficient"

        if (
            home_source == "match_statistics"
            and away_source == "match_statistics"
        ):
            return "high"

        if (
            home_source == "match_statistics"
            or away_source == "match_statistics"
        ):
            return "medium"

        if (
            home_source == "statistical_fallback"
            and away_source == "statistical_fallback"
        ):
            return "fallback"

        return "unknown"


# ============================================================
# PUBLIC API
# ============================================================

def get_observed_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None
) -> Dict[str, Any]:
    """
    Удобная публичная функция.

    Пример:

        data = get_observed_xg(123)

        print(data["home_xg"])
        print(data["away_xg"])
    """

    engine = ObservedXG(db=db)

    return engine.get_match(match_id)


# ============================================================
# TEST / MANUAL EXECUTION
# ============================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    if len(sys.argv) < 2:
        print(
            "Использование:\n"
            "python -m app.etc.observed_xg MATCH_ID"
        )
        raise SystemExit(1)

    match_id = int(sys.argv[1])

    data = get_observed_xg(match_id)

    print("=" * 70)
    print("FAJ ETC — OBSERVED xG")
    print("=" * 70)
    print(f"Матч:       {data['match_id']}")
    print(f"Home xG:    {data['home_xg']}")
    print(f"Away xG:    {data['away_xg']}")
    print(f"Источник H: {data['home_xg_source']}")
    print(f"Источник A: {data['away_xg_source']}")
    print(f"Качество:   {data['quality']}")
    print(f"Успех:      {data['success']}")

    if data["errors"]:
        print("\nОшибки:")

        for error in data["errors"]:
            print(f"  ❌ {error}")

    print("=" * 70)
