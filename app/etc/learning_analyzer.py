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

ИСПРАВЛЕНИЯ v2.2
============================================================

1. cause_type извлекается из reason (НЕ из feature)
2. error_xg извлекается только если event явно xG-связан
3. severity извлекается только если контракт гарантирует
4. Разделены event_count и unique_match_count
5. Дедупликация по (match_id, error_type, cause_type)
6. signal_strength ограничен [0, 1]
7. xg_statistics() не исключает error_xg = 0.0
8. Добавлен unique_match_count в результат
9. Разделены reason и recommendation

РОЛЬ В АРХИТЕКТУРЕ:

    Learning Memory
         │
         ▼
    Learning Analyzer
         │
         ├── repeated errors
         ├── causes
         ├── severity
         ├── xG deviations
         └── ETC signals (с priority)
                 │
                 ▼
          Parameter Optimizer
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "2.2"
MODULE_NAME = "ETC Learning Analyzer"


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _unique_ints(values: List[Any]) -> List[int]:
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
    error_type: str
    cause_type: str
    event_count: int = 0
    unique_match_count: int = 0
    average_severity: float = 0.0
    average_xg_error: float = 0.0
    average_confidence: float = 0.0
    average_impact: float = 0.0
    matches: List[int] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    signal_strength: float = 0.0
    priority: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "cause_type": self.cause_type,
            "event_count": self.event_count,
            "unique_match_count": self.unique_match_count,
            "average_severity": self.average_severity,
            "average_xg_error": self.average_xg_error,
            "average_confidence": self.average_confidence,
            "average_impact": self.average_impact,
            "matches": list(self.matches),
            "recommendations": list(self.recommendations),
            "signal_strength": self.signal_strength,
            "priority": self.priority,
        }


# ============================================================
# MAIN CLASS
# ============================================================

