#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/xg_calibration.py
============================================================

XG CALIBRATION v2.2
============================================================

ИСПРАВЛЕНИЯ v2.2
============================================================

1. _get_predictive_xg() — REJECT, а не clamp (MAX_XG)
2. Убран clamp для xg_deviation (согласован с absolute_error)
3. matches_analyzed переименован в matches_with_predictive_xg
4. Добавлена проверка завершённости матча (fact_status)
5. Добавлена дедупликация по match_id
6. Добавлена проверка math.isfinite() в _safe_float
7. eligible_for_learning учитывает source_quality

НАЗНАЧЕНИЕ
-----------

Сравнение исторического Predictive xG FAJ
с фактическим Observed xG после завершения матча.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Set

from app.database import FAJDatabase
from app.etc.observed_xg import ObservedXG


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.2"
CALIBRATION_VERSION = "2.2"
MODULE_NAME = "FAJ ETC XG Calibration"


# ============================================================
# CONFIGURATION
# ============================================================

MIN_MATCHES_FOR_STABLE_SIGNAL = 3
MIN_MATCHES_FOR_DEVELOPING_SIGNAL = 2
CALIBRATION_EPSILON = 0.05
MAX_DEVIATION = 3.0
MAX_XG = 10.0


# ============================================================
# SAFE HELPERS
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
    default: Optional[int] = None,
) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_match_completed(match: Dict[str, Any]) -> bool:
    """
    Проверяет, завершён ли матч и имеет ли факт.
    """
    status = match.get("status", "")
    if str(status).lower() not in ("finished", "completed", "played", "ft"):
        return False

    fact_status = match.get("fact_status", "")
    if fact_status not in ("verified", "locked", "gold", "completed"):
        return False

    return True


# ============================================================
# XG CALIBRATION
# ============================================================

