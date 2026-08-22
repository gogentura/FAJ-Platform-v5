#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/xg_calibration.py
============================================================

XG CALIBRATION v2.0
============================================================

НАЗНАЧЕНИЕ
-----------

Сравнение исторического Predictive xG FAJ
с фактическим Observed xG после завершения матча.

ЦЕПОЧКА:

    MATCH
      │
      ├── Predictive xG
      │      matches.home_xg
      │      matches.away_xg
      │
      └── FACT
             │
             └── ObservedXG
                    │
                    └── match_statistics.xg
                           │
                           ▼
                    XG Calibration
                           │
                           ▼
                Calibration Signal
                           │
                           ▼
                    ETC Analyzer
                           │
                           ▼
                    ETC Learning
                           │
                           ▼
                    Parameter Proposal

============================================================

АРХИТЕКТУРНЫЕ ПРАВИЛА
----------------------

1. SQLite only.

2. FAJDatabase — единственный объект доступа к БД.

3. database.py не изменяется.

4. Calibration работает только с завершёнными матчами.

5. Predictive xG НЕ рассчитывается заново.
   Используется историческое значение,
   сохранённое в matches.

6. Observed xG НЕ дублируется здесь.
   Для его получения используется ObservedXG.

7. Calibration только анализирует:
       Predictive xG ↔ Observed xG

8. Calibration НЕ:
       - изменяет predictions;
       - изменяет match_results;
       - изменяет match_statistics;
       - изменяет gold_dataset;
       - изменяет learning_memory;
       - изменяет model_parameters;
       - изменяет FAJ Rating;
       - создаёт новые прогнозы;
       - запускает обучение.

9. Никакого DELETE.
10. Никакого INSERT.
11. Никакого UPDATE.

12. Результат является аналитическим объектом
    для следующих ETC-слоёв.

============================================================

ОПРЕДЕЛЕНИЯ
------------

Predictive xG:

    xG, который FAJ рассчитал ДО матча
    и сохранил в matches.

Observed xG:

    фактический xG после матча,
    полученный через ObservedXG.

Deviation:

    observed_xg - predictive_xg

    > 0:
        FAJ недооценил атакующий потенциал.

    < 0:
        FAJ переоценил атакующий потенциал.

Absolute error:

    abs(observed_xg - predictive_xg)

Sample size:

    количество валидных пар
    Predictive xG ↔ Observed xG.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase
from app.etc.observed_xg import ObservedXG


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.0"
MODULE_NAME = "FAJ ETC XG Calibration"


# ============================================================
# CONFIGURATION
# ============================================================

# После этого количества наблюдений сигнал считается
# достаточно устойчивым для дальнейшего ETC-анализа.
MIN_MATCHES_FOR_STABLE_SIGNAL = 3

# Два наблюдения — уже не одиночный случай,
# но ещё недостаточно для стабильного сигнала.
MIN_MATCHES_FOR_DEVELOPING_SIGNAL = 2

# Небольшая зона, в которой считаем модель
# практически откалиброванной.
CALIBRATION_EPSILON = 0.05

# Защита от экстремальных выбросов.
MAX_DEVIATION = 3.0

# Максимальный диапазон xG, принимаемый
# для исторического значения.
MAX_XG = 10.0


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование в float.
    """

    if value is None:
        return default

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:
    """
    Безопасное преобразование в int.
    """

    if value is None:
        return default

    try:
        return int(value)

    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Ограничивает значение диапазоном.
    """

    return max(
        minimum,
        min(maximum, value),
    )


# ============================================================
# XG CALIBRATION
# ============================================================