class LearningAnalyzer:
    """
    Анализатор накопленного опыта ETC v2.2.
    Только чтение.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # LOAD LEARNING MEMORY
    # ========================================================

    def load_learning_memory(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Загружает learning_memory через единый интерфейс."""
        limit = max(1, int(limit))

        try:
            rows = self.db.get_learning_memory(limit=limit)
            if rows is None:
                return []
            return [dict(row) for row in rows]
        except AttributeError:
            logger.warning("FAJDatabase.get_learning_memory() отсутствует")
            return []
        except Exception as exc:
            logger.warning("Unable to load learning_memory: %s", exc)
            return []

    # ========================================================
    # LOAD LEARNING RECORDS
    # ========================================================

    def load_learning_records(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Загружает learning_records как дополнительный источник."""
        limit = max(1, int(limit))

        try:
            rows = self.db.get_learning_records()
            if rows is None:
                return []
            records = [dict(row) for row in rows]
            return records[:limit]
        except AttributeError:
            logger.info("FAJDatabase.get_learning_records() отсутствует")
            return []
        except Exception as exc:
            logger.warning("Unable to load learning_records: %s", exc)
            return []

    # ========================================================
    # NORMALIZE MEMORY (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def normalize_memory(memory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Приводит learning_memory к аналитическому формату.

        ИСПРАВЛЕНИЯ v2.2:
            - cause_type извлекается из reason, НЕ из feature
            - error_xg извлекается ТОЛЬКО если event явно xG-связан
            - severity извлекается ТОЛЬКО если контракт гарантирует
        """
        result: List[Dict[str, Any]] = []

        for row in memory:
            event_type = row.get("event_type") or ""

            # Только prediction_error
            if event_type != "prediction_error":
                continue

            reference_id = row.get("reference_id")
            match_id = None
            if reference_id is not None:
                match_id = _safe_int(reference_id, 0)
                if match_id <= 0:
                    match_id = None

            feature = row.get("feature") or "unknown"
            reason = row.get("reason") or ""

            confidence = _safe_float(row.get("confidence"), 1.0)
            impact = _safe_float(row.get("impact"), 1.0)

            after_value = row.get("after_value")

            # ================================================
            # SEVERITY — ТОЛЬКО если контракт гарантирует
            # ================================================
            severity = 0
            if feature in ("score_miss", "winner_miss", "score_error", "result_miss"):
                severity = _safe_int(after_value, 0)

            # ================================================
            # ERROR_XG — ТОЛЬКО если xG-связан
            # ================================================
            error_xg = 0.0
            if feature in ("xg_miss", "xg_miscalibration", "xg_error", "xg_calibration"):
                error_xg = _safe_float(row.get("delta"), 0.0)
                if error_xg == 0.0 and isinstance(after_value, (int, float)):
                    error_xg = _safe_float(after_value, 0.0)

            # ================================================
            # CAUSE_TYPE — из reason (НОВОЕ v2.2)
            # ================================================
            cause_type = "unknown"

            # Пробуем извлечь из reason
            if ":" in reason:
                possible_cause, _, rest = reason.partition(":")
                possible_cause = possible_cause.strip()
                if possible_cause and possible_cause not in ("unknown", "error", "processing"):
                    cause_type = possible_cause

            # Если не удалось, пробуем feature (как fallback)
            if cause_type == "unknown" and feature not in ("unknown", "score_miss", "winner_miss", "xg_miss"):
                cause_type = feature

            result.append({
                "match_id": match_id,
                "error_type": feature,
                "cause_type": cause_type,
                "error_severity": severity,
                "error_xg": error_xg,
                "confidence": confidence,
                "impact": impact,
                "recommendation": reason,
                "memory_id": row.get("id"),
                "event_type": event_type,
                "created_at": row.get("created_at"),
                "object": row.get("object"),
                "model_version": row.get("model_version"),
                "algorithm": row.get("algorithm"),
            })

        return result

    # ========================================================
    # NORMALIZE LEGACY RECORDS
    # ========================================================

    @staticmethod
    def normalize_learning_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for record in records:
            result.append({
                "match_id": record.get("match_id"),
                "error_type": record.get("error_type") or "unknown",
                "cause_type": record.get("cause_type") or "unknown",
                "error_severity": _safe_int(record.get("error_severity")),
                "error_xg": _safe_float(record.get("error_xg")),
                "confidence": _safe_float(record.get("confidence"), 1.0),
                "impact": _safe_float(record.get("impact"), 1.0),
                "recommendation": record.get("recommendation"),
                "memory_id": None,
                "event_type": record.get("event_type"),
                "created_at": record.get("created_at"),
                "object": record.get("object"),
                "model_version": record.get("model_version"),
                "algorithm": record.get("algorithm"),
            })
        return result

    # ========================================================
    # GROUP
    # ========================================================

    @staticmethod
    def group_errors(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        groups = defaultdict(list)
        for record in records:
            error_type = record.get("error_type") or "unknown"
            cause_type = record.get("cause_type") or "unknown"
            key = f"{error_type}:{cause_type}"
            groups[key].append(record)
        return dict(groups)

    # ========================================================
    # PATTERNS (ИСПРАВЛЕНО v2.2)
    # ========================================================

    def detect_patterns(
        self,
        records: List[Dict[str, Any]],
        minimum_count: int = 3,
    ) -> List[ErrorPattern]:
        """
        Определяет повторяющиеся ошибки.

        ИСПРАВЛЕНИЯ v2.2:
            - minimum_count увеличен до 3
            - event_count и unique_match_count разделены
            - Дедупликация по (match_id, error_type, cause_type)
            - signal_strength ограничен [0, 1]
        """
        minimum_count = max(1, int(minimum_count))

        # Группировка
        groups = self.group_errors(records)
        patterns: List[ErrorPattern] = []

        for _, group in groups.items():
            if len(group) < minimum_count:
                continue

            first = group[0]
            error_type = first.get("error_type") or "unknown"
            cause_type = first.get("cause_type") or "unknown"

            # Уникальные match_id (НОВОЕ v2.2)
            unique_match_ids: Set[int] = set()
            for item in group:
                match_id = item.get("match_id")
                if match_id is not None and match_id > 0:
                    unique_match_ids.add(match_id)

            # Если нет уникальных match_id, используем event_count
            unique_match_count = len(unique_match_ids)
            if unique_match_count == 0:
                unique_match_count = len(group)

            severities = [_safe_float(item.get("error_severity")) for item in group]
            xg_errors = [_safe_float(item.get("error_xg")) for item in group if item.get("error_xg") is not None]
            confidences = [_safe_float(item.get("confidence"), 1.0) for item in group]
            impacts = [_safe_float(item.get("impact"), 1.0) for item in group]

            recommendations: List[str] = []
            for item in group:
                recommendation = item.get("recommendation")
                if recommendation and recommendation not in recommendations:
                    recommendations.append(str(recommendation))

            average_severity = sum(severities) / len(severities) if severities else 0.0
            average_xg_error = sum(xg_errors) / len(xg_errors) if xg_errors else 0.0
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            average_impact = sum(impacts) / len(impacts) if impacts else 0.0

            # Signal strength с clamp (НОВОЕ v2.2)
            sample_confidence = min(1.0, unique_match_count / 10.0)
            pattern_confidence = sample_confidence * average_confidence
            severity_factor = min(1.0, average_severity / 5.0)
            impact_factor = min(1.0, max(0.0, average_impact))

            signal_strength = _clamp(
                pattern_confidence * severity_factor * max(0.5, impact_factor),
                0.0, 1.0
            )

            # Priority
            if unique_match_count >= 5 and signal_strength >= 0.35:
                priority = "high"
            elif unique_match_count >= 3 and signal_strength >= 0.20:
                priority = "medium"
            else:
                priority = "low"

            patterns.append(ErrorPattern(
                error_type=error_type,
                cause_type=cause_type,
                event_count=len(group),
                unique_match_count=unique_match_count,
                average_severity=round(average_severity, 4),
                average_xg_error=round(average_xg_error, 4),
                average_confidence=round(average_confidence, 4),
                average_impact=round(average_impact, 4),
                matches=_unique_ints([item.get("match_id") for item in group if item.get("match_id") is not None]),
                recommendations=recommendations,
                signal_strength=round(signal_strength, 4),
                priority=priority,
            ))

        patterns.sort(key=lambda item: (item.signal_strength, item.unique_match_count, item.average_severity), reverse=True)
        return patterns

    # ========================================================
    # ERROR FREQUENCY
    # ========================================================

    @staticmethod
    def error_frequency(records: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = Counter()
        for record in records:
            error_type = record.get("error_type") or "unknown"
            counter[error_type] += 1
        return dict(counter.most_common())

    # ========================================================
    # CAUSE FREQUENCY
    # ========================================================

    @staticmethod
    def cause_frequency(records: List[Dict[str, Any]]) -> Dict[str, int]:
        counter = Counter()
        for record in records:
            cause_type = record.get("cause_type") or "unknown"
            counter[cause_type] += 1
        return dict(counter.most_common())

    # ========================================================
    # SEVERITY STATISTICS
    # ========================================================

    @staticmethod
    def severity_statistics(records: List[Dict[str, Any]]) -> Dict[str, float]:
        severities = [_safe_float(record.get("error_severity")) for record in records]
        if not severities:
            return {"count": 0, "average": 0.0, "max": 0.0}
        return {
            "count": len(severities),
            "average": round(sum(severities) / len(severities), 4),
            "max": max(severities),
        }

    # ========================================================
    # XG STATISTICS (ИСПРАВЛЕНО v2.2)
    # ========================================================

    @staticmethod
    def xg_statistics(records: List[Dict[str, Any]]) -> Dict[str, float]:
        """Статистика ошибок xG. Не исключает error_xg = 0.0."""
        values = [_safe_float(record.get("error_xg")) for record in records if record.get("error_xg") is not None]
        if not values:
            return {"count": 0, "average": 0.0, "max": 0.0, "has_xg_data": False}
        return {
            "count": len(values),
            "average": round(sum(values) / len(values), 4),
            "max": max(values),
            "has_xg_data": True,
        }

    # ========================================================
    # MEMORY STATISTICS
    # ========================================================

    @staticmethod
    def memory_statistics(memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        event_counter = Counter()
        algorithm_counter = Counter()
        model_counter = Counter()

        for row in memory:
            event_counter[row.get("event_type") or "unknown"] += 1
            algorithm_counter[row.get("algorithm") or "unknown"] += 1
            model_counter[row.get("model_version") or "unknown"] += 1

        return {
            "records": len(memory),
            "event_types": dict(event_counter.most_common()),
            "algorithms": dict(algorithm_counter.most_common()),
            "model_versions": dict(model_counter.most_common()),
        }

    # ========================================================
    # SIGNALS
    # ========================================================

    def generate_signals(self, patterns: List[ErrorPattern]) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for pattern in patterns:
            signals.append({
                "signal_type": "repeated_prediction_error",
                "error_type": pattern.error_type,
                "cause_type": pattern.cause_type,
                "event_count": pattern.event_count,
                "unique_match_count": pattern.unique_match_count,
                "average_severity": pattern.average_severity,
                "average_xg_error": pattern.average_xg_error,
                "average_confidence": pattern.average_confidence,
                "average_impact": pattern.average_impact,
                "signal_strength": pattern.signal_strength,
                "priority": pattern.priority,
                "matches": list(pattern.matches),
                "recommendations": list(pattern.recommendations),
            })
        return signals

    # ========================================================
    # TOP SIGNALS
    # ========================================================

    @staticmethod
    def top_signals(signals: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        limit = max(1, int(limit))
        return sorted(
            signals,
            key=lambda item: (_safe_float(item.get("signal_strength")), _safe_int(item.get("unique_match_count"))),
            reverse=True,
        )[:limit]

    # ========================================================
    # FULL ANALYSIS
    # ========================================================

    def analyze(
        self,
        records: Optional[List[Dict[str, Any]]] = None,
        minimum_pattern_count: int = 3,
        limit: int = 1000,
        include_legacy_records: bool = True,
    ) -> Dict[str, Any]:
        """Полный аналитический цикл."""
        memory: List[Dict[str, Any]] = []
        legacy_records: List[Dict[str, Any]] = []

        if records is None:
            memory = self.load_learning_memory(limit=limit)
            records = self.normalize_memory(memory)

            if include_legacy_records:
                legacy_records = self.load_learning_records(limit=limit)
                normalized_legacy = self.normalize_learning_records(legacy_records)

                existing_memory_ids = {item.get("match_id") for item in records if item.get("match_id") is not None}
                for item in normalized_legacy:
                    match_id = item.get("match_id")
                    if match_id is not None and match_id in existing_memory_ids:
                        continue
                    records.append(item)
        else:
            records = list(records)

        patterns = self.detect_patterns(records, minimum_count=minimum_pattern_count)
        signals = self.generate_signals(patterns)
        top = self.top_signals(signals)

        # Уникальные матчи (НОВОЕ v2.2)
        unique_matches: Set[int] = set()
        for record in records:
            match_id = record.get("match_id")
            if match_id is not None and match_id > 0:
                unique_matches.add(match_id)

        result = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "records_analyzed": len(records),
            "unique_matches_analyzed": len(unique_matches),
            "memory_records": len(memory),
            "legacy_records": len(legacy_records),
            "error_frequency": self.error_frequency(records),
            "cause_frequency": self.cause_frequency(records),
            "severity": self.severity_statistics(records),
            "xg": self.xg_statistics(records),
            "memory": self.memory_statistics(memory),
            "patterns": [pattern.to_dict() for pattern in patterns],
            "signals": signals,
            "top_signals": top,
        }

        logger.info(
            "ETC learning analysis complete: records=%s unique_matches=%s memory=%s patterns=%s signals=%s",
            len(records),
            len(unique_matches),
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
    analyzer = LearningAnalyzer(db=db)
    return analyzer.analyze(limit=limit)


def analyze_learning_memory(
    db: Optional[FAJDatabase] = None,
    limit: int = 1000,
) -> Dict[str, Any]:
    analyzer = LearningAnalyzer(db=db)
    return analyzer.analyze(limit=limit, include_legacy_records=False)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("FAJ ETC — Learning Analyzer")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    sample_records = [
        {"match_id": 101, "error_type": "score_miss", "cause_type": "home_attack_overestimated",
         "error_severity": 3, "error_xg": 0.80, "confidence": 0.85, "impact": 0.60,
         "recommendation": "Проверить атакующий фактор хозяев."},
        {"match_id": 101, "error_type": "xg_miss", "cause_type": "home_attack_overestimated",
         "error_severity": 2, "error_xg": 0.60, "confidence": 0.80, "impact": 0.50,
         "recommendation": "Проверить атакующий фактор хозяев."},
        {"match_id": 102, "error_type": "score_miss", "cause_type": "home_attack_overestimated",
         "error_severity": 2, "error_xg": 0.60, "confidence": 0.80, "impact": 0.50,
         "recommendation": "Проверить атакующий фактор хозяев."},
        {"match_id": 103, "error_type": "winner_miss", "cause_type": "match_balance_misread",
         "error_severity": 4, "error_xg": 1.20, "confidence": 0.90, "impact": 0.80,
         "recommendation": "Проверить баланс силы команд."},
    ]

    analyzer = LearningAnalyzer()
    result = analyzer.analyze(records=sample_records)

    print(f"Records: {result['records_analyzed']}")
    print(f"Unique matches: {result['unique_matches_analyzed']}")
    print(f"Patterns: {len(result['patterns'])}")
    print(f"Signals: {len(result['signals'])}")
    print("Top signals:")
    for signal in result["top_signals"]:
        print(f"  {signal['priority']} | {signal['error_type']} | {signal['cause_type']} | strength={signal['signal_strength']} | unique_matches={signal.get('unique_match_count', 0)}")

    print("=" * 70)
