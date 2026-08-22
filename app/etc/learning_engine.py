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

ETC Learning Engine — оркестратор пакетного процесса
эволюционного обучения FAJ.

АРХИТЕКТУРА:

    FACTS
      │
      ▼
    BatchController
      │
      │ READY
      ▼
    select_batch()
      │
      ▼
    StatisticalAnalyzer
      │
      ▼
    ETC Learning Engine
      │
      ├── анализ фактов
      │
      ├── фиксация ETC memory
      │
      └── фиксация batch processing
      │
      ▼
    LearningMemory
      │
      ▼
    SQLite / FAJDatabase


ВАЖНО
-----

Этот модуль НЕ является заменой:

    app/learning_engine.py

Существующий FAJ Learning Engine НЕ изменяется.

ETC Learning Engine отвечает только за ETC-оркестрацию.


МОДУЛЬ НЕ:

    - изменяет database.py;
    - удаляет данные;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет исторические факты;
    - самостоятельно рассчитывает прогнозы;
    - самостоятельно рассчитывает xG;
    - самостоятельно изменяет FAJ Rating;
    - самостоятельно изменяет model_parameters;
    - выполняет DELETE;
    - выполняет DROP.


МОДУЛЬ:

    - получает готовый батч через BatchController;
    - передаёт матчи StatisticalAnalyzer;
    - получает объективный статистический анализ;
    - сохраняет только переданные ETC memory events;
    - фиксирует обработанные матчи в learning_memory;
    - возвращает результат ETC.


ПРИНЦИП ПАМЯТИ:

    learning_memory = APPEND ONLY

Существующие записи не удаляются
и не переписываются.


ЦИКЛ:

    MATCH
      ↓
    FACTS
      ↓
    BatchController
      ↓
    READY
      ↓
    select_batch()
      ↓
    StatisticalAnalyzer
      ↓
    ETCLearningEngine
      ↓
    LearningMemory
      ↓
    NEXT BATCH


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


