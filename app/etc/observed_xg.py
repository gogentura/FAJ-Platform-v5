#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
Observed xG v1.2
============================================================

app/etc/observed_xg.py

НАЗНАЧЕНИЕ
-----------
Получение и нормализация фактического xG матча
для Evolution Training Center (ETC).

АРХИТЕКТУРА:

    MATCH RESULT
         +
    match_statistics
         ↓
    ObservedXG
         ↓
    фактический xG
         +
    источник
         +
    качество
         +
    confidence
         ↓
    ErrorClassifier
         ↓
    Learning Analyzer
         ↓
    ETC

ВАЖНО
------
Predictive xG:
    прогноз FAJ до матча.

Observed xG:
    фактический xG после матча,
    полученный из match_statistics.xg,
    если источник его предоставил.

Fallback xG:
    расчётная оценка на основе фактической статистики,
    используемая только если настоящий xG отсутствует.

Fallback НЕ считается равноценным источником
Observed xG.

МОДУЛЬ НЕ:
    - изменяет predictions;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - запускает обучение;
    - создаёт прогнозы;
    - удаляет данные;
    - изменяет match_results;
    - изменяет gold_dataset;
    - записывает что-либо в SQLite.

SQLite only.

FAJDatabase — единственный штатный объект доступа к БД.

============================================================
VERSION
============================================================

v1.2

Основные изменения относительно v1.1:

    1. Улучшена формула fallback xG.
    2. Добавлен флаг xg_calibration_available.
    3. Улучшена обработка big_chances в fallback.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


from app.database import FAJDatabase


logger = logging.getLogger(__name__)


OBSERVED_XG_VERSION = "1.2"
MODULE_NAME = "FAJ ETC Observed xG"


# ============================================================
# CONSTANTS
# ============================================================

# Настоящий источник xG.
SOURCE_MATCH_STATISTICS = "match_statistics"

# Расчётная оценка, если источник xG отсутствует.
SOURCE_STATISTICAL_FALLBACK = "statistical_fallback"

# xG отсутствует.
SOURCE_UNAVAILABLE = None

# Максимально допустимое значение при чтении источника.
# Это техническая защита от мусорных значений.
SOURCE_XG_MIN = 0.0
SOURCE_XG_MAX = 10.0

