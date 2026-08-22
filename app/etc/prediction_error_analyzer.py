#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Prediction Error Analyzer v2.0
============================================================

НАЗНАЧЕНИЕ
-----------

Анализ ошибок прогнозов FAJ после завершения матча.

ЦЕПОЧКА:

    FAJ Prediction
          │
          ▼
    Actual Result
          │
          ├───────────────┐
          ▼               ▼
    Observed xG       Match Facts
          │               │
          └───────┬───────┘
                  ▼
       Prediction Error Analyzer
                  │
                  ├── score error
                  ├── xG error
                  ├── result error
                  ├── BTTS error
                  ├── total error
                  ├── cause classification
                  ├── severity
                  └── recommendation
                  │
                  ▼
          LearningAnalyzer
                  │
                  ▼
           ETC Signals
                  │
                  ▼
        ParameterOptimizer
                  │
                  ▼
        Evolution Engine


ВАЖНЫЙ ПРИНЦИП
---------------

Этот модуль анализирует ОДИН завершённый матч.

Он НЕ определяет по одному матчу,
что параметр модели необходимо менять.

Это делает следующий уровень ETC:

    PredictionErrorAnalyzer
            ↓
    LearningAnalyzer
            ↓
    ParameterOptimizer
            ↓
    EvolutionEngine


МОДУЛЬ НЕ:

    - изменяет model_parameters;
    - изменяет FAJ Rating;
    - изменяет xg_memory;
    - изменяет predictions;
    - создаёт новые прогнозы;
    - изменяет match_results;
    - изменяет gold_dataset;
    - записывает данные в SQLite;
    - запускает обучение.


ОСНОВНОЙ ПРИНЦИП v2.0
---------------------

Отсутствующее значение НЕ считается нулём.

Например:

    отсутствующий Observed xG
        !=
    Observed xG = 0.0

Это критически важно для ETC.

Если фактический xG отсутствует,
xG-ошибка не рассчитывается.


SQLite:
    только через переданные данные.

Prediction Error Analyzer не зависит
от конкретной схемы SQLite.


============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


ANALYZER_VERSION = "2.0"
ANALYZER_NAME = "FAJ ETC Prediction Error Analyzer"


# ============================================================
# THRESHOLDS
# ============================================================

XG_CAUSE_THRESHOLD = 0.60
XG_MAJOR_ERROR_THRESHOLD = 1.20

SCORE_MINOR_THRESHOLD = 2
SCORE_MAJOR_THRESHOLD = 3

SEVERITY_XG_HIGH = 1.50
SEVERITY_XG_MEDIUM = 0.80


# ============================================================
# SAFE CONVERSION
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование в float.

    В отличие от старой версии:
        отсутствие значения -> None.

    Это необходимо для ETC,
    чтобы отсутствие факта не превращалось
    в ложный нулевой результат.
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


# ============================================================
# RESULT HELPERS
# ============================================================

def _winner(
    home_goals: int,
    away_goals: int,
) -> str:

    if home_goals > away_goals:
        return "home"

    if home_goals < away_goals:
        return "away"

    return "draw"


def _btts(
    home_goals: int,
    away_goals: int,
) -> int:

    return int(
        home_goals > 0
        and away_goals > 0
    )


def _over25(
    home_goals: int,
    away_goals: int,
) -> int:

    return int(
        home_goals + away_goals > 2
    )


def _over35(
    home_goals: int,
    away_goals: int,
) -> int:

    return int(
        home_goals + away_goals > 3
    )


# ============================================================
# ANALYZER
# ============================================================

