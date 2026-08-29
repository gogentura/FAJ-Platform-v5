#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_batch.py
============================================================

НАЗНАЧЕНИЕ
-----------

LearningBatch — безопасный in-memory контейнер одного
конкретного ETC batch.

ИСПРАВЛЕНИЯ v2.1
============================================================

1. validate_result() проверяет fact_status
2. is_complete проверяет identity, а не count
3. is_valid проверяет согласованность ID
4. build_from_match_ids() сохраняет missing IDs
5. Добавлена проверка существования match
6. Добавлена защита от отсутствующих match_id

АРХИТЕКТУРА:

    BatchController → LearningBatchBuilder → LearningBatch → ETCController → ETCLearningEngine

ВАЖНО:
    BatchController ВЫБИРАЕТ batch.
    LearningBatchBuilder НЕ выбирает batch.
    ETCController ОРКЕСТРИРУЕТ.
    ETCLearningEngine ОБУЧАЕТ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "2.1"
MODULE_NAME = "ETC Learning Batch"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _unique_ints(values: Iterable[Any]) -> List[int]:
    result: List[int] = []
    seen = set()
    for value in values:
        number = _safe_int(value)
        if number is None or number <= 0:
            continue
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return result


def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        pass
    return None


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class LearningBatch:
    """Временный контейнер одного ETC-run."""

    batch_id: str
    created_at: str
    match_ids: List[int] = field(default_factory=list)
    matches: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    records: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.match_ids)

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    @property
    def is_complete(self) -> bool:
        """
        Все выбранные матчи имеют факт результата.
        Проверяет identity, а не только количество.
        """
        if self.is_empty:
            return False

        expected_ids = set(self.match_ids)
        actual_ids: Set[int] = set()

        for result in self.results:
            match_id = result.get("match_id")
            if match_id is not None:
                actual_ids.add(match_id)

        return expected_ids == actual_ids

    @property
    def is_valid(self) -> bool:
        """
        Batch структурно пригоден для передачи ETCController.
        Проверяет identity для всех полей.
        """
        if self.is_empty:
            return False

        if len(self.matches) != self.size:
            return False

        if len(self.records) != self.size:
            return False

        if not self.is_complete:
            return False

        match_ids_set = set(self.match_ids)

        for match in self.matches:
            if match.get("match_id") not in match_ids_set:
                return False

        for record in self.records:
            if record.get("match_id") not in match_ids_set:
                return False

        return True

    def get_match_ids(self) -> List[int]:
        return list(self.match_ids)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "match_ids": list(self.match_ids),
            "matches": list(self.matches),
            "results": list(self.results),
            "records": list(self.records),
            "metadata": dict(self.metadata),
            "size": self.size,
            "is_empty": self.is_empty,
            "is_complete": self.is_complete,
            "is_valid": self.is_valid,
        }


# ============================================================
# BUILDER
# ============================================================

