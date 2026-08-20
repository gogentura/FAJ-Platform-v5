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
ETC Learning Engine — оркестратор процесса эволюционного
обучения FAJ.

ВАЖНО
-----
Это НЕ замена:

    app/learning_engine.py

Существующий FAJ Learning Engine остаётся без изменений.

ETC Learning Engine отвечает только за последовательность:

    Batch
      ↓
    Statistical Analyzer
      ↓
    Learning Memory
      ↓
    ETC Result

МОДУЛЬ НЕ:
    - изменяет database.py;
    - удаляет данные;
    - изменяет исторические результаты;
    - самостоятельно рассчитывает прогнозы;
    - самостоятельно изменяет FAJ Rating;
    - самостоятельно изменяет параметры модели.

ПРИНЦИП:

    ETC Controller
          ↓
    Statistical Analyzer
          ↓
    Learning Engine
          ↓
    Learning Memory
          ↓
    SQLite через FAJDatabase

Все изменения памяти — append-only.
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase

from app.etc.batch_controller import BatchController
from app.etc.learning_memory import LearningMemory
from app.etc.statistical_analyzer import StatisticalAnalyzer


logger = logging.getLogger(__name__)


MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Learning Engine"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


# ============================================================
# MAIN CLASS
# ============================================================

class ETCLearningEngine:
    """
    Главный оркестратор ETC.

    Он связывает:

        BatchController
        StatisticalAnalyzer
        LearningMemory

    и не вмешивается напрямую в архитектуру
    существующего app/learning_engine.py.
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
        Обрабатывает один матч через ETC.

        Метод предназначен прежде всего для диагностики
        и пошаговой обработки.

        Возвращает результат анализа.
        """

        logger.info(
            "ETC: processing match_id=%s",
            match_id,
        )

        try:

            analysis = self.analyzer.analyze_match(
                match_id=match_id
            )

        except AttributeError:

            logger.warning(
                "StatisticalAnalyzer.analyze_match() "
                "not implemented yet"
            )

            return {
                "success": False,
                "match_id": match_id,
                "status": "analyzer_not_ready",
                "created_at": _now(),
            }

        except Exception as exc:

            logger.exception(
                "ETC analysis failed for match_id=%s",
                match_id,
            )

            return {
                "success": False,
                "match_id": match_id,
                "status": "error",
                "error": str(exc),
                "created_at": _now(),
            }

        if not analysis:
            return {
                "success": False,
                "match_id": match_id,
                "status": "no_analysis",
                "created_at": _now(),
            }

        memory_ids = self._store_analysis_memory(
            match_id=match_id,
            analysis=analysis,
        )

        return {
            "success": True,
            "match_id": match_id,
            "status": "processed",
            "analysis": analysis,
            "memory_ids": memory_ids,
            "created_at": _now(),
        }

    # ========================================================
    # BATCH
    # ========================================================

    def run_batch(
        self,
        batch: Optional[List[Dict[str, Any]]] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Обрабатывает batch матчей.

        Если batch передан напрямую — используется он.

        Если batch не передан — ETC пытается получить его
        через BatchController.

        ВАЖНО:
            здесь нет DELETE;
            старые записи памяти не удаляются.
        """

        logger.info(
            "ETC: starting learning batch"
        )

        if batch is None:

            batch = self._get_batch(limit)

        if not batch:

            logger.info(
                "ETC: learning batch is empty"
            )

            return {
                "success": True,
                "status": "empty",
                "processed": 0,
                "failed": 0,
                "memory_ids": [],
                "created_at": _now(),
            }

        processed = 0
        failed = 0
        memory_ids: List[int] = []
        errors: List[Dict[str, Any]] = []

        for item in batch:

            match_id = self._extract_match_id(item)

            if match_id is None:

                failed += 1

                errors.append({
                    "item": item,
                    "error": "match_id not found",
                })

                continue

            result = self.process_match(
                match_id=match_id
            )

            if result.get("success"):

                processed += 1

                memory_ids.extend(
                    result.get("memory_ids", [])
                )

            else:

                failed += 1

                errors.append({
                    "match_id": match_id,
                    "error": result.get(
                        "error",
                        result.get("status"),
                    ),
                })

        return {
            "success": failed == 0,
            "status": "completed",
            "processed": processed,
            "failed": failed,
            "memory_ids": memory_ids,
            "errors": errors,
            "created_at": _now(),
        }

    # ========================================================
    # BATCH LOADING
    # ========================================================

    def _get_batch(
        self,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Получает batch через BatchController.

        Поддерживает несколько возможных интерфейсов,
        чтобы ETC можно было собирать постепенно.
        """

        try:

            if hasattr(
                self.batch_controller,
                "get_learning_batch",
            ):

                batch = (
                    self.batch_controller
                    .get_learning_batch(limit=limit)
                )

                return list(batch or [])

            if hasattr(
                self.batch_controller,
                "get_batch",
            ):

                batch = (
                    self.batch_controller
                    .get_batch(limit=limit)
                )

                return list(batch or [])

            if hasattr(
                self.batch_controller,
                "build_batch",
            ):

                batch = (
                    self.batch_controller
                    .build_batch(limit=limit)
                )

                return list(batch or [])

        except Exception:

            logger.exception(
                "ETC BatchController failed"
            )

            return []

        logger.warning(
            "BatchController has no supported batch method"
        )

        return []

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Dict[str, Any],
    ) -> Optional[int]:
        """
        Извлекает match_id из записи batch.
        """

        if not isinstance(item, dict):
            return None

        value = item.get("match_id")

        if value is None:
            value = item.get("id")

        if value is None:
            return None

        try:
            return int(value)

        except (TypeError, ValueError):
            return None

    # ========================================================
    # MEMORY
    # ========================================================

    def _store_analysis_memory(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[int]:
        """
        Переносит результаты анализа в learning_memory.

        Здесь сохраняются только события, которые реально
        представлены анализатором.

        Метод НЕ изменяет существующие записи.
        """

        memory_ids: List[int] = []

        events = analysis.get("memory_events")

        if events is None:

            events = []

        if not isinstance(events, list):

            events = [events]

        for event in events:

            if not isinstance(event, dict):
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
                        "v12.1",
                    ),
                    reference_id=event.get(
                        "reference_id",
                        match_id,
                    ),
                )

                memory_ids.append(
                    int(memory_id)
                )

            except Exception:

                logger.exception(
                    "Failed to store ETC memory "
                    "for match_id=%s",
                    match_id,
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
                self.batch_controller.__class__.__name__
            ),
            "analyzer": (
                self.analyzer.__class__.__name__
            ),
            "memory": (
                self.memory.__class__.__name__
            ),
            "append_only": True,
            "database_modified": False,
            "created_at": _now(),
        }


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def run_learning_batch(
    db: Optional[FAJDatabase] = None,
    batch: Optional[List[Dict[str, Any]]] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Удобная точка запуска ETC Learning Engine.
    """

    engine = ETCLearningEngine(db=db)

    return engine.run_batch(
        batch=batch,
        limit=limit,
    )


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 70)
    print("FAJ ETC — Learning Engine")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        engine = ETCLearningEngine()

        print(
            "Module:",
            engine.status()
        )

        print(
            "ETC Learning Engine готов."
        )

        print(
            "Существующий app/learning_engine.py "
            "не изменяется."
        )

        print(
            "database.py не изменяется."
        )

    except Exception as exc:

        print(
            f"ETC Learning Engine initialization error: {exc}"
        )


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================
LearningEngine = ETCLearningEngine
