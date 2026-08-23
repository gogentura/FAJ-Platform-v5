#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_engine.py
============================================================

НАЗНАЧЕНИЕ
-----------

ETC Learning Engine — строгий оркестратор пакетного
эволюционного анализа FAJ.

КОНТРАКТ:

    FACTS
      │
      ▼
    BatchController
      │
      ├── WAIT
      ├── READY
      └── ALREADY_PROCESSED
              │
              ▼
       get_learning_batch()
              │
              ▼
    StatisticalAnalyzer
              │
              ▼
      ETCLearningEngine
              │
              ├── analysis memory
              │
              └── batch_learning
                      │
                      ▼
              LearningMemory
                      │
                      ▼
                 FAJDatabase
                      │
                      ▼
                    SQLite


ВАЖНО
------

Этот модуль НЕ:

    - изменяет database.py;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - удаляет данные;
    - выполняет DELETE;
    - выполняет DROP;
    - самостоятельно рассчитывает прогноз;
    - самостоятельно рассчитывает xG;
    - самостоятельно изменяет FAJ Rating;
    - самостоятельно изменяет model_parameters;
    - переписывает исторические факты.


ОТВЕТСТВЕННОСТЬ
---------------

ETCLearningEngine отвечает только за:

    1. получение готового batch;
    2. последовательную обработку матчей;
    3. получение результатов StatisticalAnalyzer;
    4. передачу memory events в LearningMemory;
    5. фиксацию успешной обработки матча;
    6. возврат строгого результата ETC.


ПРАВИЛО BATCH
-------------

BatchController определяет:

    READY
    WAIT
    UNKNOWN_LEAGUE
    ALREADY_PROCESSED

ETCLearningEngine НЕ переопределяет
решение BatchController.


ПРАВИЛО PROCESSED
-----------------

Матч считается обработанным ETC только после
успешного завершения его обработки.

Маркер:

    event_type = 'batch_learning'
    reference_id = match_id

Создаётся через:

    LearningMemory.record()

Никаких прямых INSERT в learning_memory.


ПРАВИЛО ATOMIC BATCH
--------------------

Полный batch считается completed только если:

    каждый выбранный матч
    успешно прошёл StatisticalAnalyzer.

Если хотя бы один матч завершился ошибкой:

    batch status = failed / partial

и fingerprint полного batch НЕ записывается
как успешно обработанный batch.


ПРАВИЛО APPEND-ONLY
-------------------

learning_memory:

    APPEND ONLY

Существующие записи:

    НЕ изменяются
    НЕ удаляются
    НЕ переписываются.


============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


from app.database import FAJDatabase

from app.etc.batch_controller import (
    BatchController,
    STATUS_READY,
)

from app.etc.learning_memory import (
    LearningMemory,
)

from app.etc.statistical_analyzer import (
    StatisticalAnalyzer,
)


logger = logging.getLogger(__name__)


MODULE_VERSION = "1.2"
MODULE_NAME = "FAJ ETC Learning Engine"


PROCESSED_EVENT_TYPE = "batch_learning"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает текущее локальное время
    в ISO формате.
    """

    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:
    """
    Безопасное преобразование в int.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):

        return default


# ============================================================
# MAIN CLASS
# ============================================================