class PredictionErrorAnalyzer:
    """
    Анализатор ошибки одного прогноза FAJ.

    Только аналитика.

    Никакой записи в БД.
    Никакого обучения.
    """

    def __init__(self) -> None:

        self.version = ANALYZER_VERSION
        self.name = ANALYZER_NAME

    # ========================================================
    # PUBLIC
    # ========================================================

    def analyze(
        self,
        prediction: Dict[str, Any],
        result: Dict[str, Any],
        predicted_xg: Optional[Dict[str, Any]] = None,
        observed_xg: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Полный анализ ошибки одного матча.

        prediction:
            прогноз FAJ.

        result:
            фактический результат.

        predicted_xg:
            Predictive xG.

        observed_xg:
            Observed xG.

        Возвращает структурированный аналитический факт.
        """

        prediction = prediction or {}
        result = result or {}
        predicted_xg = predicted_xg or {}
        observed_xg = observed_xg or {}

        output = self._empty_result()

        try:

            # =================================================
            # MATCH ID
            # =================================================

            output["match_id"] = (
                result.get("match_id")
                or prediction.get("match_id")
            )

            # =================================================
            # ACTUAL SCORE
            # =================================================

            actual_home = _safe_int(
                result.get("home_goals")
            )

            actual_away = _safe_int(
                result.get("away_goals")
            )

            if (
                actual_home is None
                or actual_away is None
            ):
                output["errors"].append(
                    "Фактический счёт отсутствует."
                )

                return output

            output["actual_score"] = (
                f"{actual_home}:{actual_away}"
            )

            actual_winner = _winner(
                actual_home,
                actual_away,
            )

            output["actual_winner"] = actual_winner

            # =================================================
            # PREDICTED SCORE
            # =================================================

            predicted_home = (
                self._extract_predicted_home_score(
                    prediction
                )
            )

            predicted_away = (
                self._extract_predicted_away_score(
                    prediction
                )
            )

            if (
                predicted_home is not None
                and predicted_away is not None
            ):

                output["predicted_score"] = (
                    f"{predicted_home}:{predicted_away}"
                )

                output["error_score"] = (
                    abs(
                        predicted_home
                        - actual_home
                    )
                    +
                    abs(
                        predicted_away
                        - actual_away
                    )
                )

            # =================================================
            # PREDICTED RESULT
            # =================================================

            predicted_winner = (
                self._extract_predicted_winner(
                    prediction
                )
            )

            output["predicted_winner"] = (
                predicted_winner
            )

            if predicted_winner is not None:

                output["result_error"] = int(
                    predicted_winner
                    != actual_winner
                )

            # =================================================
            # XG
            # =================================================

            predicted_home_xg = _safe_float(
                predicted_xg.get("xg_home")
            )

            predicted_away_xg = _safe_float(
                predicted_xg.get("xg_away")
            )

            actual_home_xg = _safe_float(
                observed_xg.get("home_xg")
            )

            actual_away_xg = _safe_float(
                observed_xg.get("away_xg")
            )

            output["predicted_home_xg"] = (
                predicted_home_xg
            )

            output["predicted_away_xg"] = (
                predicted_away_xg
            )

            output["actual_home_xg"] = (
                actual_home_xg
            )

            output["actual_away_xg"] = (
                actual_away_xg
            )

            # -------------------------------------------------
            # XG ERROR
            # -------------------------------------------------

            if (
                predicted_home_xg is not None
                and predicted_away_xg is not None
                and actual_home_xg is not None
                and actual_away_xg is not None
            ):

                xg_error = (
                    abs(
                        predicted_home_xg
                        - actual_home_xg
                    )
                    +
                    abs(
                        predicted_away_xg
                        - actual_away_xg
                    )
                )

                output["error_xg"] = round(
                    xg_error,
                    4,
                )

                output["xg_available"] = True

            else:

                output["xg_available"] = False

                output["errors"].append(
                    "Полный набор Predictive/Observed xG "
                    "отсутствует. xG error не рассчитывался."
                )

            # =================================================
            # MARKETS
            # =================================================

            actual_btts = _btts(
                actual_home,
                actual_away,
            )

            actual_over25 = _over25(
                actual_home,
                actual_away,
            )

            actual_over35 = _over35(
                actual_home,
                actual_away,
            )

            output["actual_btts"] = actual_btts
            output["actual_over25"] = actual_over25
            output["actual_over35"] = actual_over35

            predicted_btts = (
                self._extract_probability_boolean(
                    prediction.get("btts")
                )
            )

            predicted_over25 = (
                self._extract_probability_boolean(
                    prediction.get("over25")
                )
            )

            predicted_over35 = (
                self._extract_probability_boolean(
                    prediction.get("over35")
                )
            )

            output["predicted_btts"] = (
                predicted_btts
            )

            output["predicted_over25"] = (
                predicted_over25
            )

            output["predicted_over35"] = (
                predicted_over35
            )

            if predicted_btts is not None:

                output["error_btts"] = int(
                    predicted_btts
                    != actual_btts
                )

            if predicted_over25 is not None:

                output["error_total_25"] = int(
                    predicted_over25
                    != actual_over25
                )

            if predicted_over35 is not None:

                output["error_total_35"] = int(
                    predicted_over35
                    != actual_over35
                )

            # =================================================
            # CAUSE
            # =================================================

            cause = self._classify_cause(
                predicted_home_xg=predicted_home_xg,
                predicted_away_xg=predicted_away_xg,
                actual_home_xg=actual_home_xg,
                actual_away_xg=actual_away_xg,
                predicted_winner=predicted_winner,
                actual_winner=actual_winner,
            )

            output["error_type"] = (
                cause["error_type"]
            )

            output["cause_type"] = (
                cause["cause_type"]
            )

            output["error_detail"] = (
                cause["detail"]
            )

            # =================================================
            # SEVERITY
            # =================================================

            severity = self._calculate_severity(
                score_error=output["error_score"],
                xg_error=output["error_xg"],
                result_error=output["result_error"],
                btts_error=output["error_btts"],
                total25_error=output["error_total_25"],
                total35_error=output["error_total_35"],
            )

            output["error_severity"] = severity

            # =================================================
            # RECOMMENDATION
            # =================================================

            output["recommendation"] = (
                self._recommend(
                    cause_type=output["cause_type"],
                    score_error=output["error_score"],
                    xg_error=output["error_xg"],
                )
            )

            output["success"] = True

            return output

        except Exception as exc:

            logger.exception(
                "Prediction Error Analyzer failed"
            )

            output["errors"].append(
                str(exc)
            )

            return output

    # ========================================================
    # EMPTY RESULT
    # ========================================================

    def _empty_result(self) -> Dict[str, Any]:
        """
        Единый контракт результата.

        None означает отсутствие факта,
        а не нулевую ошибку.
        """

        return {

            "success": False,

            "analyzer": self.name,
            "analyzer_version": self.version,

            "match_id": None,

            # SCORE
            "predicted_score": None,
            "actual_score": None,

            "error_score": None,

            # XG
            "predicted_home_xg": None,
            "predicted_away_xg": None,

            "actual_home_xg": None,
            "actual_away_xg": None,

            "error_xg": None,
            "xg_available": False,

            # RESULT
            "predicted_winner": None,
            "actual_winner": None,
            "result_error": None,

            # MARKETS
            "predicted_btts": None,
            "actual_btts": None,
            "error_btts": None,

            "predicted_over25": None,
            "actual_over25": None,
            "error_total_25": None,

            "predicted_over35": None,
            "actual_over35": None,
            "error_total_35": None,

            # CLASSIFICATION
            "error_type": "unknown",
            "cause_type": "unknown",
            "error_detail": None,

            # SEVERITY
            "error_severity": None,

            # RECOMMENDATION
            "recommendation": None,

            # DIAGNOSTICS
            "errors": [],
        }

    # ========================================================
    # PREDICTED SCORE
    # ========================================================

    @staticmethod
    def _extract_predicted_home_score(
        prediction: Dict[str, Any],
    ) -> Optional[int]:

        value = prediction.get(
            "predicted_home"
        )

        if value is None:

            value = prediction.get(
                "home_goals"
            )

        return _safe_int(value)

    @staticmethod
    def _extract_predicted_away_score(
        prediction: Dict[str, Any],
    ) -> Optional[int]:

        value = prediction.get(
            "predicted_away"
        )

        if value is None:

            value = prediction.get(
                "away_goals"
            )

        return _safe_int(value)

    # ========================================================
    # PREDICTED WINNER
    # ========================================================

    @staticmethod
    def _extract_predicted_winner(
        prediction: Dict[str, Any],
    ) -> Optional[str]:
        """
        Определяет прогнозируемый исход.

        Поддерживает:

            home_win
            draw
            away_win

        Если ни одного значения нет,
        исход считается неизвестным.
        """

        home = _safe_float(
            prediction.get("home_win")
        )

        draw = _safe_float(
            prediction.get("draw")
        )

        away = _safe_float(
            prediction.get("away_win")
        )

        values = {}

        if home is not None:
            values["home"] = home

        if draw is not None:
            values["draw"] = draw

        if away is not None:
            values["away"] = away

        if not values:
            return None

        return max(
            values,
            key=values.get,
        )

    # ========================================================
    # PROBABILITY BOOLEAN
    # ========================================================

    @staticmethod
    def _extract_probability_boolean(
        value: Any,
    ) -> Optional[int]:
        """
        Преобразует вероятность в бинарный прогноз.

            >= 0.50 -> 1
            < 0.50  -> 0

        None -> None.
        """

        probability = _safe_float(value)

        if probability is None:
            return None

        return int(
            probability >= 0.50
        )

    # ========================================================
    # CAUSE CLASSIFICATION
    # ========================================================

    @staticmethod
    def _classify_cause(
        predicted_home_xg: Optional[float],
        predicted_away_xg: Optional[float],
        actual_home_xg: Optional[float],
        actual_away_xg: Optional[float],
        predicted_winner: Optional[str],
        actual_winner: str,
    ) -> Dict[str, str]:
        """
        Классифицирует причину ошибки.

        Важный принцип:

        Если Observed xG отсутствует,
        нельзя делать вывод об атакующей
        переоценке/недооценке.

        В таком случае используем только
        доступную информацию об исходе.
        """

        # ----------------------------------------------------
        # XG CLASSIFICATION POSSIBLE
        # ----------------------------------------------------

        if (
            predicted_home_xg is not None
            and predicted_away_xg is not None
            and actual_home_xg is not None
            and actual_away_xg is not None
        ):

            home_xg_error = (
                predicted_home_xg
                - actual_home_xg
            )

            away_xg_error = (
                predicted_away_xg
                - actual_away_xg
            )

            total_xg_error = (
                abs(home_xg_error)
                +
                abs(away_xg_error)
            )

            # ----------------------------------------------
            # Correct result + strong xG mismatch
            # ----------------------------------------------

            if (
                predicted_winner == actual_winner
                and total_xg_error
                > XG_MAJOR_ERROR_THRESHOLD
            ):

                return {
                    "error_type": "xg_miscalibration",
                    "cause_type": (
                        "xg_over_or_underestimated"
                    ),
                    "detail": (
                        "Исход определён правильно, "
                        "но Predictive xG существенно "
                        "отличается от Observed xG."
                    ),
                }

            # ----------------------------------------------
            # Home attack
            # ----------------------------------------------

            if (
                home_xg_error
                > XG_CAUSE_THRESHOLD
            ):

                return {
                    "error_type": "score_miss",
                    "cause_type": (
                        "home_attack_overestimated"
                    ),
                    "detail": (
                        "FAJ переоценила атакующий "
                        "потенциал хозяев."
                    ),
                }

            if (
                home_xg_error
                < -XG_CAUSE_THRESHOLD
            ):

                return {
                    "error_type": "score_miss",
                    "cause_type": (
                        "home_attack_underestimated"
                    ),
                    "detail": (
                        "FAJ недооценила атакующий "
                        "потенциал хозяев."
                    ),
                }

            # ----------------------------------------------
            # Away attack
            # ----------------------------------------------

            if (
                away_xg_error
                > XG_CAUSE_THRESHOLD
            ):

                return {
                    "error_type": "score_miss",
                    "cause_type": (
                        "away_attack_overestimated"
                    ),
                    "detail": (
                        "FAJ переоценила атакующий "
                        "потенциал гостей."
                    ),
                }

            if (
                away_xg_error
                < -XG_CAUSE_THRESHOLD
            ):

                return {
                    "error_type": "score_miss",
                    "cause_type": (
                        "away_attack_underestimated"
                    ),
                    "detail": (
                        "FAJ недооценила атакующий "
                        "потенциал гостей."
                    ),
                }

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if (
            predicted_winner is not None
            and predicted_winner != actual_winner
        ):

            return {
                "error_type": "result_miss",
                "cause_type": (
                    "winner_misclassified"
                ),
                "detail": (
                    "FAJ неверно определила "
                    "исход матча."
                ),
            }

        # ----------------------------------------------------
        # NO SIGNIFICANT CAUSE
        # ----------------------------------------------------

        return {
            "error_type": "minor_prediction_error",
            "cause_type": "normal_variance",
            "detail": (
                "Ошибка находится в пределах "
                "обычной вариативности футбольного матча."
            ),
        }

    # ========================================================
    # SEVERITY
    # ========================================================

    @staticmethod
    def _calculate_severity(
        score_error: Optional[int],
        xg_error: Optional[float],
        result_error: Optional[int],
        btts_error: Optional[int],
        total25_error: Optional[int],
        total35_error: Optional[int],
    ) -> int:
        """
        Рассчитывает severity.

        None не считается ошибкой.
        """

        severity = 0

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        if score_error is not None:

            if score_error >= SCORE_MAJOR_THRESHOLD:
                severity += 2

            elif score_error >= SCORE_MINOR_THRESHOLD:
                severity += 1

        # ----------------------------------------------------
        # XG
        # ----------------------------------------------------

        if xg_error is not None:

            if xg_error >= SEVERITY_XG_HIGH:
                severity += 2

            elif xg_error >= SEVERITY_XG_MEDIUM:
                severity += 1

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if result_error == 1:
            severity += 2

        # ----------------------------------------------------
        # MARKETS
        # ----------------------------------------------------

        if btts_error == 1:
            severity += 1

        if total25_error == 1:
            severity += 1

        if total35_error == 1:
            severity += 1

        # ----------------------------------------------------
        # SCALE
        # ----------------------------------------------------

        if severity >= 6:
            return 5

        if severity >= 4:
            return 4

        if severity >= 3:
            return 3

        if severity >= 1:
            return 2

        return 1

    # ========================================================
    # RECOMMENDATION
    # ========================================================

    @staticmethod
    def _recommend(
        cause_type: str,
        score_error: Optional[int],
        xg_error: Optional[float],
    ) -> str:
        """
        Формирует диагностическую рекомендацию.

        Это рекомендация для ETC,
        а НЕ команда на изменение параметров.
        """

        recommendations = {

            "home_attack_overestimated": (
                "Передать сигнал в LearningAnalyzer "
                "для проверки повторяемости переоценки "
                "атаки хозяев."
            ),

            "home_attack_underestimated": (
                "Передать сигнал в LearningAnalyzer "
                "для проверки повторяемости недооценки "
                "атаки хозяев."
            ),

            "away_attack_overestimated": (
                "Передать сигнал в LearningAnalyzer "
                "для проверки повторяемости переоценки "
                "атаки гостей."
            ),

            "away_attack_underestimated": (
                "Передать сигнал в LearningAnalyzer "
                "для проверки повторяемости недооценки "
                "атаки гостей."
            ),

            "xg_over_or_underestimated": (
                "Передать наблюдение в XG Calibration "
                "и LearningAnalyzer."
            ),

            "winner_misclassified": (
                "Проверить FAJ Rating, форму, "
                "домашний фактор и tactical matchup. "
                "Не изменять параметры по одному матчу."
            ),

            "normal_variance": (
                "Дополнительное изменение параметров "
                "не требуется."
            ),
        }

        recommendation = recommendations.get(
            cause_type,
            (
                "Передать аналитический факт "
                "в LearningAnalyzer."
            ),
        )

        if (
            score_error is not None
            and score_error >= SCORE_MAJOR_THRESHOLD
        ):

            recommendation += (
                " Ошибка точного счёта существенная."
            )

        if (
            xg_error is not None
            and xg_error >= SEVERITY_XG_HIGH
        ):

            recommendation += (
                " Наблюдается существенная ошибка xG."
            )

        return recommendation


# ============================================================
# PUBLIC API
# ============================================================

def analyze_prediction_error(
    prediction: Dict[str, Any],
    result: Dict[str, Any],
    predicted_xg: Optional[Dict[str, Any]] = None,
    observed_xg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Удобный публичный API ETC.
    """

    analyzer = PredictionErrorAnalyzer()

    return analyzer.analyze(
        prediction=prediction,
        result=result,
        predicted_xg=predicted_xg,
        observed_xg=observed_xg,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    prediction = {
        "match_id": 123,

        "predicted_home": 2,
        "predicted_away": 1,

        "home_win": 0.62,
        "draw": 0.23,
        "away_win": 0.15,

        "btts": 0.58,
        "over25": 0.64,
        "over35": 0.31,
    }

    result = {
        "match_id": 123,
        "home_goals": 0,
        "away_goals": 2,
    }

    predicted_xg = {
        "xg_home": 1.85,
        "xg_away": 0.95,
    }

    observed_xg = {
        "home_xg": 0.48,
        "away_xg": 1.72,
    }

    analysis = analyze_prediction_error(
        prediction=prediction,
        result=result,
        predicted_xg=predicted_xg,
        observed_xg=observed_xg,
    )

    print("=" * 70)
    print(ANALYZER_NAME)
    print("=" * 70)

    for key, value in analysis.items():
        print(f"{key}: {value}")

    print("=" * 70)
