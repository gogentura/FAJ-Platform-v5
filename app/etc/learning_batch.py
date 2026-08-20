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
Формирование единого batch данных для ETC.

ЦЕПОЧКА:

    SQLite
       ↓
    gold_dataset
       ↓
    learning_records
       ↓
    LearningBatch
       ↓
    batch_controller.py
       ↓
    ETC

МОДУЛЬ НЕ:
    - не обучает модель;
    - не изменяет database.py;
    - не удаляет записи;
    - не изменяет gold_dataset;
    - не изменяет predictions;
    - не изменяет FAJ Rating;
    - не изменяет model_parameters.

МОДУЛЬ:
    - собирает готовые записи;
    - проверяет минимальную готовность;
    - формирует batch;
    - предоставляет статистику batch;
    - сохраняет исходные ID для аудита.

ПРИНЦИП:
    READ ONLY относительно SQLite.

============================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Learning Batch"


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class LearningBatch:
    """
    Единый контейнер одного batch ETC.
    """

    batch_id: str
    created_at: str

    gold_records: List[Dict[str, Any]] = field(default_factory=list)
    learning_records: List[Dict[str, Any]] = field(default_factory=list)

    source_gold_ids: List[int] = field(default_factory=list)
    source_learning_ids: List[int] = field(default_factory=list)

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.gold_records)

    @property
    def learning_size(self) -> int:
        return len(self.learning_records)

    @property
    def is_empty(self) -> bool:
        return self.size == 0 and self.learning_size == 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует batch в обычный dict.
        """

        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "gold_records": self.gold_records,
            "learning_records": self.learning_records,
            "source_gold_ids": self.source_gold_ids,
            "source_learning_ids": self.source_learning_ids,
            "metadata": self.metadata,
            "size": self.size,
            "learning_size": self.learning_size,
        }


# ============================================================
# MAIN CLASS
# ============================================================

class LearningBatchBuilder:
    """
    Формирует batch для ETC.

    Важное правило:
    builder только читает БД.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
        self.db = db or FAJDatabase()

    # ========================================================
    # BATCH ID
    # ========================================================

    @staticmethod
    def _make_batch_id() -> str:
        """
        Создаёт уникальный идентификатор batch.

        ID не хранится в БД на этом уровне.
        """

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")

        return f"ETC-{timestamp}"

    # ========================================================
    # GOLD DATA
    # ========================================================

    def get_pending_gold(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Получает незаблокированные gold-записи.

        Предпочтительно использует database.py API.
        """

        limit = max(1, int(limit))

        try:
            rows = self.db.get_gold_pending()

            records = [dict(row) for row in rows]

            return records[:limit]

        except AttributeError:
            logger.warning(
                "FAJDatabase.get_gold_pending() отсутствует"
            )
            return []

    # ========================================================
    # LEARNING RECORDS
    # ========================================================

    def get_new_learning_records(
        self,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Получает новые learning_records.

        Ничего не изменяет.
        """

        limit = max(1, int(limit))

        try:
            rows = self.db.get_learning_records(status="new")

            records = [dict(row) for row in rows]

            return records[:limit]

        except AttributeError:
            logger.warning(
                "FAJDatabase.get_learning_records() отсутствует"
            )
            return []

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_gold(record: Dict[str, Any]) -> bool:
        """
        Проверяет минимальную готовность gold-записи.
        """

        if not record:
            return False

        if record.get("locked") in (1, True):
            return False

        actual_score = record.get("actual_score")

        if actual_score is None:
            return False

        return True

    @staticmethod
    def _validate_learning_record(
        record: Dict[str, Any],
    ) -> bool:
        """
        Проверяет минимальную готовность learning_record.
        """

        if not record:
            return False

        if not record.get("match_id"):
            return False

        if not record.get("error_type"):
            return False

        return True

    # ========================================================
    # BUILD
    # ========================================================

    def build(
        self,
        gold_limit: int = 100,
        learning_limit: int = 500,
    ) -> LearningBatch:
        """
        Формирует новый batch ETC.

        Только чтение.
        """

        batch_id = self._make_batch_id()

        created_at = datetime.now().isoformat()

        gold = self.get_pending_gold(limit=gold_limit)

        learning = self.get_new_learning_records(
            limit=learning_limit
        )

        valid_gold = [
            record
            for record in gold
            if self._validate_gold(record)
        ]

        valid_learning = [
            record
            for record in learning
            if self._validate_learning_record(record)
        ]

        gold_ids = [
            int(record["id"])
            for record in valid_gold
            if record.get("id") is not None
        ]

        learning_ids = [
            int(record["id"])
            for record in valid_learning
            if record.get("id") is not None
        ]

        metadata = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,
            "gold_requested": len(gold),
            "gold_valid": len(valid_gold),
            "learning_requested": len(learning),
            "learning_valid": len(valid_learning),
        }

        batch = LearningBatch(
            batch_id=batch_id,
            created_at=created_at,
            gold_records=valid_gold,
            learning_records=valid_learning,
            source_gold_ids=gold_ids,
            source_learning_ids=learning_ids,
            metadata=metadata,
        )

        logger.info(
            "ETC batch built: id=%s gold=%s learning=%s",
            batch.batch_id,
            batch.size,
            batch.learning_size,
        )

        return batch

    # ========================================================
    # READINESS
    # ========================================================

    def is_ready(
        self,
        gold_limit: int = 1,
    ) -> bool:
        """
        Проверяет, есть ли хотя бы одна готовая gold-запись.
        """

        gold = self.get_pending_gold(limit=gold_limit)

        return any(
            self._validate_gold(record)
            for record in gold
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    @staticmethod
    def summarize(
        batch: LearningBatch,
    ) -> Dict[str, Any]:
        """
        Возвращает краткую статистику batch.
        """

        return {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,
            "gold_count": batch.size,
            "learning_count": batch.learning_size,
            "gold_ids": batch.source_gold_ids,
            "learning_ids": batch.source_learning_ids,
            "is_empty": batch.is_empty,
            "ready": not batch.is_empty,
        }


# ============================================================
# MODULE-LEVEL HELPERS
# ============================================================

def build_learning_batch(
    db: Optional[FAJDatabase] = None,
    gold_limit: int = 100,
    learning_limit: int = 500,
) -> LearningBatch:
    """
    Удобная функция для ETC.
    """

    builder = LearningBatchBuilder(db)

    return builder.build(
        gold_limit=gold_limit,
        learning_limit=learning_limit,
    )


def is_learning_ready(
    db: Optional[FAJDatabase] = None,
) -> bool:
    """
    Проверяет готовность данных для обучения.
    """

    builder = LearningBatchBuilder(db)

    return builder.is_ready()


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 70)
    print("FAJ ETC — Learning Batch")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:
        db = FAJDatabase()

        builder = LearningBatchBuilder(db)

        batch = builder.build(
            gold_limit=10,
            learning_limit=50,
        )

        print(f"Batch ID: {batch.batch_id}")
        print(f"Gold records: {batch.size}")
        print(f"Learning records: {batch.learning_size}")
        print(f"Empty: {batch.is_empty}")

    except Exception as exc:
        logger.error(
            "Learning batch self-test failed: %s",
            exc,
        )
