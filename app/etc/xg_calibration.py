#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — XG Calibration v1.0
============================================================

НАЗНАЧЕНИЕ:

    Сравнение Predictive xG FAJ с Observed xG,
    полученным после завершения матча.

ЦЕПОЧКА:

    Predictive xG
        │
        ├── matches.home_xg
        └── matches.away_xg
                 │
                 ▼
          XG Calibration
                 ▲
                 │
        ├── match_statistics.xg
        │
        ▼
    Observed xG

РЕЗУЛЬТАТ:

    Для каждой команды рассчитывается:

        observed_xg
        predictive_xg
        deviation
        absolute_error
        direction
        sample_size

ВАЖНЫЕ ПРИНЦИПЫ:

    1. database.py НЕ изменяется.
    2. Никакого обучения параметров здесь нет.
    3. FAJ Rating здесь НЕ изменяется.
    4. xg_memory здесь НЕ изменяется.
    5. Модуль только анализирует и возвращает результат.
    6. Все факты читаются из SQLite через FAJDatabase.
    7. Никакого DELETE.
    8. Никакого изменения исторических результатов.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


CALIBRATION_VERSION = "1.0"
CALIBRATION_NAME = "FAJ ETC XG Calibration v1.0"


# ------------------------------------------------------------
# НАСТРОЙКИ
# ------------------------------------------------------------

# Минимальное количество матчей команды,
# после которого сигнал считается более устойчивым.
MIN_MATCHES_FOR_STABLE_SIGNAL = 3

# Максимальное отклонение, которое допускаем
# без дополнительного ограничения.
MAX_DEVIATION = 3.0


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
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


# ------------------------------------------------------------
# MAIN CLASS
# ------------------------------------------------------------

