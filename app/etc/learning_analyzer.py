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
Анализ накопленной памяти и результатов обучения ETC.

РОЛЬ В АРХИТЕКТУРЕ:

    MATCH RESULT
         │
         ▼
    Statistical Analyzer
         │
         ▼
    Error Classifier
         │
         ▼
    Learning Engine
         │
         ▼
    Learning Memory
         │
         ▼
    Learning Analyzer
         │
         ├── repeated errors
         ├── causes
         ├── trends
         ├── severity
         ├── xG deviations
         └── ETC signals
                 │
                 ▼
          Parameter Optimizer


ВАЖНО
------
LearningAnalyzer НЕ:

    - не изменяет database.py;
    - не изменяет match_results;
    - не изменяет predictions;
    - не изменяет gold_dataset;
    - не изменяет FAJ Rating;
    - не изменяет model_parameters;
    - не запускает обучение;
    - не применяет рекомендации автоматически;
    - не удаляет learning_memory;
    - не переписывает старую память.

LearningAnalyzer ТОЛЬКО:

    - читает накопленные данные;
    - анализирует повторяющиеся ошибки;
    - группирует причины;
    - считает частоту;
    - считает severity;
    - анализирует xG deviation;
    - формирует аналитические сигналы;
    - передаёт сигналы следующему уровню ETC.

============================================================
ИСТОЧНИКИ ДАННЫХ
============================================================

Основной источник:

    learning_memory

Дополнительный источник:

    learning_records

Learning Memory является append-only историей эволюции ETC.

Формат памяти:

    event_type
    object
    feature
    before_value
    after_value
    delta
    reason
    confidence
    impact
    algorithm
    model_version
    reference_id
    created_at

============================================================
ПРИНЦИП
============================================================

ANALYZE ≠ LEARN

LearningAnalyzer обнаруживает:

    "модель систематически ошибается здесь"

но НЕ говорит:

    "немедленно измени параметр".

Окончательное решение об изменении параметров
принимает ParameterOptimizer / LearningEngine
согласно общему ETC pipeline.

============================================================
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "2.0"
MODULE_NAME = "ETC Learning Analyzer"


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Безопасное преобразование в float.
    """

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
    """
    Безопасное преобразование в int.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):

        return default


def _unique_ints(
    values: List[Any],
) -> List[int]:
    """
    Уникальные integer ID с сохранением порядка.
    """

    result: List[int] = []
    seen = set()

    for value in values:

        try:

            item = int(value)

        except (TypeError, ValueError):

            continue

        if item in seen:
            continue

        seen.add(item)
        result.append(item)

    return result


# ============================================================
# DATA STRUCTURES
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

    average_confidence: float = 0.0
    average_impact: float = 0.0

    matches: List[int] = field(
        default_factory=list
    )

    recommendations: List[str] = field(
        default_factory=list
    )

    signal_strength: float = 0.0
    priority: str = "low"

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "error_type": self.error_type,
            "cause_type": self.cause_type,
            "count": self.count,
            "average_severity": (
                self.average_severity
            ),
            "average_xg_error": (
                self.average_xg_error
            ),
            "average_confidence": (
                self.average_confidence
            ),
            "average_impact": (
                self.average_impact
            ),
            "matches": list(self.matches),
            "recommendations": list(
                self.recommendations
            ),
            "signal_strength": (
                self.signal_strength
            ),
            "priority": self.priority,
        }


# ============================================================
# MAIN CLASS
# ============================================================

