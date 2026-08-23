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

ВАЖНО:

    BatchController ВЫБИРАЕТ batch.

    LearningBatchBuilder НЕ выбирает batch.

    ETCController ОРКЕСТРИРУЕТ.

    ETCLearningEngine ОБУЧАЕТ.

АРХИТЕКТУРА:

    match_results
          │
          ▼
    BatchController
          │
          │ selected matches
          ▼
    LearningBatchBuilder
          │
          ▼
    LearningBatch
          │
          ▼
    ETCController
          │
          ▼
    ETCLearningEngine
          │
          ▼
    learning_memory

============================================================
ОТВЕТСТВЕННОСТЬ
============================================================

Этот модуль:

    - принимает уже выбранные BatchController матчи;
    - читает необходимые факты из SQLite;
    - формирует временный LearningBatch;
    - выполняет структурную валидацию;
    - предоставляет статистику;
    - не обучает модель.

Этот модуль НЕ:

    - выбирает batch;
    - определяет размер batch;
    - проверяет processed marker;
    - создаёт batch_learning;
    - пишет learning_memory;
    - изменяет match_results;
    - изменяет matches;
    - изменяет predictions;
    - изменяет model_parameters;
    - изменяет FAJ Rating;
    - удаляет данные;
    - создаёт собственную схему БД.

database.py остаётся единым источником схемы.

============================================================
ГЛАВНОЕ ПРАВИЛО
============================================================

BatchController:

    "ВОТ ЭТИ МАТЧИ ДОЛЖНЫ ОБРАБАТЫВАТЬСЯ."

LearningBatchBuilder:

    "ПРИНЯЛ. УПАКОВАЛ ИХ В РАБОЧИЙ КОНТЕЙНЕР."

ETCController:

    "ПЕРЕДАЮ КОНТЕЙНЕР В ENGINE."

ETCLearningEngine:

    "ОБРАБАТЫВАЮ И ФИКСИРУЮ УСПЕШНЫЙ РЕЗУЛЬТАТ."

============================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "2.0"
MODULE_NAME = "ETC Learning Batch"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """Текущее время создания in-memory batch."""
    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:
    """Безопасное преобразование значения в int."""

    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def _unique_ints(
    values: Iterable[Any],
) -> List[int]:
    """
    Уникальные положительные int
    с сохранением исходного порядка.
    """

    result: List[int] = []
    seen = set()

    for value in values:

        number = _safe_int(value)

        if number is None:
            continue

        if number <= 0:
            continue

        if number in seen:
            continue

        seen.add(number)
        result.append(number)

    return result


