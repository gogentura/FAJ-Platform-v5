#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/error_classifier.py
============================================================

НАЗНАЧЕНИЕ
-----------

Классификация ошибок FAJ Prediction после получения
фактического результата матча.

ИСПРАВЛЕНИЯ v2.2
============================================================

1. xg_error() возвращает None → сохраняется как None (не 0.0)
2. Добавлен тип ошибки data_incomplete (отсутствие xG не = correct)
3. score_error() возвращает None при отсутствии данных
4. xg_available проверяет нормализованные значения
5. Разделены errors (ошибки модели) и warnings (отсутствие данных)

АРХИТЕКТУРА:

    PREDICTION
         +
    MATCH RESULT
         +
    OBSERVED xG
         ↓
    ErrorClassifier
         ↓
    ERROR ANALYSIS
         │
         ├── error_type
         ├── cause_type
         ├── severity
         ├── score_error (None = нет данных)
         ├── xg_error (None = нет данных)
         ├── result_error
         ├── recommendation
         ├── errors (модельные ошибки)
         └── warnings (отсутствие данных)
                ↓
          ETC CONTROLLER
                ↓
        другие ETC-модули
                ↓
          Learning Memory

============================================================

ВАЖНЫЙ ПРИНЦИП

Отсутствующее значение НЕ считается нулём.
Отсутствие данных НЕ считается правильным прогнозом.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.2"
MODULE_NAME = "FAJ ETC Error Classifier v2.2"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
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
# MAIN CLASS
# ============================================================