class LearningAnalyzer:
    """
    Анализатор накопленного опыта ETC.

    Только чтение.

    Основной источник:
        learning_memory

    Дополнительный источник:
        learning_records
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # LOAD LEARNING MEMORY
    # ========================================================

    def load_learning_memory(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Загружает learning_memory.

        Использует единый интерфейс
        LearningMemory / database.py.

        Ничего не изменяет.
        """

        limit = max(1, int(limit))

        try:

            rows = self.db.get_learning_memory(
                limit=limit
            )

            if rows is None:
                return []

            return [
                dict(row)
                for row in rows
            ]

        except AttributeError:

            logger.warning(
                "FAJDatabase.get_learning_memory() "
                "отсутствует"
            )

            return []

        except Exception as exc:

            logger.warning(
                "Unable to load learning_memory: %s",
                exc,
            )

            return []

    # ========================================================
    # LOAD LEARNING RECORDS
    # ========================================================

    def load_learning_records(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Загружает learning_records.

        Используется как дополнительный источник
        совместимости со старым learning pipeline.

        Ничего не изменяет.
        """

        limit = max(1, int(limit))

        try:

            rows = self.db.get_learning_records()

            if rows is None:
                return []

            records = [
                dict(row)
                for row in rows
            ]

            return records[:limit]

        except AttributeError:

            logger.info(
                "FAJDatabase.get_learning_records() "
                "отсутствует — используем только memory"
            )

            return []

        except Exception as exc:

            logger.warning(
                "Unable to load learning_records: %s",
                exc,
            )

            return []

    # ========================================================
    # NORMALIZE MEMORY
    # ========================================================

    @staticmethod
    def normalize_memory(
        memory: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Приводит learning_memory к аналитическому формату.

        ВАЖНО:

        learning_memory может содержать разные типы событий:

            xg_calibration
            club_rating_update
            parameter_update
            prediction_error

        Анализатор не должен считать все события
        prediction errors.

        Только prediction_error является
        непосредственным событием ошибки прогноза.
        """

        result: List[Dict[str, Any]] = []

        for row in memory:

            event_type = (
                row.get("event_type")
                or ""
            )

            if event_type != "prediction_error":
                continue

            object_type = (
                row.get("object")
                or ""
            )

            reference_id = row.get(
                "reference_id"
            )

            match_id = None

            if reference_id is not None:

                match_id = _safe_int(
                    reference_id,
                    0,
                )

                if match_id <= 0:
                    match_id = None

            feature = (
                row.get("feature")
                or "unknown"
            )

            reason = (
                row.get("reason")
                or ""
            )

            confidence = _safe_float(
                row.get("confidence"),
                1.0,
            )

            impact = _safe_float(
                row.get("impact"),
                1.0,
            )

            after_value = row.get(
                "after_value"
            )

            severity = _safe_int(
                after_value,
                0,
            )

            # ------------------------------------------------
            # CAUSE
            # ------------------------------------------------
            #
            # LearningMemory record_prediction_error()
            # сохраняет:
            #
            #     cause_type: reason
            #
            # поэтому пытаемся восстановить cause_type
            # из начала reason.
            #
            cause_type = "unknown"

            if ":" in reason:

                possible_cause, _, _ = (
                    reason.partition(":")
                )

                possible_cause = (
                    possible_cause.strip()
                )

                if possible_cause:
                    cause_type = possible_cause

            result.append(
                {
                    "match_id": match_id,
                    "error_type": feature,
                    "cause_type": cause_type,
                    "error_severity": severity,
                    "error_xg": 0.0,
                    "confidence": confidence,
                    "impact": impact,
                    "recommendation": reason,
                    "memory_id": row.get("id"),
                    "event_type": event_type,
                    "created_at": row.get(
                        "created_at"
                    ),
                    "object": object_type,
                    "model_version": row.get(
                        "model_version"
                    ),
                    "algorithm": row.get(
                        "algorithm"
                    ),
                }
            )

        return result

    # ========================================================
    # NORMALIZE LEGACY RECORDS
    # ========================================================

    @staticmethod
    def normalize_learning_records(
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Нормализует старые learning_records.

        Этот источник используется только если
        learning_records реально существуют.

        Формат сохраняется совместимым
        со старым ETC.
        """

        result: List[Dict[str, Any]] = []

        for record in records:

            result.append(
                {
                    "match_id": record.get(
                        "match_id"
                    ),
                    "error_type": (
                        record.get("error_type")
                        or "unknown"
                    ),
                    "cause_type": (
                        record.get("cause_type")
                        or "unknown"
                    ),
                    "error_severity": _safe_int(
                        record.get(
                            "error_severity"
                        )
                    ),
                    "error_xg": _safe_float(
                        record.get(
                            "error_xg"
                        )
                    ),
                    "confidence": _safe_float(
                        record.get(
                            "confidence"
                        ),
                        1.0,
                    ),
                    "impact": _safe_float(
                        record.get(
                            "impact"
                        ),
                        1.0,
                    ),
                    "recommendation": (
                        record.get(
                            "recommendation"
                        )
                    ),
                    "memory_id": None,
                    "event_type": (
                        record.get(
                            "event_type"
                        )
                    ),
                    "created_at": (
                        record.get(
                            "created_at"
                        )
                    ),
                    "object": (
                        record.get(
                            "object"
                        )
                    ),
                    "model_version": (
                        record.get(
                            "model_version"
                        )
                    ),
                    "algorithm": (
                        record.get(
                            "algorithm"
                        )
                    ),
                }
            )

        return result

    # ========================================================
    # GROUP
    # ========================================================

    @staticmethod
    def group_errors(
        records: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Группирует ошибки:

            error_type + cause_type
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

            key = (
                f"{error_type}:"
                f"{cause_type}"
            )

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

        minimum_count = max(
            1,
            int(minimum_count),
        )

        groups = self.group_errors(
            records
        )

        patterns: List[ErrorPattern] = []

        for _, group in groups.items():

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
                    item.get(
                        "error_severity"
                    )
                )
                for item in group
            ]

            xg_errors = [
                _safe_float(
                    item.get(
                        "error_xg"
                    )
                )
                for item in group
            ]

            confidences = [
                _safe_float(
                    item.get(
                        "confidence"
                    ),
                    1.0,
                )
                for item in group
            ]

            impacts = [
                _safe_float(
                    item.get(
                        "impact"
                    ),
                    1.0,
                )
                for item in group
            ]

            matches = _unique_ints(
                [
                    item.get("match_id")
                    for item in group
                    if item.get("match_id")
                    is not None
                ]
            )

            recommendations: List[str] = []

            for item in group:

                recommendation = item.get(
                    "recommendation"
                )

                if (
                    recommendation
                    and recommendation
                    not in recommendations
                ):

                    recommendations.append(
                        str(recommendation)
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

            average_confidence = (
                sum(confidences)
                / len(confidences)
                if confidences
                else 0.0
            )

            average_impact = (
                sum(impacts)
                / len(impacts)
                if impacts
                else 0.0
            )

            # -----------------------------------------------
            # CONFIDENCE OF PATTERN
            # -----------------------------------------------
            #
            # Чем больше независимых наблюдений,
            # тем сильнее статистический сигнал.
            #
            # Это НЕ вероятность истины.
            #

            sample_confidence = min(
                1.0,
                len(group) / 10.0,
            )

            pattern_confidence = (
                sample_confidence
                * average_confidence
            )

            # -----------------------------------------------
            # SIGNAL STRENGTH
            # -----------------------------------------------

            severity_factor = min(
                1.0,
                average_severity / 5.0,
            )

            impact_factor = min(
                1.0,
                max(0.0, average_impact),
            )

            signal_strength = (
                pattern_confidence
                * severity_factor
                * max(
                    0.5,
                    impact_factor,
                )
            )

            # -----------------------------------------------
            # PRIORITY
            # -----------------------------------------------

            if (
                len(group) >= 5
                and signal_strength >= 0.35
            ):

                priority = "high"

            elif (
                len(group) >= 3
                and signal_strength >= 0.20
            ):

                priority = "medium"

            else:

                priority = "low"

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
                    average_confidence=round(
                        average_confidence,
                        4,
                    ),
                    average_impact=round(
                        average_impact,
                        4,
                    ),
                    matches=matches,
                    recommendations=(
                        recommendations
                    ),
                    signal_strength=round(
                        signal_strength,
                        4,
                    ),
                    priority=priority,
                )
            )

        patterns.sort(
            key=lambda item: (
                item.signal_strength,
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
        Частота типов ошибок.
        """

        counter = Counter()

        for record in records:

            error_type = (
                record.get("error_type")
                or "unknown"
            )

            counter[error_type] += 1

        return dict(
            counter.most_common()
        )

    # ========================================================
    # CAUSE FREQUENCY
    # ========================================================

    @staticmethod
    def cause_frequency(
        records: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Частота причин.
        """

        counter = Counter()

        for record in records:

            cause_type = (
                record.get("cause_type")
                or "unknown"
            )

            counter[cause_type] += 1

        return dict(
            counter.most_common()
        )

    # ========================================================
    # SEVERITY STATISTICS
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
    # XG STATISTICS
    # ========================================================

    @staticmethod
    def xg_statistics(
        records: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Статистика ошибок xG.

        Если источник learning_memory не содержит
        отдельного error_xg, значение остаётся 0.
        """

        values = [
            _safe_float(
                record.get(
                    "error_xg"
                )
            )
            for record in records
            if record.get("error_xg")
            is not None
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
                sum(values)
                / len(values),
                4,
            ),
            "max": max(values),
        }

    # ========================================================
    # MEMORY STATISTICS
    # ========================================================

    @staticmethod
    def memory_statistics(
        memory: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Статистика learning_memory.

        Показывает, какие типы эволюционных событий
        накоплены ETC.
        """

        event_counter = Counter()
        algorithm_counter = Counter()
        model_counter = Counter()

        for row in memory:

            event_counter[
                row.get(
                    "event_type"
                )
                or "unknown"
            ] += 1

            algorithm_counter[
                row.get(
                    "algorithm"
                )
                or "unknown"
            ] += 1

            model_counter[
                row.get(
                    "model_version"
                )
                or "unknown"
            ] += 1

        return {
            "records": len(memory),
            "event_types": dict(
                event_counter.most_common()
            ),
            "algorithms": dict(
                algorithm_counter.most_common()
            ),
            "model_versions": dict(
                model_counter.most_common()
            ),
        }

    # ========================================================
    # SIGNALS
    # ========================================================

    def generate_signals(
        self,
        patterns: List[ErrorPattern],
    ) -> List[Dict[str, Any]]:
        """
        Формирует сигналы для Parameter Optimizer.

        ВАЖНО:

        сигнал != изменение параметра.

        Этот метод только сообщает:

            "есть повторяющийся паттерн,
             который стоит проверить".
        """

        signals: List[Dict[str, Any]] = []

        for pattern in patterns:

            signals.append(
                {
                    "signal_type": (
                        "repeated_prediction_error"
                    ),

                    "error_type": (
                        pattern.error_type
                    ),

                    "cause_type": (
                        pattern.cause_type
                    ),

                    "count": (
                        pattern.count
                    ),

                    "average_severity": (
                        pattern.average_severity
                    ),

                    "average_xg_error": (
                        pattern.average_xg_error
                    ),

                    "average_confidence": (
                        pattern.average_confidence
                    ),

                    "average_impact": (
                        pattern.average_impact
                    ),

                    "signal_strength": (
                        pattern.signal_strength
                    ),

                    "priority": (
                        pattern.priority
                    ),

                    "matches": list(
                        pattern.matches
                    ),

                    "recommendations": list(
                        pattern.recommendations
                    ),
                }
            )

        return signals

    # ========================================================
    # TOP SIGNALS
    # ========================================================

    @staticmethod
    def top_signals(
        signals: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает наиболее сильные сигналы.
        """

        limit = max(
            1,
            int(limit),
        )

        return sorted(
            signals,
            key=lambda item: (
                _safe_float(
                    item.get(
                        "signal_strength"
                    )
                ),
                _safe_int(
                    item.get(
                        "count"
                    )
                ),
            ),
            reverse=True,
        )[:limit]

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
        include_legacy_records: bool = True,
    ) -> Dict[str, Any]:
        """
        Полный аналитический цикл.

        Только чтение БД.

        Если records переданы вручную —
        используется именно этот набор.

        Если records не переданы:

            1. читается learning_memory;
            2. prediction_error события
               преобразуются в аналитические записи;
            3. при необходимости добавляются
               legacy learning_records.
        """

        memory: List[Dict[str, Any]] = []

        legacy_records: List[
            Dict[str, Any]
        ] = []

        if records is None:

            memory = self.load_learning_memory(
                limit=limit
            )

            records = self.normalize_memory(
                memory
            )

            if include_legacy_records:

                legacy_records = (
                    self.load_learning_records(
                        limit=limit
                    )
                )

                normalized_legacy = (
                    self.normalize_learning_records(
                        legacy_records
                    )
                )

                # ------------------------------------------------
                # ВАЖНО
                #
                # Не дублируем prediction_error,
                # если он уже присутствует в memory.
                #
                # Legacy records добавляются только
                # как дополнительный источник.
                # ------------------------------------------------

                existing_memory_ids = {
                    item.get("match_id")
                    for item in records
                    if item.get("match_id")
                    is not None
                }

                for item in normalized_legacy:

                    match_id = item.get(
                        "match_id"
                    )

                    if (
                        match_id is not None
                        and match_id
                        in existing_memory_ids
                    ):
                        continue

                    records.append(item)

        else:

            records = list(records)

        # =====================================================
        # ANALYSIS
        # =====================================================

        patterns = self.detect_patterns(
            records,
            minimum_count=(
                minimum_pattern_count
            ),
        )

        signals = self.generate_signals(
            patterns
        )

        top = self.top_signals(
            signals
        )

        result = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,

            "records_analyzed": len(
                records
            ),

            "memory_records": len(
                memory
            ),

            "legacy_records": len(
                legacy_records
            ),

            "error_frequency": (
                self.error_frequency(
                    records
                )
            ),

            "cause_frequency": (
                self.cause_frequency(
                    records
                )
            ),

            "severity": (
                self.severity_statistics(
                    records
                )
            ),

            "xg": (
                self.xg_statistics(
                    records
                )
            ),

            "memory": (
                self.memory_statistics(
                    memory
                )
            ),

            "patterns": [
                pattern.to_dict()
                for pattern in patterns
            ],

            "signals": signals,

            "top_signals": top,
        }

        logger.info(
            "ETC learning analysis complete: "
            "records=%s memory=%s "
            "patterns=%s signals=%s",
            len(records),
            len(memory),
            len(patterns),
            len(signals),
        )

        return result


# ============================================================
# MODULE-LEVEL API
# ============================================================

def analyze_learning(
    db: Optional[FAJDatabase] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Удобная точка входа ETC.
    """

    analyzer = LearningAnalyzer(
        db=db
    )

    return analyzer.analyze(
        limit=limit
    )


def analyze_learning_memory(
    db: Optional[FAJDatabase] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    """
    Явный API анализа learning_memory.

    Используется ETC Controller,
    Streamlit ETC page и диагностикой.
    """

    analyzer = LearningAnalyzer(
        db=db
    )

    return analyzer.analyze(
        limit=limit,
        include_legacy_records=False,
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
    print("FAJ ETC — Learning Analyzer")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    sample_records = [

        {
            "match_id": 101,
            "error_type": "score_miss",
            "cause_type": (
                "home_attack_overestimated"
            ),
            "error_severity": 3,
            "error_xg": 0.80,
            "confidence": 0.85,
            "impact": 0.60,
            "recommendation": (
                "Проверить атакующий "
                "фактор хозяев."
            ),
        },

        {
            "match_id": 102,
            "error_type": "score_miss",
            "cause_type": (
                "home_attack_overestimated"
            ),
            "error_severity": 2,
            "error_xg": 0.60,
            "confidence": 0.80,
            "impact": 0.50,
            "recommendation": (
                "Проверить атакующий "
                "фактор хозяев."
            ),
        },

        {
            "match_id": 103,
            "error_type": "winner_miss",
            "cause_type": (
                "match_balance_misread"
            ),
            "error_severity": 4,
            "error_xg": 1.20,
            "confidence": 0.90,
            "impact": 0.80,
            "recommendation": (
                "Проверить баланс "
                "силы команд."
            ),
        },

    ]

    analyzer = LearningAnalyzer()

    result = analyzer.analyze(
        records=sample_records
    )

    print(
        f"Records: "
        f"{result['records_analyzed']}"
    )

    print(
        f"Patterns: "
        f"{len(result['patterns'])}"
    )

    print(
        f"Signals: "
        f"{len(result['signals'])}"
    )

    print(
        "Top signals:"
    )

    for signal in result["top_signals"]:

        print(
            f"  {signal['priority']} | "
            f"{signal['error_type']} | "
            f"{signal['cause_type']} | "
            f"strength="
            f"{signal['signal_strength']}"
        )

    print("=" * 70)