class XGCalibration:
    """
    ETC XG Calibration v2.2.

    Только аналитический слой. Никаких изменений БД.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        observed_xg: Optional[ObservedXG] = None,
    ) -> None:
        self.db = db or FAJDatabase()
        self.observed_xg = observed_xg or ObservedXG(db=self.db)

    # ========================================================
    # PUBLIC — MULTI MATCH
    # ========================================================

    def calibrate_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Рассчитывает XG Calibration по набору завершённых матчей.
        """

        result: Dict[str, Any] = {
            "success": False,
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "matches_received": len(matches),
            "matches_with_predictive_xg": 0,      # переименовано v2.2
            "matches_with_valid_pair": 0,         # НОВОЕ v2.2
            "teams_analyzed": 0,
            "team_calibrations": [],
            "calibration_signals": [],
            "errors": [],
        }

        try:
            # Дедупликация по match_id (НОВОЕ v2.2)
            unique_matches = self._deduplicate_matches(matches)

            # Фильтрация завершённых матчей (НОВОЕ v2.2)
            completed_matches = [
                m for m in unique_matches
                if _is_match_completed(m)
            ]

            if len(completed_matches) < len(unique_matches):
                skipped = len(unique_matches) - len(completed_matches)
                logger.info("Skipped %s incomplete matches", skipped)

            team_data = self._collect_team_xg(completed_matches)

            result["matches_with_predictive_xg"] = self._count_with_predictive_xg(
                completed_matches
            )
            result["matches_with_valid_pair"] = self._count_with_valid_pair(
                team_data
            )
            result["teams_analyzed"] = len(team_data)

            calibrations: List[Dict[str, Any]] = []
            signals: List[Dict[str, Any]] = []

            for team_id, data in team_data.items():
                calibration = self._calculate_team_calibration(
                    team_id=team_id,
                    data=data,
                )
                if calibration is None:
                    continue

                calibrations.append(calibration)

                signal = self._build_calibration_signal(calibration)
                if signal is not None:
                    signals.append(signal)

            result["team_calibrations"] = calibrations
            result["calibration_signals"] = signals
            result["success"] = True

            logger.info(
                "XG Calibration completed: received=%s completed=%s teams=%s signals=%s",
                result["matches_received"],
                len(completed_matches),
                result["teams_analyzed"],
                len(signals),
            )

            return result

        except Exception as exc:
            logger.exception("XG Calibration failed")
            result["errors"].append(str(exc))
            return result

    # ========================================================
    # PUBLIC — SINGLE MATCH
    # ========================================================

    def calibrate_match(self, match_id: int) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "success": False,
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "match_id": match_id,
            "teams": [],
            "signals": [],
            "errors": [],
        }

        try:
            match = self._get_match(match_id)
            if not match:
                result["errors"].append(f"Матч {match_id} не найден.")
                return result

            if not _is_match_completed(match):
                result["errors"].append(f"Матч {match_id} не завершён.")
                return result

            team_data = self._collect_team_xg([match])

            for team_id, data in team_data.items():
                calibration = self._calculate_team_calibration(
                    team_id=team_id,
                    data=data,
                )
                if calibration is None:
                    continue

                result["teams"].append(calibration)

                signal = self._build_calibration_signal(calibration)
                if signal is not None:
                    result["signals"].append(signal)

            result["success"] = True
            return result

        except Exception as exc:
            logger.exception("XG Calibration failed for match_id=%s", match_id)
            result["errors"].append(str(exc))
            return result

    # ========================================================
    # DEDUPLICATION (НОВОЕ v2.2)
    # ========================================================

    @staticmethod
    def _deduplicate_matches(
        matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Удаляет дубликаты по match_id."""
        seen: Set[int] = set()
        result: List[Dict[str, Any]] = []

        for match in matches:
            match_id = _safe_int(match.get("id"))
            if match_id is None or match_id <= 0:
                continue
            if match_id in seen:
                continue
            seen.add(match_id)
            result.append(match)

        return result

    # ========================================================
    # MATCH LOADING
    # ========================================================

    def _get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        matches = self.db.get_matches()
        target_id = _safe_int(match_id)
        if target_id is None:
            return None

        for raw_match in matches:
            match = dict(raw_match)
            current_id = _safe_int(match.get("id"))
            if current_id == target_id:
                return match

        return None

    # ========================================================
    # COLLECT TEAM XG
    # ========================================================

    def _collect_team_xg(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        """
        Собирает валидные пары Predictive xG ↔ Observed xG.
        """
        teams: Dict[int, Dict[str, Any]] = {}

        for raw_match in matches:
            match = dict(raw_match)
            match_id = _safe_int(match.get("id"))
            home_team_id = _safe_int(match.get("home_team_id"))
            away_team_id = _safe_int(match.get("away_team_id"))

            if None in (match_id, home_team_id, away_team_id):
                continue

            predictive_home = self._get_predictive_xg(match.get("home_xg"))
            predictive_away = self._get_predictive_xg(match.get("away_xg"))

            # Observed xG
            observed_result = self.observed_xg.get_match(match_id)
            if not observed_result.get("success"):
                continue

            # Используем только observed_xg_available (НОВОЕ v2.2)
            if not observed_result.get("observed_xg_available", False):
                continue

            observed_home = _safe_float(observed_result.get("home_xg"))
            observed_away = _safe_float(observed_result.get("away_xg"))

            # HOME
            if predictive_home is not None and observed_home is not None:
                self._append_observation(
                    teams=teams,
                    team_id=home_team_id,
                    match_id=match_id,
                    predictive_xg=predictive_home,
                    observed_xg=observed_home,
                    venue="home",
                    observed_source=observed_result.get("home_xg_source"),
                )

            # AWAY
            if predictive_away is not None and observed_away is not None:
                self._append_observation(
                    teams=teams,
                    team_id=away_team_id,
                    match_id=match_id,
                    predictive_xg=predictive_away,
                    observed_xg=observed_away,
                    venue="away",
                    observed_source=observed_result.get("away_xg_source"),
                )

        return teams

    # ========================================================
    # PREDICTIVE XG (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def _get_predictive_xg(value: Any) -> Optional[float]:
        """
        Получает исторический Predictive xG.

        ВАЖНО: REJECT, а не clamp.
        """
        xg = _safe_float(value)
        if xg is None:
            return None
        if xg < 0:
            return None
        if xg > MAX_XG:
            logger.warning("Predictive xG вне допустимого диапазона: %s (MAX_XG=%s)", xg, MAX_XG)
            return None
        return xg

    # ========================================================
    # APPEND OBSERVATION
    # ========================================================

    @staticmethod
    def _append_observation(
        teams: Dict[int, Dict[str, Any]],
        team_id: int,
        match_id: int,
        predictive_xg: float,
        observed_xg: float,
        venue: str,
        observed_source: Optional[str],
    ) -> None:
        if team_id not in teams:
            teams[team_id] = {
                "team_id": team_id,
                "matches": [],
                "predictive_xg": [],
                "observed_xg": [],
                "deviations": [],
                "venues": [],
                "observed_sources": [],
            }

        deviation = observed_xg - predictive_xg
        teams[team_id]["matches"].append(match_id)
        teams[team_id]["predictive_xg"].append(predictive_xg)
        teams[team_id]["observed_xg"].append(observed_xg)
        teams[team_id]["deviations"].append(deviation)
        teams[team_id]["venues"].append(venue)
        teams[team_id]["observed_sources"].append(observed_source)

    # ========================================================
    # CALCULATION
    # ========================================================

    def _calculate_team_calibration(
        self,
        team_id: int,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        predictive = data.get("predictive_xg", [])
        observed = data.get("observed_xg", [])
        deviations = data.get("deviations", [])
        matches = data.get("matches", [])

        sample_size = min(len(predictive), len(observed), len(deviations), len(matches))

        if sample_size <= 0:
            return None

        predictive_avg = sum(predictive[:sample_size]) / sample_size
        observed_avg = sum(observed[:sample_size]) / sample_size

        # raw deviation (без clamp) — ИСПРАВЛЕНО v2.2
        mean_deviation = sum(deviations[:sample_size]) / sample_size
        absolute_error = sum(abs(d) for d in deviations[:sample_size]) / sample_size

        direction = self._determine_direction(mean_deviation)
        signal_strength = self._calculate_signal_strength(mean_deviation)
        reliability = self._determine_reliability(sample_size)
        source_quality = self._calculate_source_quality(data.get("observed_sources", []))

        # НОВОЕ v2.2: home/away decomposition
        venues = data.get("venues", [])
        home_count = sum(1 for v in venues[:sample_size] if v == "home")
        away_count = sample_size - home_count

        return {
            "team_id": team_id,
            "sample_size": sample_size,
            "matches_count": sample_size,
            "match_ids": matches[:sample_size],
            "predictive_xg_avg": round(predictive_avg, 4),
            "observed_xg_avg": round(observed_avg, 4),
            "xg_deviation": round(mean_deviation, 4),  # ← без clamp
            "absolute_error": round(absolute_error, 4),
            "direction": direction,
            "signal_strength": round(signal_strength, 4),
            "reliability": reliability,
            "observed_source_quality": source_quality,
            # НОВОЕ v2.2: home/away decomposition
            "home_count": home_count,
            "away_count": away_count,
            "home_deviation": None,  # можно добавить при необходимости
            "away_deviation": None,
            "calibration_version": CALIBRATION_VERSION,
        }

    # ========================================================
    # DIRECTION
    # ========================================================

    @staticmethod
    def _determine_direction(deviation: float) -> str:
        if deviation > CALIBRATION_EPSILON:
            return "underestimated"
        if deviation < -CALIBRATION_EPSILON:
            return "overestimated"
        return "calibrated"

    # ========================================================
    # SIGNAL STRENGTH
    # ========================================================

    @staticmethod
    def _calculate_signal_strength(deviation: float) -> float:
        """Преобразует отклонение в силу сигнала 0..1."""
        return round(max(0.0, min(1.0, abs(deviation))), 4)

    # ========================================================
    # RELIABILITY
    # ========================================================

    @staticmethod
    def _determine_reliability(sample_size: int) -> str:
        if sample_size >= MIN_MATCHES_FOR_STABLE_SIGNAL:
            return "stable"
        if sample_size >= MIN_MATCHES_FOR_DEVELOPING_SIGNAL:
            return "developing"
        return "weak"

    # ========================================================
    # SOURCE QUALITY
    # ========================================================

    @staticmethod
    def _calculate_source_quality(sources: List[Any]) -> str:
        normalized = [str(s) for s in sources if s]
        if not normalized:
            return "unknown"

        primary_count = sum(1 for s in normalized if s == "match_statistics")
        if primary_count == len(normalized):
            return "high"
        if primary_count > 0:
            return "medium"
        if all(s == "statistical_fallback" for s in normalized):
            return "fallback"
        return "unknown"

    # ========================================================
    # CALIBRATION SIGNAL (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def _build_calibration_signal(
        calibration: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not calibration:
            return None

        sample_size = calibration.get("sample_size", 0)
        deviation = calibration.get("xg_deviation", 0.0)
        signal_strength = calibration.get("signal_strength", 0.0)
        reliability = calibration.get("reliability", "weak")
        source_quality = calibration.get("observed_source_quality", "unknown")

        if sample_size <= 0:
            return None

        # eligible_for_learning учитывает source_quality (НОВОЕ v2.2)
        eligible = (
            sample_size >= MIN_MATCHES_FOR_STABLE_SIGNAL
            and reliability == "stable"
            and source_quality in ("high", "medium")
        )

        return {
            "signal_type": "xg_calibration",
            "team_id": calibration.get("team_id"),
            "sample_size": sample_size,
            "xg_deviation": deviation,
            "absolute_error": calibration.get("absolute_error", 0.0),
            "direction": calibration.get("direction"),
            "signal_strength": signal_strength,
            "reliability": reliability,
            "observed_source_quality": source_quality,
            "home_count": calibration.get("home_count", 0),
            "away_count": calibration.get("away_count", 0),
            "eligible_for_learning": eligible,
            "calibration_version": CALIBRATION_VERSION,
        }

    # ========================================================
    # COUNTERS
    # ========================================================

    @staticmethod
    def _count_with_predictive_xg(matches: List[Dict[str, Any]]) -> int:
        """Считает матчи с Predictive xG (переименовано v2.2)."""
        count = 0
        for match in matches:
            home_xg = _safe_float(match.get("home_xg"))
            away_xg = _safe_float(match.get("away_xg"))
            if home_xg is not None and away_xg is not None:
                count += 1
        return count

    @staticmethod
    def _count_with_valid_pair(team_data: Dict[int, Dict[str, Any]]) -> int:
        """Считает матчи с валидной парой Predictive/Observed xG (НОВОЕ v2.2)."""
        all_matches: Set[int] = set()
        for data in team_data.values():
            for match_id in data.get("matches", []):
                all_matches.add(match_id)
        return len(all_matches)


# ============================================================
# PUBLIC API
# ============================================================

def calibrate_xg(
    matches: List[Dict[str, Any]],
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    engine = XGCalibration(db=db)
    return engine.calibrate_matches(matches)


def calibrate_match_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    engine = XGCalibration(db=db)
    return engine.calibrate_match(match_id)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("FAJ ETC — XG CALIBRATION")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:
        db = FAJDatabase()
        matches = db.get_matches()
        engine = XGCalibration(db=db)
        result = engine.calibrate_matches(matches)

        print(f"Успех: {result['success']}")
        print(f"Получено матчей: {result['matches_received']}")
        print(f"Матчей с Predictive xG: {result['matches_with_predictive_xg']}")
        print(f"Матчей с валидной парой: {result['matches_with_valid_pair']}")
        print(f"Команд: {result['teams_analyzed']}")
        print(f"Сигналов: {len(result['calibration_signals'])}")
        print()

        for calibration in result["team_calibrations"]:
            print(
                f"Team {calibration['team_id']}: "
                f"n={calibration['sample_size']} | "
                f"Predictive={calibration['predictive_xg_avg']:.3f} | "
                f"Observed={calibration['observed_xg_avg']:.3f} | "
                f"Deviation={calibration['xg_deviation']:+.3f} | "
                f"{calibration['direction']} | "
                f"{calibration['reliability']} | "
                f"source={calibration['observed_source_quality']} | "
                f"home={calibration['home_count']} away={calibration['away_count']}"
            )

        if result["errors"]:
            print()
            for error in result["errors"]:
                print(f"❌ {error}")

    except Exception as exc:
        logger.exception("XG Calibration self-test failed")
        print(f"❌ Ошибка: {exc}")

    print("=" * 70)