class XGCalibration:
    """
    ETC XG Calibration.

    Отвечает только за сравнение:

        Predictive xG ↔ Observed xG

    и формирование калибровочного сигнала.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC API
    # ========================================================

    def calibrate_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Рассчитывает xG-калибровку по завершённым матчам.

        Возвращает агрегированный результат по командам.
        """

        result = {
            "success": False,
            "version": CALIBRATION_VERSION,
            "engine": CALIBRATION_NAME,
            "matches_analyzed": 0,
            "teams_analyzed": 0,
            "team_calibrations": [],
            "errors": [],
        }

        try:
            team_data = self._collect_team_xg(matches)

            result["matches_analyzed"] = len(matches)
            result["teams_analyzed"] = len(team_data)

            calibrations = []

            for team_id, data in team_data.items():
                calibration = self._calculate_team_calibration(
                    team_id=team_id,
                    data=data,
                )

                if calibration is not None:
                    calibrations.append(calibration)

            result["team_calibrations"] = calibrations
            result["success"] = True

            logger.info(
                "XG Calibration completed: matches=%s teams=%s",
                result["matches_analyzed"],
                result["teams_analyzed"],
            )

            return result

        except Exception as exc:
            logger.exception("XG Calibration error")
            result["errors"].append(str(exc))
            return result

    def calibrate_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Рассчитывает xG-калибровку для одного матча.
        """

        result = {
            "success": False,
            "version": CALIBRATION_VERSION,
            "engine": CALIBRATION_NAME,
            "match_id": match_id,
            "teams": [],
            "errors": [],
        }

        try:
            match = self._get_match(match_id)

            if not match:
                result["errors"].append(
                    f"Матч {match_id} не найден."
                )
                return result

            team_data = self._collect_team_xg([match])

            for team_id, data in team_data.items():
                calibration = self._calculate_team_calibration(
                    team_id=team_id,
                    data=data,
                )

                if calibration:
                    result["teams"].append(calibration)

            result["success"] = True
            return result

        except Exception as exc:
            logger.exception(
                "XG Calibration error for match %s",
                match_id,
            )
            result["errors"].append(str(exc))
            return result

    # ========================================================
    # MATCH LOADING
    # ========================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает матч через FAJDatabase.
        """

        matches = self.db.get_matches()

        for match in matches:
            if _safe_int(match.get("id")) == match_id:
                return match

        return None

    # ========================================================
    # COLLECT XG
    # ========================================================

    def _collect_team_xg(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        """
        Собирает Predictive и Observed xG по каждой команде.

        Predictive xG:
            matches.home_xg
            matches.away_xg

        Observed xG:
            match_statistics.xg
        """

        teams: Dict[int, Dict[str, Any]] = {}

        for match in matches:

            match_id = _safe_int(match.get("id"))

            home_team_id = match.get("home_team_id")
            away_team_id = match.get("away_team_id")

            if home_team_id is None or away_team_id is None:
                continue

            home_team_id = _safe_int(home_team_id)
            away_team_id = _safe_int(away_team_id)

            predictive_home = _safe_float(
                match.get("home_xg")
            )

            predictive_away = _safe_float(
                match.get("away_xg")
            )

            if predictive_home is None and predictive_away is None:
                continue

            observed = self._get_observed_xg(match_id)

            observed_home = observed.get(home_team_id)
            observed_away = observed.get(away_team_id)

            # ----------------------------------------------
            # HOME
            # ----------------------------------------------

            if predictive_home is not None and observed_home is not None:

                self._ensure_team(
                    teams,
                    home_team_id,
                )

                teams[home_team_id]["matches"] += 1

                teams[home_team_id]["predictive_xg"].append(
                    predictive_home
                )

                teams[home_team_id]["observed_xg"].append(
                    observed_home
                )

                teams[home_team_id]["deviations"].append(
                    observed_home - predictive_home
                )

            # ----------------------------------------------
            # AWAY
            # ----------------------------------------------

            if predictive_away is not None and observed_away is not None:

                self._ensure_team(
                    teams,
                    away_team_id,
                )

                teams[away_team_id]["matches"] += 1

                teams[away_team_id]["predictive_xg"].append(
                    predictive_away
                )

                teams[away_team_id]["observed_xg"].append(
                    observed_away
                )

                teams[away_team_id]["deviations"].append(
                    observed_away - predictive_away
                )

        return teams

    def _get_observed_xg(
        self,
        match_id: int,
    ) -> Dict[int, float]:
        """
        Получает Observed xG из match_statistics.

        Формат:

            {
                team_id: observed_xg
            }
        """

        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT team_id, xg
                FROM match_statistics
                WHERE match_id = ?
                """,
                (match_id,),
            )

            rows = cursor.fetchall()

            result: Dict[int, float] = {}

            for row in rows:

                team_id = row["team_id"]
                xg = _safe_float(row["xg"])

                if team_id is None or xg is None:
                    continue

                result[_safe_int(team_id)] = xg

            return result

        finally:
            conn.close()

    # ========================================================
    # TEAM DATA
    # ========================================================

    @staticmethod
    def _ensure_team(
        teams: Dict[int, Dict[str, Any]],
        team_id: int,
    ) -> None:

        if team_id not in teams:

            teams[team_id] = {
                "team_id": team_id,
                "matches": 0,
                "predictive_xg": [],
                "observed_xg": [],
                "deviations": [],
            }

    # ========================================================
    # CALCULATION
    # ========================================================

    def _calculate_team_calibration(
        self,
        team_id: int,
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Рассчитывает итоговую калибровку одной команды.
        """

        predictive = data.get("predictive_xg", [])
        observed = data.get("observed_xg", [])
        deviations = data.get("deviations", [])

        if not predictive or not observed or not deviations:
            return None

        count = min(
            len(predictive),
            len(observed),
            len(deviations),
        )

        if count <= 0:
            return None

        predictive_avg = sum(predictive) / count
        observed_avg = sum(observed) / count
        deviation = sum(deviations) / count

        absolute_error = sum(
            abs(value)
            for value in deviations
        ) / count

        # ----------------------------------------------------
        # Направление ошибки
        # ----------------------------------------------------

        if deviation > 0.05:
            direction = "underestimated"

        elif deviation < -0.05:
            direction = "overestimated"

        else:
            direction = "calibrated"

        # ----------------------------------------------------
        # Сила сигнала
        # ----------------------------------------------------

        signal_strength = _clamp(
            abs(deviation) / 1.0,
            0.0,
            1.0,
        )

        # ----------------------------------------------------
        # Надёжность сигнала
        # ----------------------------------------------------

        if count >= MIN_MATCHES_FOR_STABLE_SIGNAL:
            reliability = "stable"
        elif count >= 2:
            reliability = "developing"
        else:
            reliability = "weak"

        return {
            "team_id": team_id,
            "matches_count": count,

            "predictive_xg_avg": round(
                predictive_avg,
                4,
            ),

            "observed_xg_avg": round(
                observed_avg,
                4,
            ),

            # Положительное значение:
            # фактический xG выше прогнозного.
            #
            # Отрицательное значение:
            # фактический xG ниже прогнозного.
            "xg_deviation": round(
                _clamp(
                    deviation,
                    -MAX_DEVIATION,
                    MAX_DEVIATION,
                ),
                4,
            ),

            "absolute_error": round(
                absolute_error,
                4,
            ),

            "direction": direction,

            "signal_strength": round(
                signal_strength,
                4,
            ),

            "reliability": reliability,

            "calibration_version": CALIBRATION_VERSION,
        }


# ============================================================
# PUBLIC FUNCTIONS
# ============================================================

def calibrate_xg(
    matches: List[Dict[str, Any]],
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Удобный публичный API ETC.
    """

    engine = XGCalibration(db=db)

    return engine.calibrate_matches(matches)


def calibrate_match_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Калибровка одного матча.
    """

    engine = XGCalibration(db=db)

    return engine.calibrate_match(match_id)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    db = FAJDatabase()

    matches = db.get_matches()

    engine = XGCalibration(db=db)

    result = engine.calibrate_matches(matches)

    print("=" * 70)
    print("FAJ ETC — XG CALIBRATION v1.0")
    print("=" * 70)

    print(
        f"Успех: {result['success']}"
    )

    print(
        f"Матчей: {result['matches_analyzed']}"
    )

    print(
        f"Команд: {result['teams_analyzed']}"
    )

    print()

    for calibration in result["team_calibrations"]:

        print(
            f"Team {calibration['team_id']}: "
            f"Predictive={calibration['predictive_xg_avg']:.3f} | "
            f"Observed={calibration['observed_xg_avg']:.3f} | "
            f"Deviation={calibration['xg_deviation']:+.3f} | "
            f"{calibration['direction']} | "
            f"{calibration['reliability']}"
        )

    if result["errors"]:

        print()

        for error in result["errors"]:
            print(f"❌ {error}")

    print("=" * 70)
