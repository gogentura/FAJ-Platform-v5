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
Контейнер и builder данных для ETC.

ВАЖНО:

    learning_batch.py НЕ является оркестратором ETC.

    Главный оркестратор:
        etc_controller.py

    Управление batch:
        batch_controller.py

    learning_batch.py:
        только формирует безопасный контейнер
        данных для ETC и предоставляет методы
        проверки/статистики.

АРХИТЕКТУРА:

    MATCH RESULTS / GOLD / LEARNING RECORDS
                     │
                     ▼
             LearningBatchBuilder
                     │
                     ▼
              LearningBatch
                     │
                     ▼
             BatchController
                     │
                     ▼
                 ETC
                     │
                     ▼
             Learning Engine
                     │
                     ▼
             Learning Memory
                     │
                     ▼
                  SQLite

============================================================
ПРИНЦИПЫ
============================================================

МОДУЛЬ:

    - READ ONLY относительно SQLite;
    - не обучает модель;
    - не изменяет database.py;
    - не изменяет match_results;
    - не изменяет predictions;
    - не изменяет gold;
    - не изменяет learning_memory;
    - не изменяет FAJ Rating;
    - не изменяет model_parameters;
    - не удаляет данные;
    - не блокирует данные;
    - не помечает записи processed.

database.py остаётся единым источником схемы.

============================================================
РОЛЬ BATCH
============================================================

LearningBatch — временный объект одного запуска ETC.

Он содержит:

    match_ids
    gold_records
    learning_records
    source IDs
    metadata

Старые записи SQLite не являются частью batch навсегда.

Batch — это рабочий снимок данных для конкретного ETC-run.

============================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.1"
MODULE_NAME = "ETC Learning Batch"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


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


def _unique_ints(values: Iterable[Any]) -> List[int]:
    """
    Преобразует значения в уникальные int,
    сохраняя порядок.
    """

    result: List[int] = []
    seen = set()

    for value in values:

        number = _safe_int(value)

        if number is None:
            continue

        if number in seen:
            continue

        seen.add(number)
        result.append(number)

    return result


# ============================================================
# DATA STRUCTURE
# ============================================================

