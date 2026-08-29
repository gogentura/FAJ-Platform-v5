#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
Observed xG v1.3
============================================================

app/etc/observed_xg.py

ИСПРАВЛЕНИЯ v1.3
============================================================

1. _read_source_xg() — REJECT, а не clamp
2. Используется db.get_match_statistics() вместо прямого SQL
3. Добавлена проверка завершённости матча
4. Разделены success и observed_xg_available
5. xg_calibration_available = observed_xg_available (НЕ fallback)
6. Добавлена проверка math.isfinite() в _safe_float

НАЗНАЧЕНИЕ
-----------
Получение и нормализация фактического xG матча
для Evolution Training Center (ETC).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


OBSERVED_XG_VERSION = "1.3"
MODULE_NAME = "FAJ ETC Observed xG"


# ============================================================
# CONSTANTS
# ============================================================

SOURCE_MATCH_STATISTICS = "match_statistics"
SOURCE_STATISTICAL_FALLBACK = "statistical_fallback"
SOURCE_UNAVAILABLE = None

SOURCE_XG_MIN = 0.0
SOURCE_XG_MAX = 10.0

FALLBACK_XG_MIN = 0.05
FALLBACK_XG_MAX = 5.0


# ============================================================
# SAFE CONVERSION
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование в float с проверкой на конечность.
    """
    if value is None:
        return default

    try:
        result = float(value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(result):
        return default

    return result


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _is_match_completed(match: Dict[str, Any]) -> bool:
    """Проверяет, завершён ли матч."""
    status = str(match.get("status", "")).lower()
    if status not in ("finished", "completed", "played", "ft"):
        return False

    fact_status = match.get("fact_status", "")
    if fact_status not in ("verified", "locked", "gold", "completed"):
        return False

    return True


# ============================================================
# OBSERVED XG ENGINE
# ============================================================

class ObservedXG:
    """
    FAJ ETC — Observed xG Engine v1.3.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC
    # ========================================================

    def get_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Получает нормализованный Observed xG для одного матча.

        ВАЖНО v1.3:
            - success означает "модуль успешно обработал матч"
            - observed_xg_available = оба значения из match_statistics
            - xg_calibration_available = observed_xg_available (НЕ fallback)
        """
        result: Dict[str, Any] = {
            "success": False,
            "module": MODULE_NAME,
            "version": OBSERVED_XG_VERSION,
            "match_id": match_id,
            "home_team_id": None,
            "away_team_id": None,
            "home_xg": None,
            "away_xg": None,
            "home_xg_source": SOURCE_UNAVAILABLE,
            "away_xg_source": SOURCE_UNAVAILABLE,
            "home_xg_observed": False,
            "away_xg_observed": False,
            "home_xg_fallback": False,
            "away_xg_fallback": False,
            "observed_xg_available": False,
            "fallback_used": False,
            "xg_calibration_available": False,
            "quality": "unknown",
            "confidence": 0.0,
            "home_statistics": {},
            "away_statistics": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # =================================================
            # STEP 1 — MATCH
            # =================================================

            match = self._get_match(match_id)
            if not match:
                result["errors"].append(f"Матч {match_id} не найден.")
                return result

            # Проверка завершённости (НОВОЕ v1.3)
            if not _is_match_completed(match):
                result["errors"].append(f"Матч {match_id} не завершён.")
                return result

            result["home_team_id"] = match.get("home_team_id")
            result["away_team_id"] = match.get("away_team_id")

            # =================================================
            # STEP 2 — MATCH STATISTICS (ИСПРАВЛЕНО v1.3)
            # =================================================

            statistics = self._get_match_statistics(match_id)

            if not statistics:
                result["errors"].append(f"Фактическая статистика матча {match_id} отсутствует.")
                return result

            # =================================================
            # STEP 3 — TEAM STATISTICS
            # =================================================

            home_stats = self._find_team_stats(statistics, result["home_team_id"])
            away_stats = self._find_team_stats(statistics, result["away_team_id"])

            result["home_statistics"] = home_stats or {}
            result["away_statistics"] = away_stats or {}

            if home_stats is None:
                result["warnings"].append("Статистика хозяев отсутствует.")
            if away_stats is None:
                result["warnings"].append("Статистика гостей отсутствует.")

            # =================================================
            # STEP 4 — PRIMARY OBSERVED XG (ИСПРАВЛЕНО v1.3)
            # =================================================

            home_xg = self._read_source_xg(home_stats)
            away_xg = self._read_source_xg(away_stats)

            if home_xg is not None:
                result["home_xg"] = home_xg
                result["home_xg_source"] = SOURCE_MATCH_STATISTICS
                result["home_xg_observed"] = True

            if away_xg is not None:
                result["away_xg"] = away_xg
                result["away_xg_source"] = SOURCE_MATCH_STATISTICS
                result["away_xg_observed"] = True

            # =================================================
            # STEP 5 — FALLBACK
            # =================================================

            if result["home_xg"] is None and home_stats:
                fallback = self._estimate_xg(home_stats)
                if fallback is not None:
                    result["home_xg"] = fallback
                    result["home_xg_source"] = SOURCE_STATISTICAL_FALLBACK
                    result["home_xg_fallback"] = True
                    result["warnings"].append("Home xG получен через statistical fallback.")

            if result["away_xg"] is None and away_stats:
                fallback = self._estimate_xg(away_stats)
                if fallback is not None:
                    result["away_xg"] = fallback
                    result["away_xg_source"] = SOURCE_STATISTICAL_FALLBACK
                    result["away_xg_fallback"] = True
                    result["warnings"].append("Away xG получен через statistical fallback.")

            # =================================================
            # STEP 6 — AVAILABILITY (ИСПРАВЛЕНО v1.3)
            # =================================================

            result["observed_xg_available"] = (
                result["home_xg_observed"] and result["away_xg_observed"]
            )

            result["fallback_used"] = (
                result["home_xg_fallback"] or result["away_xg_fallback"]
            )

            # ✅ xg_calibration_available = ТОЛЬКО observed_xg_available (НЕ fallback)
            result["xg_calibration_available"] = result["observed_xg_available"]

            # =================================================
            # STEP 7 — QUALITY
            # =================================================

            quality, confidence = self._calculate_quality(
                home_xg=result["home_xg"],
                away_xg=result["away_xg"],
                home_source=result["home_xg_source"],
                away_source=result["away_xg_source"],
            )

            result["quality"] = quality
            result["confidence"] = confidence

            # =================================================
            # STEP 8 — MISSING DATA
            # =================================================

            if result["home_xg"] is None:
                result["errors"].append("Home Observed xG отсутствует.")

            if result["away_xg"] is None:
                result["errors"].append("Away Observed xG отсутствует.")

            # =================================================
            # STEP 9 — SUCCESS (ИСПРАВЛЕНО v1.3)
            # =================================================

            # success = модуль успешно обработал матч
            # (даже если только fallback)
            result["success"] = (
                result["home_xg"] is not None and
                result["away_xg"] is not None
            )

            return result

        except Exception as exc:
            logger.exception("Observed xG error for match %s", match_id)
            result["errors"].append(str(exc))
            return result

    # ========================================================
    # MATCH
    # ========================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        try:
            matches = self.db.get_matches()
        except Exception:
            logger.exception("Unable to load matches")
            raise

        for match in matches:
            try:
                current_id = int(match.get("id", -1))
            except (TypeError, ValueError, AttributeError):
                continue

            if current_id == int(match_id):
                return dict(match)

        return None

    # ========================================================
    # MATCH STATISTICS (ИСПРАВЛЕНО v1.3)
    # ========================================================

    def _get_match_statistics(self, match_id: int) -> List[Dict[str, Any]]:
        """
        Получает фактическую статистику матча.

        ИСПРАВЛЕНО v1.3:
            Использует публичный метод db.get_match_statistics()
            вместо прямого SQL.
        """
        try:
            # Пробуем использовать публичный метод
            if hasattr(self.db, "get_match_statistics"):
                return self.db.get_match_statistics(match_id)

            # Fallback: прямой SELECT через get_connection()
            conn = self.db.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM match_statistics WHERE match_id = ? ORDER BY team_id ASC",
                    (match_id,),
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

        except Exception as exc:
            logger.warning("Failed to get match statistics: %s", exc)
            return []

    # ========================================================
    # SOURCE XG (ИСПРАВЛЕНО v1.3)
    # ========================================================

    @staticmethod
    def _read_source_xg(stats: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Читает xG непосредственно из статистики.

        ИСПРАВЛЕНО v1.3: REJECT, а не clamp.
        """
        if not stats:
            return None

        value = _safe_float(stats.get("xg"))
        if value is None:
            return None

        if value < SOURCE_XG_MIN:
            logger.warning("Observed xG below zero: %s", value)
            return None

        if value > SOURCE_XG_MAX:
            logger.warning("Observed xG unusually high: %s (max: %s)", value, SOURCE_XG_MAX)
            return None

        return round(value, 4)

    # ========================================================
    # TEAM STATISTICS
    # ========================================================

    @staticmethod
    def _find_team_stats(
        statistics: List[Dict[str, Any]],
        team_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if team_id is None:
            return None

        try:
            target_team_id = int(team_id)
        except (TypeError, ValueError):
            return None

        for row in statistics:
            try:
                row_team_id = int(row.get("team_id"))
            except (TypeError, ValueError, AttributeError):
                continue

            if row_team_id == target_team_id:
                return row

        return None

    # ========================================================
    # FALLBACK XG
    # ========================================================

    @staticmethod
    def _estimate_xg(stats: Dict[str, Any]) -> Optional[float]:
        """Расчётный fallback xG."""
        if not stats:
            return None

        shots = _safe_int(stats.get("shots"), 0)
        shots_on_target = _safe_int(stats.get("shots_on_target"), 0)
        big_chances = _safe_int(stats.get("big_chances"), 0)

        shots = max(0, shots)
        shots_on_target = max(0, shots_on_target)
        big_chances = max(0, big_chances)

        if shots <= 0 and shots_on_target <= 0 and big_chances <= 0:
            return None

        estimate = shots * 0.04
        estimate += shots_on_target * 0.12
        estimate += big_chances * 0.25

        if shots > 0:
            shot_accuracy = shots_on_target / shots
            estimate += shot_accuracy * 0.10

        estimate = _clamp(estimate, FALLBACK_XG_MIN, FALLBACK_XG_MAX)
        return round(estimate, 4)

    # ========================================================
    # QUALITY
    # ========================================================

    @staticmethod
    def _calculate_quality(
        home_xg: Optional[float],
        away_xg: Optional[float],
        home_source: Optional[str],
        away_source: Optional[str],
    ) -> tuple[str, float]:
        if home_xg is None or away_xg is None:
            return ("insufficient", 0.0)

        home_real = home_source == SOURCE_MATCH_STATISTICS
        away_real = away_source == SOURCE_MATCH_STATISTICS
        home_fallback = home_source == SOURCE_STATISTICAL_FALLBACK
        away_fallback = away_source == SOURCE_STATISTICAL_FALLBACK

        if home_real and away_real:
            return ("high", 1.0)

        if (home_real and away_fallback) or (away_real and home_fallback):
            return ("medium", 0.70)

        if home_fallback and away_fallback:
            return ("fallback", 0.40)

        return ("unknown", 0.0)


# ============================================================
# PUBLIC API
# ============================================================

def get_observed_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    engine = ObservedXG(db=db)
    return engine.get_match(match_id)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if len(sys.argv) < 2:
        print("Использование: python -m app.etc.observed_xg MATCH_ID")
        raise SystemExit(1)

    try:
        match_id = int(sys.argv[1])
    except ValueError:
        print("MATCH_ID должен быть числом.")
        raise SystemExit(1)

    data = get_observed_xg(match_id)

    print("=" * 70)
    print("FAJ ETC — OBSERVED xG v1.3")
    print("=" * 70)
    print(f"Матч: {data['match_id']}")
    print(f"Home xG: {data['home_xg']}")
    print(f"Away xG: {data['away_xg']}")
    print(f"Источник Home: {data['home_xg_source']}")
    print(f"Источник Away: {data['away_xg_source']}")
    print(f"Home observed: {data['home_xg_observed']}")
    print(f"Away observed: {data['away_xg_observed']}")
    print(f"Fallback used: {data['fallback_used']}")
    print(f"Observed available: {data['observed_xg_available']}")
    print(f"XG Calibration avail: {data['xg_calibration_available']}")
    print(f"Качество: {data['quality']}")
    print(f"Confidence: {data['confidence']}")
    print(f"Успех: {data['success']}")

    if data["warnings"]:
        print("\nПредупреждения:")
        for warning in data["warnings"]:
            print(f"  ⚠️ {warning}")

    if data["errors"]:
        print("\nОшибки:")
        for error in data["errors"]:
            print(f"  ❌ {error}")

    print("=" * 70)
