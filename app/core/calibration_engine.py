#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Calibration Engine v1.4
=====================================================

РОЛЬ:
    Корректировка вероятностей FAJ на основе
    накопленных исторических данных.

ПРИНЦИП FAJ:
    ✅ Calibration Engine не является моделью.
    ✅ Не изменяет xG.
    ✅ Не изменяет score_matrix.
    ✅ Не изменяет факты.
    ✅ Не работает с БД напрямую.
    ✅ Коэффициенты обновляются только через Learning Layer.
    ❌ Нет JSON-конфигурации.
    ❌ Нет ручного подгона под отдельный матч.

ИЗМЕНЕНИЯ v1.4:
    1. Добавлена защита MAX_SHIFT.
    2. Максимальный сдвиг вероятности ограничен 10 п.п.
    3. Ограничение применяется после нормализации.
    4. Добавлено безопасное преобразование входных вероятностей.
    5. Защищён результат от NaN / inf / отрицательных значений.
    6. Сохраняется информация о применённых коэффициентах.
=====================================================
"""

import logging
import math
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class CalibrationEngine:
    """
    Calibration Engine FAJ.

    Отвечает только за корректировку вероятностей
    1X2 после основного математического расчёта.
    """

    VERSION = "1.4"

    # ============================================================
    # DEFAULT COEFFICIENTS
    # ============================================================

    DEFAULT_COEFFICIENTS = {
        "home_bias": 0.97,
        "draw_bias": 1.02,
        "away_bias": 1.01,
    }

    # ============================================================
    # VALIDATION LIMITS
    # ============================================================

    COEFFICIENT_MIN = 0.5
    COEFFICIENT_MAX = 1.5

    # Максимальный допустимый сдвиг
    # одной вероятности после всей калибровки.
    #
    # 0.10 = 10 процентных пунктов.
    MAX_SHIFT = 0.10

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self):
        self.version = self.VERSION
        self.coefficients = self.DEFAULT_COEFFICIENTS.copy()

        logger.info(
            "Calibration Engine v%s initialized | coefficients=%s | max_shift=%.2f",
            self.VERSION,
            self.coefficients,
            self.MAX_SHIFT,
        )

    # ============================================================
    # ADJUST
    # ============================================================

    def adjust(
        self,
        raw_prediction: Dict[str, Any],
        coefficients: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Калибрует вероятности 1X2.

        Args:
            raw_prediction:
                Сырой прогноз Pipeline.

                Ожидается:
                {
                    "probability": {
                        "home": ...,
                        "draw": ...,
                        "away": ...
                    }
                }

            coefficients:
                Опциональные коэффициенты из Learning Layer.

        Returns:
            {
                "home": float,
                "draw": float,
                "away": float,
                "applied": bool,
                "limited": bool,
                "coefficients_used": {...}
            }
        """

        if not isinstance(raw_prediction, dict):
            raise ValueError("raw_prediction must be dict")

        # ========================================================
        # COEFFICIENTS
        # ========================================================

        coeffs = self.coefficients.copy()

        if coefficients:
            validated = self._validate_coefficients(coefficients)
            coeffs.update(validated)

        # ========================================================
        # RAW PROBABILITIES
        # ========================================================

        raw_probs = raw_prediction.get("probability", {})

        if not isinstance(raw_probs, dict):
            raise ValueError("raw_prediction['probability'] must be dict")

        home = self._safe_probability(
            raw_probs.get("home", 0.33),
            "home",
        )

        draw = self._safe_probability(
            raw_probs.get("draw", 0.33),
            "draw",
        )

        away = self._safe_probability(
            raw_probs.get("away", 0.33),
            "away",
        )

        raw_normalized = self._normalize(
            home,
            draw,
            away,
        )

        home = raw_normalized["home"]
        draw = raw_normalized["draw"]
        away = raw_normalized["away"]

        # ========================================================
        # APPLY COEFFICIENTS
        # ========================================================

        calibrated_home = home * coeffs.get("home_bias", 1.0)
        calibrated_draw = draw * coeffs.get("draw_bias", 1.0)
        calibrated_away = away * coeffs.get("away_bias", 1.0)

        calibrated = self._normalize(
            calibrated_home,
            calibrated_draw,
            calibrated_away,
        )

        # ========================================================
        # LIMIT CALIBRATION SHIFT
        # ========================================================

        calibrated_home = calibrated["home"]
        calibrated_draw = calibrated["draw"]
        calibrated_away = calibrated["away"]

        shifts = {
            "home": abs(calibrated_home - home),
            "draw": abs(calibrated_draw - draw),
            "away": abs(calibrated_away - away),
        }

        max_shift = max(shifts.values())

        limited = False

        if max_shift > self.MAX_SHIFT:

            factor = self.MAX_SHIFT / max_shift

            calibrated_home = home + (
                calibrated_home - home
            ) * factor

            calibrated_draw = draw + (
                calibrated_draw - draw
            ) * factor

            calibrated_away = away + (
                calibrated_away - away
            ) * factor

            limited = True

            logger.warning(
                "Calibration shift limited | "
                "max_shift=%.4f | allowed=%.4f | factor=%.4f",
                max_shift,
                self.MAX_SHIFT,
                factor,
            )

        # ========================================================
        # FINAL NORMALIZATION
        # ========================================================

        final = self._normalize(
            calibrated_home,
            calibrated_draw,
            calibrated_away,
        )

        # ========================================================
        # FINAL SAFETY
        # ========================================================

        home_final = final["home"]
        draw_final = final["draw"]
        away_final = final["away"]

        # Повторная проверка.
        # После нормализации теоретически возможен
        # небольшой дополнительный сдвиг.

        final_shifts = {
            "home": abs(home_final - home),
            "draw": abs(draw_final - draw),
            "away": abs(away_final - away),
        }

        final_max_shift = max(final_shifts.values())

        if final_max_shift > self.MAX_SHIFT + 1e-9:

            logger.warning(
                "Final calibration shift exceeded limit after normalization | "
                "shift=%.6f | limit=%.6f",
                final_max_shift,
                self.MAX_SHIFT,
            )

            # Последняя жёсткая защита.
            factor = self.MAX_SHIFT / final_max_shift

            home_final = home + (
                home_final - home
            ) * factor

            draw_final = draw + (
                draw_final - draw
            ) * factor

            away_final = away + (
                away_final - away
            ) * factor

            final = self._normalize(
                home_final,
                draw_final,
                away_final,
            )

            home_final = final["home"]
            draw_final = final["draw"]
            away_final = final["away"]

            limited = True

        # ========================================================
        # RESULT
        # ========================================================

        result = {
            "home": round(home_final, 4),
            "draw": round(draw_final, 4),
            "away": round(away_final, 4),

            "applied": True,

            "limited": limited,

            "coefficients_used": coeffs,
        }

        logger.debug(
            "Calibration applied | "
            "raw=%.4f/%.4f/%.4f | "
            "final=%.4f/%.4f/%.4f | "
            "limited=%s",
            home,
            draw,
            away,
            home_final,
            draw_final,
            away_final,
            limited,
        )

        return result

    # ============================================================
    # SAFE PROBABILITY
    # ============================================================

    def _safe_probability(
        self,
        value: Any,
        name: str,
    ) -> float:
        """
        Безопасно преобразует вероятность в диапазон 0..1.
        """

        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid probability '%s'=%r, fallback=0.33",
                name,
                value,
            )
            return 0.33

        if not math.isfinite(value):
            logger.warning(
                "Non-finite probability '%s'=%r, fallback=0.33",
                name,
                value,
            )
            return 0.33

        return max(0.0, min(1.0, value))

    # ============================================================
    # NORMALIZE
    # ============================================================

    def _normalize(
        self,
        home: float,
        draw: float,
        away: float,
    ) -> Dict[str, float]:
        """
        Нормализация вероятностей.

        Гарантирует:
            home + draw + away = 1
        """

        home = max(0.0, float(home))
        draw = max(0.0, float(draw))
        away = max(0.0, float(away))

        total = home + draw + away

        if total <= 0:
            logger.warning(
                "Calibration normalization failed: "
                "all probabilities <= 0. Using 1/3."
            )

            return {
                "home": 1.0 / 3.0,
                "draw": 1.0 / 3.0,
                "away": 1.0 / 3.0,
            }

        return {
            "home": home / total,
            "draw": draw / total,
            "away": away / total,
        }

    # ============================================================
    # VALIDATE COEFFICIENTS
    # ============================================================

    def _validate_coefficients(
        self,
        coefficients: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Проверяет коэффициенты Learning Layer.

        Разрешены только известные коэффициенты.
        """

        if not isinstance(coefficients, dict):
            raise ValueError(
                "Calibration coefficients must be dict"
            )

        valid = {}

        for key, value in coefficients.items():

            if key not in self.DEFAULT_COEFFICIENTS:
                logger.warning(
                    "Unknown calibration coefficient '%s', ignoring",
                    key,
                )
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Invalid calibration coefficient '{key}': {value}"
                )

            if not math.isfinite(value):
                raise ValueError(
                    f"Calibration coefficient '{key}' "
                    f"must be finite"
                )

            if not (
                self.COEFFICIENT_MIN
                <= value
                <= self.COEFFICIENT_MAX
            ):
                raise ValueError(
                    f"Invalid calibration coefficient '{key}': {value}. "
                    f"Must be between "
                    f"{self.COEFFICIENT_MIN} and "
                    f"{self.COEFFICIENT_MAX}"
                )

            valid[key] = value

        return valid

    # ============================================================
    # UPDATE
    # ============================================================

    def update_coefficients(
        self,
        new_coefficients: Dict[str, float],
    ) -> None:
        """
        Безопасное обновление коэффициентов.

        Вызывается Learning Layer.
        """

        validated = self._validate_coefficients(
            new_coefficients
        )

        self.coefficients.update(validated)

        logger.info(
            "Calibration coefficients updated: %s",
            validated,
        )

    # ============================================================
    # GET
    # ============================================================

    def get_coefficients(self) -> Dict[str, float]:
        """
        Возвращает текущие коэффициенты.
        """

        return self.coefficients.copy()

    # ============================================================
    # RESET
    # ============================================================

    def reset_coefficients(self) -> None:
        """
        Сбрасывает коэффициенты к базовым.
        """

        self.coefficients = (
            self.DEFAULT_COEFFICIENTS.copy()
        )

        logger.info(
            "Calibration coefficients reset to default"
        )


# ================================================================
# SELF TEST
# ================================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    engine = CalibrationEngine()

    print(
        f"Calibration Engine v{engine.VERSION}"
    )

    print(
        f"Default coefficients: "
        f"{engine.DEFAULT_COEFFICIENTS}"
    )

    print(
        f"Coefficient range: "
        f"{engine.COEFFICIENT_MIN} - "
        f"{engine.COEFFICIENT_MAX}"
    )

    print(
        f"Maximum probability shift: "
        f"{engine.MAX_SHIFT * 100:.1f}%"
    )

    # ------------------------------------------------------------
    # TEST 1 — normal calibration
    # ------------------------------------------------------------

    result = engine.adjust(
        {
            "probability": {
                "home": 0.50,
                "draw": 0.25,
                "away": 0.25,
            }
        }
    )

    print("\nTEST 1")
    print(result)

    # ------------------------------------------------------------
    # TEST 2 — extreme coefficients
    # ------------------------------------------------------------

    result = engine.adjust(
        {
            "probability": {
                "home": 0.90,
                "draw": 0.05,
                "away": 0.05,
            }
        },
        coefficients={
            "home_bias": 0.5,
            "draw_bias": 1.5,
            "away_bias": 1.5,
        },
    )

    print("\nTEST 2 — MAX SHIFT")
    print(result)

    # ------------------------------------------------------------
    # TEST 3 — invalid coefficient
    # ------------------------------------------------------------

    try:

        engine.update_coefficients(
            {
                "home_bias": 2.0
            }
        )

        print(
            "ERROR: invalid coefficient accepted"
        )

    except ValueError as e:

        print(
            "\nTEST 3 — INVALID COEFFICIENT"
        )

        print(
            f"OK: rejected: {e}"
        )

    # ------------------------------------------------------------
    # TEST 4 — unknown coefficient
    # ------------------------------------------------------------

    result = engine.adjust(
        {
            "probability": {
                "home": 0.4,
                "draw": 0.3,
                "away": 0.3,
            }
        },
        coefficients={
            "home_bias": 1.0,
            "unknown_bias": 1.4,
        },
    )

    print(
        "\nTEST 4 — UNKNOWN COEFFICIENT"
    )

    print(result)

    # ------------------------------------------------------------
    # TEST 5 — malformed input
    # ------------------------------------------------------------

    result = engine.adjust(
        {
            "probability": {
                "home": None,
                "draw": "bad",
                "away": float("nan"),
            }
        }
    )

    print(
        "\nTEST 5 — INVALID PROBABILITIES"
    )

    print(result)
