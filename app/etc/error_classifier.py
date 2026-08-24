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
         ├── score_error
         ├── xg_error
         ├── result_error
         ├── recommendation
         └── diagnostic flags
                ↓
          ETC CONTROLLER
                ↓
        другие ETC-модули
                ↓
          Learning Memory

============================================================

ВАЖНЫЙ ПРИНЦИП

Этот модуль НЕ:

    - изменяет database.py;
    - изменяет match_results;
    - изменяет predictions;
    - изменяет passports;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - пишет в learning_memory;
    - выполняет обучение;
    - выполняет калибровку;
    - принимает решение об изменении модели.

Он только отвечает на вопрос:

    "Насколько и каким образом FAJ ошибся?"

Решение о дальнейшей реакции принимает ETC.

============================================================

КОНТРАКТ

INPUT:

prediction = {
    predicted_score,
    predicted_home_xg,
    predicted_away_xg,
    predicted_winner,
    predicted_btts,
    predicted_over25,
    predicted_over35,
}

fact = {
    actual_score,
    actual_home_goals,
    actual_away_goals,
    actual_home_xg,
    actual_away_xg,
}

OUTPUT:

{
    success,
    error_type,
    cause_type,
    severity,
    error_score,
    error_xg,
    winner_correct,
    btts_correct,
    over25_correct,
    over35_correct,
    recommendation,
    errors,
}

============================================================

ИСПРАВЛЕНИЯ v2.1
============================================================

1. xg_error() возвращает None вместо 0.0, когда xG отсутствует.

2. _classify_cause() сначала проверяет total xG ошибку,
   затем home/away xG.

3. _severity() — xG недоступен не влияет на severity.

============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.1"
MODULE_NAME = "FAJ ETC Error Classifier v2.1"


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


def _winner(
    home_goals: int,
    away_goals: int,
) -> str:

    if home_goals > away_goals:
        return "home"

    if away_goals > home_goals:
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