class XGCalibration:
    """
    ETC XG Calibration.

    Только аналитический слой.

    Отвечает за сравнение:

        Predictive xG
             ↕
        Observed xG

    и формирует calibration signals.

    Никаких изменений БД.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        observed_xg: Optional[ObservedXG] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.observed_xg = (
            observed_xg
            or ObservedXG(db=self.db)
        )

    # ========================================================
    # PUBLIC — MULTI MATCH
    # ========================================================

    def calibrate_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Рассчитывает XG Calibration
        по набору завершённых матчей.

        На выходе:

            team_calibrations
            calibration_signals

        Никакой записи в БД.
        """

        result: Dict[str, Any] = {
            "success": False,
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "matches_received": len(matches),
            "matches_analyzed": 0,

            "teams_analyzed": 0,

            "team_calibrations": [],
            "calibration_signals": [],

            "errors": [],
        }

        try:

            team_data = self._collect_team_xg(
                matches
            )

            result["matches_analyzed"] = (
                self._count_analyzed_matches(
                    matches
                )
            )

            result["teams_analyzed"] = len(
                team_data
            )

            calibrations: List[
                Dict[str, Any]
            ] = []

            signals: List[
                Dict[str, Any]
            ] = []

            for team_id, data in team_data.items():

                calibration = (
                    self._calculate_team_calibration(
                        team_id=team_id,
                        data=data,
                    )
                )

                if calibration is None:
                    continue

                calibrations.append(
                    calibration
                )

                signal = (
                    self._build_calibration_signal(
                        calibration
                    )
                )

                if signal is not None:
                    signals.append(signal)

            result["team_calibrations"] = (
                calibrations
            )

            result["calibration_signals"] = (
                signals
            )

            result["success"] = True

            logger.info(
                "XG Calibration completed: "
                "received=%s analyzed=%s "
                "teams=%s signals=%s",
                result["matches_received"],
                result["matches_analyzed"],
                result["teams_analyzed"],
                len(signals),
            )

            return result

        except Exception as exc:

            logger.exception(
                "XG Calibration failed"
            )

            result["errors"].append(
                str(exc)
            )

            return result

    # ========================================================
    # PUBLIC — SINGLE MATCH
    # ========================================================

    def calibrate_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Калибровка одного матча.

        Используется Match Laboratory
        и диагностическими инструментами ETC.

        Важно:

        Один матч НЕ может создать стабильный
        долгосрочный calibration signal.
        """

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

            match = self._get_match(
                match_id
            )

            if not match:

                result["errors"].append(
                    f"Матч {match_id} не найден."
                )

                return result

            team_data = self._collect_team_xg(
                [match]
            )

            for team_id, data in team_data.items():

                calibration = (
                    self._calculate_team_calibration(
                        team_id=team_id,
                        data=data,
                    )
                )

                if calibration is None:
                    continue

                result["teams"].append(
                    calibration
                )

                signal = (
                    self._build_calibration_signal(
                        calibration
                    )
                )

                if signal is not None:
                    result["signals"].append(
                        signal
                    )

            result["success"] = True

            return result

        except Exception as exc:

            logger.exception(
                "XG Calibration failed "
                "for match_id=%s",
                match_id,
            )

            result["errors"].append(
                str(exc)
            )

            return result

    # ========================================================
    # MATCH LOADING
    # ========================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает исторический матч
        через FAJDatabase.

        Только чтение.
        """

        matches = self.db.get_matches()

        target_id = _safe_int(
            match_id
        )

        if target_id is None:
            return None

        for raw_match in matches:

            match = dict(raw_match)

            current_id = _safe_int(
                match.get("id")
            )

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
        Собирает валидные пары:

            Predictive xG
                  +
            Observed xG

        отдельно для каждой команды.

        Важнейшее правило:

        Если Predictive или Observed xG отсутствует,
        наблюдение НЕ попадает в calibration sample.
        """

        teams: Dict[
            int,
            Dict[str, Any]
        ] = {}

        for raw_match in matches:

            match = dict(raw_match)

            match_id = _safe_int(
                match.get("id")
            )

            home_team_id = _safe_int(
                match.get("home_team_id")
            )

            away_team_id = _safe_int(
                match.get("away_team_id")
            )

            if (
                match_id is None
                or home_team_id is None
                or away_team_id is None
            ):
                continue

            predictive_home = self._get_predictive_xg(
                match.get("home_xg")
            )

            predictive_away = self._get_predictive_xg(
                match.get("away_xg")
            )

            # ------------------------------------------------
            # Observed xG
            # ------------------------------------------------

            observed_result = (
                self.observed_xg.get_match(
                    match_id
                )
            )

            if not observed_result.get(
                "success"
            ):
                continue

            observed_home = _safe_float(
                observed_result.get(
                    "home_xg"
                )
            )

            observed_away = _safe_float(
                observed_result.get(
                    "away_xg"
                )
            )

            # ------------------------------------------------
            # HOME
            # ------------------------------------------------

            if (
                predictive_home is not None
                and observed_home is not None
            ):

                self._append_observation(
                    teams=teams,
                    team_id=home_team_id,
                    match_id=match_id,
                    predictive_xg=predictive_home,
                    observed_xg=observed_home,
                    venue="home",
                    observed_source=(
                        observed_result.get(
                            "home_xg_source"
                        )
                    ),
                )

            # ------------------------------------------------
            # AWAY
            # ------------------------------------------------

            if (
                predictive_away is not None
                and observed_away is not None
            ):

                self._append_observation(
                    teams=teams,
                    team_id=away_team_id,
                    match_id=match_id,
                    predictive_xg=predictive_away,
                    observed_xg=observed_away,
                    venue="away",
                    observed_source=(
                        observed_result.get(
                            "away_xg_source"
                        )
                    ),
                )

        return teams

    # ========================================================
    # PREDICTIVE XG
    # ========================================================

    @staticmethod
    def _get_predictive_xg(
        value: Any,
    ) -> Optional[float]:
        """
        Получает исторический Predictive xG.

        ВАЖНО:

        Здесь НЕ рассчитывается новый xG.

        Берётся только значение,
        сохранённое в matches.
        """

        xg = _safe_float(value)

        if xg is None:
            return None

        if xg < 0:
            return None

        return _clamp(
            xg,
            0.0,
            MAX_XG,
        )

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
        """
        Добавляет одно валидное наблюдение.
        """

        XGCalibration._ensure_team(
            teams,
            team_id,
        )

        deviation = (
            observed_xg
            - predictive_xg
        )

        teams[team_id]["matches"].append(
            match_id
        )

        teams[team_id]["predictive_xg"].append(
            predictive_xg
        )

        teams[team_id]["observed_xg"].append(
            observed_xg
        )

        teams[team_id]["deviations"].append(
            deviation
        )

        teams[team_id]["venues"].append(
            venue
        )

        teams[team_id]["observed_sources"].append(
            observed_source
        )

    # ========================================================
    # TEAM DATA
    # ========================================================

    @staticmethod
    def _ensure_team(
        teams: Dict[int, Dict[str, Any]],
        team_id: int,
    ) -> None:
        """
        Создаёт контейнер команды.
        """

        if team_id in teams:
            return

        teams[team_id] = {
            "team_id": team_id,

            "matches": [],

            "predictive_xg": [],

            "observed_xg": [],

            "deviations": [],

            "venues": [],

            "observed_sources": [],
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
        Рассчитывает калибровку одной команды.
        """

        predictive = list(
            data.get(
                "predictive_xg",
                [],
            )
        )

        observed = list(
            data.get(
                "observed_xg",
                [],
            )
        )

        deviations = list(
            data.get(
                "deviations",
                [],
            )
        )

        matches = list(
            data.get(
                "matches",
                [],
            )
        )

        sample_size = min(
            len(predictive),
            len(observed),
            len(deviations),
            len(matches),
        )

        if sample_size <= 0:
            return None

        predictive = predictive[
            :sample_size
        ]

        observed = observed[
            :sample_size
        ]

        deviations = deviations[
            :sample_size
        ]

        matches = matches[
            :sample_size
        ]

        predictive_avg = (
            sum(predictive)
            / sample_size
        )

        observed_avg = (
            sum(observed)
            / sample_size
        )

        mean_deviation = (
            sum(deviations)
            / sample_size
        )

        absolute_error = (
            sum(
                abs(value)
                for value in deviations
            )
            / sample_size
        )

        # ----------------------------------------------------
        # Direction
        # ----------------------------------------------------

        direction = (
            self._determine_direction(
                mean_deviation
            )
        )

        # ----------------------------------------------------
        # Signal strength
        # ----------------------------------------------------

        signal_strength = (
            self._calculate_signal_strength(
                mean_deviation
            )
        )

        # ----------------------------------------------------
        # Reliability
        # ----------------------------------------------------

        reliability = (
            self._determine_reliability(
                sample_size
            )
        )

        # ----------------------------------------------------
        # Observed source quality
        # ----------------------------------------------------

        observed_source_quality = (
            self._calculate_source_quality(
                data.get(
                    "observed_sources",
                    [],
                )
            )
        )

        return {
            "team_id": team_id,

            "sample_size": sample_size,

            "matches_count": sample_size,

            "match_ids": matches,

            "predictive_xg_avg": round(
                predictive_avg,
                4,
            ),

            "observed_xg_avg": round(
                observed_avg,
                4,
            ),

            # Положительное:
            # observed > predictive.
            #
            # Отрицательное:
            # observed < predictive.
            "xg_deviation": round(
                _clamp(
                    mean_deviation,
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

            "observed_source_quality": (
                observed_source_quality
            ),

            "calibration_version": (
                CALIBRATION_VERSION
            ),
        }

    # ========================================================
    # DIRECTION
    # ========================================================

    @staticmethod
    def _determine_direction(
        deviation: float,
    ) -> str:
        """
        Определяет направление систематической ошибки.
        """

        if deviation > CALIBRATION_EPSILON:
            return "underestimated"

        if deviation < -CALIBRATION_EPSILON:
            return "overestimated"

        return "calibrated"

    # ========================================================
    # SIGNAL STRENGTH
    # ========================================================

    @staticmethod
    def _calculate_signal_strength(
        deviation: float,
    ) -> float:
        """
        Преобразует абсолютное отклонение
        в силу сигнала 0..1.

        1.0 соответствует отклонению >= 1.0 xG.
        """

        return round(
            _clamp(
                abs(deviation),
                0.0,
                1.0,
            ),
            4,
        )

    # ========================================================
    # RELIABILITY
    # ========================================================

    @staticmethod
    def _determine_reliability(
        sample_size: int,
    ) -> str:
        """
        Определяет статистическую зрелость сигнала.
        """

        if (
            sample_size
            >= MIN_MATCHES_FOR_STABLE_SIGNAL
        ):
            return "stable"

        if (
            sample_size
            >= MIN_MATCHES_FOR_DEVELOPING_SIGNAL
        ):
            return "developing"

        return "weak"

    # ========================================================
    # SOURCE QUALITY
    # ========================================================

    @staticmethod
    def _calculate_source_quality(
        sources: List[Any],
    ) -> str:
        """
        Оценивает качество Observed xG.

        Приоритет:

            match_statistics
                >
            statistical_fallback
        """

        normalized = [
            str(source)
            for source in sources
            if source
        ]

        if not normalized:
            return "unknown"

        primary_count = sum(
            1
            for source in normalized
            if source == "match_statistics"
        )

        if primary_count == len(normalized):
            return "high"

        if primary_count > 0:
            return "medium"

        if all(
            source == "statistical_fallback"
            for source in normalized
        ):
            return "fallback"

        return "unknown"

    # ========================================================
    # CALIBRATION SIGNAL
    # ========================================================

    @staticmethod
    def _build_calibration_signal(
        calibration: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Формирует аналитический сигнал.

        ВАЖНО:

        Это НЕ команда на изменение параметра.

        Следующий слой сам решает,
        достаточно ли сигнала для обучения.
        """

        if not calibration:
            return None

        sample_size = _safe_int(
            calibration.get(
                "sample_size"
            ),
            0,
        )

        deviation = _safe_float(
            calibration.get(
                "xg_deviation"
            ),
            0.0,
        )

        signal_strength = _safe_float(
            calibration.get(
                "signal_strength"
            ),
            0.0,
        )

        if sample_size is None:
            sample_size = 0

        if deviation is None:
            deviation = 0.0

        if signal_strength is None:
            signal_strength = 0.0

        if sample_size <= 0:
            return None

        return {
            "signal_type": (
                "xg_calibration"
            ),

            "team_id": calibration.get(
                "team_id"
            ),

            "sample_size": sample_size,

            "xg_deviation": deviation,

            "absolute_error": (
                calibration.get(
                    "absolute_error",
                    0.0,
                )
            ),

            "direction": calibration.get(
                "direction"
            ),

            "signal_strength": (
                signal_strength
            ),

            "reliability": calibration.get(
                "reliability"
            ),

            "observed_source_quality": (
                calibration.get(
                    "observed_source_quality"
                )
            ),

            "eligible_for_learning": (
                sample_size
                >= MIN_MATCHES_FOR_STABLE_SIGNAL
                and calibration.get(
                    "reliability"
                ) == "stable"
            ),

            "calibration_version": (
                CALIBRATION_VERSION
            ),
        }

    # ========================================================
    # ANALYZED MATCH COUNT
    # ========================================================

    @staticmethod
    def _count_analyzed_matches(
        matches: List[Dict[str, Any]],
    ) -> int:
        """
        Считает количество матчей,
        в которых присутствуют обе стороны
        и исторический Predictive xG.

        Это диагностический счётчик.
        """

        count = 0

        for raw_match in matches:

            match = dict(raw_match)

            match_id = _safe_int(
                match.get("id")
            )

            home_team = _safe_int(
                match.get("home_team_id")
            )

            away_team = _safe_int(
                match.get("away_team_id")
            )

            home_xg = (
                XGCalibration._get_predictive_xg(
                    match.get("home_xg")
                )
            )

            away_xg = (
                XGCalibration._get_predictive_xg(
                    match.get("away_xg")
                )
            )

            if (
                match_id is not None
                and home_team is not None
                and away_team is not None
                and home_xg is not None
                and away_xg is not None
            ):
                count += 1

        return count


# ============================================================
# PUBLIC API
# ============================================================

def calibrate_xg(
    matches: List[Dict[str, Any]],
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API для пакетной калибровки.
    """

    engine = XGCalibration(
        db=db
    )

    return engine.calibrate_matches(
        matches
    )


def calibrate_match_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичный API для одного матча.
    """

    engine = XGCalibration(
        db=db
    )

    return engine.calibrate_match(
        match_id
    )


# ============================================================
# CLI / SELF TEST
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
        "FAJ ETC — XG CALIBRATION"
    )
    print(
        f"Version: {MODULE_VERSION}"
    )
    print("=" * 70)

    try:

        db = FAJDatabase()

        matches = db.get_matches()

        engine = XGCalibration(
            db=db
        )

        result = engine.calibrate_matches(
            matches
        )

        print(
            f"Успех: "
            f"{result['success']}"
        )

        print(
            f"Получено матчей: "
            f"{result['matches_received']}"
        )

        print(
            f"Матчей с Predictive xG: "
            f"{result['matches_analyzed']}"
        )

        print(
            f"Команд: "
            f"{result['teams_analyzed']}"
        )

        print(
            f"Сигналов: "
            f"{len(result['calibration_signals'])}"
        )

        print()

        for calibration in (
            result["team_calibrations"]
        ):

            print(
                f"Team {calibration['team_id']}: "
                f"n={calibration['sample_size']} | "
                f"Predictive="
                f"{calibration['predictive_xg_avg']:.3f} | "
                f"Observed="
                f"{calibration['observed_xg_avg']:.3f} | "
                f"Deviation="
                f"{calibration['xg_deviation']:+.3f} | "
                f"{calibration['direction']} | "
                f"{calibration['reliability']} | "
                f"source="
                f"{calibration['observed_source_quality']}"
            )

        if result["errors"]:

            print()

            for error in result["errors"]:

                print(
                    f"❌ {error}"
                )

    except Exception as exc:

        logger.exception(
            "XG Calibration self-test failed"
        )

        print(
            f"❌ Ошибка: {exc}"
        )

    print("=" * 70)