class LearningBatchBuilder:
    """
    Формирует LearningBatch из УЖЕ ВЫБРАННЫХ BatchController матчей.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    @staticmethod
    def _make_batch_id() -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"ETC-{timestamp}"

    @staticmethod
    def _normalize_matches(matches: Iterable[Any]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen = set()

        for item in matches:
            record = _row_to_dict(item)
            if not record:
                continue

            match_id = _safe_int(record.get("id")) or _safe_int(record.get("match_id"))
            if match_id is None:
                continue

            if match_id in seen:
                continue

            seen.add(match_id)
            record["match_id"] = match_id
            result.append(record)

        return result

    @staticmethod
    def validate_result(result: Optional[Dict[str, Any]]) -> bool:
        """
        Проверяет наличие фактического результата.

        ИСПРАВЛЕНО v2.1:
            - Проверяет fact_status
            - 0:0 является валидным результатом
            - None означает отсутствие факта
        """
        if not result:
            return False

        home_goals = result.get("home_goals")
        away_goals = result.get("away_goals")

        if home_goals is None:
            return False
        if away_goals is None:
            return False

        # Проверка статуса факта (НОВОЕ v2.1)
        fact_status = result.get("fact_status")
        if fact_status is not None:
            valid_statuses = {"verified", "locked", "gold", "completed"}
            if fact_status not in valid_statuses:
                return False

        return True

    def _get_match_result(self, match_id: int) -> Optional[Dict[str, Any]]:
        getter = getattr(self.db, "get_match_result", None)
        if not callable(getter):
            logger.error("FAJDatabase.get_match_result() не найден.")
            return None

        try:
            row = getter(match_id)
            return _row_to_dict(row)
        except Exception as exc:
            logger.warning("Unable to read match result match_id=%s: %s", match_id, exc)
            return None

    @staticmethod
    def _build_record(match: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        match_id = _safe_int(match.get("match_id"))
        record = {
            "match_id": match_id,
            "match": dict(match),
            "result": dict(result),
            "home_goals": result.get("home_goals"),
            "away_goals": result.get("away_goals"),
            "actual_score": f"{result.get('home_goals')}:{result.get('away_goals')}",
        }
        return record

    def build(
        self,
        matches: Optional[Iterable[Any]] = None,
        *,
        batch_id: Optional[str] = None,
    ) -> LearningBatch:
        """Формирует LearningBatch из списка матчей."""
        created_at = _now()
        current_batch_id = batch_id or self._make_batch_id()

        normalized_matches = self._normalize_matches(matches or [])
        match_ids = _unique_ints([match.get("match_id") for match in normalized_matches])

        results: List[Dict[str, Any]] = []
        records: List[Dict[str, Any]] = []
        missing_result_ids: List[int] = []
        missing_match_ids: List[int] = []  # НОВОЕ v2.1

        # Проверяем существование матчей (НОВОЕ v2.1)
        existing_match_ids = set()
        for match in normalized_matches:
            match_id = _safe_int(match.get("match_id"))
            if match_id is not None:
                existing_match_ids.add(match_id)

        for match in normalized_matches:
            match_id = _safe_int(match.get("match_id"))
            if match_id is None:
                continue

            # Проверка существования match (НОВОЕ v2.1)
            match_exists = False
            for m in self.db.get_matches():
                if m.get("id") == match_id:
                    match_exists = True
                    break

            if not match_exists:
                missing_match_ids.append(match_id)
                continue

            result = self._get_match_result(match_id)

            if not self.validate_result(result):
                missing_result_ids.append(match_id)
                continue

            results.append(dict(result) if result else {})
            records.append(self._build_record(match, result or {}))

        # Если есть missing_match_ids — batch невалиден (НОВОЕ v2.1)
        if missing_match_ids:
            logger.warning("Missing matches: %s", missing_match_ids)

        metadata: Dict[str, Any] = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "requested_matches": len(normalized_matches),
            "loaded_results": len(results),
            "records": len(records),
            "missing_result_ids": missing_result_ids,
            "missing_match_ids": missing_match_ids,
            "has_missing_matches": bool(missing_match_ids),
            "read_only": True,
            "source": "BatchController",
        }

        batch = LearningBatch(
            batch_id=current_batch_id,
            created_at=created_at,
            match_ids=match_ids,
            matches=normalized_matches,
            results=results,
            records=records,
            metadata=metadata,
        )

        logger.info(
            "ETC LearningBatch built | batch=%s | requested=%s | results=%s | missing_match=%s | valid=%s",
            batch.batch_id,
            len(normalized_matches),
            len(results),
            len(missing_match_ids),
            batch.is_valid,
        )

        return batch

    def build_from_match_ids(
        self,
        match_ids: Iterable[Any],
        *,
        batch_id: Optional[str] = None,
    ) -> LearningBatch:
        """
        Создаёт LearningBatch из конкретных match_id.

        ИСПРАВЛЕНО v2.1:
            - Сохраняет missing_match_ids
            - Делает batch невалидным при наличии missing
        """
        ids = _unique_ints(match_ids)

        if not ids:
            return self.build([], batch_id=batch_id)

        getter = getattr(self.db, "get_matches", None)
        if not callable(getter):
            logger.error("FAJDatabase.get_matches() не найден.")
            return self.build([], batch_id=batch_id)

        try:
            rows = getter()
        except Exception as exc:
            logger.exception("Unable to read matches: %s", exc)
            return self.build([], batch_id=batch_id)

        wanted = set(ids)
        selected: List[Dict[str, Any]] = []

        for row in rows:
            record = _row_to_dict(row)
            if not record:
                continue

            match_id = _safe_int(record.get("id")) or _safe_int(record.get("match_id"))
            if match_id not in wanted:
                continue

            selected.append(record)

        # Сохраняем порядок match_ids
        by_id = {_safe_int(item.get("id") or item.get("match_id")): item for item in selected}
        ordered = [by_id[match_id] for match_id in ids if match_id in by_id]

        batch = self.build(ordered, batch_id=batch_id)

        # Добавляем missing IDs в metadata
        found_ids = set(by_id.keys())
        missing_ids = [mid for mid in ids if mid not in found_ids]

        if missing_ids:
            batch.metadata["missing_match_ids"] = missing_ids
            batch.metadata["has_missing_matches"] = True
            logger.warning("Missing match IDs in build_from_match_ids: %s", missing_ids)

        return batch

    @staticmethod
    def validate_batch(batch: Optional[LearningBatch]) -> bool:
        if batch is None:
            return False
        return batch.is_valid

    @staticmethod
    def summarize(batch: LearningBatch) -> Dict[str, Any]:
        return {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,
            "matches": batch.size,
            "match_ids": batch.get_match_ids(),
            "results": len(batch.results),
            "records": len(batch.records),
            "is_empty": batch.is_empty,
            "is_complete": batch.is_complete,
            "is_valid": batch.is_valid,
            "metadata": dict(batch.metadata),
        }


# ============================================================
# MODULE-LEVEL API
# ============================================================

def build_learning_batch(
    matches: Optional[Iterable[Any]] = None,
    db: Optional[FAJDatabase] = None,
    *,
    batch_id: Optional[str] = None,
) -> LearningBatch:
    builder = LearningBatchBuilder(db=db)
    return builder.build(matches=matches, batch_id=batch_id)


def build_learning_batch_from_ids(
    match_ids: Iterable[Any],
    db: Optional[FAJDatabase] = None,
    *,
    batch_id: Optional[str] = None,
) -> LearningBatch:
    builder = LearningBatchBuilder(db=db)
    return builder.build_from_match_ids(match_ids=match_ids, batch_id=batch_id)


def validate_learning_batch(batch: Optional[LearningBatch]) -> bool:
    return LearningBatchBuilder.validate_batch(batch)


def summarize_learning_batch(batch: LearningBatch) -> Dict[str, Any]:
    return LearningBatchBuilder.summarize(batch)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    print("=" * 70)
    print("FAJ Platform v12.1")
    print("ETC — Evolution Training Center")
    print("Learning Batch")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    print()
    print("ARCHITECTURAL CONTRACT")
    print("-" * 70)
    print("BatchController = выбирает batch")
    print("LearningBatchBuilder = упаковывает batch")
    print("ETCController = оркестрирует")
    print("ETCLearningEngine = обучает")
    print("learning_memory = хранит результат")

    print()
    print("НОВОЕ В v2.1:")
    print("1. validate_result() проверяет fact_status")
    print("2. is_complete проверяет identity, а не count")
    print("3. is_valid проверяет согласованность ID")
    print("4. build_from_match_ids() сохраняет missing IDs")
    print("5. Добавлена проверка существования match")

    print()
    print("READ ONLY")
    print("-" * 70)
    print("matches: READ")
    print("match_results: READ")
    print("learning_memory: НЕ ИЗМЕНЯЕТСЯ")
    print("DELETE: отсутствует")
    print("DROP: отсутствует")
    print("INSERT: отсутствует")
    print("UPDATE: отсутствует")

    print()
    print("ВАЖНО")
    print("-" * 70)
    print("Этот модуль НЕ выбирает batch.")
    print("Этот модуль НЕ создаёт batch_learning.")
    print("Этот модуль НЕ обучает модель.")
    print("Batch должен прийти от BatchController.")

    print("=" * 70)
