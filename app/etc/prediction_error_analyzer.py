#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Prediction Error Analyzer
============================================================

НАЗНАЧЕНИЕ:

    Анализ ошибок прогнозов FAJ после завершённого матча.

ЦЕПОЧКА:

    FAJ Prediction
          │
          ▼
    Actual Result
          │
          ▼
    Prediction Error Analyzer
          │
          ├── Score Error
          ├── xG Error
          ├── Result Error
          ├── BTTS Error
          ├── Total Error
          ├── Cause Classification
          └── Recommendation
          │
          ▼
    learning_records / learning_events
          │
          ▼
    ETC Learning

ВАЖНО:

    Этот модуль НЕ:
        - изменяет model_parameters
        - изменяет FAJ Rating
        - изменяет xg_memory
        - запускает обучение
        - создаёт новые прогнозы

    Он только анализирует и возвращает результат.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)

ANALYZER_VERSION = "1.0"
ANALYZER_NAME = "FAJ ETC Prediction Error Analyzer"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
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


def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def _btts(home_goals: int, away_goals: int) -> int:
    return 1 if home_goals > 0 and away_goals > 0 else 0


def _over25(home_goals: int, away_goals: int) -> int:
    return 1 if home_goals + away_goals > 2 else 0


def _over35(home_goals: int, away_goals: int) -> int:
    return 1 if home_goals + away_goals > 3 else 0


# ============================================================
# ANALYZER
# ============================================================

