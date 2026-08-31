#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Prediction Error Analyzer v2.1
============================================================

НАЗНАЧЕНИЕ
-----------

Анализ ошибок прогнозов FAJ после завершения матча.

ИСПРАВЛЕНИЯ v2.1
============================================================

1. Убран fallback на home_goals в _extract_predicted_home_score()
2. Добавлен fallback через predicted_score в _extract_predicted_winner()
3. Добавлена проверка prediction.match_id == result.match_id
4. Разделены errors (ошибки модели) и warnings (отсутствие данных)
5. Добавлены home_xg_delta, away_xg_delta, total_xg_delta
6. error_score переименован в score_distance
7. Пороги вынесены в конфиг

ИСПРАВЛЕНИЯ v2.2 (2026-08-31)
============================================================

1. Добавлена нормализация sqlite3.Row → dict в начале analyze()
2. Исправлена ошибка AttributeError: 'sqlite3.Row' object has no attribute 'get'

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
                  ├── score_distance
                  ├── xG delta (home, away, total)
                  ├── result error
                  ├── BTTS error
                  ├── total error
                  └── warnings (отсутствие данных)
                  │
                  ▼
          ErrorClassifier
                  │
                  ▼
          LearningAnalyzer
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


ANALYZER_VERSION = "2.2"
ANALYZER_NAME = "FAJ ETC Prediction Error Analyzer v2.2"


# ============================================================
# CONFIGURATION
# ============================================================

XG_CAUSE_THRESHOLD = 0.60
XG_MAJOR_ERROR_THRESHOLD = 1.20

SCORE_MINOR_THRESHOLD = 2
SCORE_MAJOR_THRESHOLD = 3

SEVERITY_XG_HIGH = 1.50
SEVERITY_XG_MEDIUM = 0.80

PROBABILITY_THRESHOLD = 0.50


# ============================================================
# SAFE CONVERSION
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
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
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# RESULT HELPERS
# ============================================================

def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def _btts(home_goals: int, away_goals: int) -> int:
    return int(home_goals > 0 and away_goals > 0)


def _over25(home_goals: int, away_goals: int) -> int:
    return int(home_goals + away_goals > 2)


def _over35(home_goals: int, away_goals: int) -> int:
    return int(home_goals + away_goals > 3)


