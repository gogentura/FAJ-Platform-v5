#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/etc_controller.py
============================================================

НАЗНАЧЕНИЕ
-----------

Верхний оркестратор ETC.

ETC запускается только после появления новых фактов
сыгранных матчей.

АРХИТЕКТУРА:

    MATCH
      ↓
    IMPORT FACTS
      ↓
    match_results / match_statistics
      ↓
    ETCController
      ↓
    BatchController
      ↓
    READY / WAIT / ALREADY_PROCESSED
      ↓
    готовый batch
      ↓
    ETCLearningEngine.process_match()
      ↓
    StatisticalAnalyzer
      ↓
    LearningMemory
      ↓
    BatchController.mark_processed()
      ↓
    NEXT ETC BATCH


ГРАНИЦЫ ОТВЕТСТВЕННОСТИ
------------------------

ETCController НЕ:

    - считает xG;
    - считает прогноз;
    - классифицирует ошибки;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - пишет learning_memory напрямую;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - изменяет календарь;
    - изменяет database.py;
    - выполняет DELETE;
    - выполняет DROP.

ETCController отвечает только за ORCHESTRATION:

    1. получение batch;
    2. последовательный запуск LearningEngine;
    3. сбор результатов;
    4. передача только успешных матчей
       в BatchController.mark_processed();
    5. возврат строгого результата ETC.


ВАЖНО
------

ETCLearningEngine уже владеет:

    StatisticalAnalyzer
    LearningMemory

Поэтому ETCController никогда не вызывает
StatisticalAnalyzer напрямую.


ВАЖНО №2
---------

ETCLearningEngine.process_match() НЕ должен создавать
batch_learning marker.

Marker успешной обработки матча создаётся владельцем
batch-state:

    BatchController.mark_processed()

Это устраняет двойное владение состоянием.


ИДЕМПОТЕНТНОСТЬ
---------------

BatchController является единственным владельцем
состояния processed/unprocessed.

ETCController:

    НЕ хранит свой список обработанных матчей;
    НЕ определяет самостоятельно processed;
    НЕ пишет learning_memory;
    НЕ пытается заменить BatchController.


ОШИБКА ОДНОГО МАТЧА
-------------------

Ошибка одного матча НЕ останавливает batch.

Успешные матчи:

    → передаются в mark_processed()

Неуспешные:

    → НЕ передаются в mark_processed()

Следующий ETC-run сможет обработать
оставшиеся матчи.


FORCE
-----

force=True только передаётся BatchController.

force НЕ превращает ошибку анализа
в успешную обработку.


============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


from app.database import FAJDatabase

from app.etc.batch_controller import (
    BatchController,
)

from app.etc.learning_engine import (
    ETCLearningEngine,
)


logger = logging.getLogger(__name__)


MODULE_VERSION = "3.0"
MODULE_NAME = "FAJ ETC Controller"


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
    Безопасное преобразование значения в int.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):

        return default


def _safe_count(
    value: Any,
    default: int = 0,
) -> int:
    """
    Безопасное преобразование значения
    в неотрицательный счётчик.
    """

    try:

        if value is None:
            return default

        return max(
            0,
            int(value),
        )

    except (TypeError, ValueError):

        return default