@dataclass
class LearningBatch:
    """
    Временный контейнер данных одного ETC-run.

    ВАЖНО:

        LearningBatch не пишет в БД.

        Это обычный in-memory объект.
    """

    batch_id: str
    created_at: str

    # --------------------------------------------------------
    # Основные источники
    # --------------------------------------------------------

    match_ids: List[int] = field(
        default_factory=list
    )

    gold_records: List[Dict[str, Any]] = field(
        default_factory=list
    )

    learning_records: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    source_gold_ids: List[int] = field(
        default_factory=list
    )

    source_learning_ids: List[int] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ========================================================
    # PROPERTIES
    # ========================================================

    @property
    def size(self) -> int:
        """
        Количество уникальных матчей batch.
        """

        return len(self.match_ids)

    @property
    def gold_size(self) -> int:
        return len(self.gold_records)

    @property
    def learning_size(self) -> int:
        return len(self.learning_records)

    @property
    def is_empty(self) -> bool:
        return (
            self.size == 0
            and self.gold_size == 0
            and self.learning_size == 0
        )

    @property
    def is_ready(self) -> bool:
        """
        Batch считается готовым,
        если в нём есть хотя бы один источник данных.
        """

        return not self.is_empty

    # ========================================================
    # MATCH IDS
    # ========================================================

    def get_match_ids(self) -> List[int]:
        """
        Возвращает уникальные match_id.
        """

        ids = list(self.match_ids)

        for record in self.gold_records:
            ids.append(
                record.get("match_id")
            )

        for record in self.learning_records:
            ids.append(
                record.get("match_id")
            )

        return _unique_ints(ids)

    # ========================================================
    # DICT
    # ========================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует batch в обычный dict.
        """

        match_ids = self.get_match_ids()

        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,

            "match_ids": match_ids,

            "gold_records": self.gold_records,
            "learning_records": self.learning_records,

            "source_gold_ids": self.source_gold_ids,
            "source_learning_ids": (
                self.source_learning_ids
            ),

            "metadata": self.metadata,

            "size": len(match_ids),
            "gold_size": self.gold_size,
            "learning_size": self.learning_size,

            "is_empty": self.is_empty,
            "is_ready": self.is_ready,
        }


# ============================================================
# BUILDER
# ============================================================

class LearningBatchBuilder:
    """
    Формирует временный LearningBatch.

    Только READ из SQLite.

    ВАЖНО:

        Builder не управляет жизненным циклом batch.

        За lifecycle отвечает BatchController.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # BATCH ID
    # ========================================================

    @staticmethod
    def _make_batch_id() -> str:
        """
        Уникальный ID текущего in-memory batch.
        """

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )

        return f"ETC-{timestamp}"

    # ========================================================
    # GOLD
    # ========================================================

    def get_pending_gold(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Получает доступные gold-записи.

        Использует только API database.py.

        Никаких прямых SQL-запросов здесь нет.
        """

        limit = max(1, int(limit))

        getter = getattr(
            self.db,
            "get_gold_pending",
            None,
        )

        if not callable(getter):

            logger.info(
                "FAJDatabase.get_gold_pending() "
                "не предоставлен — gold source пропущен."
            )

            return []

        try:

            rows = getter()

            records = [
                dict(row)
                for row in rows
            ]

            return records[:limit]

        except Exception as exc:

            logger.warning(
                "Unable to read pending gold: %s",
                exc,
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

        Только чтение.
        """

        limit = max(1, int(limit))

        getter = getattr(
            self.db,
            "get_learning_records",
            None,
        )

        if not callable(getter):

            logger.info(
                "FAJDatabase.get_learning_records() "
                "не предоставлен — learning source пропущен."
            )

            return []

        try:

            # Сначала пытаемся использовать status="new",
            # если текущий database.py поддерживает этот API.
            try:

                rows = getter(
                    status="new"
                )

            except TypeError:

                # Совместимость с API без status.
                rows = getter()

            records = [
                dict(row)
                for row in rows
            ]

            # Не ограничиваем источник SQL-запросом здесь.
            # Просто ограничиваем рабочий batch.
            return records[:limit]

        except Exception as exc:

            logger.warning(
                "Unable to read learning records: %s",
                exc,
            )

            return []

    # ========================================================
    # VALIDATE GOLD
    # ========================================================

    @staticmethod
    def validate_gold(
        record: Dict[str, Any],
    ) -> bool:
        """
        Минимальная проверка gold.

        Не требует изменения записи.
        """

        if not record:
            return False

        # Старые/заблокированные записи не берём
        # в новый рабочий batch.

        locked = record.get("locked")

        if locked in (
            1,
            True,
            "1",
            "true",
            "True",
        ):
            return False

        # Gold должен иметь идентификатор
        # или match_id для аудита.

        record_id = record.get("id")
        match_id = record.get("match_id")

        if (
            record_id is None
            and match_id is None
        ):
            return False

        # Факт счёта — минимальный признак
        # завершённого gold объекта.

        actual_score = record.get(
            "actual_score"
        )

        if actual_score is None:

            # Возможны схемы, где счёт хранится
            # отдельными полями.

            home_goals = record.get(
                "actual_home_goals"
            )

            away_goals = record.get(
                "actual_away_goals"
            )

            if (
                home_goals is None
                or away_goals is None
            ):
                return False

        return True

    # ========================================================
    # VALIDATE LEARNING RECORD
    # ========================================================

    @staticmethod
    def validate_learning_record(
        record: Dict[str, Any],
    ) -> bool:
        """
        Минимальная проверка learning_record.
        """

        if not record:
            return False

        match_id = _safe_int(
            record.get("match_id")
        )

        if match_id is None:
            return False

        # Для ETC запись должна содержать
        # хотя бы некоторый сигнал обучения.

        error_type = record.get(
            "error_type"
        )

        cause_type = record.get(
            "cause_type"
        )

        learning_type = record.get(
            "learning_type"
        )

        if not any(
            (
                error_type,
                cause_type,
                learning_type,
            )
        ):
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
        Создаёт новый временный LearningBatch.

        НИЧЕГО не записывает в SQLite.
        """

        gold_limit = max(
            1,
            int(gold_limit),
        )

        learning_limit = max(
            1,
            int(learning_limit),
        )

        batch_id = self._make_batch_id()
        created_at = _now()

        # ----------------------------------------------------
        # GOLD
        # ----------------------------------------------------

        raw_gold = self.get_pending_gold(
            limit=gold_limit
        )

        valid_gold = [
            record
            for record in raw_gold
            if self.validate_gold(record)
        ]

        # ----------------------------------------------------
        # LEARNING
        # ----------------------------------------------------

        raw_learning = (
            self.get_new_learning_records(
                limit=learning_limit
            )
        )

        valid_learning = [
            record
            for record in raw_learning
            if self.validate_learning_record(
                record
            )
        ]

        # ----------------------------------------------------
        # SOURCE IDS
        # ----------------------------------------------------

        gold_ids = _unique_ints(
            record.get("id")
            for record in valid_gold
        )

        learning_ids = _unique_ints(
            record.get("id")
            for record in valid_learning
        )

        # ----------------------------------------------------
        # MATCH IDS
        # ----------------------------------------------------

        match_ids: List[int] = []

        for record in valid_gold:
            match_ids.append(
                record.get("match_id")
            )

        for record in valid_learning:
            match_ids.append(
                record.get("match_id")
            )

        match_ids = _unique_ints(
            match_ids
        )

        # ----------------------------------------------------
        # METADATA
        # ----------------------------------------------------

        metadata = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,

            "gold_requested": len(raw_gold),
            "gold_valid": len(valid_gold),

            "learning_requested": (
                len(raw_learning)
            ),

            "learning_valid": (
                len(valid_learning)
            ),

            "matches": len(match_ids),

            "read_only": True,
        }

        # ----------------------------------------------------
        # OBJECT
        # ----------------------------------------------------

        batch = LearningBatch(
            batch_id=batch_id,
            created_at=created_at,

            match_ids=match_ids,

            gold_records=valid_gold,
            learning_records=valid_learning,

            source_gold_ids=gold_ids,
            source_learning_ids=learning_ids,

            metadata=metadata,
        )

        logger.info(
            "ETC LearningBatch built: "
            "id=%s matches=%s gold=%s learning=%s",
            batch.batch_id,
            len(match_ids),
            len(valid_gold),
            len(valid_learning),
        )

        return batch

    # ========================================================
    # READINESS
    # ========================================================

    def is_ready(
        self,
        gold_limit: int = 1,
        learning_limit: int = 1,
    ) -> bool:
        """
        Проверяет, есть ли данные для ETC.

        Готовность определяется не только gold.

        Это важно для новой архитектуры ETC,
        где learning_records являются отдельным
        источником аналитических сигналов.
        """

        gold = self.get_pending_gold(
            limit=max(1, int(gold_limit))
        )

        if any(
            self.validate_gold(record)
            for record in gold
        ):
            return True

        learning = (
            self.get_new_learning_records(
                limit=max(
                    1,
                    int(learning_limit),
                )
            )
        )

        if any(
            self.validate_learning_record(record)
            for record in learning
        ):
            return True

        return False

    # ========================================================
    # SUMMARY
    # ========================================================

    @staticmethod
    def summarize(
        batch: LearningBatch,
    ) -> Dict[str, Any]:
        """
        Краткая статистика batch.
        """

        match_ids = batch.get_match_ids()

        return {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,

            "matches": len(match_ids),
            "match_ids": match_ids,

            "gold_count": batch.gold_size,
            "learning_count": (
                batch.learning_size
            ),

            "gold_ids": (
                batch.source_gold_ids
            ),

            "learning_ids": (
                batch.source_learning_ids
            ),

            "is_empty": batch.is_empty,
            "ready": batch.is_ready,
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
    Публичная точка формирования batch.

    Только READ.
    """

    builder = LearningBatchBuilder(
        db=db
    )

    return builder.build(
        gold_limit=gold_limit,
        learning_limit=learning_limit,
    )


def is_learning_ready(
    db: Optional[FAJDatabase] = None,
) -> bool:
    """
    Проверяет наличие данных,
    готовых для ETC.
    """

    builder = LearningBatchBuilder(
        db=db
    )

    return builder.is_ready()


def summarize_learning_batch(
    batch: LearningBatch,
) -> Dict[str, Any]:
    """
    Публичный helper статистики batch.
    """

    return LearningBatchBuilder.summarize(
        batch
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
    print("FAJ Platform v12.1")
    print("ETC — Learning Batch")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        db = FAJDatabase()

        builder = LearningBatchBuilder(
            db=db
        )

        batch = builder.build(
            gold_limit=10,
            learning_limit=50,
        )

        summary = builder.summarize(
            batch
        )

        print(
            f"Batch ID: "
            f"{summary['batch_id']}"
        )

        print(
            f"Matches: "
            f"{summary['matches']}"
        )

        print(
            f"Gold records: "
            f"{summary['gold_count']}"
        )

        print(
            f"Learning records: "
            f"{summary['learning_count']}"
        )

        print(
            f"Ready: "
            f"{summary['ready']}"
        )

        print(
            f"Empty: "
            f"{summary['is_empty']}"
        )

    except Exception as exc:

        logger.error(
            "Learning batch self-test failed: %s",
            exc,
        )

    print("=" * 70)