MODULE_VERSION = "1.1"
MODULE_NAME = "ETC Learning Engine"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает текущее время в ISO формате.
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

    Отвечает только за последовательность:

        BatchController
              ↓
        StatisticalAnalyzer
              ↓
        LearningMemory

    Никакого самостоятельного обучения модели здесь нет.
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

        Используется для:

            - диагностики;
            - пошаговой обработки;
            - тестирования ETC.

        ВАЖНО:

        Сам анализ не означает изменение модели.

        StatisticalAnalyzer только читает FACTS.
        """

        match_id = _safe_int(match_id)

        if match_id is None:

            return {
                "success": False,
                "status": "invalid_match_id",
                "match_id": None,
                "created_at": _now(),
            }

        logger.info(
            "ETC: processing match_id=%s",
            match_id,
        )

        # ----------------------------------------------------
        # ANALYZE
        # ----------------------------------------------------

        try:

            analysis = self.analyzer.analyze_match(
                match_id=match_id
            )

        except Exception as exc:

            logger.exception(
                "ETC analysis failed for match_id=%s",
                match_id,
            )

            return {
                "success": False,
                "status": "analysis_error",
                "match_id": match_id,
                "error": str(exc),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # ANALYZER RESULT
        # ----------------------------------------------------

        if not analysis:

            return {
                "success": False,
                "status": "no_analysis",
                "match_id": match_id,
                "created_at": _now(),
            }

        if not analysis.get("success", False):

            return {
                "success": False,
                "status": "analysis_failed",
                "match_id": match_id,
                "analysis": analysis,
                "errors": analysis.get(
                    "errors",
                    [],
                ),
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # STORE MEMORY EVENTS
        # ----------------------------------------------------

        memory_ids = self._store_analysis_memory(
            match_id=match_id,
            analysis=analysis,
        )

        return {
            "success": True,
            "status": "processed",
            "match_id": match_id,
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
        batch: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Запускает один ETC batch.

        Варианты:

        1. batch передан напрямую:

            run_batch(batch=[...])

        2. batch не передан:

            требуется league.

            BatchController сам определяет:

                READY
                WAIT
                UNKNOWN_LEAGUE
                ALREADY_PROCESSED

            и при READY возвращает select_batch().

        ВАЖНО:

            Метод НЕ запускает app/learning_engine.py.

            Это только ETC analysis / memory stage.
        """

        started_at = _now()

        logger.info(
            "ETC: starting batch"
        )

        # ----------------------------------------------------
        # DIRECT BATCH
        # ----------------------------------------------------

        if batch is not None:

            selected_batch = list(batch)

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
                    _safe_int(item.get("id"))
                    for item in selected_batch
                    if isinstance(item, dict)
                    and _safe_int(item.get("id")) is not None
                ],
            }

        # ----------------------------------------------------
        # CONTROLLER BATCH
        # ----------------------------------------------------

        else:

            if not league:

                return {
                    "success": False,
                    "status": "league_required",
                    "processed": 0,
                    "failed": 0,
                    "memory_ids": [],
                    "errors": [
                        "Для автоматического batch "
                        "необходимо указать league."
                    ],
                    "created_at": started_at,
                }

            try:

                batch_check = self.batch_controller.check(
                    league=league,
                    season_id=season_id,
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
                    "errors": [str(exc)],
                    "created_at": _now(),
                }

            # ------------------------------------------------
            # BATCH NOT READY
            # ------------------------------------------------

            if batch_check.get("status") != "READY":

                return {
                    "success": True,
                    "status": batch_check.get(
                        "status",
                        "WAIT",
                    ),
                    "league": batch_check.get(
                        "league",
                        league,
                    ),
                    "season_id": season_id,
                    "processed": 0,
                    "failed": 0,
                    "memory_ids": [],
                    "batch_check": batch_check,
                    "errors": [],
                    "created_at": _now(),
                }

            # ------------------------------------------------
            # SELECT EXACT BATCH
            # ------------------------------------------------

            try:

                selected_batch = (
                    self.batch_controller.select_batch(
                        league=league,
                        season_id=season_id,
                    )
                )

            except Exception as exc:

                logger.exception(
                    "ETC batch selection failed"
                )

                return {
                    "success": False,
                    "status": "batch_selection_error",
                    "processed": 0,
                    "failed": 0,
                    "memory_ids": [],
                    "batch_check": batch_check,
                    "errors": [str(exc)],
                    "created_at": _now(),
                }

        # ----------------------------------------------------
        # EMPTY
        # ----------------------------------------------------

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
                "batch_check": batch_check,
                "errors": [],
                "created_at": _now(),
            }

        # ----------------------------------------------------
        # LIMIT SAFETY
        # ----------------------------------------------------

        if len(selected_batch) > 100:

            selected_batch = selected_batch[:100]

            logger.warning(
                "ETC batch limited to 100 matches"
            )

        # ----------------------------------------------------
        # PROCESS MATCHES
        # ----------------------------------------------------

        processed = 0
        failed = 0

        memory_ids: List[int] = []

        errors: List[Dict[str, Any]] = []

        processed_match_ids: List[int] = []

        for item in selected_batch:

            match_id = self._extract_match_id(item)

            if match_id is None:

                failed += 1

                errors.append(
                    {
                        "item": item,
                        "error": "match_id not found",
                    }
                )

                continue

            result = self.process_match(
                match_id=match_id
            )

            if result.get("success"):

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

            else:

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

        # ----------------------------------------------------
        # BATCH MEMORY
        # ----------------------------------------------------

        batch_memory_ids = (
            self._record_batch_processing(
                league=league,
                season_id=season_id,
                batch_check=batch_check,
                processed_match_ids=processed_match_ids,
            )
        )

        memory_ids.extend(
            batch_memory_ids
        )

        # ----------------------------------------------------
        # FINAL STATUS
        # ----------------------------------------------------

        if failed == 0:

            status = "completed"

        elif processed > 0:

            status = "partial"

        else:

            status = "failed"

        logger.info(
            "ETC batch finished: "
            "status=%s processed=%s failed=%s",
            status,
            processed,
            failed,
        )

        return {
            "success": failed == 0,
            "status": status,
            "league": league,
            "season_id": season_id,
            "processed": processed,
            "failed": failed,
            "processed_match_ids": processed_match_ids,
            "memory_ids": memory_ids,
            "batch_memory_ids": batch_memory_ids,
            "batch_check": batch_check,
            "errors": errors,
            "created_at": _now(),
        }

    # ========================================================
    # BATCH PROCESSING MEMORY
    # ========================================================

    def _record_batch_processing(
        self,
        league: Optional[str],
        season_id: Optional[int],
        batch_check: Dict[str, Any],
        processed_match_ids: List[int],
    ) -> List[int]:
        """
        Фиксирует факт обработки матчей ETC.

        Это необходимо BatchController для защиты
        от повторной обработки.

        ВАЖНО:

            это НЕ изменение модели.

        Это только журнал:

            "этот матч уже прошёл ETC batch".

        Записи append-only.
        """

        memory_ids: List[int] = []

        if not processed_match_ids:
            return memory_ids

        fingerprint = batch_check.get(
            "batch_fingerprint"
        )

        for match_id in processed_match_ids:

            try:

                memory_id = self.memory.record(
                    event_type="batch_learning",
                    object_type=(
                        f"match:{match_id}"
                    ),
                    feature="etc_batch_processed",
                    before_value=None,
                    after_value="processed",
                    delta=None,
                    reason=(
                        "Матч обработан ETC "
                        "в рамках пакетного анализа."
                    ),
                    confidence=1.0,
                    impact=0.0,
                    algorithm="ETC.LearningEngine",
                    model_version=MODULE_VERSION,
                    reference_id=match_id,
                )

                memory_ids.append(
                    int(memory_id)
                )

            except Exception:

                logger.exception(
                    "Failed to record ETC batch "
                    "processing for match_id=%s",
                    match_id,
                )

        # ----------------------------------------------------
        # BATCH FINGERPRINT EVENT
        # ----------------------------------------------------

        if fingerprint:

            try:

                memory_id = self.memory.record(
                    event_type="batch_learning",
                    object_type=(
                        f"league:{league or 'unknown'}"
                    ),
                    feature="batch_fingerprint",
                    before_value=None,
                    after_value=fingerprint,
                    delta=None,
                    reason=(
                        "ETC batch успешно обработан."
                    ),
                    confidence=1.0,
                    impact=0.0,
                    algorithm="ETC.BatchController",
                    model_version=MODULE_VERSION,
                    reference_id=None,
                )

                memory_ids.append(
                    int(memory_id)
                )

            except Exception:

                logger.exception(
                    "Failed to record ETC batch fingerprint"
                )

        return memory_ids

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Dict[str, Any],
    ) -> Optional[int]:
        """
        Извлекает ID матча из batch item.
        """

        if not isinstance(item, dict):

            return None

        value = item.get("match_id")

        if value is None:

            value = item.get("id")

        return _safe_int(value)

    # ========================================================
    # MEMORY
    # ========================================================

    def _store_analysis_memory(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[int]:
        """
        Сохраняет memory_events, если их сформировал
        StatisticalAnalyzer или следующий ETC-анализатор.

        В текущей архитектуре StatisticalAnalyzer
        не обязан изменять память.

        Поэтому отсутствие memory_events — НОРМАЛЬНО.
        """

        memory_ids: List[int] = []

        events = analysis.get(
            "memory_events"
        )

        if events is None:

            return memory_ids

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
    batch: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Удобная точка запуска ETC.

    Автоматический режим:

        run_learning_batch(
            db=db,
            league="РПЛ",
            season_id=...
        )

    Ручной режим:

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

        print(
            "Module:",
            engine.status()
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
            "app/learning_engine.py НЕ изменяется."
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
            f"ETC Learning Engine initialization error: {exc}"
        )
