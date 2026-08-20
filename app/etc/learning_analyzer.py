#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_analyzer.py
============================================================

НАЗНАЧЕНИЕ
-----------
Анализ накопленных ошибок FAJ.

ЦЕПОЧКА:

    learning_records
          +
    learning_events
          +
    learning_memory
          ↓
    LearningAnalyzer
          ↓
    Повторяющиеся ошибки
    Причины
    Тренды
    Severity
    Рекомендации
          ↓
    Parameter Optimizer

МОДУЛЬ НЕ:
    - не изменяет database.py;
    - не изменяет predictions;
    - не изменяет gold_dataset;
    - не изменяет FAJ Rating;
    - не изменяет model_parameters;
    - не обучает модель напрямую.

МОДУЛЬ:
    - анализирует накопленные ошибки;
    - группирует ошибки;
    - определяет частоту;
    - определяет среднюю тяжесть;
    - определяет повторяемость причин;
    - формирует аналитические сигналы для ETC.

============================================================
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Learning Analyzer"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class ErrorPattern:
    """
    Повторяющийся паттерн ошибки.
    """

    error_type: str
    cause_type: str

    count: int = 0
    average_severity: float = 0.0
    average_xg_error: float = 0.0

    matches: List[int] = field(
        default_factory=list
    )

    recommendations: List[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:

        return {
            "error_type": self.error_type,
            "cause_type": self.cause_type,
            "count": self.count,
            "average_severity": self.average_severity,
            "average_xg_error": self.average_xg_error,
            "matches": self.matches,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
        }


# ============================================================
# MAIN CLASS
# ============================================================

class LearningAnalyzer:
    """
    Анализатор накопленного опыта ETC.

    Только чтение БД.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # LOAD
    # ========================================================

    def load_learning_records(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Загружает learning_records.

        Ничего не изменяет.
        """

        limit = max(1, int(limit))

        try:

            rows = self.db.get_learning_records()

            records = [
                dict(row)
                for row in rows
            ]

            return records[:limit]

        except AttributeError:

            logger.warning(
                "FAJDatabase.get_learning_records() отсутствует"
            )

            return []

    # ========================================================
    # GROUP
    # ========================================================

    @staticmethod
    def group_errors(
        records: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Группирует ошибки по error_type + cause_type.
        """

        groups = defaultdict(list)

        for record in records:

            error_type = (
                record.get("error_type")
                or "unknown"
            )

            cause_type = (
                record.get("cause_type")
                or "unknown"
            )

            key = f"{error_type}:{cause_type}"

            groups[key].append(record)

        return dict(groups)

    # ========================================================
    # PATTERNS
    # ========================================================

    def detect_patterns(
        self,
        records: List[Dict[str, Any]],
        minimum_count: int = 2,
    ) -> List[ErrorPattern]:
        """
        Определяет повторяющиеся ошибки.
        """

        groups = self.group_errors(records)

        patterns: List[ErrorPattern] = []

        for key, group in groups.items():

            if len(group) < minimum_count:
                continue

            first = group[0]

            error_type = (
                first.get("error_type")
                or "unknown"
            )

            cause_type = (
                first.get("cause_type")
                or "unknown"
            )

            severities = [
                _safe_float(
                    record.get(
                        "error_severity"
                    )
                )
                for record in group
            ]

            xg_errors = [
                _safe_float(
                    record.get(
                        "error_xg"
                    )
                )
                for record in group
            ]

            matches = []

            recommendations = []

            for record in group:

                match_id = record.get(
                    "match_id"
                )

                if match_id is not None:

                    try:
                        matches.append(
                            int(match_id)
                        )
                    except (TypeError, ValueError):
                        pass

                recommendation = record.get(
                    "recommendation"
                )

                if (
                    recommendation
                    and recommendation
                    not in recommendations
                ):
                    recommendations.append(
                        recommendation
                    )

            average_severity = (
                sum(severities)
                / len(severities)
                if severities
                else 0.0
            )

            average_xg_error = (
                sum(xg_errors)
                / len(xg_errors)
                if xg_errors
                else 0.0
            )

            confidence = min(
                1.0,
                len(group) / 10.0,
            )

            patterns.append(
                ErrorPattern(
                    error_type=error_type,
                    cause_type=cause_type,
                    count=len(group),
                    average_severity=round(
                        average_severity,
                        4,
                    ),
                    average_xg_error=round(
                        average_xg_error,
                        4,
                    ),
                    matches=matches,
                    recommendations=recommendations,
                    confidence=round(
                        confidence,
                        4,
                    ),
                )
            )

        patterns.sort(
            key=lambda item: (
                item.count,
                item.average_severity,
            ),
            reverse=True,
        )

        return patterns

    # ========================================================
    # ERROR FREQUENCY
    # ========================================================

    @staticmethod
    def error_frequency(
        records: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Частота каждого типа ошибки.
        """

        counter = Counter()

        for record in records:

            error_type = (
                record.get("error_type")
                or "unknown"
            )

            counter[error_type] += 1

        return dict(counter)

    # ========================================================
    # CAUSE FREQUENCY
    # ========================================================

    @staticmethod
    def cause_frequency(
        records: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Частота причин ошибок.
        """

        counter = Counter()

        for record in records:

            cause_type = (
                record.get("cause_type")
                or "unknown"
            )

            counter[cause_type] += 1

        return dict(counter)

    # ========================================================
    # SEVERITY
    # ========================================================

    @staticmethod
    def severity_statistics(
        records: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Статистика тяжести ошибок.
        """

        severities = [
            _safe_float(
                record.get(
                    "error_severity"
                )
            )
            for record in records
        ]

        if not severities:

            return {
                "count": 0,
                "average": 0.0,
                "max": 0.0,
            }

        return {
            "count": len(severities),
            "average": round(
                sum(severities)
                / len(severities),
                4,
            ),
            "max": max(severities),
        }

    # ========================================================
    # XG ANALYSIS
    # ========================================================

    @staticmethod
    def xg_statistics(
        records: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Анализ ошибок xG.
        """

        values = [
            _safe_float(
                record.get("error_xg")
            )
            for record in records
            if record.get("error_xg") is not None
        ]

        if not values:

            return {
                "count": 0,
                "average": 0.0,
                "max": 0.0,
            }

        return {
            "count": len(values),
            "average": round(
                sum(values) / len(values),
                4,
            ),
            "max": max(values),
        }

    # ========================================================
    # SIGNALS
    # ========================================================

    def generate_signals(
        self,
        patterns: List[ErrorPattern],
    ) -> List[Dict[str, Any]]:
        """
        Формирует сигналы для следующего слоя ETC.

        ВАЖНО:
        сигналы не являются командами на изменение модели.
        """

        signals = []

        for pattern in patterns:

            signal_strength = (
                pattern.confidence
                * min(
                    1.0,
                    pattern.average_severity / 5.0,
                )
            )

            if pattern.count >= 5:

                priority = "high"

            elif pattern.count >= 3:

                priority = "medium"

            else:

                priority = "low"

            signals.append(
                {
                    "signal_type": (
                        "repeated_prediction_error"
                    ),
                    "error_type": pattern.error_type,
                    "cause_type": pattern.cause_type,
                    "count": pattern.count,
                    "average_severity": (
                        pattern.average_severity
                    ),
                    "average_xg_error": (
                        pattern.average_xg_error
                    ),
                    "confidence": (
                        pattern.confidence
                    ),
                    "signal_strength": round(
                        signal_strength,
                        4,
                    ),
                    "priority": priority,
                    "recommendations": (
                        pattern.recommendations
                    ),
                }
            )

        return signals

    # ========================================================
    # FULL ANALYSIS
    # ========================================================

    def analyze(
        self,
        records: Optional[
            List[Dict[str, Any]]
        ] = None,
        minimum_pattern_count: int = 2,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Полный аналитический цикл.

        Только чтение.
        """

        if records is None:

            records = (
                self.load_learning_records(
                    limit=limit
                )
            )

        patterns = self.detect_patterns(
            records,
            minimum_count=minimum_pattern_count,
        )

        signals = self.generate_signals(
            patterns
        )

        result = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "records_analyzed": len(records),

            "error_frequency": (
                self.error_frequency(records)
            ),

            "cause_frequency": (
                self.cause_frequency(records)
            ),

            "severity": (
                self.severity_statistics(records)
            ),

            "xg": (
                self.xg_statistics(records)
            ),

            "patterns": [
                pattern.to_dict()
                for pattern in patterns
            ],

            "signals": signals,
        }

        logger.info(
            "ETC learning analysis complete: "
            "records=%s patterns=%s signals=%s",
            len(records),
            len(patterns),
            len(signals),
        )

        return result


# ============================================================
# MODULE-LEVEL HELPER
# ============================================================

def analyze_learning(
    db: Optional[FAJDatabase] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Удобная функция запуска анализа.
    """

    analyzer = LearningAnalyzer(db)

    return analyzer.analyze(
        limit=limit
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
    print("FAJ ETC — Learning Analyzer")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    sample_records = [

        {
            "match_id": 101,
            "error_type": "score_miss",
            "cause_type": "home_attack_overestimated",
            "error_severity": 3,
            "error_xg": 0.80,
            "recommendation": (
                "Проверить атакующий фактор хозяев."
            ),
        },

        {
            "match_id": 102,
            "error_type": "score_miss",
            "cause_type": "home_attack_overestimated",
            "error_severity": 2,
            "error_xg": 0.60,
            "recommendation": (
                "Проверить атакующий фактор хозяев."
            ),
        },

        {
            "match_id": 103,
            "error_type": "winner_miss",
            "cause_type": "match_balance_misread",
            "error_severity": 4,
            "error_xg": 1.20,
            "recommendation": (
                "Проверить баланс силы команд."
            ),
        },
    ]

    analyzer = LearningAnalyzer()

    result = analyzer.analyze(
        records=sample_records
    )

    print(
        f"Records: {result['records_analyzed']}"
    )

    print(
        f"Patterns: {len(result['patterns'])}"
    )

    print(
        f"Signals: {len(result['signals'])}"
    )

    print("=" * 70)