def _row_to_dict(
    row: Any,
) -> Optional[Dict[str, Any]]:
    """
    Унифицированное преобразование строки БД
    в обычный dict.

    Поддерживает:

        dict
        sqlite3.Row
        mapping-like object
    """

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
    """
    Временный контейнер одного ETC-run.

    ВАЖНО:

        LearningBatch ничего не записывает в SQLite.

    BatchController уже определил,
    какие матчи входят в batch.

    Здесь они только представлены
    в безопасном рабочем формате.
    """

    batch_id: str
    created_at: str

    # --------------------------------------------------------
    # Идентификаторы выбранных матчей
    # --------------------------------------------------------

    match_ids: List[int] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Полные строки matches
    # --------------------------------------------------------

    matches: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Фактические результаты
    # --------------------------------------------------------

    results: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Объединённые записи:
    #
    # match + result
    # --------------------------------------------------------

    records: List[Dict[str, Any]] = field(
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
        """Количество матчей в batch."""
        return len(
            self.match_ids
        )

    @property
    def is_empty(self) -> bool:
        """Пуст ли batch."""
        return self.size == 0

    @property
    def is_complete(self) -> bool:
        """
        Все выбранные матчи имеют факт результата.

        Это НЕ решение READY/WAIT.

        Это только структурная проверка
        уже выбранного batch.
        """

        if self.is_empty:
            return False

        return (
            len(self.results)
            == len(self.match_ids)
        )

    @property
    def is_valid(self) -> bool:
        """
        Batch структурно пригоден
        для передачи ETCController.
        """

        if self.is_empty:
            return False

        if len(self.matches) != self.size:
            return False

        if len(self.records) != self.size:
            return False

        if not self.is_complete:
            return False

        return True

    # ========================================================
    # MATCH IDS
    # ========================================================

    def get_match_ids(self) -> List[int]:
        """Возвращает уникальные match_id."""

        return list(
            self.match_ids
        )

    # ========================================================
    # DICT
    # ========================================================

    def to_dict(self) -> Dict[str, Any]:
        """Безопасное представление batch в виде dict."""

        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,

            "match_ids": list(
                self.match_ids
            ),

            "matches": list(
                self.matches
            ),

            "results": list(
                self.results
            ),

            "records": list(
                self.records
            ),

            "metadata": dict(
                self.metadata
            ),

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
    Формирует LearningBatch из УЖЕ ВЫБРАННЫХ
    BatchController матчей.

    Builder НЕ выбирает batch.

    Builder НЕ знает правил:

        РПЛ = 5
        АПЛ = 3
        ЛЧ = 2

    Эти правила принадлежат BatchController.
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
        Уникальный ID in-memory batch.
        """

        timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S%f"
        )

        return f"ETC-{timestamp}"

    # ========================================================
    # NORMALIZE MATCHES
    # ========================================================

    @staticmethod
    def _normalize_matches(
        matches: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Преобразует переданные BatchController
        match objects в обычные dict.

        Никакого поиска дополнительных матчей.
        """

        result: List[
            Dict[str, Any]
        ] = []

        seen = set()

        for item in matches:

            record = _row_to_dict(
                item
            )

            if not record:
                continue

            match_id = _safe_int(
                record.get("id")
            )

            if match_id is None:
                match_id = _safe_int(
                    record.get("match_id")
                )

            if match_id is None:
                continue

            if match_id in seen:
                continue

            seen.add(match_id)

            # Нормализуем canonical match_id.
            record["match_id"] = match_id

            result.append(
                record
            )

        return result

    # ========================================================
    # READ RESULT
    # ========================================================

    def _get_match_result(
        self,
        match_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Читает фактический результат конкретного матча.

        Только READ.

        Источник:

            FAJDatabase.get_match_result()
        """

        getter = getattr(
            self.db,
            "get_match_result",
            None,
        )

        if not callable(getter):

            logger.error(
                "FAJDatabase.get_match_result() "
                "не найден."
            )

            return None

        try:

            row = getter(
                match_id
            )

            return _row_to_dict(
                row
            )

        except Exception as exc:

            logger.warning(
                "Unable to read match result "
                "match_id=%s: %s",
                match_id,
                exc,
            )

            return None

    # ========================================================
    # VALIDATE RESULT
    # ========================================================

    @staticmethod
    def validate_result(
        result: Optional[Dict[str, Any]],
    ) -> bool:
        """
        Проверяет наличие фактического результата.

        0:0 является валидным результатом.

        None означает отсутствие факта.
        """

        if not result:
            return False

        home_goals = result.get(
            "home_goals"
        )

        away_goals = result.get(
            "away_goals"
        )

        if home_goals is None:
            return False

        if away_goals is None:
            return False

        return True

    # ========================================================
    # BUILD RECORD
    # ========================================================

    @staticmethod
    def _build_record(
        match: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Создаёт единый рабочий record:

            match
            +
            result
        """

        match_id = _safe_int(
            match.get("match_id")
        )

        record: Dict[str, Any] = {
            "match_id": match_id,
            "match": dict(match),
            "result": dict(result),
        }

        # ----------------------------------------------------
        # Удобные canonical поля.
        # ----------------------------------------------------

        record["home_goals"] = result.get(
            "home_goals"
        )

        record["away_goals"] = result.get(
            "away_goals"
        )

        record["actual_score"] = (
            f"{result.get('home_goals')}:"
            f"{result.get('away_goals')}"
        )

        return record

    # ========================================================
    # BUILD
    # ========================================================

    def build(
        self,
        matches: Optional[
            Iterable[Any]
        ] = None,
        *,
        batch_id: Optional[str] = None,
    ) -> LearningBatch:
        """
        Формирует LearningBatch из конкретного
        списка матчей.

        ВАЖНО:

        matches должен прийти от BatchController.

        Если matches не передан,
        создаётся пустой batch.

        Builder НЕ вызывает:

            BatchController.create_batch()
            BatchController.check()
            get_pending_count()

        Он не выбирает матчи самостоятельно.
        """

        created_at = _now()

        if batch_id:
            current_batch_id = str(
                batch_id
            )
        else:
            current_batch_id = (
                self._make_batch_id()
            )

        normalized_matches = (
            self._normalize_matches(
                matches or []
            )
        )

        match_ids = [
            _safe_int(
                match.get("match_id")
            )
            for match in normalized_matches
        ]

        match_ids = _unique_ints(
            match_ids
        )

        results: List[
            Dict[str, Any]
        ] = []

        records: List[
            Dict[str, Any]
        ] = []

        missing_result_ids: List[int] = []

        # ----------------------------------------------------
        # READ FACTS
        # ----------------------------------------------------

        for match in normalized_matches:

            match_id = _safe_int(
                match.get("match_id")
            )

            if match_id is None:
                continue

            result = self._get_match_result(
                match_id
            )

            if not self.validate_result(
                result
            ):

                missing_result_ids.append(
                    match_id
                )

                continue

            # result точно Dict после validation
            assert result is not None

            results.append(
                dict(result)
            )

            records.append(
                self._build_record(
                    match,
                    result,
                )
            )

        # ----------------------------------------------------
        # METADATA
        # ----------------------------------------------------

        metadata: Dict[str, Any] = {
            "module": MODULE_NAME,
            "module_version": MODULE_VERSION,

            "requested_matches": len(
                normalized_matches
            ),

            "loaded_results": len(
                results
            ),

            "records": len(
                records
            ),

            "missing_result_ids": (
                missing_result_ids
            ),

            "read_only": True,

            "source": (
                "BatchController"
            ),
        }

        # ----------------------------------------------------
        # OBJECT
        # ----------------------------------------------------

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
            "ETC LearningBatch built | "
            "batch=%s | requested=%s | "
            "results=%s | valid=%s",
            batch.batch_id,
            len(normalized_matches),
            len(results),
            batch.is_valid,
        )

        return batch

    # ========================================================
    # BUILD FROM IDS
    # ========================================================

    def build_from_match_ids(
        self,
        match_ids: Iterable[Any],
        *,
        batch_id: Optional[str] = None,
    ) -> LearningBatch:
        """
        Совместимый способ построения batch,
        если ETCController передаёт только IDs.

        ВАЖНО:

        Этот метод НЕ выбирает batch.

        Он только загружает конкретные match_id,
        которые уже были выбраны выше по цепочке.
        """

        ids = _unique_ints(
            match_ids
        )

        if not ids:
            return self.build(
                [],
                batch_id=batch_id,
            )

        getter = getattr(
            self.db,
            "get_matches",
            None,
        )

        if not callable(getter):

            logger.error(
                "FAJDatabase.get_matches() "
                "не найден."
            )

            return self.build(
                [],
                batch_id=batch_id,
            )

        try:

            rows = getter()

        except Exception as exc:

            logger.exception(
                "Unable to read matches: %s",
                exc,
            )

            return self.build(
                [],
                batch_id=batch_id,
            )

        wanted = set(ids)

        selected: List[
            Dict[str, Any]
        ] = []

        for row in rows:

            record = _row_to_dict(
                row
            )

            if not record:
                continue

            match_id = _safe_int(
                record.get("id")
            )

            if match_id is None:
                match_id = _safe_int(
                    record.get("match_id")
                )

            if match_id not in wanted:
                continue

            selected.append(
                record
            )

        # ----------------------------------------------------
        # Сохраняем порядок match_ids,
        # заданный BatchController.
        # ----------------------------------------------------

        by_id = {
            _safe_int(
                item.get("id")
                or item.get("match_id")
            ): item
            for item in selected
        }

        ordered = [
            by_id[match_id]
            for match_id in ids
            if match_id in by_id
        ]

        return self.build(
            ordered,
            batch_id=batch_id,
        )

    # ========================================================
    # VALIDATE BATCH
    # ========================================================

    @staticmethod
    def validate_batch(
        batch: Optional[LearningBatch],
    ) -> bool:
        """
        Структурная проверка LearningBatch.

        Это НЕ проверка ETC readiness.

        READY/WAIT принадлежит BatchController.
        """

        if batch is None:
            return False

        return batch.is_valid

    # ========================================================
    # SUMMARY
    # ========================================================

    @staticmethod
    def summarize(
        batch: LearningBatch,
    ) -> Dict[str, Any]:
        """
        Диагностическая статистика batch.
        """

        return {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,

            "matches": batch.size,
            "match_ids": batch.get_match_ids(),

            "results": len(
                batch.results
            ),

            "records": len(
                batch.records
            ),

            "is_empty": batch.is_empty,
            "is_complete": batch.is_complete,
            "is_valid": batch.is_valid,

            "metadata": dict(
                batch.metadata
            ),
        }


# ============================================================
# MODULE-LEVEL API
# ============================================================

def build_learning_batch(
    matches: Optional[
        Iterable[Any]
    ] = None,
    db: Optional[FAJDatabase] = None,
    *,
    batch_id: Optional[str] = None,
) -> LearningBatch:
    """
    Публичная точка создания LearningBatch.

    В нормальной ETC-цепи:

        matches = результат BatchController.
    """

    builder = LearningBatchBuilder(
        db=db
    )

    return builder.build(
        matches=matches,
        batch_id=batch_id,
    )


def build_learning_batch_from_ids(
    match_ids: Iterable[Any],
    db: Optional[FAJDatabase] = None,
    *,
    batch_id: Optional[str] = None,
) -> LearningBatch:
    """
    Создаёт LearningBatch из конкретных match_id.

    IDs должны быть получены выше по цепочке.
    """

    builder = LearningBatchBuilder(
        db=db
    )

    return builder.build_from_match_ids(
        match_ids=match_ids,
        batch_id=batch_id,
    )


def validate_learning_batch(
    batch: Optional[LearningBatch],
) -> bool:
    """
    Проверяет структурную целостность batch.
    """

    return LearningBatchBuilder.validate_batch(
        batch
    )


def summarize_learning_batch(
    batch: LearningBatch,
) -> Dict[str, Any]:
    """
    Публичный helper статистики.
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
    print("ETC — Evolution Training Center")
    print("Learning Batch")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    print()
    print("ARCHITECTURAL CONTRACT")
    print("-" * 70)

    print(
        "BatchController = выбирает batch"
    )

    print(
        "LearningBatchBuilder = упаковывает batch"
    )

    print(
        "ETCController = оркестрирует"
    )

    print(
        "ETCLearningEngine = обучает"
    )

    print(
        "learning_memory = хранит результат"
    )

    print()
    print("READ ONLY")
    print("-" * 70)

    print(
        "matches: READ"
    )

    print(
        "match_results: READ"
    )

    print(
        "learning_memory: НЕ ИЗМЕНЯЕТСЯ"
    )

    print(
        "DELETE: отсутствует"
    )

    print(
        "DROP: отсутствует"
    )

    print(
        "INSERT: отсутствует"
    )

    print(
        "UPDATE: отсутствует"
    )

    print()
    print("ВАЖНО")
    print("-" * 70)

    print(
        "Этот модуль НЕ выбирает batch."
    )

    print(
        "Этот модуль НЕ создаёт batch_learning."
    )

    print(
        "Этот модуль НЕ обучает модель."
    )

    print(
        "Batch должен прийти от BatchController."
    )

    print("=" * 70)