# ============================================================
# ETC CONTROLLER
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center.

    ETCController НЕ содержит математической логики.

    Его ответственность:

        BatchController
              ↓
        ETCLearningEngine
              ↓
        BatchController.mark_processed()

    Владелец:

        batch lifecycle = BatchController
        analysis       = ETCLearningEngine
        statistics     = StatisticalAnalyzer
        memory         = LearningMemory
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        batch_controller: Optional[
            BatchController
        ] = None,
        learning_engine: Optional[
            ETCLearningEngine
        ] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        # ----------------------------------------------------
        # SINGLE OWNER OF BATCH STATE
        # ----------------------------------------------------

        self.batch_controller = (
            batch_controller
            or BatchController(
                db=self.db
            )
        )

        # ----------------------------------------------------
        # SINGLE OWNER OF ANALYSIS
        # ----------------------------------------------------

        self.learning_engine = (
            learning_engine
            or ETCLearningEngine(
                db=self.db
            )
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Read-only состояние ETC.

        Никаких изменений БД.
        """

        result: Dict[str, Any] = {

            "module": MODULE_NAME,

            "version": MODULE_VERSION,

            "status": "ready",

            "timestamp": _now(),

            "pending_matches": None,

            "batch_controller": (
                self.batch_controller
                .__class__
                .__name__
            ),

            "learning_engine": (
                self.learning_engine
                .__class__
                .__name__
            ),

            "batch_state_owner": (
                "BatchController"
            ),

            "analysis_owner": (
                "ETCLearningEngine"
            ),

            "memory_owner": (
                "LearningMemory"
            ),

            "historical_facts_modified": False,

            "model_parameters_modified": False,

            "faj_rating_modified": False,

            "predictions_modified": False,

            "append_only_memory": True,
        }

        try:

            method = getattr(
                self.batch_controller,
                "get_pending_count",
                None,
            )

            if callable(method):

                result[
                    "pending_matches"
                ] = _safe_count(
                    method()
                )

        except Exception as exc:

            logger.warning(
                "ETC status degraded: %s",
                exc,
            )

            result[
                "status"
            ] = "degraded"

            result[
                "status_error"
            ] = str(exc)

        return result

    # ========================================================
    # RUN
    # ========================================================

    def run(
        self,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Выполняет один полный ETC-run.

        FLOW:

            1. BatchController.create_batch()
            2. LearningEngine.process_match()
            3. BatchController.mark_processed()

        Только успешные матчи передаются
        в mark_processed().
        """

        started_at = _now()

        result: Dict[str, Any] = {

            "module": MODULE_NAME,

            "version": MODULE_VERSION,

            "status": "started",

            "started_at": started_at,

            "finished_at": None,

            "batch_size": 0,

            "analyzed": 0,

            "learned": 0,

            "processed": 0,

            "memory_events": 0,

            "learning_events": 0,

            "errors": 0,

            "failed_matches": [],

            "processed_match_ids": [],

            "message": "",
        }

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC RUN STARTED | limit=%s | force=%s",
            limit,
            force,
        )

        # ====================================================
        # STEP 1
        # ====================================================

        try:

            logger.info(
                "ETC STEP 1/3 — CREATE BATCH"
            )

            batch = (
                self.batch_controller.create_batch(
                    limit=limit,
                    force=force,
                )
            )

        except Exception as exc:

            logger.exception(
                "ETC BatchController.create_batch failed"
            )

            result[
                "status"
            ] = "batch_error"

            result[
                "errors"
            ] = 1

            result[
                "message"
            ] = str(exc)

            result[
                "finished_at"
            ] = _now()

            return result

        # ====================================================
        # EMPTY BATCH
        # ====================================================

        if not batch:

            result[
                "status"
            ] = "nothing_to_process"

            result[
                "message"
            ] = (
                "Нет новых завершённых "
                "матчей для ETC."
            )

            result[
                "finished_at"
            ] = _now()

            logger.info(
                "ETC RUN FINISHED — "
                "nothing to process"
            )

            return result

        result[
            "batch_size"
        ] = len(batch)

        logger.info(
            "ETC batch created: %s matches",
            len(batch),
        )

        # ====================================================
        # STEP 2
        # ====================================================

        logger.info(
            "ETC STEP 2/3 — LEARNING ENGINE"
        )

        successful_items: List[Any] = []

        for batch_item in batch:

            match_id = (
                self._extract_match_id(
                    batch_item
                )
            )

            # ------------------------------------------------
            # INVALID ITEM
            # ------------------------------------------------

            if match_id is None:

                result[
                    "errors"
                ] += 1

                result[
                    "failed_matches"
                ].append(
                    {
                        "match_id": None,
                        "stage": "batch",
                        "error": (
                            "Batch item "
                            "не содержит "
                            "валидный match_id"
                        ),
                    }
                )

                logger.error(
                    "ETC invalid batch item: %r",
                    batch_item,
                )

                continue

            # ------------------------------------------------
            # PROCESS MATCH
            # ------------------------------------------------

            try:

                learning_result = (
                    self.learning_engine
                    .process_match(
                        match_id=match_id
                    )
                )

                if not isinstance(
                    learning_result,
                    dict,
                ):

                    raise ValueError(
                        "LearningEngine "
                        "вернул не-dict"
                    )

                if not learning_result.get(
                    "success",
                    False,
                ):

                    status = (
                        learning_result.get(
                            "status",
                            "processing_failed",
                        )
                    )

                    error = (
                        learning_result.get(
                            "error"
                        )
                        or status
                    )

                    raise ValueError(
                        f"LearningEngine "
                        f"неуспешен: {error}"
                    )

                # --------------------------------------------
                # SUCCESS
                # --------------------------------------------

                successful_items.append(
                    batch_item
                )

                result[
                    "analyzed"
                ] += 1

                result[
                    "learned"
                ] += 1

                result[
                    "processed_match_ids"
                ].append(
                    match_id
                )

                memory_ids = (
                    learning_result.get(
                        "memory_ids",
                        [],
                    )
                )

                if isinstance(
                    memory_ids,
                    list,
                ):

                    result[
                        "memory_events"
                    ] += len(
                        memory_ids
                    )

                result[
                    "learning_events"
                ] += _safe_count(
                    learning_result.get(
                        "learning_events",
                        0,
                    )
                )

                logger.info(
                    "ETC learning OK | "
                    "match_id=%s",
                    match_id,
                )

            except Exception as exc:

                result[
                    "errors"
                ] += 1

                result[
                    "failed_matches"
                ].append(
                    {
                        "match_id": match_id,
                        "stage": "learning",
                        "error": str(exc),
                    }
                )

                logger.exception(
                    "ETC learning failed | "
                    "match_id=%s",
                    match_id,
                )

                # ВАЖНО:
                #
                # Ошибка одного матча
                # НЕ останавливает batch.

                continue

        # ====================================================
        # STEP 3
        # ====================================================

        logger.info(
            "ETC STEP 3/3 — MARK PROCESSED"
        )

        # ----------------------------------------------------
        # НЕТ УСПЕШНЫХ МАТЧЕЙ
        # ----------------------------------------------------

        if not successful_items:

            result[
                "status"
            ] = "failed"

            result[
                "message"
            ] = (
                "Ни один матч не прошёл "
                "ETCLearningEngine."
            )

            result[
                "finished_at"
            ] = _now()

            return result

        # ----------------------------------------------------
        # MARK ONLY SUCCESSFUL ITEMS
        # ----------------------------------------------------

        try:

            processed = (
                self.batch_controller
                .mark_processed(
                    successful_items
                )
            )

            result[
                "processed"
            ] = _safe_count(
                processed,
                0,
            )

        except Exception as exc:

            # ------------------------------------------------
            # CRITICAL
            # ------------------------------------------------

            result[
                "processed"
            ] = 0

            result[
                "errors"
            ] += 1

            result[
                "failed_matches"
            ].append(
                {
                    "match_id": None,
                    "stage": "mark_processed",
                    "error": str(exc),
                }
            )

            logger.exception(
                "ETC mark_processed failed"
            )

        # ====================================================
        # FINAL STATUS
        # ====================================================

        result[
            "finished_at"
        ] = _now()

        batch_size = (
            result["batch_size"]
        )

        processed = (
            result["processed"]
        )

        failed = (
            result["errors"]
        )

        # ----------------------------------------------------
        # COMPLETE
        # ----------------------------------------------------

        if (
            processed == batch_size
            and failed == 0
        ):

            result[
                "status"
            ] = "completed"

            result[
                "message"
            ] = (
                "ETC полностью обработал "
                "batch."
            )

        # ----------------------------------------------------
        # PARTIAL
        # ----------------------------------------------------

        elif processed > 0:

            result[
                "status"
            ] = "partial"

            result[
                "message"
            ] = (
                "ETC частично обработал "
                "batch. Неуспешные матчи "
                "не закрыты."
            )

        # ----------------------------------------------------
        # ANALYSIS SUCCESS BUT MARK FAILED
        # ----------------------------------------------------

        elif result["learned"] > 0:

            result[
                "status"
            ] = "mark_failed"

            result[
                "message"
            ] = (
                "Анализ ETC выполнен, "
                "но BatchController "
                "не смог закрыть "
                "обработанные матчи."
            )

        # ----------------------------------------------------
        # TOTAL FAILURE
        # ----------------------------------------------------

        else:

            result[
                "status"
            ] = "failed"

            result[
                "message"
            ] = (
                "ETC не смог успешно "
                "обработать batch."
            )

        logger.info(
            "ETC RUN FINISHED | "
            "status=%s | "
            "batch=%s | "
            "analyzed=%s | "
            "learned=%s | "
            "processed=%s | "
            "errors=%s",
            result["status"],
            result["batch_size"],
            result["analyzed"],
            result["learned"],
            result["processed"],
            result["errors"],
        )

        logger.info(
            "=================================================="
        )

        return result

    # ========================================================
    # SINGLE MATCH
    # ========================================================

    def process_match(
        self,
        match_id: int,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Диагностическая обработка одного матча.

        ВАЖНО:

        Здесь НЕ вызывается BatchController.mark_processed().

        Этот метод предназначен для:

            Match Laboratory
            диагностики
            ручного анализа

        Полный ETC lifecycle использует run().
        """

        normalized_match_id = (
            _safe_int(match_id)
        )

        result: Dict[str, Any] = {

            "module": MODULE_NAME,

            "version": MODULE_VERSION,

            "match_id": normalized_match_id,

            "status": "started",

            "learning": None,

            "error": None,
        }

        if normalized_match_id is None:

            result[
                "status"
            ] = "invalid_match_id"

            result[
                "error"
            ] = "Некорректный match_id"

            if force:
                return result

            raise ValueError(
                "Некорректный match_id"
            )

        try:

            learning = (
                self.learning_engine
                .process_match(
                    match_id=normalized_match_id
                )
            )

            result[
                "learning"
            ] = learning

            if not isinstance(
                learning,
                dict,
            ):

                raise ValueError(
                    "LearningEngine "
                    "вернул не-dict"
                )

            if not learning.get(
                "success",
                False,
            ):

                raise ValueError(
                    "LearningEngine "
                    "неуспешен: "
                    f"{learning.get('error') "
                    f"or learning.get('status', "
                    f"'processing_failed')}"
                )

            result[
                "status"
            ] = "completed"

            return result

        except Exception as exc:

            result[
                "status"
            ] = "failed"

            result[
                "error"
            ] = str(exc)

            logger.exception(
                "ETC single match failed | "
                "match_id=%s",
                normalized_match_id,
            )

            if force:
                return result

            raise

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Any,
    ) -> Optional[int]:
        """
        Унифицированное извлечение match_id.

        Поддерживает:

            int
            dict
            sqlite3.Row
            Mapping
            object.match_id
            object.id
        """

        if item is None:
            return None

        # ----------------------------------------------------
        # INT
        # ----------------------------------------------------

        if isinstance(
            item,
            int,
        ):

            return (
                item
                if item > 0
                else None
            )

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(
            item,
            dict,
        ):

            value = item.get(
                "match_id"
            )

            if value is None:

                value = item.get(
                    "id"
                )

            normalized = _safe_int(
                value
            )

            if (
                normalized is not None
                and normalized > 0
            ):

                return normalized

            return None

        # ----------------------------------------------------
        # MAPPING / SQLITE ROW
        # ----------------------------------------------------

        for key in (
            "match_id",
            "id",
        ):

            try:

                value = item[key]

                normalized = _safe_int(
                    value
                )

                if (
                    normalized is not None
                    and normalized > 0
                ):

                    return normalized

            except Exception:
                pass

        # ----------------------------------------------------
        # OBJECT
        # ----------------------------------------------------

        for attribute in (
            "match_id",
            "id",
        ):

            try:

                value = getattr(
                    item,
                    attribute,
                    None,
                )

                normalized = _safe_int(
                    value
                )

                if (
                    normalized is not None
                    and normalized > 0
                ):

                    return normalized

            except Exception:
                pass

        return None


# ============================================================
# PUBLIC API
# ============================================================

def run_etc(
    db: Optional[FAJDatabase] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Главная публичная точка запуска ETC.

    Используется:

        faj_cycle.py
        Streamlit ETC page
        ручной запуск ETC
    """

    controller = ETCController(
        db=db
    )

    return controller.run(
        limit=limit,
        force=force,
    )


def process_etc_match(
    match_id: int,
    db: Optional[FAJDatabase] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Публичная диагностическая точка
    обработки одного матча.
    """

    controller = ETCController(
        db=db
    )

    return controller.process_match(
        match_id=match_id,
        force=force,
    )


def get_etc_status(
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Read-only состояние ETC.
    """

    controller = ETCController(
        db=db
    )

    return controller.status()


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
    print("ETC Controller")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        controller = ETCController()

        print()
        print("ETC STATUS")
        print("-" * 70)

        status = controller.status()

        for key, value in status.items():

            print(
                f"{key}: {value}"
            )

        print()
        print(
            "ETC Controller готов."
        )

        print(
            "Batch state owner: "
            "BatchController"
        )

        print(
            "Analysis owner: "
            "ETCLearningEngine"
        )

        print(
            "Memory owner: "
            "LearningMemory"
        )

        print(
            "Historical facts: "
            "READ ONLY"
        )

        print(
            "Database schema: "
            "READ ONLY"
        )

        print(
            "DELETE/DROP: "
            "FORBIDDEN"
        )

    except Exception as exc:

        print(
            "ETC Controller unavailable: "
            f"{exc}"
        )

    print("=" * 70)
