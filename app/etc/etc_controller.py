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
    BatchController
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
    - изменяет календарь;
    - изменяет database.py;
    - выполняет DELETE;
    - выполняет DROP.

ETCController только:

    1. получает batch через BatchController;
    2. передаёт каждый матч в ETCLearningEngine;
    3. собирает результаты;
    4. передаёт BatchController только успешные матчи
       для закрытия batch.

ВАЖНО
------

В текущей архитектуре ETCLearningEngine уже содержит:

    StatisticalAnalyzer
    LearningMemory

Поэтому ETCController НЕ должен повторно вызывать
StatisticalAnalyzer.

Это устраняет двойной анализ одного матча.

ИДЕМПОТЕНТНОСТЬ
---------------

BatchController является владельцем состояния batch.

ETCController не хранит собственный список обработанных
матчей и не пытается самостоятельно определять,
обработан матч или нет.

force=True только передаётся BatchController.

Ошибка одного матча не должна уничтожать результаты
остальных матчей.

Только матчи, успешно прошедшие ETCLearningEngine,
передаются в mark_processed().

============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase

from app.etc.batch_controller import BatchController
from app.etc.learning_engine import LearningEngine


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.1"
MODULE_NAME = "ETC Controller"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """Текущее локальное время в ISO-формате."""
    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: Optional[int] = None,
) -> Optional[int]:
    """Безопасное преобразование в int."""
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
    """Безопасное преобразование счётчика."""
    try:
        if value is None:
            return default
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


# ============================================================
# CONTROLLER
# ============================================================