class PredictionErrorAnalyzer:
    """
    Анализатор ошибок прогнозов FAJ.

    Работает поверх уже существующих данных.
    Ничего не записывает в БД самостоятельно.
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
        Полный анализ ошибки одного прогноза.

        prediction:
            Данные из predictions.

        result:
            Данные из match_results.

        predicted_xg:
            Данные из match_predictions.

        observed_xg:
            Фактический xG.

        Возвращает структурированный результат анализа.
        """

        predicted_xg = predicted_xg or {}
        observed_xg = observed_xg or {}

        actual_home = _safe_int(result.get("home_goals"))
        actual_away = _safe_int(result.get("away_goals"))

        predicted_home = self._extract_predicted_home_score(prediction)
        predicted_away = self._extract_predicted_away_score(prediction)

        actual_winner = _winner(actual_home, actual_away)

        predicted_winner = self._extract_predicted_winner(prediction)

        score_error = abs(
            predicted_home - actual_home
        ) + abs(
            predicted_away - actual_away
        )

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

        xg_error = (
            abs(predicted_home_xg - actual_home_xg)
            + abs(predicted_away_xg - actual_away_xg)
        )

        result_error = (
            0 if predicted_winner == actual_winner else 1
        )

        actual_btts = _btts(actual_home, actual_away)
        actual_over25 = _over25(actual_home, actual_away)
        actual_over35 = _over35(actual_home, actual_away)

        predicted_btts = self._extract_probability_boolean(
            prediction.get("btts")
        )

        predicted_over25 = self._extract_probability_boolean(
            prediction.get("over25")
        )

        predicted_over35 = self._extract_probability_boolean(
            prediction.get("over35")
        )

        btts_error = (
            0
            if predicted_btts is None
            or predicted_btts == actual_btts
            else 1
        )

        total25_error = (
            0
            if predicted_over25 is None
            or predicted_over25 == actual_over25
            else 1
        )

        total35_error = (
            0
            if predicted_over35 is None
            or predicted_over35 == actual_over35
            else 1
        )

        cause = self._classify_cause(
            predicted_home_xg=predicted_home_xg,
            predicted_away_xg=predicted_away_xg,
            actual_home_xg=actual_home_xg,
            actual_away_xg=actual_away_xg,
            actual_home=actual_home,
            actual_away=actual_away,
            predicted_winner=predicted_winner,
            actual_winner=actual_winner,
        )

        severity = self._calculate_severity(
            score_error=score_error,
            xg_error=xg_error,
            result_error=result_error,
            btts_error=btts_error,
            total25_error=total25_error,
            total35_error=total35_error,
        )

        recommendation = self._recommend(
            cause_type=cause["cause_type"],
            score_error=score_error,
            xg_error=xg_error,
        )

        return {
            "analyzer": self.name,
            "analyzer_version": self.version,

            # ------------------------------------------------
            # SCORE
            # ------------------------------------------------

            "predicted_score": (
                f"{predicted_home}:{predicted_away}"
            ),

            "actual_score": (
                f"{actual_home}:{actual_away}"
            ),

            "error_score": score_error,

            # ------------------------------------------------
            # XG
            # ------------------------------------------------

            "predicted_home_xg": predicted_home_xg,
            "predicted_away_xg": predicted_away_xg,

            "actual_home_xg": actual_home_xg,
            "actual_away_xg": actual_away_xg,

            "error_xg": round(xg_error, 4),

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            "predicted_winner": predicted_winner,
            "actual_winner": actual_winner,
            "result_error": result_error,

            # ------------------------------------------------
            # MARKETS
            # ------------------------------------------------

            "predicted_btts": predicted_btts,
            "actual_btts": actual_btts,
            "error_btts": btts_error,

            "predicted_over25": predicted_over25,
            "actual_over25": actual_over25,
            "error_total_25": total25_error,

            "predicted_over35": predicted_over35,
            "actual_over35": actual_over35,
            "error_total_35": total35_error,

            # ------------------------------------------------
            # CLASSIFICATION
            # ------------------------------------------------

            "error_type": cause["error_type"],
            "cause_type": cause["cause_type"],
            "error_detail": cause["detail"],

            # ------------------------------------------------
            # SEVERITY
            # ------------------------------------------------

            "error_severity": severity,

            # ------------------------------------------------
            # RECOMMENDATION
            # ------------------------------------------------

            "recommendation": recommendation,
        }

    # ========================================================
    # PREDICTED SCORE
    # ========================================================

    @staticmethod
    def _extract_predicted_home_score(
        prediction: Dict[str, Any]
    ) -> int:
        """
        Получает прогнозный домашний счёт.

        ВАЖНО:
        Если exact score отсутствует, используем 0.

        Позже ETC может получать Top-5 score
        отдельно через prediction_scores.
        """

        value = prediction.get("predicted_home")

        if value is None:
            value = prediction.get("home_goals")

        return _safe_int(value)

    @staticmethod
    def _extract_predicted_away_score(
        prediction: Dict[str, Any]
    ) -> int:
        value = prediction.get("predicted_away")

        if value is None:
            value = prediction.get("away_goals")

        return _safe_int(value)

    # ========================================================
    # PREDICTED WINNER
    # ========================================================

    @staticmethod
    def _extract_predicted_winner(
        prediction: Dict[str, Any]
    ) -> str:
        """
        Определяет прогнозируемый исход
        по максимальной вероятности.
        """

        home = _safe_float(prediction.get("home_win"))
        draw = _safe_float(prediction.get("draw"))
        away = _safe_float(prediction.get("away_win"))

        values = {
            "home": home,
            "draw": draw,
            "away": away,
        }

        return max(values, key=values.get)

    # ========================================================
    # BOOLEAN PROBABILITIES
    # ========================================================

    @staticmethod
    def _extract_probability_boolean(
        value: Any
    ) -> Optional[int]:
        """
        Преобразует вероятность в бинарный прогноз.

        >= 0.50 → YES
        < 0.50 → NO

        Если значение отсутствует → None.
        """

        if value is None:
            return None

        value = _safe_float(value)

        return 1 if value >= 0.50 else 0

    # ========================================================
    # CAUSE
    # ========================================================

    @staticmethod
    def _classify_cause(
        predicted_home_xg: float,
        predicted_away_xg: float,
        actual_home_xg: float,
        actual_away_xg: float,
        actual_home: int,
        actual_away: int,
        predicted_winner: str,
        actual_winner: str,
    ) -> Dict[str, str]:

        home_xg_error = predicted_home_xg - actual_home_xg
        away_xg_error = predicted_away_xg - actual_away_xg

        # ----------------------------------------------------
        # Результат угадан, но xG сильно ошибся
        # ----------------------------------------------------

        if (
            predicted_winner == actual_winner
            and abs(home_xg_error) + abs(away_xg_error) > 1.20
        ):
            return {
                "error_type": "xg_miscalibration",
                "cause_type": "xg_over_or_underestimated",
                "detail": (
                    "Исход матча определён правильно, "
                    "но Predictive xG существенно отличается "
                    "от Observed xG."
                ),
            }

        # ----------------------------------------------------
        # FAJ переоценила хозяев
        # ----------------------------------------------------

        if home_xg_error > 0.60:
            return {
                "error_type": "score_miss",
                "cause_type": "home_attack_overestimated",
                "detail": (
                    "FAJ переоценила атакующий потенциал "
                    "хозяев."
                ),
            }

        # ----------------------------------------------------
        # FAJ недооценила хозяев
        # ----------------------------------------------------

        if home_xg_error < -0.60:
            return {
                "error_type": "score_miss",
                "cause_type": "home_attack_underestimated",
                "detail": (
                    "FAJ недооценила атакующий потенциал "
                    "хозяев."
                ),
            }

        # ----------------------------------------------------
        # FAJ переоценила гостей
        # ----------------------------------------------------

        if away_xg_error > 0.60:
            return {
                "error_type": "score_miss",
                "cause_type": "away_attack_overestimated",
                "detail": (
                    "FAJ переоценила атакующий потенциал "
                    "гостей."
                ),
            }

        # ----------------------------------------------------
        # FAJ недооценила гостей
        # ----------------------------------------------------

        if away_xg_error < -0.60:
            return {
                "error_type": "score_miss",
                "cause_type": "away_attack_underestimated",
                "detail": (
                    "FAJ недооценила атакующий потенциал "
                    "гостей."
                ),
            }

        # ----------------------------------------------------
        # Ошибка исхода
        # ----------------------------------------------------

        if predicted_winner != actual_winner:
            return {
                "error_type": "result_miss",
                "cause_type": "winner_misclassified",
                "detail": (
                    "FAJ неверно определила исход матча."
                ),
            }

        # ----------------------------------------------------
        # Общая ошибка
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
        score_error: int,
        xg_error: float,
        result_error: int,
        btts_error: int,
        total25_error: int,
        total35_error: int,
    ) -> int:

        severity = 0

        if score_error >= 3:
            severity += 2
        elif score_error >= 2:
            severity += 1

        if xg_error >= 1.50:
            severity += 2
        elif xg_error >= 0.80:
            severity += 1

        if result_error:
            severity += 2

        if btts_error:
            severity += 1

        if total25_error:
            severity += 1

        if total35_error:
            severity += 1

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
        score_error: int,
        xg_error: float,
    ) -> str:

        recommendations = {
            "home_attack_overestimated": (
                "Проверить home attack factor и калибровку "
                "атакующей силы хозяев."
            ),

            "home_attack_underestimated": (
                "Проверить home attack factor и возможность "
                "недооценки атакующей силы хозяев."
            ),

            "away_attack_overestimated": (
                "Проверить away attack factor и калибровку "
                "атакующей силы гостей."
            ),

            "away_attack_underestimated": (
                "Проверить away attack factor и возможность "
                "недооценки атакующей силы гостей."
            ),

            "xg_over_or_underestimated": (
                "Передать матч в модуль xG Calibration "
                "для обновления командной xG-памяти."
            ),

            "winner_misclassified": (
                "Проверить FAJ Club Rating, форму, "
                "домашний фактор и tactical matchup."
            ),

            "normal_variance": (
                "Изменение параметров не требуется."
            ),
        }

        recommendation = recommendations.get(
            cause_type,
            "Передать ошибку в ETC для дальнейшего анализа."
        )

        if score_error >= 3:
            recommendation += (
                " Ошибка точного счёта существенная."
            )

        if xg_error >= 1.50:
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
