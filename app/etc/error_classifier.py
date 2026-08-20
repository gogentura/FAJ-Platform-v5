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
Классификация ошибок прогноза FAJ.

ЦЕПОЧКА:

    FAJ Prediction
          +
    Match Result
          +
    Observed xG
          ↓
    ErrorClassifier
          ↓
    error_type
    cause_type
    severity
    error_score
    error_xg
    recommendation
          ↓
    learning_records / learning_events

МОДУЛЬ НЕ:
    - не изменяет database.py;
    - не изменяет predictions;
    - не изменяет gold_dataset;
    - не меняет FAJ Rating;
    - не меняет model_parameters;
    - не обучает модель.

МОДУЛЬ:
    - сравнивает прогноз с фактом;
    - классифицирует ошибку;
    - рассчитывает величину ошибки;
    - формирует рекомендацию для ETC.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Error Classifier"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _winner(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def _btts(home_goals: int, away_goals: int) -> int:
    return int(home_goals > 0 and away_goals > 0)


def _over25(home_goals: int, away_goals: int) -> int:
    return int((home_goals + away_goals) > 2)


def _over35(home_goals: int, away_goals: int) -> int:
    return int((home_goals + away_goals) > 3)


# ============================================================
# MAIN CLASS
# ============================================================

class ErrorClassifier:
    """
    Классификатор ошибок ETC.

    Работает только с переданными данными.
    """

    # ========================================================
    # SCORE ERROR
    # ========================================================

    @staticmethod
    def score_error(
        predicted_score: Optional[str],
        actual_score: Optional[str],
    ) -> int:
        """
        0 — точный счёт угадан.
        1 — точный счёт не угадан.
        """

        if not predicted_score or not actual_score:
            return 1

        return int(
            str(predicted_score).strip()
            != str(actual_score).strip()
        )

    # ========================================================
    # XG ERROR
    # ========================================================

    @staticmethod
    def xg_error(
        predicted_home_xg: Any,
        predicted_away_xg: Any,
        actual_home_xg: Any,
        actual_away_xg: Any,
    ) -> float:
        """
        Суммарная абсолютная ошибка xG.
        """

        ph = _safe_float(predicted_home_xg)
        pa = _safe_float(predicted_away_xg)
        ah = _safe_float(actual_home_xg)
        aa = _safe_float(actual_away_xg)

        if None in (ph, pa, ah, aa):
            return 0.0

        return round(
            abs(ph - ah) + abs(pa - aa),
            4,
        )

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    def classify(
        self,
        prediction: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Полностью классифицирует прогноз относительно факта.

        Ожидает максимально простой словарь.

        prediction:
            predicted_score
            predicted_home_xg
            predicted_away_xg
            predicted_winner
            predicted_btts
            predicted_over25
            predicted_over35

        result:
            actual_score
            actual_home_goals
            actual_away_goals
            actual_home_xg
            actual_away_xg
        """

        actual_home = _safe_int(
            result.get("actual_home_goals")
        )
        actual_away = _safe_int(
            result.get("actual_away_goals")
        )

        if actual_home is None or actual_away is None:
            raise ValueError(
                "Фактические голы обязательны"
            )

        actual_winner = _winner(
            actual_home,
            actual_away,
        )

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

        predicted_winner = (
            prediction.get("predicted_winner")
        )

        predicted_btts = prediction.get(
            "predicted_btts"
        )

        predicted_over25 = prediction.get(
            "predicted_over25"
        )

        predicted_over35 = prediction.get(
            "predicted_over35"
        )

        predicted_score = prediction.get(
            "predicted_score"
        )

        actual_score = result.get(
            "actual_score"
        )

        score_error = self.score_error(
            predicted_score,
            actual_score,
        )

        error_xg = self.xg_error(
            prediction.get("predicted_home_xg"),
            prediction.get("predicted_away_xg"),
            result.get("actual_home_xg"),
            result.get("actual_away_xg"),
        )

        errors = []

        # ----------------------------------------------------
        # WINNER
        # ----------------------------------------------------

        if predicted_winner is not None:
            if str(predicted_winner) != actual_winner:
                errors.append("winner_miss")

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        if score_error:
            errors.append("score_miss")

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        if predicted_btts is not None:
            if int(predicted_btts) != actual_btts:
                errors.append("btts_miss")

        # ----------------------------------------------------
        # TOTAL 2.5
        # ----------------------------------------------------

        if predicted_over25 is not None:
            if int(predicted_over25) != actual_over25:
                errors.append("over25_miss")

        # ----------------------------------------------------
        # TOTAL 3.5
        # ----------------------------------------------------

        if predicted_over35 is not None:
            if int(predicted_over35) != actual_over35:
                errors.append("over35_miss")

        # ----------------------------------------------------
        # ERROR TYPE
        # ----------------------------------------------------

        if not errors and error_xg <= 0.25:
            error_type = "correct"

        elif "score_miss" in errors:
            error_type = "score_miss"

        elif "winner_miss" in errors:
            error_type = "winner_miss"

        elif "btts_miss" in errors:
            error_type = "btts_miss"

        elif "over25_miss" in errors:
            error_type = "over25_miss"

        elif "over35_miss" in errors:
            error_type = "over35_miss"

        else:
            error_type = "xg_miss"

        # ----------------------------------------------------
        # CAUSE
        # ----------------------------------------------------

        cause_type = self._classify_cause(
            prediction,
            result,
            actual_winner,
        )

        # ----------------------------------------------------
        # SEVERITY
        # ----------------------------------------------------

        severity = self._severity(
            error_type=error_type,
            score_error=score_error,
            error_xg=error_xg,
            errors_count=len(errors),
        )

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        recommendation = self._recommendation(
            error_type,
            cause_type,
            severity,
        )

        return {
            "error_type": error_type,
            "cause_type": cause_type,
            "error_severity": severity,
            "error_score": score_error,
            "error_xg": error_xg,
            "actual_winner": actual_winner,
            "actual_btts": actual_btts,
            "actual_over25": actual_over25,
            "actual_over35": actual_over35,
            "errors": errors,
            "recommendation": recommendation,
        }

    # ========================================================
    # CAUSE
    # ========================================================

    @staticmethod
    def _classify_cause(
        prediction: Dict[str, Any],
        result: Dict[str, Any],
        actual_winner: str,
    ) -> str:
        """
        Определяет предварительную причину ошибки.

        Это НЕ окончательный вывод ETC.
        """

        predicted_home_xg = _safe_float(
            prediction.get("predicted_home_xg")
        )

        predicted_away_xg = _safe_float(
            prediction.get("predicted_away_xg")
        )

        actual_home_xg = _safe_float(
            result.get("actual_home_xg")
        )

        actual_away_xg = _safe_float(
            result.get("actual_away_xg")
        )

        if None not in (
            predicted_home_xg,
            actual_home_xg,
        ):
            if predicted_home_xg - actual_home_xg > 0.50:
                return "home_attack_overestimated"

            if actual_home_xg - predicted_home_xg > 0.50:
                return "home_attack_underestimated"

        if None not in (
            predicted_away_xg,
            actual_away_xg,
        ):
            if predicted_away_xg - actual_away_xg > 0.50:
                return "away_attack_overestimated"

            if actual_away_xg - predicted_away_xg > 0.50:
                return "away_attack_underestimated"

        predicted_winner = prediction.get(
            "predicted_winner"
        )

        if (
            predicted_winner is not None
            and str(predicted_winner) != actual_winner
        ):
            return "match_balance_misread"

        return "model_uncertainty"

    # ========================================================
    # SEVERITY
    # ========================================================

    @staticmethod
    def _severity(
        error_type: str,
        score_error: int,
        error_xg: float,
        errors_count: int,
    ) -> int:
        """
        Severity:

        0 — correct
        1 — minor
        2 — moderate
        3 — serious
        4 — critical
        5 — catastrophic
        """

        if error_type == "correct":
            return 0

        score = 0

        if score_error:
            score += 2

        if error_xg >= 1.50:
            score += 3
        elif error_xg >= 1.00:
            score += 2
        elif error_xg >= 0.50:
            score += 1

        if errors_count >= 3:
            score += 2
        elif errors_count >= 2:
            score += 1

        if score >= 5:
            return 5

        if score >= 4:
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
    def _recommendation(
        error_type: str,
        cause_type: str,
        severity: int,
    ) -> str:
        """
        Формирует текстовую рекомендацию.

        Важно:
        это только рекомендация.
        Автоматического изменения параметров здесь нет.
        """

        if error_type == "correct":
            return "Изменение параметров не требуется."

        if cause_type == "home_attack_overestimated":
            return (
                "Проверить завышение атакующего фактора "
                "хозяев и xG-калибровку."
            )

        if cause_type == "home_attack_underestimated":
            return (
                "Проверить занижение атакующего фактора "
                "хозяев и xG-калибровку."
            )

        if cause_type == "away_attack_overestimated":
            return (
                "Проверить завышение атакующего фактора "
                "гостей и xG-калибровку."
            )

        if cause_type == "away_attack_underestimated":
            return (
                "Проверить занижение атакующего фактора "
                "гостей и xG-калибровку."
            )

        if cause_type == "match_balance_misread":
            return (
                "Проверить баланс силы команд, "
                "FAJ Rating и home advantage."
            )

        if severity >= 4:
            return (
                "Критическая ошибка. Требуется дополнительный "
                "анализ перед изменением параметров."
            )

        return (
            "Провести накопительный анализ аналогичных "
            "ошибок перед изменением модели."
        )


# ============================================================
# MODULE-LEVEL HELPER
# ============================================================

def classify_prediction_error(
    prediction: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Удобная функция для ETC.
    """

    classifier = ErrorClassifier()

    return classifier.classify(
        prediction=prediction,
        result=result,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

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

    result = {
        "actual_score": "1:2",
        "actual_home_goals": 1,
        "actual_away_goals": 2,
        "actual_home_xg": 0.95,
        "actual_away_xg": 1.75,
    }

    classifier = ErrorClassifier()

    result_data = classifier.classify(
        prediction,
        result,
    )

    for key, value in result_data.items():
        print(f"{key}: {value}")

    print("=" * 70)