def _normalize_bool(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# ANALYZER
# ============================================================

class PredictionErrorAnalyzer:
    """
    Анализатор ошибки одного прогноза FAJ.

    Только аналитика. Никакой записи в БД. Никакого обучения.
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
        """
        # =================================================
        # НОРМАЛИЗАЦИЯ ВХОДНЫХ ДАННЫХ (sqlite3.Row → dict)
        # =================================================
        #
        # Исправление v2.2: FAJDatabase возвращает sqlite3.Row,
        # у которого нет метода .get(). Преобразуем в dict.
        #
        if hasattr(prediction, 'keys'):  # sqlite3.Row имеет keys()
            prediction = dict(prediction)
        if hasattr(result, 'keys'):
            result = dict(result)
        if predicted_xg is not None and hasattr(predicted_xg, 'keys'):
            predicted_xg = dict(predicted_xg)
        if observed_xg is not None and hasattr(observed_xg, 'keys'):
            observed_xg = dict(observed_xg)

        prediction = prediction or {}
        result = result or {}
        predicted_xg = predicted_xg or {}
        observed_xg = observed_xg or {}

        output = self._empty_result()

        try:
            # =================================================
            # MATCH ID — ВАЛИДАЦИЯ (НОВОЕ v2.1)
            # =================================================

            pred_match_id = _safe_int(prediction.get("match_id"))
            result_match_id = _safe_int(result.get("match_id"))

            if pred_match_id is not None and result_match_id is not None:
                if pred_match_id != result_match_id:
                    output["errors"].append("prediction_result_match_id_mismatch")
                    return output

            output["match_id"] = pred_match_id or result_match_id

            # =================================================
            # ACTUAL SCORE
            # =================================================

            actual_home = _safe_int(result.get("home_goals"))
            actual_away = _safe_int(result.get("away_goals"))

            if actual_home is None or actual_away is None:
                output["warnings"].append("Фактический счёт отсутствует.")
                return output

            output["actual_score"] = f"{actual_home}:{actual_away}"
            actual_winner = _winner(actual_home, actual_away)
            output["actual_winner"] = actual_winner

            # =================================================
            # PREDICTED SCORE (ИСПРАВЛЕНО v2.1)
            # =================================================

            predicted_home = self._extract_predicted_home_score(prediction)
            predicted_away = self._extract_predicted_away_score(prediction)

            if predicted_home is not None and predicted_away is not None:
                output["predicted_score"] = f"{predicted_home}:{predicted_away}"
                # Переименовано в score_distance (v2.1)
                output["score_distance"] = (
                    abs(predicted_home - actual_home) +
                    abs(predicted_away - actual_away)
                )
                output["score_correct"] = int(
                    predicted_home == actual_home and predicted_away == actual_away
                )

            # =================================================
            # PREDICTED RESULT (ИСПРАВЛЕНО v2.1)
            # =================================================

            predicted_winner = self._extract_predicted_winner(prediction)
            output["predicted_winner"] = predicted_winner

            if predicted_winner is not None:
                output["result_error"] = int(predicted_winner != actual_winner)
                output["winner_correct"] = int(predicted_winner == actual_winner)

            # =================================================
            # XG (НОВОЕ v2.1: delta поля)
            # =================================================

            predicted_home_xg = _safe_float(predicted_xg.get("xg_home"))
            predicted_away_xg = _safe_float(predicted_xg.get("xg_away"))
            actual_home_xg = _safe_float(observed_xg.get("home_xg"))
            actual_away_xg = _safe_float(observed_xg.get("away_xg"))

            output["predicted_home_xg"] = predicted_home_xg
            output["predicted_away_xg"] = predicted_away_xg
            output["actual_home_xg"] = actual_home_xg
            output["actual_away_xg"] = actual_away_xg

            # xG delta (направление ошибки) — НОВОЕ v2.1
            if predicted_home_xg is not None and actual_home_xg is not None:
                output["home_xg_delta"] = round(predicted_home_xg - actual_home_xg, 4)
            if predicted_away_xg is not None and actual_away_xg is not None:
                output["away_xg_delta"] = round(predicted_away_xg - actual_away_xg, 4)
            if (predicted_home_xg is not None and predicted_away_xg is not None and
                actual_home_xg is not None and actual_away_xg is not None):
                output["total_xg_delta"] = round(
                    (predicted_home_xg + predicted_away_xg) -
                    (actual_home_xg + actual_away_xg),
                    4
                )

            # XG ERROR
            if (predicted_home_xg is not None and predicted_away_xg is not None and
                actual_home_xg is not None and actual_away_xg is not None):
                xg_error = (abs(predicted_home_xg - actual_home_xg) +
                           abs(predicted_away_xg - actual_away_xg))
                output["error_xg"] = round(xg_error, 4)
                output["xg_available"] = True
            else:
                output["xg_available"] = False
                output["warnings"].append("xg_data_incomplete")

            # =================================================
            # MARKETS
            # =================================================

            actual_btts = _btts(actual_home, actual_away)
            actual_over25 = _over25(actual_home, actual_away)
            actual_over35 = _over35(actual_home, actual_away)

            output["actual_btts"] = actual_btts
            output["actual_over25"] = actual_over25
            output["actual_over35"] = actual_over35

            predicted_btts = self._extract_probability_boolean(prediction.get("btts"))
            predicted_over25 = self._extract_probability_boolean(prediction.get("over25"))
            predicted_over35 = self._extract_probability_boolean(prediction.get("over35"))

            output["predicted_btts"] = predicted_btts
            output["predicted_over25"] = predicted_over25
            output["predicted_over35"] = predicted_over35

            if predicted_btts is not None:
                output["btts_error"] = int(predicted_btts != actual_btts)
            if predicted_over25 is not None:
                output["total25_error"] = int(predicted_over25 != actual_over25)
            if predicted_over35 is not None:
                output["total35_error"] = int(predicted_over35 != actual_over35)

            # =================================================
            # SEVERITY
            # =================================================

            output["error_severity"] = self._calculate_severity(
                score_distance=output.get("score_distance"),
                xg_error=output.get("error_xg"),
                result_error=output.get("result_error"),
                btts_error=output.get("btts_error"),
                total25_error=output.get("total25_error"),
                total35_error=output.get("total35_error"),
                xg_available=output.get("xg_available", False),
            )

            output["success"] = True

            # =================================================
            # ДИАГНОСТИКА: если нет ошибок, но есть предупреждения
            # =================================================

            if not output.get("errors") and output.get("warnings"):
                output["error_type"] = "data_incomplete"

            return output

        except Exception as exc:
            logger.exception("Prediction Error Analyzer failed")
            output["errors"].append(str(exc))
            return output

    # ========================================================
    # EMPTY RESULT (ОБНОВЛЕНО v2.1)
    # ========================================================

    def _empty_result(self) -> Dict[str, Any]:
        """Единый контракт результата с разделением errors/warnings."""
        return {
            "success": False,
            "analyzer": self.name,
            "analyzer_version": self.version,
            "match_id": None,
            "prediction_available": False,
            "fact_available": False,
            # SCORE
            "predicted_score": None,
            "actual_score": None,
            "score_distance": None,
            "score_correct": None,
            # XG
            "predicted_home_xg": None,
            "predicted_away_xg": None,
            "actual_home_xg": None,
            "actual_away_xg": None,
            "home_xg_delta": None,      # НОВОЕ v2.1
            "away_xg_delta": None,      # НОВОЕ v2.1
            "total_xg_delta": None,     # НОВОЕ v2.1
            "error_xg": None,
            "xg_available": False,
            # RESULT
            "predicted_winner": None,
            "actual_winner": None,
            "result_error": None,
            "winner_correct": None,
            # MARKETS
            "predicted_btts": None,
            "actual_btts": None,
            "btts_error": None,
            "predicted_over25": None,
            "actual_over25": None,
            "total25_error": None,
            "predicted_over35": None,
            "actual_over35": None,
            "total35_error": None,
            # DIAGNOSTICS
            "error_type": None,
            "cause_type": None,
            "error_detail": None,
            "error_severity": None,
            "recommendation": None,
            "errors": [],     # ← только ошибки модели
            "warnings": [],   # ← отсутствие данных (НОВОЕ v2.1)
        }

    # ========================================================
    # PREDICTED SCORE (ИСПРАВЛЕНО v2.1)
    # ========================================================

    @staticmethod
    def _extract_predicted_home_score(prediction: Dict[str, Any]) -> Optional[int]:
        """Извлекает прогнозируемый счёт хозяев. БЕЗ fallback на home_goals."""
        value = prediction.get("predicted_home")
        if value is not None:
            return _safe_int(value)
        # Fallback через predicted_score
        predicted_score = prediction.get("predicted_score")
        if predicted_score and ":" in str(predicted_score):
            try:
                parts = str(predicted_score).split(":", 1)
                return _safe_int(parts[0].strip())
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _extract_predicted_away_score(prediction: Dict[str, Any]) -> Optional[int]:
        """Извлекает прогнозируемый счёт гостей. БЕЗ fallback на away_goals."""
        value = prediction.get("predicted_away")
        if value is not None:
            return _safe_int(value)
        # Fallback через predicted_score
        predicted_score = prediction.get("predicted_score")
        if predicted_score and ":" in str(predicted_score):
            try:
                parts = str(predicted_score).split(":", 1)
                return _safe_int(parts[1].strip())
            except (TypeError, ValueError):
                pass
        return None

    # ========================================================
    # PREDICTED WINNER (ИСПРАВЛЕНО v2.1)
    # ========================================================

    @staticmethod
    def _extract_predicted_winner(prediction: Dict[str, Any]) -> Optional[str]:
        """
        Определяет прогнозируемый исход.

        Приоритет:
            1. predicted_winner (прямое поле)
            2. home_win / draw / away_win (вероятности)
            3. predicted_score → winner
        """
        # 1. Прямое поле
        predicted_winner = prediction.get("predicted_winner")
        if predicted_winner is not None:
            return str(predicted_winner).lower()

        # 2. Вероятности
        home = _safe_float(prediction.get("home_win"))
        draw = _safe_float(prediction.get("draw"))
        away = _safe_float(prediction.get("away_win"))

        values = {}
        if home is not None:
            values["home"] = home
        if draw is not None:
            values["draw"] = draw
        if away is not None:
            values["away"] = away

        if values:
            return max(values, key=values.get)

        # 3. Fallback через predicted_score (НОВОЕ v2.1)
        predicted_score = prediction.get("predicted_score")
        if predicted_score and ":" in str(predicted_score):
            try:
                parts = str(predicted_score).split(":", 1)
                home_goals = _safe_int(parts[0].strip())
                away_goals = _safe_int(parts[1].strip())
                if home_goals is not None and away_goals is not None:
                    return _winner(home_goals, away_goals)
            except (TypeError, ValueError):
                pass

        return None

    # ========================================================
    # PROBABILITY BOOLEAN
    # ========================================================

    @staticmethod
    def _extract_probability_boolean(value: Any) -> Optional[int]:
        probability = _safe_float(value)
        if probability is None:
            return None
        return int(probability >= PROBABILITY_THRESHOLD)

    # ========================================================
    # SEVERITY (ОБНОВЛЕНО v2.1)
    # ========================================================

    @staticmethod
    def _calculate_severity(
        score_distance: Optional[int],
        xg_error: Optional[float],
        result_error: Optional[int],
        btts_error: Optional[int],
        total25_error: Optional[int],
        total35_error: Optional[int],
        xg_available: bool = False,
    ) -> int:
        """Рассчитывает severity. None не считается ошибкой."""
        severity = 0

        if score_distance is not None:
            if score_distance >= SCORE_MAJOR_THRESHOLD:
                severity += 2
            elif score_distance >= SCORE_MINOR_THRESHOLD:
                severity += 1

        if xg_available and xg_error is not None:
            if xg_error >= SEVERITY_XG_HIGH:
                severity += 2
            elif xg_error >= SEVERITY_XG_MEDIUM:
                severity += 1

        if result_error == 1:
            severity += 2

        if btts_error == 1:
            severity += 1
        if total25_error == 1:
            severity += 1
        if total35_error == 1:
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


# ============================================================
# PUBLIC API
# ============================================================

def analyze_prediction_error(
    prediction: Dict[str, Any],
    result: Dict[str, Any],
    predicted_xg: Optional[Dict[str, Any]] = None,
    observed_xg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print(ANALYZER_NAME)
    print("=" * 70)

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

    for key, value in analysis.items():
        print(f"{key}: {value}")

    print("=" * 70)