def _normalize_bool(
    value: Any,
) -> Optional[int]:

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
    # SCORE ERROR
    # ========================================================

    @staticmethod
    def score_error(
        predicted_score: Optional[str],
        actual_score: Optional[str],
    ) -> int:
        """
        0 = точный счёт угадан.
        1 = точный счёт не угадан.
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
    ) -> Optional[float]:
        """
        Суммарная абсолютная ошибка xG.

        Формула:

            |Pred Home xG - Observed Home xG|
          + |Pred Away xG - Observed Away xG|

        ИСПРАВЛЕНИЕ v2.1:

            Если любой из xG отсутствует,
            возвращается None.
            Это отличает "нет данных" от "ошибка = 0".
        """

        ph = _safe_float(predicted_home_xg)
        pa = _safe_float(predicted_away_xg)

        ah = _safe_float(actual_home_xg)
        aa = _safe_float(actual_away_xg)

        if None in (
            ph,
            pa,
            ah,
            aa,
        ):
            return None

        return round(
            abs(ph - ah)
            + abs(pa - aa),
            4,
        )

    # ========================================================
    # RESULT ERROR
    # ========================================================

    @staticmethod
    def result_error(
        predicted_winner: Any,
        actual_winner: str,
    ) -> int:

        if predicted_winner is None:
            return 1

        return int(
            str(predicted_winner).lower()
            != actual_winner
        )

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

            "error_score": 0,
            "error_xg": 0.0,

            "winner_correct": None,
            "btts_correct": None,
            "over25_correct": None,
            "over35_correct": None,

            "actual_winner": None,
            "actual_btts": None,
            "actual_over25": None,
            "actual_over35": None,

            "errors": [],

            "recommendation": "",

        }

        # ----------------------------------------------------
        # FACT VALIDATION
        # ----------------------------------------------------

        actual_home = _safe_int(
            fact.get("actual_home_goals")
        )

        actual_away = _safe_int(
            fact.get("actual_away_goals")
        )

        if actual_home is None:
            result["errors"].append(
                "actual_home_goals отсутствует."
            )

        if actual_away is None:
            result["errors"].append(
                "actual_away_goals отсутствует."
            )

        if result["errors"]:
            return result

        # ----------------------------------------------------
        # ACTUAL FACTS
        # ----------------------------------------------------

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

        result["actual_winner"] = actual_winner
        result["actual_btts"] = actual_btts
        result["actual_over25"] = actual_over25
        result["actual_over35"] = actual_over35

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        predicted_winner = prediction.get(
            "predicted_winner"
        )

        predicted_btts = _normalize_bool(
            prediction.get("predicted_btts")
        )

        predicted_over25 = _normalize_bool(
            prediction.get("predicted_over25")
        )

        predicted_over35 = _normalize_bool(
            prediction.get("predicted_over35")
        )

        predicted_score = prediction.get(
            "predicted_score"
        )

        actual_score = fact.get(
            "actual_score"
        )

        # ----------------------------------------------------
        # WINNER
        # ----------------------------------------------------

        if predicted_winner is not None:

            winner_correct = int(
                str(predicted_winner).lower()
                == actual_winner
            )

            result["winner_correct"] = winner_correct

            if not winner_correct:

                result["errors"].append(
                    "winner_miss"
                )

        # ----------------------------------------------------
        # EXACT SCORE
        # ----------------------------------------------------

        score_error = self.score_error(
            predicted_score,
            actual_score,
        )

        result["error_score"] = score_error

        if score_error:

            result["errors"].append(
                "score_miss"
            )

        # ----------------------------------------------------
        # BTTS
        # ----------------------------------------------------

        if predicted_btts is not None:

            btts_correct = int(
                predicted_btts
                == actual_btts
            )

            result["btts_correct"] = (
                btts_correct
            )

            if not btts_correct:

                result["errors"].append(
                    "btts_miss"
                )

        # ----------------------------------------------------
        # OVER 2.5
        # ----------------------------------------------------

        if predicted_over25 is not None:

            over25_correct = int(
                predicted_over25
                == actual_over25
            )

            result["over25_correct"] = (
                over25_correct
            )

            if not over25_correct:

                result["errors"].append(
                    "over25_miss"
                )

        # ----------------------------------------------------
        # OVER 3.5
        # ----------------------------------------------------

        if predicted_over35 is not None:

            over35_correct = int(
                predicted_over35
                == actual_over35
            )

            result["over35_correct"] = (
                over35_correct
            )

            if not over35_correct:

                result["errors"].append(
                    "over35_miss"
                )

        # ----------------------------------------------------
        # xG ERROR
        # ----------------------------------------------------

        error_xg = self.xg_error(
            prediction.get(
                "predicted_home_xg"
            ),
            prediction.get(
                "predicted_away_xg"
            ),
            fact.get(
                "actual_home_xg"
            ),
            fact.get(
                "actual_away_xg"
            ),
        )

        result["error_xg"] = error_xg if error_xg is not None else 0.0

        # Проверяем доступность xG
        xg_available = (
            prediction.get("predicted_home_xg") is not None
            and prediction.get("predicted_away_xg") is not None
            and fact.get("actual_home_xg") is not None
            and fact.get("actual_away_xg") is not None
        )

        # Добавляем xg_miss только если xG доступен
        if xg_available and error_xg is not None and error_xg > 0.25:

            result["errors"].append(
                "xg_miss"
            )

        # ----------------------------------------------------
        # ERROR TYPE
        # ----------------------------------------------------

        result["error_type"] = (
            self._classify_error_type(
                result
            )
        )

        # ----------------------------------------------------
        # CAUSE
        # ----------------------------------------------------

        result["cause_type"] = (
            self._classify_cause(
                prediction,
                fact,
                actual_winner,
            )
        )

        # ----------------------------------------------------
        # SEVERITY
        # ----------------------------------------------------

        result["severity"] = (
            self._severity(
                error_type=result["error_type"],
                score_error=score_error,
                error_xg=error_xg if error_xg is not None else 0.0,
                errors_count=len(
                    result["errors"]
                ),
                xg_available=xg_available,
            )
        )

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        result["recommendation"] = (
            self._recommendation(
                result["error_type"],
                result["cause_type"],
                result["severity"],
            )
        )

        result["success"] = True

        return result

    # ========================================================
    # ERROR TYPE
    # ========================================================

    @staticmethod
    def _classify_error_type(
        analysis: Dict[str, Any],
    ) -> str:

        errors = analysis.get(
            "errors",
            [],
        )

        error_xg = _safe_float(
            analysis.get(
                "error_xg"
            ),
            0.0,
        )

        if not errors and error_xg <= 0.25:

            return "correct"

        # Приоритет результата:
        # сначала направление матча,
        # затем счёт,
        # затем рынки,
        # затем xG.

        if "winner_miss" in errors:

            return "winner_miss"

        if "score_miss" in errors:

            return "score_miss"

        if "btts_miss" in errors:

            return "btts_miss"

        if "over25_miss" in errors:

            return "over25_miss"

        if "over35_miss" in errors:

            return "over35_miss"

        if "xg_miss" in errors:

            return "xg_miss"

        return "model_miss"

    # ========================================================
    # CAUSE
    # ========================================================

    @staticmethod
    def _classify_cause(
        prediction: Dict[str, Any],
        fact: Dict[str, Any],
        actual_winner: str,
    ) -> str:
        """
        Определяет предварительную причину.

        Это диагностическая гипотеза,
        а не решение об изменении модели.

        ИСПРАВЛЕНИЕ v2.1:

        Сначала проверяется общая xG ошибка (total),
        затем home/away xG, затем winner.
        """

        predicted_home_xg = _safe_float(
            prediction.get(
                "predicted_home_xg"
            )
        )

        predicted_away_xg = _safe_float(
            prediction.get(
                "predicted_away_xg"
            )
        )

        actual_home_xg = _safe_float(
            fact.get(
                "actual_home_xg"
            )
        )

        actual_away_xg = _safe_float(
            fact.get(
                "actual_away_xg"
            )
        )

        # ----------------------------------------------------
        # TOTAL xG ОШИБКА (v2.1)
        # ----------------------------------------------------

        if None not in (
            predicted_home_xg,
            predicted_away_xg,
            actual_home_xg,
            actual_away_xg,
        ):

            total_predicted = (
                predicted_home_xg + predicted_away_xg
            )

            total_actual = (
                actual_home_xg + actual_away_xg
            )

            total_diff = total_predicted - total_actual

            if total_diff > 0.60:

                return "xg_overestimated"

            if total_diff < -0.60:

                return "xg_underestimated"

        # ----------------------------------------------------
        # HOME xG
        # ----------------------------------------------------

        if None not in (
            predicted_home_xg,
            actual_home_xg,
        ):

            difference = (
                predicted_home_xg
                - actual_home_xg
            )

            if difference > 0.50:

                return (
                    "home_attack_overestimated"
                )

            if difference < -0.50:

                return (
                    "home_attack_underestimated"
                )

        # ----------------------------------------------------
        # AWAY xG
        # ----------------------------------------------------

        if None not in (
            predicted_away_xg,
            actual_away_xg,
        ):

            difference = (
                predicted_away_xg
                - actual_away_xg
            )

            if difference > 0.50:

                return (
                    "away_attack_overestimated"
                )

            if difference < -0.50:

                return (
                    "away_attack_underestimated"
                )

        # ----------------------------------------------------
        # WINNER
        # ----------------------------------------------------

        predicted_winner = prediction.get(
            "predicted_winner"
        )

        if (
            predicted_winner is not None
            and str(
                predicted_winner
            ).lower()
            != actual_winner
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
        xg_available: bool = False,
    ) -> int:
        """
        Шкала:

            0 = correct
            1 = minor
            2 = moderate
            3 = serious
            4 = critical
            5 = catastrophic

        ИСПРАВЛЕНИЕ v2.1:

            Если xG недоступен, он не влияет на severity.
        """

        if error_type == "correct":

            return 0

        score = 0

        # Точный счёт сам по себе
        # не должен автоматически делать
        # ошибку критической.

        if score_error:

            score += 1

        # xG влияет на severity только если доступен
        if xg_available:

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
    def _recommendation(
        error_type: str,
        cause_type: str,
        severity: int,
    ) -> str:

        if error_type == "correct":

            return (
                "Прогноз соответствует факту. "
                "Изменение модели не требуется."
            )

        if (
            cause_type
            == "home_attack_overestimated"
        ):

            return (
                "Проверить завышение атакующего "
                "фактора хозяев и xG-калибровку."
            )

        if (
            cause_type
            == "home_attack_underestimated"
        ):

            return (
                "Проверить занижение атакующего "
                "фактора хозяев и xG-калибровку."
            )

        if (
            cause_type
            == "away_attack_overestimated"
        ):

            return (
                "Проверить завышение атакующего "
                "фактора гостей и xG-калибровку."
            )

        if (
            cause_type
            == "away_attack_underestimated"
        ):

            return (
                "Проверить занижение атакующего "
                "фактора гостей и xG-калибровку."
            )

        if (
            cause_type
            == "match_balance_misread"
        ):

            return (
                "Проверить баланс силы команд, "
                "FAJ Rating и home advantage."
            )

        if severity >= 4:

            return (
                "Серьёзная ошибка. Не изменять параметры "
                "по одному матчу. Требуется накопительный анализ."
            )

        return (
            "Накопить аналогичные ошибки и проверить "
            "систематический характер отклонения."
        )


# ============================================================
# PUBLIC API
# ============================================================

def classify_prediction_error(
    prediction: Dict[str, Any],
    fact: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Публичный API ETC.
    """

    classifier = ErrorClassifier()

    return classifier.classify(
        prediction=prediction,
        fact=fact,
    )


# ============================================================
# SELF TEST
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

    analysis = classifier.classify(
        prediction=prediction,
        fact=fact,
    )

    for key, value in analysis.items():

        print(
            f"{key}: {value}"
        )

    print("=" * 70)