class ErrorClassifier:
    """
    Чистый диагностический классификатор ETC.

    Не имеет побочных эффектов.
    """

    # ========================================================
    # SCORE ERROR (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def score_error(
        predicted_score: Optional[str],
        actual_score: Optional[str],
    ) -> Optional[int]:
        """
        Возвращает:
            0 = точный счёт угадан
            1 = точный счёт не угадан
            None = нельзя оценить (данные отсутствуют)
        """
        # Если хотя бы один из счетов отсутствует → нельзя оценить
        if not predicted_score or not actual_score:
            return None

        return int(str(predicted_score).strip() != str(actual_score).strip())

    # ========================================================
    # XG ERROR
    # ========================================================

    @staticmethod
    def xg_error(
        predicted_home_xg: Any,
        predicted_away_xg: Any,
        actual_home_xg: Any,
        actual_away_xg: Any,
    ) -> Optional[float]:
        """
        Суммарная абсолютная ошибка xG.

        Возвращает None, если любой xG отсутствует.
        Это отличает "нет данных" от "ошибка = 0".
        """
        ph = _safe_float(predicted_home_xg)
        pa = _safe_float(predicted_away_xg)
        ah = _safe_float(actual_home_xg)
        aa = _safe_float(actual_away_xg)

        if None in (ph, pa, ah, aa):
            return None

        return round(abs(ph - ah) + abs(pa - aa), 4)

    # ========================================================
    # RESULT ERROR
    # ========================================================

    @staticmethod
    def result_error(predicted_winner: Any, actual_winner: str) -> int:
        if predicted_winner is None:
            return 1
        return int(str(predicted_winner).lower() != actual_winner)

    # ========================================================
    # MAIN CLASSIFICATION
    # ========================================================

    def classify(
        self,
        prediction: Dict[str, Any],
        fact: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Полная классификация прогноза относительно факта.
        """
        result: Dict[str, Any] = {
            "success": False,
            "version": MODULE_VERSION,
            "classifier": MODULE_NAME,

            "error_type": None,
            "cause_type": None,

            "severity": 0,

            "error_score": None,      # ← None = нет данных
            "error_xg": None,         # ← None = нет данных

            "winner_correct": None,
            "btts_correct": None,
            "over25_correct": None,
            "over35_correct": None,

            "actual_winner": None,
            "actual_btts": None,
            "actual_over25": None,
            "actual_over35": None,

            "errors": [],             # ← ошибки модели
            "warnings": [],           # ← отсутствие данных
            "xg_available": False,

            "recommendation": "",
        }

        # ----------------------------------------------------
        # FACT VALIDATION
        # ----------------------------------------------------

        actual_home = _safe_int(fact.get("actual_home_goals"))
        actual_away = _safe_int(fact.get("actual_away_goals"))

        if actual_home is None:
            result["warnings"].append("actual_home_goals отсутствует.")

        if actual_away is None:
            result["warnings"].append("actual_away_goals отсутствует.")

        if actual_home is None or actual_away is None:
            return result

        # ----------------------------------------------------
        # ACTUAL FACTS
        # ----------------------------------------------------

        actual_winner = _winner(actual_home, actual_away)
        actual_btts = _btts(actual_home, actual_away)
        actual_over25 = _over25(actual_home, actual_away)
        actual_over35 = _over35(actual_home, actual_away)

        result["actual_winner"] = actual_winner
        result["actual_btts"] = actual_btts
        result["actual_over25"] = actual_over25
        result["actual_over35"] = actual_over35

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        predicted_winner = prediction.get("predicted_winner")
        predicted_btts = _normalize_bool(prediction.get("predicted_btts"))
        predicted_over25 = _normalize_bool(prediction.get("predicted_over25"))
        predicted_over35 = _normalize_bool(prediction.get("predicted_over35"))
        predicted_score = prediction.get("predicted_score")
        actual_score = fact.get("actual_score")

        # ----------------------------------------------------
        # WINNER
        # ----------------------------------------------------

        if predicted_winner is not None:
            winner_correct = int(str(predicted_winner).lower() == actual_winner)
            result["winner_correct"] = winner_correct
            if not winner_correct:
                result["errors"].append("winner_miss")

        # ----------------------------------------------------
        # EXACT SCORE (ИСПРАВЛЕНО v2.2)
        # ----------------------------------------------------

        score_error = self.score_error(predicted_score, actual_score)

        # Сохраняем None как None
        result["error_score"] = score_error

        if score_error is None:
            result["warnings"].append("score_data_missing")
        elif score_error:
            result["errors"].append("score_miss")

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        if predicted_btts is not None:
            btts_correct = int(predicted_btts == actual_btts)
            result["btts_correct"] = btts_correct
            if not btts_correct:
                result["errors"].append("btts_miss")

        # ----------------------------------------------------
        # OVER 2.5
        # ----------------------------------------------------

        if predicted_over25 is not None:
            over25_correct = int(predicted_over25 == actual_over25)
            result["over25_correct"] = over25_correct
            if not over25_correct:
                result["errors"].append("over25_miss")

        # ----------------------------------------------------
        # OVER 3.5
        # ----------------------------------------------------

        if predicted_over35 is not None:
            over35_correct = int(predicted_over35 == actual_over35)
            result["over35_correct"] = over35_correct
            if not over35_correct:
                result["errors"].append("over35_miss")

        # ----------------------------------------------------
        # xG ERROR (ИСПРАВЛЕНО v2.2)
        # ----------------------------------------------------

        # Нормализуем xG для проверки доступности
        ph = _safe_float(prediction.get("predicted_home_xg"))
        pa = _safe_float(prediction.get("predicted_away_xg"))
        ah = _safe_float(fact.get("actual_home_xg"))
        aa = _safe_float(fact.get("actual_away_xg"))

        xg_available = (ph is not None and pa is not None and ah is not None and aa is not None)
        result["xg_available"] = xg_available

        if not xg_available:
            result["warnings"].append("xg_data_incomplete")

        error_xg = self.xg_error(ph, pa, ah, aa)

        # Сохраняем None как None
        result["error_xg"] = error_xg

        # Добавляем xg_miss ТОЛЬКО если xG доступен И ошибка > порога
        if xg_available and error_xg is not None and error_xg > 0.25:
            result["errors"].append("xg_miss")

        # ----------------------------------------------------
        # ERROR TYPE (ИСПРАВЛЕНО v2.2)
        # ----------------------------------------------------

        result["error_type"] = self._classify_error_type(result)

        # ----------------------------------------------------
        # CAUSE
        # ----------------------------------------------------

        result["cause_type"] = self._classify_cause(
            prediction,
            fact,
            actual_winner,
            xg_available,
        )

        # ----------------------------------------------------
        # SEVERITY (ИСПРАВЛЕНО v2.2)
        # ----------------------------------------------------

        result["severity"] = self._severity(
            error_type=result["error_type"],
            score_error=score_error,
            error_xg=error_xg,
            errors_count=len(result["errors"]),
            xg_available=xg_available,
        )

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        result["recommendation"] = self._recommendation(
            result["error_type"],
            result["cause_type"],
            result["severity"],
        )

        result["success"] = True

        return result

    # ========================================================
    # ERROR TYPE (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def _classify_error_type(analysis: Dict[str, Any]) -> str:
        errors = analysis.get("errors", [])
        error_xg = analysis.get("error_xg")  # ← может быть None
        xg_available = analysis.get("xg_available", False)

        # Если есть ошибки в результативных компонентах
        if errors:
            # Приоритет ошибок
            for priority in ("winner_miss", "score_miss", "btts_miss", "over25_miss", "over35_miss"):
                if priority in errors:
                    return priority

        # Если xG доступен и ошибочен
        if xg_available and error_xg is not None and error_xg > 0.25:
            return "xg_miss"

        # Если xG доступен и есть ошибка (даже маленькая)
        if xg_available and error_xg is not None and error_xg > 0.0:
            return "xg_miss"

        # Если xG недоступен, но других ошибок нет
        if not xg_available and not errors:
            return "data_incomplete"

        return "correct"

    # ========================================================
    # CAUSE
    # ========================================================

    @staticmethod
    def _classify_cause(
        prediction: Dict[str, Any],
        fact: Dict[str, Any],
        actual_winner: str,
        xg_available: bool = False,
    ) -> str:
        """
        Определяет предварительную причину.

        Если xG недоступен, использует только информацию об исходе.
        """

        predicted_home_xg = _safe_float(prediction.get("predicted_home_xg"))
        predicted_away_xg = _safe_float(prediction.get("predicted_away_xg"))
        actual_home_xg = _safe_float(fact.get("actual_home_xg"))
        actual_away_xg = _safe_float(fact.get("actual_away_xg"))

        # ----------------------------------------------------
        # TOTAL xG ОШИБКА (только если xG доступен)
        # ----------------------------------------------------

        if xg_available and None not in (predicted_home_xg, predicted_away_xg, actual_home_xg, actual_away_xg):
            total_predicted = predicted_home_xg + predicted_away_xg
            total_actual = actual_home_xg + actual_away_xg
            total_diff = total_predicted - total_actual

            if total_diff > 0.60:
                return "xg_overestimated"
            if total_diff < -0.60:
                return "xg_underestimated"

        # ----------------------------------------------------
        # HOME xG
        # ----------------------------------------------------

        if None not in (predicted_home_xg, actual_home_xg):
            difference = predicted_home_xg - actual_home_xg
            if difference > 0.50:
                return "home_attack_overestimated"
            if difference < -0.50:
                return "home_attack_underestimated"

        # ----------------------------------------------------
        # AWAY xG
        # ----------------------------------------------------

        if None not in (predicted_away_xg, actual_away_xg):
            difference = predicted_away_xg - actual_away_xg
            if difference > 0.50:
                return "away_attack_overestimated"
            if difference < -0.50:
                return "away_attack_underestimated"

        # ----------------------------------------------------
        # WINNER (даже если xG недоступен)
        # ----------------------------------------------------

        predicted_winner = prediction.get("predicted_winner")
        if predicted_winner is not None and str(predicted_winner).lower() != actual_winner:
            return "match_balance_misread"

        return "model_uncertainty"

    # ========================================================
    # SEVERITY (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def _severity(
        error_type: str,
        score_error: Optional[int],
        error_xg: Optional[float],
        errors_count: int,
        xg_available: bool = False,
    ) -> int:
        """
        Шкала:
            0 = correct / data_incomplete
            1 = minor
            2 = moderate
            3 = serious
            4 = critical
            5 = catastrophic
        """
        if error_type in ("correct", "data_incomplete"):
            return 0

        score = 0

        # score_error: None = нет данных (не добавляем)
        if score_error == 1:
            score += 1

        # xG влияет только если доступен
        if xg_available and error_xg is not None:
            if error_xg >= 1.50:
                score += 3
            elif error_xg >= 1.00:
                score += 2
            elif error_xg >= 0.50:
                score += 1

        if errors_count >= 4:
            score += 2
        elif errors_count >= 2:
            score += 1

        if error_type == "winner_miss":
            score += 1

        if score >= 6:
            return 5
        if score >= 5:
            return 4
        if score >= 3:
            return 3
        if score >= 2:
            return 2
        return 1

    # ========================================================
    # RECOMMENDATION
    # ========================================================

    @staticmethod
    def _recommendation(error_type: str, cause_type: str, severity: int) -> str:
        if error_type == "correct":
            return "Прогноз соответствует факту. Изменение модели не требуется."

        if error_type == "data_incomplete":
            return "Данные для оценки неполные. Проверьте факты матча."

        cause_map = {
            "home_attack_overestimated": "Проверить завышение атакующего фактора хозяев и xG-калибровку.",
            "home_attack_underestimated": "Проверить занижение атакующего фактора хозяев и xG-калибровку.",
            "away_attack_overestimated": "Проверить завышение атакующего фактора гостей и xG-калибровку.",
            "away_attack_underestimated": "Проверить занижение атакующего фактора гостей и xG-калибровку.",
            "match_balance_misread": "Проверить баланс силы команд, FAJ Rating и home advantage.",
        }

        if cause_type in cause_map:
            return cause_map[cause_type]

        if severity >= 4:
            return "Серьёзная ошибка. Не изменять параметры по одному матчу. Требуется накопительный анализ."

        return "Накопить аналогичные ошибки и проверить систематический характер отклонения."


# ============================================================
# PUBLIC API
# ============================================================

def classify_prediction_error(
    prediction: Dict[str, Any],
    fact: Dict[str, Any],
) -> Dict[str, Any]:
    """Публичный API ETC."""
    classifier = ErrorClassifier()
    return classifier.classify(prediction=prediction, fact=fact)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("FAJ ETC — Error Classifier")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    prediction = {
        "predicted_score": "2:1",
        "predicted_home_xg": 1.80,
        "predicted_away_xg": 0.90,
        "predicted_winner": "home",
        "predicted_btts": 1,
        "predicted_over25": 1,
        "predicted_over35": 0,
    }

    fact = {
        "actual_score": "1:2",
        "actual_home_goals": 1,
        "actual_away_goals": 2,
        "actual_home_xg": 0.95,
        "actual_away_xg": 1.75,
    }

    classifier = ErrorClassifier()
    analysis = classifier.classify(prediction=prediction, fact=fact)

    for key, value in analysis.items():
        print(f"{key}: {value}")

    print("=" * 70)