# Диапазон fallback.
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
    default: int = 0,
) -> int:
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
    Ограничивает число заданным диапазоном.
    """

    return max(
        minimum,
        min(maximum, value),
    )


# ============================================================
# OBSERVED XG ENGINE
# ============================================================

class ObservedXG:
    """
    FAJ ETC — Observed xG Engine.

    Отвечает исключительно за получение фактического xG.

    Приоритет:

        1. match_statistics.xg
        2. statistical fallback

    При этом fallback никогда не маскируется
    под настоящий источник xG.
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
        Получает нормализованный Observed xG
        для одного матча.

        Только чтение.

        Основные поля:

            home_xg
            away_xg

            home_xg_source
            away_xg_source

            quality
            confidence

            observed_xg_available
            fallback_used
            xg_calibration_available

        """

        result: Dict[str, Any] = {

            "success": False,

            "module": MODULE_NAME,
            "version": OBSERVED_XG_VERSION,

            "match_id": match_id,

            "home_team_id": None,
            "away_team_id": None,

            # ------------------------------------------------
            # XG
            # ------------------------------------------------

            "home_xg": None,
            "away_xg": None,

            # ------------------------------------------------
            # SOURCE
            # ------------------------------------------------

            "home_xg_source": SOURCE_UNAVAILABLE,
            "away_xg_source": SOURCE_UNAVAILABLE,

            # ------------------------------------------------
            # SOURCE FLAGS
            # ------------------------------------------------

            "home_xg_observed": False,
            "away_xg_observed": False,

            "home_xg_fallback": False,
            "away_xg_fallback": False,

            "observed_xg_available": False,
            "fallback_used": False,
            "xg_calibration_available": False,

            # ------------------------------------------------
            # QUALITY
            # ------------------------------------------------

            "quality": "unknown",
            "confidence": 0.0,

            # ------------------------------------------------
            # RAW STATISTICS
            # ------------------------------------------------

            "home_statistics": {},
            "away_statistics": {},

            # ------------------------------------------------
            # DIAGNOSTICS
            # ------------------------------------------------

            "errors": [],
            "warnings": [],

        }

        try:

            # =================================================
            # STEP 1 — MATCH
            # =================================================

            match = self._get_match(match_id)

            if not match:

                result["errors"].append(
                    f"Матч {match_id} не найден."
                )

                return result

            result["home_team_id"] = match.get(
                "home_team_id"
            )

            result["away_team_id"] = match.get(
                "away_team_id"
            )

            # =================================================
            # STEP 2 — MATCH STATISTICS
            # =================================================

            statistics = self._get_match_statistics(
                match_id
            )

            if not statistics:

                result["errors"].append(
                    "Фактическая статистика матча "
                    f"{match_id} отсутствует."
                )

                return result

            # =================================================
            # STEP 3 — TEAM STATISTICS
            # =================================================

            home_stats = self._find_team_stats(
                statistics,
                result["home_team_id"],
            )

            away_stats = self._find_team_stats(
                statistics,
                result["away_team_id"],
            )

            result["home_statistics"] = (
                home_stats or {}
            )

            result["away_statistics"] = (
                away_stats or {}
            )

            if home_stats is None:

                result["warnings"].append(
                    "Статистика хозяев отсутствует."
                )

            if away_stats is None:

                result["warnings"].append(
                    "Статистика гостей отсутствует."
                )

            # =================================================
            # STEP 4 — PRIMARY OBSERVED XG
            # =================================================

            home_xg = self._read_source_xg(
                home_stats
            )

            away_xg = self._read_source_xg(
                away_stats
            )

            if home_xg is not None:

                result["home_xg"] = home_xg

                result["home_xg_source"] = (
                    SOURCE_MATCH_STATISTICS
                )

                result["home_xg_observed"] = True

            if away_xg is not None:

                result["away_xg"] = away_xg

                result["away_xg_source"] = (
                    SOURCE_MATCH_STATISTICS
                )

                result["away_xg_observed"] = True

            # =================================================
            # STEP 5 — FALLBACK
            # =================================================

            if (
                result["home_xg"] is None
                and home_stats
            ):

                fallback = self._estimate_xg(
                    home_stats
                )

                if fallback is not None:

                    result["home_xg"] = fallback

                    result["home_xg_source"] = (
                        SOURCE_STATISTICAL_FALLBACK
                    )

                    result["home_xg_fallback"] = True

                    result["warnings"].append(
                        "Home xG получен через "
                        "statistical fallback."
                    )

            if (
                result["away_xg"] is None
                and away_stats
            ):

                fallback = self._estimate_xg(
                    away_stats
                )

                if fallback is not None:

                    result["away_xg"] = fallback

                    result["away_xg_source"] = (
                        SOURCE_STATISTICAL_FALLBACK
                    )

                    result["away_xg_fallback"] = True

                    result["warnings"].append(
                        "Away xG получен через "
                        "statistical fallback."
                    )

            # =================================================
            # STEP 6 — AVAILABILITY
            # =================================================

            result["observed_xg_available"] = (
                result["home_xg_observed"]
                and result["away_xg_observed"]
            )

            result["fallback_used"] = (
                result["home_xg_fallback"]
                or result["away_xg_fallback"]
            )

            result["xg_calibration_available"] = (
                result["observed_xg_available"]
                or result["fallback_used"]
            )

            # =================================================
            # STEP 7 — QUALITY
            # =================================================

            quality, confidence = (
                self._calculate_quality(
                    home_xg=result["home_xg"],
                    away_xg=result["away_xg"],
                    home_source=result[
                        "home_xg_source"
                    ],
                    away_source=result[
                        "away_xg_source"
                    ],
                )
            )

            result["quality"] = quality
            result["confidence"] = confidence

            # =================================================
            # STEP 8 — MISSING DATA
            # =================================================

            if result["home_xg"] is None:

                result["errors"].append(
                    "Home Observed xG отсутствует."
                )

            if result["away_xg"] is None:

                result["errors"].append(
                    "Away Observed xG отсутствует."
                )

            # =================================================
            # STEP 9 — SUCCESS
            # =================================================

            result["success"] = (
                result["home_xg"] is not None
                and result["away_xg"] is not None
            )

            return result

        except Exception as exc:

            logger.exception(
                "Observed xG error for match %s",
                match_id,
            )

            result["errors"].append(
                str(exc)
            )

            return result

    # ========================================================
    # MATCH
    # ========================================================

    def _get_match(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Получает матч через FAJDatabase.

        Не выполняет SQL напрямую.
        """

        try:

            matches = self.db.get_matches()

        except Exception:

            logger.exception(
                "Unable to load matches"
            )

            raise

        for match in matches:

            try:

                current_id = int(
                    match.get("id", -1)
                )

            except (
                TypeError,
                ValueError,
                AttributeError,
            ):

                continue

            if current_id == int(match_id):

                return dict(match)

        return None

    # ========================================================
    # MATCH STATISTICS
    # ========================================================

    def _get_match_statistics(
        self,
        match_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Получает фактическую статистику матча.

        В текущей архитектуре database.py v12.1
        отдельного публичного метода для match_statistics
        может не быть.

        Поэтому здесь разрешён только SELECT
        через существующее соединение FAJDatabase.

        Никаких INSERT / UPDATE / DELETE.
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
                (match_id,),
            )

            rows = cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            conn.close()

    # ========================================================
    # SOURCE XG
    # ========================================================

    @staticmethod
    def _read_source_xg(
        stats: Optional[Dict[str, Any]],
    ) -> Optional[float]:
        """
        Читает xG непосредственно из статистики.

        ВАЖНО:

        Здесь НЕ производится fallback.

        Если xG отсутствует —
        возвращается None.

        Это позволяет ETC отличать настоящий
        источник xG от расчётной оценки.
        """

        if not stats:

            return None

        value = _safe_float(
            stats.get("xg")
        )

        if value is None:

            return None

        # ----------------------------------------------------
        # Санитарная проверка
        # ----------------------------------------------------

        if value < SOURCE_XG_MIN:

            logger.warning(
                "Observed xG below zero: %s",
                value,
            )

            return None

        if value > SOURCE_XG_MAX:

            logger.warning(
                "Observed xG unusually high: %s",
                value,
            )

            # Не удаляем факт.
            # Только ограничиваем значение для ETC.
            value = SOURCE_XG_MAX

        return round(
            value,
            4,
        )

    # ========================================================
    # TEAM STATISTICS
    # ========================================================

    @staticmethod
    def _find_team_stats(
        statistics: List[Dict[str, Any]],
        team_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """
        Находит строку статистики конкретной команды.
        """

        if team_id is None:

            return None

        try:

            target_team_id = int(team_id)

        except (
            TypeError,
            ValueError,
        ):

            return None

        for row in statistics:

            try:

                row_team_id = int(
                    row.get("team_id")
                )

            except (
                TypeError,
                ValueError,
                AttributeError,
            ):

                continue

            if row_team_id == target_team_id:

                return row

        return None

    # ========================================================
    # FALLBACK XG
    # ========================================================

    @staticmethod
    def _estimate_xg(
        stats: Dict[str, Any],
    ) -> Optional[float]:
        """
        Расчётный fallback xG.

        ЭТО НЕ НАСТОЯЩИЙ Observed xG.

        Используется только для того, чтобы ETC
        не терял матч полностью при отсутствии
        xG у внешнего источника.

        Формула (улучшена в v1.2):

            shots * 0.04
          + shots_on_target * 0.12
          + big_chances * 0.25
          + (shots_on_target / max(shots, 1)) * 0.10

        Голы намеренно НЕ используются.

        Причина:

            Observed xG должен описывать качество
            созданных моментов, а не просто повторять
            фактический счёт.

        Результат маркируется:

            source = statistical_fallback
        """

        if not stats:

            return None

        shots = _safe_int(
            stats.get("shots"),
            0,
        )

        shots_on_target = _safe_int(
            stats.get("shots_on_target"),
            0,
        )

        big_chances = _safe_int(
            stats.get("big_chances"),
            0,
        )

        # ----------------------------------------------------
        # Нормализация отрицательных значений
        # ----------------------------------------------------

        shots = max(
            0,
            shots,
        )

        shots_on_target = max(
            0,
            shots_on_target,
        )

        big_chances = max(
            0,
            big_chances,
        )

        if (
            shots <= 0
            and shots_on_target <= 0
            and big_chances <= 0
        ):

            return None

        # ----------------------------------------------------
        # Fallback formula (v1.2)
        # ----------------------------------------------------

        # Базовый вклад от ударов
        estimate = shots * 0.04

        # Вклад от ударов в створ (увеличен с 0.10 до 0.12)
        estimate += shots_on_target * 0.12

        # Вклад от больших моментов (увеличен с 0.20 до 0.25)
        estimate += big_chances * 0.25

        # Бонус за эффективность ударов
        if shots > 0:
            shot_accuracy = shots_on_target / shots
            estimate += shot_accuracy * 0.10

        estimate = _clamp(
            estimate,
            FALLBACK_XG_MIN,
            FALLBACK_XG_MAX,
        )

        return round(
            estimate,
            4,
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
    ) -> tuple[str, float]:
        """
        Определяет качество Observed xG.

        Уровни:

            high
                оба значения получены непосредственно
                из match_statistics.xg

            medium
                одно значение настоящее,
                второе fallback

            fallback
                оба значения рассчитаны fallback

            insufficient
                одного или обоих значений нет

        Confidence:

            high      = 1.00
            medium    = 0.70
            fallback  = 0.40
            insufficient = 0.00
        """

        if (
            home_xg is None
            or away_xg is None
        ):

            return (
                "insufficient",
                0.0,
            )

        home_real = (
            home_source
            == SOURCE_MATCH_STATISTICS
        )

        away_real = (
            away_source
            == SOURCE_MATCH_STATISTICS
        )

        home_fallback = (
            home_source
            == SOURCE_STATISTICAL_FALLBACK
        )

        away_fallback = (
            away_source
            == SOURCE_STATISTICAL_FALLBACK
        )

        # ----------------------------------------------------
        # HIGH
        # ----------------------------------------------------

        if home_real and away_real:

            return (
                "high",
                1.0,
            )

        # ----------------------------------------------------
        # MEDIUM
        # ----------------------------------------------------

        if (
            (home_real and away_fallback)
            or
            (away_real and home_fallback)
        ):

            return (
                "medium",
                0.70,
            )

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if home_fallback and away_fallback:

            return (
                "fallback",
                0.40,
            )

        return (
            "unknown",
            0.0,
        )


# ============================================================
# PUBLIC API
# ============================================================

def get_observed_xg(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичная точка входа ETC.

    Пример:

        data = get_observed_xg(123)

        print(data["home_xg"])
        print(data["away_xg"])
        print(data["quality"])
    """

    engine = ObservedXG(
        db=db,
    )

    return engine.get_match(
        match_id,
    )


# ============================================================
# TEST / MANUAL EXECUTION
# ============================================================

if __name__ == "__main__":

    import sys

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    if len(sys.argv) < 2:

        print(
            "Использование:\n"
            "python -m "
            "app.etc.observed_xg MATCH_ID"
        )

        raise SystemExit(1)

    try:

        match_id = int(
            sys.argv[1]
        )

    except ValueError:

        print(
            "MATCH_ID должен быть числом."
        )

        raise SystemExit(1)

    data = get_observed_xg(
        match_id
    )

    print("=" * 70)
    print("FAJ ETC — OBSERVED xG")
    print("=" * 70)

    print(
        f"Матч:              "
        f"{data['match_id']}"
    )

    print(
        f"Home xG:           "
        f"{data['home_xg']}"
    )

    print(
        f"Away xG:           "
        f"{data['away_xg']}"
    )

    print(
        f"Источник Home:     "
        f"{data['home_xg_source']}"
    )

    print(
        f"Источник Away:     "
        f"{data['away_xg_source']}"
    )

    print(
        f"Home observed:     "
        f"{data['home_xg_observed']}"
    )

    print(
        f"Away observed:     "
        f"{data['away_xg_observed']}"
    )

    print(
        f"Fallback used:     "
        f"{data['fallback_used']}"
    )

    print(
        f"Observed available:"
        f" {data['observed_xg_available']}"
    )

    print(
        f"XG Calibration avail:"
        f" {data['xg_calibration_available']}"
    )

    print(
        f"Качество:          "
        f"{data['quality']}"
    )

    print(
        f"Confidence:        "
        f"{data['confidence']}"
    )

    print(
        f"Успех:             "
        f"{data['success']}"
    )

    if data["warnings"]:

        print("\nПредупреждения:")

        for warning in data["warnings"]:

            print(
                f"  ⚠️ {warning}"
            )

    if data["errors"]:

        print("\nОшибки:")

        for error in data["errors"]:

            print(
                f"  ❌ {error}"
            )

    print("=" * 70)
