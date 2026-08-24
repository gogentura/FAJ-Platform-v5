#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_engine.py
============================================================

ETC LEARNING ENGINE v1.9
============================================================

НАЗНАЧЕНИЕ
-----------

ETCLearningEngine — исполнитель ETC.

Он получает batch от BatchController,
передаёт завершённые матчи в StatisticalAnalyzer,
преобразует результат анализа в memory events
и через LearningMemory фиксирует результаты обучения.

АРХИТЕКТУРА:

    FACTS
      │
      ▼
    BatchController
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
    analysis
      │
      ├── observations
      ├── prediction data
      ├── fact data
      ├── xG data
      │
      ▼
    ETC memory-event builder
      │
      ▼
    LearningMemory
      │
      ▼
    batch_learning marker
      │
      ▼
    SQLite


КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ v1.9
--------------------------

Ранее ETC ожидал:

    analysis["memory_events"]

Но StatisticalAnalyzer фактически возвращает:

    analysis["success"]
    analysis["observations"]
    ...

без обязательного поля:

    memory_events

В результате:

    events = None
    return []

и ETC останавливался:

    no_memory_events

Теперь ETCLearningEngine сам преобразует
результат StatisticalAnalyzer в memory events.

Источник событий:

    1. analysis["memory_events"]       — если уже есть;
    2. analysis["observations"]        — основной источник;
    3. prediction/fact data            — prediction_error;
    4. xG data                         — xg_calibration.

ВАЖНО:

ETC НЕ придумывает факты.

Если prediction/fact/xG данных нет,
соответствующее специализированное событие
не создаётся.

Но наличие observations достаточно,
чтобы анализ матча был сохранён в LearningMemory.

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

ETCLearningEngine отвечает только за:

    1. получение готового batch;
    2. обработку матчей;
    3. вызов StatisticalAnalyzer;
    4. преобразование analysis в memory events;
    5. запись memory events;
    6. создание batch_learning marker;
    7. создание batch fingerprint;
    8. возврат строгого результата.


КОНТРАК MATCH
--------------

Матч считается успешно обработанным ETC только если:

    1. match_id валиден;
    2. StatisticalAnalyzer успешно завершил анализ;
    3. создан хотя бы один memory event;
    4. все созданные memory events записаны;
    5. batch_learning marker успешно записан.

Только после выполнения этих условий:

    success = True


КОНТРАК PROCESSED
------------------

Для каждого успешно обработанного нового матча:

    event_type = 'batch_learning'
    reference_id = match_id

Запись выполняется через:

    LearningMemory.record_batch_learning()


ПОВТОРНАЯ ОБРАБОТКА
-------------------

Если для match_id уже существует:

    event_type = 'batch_learning'
    reference_id = match_id

новый marker не создаётся.

Матч считается уже обработанным.


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

Основной ETC-контракт:

    process_match()
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


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


# ============================================================
# MODULE
# ============================================================

MODULE_VERSION = "1.9"
MODULE_NAME = "FAJ ETC Learning Engine"

PROCESSED_EVENT_TYPE = "batch_learning"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Текущее локальное время в ISO формате.
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


