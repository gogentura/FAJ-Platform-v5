#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_engine.py
============================================================

ETC LEARNING ENGINE v1.4
============================================================

НАЗНАЧЕНИЕ
-----------

ETCLearningEngine — исполнитель ETC.

Он получает batch от BatchController,
передаёт завершённые матчи в StatisticalAnalyzer
и через LearningMemory фиксирует результаты анализа.

АРХИТЕКТУРА:

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
       ETCLearningEngine
              │
              ▼
       StatisticalAnalyzer
              │
              ▼
        analysis result
              │
              ├── analysis memory
              │
              └── batch_learning
                      │
                      ▼
                LearningMemory
                      │
                      ▼
                    SQLite


ГРАНИЦЫ ОТВЕТСТВЕННОСТИ
------------------------

ETCLearningEngine НЕ:

    - изменяет database.py;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - удаляет данные;
    - выполняет DELETE;
    - выполняет DROP;
    - рассчитывает прогноз;
    - рассчитывает xG самостоятельно;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - изменяет predictions;
    - изменяет календарь;
    - переписывает исторические факты.


ОТВЕТСТВЕННОСТЬ
---------------

ETCLearningEngine отвечает только за:

    1. получение готового batch;
    2. последовательную обработку матчей;
    3. вызов StatisticalAnalyzer;
    4. передачу analysis memory в LearningMemory;
    5. создание batch_learning marker;
    6. возврат строгого результата.


КОНТРАКТ MATCH
--------------

Матч считается успешно обработанным ETC только если:

    1. match_id валиден;
    2. StatisticalAnalyzer успешно завершил анализ;
    3. все memory events анализа успешно записаны;
    4. batch_learning marker успешно записан.

Только после выполнения всех четырёх условий:

    success = True


КОНТРАКТ PROCESSED
------------------

Для каждого успешно обработанного нового матча создаётся:

    event_type = 'batch_learning'
    reference_id = match_id

Запись выполняется ТОЛЬКО через:

    LearningMemory.record()


ПОВТОРНАЯ ОБРАБОТКА
-------------------

Если для match_id уже существует:

    event_type = 'batch_learning'
    reference_id = match_id

новый marker не создаётся.

Матч считается уже обработанным.


КОНТРАКТ BATCH
--------------

BatchController является владельцем:

    READY
    WAIT
    UNKNOWN_LEAGUE
    ALREADY_PROCESSED

ETCLearningEngine не переопределяет это решение.


ПОЛНЫЙ BATCH
------------

Полный batch считается completed только если:

    processed == total
    failed == 0

Только после этого может быть записан:

    batch_fingerprint


APPEND ONLY
-----------

learning_memory:

    APPEND ONLY

ETCLearningEngine:

    НЕ изменяет
    НЕ удаляет
    НЕ переписывает

существующие memory events.


СОВМЕСТИМОСТЬ
-------------

Сохраняется:

    LearningEngine = ETCLearningEngine

Также предоставляется:

    process_analysis()

как совместимая публичная точка.

Основной ETC-контракт:

    process_match()
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