class ETCController:
    """
    Главный оркестратор ETC.

    Контроллер не содержит бизнес-математики.

    Цепочка:

        BatchController
              ↓
        ETCLearningEngine
              ↓
        StatisticalAnalyzer
              ↓
        LearningMemory
              ↓
        BatchController.mark_processed()
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        batch_controller: Optional[BatchController] = None,
        learning_engine: Optional[LearningEngine] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.batch_controller = (
            batch_controller
            or BatchController(db=self.db)
        )

        self.learning_engine = (
            learning_engine
            or LearningEngine(db=self.db)
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Read-only состояние ETC.

        Если BatchController не предоставляет
        get_pending_count(), статус всё равно остаётся
        рабочим: controller_ready.
        """

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "ready",
            "timestamp": _now(),
            "pending_matches": None,
            "batch_controller": (
                self.batch_controller.__class__.__name__
            ),
            "learning_engine": (
                self.learning_engine.__class__.__name__
            ),
        }

        try:
            get_pending_count = getattr(
                self.batch_controller,
                "get_pending_count",
                None,
            )

            if callable(get_pending_count):
                result["pending_matches"] = _safe_count(
                    get_pending_count(),
                    0,
                )

        except Exception as exc:
            logger.warning(
                "ETC status degraded: %s",
                exc,
            )
            result["status"] = "degraded"

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
        Выполняет один ETC-run.

        STEP 1:
            BatchController.create_batch()

        STEP 2:
            LearningEngine.process_match()

            Внутри него уже выполняются:
                StatisticalAnalyzer
                LearningMemory

        STEP 3:
            BatchController.mark_processed()

        ВАЖНО:

            mark_processed получает только успешные
            batch items.

        Неуспешные матчи остаются незакрытыми.
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

            "learning_events": 0,
            "memory_events": 0,

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

        try:
            # =================================================
            # STEP 1 — BUILD BATCH
            # =================================================

            logger.info(
                "ETC STEP 1/3 — BUILD BATCH"
            )

            batch = self.batch_controller.create_batch(
                limit=limit,
                force=force,
            )

            if not batch:
                result["status"] = "nothing_to_process"
                result["message"] = (
                    "Нет новых завершённых матчей для ETC."
                )
                result["finished_at"] = _now()

                logger.info(
                    "ETC RUN FINISHED — nothing to process"
                )

                return result

            result["batch_size"] = len(batch)

            logger.info(
                "ETC batch created: %s matches",
                len(batch),
            )

            # =================================================
            # STEP 2 — LEARNING ENGINE
            # =================================================

            logger.info(
                "ETC STEP 2/3 — LEARNING ENGINE"
            )

            successful_items: List[Any] = []

            for batch_item in batch:

                match_id = self._extract_match_id(
                    batch_item
                )

                if match_id is None:
                    result["errors"] += 1
                    result["failed_matches"].append(
                        {
                            "match_id": None,
                            "stage": "batch",
                            "error": (
                                "Batch item не содержит "
                                "match_id"
                            ),
                        }
                    )

                    logger.error(
                        "ETC batch item without match_id: %r",
                        batch_item,
                    )
                    continue

                try:
                    learning_result = (
                        self.learning_engine.process_match(
                            match_id=match_id
                        )
                    )

                    if not isinstance(
                        learning_result,
                        dict,
                    ):
                        raise ValueError(
                            "LearningEngine вернул не-dict"
                        )

                    if not learning_result.get(
                        "success",
                        False,
                    ):
                        raise ValueError(
                            "LearningEngine неуспешен: "
                            f"{learning_result.get('error', "
                            f"learning_result.get('status', "
                            f"'processing_failed'"))}"
                        )

                    # -----------------------------------------
                    # УСПЕШНЫЙ МАТЧ
                    # -----------------------------------------

                    successful_items.append(
                        batch_item
                    )

                    result["analyzed"] += 1
                    result["learned"] += 1

                    memory_ids = learning_result.get(
                        "memory_ids",
                        [],
                    )

                    if isinstance(memory_ids, list):
                        result["memory_events"] += len(
                            memory_ids
                        )

                    # ETCLearningEngine.process_match()
                    # в текущем контракте не создаёт
                    # отдельный learning_events counter.
                    result["learning_events"] += _safe_count(
                        learning_result.get(
                            "learning_events",
                            0,
                        ),
                        0,
                    )

                    result["processed_match_ids"].append(
                        match_id
                    )

                    logger.info(
                        "ETC learning OK: match_id=%s",
                        match_id,
                    )

                except Exception as exc:

                    result["errors"] += 1

                    result["failed_matches"].append(
                        {
                            "match_id": match_id,
                            "stage": "learning",
                            "error": str(exc),
                        }
                    )

                    logger.exception(
                        "ETC learning failed: match_id=%s",
                        match_id,
                    )

                    # -----------------------------------------
                    # ВАЖНО:
                    #
                    # Ошибка одного матча НЕ должна
                    # останавливать остальные.
                    #
                    # force не превращает ошибку в успех.
                    # -----------------------------------------

                    continue

            # =================================================
            # STEP 3 — MARK SUCCESSFULLY PROCESSED
            # =================================================

            logger.info(
                "ETC STEP 3/3 — MARK PROCESSED"
            )

            if successful_items:

                try:
                    processed = (
                        self.batch_controller.mark_processed(
                            successful_items
                        )
                    )

                    result["processed"] = _safe_count(
                        processed,
                        len(successful_items),
                    )

                except Exception as exc:

                    # ------------------------------------------------
                    # КРИТИЧЕСКО:
                    #
                    # Если mark_processed() не сработал,
                    # нельзя утверждать, что batch закрыт.
                    #
                    # Поэтому processed = 0,
                    # несмотря на успешный analysis/learning.
                    # ------------------------------------------------

                    result["processed"] = 0
                    result["errors"] += 1

                    result["failed_matches"].append(
                        {
                            "match_id": None,
                            "stage": "mark_processed",
                            "error": str(exc),
                        }
                    )

                    logger.exception(
                        "ETC mark_processed failed"
                    )

            # =================================================
            # FINAL STATUS
            # =================================================

            result["finished_at"] = _now()

            if result["errors"] == 0:

                result["status"] = "completed"
                result["message"] = (
                    "ETC успешно обработал batch."
                )

            elif result["processed"] > 0:

                result["status"] = "completed_with_errors"
                result["message"] = (
                    "ETC обработал часть batch. "
                    "Ошибочные матчи оставлены "
                    "для следующего запуска."
                )

            elif result["learned"] > 0:

                result["status"] = "completed_with_errors"
                result["message"] = (
                    "ETC выполнил анализ и обучение, "
                    "но batch не был закрыт."
                )

            else:

                result["status"] = "failed"
                result["message"] = (
                    "ETC не смог успешно обработать "
                    "ни одного матча."
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

        except Exception as exc:

            result["status"] = "failed"
            result["message"] = str(exc)
            result["finished_at"] = _now()

            logger.exception(
                "ETC RUN FAILED: %s",
                exc,
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
        Обрабатывает один матч.

        ВАЖНО:

        Этот метод НЕ вызывает StatisticalAnalyzer напрямую.

        Он делегирует весь анализ ETCLearningEngine,
        который является владельцем связки:

            StatisticalAnalyzer
                    ↓
            LearningMemory

        Метод не закрывает batch-запись автоматически.
        """

        normalized_match_id = _safe_int(match_id)

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "match_id": normalized_match_id,
            "status": "started",
            "learning": None,
            "error": None,
        }

        if normalized_match_id is None:
            result["status"] = "invalid_match_id"
            result["error"] = "Некорректный match_id"

            if force:
                return result

            raise ValueError(
                "Некорректный match_id"
            )

        try:
            learning = (
                self.learning_engine.process_match(
                    match_id=normalized_match_id
                )
            )

            result["learning"] = learning

            if not isinstance(
                learning,
                dict,
            ):
                raise ValueError(
                    "LearningEngine вернул не-dict"
                )

            if not learning.get(
                "success",
                False,
            ):
                raise ValueError(
                    "LearningEngine неуспешен: "
                    f"{learning.get('error', "
                    f"learning.get('status', "
                    f"'processing_failed'"))}"
                )

            result["status"] = "completed"

            return result

        except Exception as exc:

            result["status"] = "failed"
            result["error"] = str(exc)

            logger.exception(
                "ETC single match failed: match_id=%s",
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
        Унифицированно извлекает match_id.

        Поддерживает:

            int
            dict
            sqlite3.Row / Mapping
            object с attribute match_id
            object с attribute id
        """

        if item is None:
            return None

        if isinstance(item, int):
            return item

        if isinstance(item, dict):
            value = item.get("match_id")

            if value is None:
                value = item.get("id")

            return _safe_int(value)

        # sqlite3.Row / Mapping-like
        for key in ("match_id", "id"):
            try:
                value = item[key]
                normalized = _safe_int(value)

                if normalized is not None:
                    return normalized

            except Exception:
                pass

        # Object attributes
        for attribute in ("match_id", "id"):
            try:
                value = getattr(
                    item,
                    attribute,
                    None,
                )

                normalized = _safe_int(value)

                if normalized is not None:
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

        - faj_cycle.py
        - Streamlit ETC page
        - ручной запуск ETC
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
    Публичная точка обработки одного матча.

    Используется Match Laboratory и диагностикой.
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
    Публичная read-only точка состояния ETC.
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

        for key, value in controller.status().items():
            print(f"{key}: {value}")

    except Exception as exc:
        print(
            f"ETC controller unavailable: {exc}"
        )

    print("=" * 70)