def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Безопасное преобразование в float.
    """

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


def _first(
    data: Any,
    keys: List[str],
    default: Any = None,
) -> Any:
    """
    Возвращает первое найденное значение
    из списка ключей.

    Используется для совместимости разных
    структур analysis.
    """

    if not isinstance(data, dict):
        return default

    for key in keys:

        if key in data and data.get(key) is not None:
            return data.get(key)

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
        ETC memory-event builder
              ↓
        LearningMemory
              ↓
        batch_learning

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
            build memory events
                ↓
            store memory events
                ↓
            batch_learning marker
                ↓
            success
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
        # VALIDATE
        # ----------------------------------------------------

        if (
            safe_match_id is None
            or safe_match_id <= 0
        ):

            base_result["status"] = (
                "invalid_match_id"
            )

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
        # EMPTY
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
        # TYPE
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
        # ANALYSIS STATUS
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
        # BUILD + STORE MEMORY
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

        # ----------------------------------------------------
        # AT LEAST ONE EVENT REQUIRED
        # ----------------------------------------------------

        if not memory_ids:

            base_result["status"] = (
                "no_memory_events"
            )

            base_result["error"] = (
                "ETC не смог создать "
                "ни одного memory event "
                f"для match_id={safe_match_id}."
            )

            logger.warning(
                "ETC match %s: no memory events created",
                safe_match_id,
            )

            return base_result

        base_result["memory_ids"] = list(
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

        base_result["marker_id"] = marker_id

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
            "analysis_events=%s | "
            "marker_id=%s",
            safe_match_id,
            len(memory_ids),
            marker_id,
        )

        return base_result

    # ========================================================
    # PROCESS ANALYSIS
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

        Если analysis передан:

            StatisticalAnalyzer повторно
            НЕ вызывается.
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
                "learning_events": 0,
                "marker_id": None,
                "error": (
                    "Некорректный match_id."
                ),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # NO ANALYSIS
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
                    "learning_events": 0,
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
                "learning_events": 0,
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
                "learning_events": 0,
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
                "learning_events": 0,
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
                "learning_events": 0,
                "marker_id": None,
                "error": str(exc),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # NO EVENTS
        # ----------------------------------------------------

        if not memory_ids:

            return {
                "success": False,
                "status": "no_memory_events",
                "match_id": safe_match_id,
                "analysis": analysis,
                "memory_ids": [],
                "learning_events": 0,
                "marker_id": None,
                "error": (
                    "Анализ не создал событий памяти "
                    f"для match_id={safe_match_id}"
                ),
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
                "learning_events": len(
                    memory_ids
                ),
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
                "learning_events": len(
                    memory_ids
                ),
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
            "learning_events": len(
                memory_ids
            ) - 1,
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
        # DIRECT BATCH
        # ====================================================

        if batch is not None:

            selected_batch = list(
                batch
            )

            match_ids = []

            for item in selected_batch:

                extracted_id = (
                    self._extract_match_id(
                        item
                    )
                )

                if extracted_id is not None:

                    match_ids.append(
                        extracted_id
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
                "match_ids": match_ids,
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
                    "already_processed": 0,
                    "failed": 0,
                    "total": 0,
                    "learning_events": 0,
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
                    "already_processed": 0,
                    "failed": 0,
                    "total": 0,
                    "learning_events": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "errors": [str(exc)],
                    "created_at": _now(),
                }

            if not isinstance(
                batch_check,
                dict,
            ):

                return {
                    "success": False,
                    "status": (
                        "invalid_batch_controller_result"
                    ),
                    "league": league,
                    "season_id": season_id,
                    "processed": 0,
                    "already_processed": 0,
                    "failed": 0,
                    "total": 0,
                    "learning_events": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "errors": [
                        (
                            "BatchController.check() "
                            "вернул не-dict."
                        )
                    ],
                    "created_at": _now(),
                }

            controller_status = (
                batch_check.get(
                    "status"
                )
            )

            # ------------------------------------------------
            # CONTROLLER IS AUTHORITY
            # ------------------------------------------------

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
                    "already_processed": 0,
                    "failed": 0,
                    "total": 0,
                    "learning_events": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "batch_check": batch_check,
                    "errors": [],
                    "created_at": _now(),
                }

            # ------------------------------------------------
            # GET LEARNING BATCH
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
                    "status": (
                        "batch_selection_error"
                    ),
                    "league": league,
                    "season_id": season_id,
                    "processed": 0,
                    "already_processed": 0,
                    "failed": 0,
                    "total": 0,
                    "learning_events": 0,
                    "memory_ids": [],
                    "processed_match_ids": [],
                    "batch_memory_ids": [],
                    "batch_check": batch_check,
                    "errors": [str(exc)],
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
                "already_processed": 0,
                "failed": 0,
                "total": 0,
                "learning_events": 0,
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
                "already_processed": 0,
                "failed": 0,
                "total": 0,
                "learning_events": 0,
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
        # STATUS MODEL
        # ====================================================

        match_statuses: Dict[int, str] = {}

        for item in normalized_batch:

            match_id = (
                self._extract_match_id(
                    item
                )
            )

            if match_id is None:
                continue

            if self._is_match_processed(
                match_id
            ):

                match_statuses[match_id] = (
                    "already_processed"
                )

            else:

                match_statuses[match_id] = "new"

        new_match_ids = [
            mid
            for mid, status in match_statuses.items()
            if status == "new"
        ]

        already_processed_ids = [
            mid
            for mid, status in match_statuses.items()
            if status == "already_processed"
        ]

        logger.info(
            "ETC batch statuses | "
            "new=%s | already=%s | skipped=%s",
            len(new_match_ids),
            len(already_processed_ids),
            0,
        )

        # ====================================================
        # PROCESS NEW
        # ====================================================

        processed = 0
        already_processed = len(
            already_processed_ids
        )
        failed = 0
        learning_events = 0

        memory_ids: List[int] = []
        processed_match_ids: List[int] = []

        errors: List[
            Dict[str, Any]
        ] = []

        for match_id in new_match_ids:

            try:

                match_result = (
                    self.process_match(
                        match_id=match_id
                    )
                )

            except Exception as exc:

                logger.exception(
                    "ETC batch unexpected "
                    "match exception | "
                    "match_id=%s",
                    match_id,
                )

                match_result = {
                    "success": False,
                    "status": "exception",
                    "match_id": match_id,
                    "error": str(exc),
                    "memory_ids": [],
                    "learning_events": 0,
                }

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

            processed += 1

            processed_match_ids.append(
                match_id
            )

            match_learning_events = (
                _safe_int(
                    match_result.get(
                        "learning_events",
                        0,
                    ),
                    0,
                )
                or 0
            )

            learning_events += (
                match_learning_events
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

        # ====================================================
        # BATCH COMPLETION
        # ====================================================

        total = len(
            normalized_batch
        )

        #
        # ВАЖНО:
        #
        # total = все матчи batch
        #
        # batch completed:
        #
        #   processed новых + already processed
        #   == total
        #
        #   failed == 0
        #
        # То есть повторный запуск уже обработанного
        # batch не ломает completed.
        #

        batch_completed = (
            total > 0
            and (
                processed
                + already_processed
                == total
            )
            and failed == 0
        )

        # ====================================================
        # BATCH FINGERPRINT
        # ====================================================

        batch_memory_ids: List[int] = []

        fingerprint = None

        if isinstance(
            batch_check,
            dict,
        ):

            fingerprint = (
                batch_check.get(
                    "batch_fingerprint"
                )
            )

        if batch_completed:

            if fingerprint:

                fingerprint_id = (
                    self._record_batch_fingerprint(
                        league=league,
                        season_id=season_id,
                        fingerprint=fingerprint,
                    )
                )

                if fingerprint_id is None:

                    batch_completed = False

                    errors.append(
                        {
                            "match_id": None,
                            "stage": (
                                "batch_fingerprint"
                            ),
                            "error": (
                                "Batch обработан, "
                                "но batch fingerprint "
                                "не удалось записать."
                            ),
                        }
                    )

                    logger.error(
                        "ETC batch completion "
                        "BLOCKED | fingerprint "
                        "was not recorded"
                    )

                else:

                    batch_memory_ids.append(
                        fingerprint_id
                    )

                    memory_ids.append(
                        fingerprint_id
                    )

            else:

                logger.info(
                    "ETC batch fingerprint "
                    "not supplied | "
                    "league=%s | "
                    "completion accepted",
                    league,
                )

        # ====================================================
        # FINAL STATUS
        # ====================================================

        if batch_completed:

            status = "completed"

        elif processed > 0 or already_processed > 0:

            status = "partial"

        else:

            status = "failed"

        # ====================================================
        # RESULT
        # ====================================================

        result = {
            "success": batch_completed,
            "status": status,
            "league": league,
            "season_id": season_id,
            "processed": processed,
            "already_processed": already_processed,
            "failed": failed,
            "total": total,
            "learning_events": learning_events,
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
            "started_at": started_at,
            "created_at": _now(),
        }

        logger.info(
            "ETC BATCH FINISHED | "
            "status=%s | "
            "new_processed=%s | "
            "already=%s | "
            "failed=%s | "
            "total=%s | "
            "learning_events=%s | "
            "batch_memory_events=%s",
            status,
            processed,
            already_processed,
            failed,
            total,
            learning_events,
            len(batch_memory_ids),
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
        Создаёт batch_learning marker.
        """

        try:

            memory_id = (
                self.memory.record_batch_learning(
                    match_id=match_id,
                    reason=(
                        "Матч успешно обработан "
                        "ETC Learning Engine."
                    ),
                    algorithm=(
                        "ETC.LearningEngine"
                    ),
                    model_version=(
                        MODULE_VERSION
                    ),
                )
            )

            if memory_id is None:

                raise RuntimeError(
                    "LearningMemory.record_batch_learning() "
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
        Проверяет наличие batch_learning marker.
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
    # MEMORY EVENT BUILDER
    # ========================================================

    def _build_memory_events(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Главный исправленный участок ETC.

        Преобразует результат StatisticalAnalyzer
        в реальные memory events.

        Источники:

            memory_events
            observations
            prediction/fact
            xG

        Никакие факты не создаются искусственно.
        """

        events: List[
            Dict[str, Any]
        ] = []

        # ====================================================
        # 1. ГОТОВЫЕ MEMORY EVENTS
        # ====================================================

        existing_events = analysis.get(
            "memory_events"
        )

        if existing_events is not None:

            if isinstance(
                existing_events,
                list,
            ):

                for event in existing_events:

                    if isinstance(
                        event,
                        dict,
                    ):

                        events.append(
                            dict(event)
                        )

            elif isinstance(
                existing_events,
                dict,
            ):

                events.append(
                    dict(existing_events)
                )

        # ====================================================
        # 2. OBSERVATIONS
        # ====================================================

        observations = analysis.get(
            "observations",
            []
        )

        if isinstance(
            observations,
            (list, tuple),
        ):

            for index, observation in enumerate(
                observations
            ):

                event = (
                    self._observation_to_event(
                        match_id=match_id,
                        observation=observation,
                        index=index,
                    )
                )

                if event is not None:

                    events.append(
                        event
                    )

        elif observations:

            event = (
                self._observation_to_event(
                    match_id=match_id,
                    observation=observations,
                    index=0,
                )
            )

            if event is not None:

                events.append(
                    event
                )

        # ====================================================
        # 3. PREDICTION ERROR
        # ====================================================

        prediction_event = (
            self._build_prediction_error_event(
                match_id=match_id,
                analysis=analysis,
            )
        )

        if prediction_event is not None:

            events.append(
                prediction_event
            )

        # ====================================================
        # 4. XG CALIBRATION
        # ====================================================

        xg_events = (
            self._build_xg_events(
                match_id=match_id,
                analysis=analysis,
            )
        )

        events.extend(
            xg_events
        )

        # ====================================================
        # 5. FALLBACK
        # ====================================================

        #
        # Если analyzer успешно завершился, но не вернул
        # observations, всё равно сохраняем факт успешного
        # анализа как memory event.
        #
        # Это не подмена результата анализа.
        # Это технический audit event ETC.
        #

        if not events:

            summary = _first(
                analysis,
                [
                    "summary",
                    "message",
                    "status",
                ],
                "StatisticalAnalyzer успешно завершил анализ.",
            )

            events.append(
                {
                    "event_type": (
                        "analysis_completed"
                    ),
                    "object_type": (
                        f"match:{match_id}"
                    ),
                    "feature": (
                        "statistical_analysis"
                    ),
                    "after_value": summary,
                    "delta": None,
                    "reason": (
                        "StatisticalAnalyzer "
                        "успешно завершил анализ матча."
                    ),
                    "confidence": 1.0,
                    "impact": 0.1,
                    "algorithm": (
                        "ETC.StatisticalAnalyzer"
                    ),
                    "model_version": (
                        MODULE_VERSION
                    ),
                    "reference_id": match_id,
                }
            )

        return events

    # ========================================================
    # OBSERVATION -> MEMORY EVENT
    # ========================================================

    def _observation_to_event(
        self,
        match_id: int,
        observation: Any,
        index: int,
    ) -> Optional[
        Dict[str, Any]
    ]:
        """
        Преобразует observation в memory event.

        Поддерживает как string, так и dict.
        """

        if observation is None:
            return None

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(
            observation,
            dict,
        ):

            event = dict(
                observation
            )

            event.setdefault(
                "event_type",
                "observation",
            )

            event.setdefault(
                "object_type",
                f"match:{match_id}",
            )

            event.setdefault(
                "feature",
                _first(
                    observation,
                    [
                        "feature",
                        "type",
                        "category",
                        "name",
                    ],
                    f"observation_{index + 1}",
                ),
            )

            event.setdefault(
                "reason",
                _first(
                    observation,
                    [
                        "reason",
                        "description",
                        "message",
                        "observation",
                    ],
                    "",
                ),
            )

            event.setdefault(
                "confidence",
                _first(
                    observation,
                    [
                        "confidence",
                    ],
                    1.0,
                ),
            )

            event.setdefault(
                "impact",
                _first(
                    observation,
                    [
                        "impact",
                    ],
                    0.5,
                ),
            )

            event.setdefault(
                "algorithm",
                "ETC.StatisticalAnalyzer",
            )

            event.setdefault(
                "model_version",
                MODULE_VERSION,
            )

            event.setdefault(
                "reference_id",
                match_id,
            )

            return event

        # ----------------------------------------------------
        # STRING / OTHER
        # ----------------------------------------------------

        return {
            "event_type": "observation",
            "object_type": (
                f"match:{match_id}"
            ),
            "feature": (
                f"observation_{index + 1}"
            ),
            "before_value": None,
            "after_value": str(
                observation
            ),
            "delta": None,
            "reason": str(
                observation
            ),
            "confidence": 1.0,
            "impact": 0.5,
            "algorithm": (
                "ETC.StatisticalAnalyzer"
            ),
            "model_version": MODULE_VERSION,
            "reference_id": match_id,
        }

    # ========================================================
    # PREDICTION ERROR
    # ========================================================

    def _build_prediction_error_event(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> Optional[
        Dict[str, Any]
    ]:
        """
        Создаёт prediction_error только если
        prediction и fact реально присутствуют
        в analysis.

        Никаких догадок.
        """

        prediction = _first(
            analysis,
            [
                "prediction",
                "predictions",
                "match_prediction",
            ],
        )

        fact = _first(
            analysis,
            [
                "fact",
                "actual",
                "result",
                "match_result",
                "facts",
            ],
        )

        # ----------------------------------------------------
        # Иногда analyzer хранит prediction/fact
        # внутри validation.
        # ----------------------------------------------------

        validation = analysis.get(
            "validation"
        )

        if isinstance(
            validation,
            dict,
        ):

            if prediction is None:

                prediction = _first(
                    validation,
                    [
                        "prediction",
                        "predictions",
                    ],
                )

            if fact is None:

                fact = _first(
                    validation,
                    [
                        "fact",
                        "actual",
                        "result",
                    ],
                )

        if not isinstance(
            prediction,
            dict,
        ):

            return None

        if not isinstance(
            fact,
            dict,
        ):

            return None

        predicted_score = self._extract_score(
            prediction
        )

        actual_score = self._extract_score(
            fact
        )

        if (
            predicted_score is None
            or actual_score is None
        ):

            return None

        predicted_home, predicted_away = (
            predicted_score
        )

        actual_home, actual_away = (
            actual_score
        )

        score_error = (
            abs(predicted_home - actual_home)
            + abs(predicted_away - actual_away)
        )

        if score_error == 0:

            error_type = "exact_prediction"

            severity = 0.0

        elif (
            predicted_home == actual_home
            and predicted_away != actual_away
        ):

            error_type = "away_score_error"

            severity = 0.5

        elif (
            predicted_home != actual_home
            and predicted_away == actual_away
        ):

            error_type = "home_score_error"

            severity = 0.5

        else:

            error_type = "score_error"

            severity = min(
                1.0,
                score_error / 4.0,
            )

        return {
            "event_type": "prediction_error",
            "object_type": (
                f"match:{match_id}"
            ),
            "feature": error_type,
            "before_value": (
                f"{predicted_home}:{predicted_away}"
            ),
            "after_value": (
                f"{actual_home}:{actual_away}"
            ),
            "delta": score_error,
            "reason": (
                "Сравнение прогноза "
                "с фактическим результатом матча."
            ),
            "confidence": 0.8,
            "impact": severity,
            "algorithm": (
                "ETC.PredictionValidation"
            ),
            "model_version": MODULE_VERSION,
            "reference_id": match_id,
        }

    # ========================================================
    # SCORE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_score(
        data: Dict[str, Any],
    ) -> Optional[
        Tuple[int, int]
    ]:
        """
        Пытается извлечь счёт из разных
        совместимых структур.
        """

        if not isinstance(
            data,
            dict,
        ):

            return None

        # ----------------------------------------------------
        # home_score / away_score
        # ----------------------------------------------------

        home = _first(
            data,
            [
                "home_score",
                "home_goals",
                "goals_home",
                "home",
            ],
        )

        away = _first(
            data,
            [
                "away_score",
                "away_goals",
                "goals_away",
                "away",
            ],
        )

        home_i = _safe_int(
            home
        )

        away_i = _safe_int(
            away
        )

        if (
            home_i is not None
            and away_i is not None
            and home_i >= 0
            and away_i >= 0
        ):

            return (
                home_i,
                away_i,
            )

        # ----------------------------------------------------
        # score = "2:1"
        # ----------------------------------------------------

        score = _first(
            data,
            [
                "score",
                "final_score",
            ],
        )

        if isinstance(
            score,
            str,
        ):

            text = score.strip()

            if ":" in text:

                parts = text.split(
                    ":",
                    1,
                )

                if len(parts) == 2:

                    h = _safe_int(
                        parts[0].strip()
                    )

                    a = _safe_int(
                        parts[1].strip()
                    )

                    if (
                        h is not None
                        and a is not None
                        and h >= 0
                        and a >= 0
                    ):

                        return (
                            h,
                            a,
                        )

        return None

    # ========================================================
    # XG EVENTS
    # ========================================================

    def _build_xg_events(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Создаёт xG events только если xG
        реально присутствует в analysis.

        ETC не рассчитывает xG.
        Он только фиксирует отклонение
        уже рассчитанного xG.
        """

        events: List[
            Dict[str, Any]
        ] = []

        xg_data = _first(
            analysis,
            [
                "xg",
                "xg_analysis",
                "xg_calibration",
                "xg_data",
            ],
        )

        # ----------------------------------------------------
        # TEAM LIST FORMAT
        # ----------------------------------------------------

        if isinstance(
            xg_data,
            dict,
        ):

            teams = xg_data.get(
                "teams"
            )

            if isinstance(
                teams,
                list,
            ):

                for team in teams:

                    if not isinstance(
                        team,
                        dict,
                    ):

                        continue

                    event = (
                        self._xg_team_to_event(
                            match_id=match_id,
                            team=team,
                        )
                    )

                    if event is not None:

                        events.append(
                            event
                        )

            # ------------------------------------------------
            # DIRECT HOME/AWAY FORMAT
            # ------------------------------------------------

            if not teams:

                home = xg_data.get(
                    "home"
                )

                away = xg_data.get(
                    "away"
                )

                if isinstance(
                    home,
                    dict,
                ):

                    event = (
                        self._xg_team_to_event(
                            match_id=match_id,
                            team=home,
                            side="home",
                        )
                    )

                    if event is not None:

                        events.append(
                            event
                        )

                if isinstance(
                    away,
                    dict,
                ):

                    event = (
                        self._xg_team_to_event(
                            match_id=match_id,
                            team=away,
                            side="away",
                        )
                    )

                    if event is not None:

                        events.append(
                            event
                        )

        return events

    # ========================================================
    # XG TEAM EVENT
    # ========================================================

    def _xg_team_to_event(
        self,
        match_id: int,
        team: Dict[str, Any],
        side: Optional[str] = None,
    ) -> Optional[
        Dict[str, Any]
    ]:
        """
        Преобразует данные xG одной команды
        в memory event.
        """

        predicted_xg = _first(
            team,
            [
                "predicted_xg",
                "expected_xg",
                "xg_predicted",
                "prediction_xg",
            ],
        )

        actual_xg = _first(
            team,
            [
                "actual_xg",
                "observed_xg",
                "xg_actual",
                "fact_xg",
            ],
        )

        predicted = _safe_float(
            predicted_xg
        )

        actual = _safe_float(
            actual_xg
        )

        if (
            predicted is None
            or actual is None
        ):

            return None

        deviation = (
            predicted - actual
        )

        absolute_error = abs(
            deviation
        )

        direction = (
            "overestimated"
            if deviation > 0
            else (
                "underestimated"
                if deviation < 0
                else "calibrated"
            )
        )

        team_id = _first(
            team,
            [
                "team_id",
                "id",
            ],
            side or "unknown",
        )

        return {
            "event_type": (
                "xg_calibration"
            ),
            "object_type": (
                f"match:{match_id}"
            ),
            "feature": (
                "xg_deviation"
            ),
            "before_value": predicted,
            "after_value": actual,
            "delta": deviation,
            "reason": (
                f"team_{team_id}: "
                f"{direction}"
            ),
            "confidence": 0.7,
            "impact": min(
                1.0,
                absolute_error / 2.0,
            ),
            "algorithm": (
                "ETC.XGCalibration"
            ),
            "model_version": MODULE_VERSION,
            "reference_id": match_id,

            # ------------------------------------------------
            # Структурированные xG поля.
            # LearningMemory их не теряет,
            # если поддерживает соответствующие поля.
            # ------------------------------------------------

            "predicted_xg": predicted,
            "actual_xg": actual,
            "xg_deviation": deviation,
            "absolute_xg_error": absolute_error,
            "xg_available": True,
        }

    # ========================================================
    # STORE ANALYSIS MEMORY
    # ========================================================

    def _store_analysis_memory(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[int]:
        """
        Строит и сохраняет memory events.

        Ключевое отличие v1.9:

            если StatisticalAnalyzer
            не создал memory_events,

            ETC использует observations.

        batch_learning marker здесь НЕ создаётся.
        """

        events = (
            self._build_memory_events(
                match_id=match_id,
                analysis=analysis,
            )
        )

        if not events:

            return []

        memory_ids: List[int] = []

        # ----------------------------------------------------
        # WRITE EVENTS
        # ----------------------------------------------------

        for index, original_event in enumerate(
            events
        ):

            if not isinstance(
                original_event,
                dict,
            ):

                raise ValueError(
                    "Некорректный memory event "
                    f"#{index} для "
                    f"match_id={match_id}."
                )

            event = dict(
                original_event
            )

            event_type = event.get(
                "event_type",
                "learning_event",
            )

            # ------------------------------------------------
            # DUPLICATE prediction_error
            # ------------------------------------------------

            if event_type == "prediction_error":

                existing = self.memory.get(
                    event_type=(
                        "prediction_error"
                    ),
                    reference_id=match_id,
                    limit=1,
                )

                if existing:

                    logger.info(
                        "prediction_error already exists "
                        "for match_id=%s, "
                        "skipping duplicate",
                        match_id,
                    )

                    continue

            # ------------------------------------------------
            # STRUCTURED xG
            # ------------------------------------------------

            predicted_xg = _safe_float(
                event.get(
                    "predicted_xg"
                )
            )

            actual_xg = _safe_float(
                event.get(
                    "actual_xg"
                )
            )

            if (
                predicted_xg is not None
                and actual_xg is not None
            ):

                event["xg_deviation"] = (
                    predicted_xg
                    - actual_xg
                )

                event["absolute_xg_error"] = (
                    abs(
                        predicted_xg
                        - actual_xg
                    )
                )

                event["xg_available"] = True

            else:

                event["xg_available"] = bool(
                    event.get(
                        "xg_available",
                        False,
                    )
                )

            # ------------------------------------------------
            # WRITE
            # ------------------------------------------------

            try:

                memory_id = (
                    self.memory.record(
                        event_type=event_type,

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
        Записывает fingerprint полностью
        завершённого batch.
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

                raise RuntimeError(
                    "LearningMemory.record() "
                    "не вернул memory_id "
                    "для batch fingerprint."
                )

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

            "memory_event_sources": [
                "analysis.memory_events",
                "analysis.observations",
                "prediction_vs_fact",
                "xg_data",
            ],

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

            "calendar_modified": (
                False
            ),

            "delete_operations": (
                False
            ),

            "drop_operations": (
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

    print(
        "FAJ Platform v12.1"
    )

    print(
        "ETC — Evolution Training Center"
    )

    print(
        "Learning Engine"
    )

    print(
        f"Version: {MODULE_VERSION}"
    )

    print("=" * 70)

    try:

        engine = ETCLearningEngine()

        status = engine.status()

        print()
        print(
            "ETC LEARNING ENGINE STATUS"
        )

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
            "Новый контракт:"
        )

        print(
            "FACTS → BatchController → "
            "StatisticalAnalyzer → "
            "observations → "
            "memory_events → "
            "LearningMemory → "
            "batch_learning"
        )

        print()

        print(
            "Источники memory events:"
        )

        print(
            "1. analysis.memory_events"
        )

        print(
            "2. analysis.observations"
        )

        print(
            "3. prediction vs fact"
        )

        print(
            "4. xG data"
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

        print()

        print(
            "Критическое исправление v1.9:"
        )

        print(
            "StatisticalAnalyzer больше "
            "не обязан самостоятельно "
            "создавать memory_events."
        )

        print()

        print(
            "ETC сам преобразует observations "
            "в LearningMemory events."
        )

    except Exception as exc:

        print(
            "ETC Learning Engine "
            f"initialization error: {exc}"
        )

    print("=" * 70)