class ETCLearningEngine:
    """
    Главный оркестратор ETC.

    Архитектурная цепочка:

        BatchController
              ↓
        StatisticalAnalyzer
              ↓
        LearningMemory

    Никакого самостоятельного изменения
    модели внутри класса нет.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        batch_controller: Optional[BatchController] = None,
        analyzer: Optional[StatisticalAnalyzer] = None,
        memory: Optional[LearningMemory] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.batch_controller = (
            batch_controller
            or BatchController(self.db)
        )

        self.analyzer = (
            analyzer
            or StatisticalAnalyzer(self.db)
        )

        self.memory = (
            memory
            or LearningMemory(self.db)
        )

    # ========================================================
    # SINGLE MATCH
    # ========================================================

    def process_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Анализирует один завершённый матч.

        ВАЖНО:

        Успешный анализ сам по себе НЕ изменяет модель.

        StatisticalAnalyzer должен только читать
        фактические данные и возвращать analysis.

        Этот метод НЕ записывает batch_learning.

        Маркер batch_learning создаётся только
        оркестратором после подтверждённого успеха.
        """

        safe_match_id = _safe_int(
            match_id
        )

        if safe_match_id is None or safe_match_id <= 0:

            return {
                "success": False,
                "status": "invalid_match_id",
                "match_id": safe_match_id,
                "memory_ids": [],
                "created_at": _now(),
            }

        logger.info(
            "ETC: processing match_id=%s",
            safe_match_id,
        )

        # ----------------------------------------------------
        # ANALYZE
        # ----------------------------------------------------

        try:

            analysis = self.analyzer.analyze_match(
                match_id=safe_match_id
            )

        except Exception as exc:

            logger.exception(
                "ETC analysis failed | match_id=%s",
                safe_match_id,
            )

            return {
                "success": False,
                "status": "analysis_error",
                "match_id": safe_match_id,
                "error": str(exc),
                "memory_ids": [],
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # EMPTY RESULT
        # ----------------------------------------------------

        if not analysis:

            return {
                "success": False,
                "status": "no_analysis",
                "match_id": safe_match_id,
                "memory_ids": [],
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # ANALYSIS FAILED
        # ----------------------------------------------------

        if not analysis.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "status": "analysis_failed",
                "match_id": safe_match_id,
                "analysis": analysis,
                "errors": analysis.get(
                    "errors",
                    [],
                ),
                "memory_ids": [],
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # STORE ANALYSIS MEMORY
        # ----------------------------------------------------

        memory_ids = self._store_analysis_memory(
            match_id=safe_match_id,
            analysis=analysis,
        )

        return {
            "success": True,
            "status": "processed",
            "match_id": safe_match_id,
            "analysis": analysis,
            "memory_ids": memory_ids,
            "created_at": _now(),
        }

    # ========================================================
    # BATCH
    # ========================================================

    def run_batch(
        self,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
        batch: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Запускает один ETC batch.

        Автоматический режим:

            run_batch(
                league="РПЛ",
                season_id=...
            )

        Ручной режим:

            run_batch(
                batch=[...]
            )

        В автоматическом режиме:

            BatchController
                ↓
            READY
                ↓
            get_learning_batch()
                ↓
            process

        ВАЖНО:

        BatchController остаётся владельцем
        правил выбора batch.

        ETCLearningEngine не изменяет эти правила.
        """

        started_at = _now()

        logger.info(
            "ETC: starting batch"
        )

        # ====================================================
        # DIRECT BATCH
        # ====================================================

        if batch is not None:

            selected_batch = list(
                batch
            )

            batch_check = {
                "status": "DIRECT",
                "league": league,
                "season_id": season_id,

                "required_matches": len(
                    selected_batch
                ),

                "new_matches": len(
                    selected_batch
                ),

                "match_ids": [
                    self._extract_match_id(
                        item
                    )
                    for item in selected_batch
                    if self._extract_match_id(
                        item
                    ) is not None
                ],

                "batch_fingerprint": None,
            }

        # ====================================================
        # CONTROLLER MODE
        # ====================================================

        else:

            if not league:

                return {
                    "success": False,
                    "status": "league_required",
                    "processed": 0,
                    "failed": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "errors": [
                        "Для автоматического ETC batch "
                        "необходимо указать league."
                    ],
                    "created_at": started_at,
                }

            # ------------------------------------------------
            # CHECK
            # ------------------------------------------------

            try:

                batch_check = (
                    self.batch_controller.check(
                        league=league,
                        season_id=season_id,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "ETC BatchController check failed"
                )

                return {
                    "success": False,
                    "status": "batch_controller_error",
                    "processed": 0,
                    "failed": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "errors": [
                        str(exc)
                    ],
                    "created_at": _now(),
                }

            controller_status = batch_check.get(
                "status"
            )

            # ------------------------------------------------
            # NOT READY
            # ------------------------------------------------

            if controller_status != STATUS_READY:

                return {
                    "success": True,
                    "status": controller_status or "WAIT",

                    "league": batch_check.get(
                        "league",
                        league,
                    ),

                    "season_id": season_id,

                    "processed": 0,
                    "failed": 0,

                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],

                    "batch_check": batch_check,

                    "errors": [],

                    "created_at": _now(),
                }

            # ------------------------------------------------
            # OFFICIAL BATCH API
            # ------------------------------------------------

            try:

                selected_batch = (
                    self.batch_controller
                    .get_learning_batch(
                        league=league,
                        season_id=season_id,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "ETC get_learning_batch failed"
                )

                return {
                    "success": False,
                    "status": "batch_selection_error",

                    "processed": 0,
                    "failed": 0,

                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],

                    "batch_check": batch_check,

                    "errors": [
                        str(exc)
                    ],

                    "created_at": _now(),
                }

        # ====================================================
        # EMPTY
        # ====================================================

        if not selected_batch:

            logger.info(
                "ETC: selected batch is empty"
            )

            return {
                "success": True,
                "status": "empty",

                "league": league,
                "season_id": season_id,

                "processed": 0,
                "failed": 0,

                "memory_ids": [],
                "processed_match_ids": [],
                "batch_memory_ids": [],

                "batch_check": batch_check,

                "errors": [],

                "created_at": _now(),
            }

        # ====================================================
        # NORMALIZE BATCH
        # ====================================================

        normalized_batch = self._normalize_batch(
            selected_batch
        )

        if not normalized_batch:

            return {
                "success": False,
                "status": "invalid_batch",

                "league": league,
                "season_id": season_id,

                "processed": 0,
                "failed": 0,

                "memory_ids": [],
                "processed_match_ids": [],
                "batch_memory_ids": [],

                "batch_check": batch_check,

                "errors": [
                    "Batch не содержит валидных match_id."
                ],

                "created_at": _now(),
            }

        # ====================================================
        # PROCESS MATCHES
        # ====================================================

        processed = 0
        failed = 0

        memory_ids: List[int] = []

        errors: List[
            Dict[str, Any]
        ] = []

        processed_match_ids: List[int] = []

        for item in normalized_batch:

            match_id = self._extract_match_id(
                item
            )

            if match_id is None:

                failed += 1

                errors.append(
                    {
                        "item": item,
                        "error": "match_id not found",
                    }
                )

                continue

            # ------------------------------------------------
            # PROCESS
            # ------------------------------------------------

            result = self.process_match(
                match_id=match_id
            )

            if not result.get(
                "success",
                False,
            ):

                failed += 1

                errors.append(
                    {
                        "match_id": match_id,
                        "error": result.get(
                            "error",
                            result.get(
                                "status",
                                "processing_failed",
                            ),
                        ),
                    }
                )

                continue

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            processed += 1

            processed_match_ids.append(
                match_id
            )

            memory_ids.extend(
                result.get(
                    "memory_ids",
                    [],
                )
            )

            # ------------------------------------------------
            # MATCH PROCESSED MARKER
            # ------------------------------------------------

            marker_id = (
                self._record_match_processing(
                    match_id=match_id,
                    league=league,
                    season_id=season_id,
                )
            )

            if marker_id is not None:

                memory_ids.append(
                    marker_id
                )

        # ====================================================
        # DETERMINE BATCH STATUS
        # ====================================================

        total = len(
            normalized_batch
        )

        batch_completed = (
            total > 0
            and processed == total
            and failed == 0
        )

        if batch_completed:

            status = "completed"

        elif processed > 0:

            status = "partial"

        else:

            status = "failed"

        # ====================================================
        # FULL BATCH FINGERPRINT
        # ====================================================

        batch_memory_ids: List[int] = []

        if batch_completed:

            fingerprint = (
                batch_check.get(
                    "batch_fingerprint"
                )
            )

            if fingerprint:

                fingerprint_id = (
                    self._record_batch_fingerprint(
                        league=league,
                        season_id=season_id,
                        fingerprint=fingerprint,
                    )
                )

                if fingerprint_id is not None:

                    batch_memory_ids.append(
                        fingerprint_id
                    )

                    memory_ids.append(
                        fingerprint_id
                    )

        # ====================================================
        # RESULT
        # ====================================================

        logger.info(
            "ETC batch finished | "
            "status=%s | "
            "processed=%s | "
            "failed=%s",
            status,
            processed,
            failed,
        )

        return {
            "success": batch_completed,

            "status": status,

            "league": league,

            "season_id": season_id,

            "processed": processed,

            "failed": failed,

            "total": total,

            "processed_match_ids": (
                processed_match_ids
            ),

            "memory_ids": memory_ids,

            "batch_memory_ids": (
                batch_memory_ids
            ),

            "batch_completed": (
                batch_completed
            ),

            "batch_check": batch_check,

            "errors": errors,

            "created_at": _now(),
        }

    # ========================================================
    # NORMALIZE BATCH
    # ========================================================

    @staticmethod
    def _normalize_batch(
        batch: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Нормализует входной batch.

        Не меняет данные БД.

        Убирает:

            - не-dict элементы;
            - элементы без валидного ID;
            - дубликаты match_id.

        Порядок первого появления сохраняется.
        """

        result: List[
            Dict[str, Any]
        ] = []

        seen: Set[int] = set()

        for item in batch:

            if not isinstance(
                item,
                dict,
            ):
                continue

            match_id = (
                ETCLearningEngine
                ._extract_match_id(item)
            )

            if match_id is None:
                continue

            if match_id in seen:
                continue

            seen.add(
                match_id
            )

            result.append(
                item
            )

        return result

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Any,
    ) -> Optional[int]:
        """
        Извлекает ID матча.

        Поддерживаются:

            match_id
            id
        """

        if not isinstance(
            item,
            dict,
        ):
            return None

        value = item.get(
            "match_id"
        )

        if value is None:

            value = item.get(
                "id"
            )

        match_id = _safe_int(
            value
        )

        if match_id is None:
            return None

        if match_id <= 0:
            return None

        return match_id

    # ========================================================
    # MATCH PROCESSING MEMORY
    # ========================================================

    def _record_match_processing(
        self,
        match_id: int,
        league: Optional[str],
        season_id: Optional[int],
    ) -> Optional[int]:
        """
        Записывает подтверждение успешной обработки
        конкретного матча.

        КРИТИЧЕСКОЕ ПРАВИЛО:

            batch_learning
            reference_id = match_id

        создаётся только ПОСЛЕ успешного
        StatisticalAnalyzer.

        Повторный marker не создаётся, если
        такой event уже существует.
        """

        if self._is_match_processed(
            match_id
        ):

            logger.warning(
                "ETC match already processed | "
                "match_id=%s",
                match_id,
            )

            return None

        try:

            return int(
                self.memory.record(
                    event_type=(
                        PROCESSED_EVENT_TYPE
                    ),

                    object_type=(
                        f"match:{match_id}"
                    ),

                    feature=(
                        "etc_batch_processed"
                    ),

                    before_value=None,

                    after_value="processed",

                    delta=None,

                    reason=(
                        "Матч успешно обработан "
                        "ETC Learning Engine."
                    ),

                    confidence=1.0,

                    impact=0.0,

                    algorithm=(
                        "ETC.LearningEngine"
                    ),

                    model_version=(
                        MODULE_VERSION
                    ),

                    reference_id=match_id,
                )
            )

        except Exception as exc:

            logger.exception(
                "Failed to record ETC "
                "processing marker | "
                "match_id=%s",
                match_id,
            )

            return None

    # ========================================================
    # CHECK PROCESSED
    # ========================================================

    def _is_match_processed(
        self,
        match_id: int,
    ) -> bool:
        """
        Проверяет наличие подтверждённого
        batch_learning события для матча.

        Использует только SELECT через
        LearningMemory.

        База не изменяется.
        """

        try:

            rows = self.memory.get(
                event_type=(
                    PROCESSED_EVENT_TYPE
                ),

                reference_id=match_id,

                limit=1,
            )

            return bool(rows)

        except Exception as exc:

            logger.warning(
                "Unable to check ETC "
                "processing marker | "
                "match_id=%s | error=%s",
                match_id,
                exc,
            )

            return False

    # ========================================================
    # BATCH FINGERPRINT MEMORY
    # ========================================================

    def _record_batch_fingerprint(
        self,
        league: Optional[str],
        season_id: Optional[int],
        fingerprint: str,
    ) -> Optional[int]:
        """
        Фиксирует fingerprint успешно завершённого
        batch.

        Это диагностическое событие.

        Оно НЕ используется как marker отдельного
        обработанного матча.

        Поэтому:

            reference_id = NULL
        """

        try:

            return int(
                self.memory.record(
                    event_type=(
                        PROCESSED_EVENT_TYPE
                    ),

                    object_type=(
                        f"league:{league or 'unknown'}"
                    ),

                    feature="batch_fingerprint",

                    before_value=None,

                    after_value=fingerprint,

                    delta=None,

                    reason=(
                        "ETC batch полностью "
                        "и успешно обработан."
                    ),

                    confidence=1.0,

                    impact=0.0,

                    algorithm=(
                        "ETC.BatchController"
                    ),

                    model_version=(
                        MODULE_VERSION
                    ),

                    reference_id=None,
                )
            )

        except Exception as exc:

            logger.exception(
                "Failed to record ETC "
                "batch fingerprint"
            )

            return None

    # ========================================================
    # MEMORY EVENTS
    # ========================================================

    def _store_analysis_memory(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[int]:
        """
        Сохраняет memory_events, сформированные
        StatisticalAnalyzer.

        ВАЖНО:

        Отсутствие memory_events является нормальным.

        Если analyzer вернул memory_events,
        они передаются исключительно через
        LearningMemory.
        """

        memory_ids: List[int] = []

        events = analysis.get(
            "memory_events"
        )

        if events is None:

            return memory_ids

        if not isinstance(
            events,
            list,
        ):

            events = [
                events
            ]

        for event in events:

            if not isinstance(
                event,
                dict,
            ):
                continue

            try:

                memory_id = self.memory.record(
                    event_type=event.get(
                        "event_type",
                        "learning_event",
                    ),

                    object_type=event.get(
                        "object_type",
                        f"match:{match_id}",
                    ),

                    feature=event.get(
                        "feature",
                        "unknown",
                    ),

                    before_value=event.get(
                        "before_value"
                    ),

                    after_value=event.get(
                        "after_value"
                    ),

                    delta=event.get(
                        "delta"
                    ),

                    reason=event.get(
                        "reason",
                        "",
                    ),

                    confidence=event.get(
                        "confidence",
                        1.0,
                    ),

                    impact=event.get(
                        "impact",
                        1.0,
                    ),

                    algorithm=event.get(
                        "algorithm",
                        "ETC.LearningEngine",
                    ),

                    model_version=event.get(
                        "model_version",
                        MODULE_VERSION,
                    ),

                    reference_id=event.get(
                        "reference_id",
                        match_id,
                    ),
                )

                memory_ids.append(
                    int(memory_id)
                )

            except Exception as exc:

                logger.exception(
                    "Failed to store ETC "
                    "memory | match_id=%s | "
                    "error=%s",
                    match_id,
                    exc,
                )

        return memory_ids

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Возвращает состояние ETC Learning Engine.
        """

        return {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "database": "FAJDatabase",

            "batch_controller": (
                self.batch_controller
                .__class__
                .__name__
            ),

            "analyzer": (
                self.analyzer
                .__class__
                .__name__
            ),

            "memory": (
                self.memory
                .__class__
                .__name__
            ),

            "append_only": True,

            "batch_controller_is_authority": True,

            "processed_marker": (
                PROCESSED_EVENT_TYPE
            ),

            "historical_facts_modified": False,

            "model_parameters_modified": False,

            "faj_rating_modified": False,

            "predictions_modified": False,

            "created_at": _now(),
        }


# ============================================================
# PUBLIC API
# ============================================================

def run_learning_batch(
    db: Optional[FAJDatabase] = None,
    league: Optional[str] = None,
    season_id: Optional[int] = None,
    batch: Optional[
        List[Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """
    Официальная точка запуска ETC.

    Автоматический режим:

        run_learning_batch(
            db=db,
            league="РПЛ",
            season_id=...
        )

    Ручной диагностический режим:

        run_learning_batch(
            db=db,
            batch=[...]
        )
    """

    engine = ETCLearningEngine(
        db=db
    )

    return engine.run_batch(
        league=league,
        season_id=season_id,
        batch=batch,
    )


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

LearningEngine = ETCLearningEngine


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
    print("FAJ ETC — Learning Engine")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        engine = ETCLearningEngine()

        print()
        print(
            "Module:",
            engine.status(),
        )

        print()
        print(
            "ETC Learning Engine готов."
        )

        print(
            "BatchController подключён."
        )

        print(
            "StatisticalAnalyzer подключён."
        )

        print(
            "LearningMemory подключён."
        )

        print()
        print(
            "BatchController является "
            "источником решения READY/WAIT."
        )

        print(
            "batch_learning создаётся "
            "только после успешной обработки матча."
        )

        print(
            "database.py НЕ изменяется."
        )

        print(
            "Исторические факты НЕ изменяются."
        )

        print(
            "DELETE/DROP отсутствуют."
        )

    except Exception as exc:

        print(
            "ETC Learning Engine "
            f"initialization error: {exc}"
        )