MODULE_VERSION = "1.4"
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
    Главный исполнитель ETC.

    Контракт:

        BatchController
              ↓
        StatisticalAnalyzer
              ↓
        LearningMemory

    Никакой самостоятельной математики модели
    внутри класса нет.
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
            or BatchController(
                db=self.db
            )
        )

        self.analyzer = (
            analyzer
            or StatisticalAnalyzer(
                self.db
            )
        )

        self.memory = (
            memory
            or LearningMemory(
                self.db
            )
        )

    # ========================================================
    # SINGLE MATCH
    # ========================================================

    def process_match(
        self,
        match_id: int,
    ) -> Dict[str, Any]:
        """
        Полностью обрабатывает один матч.

        Последовательность:

            validate
                ↓
            processed check
                ↓
            StatisticalAnalyzer
                ↓
            analysis memory
                ↓
            batch_learning marker
                ↓
            success

        batch_learning создаётся только после
        успешной записи analysis memory.
        """

        safe_match_id = _safe_int(match_id)

        base_result: Dict[str, Any] = {
            "success": False,
            "status": "started",
            "match_id": safe_match_id,
            "analysis": None,
            "memory_ids": [],
            "learning_events": 0,
            "marker_id": None,
            "error": None,
            "created_at": _now(),
        }

        # ----------------------------------------------------
        # VALIDATE MATCH ID
        # ----------------------------------------------------

        if (
            safe_match_id is None
            or safe_match_id <= 0
        ):

            base_result["status"] = "invalid_match_id"

            base_result["error"] = (
                "Некорректный match_id."
            )

            return base_result

        logger.info(
            "ETC match START | match_id=%s",
            safe_match_id,
        )

        # ----------------------------------------------------
        # ALREADY PROCESSED
        # ----------------------------------------------------

        try:

            if self._is_match_processed(
                safe_match_id
            ):

                logger.info(
                    "ETC match already processed | "
                    "match_id=%s",
                    safe_match_id,
                )

                base_result["success"] = True
                base_result["status"] = (
                    "already_processed"
                )

                return base_result

        except Exception as exc:

            logger.exception(
                "ETC processed-state check failed | "
                "match_id=%s",
                safe_match_id,
            )

            base_result["status"] = (
                "processed_check_error"
            )

            base_result["error"] = str(exc)

            return base_result

        # ----------------------------------------------------
        # ANALYZE
        # ----------------------------------------------------

        try:

            analysis = (
                self.analyzer.analyze_match(
                    match_id=safe_match_id
                )
            )

        except Exception as exc:

            logger.exception(
                "ETC StatisticalAnalyzer failed | "
                "match_id=%s",
                safe_match_id,
            )

            base_result["status"] = (
                "analysis_error"
            )

            base_result["error"] = str(exc)

            return base_result

        # ----------------------------------------------------
        # EMPTY ANALYSIS
        # ----------------------------------------------------

        if not analysis:

            base_result["status"] = (
                "no_analysis"
            )

            base_result["error"] = (
                "StatisticalAnalyzer вернул "
                "пустой результат."
            )

            return base_result

        # ----------------------------------------------------
        # ANALYSIS MUST BE DICT
        # ----------------------------------------------------

        if not isinstance(
            analysis,
            dict,
        ):

            base_result["status"] = (
                "invalid_analysis"
            )

            base_result["error"] = (
                "StatisticalAnalyzer вернул "
                "не-dict результат."
            )

            return base_result

        base_result["analysis"] = analysis

        # ----------------------------------------------------
        # ANALYSIS FAILED
        # ----------------------------------------------------

        if not analysis.get(
            "success",
            False,
        ):

            base_result["status"] = (
                "analysis_failed"
            )

            base_result["error"] = (
                analysis.get(
                    "error",
                    analysis.get(
                        "status",
                        "analysis_failed",
                    ),
                )
            )

            base_result["errors"] = (
                analysis.get(
                    "errors",
                    [],
                )
            )

            return base_result

        # ----------------------------------------------------
        # STORE ANALYSIS MEMORY
        # ----------------------------------------------------

        try:

            memory_ids = (
                self._store_analysis_memory(
                    match_id=safe_match_id,
                    analysis=analysis,
                )
            )

        except Exception as exc:

            logger.exception(
                "ETC analysis memory failed | "
                "match_id=%s",
                safe_match_id,
            )

            base_result["status"] = (
                "memory_error"
            )

            base_result["error"] = str(exc)

            return base_result

        base_result["memory_ids"] = (
            memory_ids
        )

        base_result["learning_events"] = (
            len(memory_ids)
        )

        # ----------------------------------------------------
        # CREATE PROCESSED MARKER
        # ----------------------------------------------------

        try:

            marker_id = (
                self._record_match_processing(
                    match_id=safe_match_id,
                )
            )

        except Exception as exc:

            logger.exception(
                "ETC batch_learning marker failed | "
                "match_id=%s",
                safe_match_id,
            )

            base_result["status"] = (
                "marker_error"
            )

            base_result["error"] = str(exc)

            return base_result

        # ----------------------------------------------------
        # MARKER MUST EXIST
        # ----------------------------------------------------

        if marker_id is None:

            base_result["status"] = (
                "marker_not_created"
            )

            base_result["error"] = (
                "Не удалось создать "
                "batch_learning marker."
            )

            return base_result

        base_result["marker_id"] = (
            marker_id
        )

        base_result["memory_ids"].append(
            marker_id
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        base_result["success"] = True
        base_result["status"] = "processed"

        logger.info(
            "ETC match SUCCESS | "
            "match_id=%s | "
            "memory_events=%s | "
            "marker_id=%s",
            safe_match_id,
            len(memory_ids),
            marker_id,
        )

        return base_result

    # ========================================================
    # PROCESS ANALYSIS — COMPATIBILITY API
    # ========================================================

    def process_analysis(
        self,
        match_id: int,
        analysis: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Совместимая публичная точка обработки analysis.

        Если analysis не передан:
            process_match()

        Если analysis уже передан:
            StatisticalAnalyzer повторно НЕ вызывается.
        """

        safe_match_id = _safe_int(
            match_id
        )

        if (
            safe_match_id is None
            or safe_match_id <= 0
        ):

            return {
                "success": False,
                "status": "invalid_match_id",
                "match_id": safe_match_id,
                "memory_ids": [],
                "marker_id": None,
                "error": (
                    "Некорректный match_id."
                ),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # NO ANALYSIS PROVIDED
        # ----------------------------------------------------

        if analysis is None:

            return self.process_match(
                match_id=safe_match_id
            )

        # ----------------------------------------------------
        # ALREADY PROCESSED
        # ----------------------------------------------------

        try:

            if self._is_match_processed(
                safe_match_id
            ):

                return {
                    "success": True,
                    "status": "already_processed",
                    "match_id": safe_match_id,
                    "analysis": analysis,
                    "memory_ids": [],
                    "marker_id": None,
                    "created_at": _now(),
                }

        except Exception as exc:

            return {
                "success": False,
                "status": (
                    "processed_check_error"
                ),
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": [],
                "marker_id": None,
                "error": str(exc),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # VALIDATE ANALYSIS
        # ----------------------------------------------------

        if not isinstance(
            analysis,
            dict,
        ):

            return {
                "success": False,
                "status": "invalid_analysis",
                "match_id": safe_match_id,
                "memory_ids": [],
                "marker_id": None,
                "error": (
                    "analysis должен быть dict."
                ),
                "created_at": _now(),
            }

        if not analysis.get(
            "success",
            False,
        ):

            return {
                "success": False,
                "status": "analysis_failed",
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": [],
                "marker_id": None,
                "error": (
                    analysis.get(
                        "error",
                        analysis.get(
                            "status",
                            "analysis_failed",
                        ),
                    )
                ),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # STORE MEMORY
        # ----------------------------------------------------

        try:

            memory_ids = (
                self._store_analysis_memory(
                    match_id=safe_match_id,
                    analysis=analysis,
                )
            )

        except Exception as exc:

            return {
                "success": False,
                "status": "memory_error",
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": [],
                "marker_id": None,
                "error": str(exc),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # MARK PROCESSED
        # ----------------------------------------------------

        try:

            marker_id = (
                self._record_match_processing(
                    match_id=safe_match_id,
                )
            )

        except Exception as exc:

            return {
                "success": False,
                "status": "marker_error",
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": memory_ids,
                "marker_id": None,
                "error": str(exc),
                "created_at": _now(),
            }

        if marker_id is None:

            return {
                "success": False,
                "status": "marker_not_created",
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": memory_ids,
                "marker_id": None,
                "error": (
                    "batch_learning marker "
                    "не создан."
                ),
                "created_at": _now(),
            }

        memory_ids.append(
            marker_id
        )

        return {
            "success": True,
            "status": "processed",
            "match_id": safe_match_id,
            "analysis": analysis,
            "memory_ids": memory_ids,
            "marker_id": marker_id,
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

        Официальный ETCController передаёт:

            batch=[...]

        В этом режиме BatchController повторно
        НЕ вызывается.

        Автоматический режим остаётся совместимым,
        но основной архитектурный путь:

            ETCController
                ↓
            BatchController
                ↓
            get_learning_batch()
                ↓
            ETCLearningEngine.run_batch(batch=...)
        """

        started_at = _now()

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC BATCH START | "
            "league=%s | season=%s",
            league,
            season_id,
        )

        # ====================================================
        # DIRECT / OFFICIAL BATCH
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

                    "league": None,
                    "season_id": season_id,

                    "processed": 0,
                    "failed": 0,
                    "total": 0,

                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],

                    "errors": [
                        (
                            "Для автоматического ETC "
                            "batch необходимо указать "
                            "league."
                        )
                    ],

                    "created_at": _now(),
                }

            try:

                batch_check = (
                    self.batch_controller.check(
                        league=league,
                        season_id=season_id,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "ETC BatchController.check failed"
                )

                return {
                    "success": False,
                    "status": (
                        "batch_controller_error"
                    ),

                    "league": league,
                    "season_id": season_id,

                    "processed": 0,
                    "failed": 0,
                    "total": 0,

                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],

                    "errors": [
                        str(exc)
                    ],

                    "created_at": _now(),
                }

            controller_status = (
                batch_check.get("status")
            )

            if controller_status != STATUS_READY:

                return {
                    "success": True,
                    "status": (
                        controller_status
                        or "WAIT"
                    ),

                    "league": (
                        batch_check.get(
                            "league",
                            league,
                        )
                    ),

                    "season_id": season_id,

                    "processed": 0,
                    "failed": 0,
                    "total": 0,

                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],

                    "batch_check": batch_check,

                    "errors": [],

                    "created_at": _now(),
                }

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
                    "status": (
                        "batch_selection_error"
                    ),

                    "league": league,
                    "season_id": season_id,

                    "processed": 0,
                    "failed": 0,
                    "total": 0,

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

            return {
                "success": True,
                "status": "empty",

                "league": league,
                "season_id": season_id,

                "processed": 0,
                "failed": 0,
                "total": 0,

                "memory_ids": [],
                "processed_match_ids": [],
                "batch_memory_ids": [],

                "batch_check": batch_check,

                "errors": [],

                "created_at": _now(),
            }

        # ====================================================
        # NORMALIZE
        # ====================================================

        normalized_batch = (
            self._normalize_batch(
                selected_batch
            )
        )

        if not normalized_batch:

            return {
                "success": False,
                "status": "invalid_batch",

                "league": league,
                "season_id": season_id,

                "processed": 0,
                "failed": 0,
                "total": 0,

                "memory_ids": [],
                "processed_match_ids": [],
                "batch_memory_ids": [],

                "batch_check": batch_check,

                "errors": [
                    (
                        "Batch не содержит "
                        "валидных match_id."
                    )
                ],

                "created_at": _now(),
            }

        # ====================================================
        # PROCESS MATCHES
        # ====================================================

        processed = 0
        failed = 0
        learning_events = 0  # ← ДОБАВЛЕНО

        memory_ids: List[int] = []

        processed_match_ids: List[int] = []

        errors: List[
            Dict[str, Any]
        ] = []

        for item in normalized_batch:

            match_id = (
                self._extract_match_id(
                    item
                )
            )

            if match_id is None:

                failed += 1

                errors.append(
                    {
                        "match_id": None,
                        "error": (
                            "match_id not found"
                        ),
                    }
                )

                continue

            try:

                match_result = (
                    self.process_match(
                        match_id=match_id
                    )
                )

            except Exception as exc:

                match_result = {
                    "success": False,
                    "status": "exception",
                    "match_id": match_id,
                    "error": str(exc),
                    "memory_ids": [],
                }

            # ------------------------------------------------
            # FAILED
            # ------------------------------------------------

            if not match_result.get(
                "success",
                False,
            ):

                failed += 1

                errors.append(
                    {
                        "match_id": match_id,
                        "status": match_result.get(
                            "status"
                        ),
                        "error": match_result.get(
                            "error",
                            "processing_failed",
                        ),
                    }
                )

                logger.error(
                    "ETC batch match FAILED | "
                    "match_id=%s | status=%s",
                    match_id,
                    match_result.get(
                        "status"
                    ),
                )

                continue

            # ------------------------------------------------
            # SUCCESS / ALREADY PROCESSED
            # ------------------------------------------------

            processed += 1

            processed_match_ids.append(
                match_id
            )

            # ------------------------------------------------
            # АГРЕГАЦИЯ LEARNING_EVENTS
            # ------------------------------------------------

            learning_events += int(
                match_result.get(
                    "learning_events",
                    0,
                )
            )

            result_memory_ids = (
                match_result.get(
                    "memory_ids",
                    [],
                )
            )

            if isinstance(
                result_memory_ids,
                list,
            ):

                memory_ids.extend(
                    result_memory_ids
                )

            if (
                match_result.get("status")
                == "already_processed"
            ):

                logger.info(
                    "ETC batch match already "
                    "processed | match_id=%s",
                    match_id,
                )

        # ====================================================
        # BATCH STATUS
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
        # BATCH FINGERPRINT
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

                if fingerprint_id is None:

                    errors.append(
                        {
                            "match_id": None,
                            "stage": (
                                "batch_fingerprint"
                            ),
                            "error": (
                                "Не удалось записать "
                                "batch fingerprint."
                            ),
                        }
                    )

                    logger.error(
                        "ETC batch fingerprint "
                        "was not recorded"
                    )

                else:

                    batch_memory_ids.append(
                        fingerprint_id
                    )

                    memory_ids.append(
                        fingerprint_id
                    )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        result = {
            "success": batch_completed,

            "status": status,

            "league": league,

            "season_id": season_id,

            "processed": processed,

            "failed": failed,

            "total": total,

            "learning_events": learning_events,  # ← ДОБАВЛЕНО

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

        logger.info(
            "ETC BATCH FINISHED | "
            "status=%s | "
            "processed=%s/%s | "
            "failed=%s | "
            "learning_events=%s",
            status,
            processed,
            total,
            failed,
            learning_events,  # ← ДОБАВЛЕНО
        )

        logger.info(
            "=================================================="
        )

        return result

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
        Нормализует batch.

        Удаляет:

            - не-dict;
            - элементы без match_id;
            - дубликаты match_id.

        БД не изменяется.
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
                ._extract_match_id(
                    item
                )
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
        Извлекает match_id.

        Поддерживает:

            int

            {
                "match_id": 123
            }

            {
                "id": 123
            }
        """

        if item is None:
            return None

        if isinstance(
            item,
            int,
        ):

            return (
                item
                if item > 0
                else None
            )

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

        if (
            match_id is None
            or match_id <= 0
        ):

            return None

        return match_id

    # ========================================================
    # MATCH PROCESSING MARKER
    # ========================================================

    def _record_match_processing(
        self,
        match_id: int,
    ) -> Optional[int]:
        """
        Создаёт подтверждение успешной обработки
        конкретного матча.

        Контракт:

            event_type = batch_learning
            reference_id = match_id

        Запись выполняется только через
        LearningMemory.record().
        """

        # ----------------------------------------------------
        # DOUBLE CHECK
        # ----------------------------------------------------

        if self._is_match_processed(
            match_id
        ):

            logger.info(
                "ETC marker already exists | "
                "match_id=%s",
                match_id,
            )

            return None

        # ----------------------------------------------------
        # WRITE
        # ----------------------------------------------------

        try:

            memory_id = self.memory.record(
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

            if memory_id is None:

                raise RuntimeError(
                    "LearningMemory.record() "
                    "не вернул memory_id."
                )

            return int(
                memory_id
            )

        except Exception as exc:

            logger.exception(
                "ETC batch_learning marker "
                "failed | match_id=%s",
                match_id,
            )

            raise RuntimeError(
                f"Не удалось создать "
                f"batch_learning marker "
                f"для match_id={match_id}: "
                f"{exc}"
            ) from exc

    # ========================================================
    # CHECK PROCESSED
    # ========================================================

    def _is_match_processed(
        self,
        match_id: int,
    ) -> bool:
        """
        Проверяет наличие:

            event_type = batch_learning
            reference_id = match_id

        Используется LearningMemory.

        БД не изменяется.
        """

        rows = self.memory.get(
            event_type=(
                PROCESSED_EVENT_TYPE
            ),

            reference_id=match_id,

            limit=1,
        )

        return bool(
            rows
        )

    # ========================================================
    # ANALYSIS MEMORY
    # ========================================================

    def _store_analysis_memory(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[int]:
        """
        Сохраняет memory_events,
        сформированные StatisticalAnalyzer.

        Если хотя бы один обязательный
        memory event не записан —
        исключение.

        batch_learning marker в таком случае
        НЕ создаётся.
        """

        events = analysis.get(
            "memory_events"
        )

        if events is None:

            return []

        if not isinstance(
            events,
            list,
        ):

            events = [
                events
            ]

        memory_ids: List[int] = []

        for index, event in enumerate(
            events
        ):

            if not isinstance(
                event,
                dict,
            ):

                raise ValueError(
                    "Некорректный memory event "
                    f"#{index} для "
                    f"match_id={match_id}."
                )

            try:

                memory_id = (
                    self.memory.record(
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
                            "ETC.StatisticalAnalyzer",
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
                )

                if memory_id is None:

                    raise RuntimeError(
                        "LearningMemory.record() "
                        "вернул None."
                    )

                memory_ids.append(
                    int(memory_id)
                )

            except Exception as exc:

                raise RuntimeError(
                    "Ошибка записи "
                    f"analysis memory event "
                    f"#{index} для "
                    f"match_id={match_id}: "
                    f"{exc}"
                ) from exc

        return memory_ids

    # ========================================================
    # BATCH FINGERPRINT
    # ========================================================

    def _record_batch_fingerprint(
        self,
        league: Optional[str],
        season_id: Optional[int],
        fingerprint: str,
    ) -> Optional[int]:
        """
        Записывает диагностический fingerprint
        полностью завершённого batch.

        Это НЕ marker отдельного матча.

            reference_id = None
        """

        if not fingerprint:

            return None

        try:

            memory_id = (
                self.memory.record(
                    event_type=(
                        PROCESSED_EVENT_TYPE
                    ),

                    object_type=(
                        f"league:"
                        f"{league or 'unknown'}"
                    ),

                    feature=(
                        "batch_fingerprint"
                    ),

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
                        "ETC.LearningEngine"
                    ),

                    model_version=(
                        MODULE_VERSION
                    ),

                    reference_id=None,
                )
            )

            if memory_id is None:

                return None

            return int(
                memory_id
            )

        except Exception as exc:

            logger.exception(
                "ETC batch fingerprint "
                "write failed | "
                "league=%s | season=%s",
                league,
                season_id,
            )

            return None

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Read-only состояние ETC Learning Engine.
        """

        return {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "database": (
                "FAJDatabase"
            ),

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

            "batch_controller_is_authority": (
                True
            ),

            "processed_marker": (
                PROCESSED_EVENT_TYPE
            ),

            "analysis_method": (
                "process_match"
            ),

            "compatibility_method": (
                "process_analysis"
            ),

            "historical_facts_modified": (
                False
            ),

            "model_parameters_modified": (
                False
            ),

            "faj_rating_modified": (
                False
            ),

            "predictions_modified": (
                False
            ),

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
    Официальная точка запуска ETC batch.
    """

    engine = ETCLearningEngine(
        db=db
    )

    return engine.run_batch(
        league=league,
        season_id=season_id,
        batch=batch,
    )


def process_learning_match(
    match_id: int,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Публичная точка обработки одного матча.
    """

    engine = ETCLearningEngine(
        db=db
    )

    return engine.process_match(
        match_id=match_id
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
    print("FAJ Platform v12.1")
    print("ETC — Evolution Training Center")
    print("Learning Engine")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        engine = ETCLearningEngine()

        status = engine.status()

        print()
        print("ETC LEARNING ENGINE STATUS")
        print("-" * 70)

        for key, value in status.items():

            print(
                f"{key}: {value}"
            )

        print()
        print(
            "ETCLearningEngine готов."
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
            "Основной контракт:"
        )

        print(
            "BatchController → "
            "get_learning_batch() → "
            "ETCLearningEngine.run_batch()"
        )

        print()
        print(
            "batch_learning создаётся "
            "только после успешного анализа "
            "и успешной записи memory."
        )

        print()
        print(
            "process_analysis() доступен "
            "как compatibility API."
        )

        print()
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

    print("=" * 70)
