#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_engine.py
============================================================

ETC LEARNING ENGINE v2.1
============================================================

ИСПРАВЛЕНИЯ v2.1:
    1. Убрана самостоятельная классификация prediction error
    2. Строгий xG контракт (predicted_xg, actual_xg)
    3. Транзакционная атомарность через db.transaction()
    4. Защита от дублирования через force + get_count()
    5. Разделены memory_ids и marker_id
    6. Проверка существования match_id
    7. Поддержка force в run_batch()

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
      ├── observations (обязательно)
      ├── prediction_error (готовый от анализатора)
      ├── prediction (optional)
      ├── fact (optional)
      ├── xg (optional)
      │
      ▼
    ETC memory-event builder
      │
      ├── analysis.memory_events
      ├── analysis.observations
      ├── analysis.prediction_error (НОВОЕ)
      ├── xG data
      └── analysis_completed fallback
      │
      ▼
    LearningMemory
      │
      ▼
    batch_learning marker
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


КОНТРАКТ MATCH
--------------

Матч считается успешно обработанным ETC только если:

    1. match_id валиден;
    2. StatisticalAnalyzer успешно завершил анализ;
    3. создан хотя бы один memory event;
    4. все созданные memory events записаны;
    5. batch_learning marker успешно записан.

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

MODULE_VERSION = "2.1"
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
    Главный исполнитель ETC v2.1.

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
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Полностью обрабатывает один матч.

        НОВОЕ v2.1:
            - force: принудительная переобработка
            - транзакционная атомарность
            - разделение memory_ids и marker_id
        """

        safe_match_id = _safe_int(match_id)

        base_result: Dict[str, Any] = {
            "success": False,
            "status": "started",
            "match_id": safe_match_id,
            "analysis": None,
            "memory_ids": [],      # ← ТОЛЬКО events
            "marker_id": None,     # ← ОТДЕЛЬНО
            "learning_events": 0,
            "error": None,
            "created_at": _now(),
            "force": bool(force),
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
            "ETC match START | match_id=%s | force=%s",
            safe_match_id,
            force,
        )

        # ----------------------------------------------------
        # CHECK MATCH EXISTS
        # ----------------------------------------------------

        try:
            match = self.db._get_match(safe_match_id) if hasattr(self.db, "_get_match") else None
        except Exception:
            match = None

        if not match:
            base_result["status"] = "match_not_found"
            base_result["error"] = f"Матч {safe_match_id} не найден в БД."
            return base_result

        # ----------------------------------------------------
        # ALREADY PROCESSED (если не force)
        # ----------------------------------------------------

        if not force:
            try:
                if self._is_match_processed(safe_match_id):
                    logger.info(
                        "ETC match already processed | match_id=%s",
                        safe_match_id,
                    )
                    base_result["success"] = True
                    base_result["status"] = "already_processed"
                    return base_result
            except Exception as exc:
                logger.exception(
                    "ETC processed-state check failed | match_id=%s",
                    safe_match_id,
                )
                base_result["status"] = "processed_check_error"
                base_result["error"] = str(exc)
                return base_result

        # ----------------------------------------------------
        # GET PREDICTION, FACT, XG
        # ----------------------------------------------------

        try:
            prediction = self.db.get_latest_prediction(safe_match_id)
            fact = self.db.get_match_result(safe_match_id)
            xg = self.db.get_match_stats(safe_match_id)
        except Exception as exc:
            logger.exception("ETC data read failed | match_id=%s", safe_match_id)
            base_result["status"] = "data_read_error"
            base_result["error"] = str(exc)
            return base_result

        # ----------------------------------------------------
        # ANALYZE
        # ----------------------------------------------------

        try:
            analysis = self.analyzer.analyze_match(
                match_id=safe_match_id,
                prediction=prediction,
                fact=fact,
                xg=xg,
            )
        except Exception as exc:
            logger.exception("ETC StatisticalAnalyzer failed | match_id=%s", safe_match_id)
            base_result["status"] = "analysis_error"
            base_result["error"] = str(exc)
            return base_result

        if not analysis:
            base_result["status"] = "no_analysis"
            base_result["error"] = "StatisticalAnalyzer вернул пустой результат."
            return base_result

        if not isinstance(analysis, dict):
            base_result["status"] = "invalid_analysis"
            base_result["error"] = "StatisticalAnalyzer вернул не-dict результат."
            return base_result

        base_result["analysis"] = analysis

        if not analysis.get("success", False):
            base_result["status"] = "analysis_failed"
            base_result["error"] = analysis.get("error", analysis.get("status", "analysis_failed"))
            base_result["errors"] = analysis.get("errors", [])
            return base_result

        # ----------------------------------------------------
        # ТРАНЗАКЦИОННОЕ СОХРАНЕНИЕ
        # ----------------------------------------------------

        try:
            with self.db.transaction():
                # Проверяем processed внутри транзакции
                if not force and self._is_match_processed(safe_match_id):
                    base_result["success"] = True
                    base_result["status"] = "already_processed"
                    return base_result

                # Строим memory events
                events = self._build_memory_events(
                    match_id=safe_match_id,
                    analysis=analysis,
                )

                if not events:
                    base_result["status"] = "no_memory_events"
                    base_result["error"] = f"ETC не смог создать ни одного memory event для match_id={safe_match_id}."
                    logger.warning("ETC match %s: no memory events created", safe_match_id)
                    return base_result

                # Записываем events
                memory_ids = self._store_analysis_memory_tx(
                    match_id=safe_match_id,
                    events=events,
                )

                if not memory_ids:
                    base_result["status"] = "memory_write_failed"
                    base_result["error"] = "Не удалось записать memory events."
                    return base_result

                # Создаём marker
                marker_id = self._record_match_processing_tx(safe_match_id)

                if marker_id is None:
                    base_result["status"] = "marker_not_created"
                    base_result["error"] = "Не удалось создать batch_learning marker."
                    return base_result

                # ✅ Транзакция закоммитится автоматически при выходе из with

        except Exception as exc:
            logger.exception("ETC transaction failed | match_id=%s", safe_match_id)
            base_result["status"] = "transaction_error"
            base_result["error"] = str(exc)
            return base_result

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        base_result["success"] = True
        base_result["status"] = "processed"
        base_result["memory_ids"] = memory_ids
        base_result["marker_id"] = marker_id
        base_result["learning_events"] = len(memory_ids)

        logger.info(
            "ETC match SUCCESS | match_id=%s | events=%s | marker=%s",
            safe_match_id,
            len(memory_ids),
            marker_id,
        )

        return base_result

    # ========================================================
    # BATCH
    # ========================================================

    def run_batch(
        self,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
        batch: Optional[List[Dict[str, Any]]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Запускает один ETC batch.

        НОВОЕ v2.1:
            - force: принудительная переобработка
        """

        started_at = _now()

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC BATCH START | league=%s | season=%s | force=%s",
            league,
            season_id,
            force,
        )

        # ====================================================
        # DIRECT BATCH
        # ====================================================

        if batch is not None:
            selected_batch = list(batch)
            match_ids = []
            for item in selected_batch:
                extracted_id = self._extract_match_id(item)
                if extracted_id is not None:
                    match_ids.append(extracted_id)

            batch_check = {
                "status": "DIRECT",
                "league": league,
                "season_id": season_id,
                "required_matches": len(selected_batch),
                "new_matches": len(selected_batch),
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
                    "errors": ["Для автоматического ETC batch необходимо указать league."],
                    "created_at": _now(),
                }

            try:
                batch_check = self.batch_controller.check(league=league, season_id=season_id)
            except Exception as exc:
                logger.exception("ETC BatchController.check failed")
                return {
                    "success": False,
                    "status": "batch_controller_error",
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

            if not isinstance(batch_check, dict):
                return {
                    "success": False,
                    "status": "invalid_batch_controller_result",
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
                    "errors": ["BatchController.check() вернул не-dict."],
                    "created_at": _now(),
                }

            controller_status = batch_check.get("status")

            if controller_status != STATUS_READY:
                return {
                    "success": True,
                    "status": controller_status or "WAIT",
                    "league": batch_check.get("league", league),
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

            try:
                selected_batch = self.batch_controller.get_learning_batch(
                    league=league,
                    season_id=season_id,
                )
            except Exception as exc:
                logger.exception("ETC get_learning_batch failed")
                return {
                    "success": False,
                    "status": "batch_selection_error",
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

        normalized_batch = self._normalize_batch(selected_batch)

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
                "errors": ["Batch не содержит валидных match_id."],
                "created_at": _now(),
            }

        # ====================================================
        # STATUS MODEL (с учётом force)
        # ====================================================

        match_statuses: Dict[int, str] = {}

        for item in normalized_batch:
            match_id = self._extract_match_id(item)
            if match_id is None:
                continue

            if force:
                # При force — все матчи считаются NEW
                match_statuses[match_id] = "new"
            else:
                if self._is_match_processed(match_id):
                    match_statuses[match_id] = "already_processed"
                else:
                    match_statuses[match_id] = "new"

        new_match_ids = [mid for mid, status in match_statuses.items() if status == "new"]
        already_processed_ids = [mid for mid, status in match_statuses.items() if status == "already_processed"]

        logger.info(
            "ETC batch statuses | new=%s | already=%s | force=%s",
            len(new_match_ids),
            len(already_processed_ids),
            force,
        )

        # ====================================================
        # PROCESS NEW
        # ====================================================

        processed = 0
        already_processed = len(already_processed_ids)
        failed = 0
        learning_events = 0

        memory_ids: List[int] = []
        processed_match_ids: List[int] = []

        errors: List[Dict[str, Any]] = []

        for match_id in new_match_ids:
            try:
                match_result = self.process_match(match_id=match_id, force=force)
            except Exception as exc:
                logger.exception("ETC batch unexpected match exception | match_id=%s", match_id)
                match_result = {
                    "success": False,
                    "status": "exception",
                    "match_id": match_id,
                    "error": str(exc),
                    "memory_ids": [],
                    "marker_id": None,
                    "learning_events": 0,
                }

            if not match_result.get("success", False):
                failed += 1
                errors.append({
                    "match_id": match_id,
                    "status": match_result.get("status"),
                    "error": match_result.get("error", "processing_failed"),
                })
                logger.error("ETC batch match FAILED | match_id=%s | status=%s", match_id, match_result.get("status"))
                continue

            processed += 1
            processed_match_ids.append(match_id)

            match_learning_events = _safe_int(match_result.get("learning_events", 0), 0) or 0
            learning_events += match_learning_events

            result_memory_ids = match_result.get("memory_ids", [])
            if isinstance(result_memory_ids, list):
                memory_ids.extend(result_memory_ids)

        # ====================================================
        # BATCH COMPLETION
        # ====================================================

        total = len(normalized_batch)

        batch_completed = (
            total > 0
            and (processed + already_processed == total)
            and failed == 0
        )

        # ====================================================
        # BATCH FINGERPRINT
        # ====================================================

        batch_memory_ids: List[int] = []

        fingerprint = None
        if isinstance(batch_check, dict):
            fingerprint = batch_check.get("batch_fingerprint")

        if batch_completed and fingerprint:
            fingerprint_id = self._record_batch_fingerprint(
                league=league,
                season_id=season_id,
                fingerprint=fingerprint,
            )
            if fingerprint_id is None:
                batch_completed = False
                errors.append({
                    "match_id": None,
                    "stage": "batch_fingerprint",
                    "error": "Batch обработан, но batch fingerprint не удалось записать.",
                })
                logger.error("ETC batch completion BLOCKED | fingerprint was not recorded")
            else:
                batch_memory_ids.append(fingerprint_id)
                memory_ids.append(fingerprint_id)

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
            "processed_match_ids": processed_match_ids,
            "memory_ids": memory_ids,
            "batch_memory_ids": batch_memory_ids,
            "batch_completed": batch_completed,
            "batch_check": batch_check,
            "errors": errors,
            "started_at": started_at,
            "created_at": _now(),
            "force": force,
        }

        logger.info(
            "ETC BATCH FINISHED | status=%s | new_processed=%s | already=%s | failed=%s | total=%s | learning_events=%s | batch_memory_events=%s | force=%s",
            status,
            processed,
            already_processed,
            failed,
            total,
            learning_events,
            len(batch_memory_ids),
            force,
        )

        logger.info("==================================================")

        return result

    # ========================================================
    # NORMALIZE BATCH
    # ========================================================

    @staticmethod
    def _normalize_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Нормализует batch.
        Удаляет не-dict, элементы без match_id, дубликаты.
        """
        result: List[Dict[str, Any]] = []
        seen: Set[int] = set()

        for item in batch:
            if not isinstance(item, dict):
                continue

            match_id = ETCLearningEngine._extract_match_id(item)
            if match_id is None:
                continue

            if match_id in seen:
                continue

            seen.add(match_id)
            result.append(item)

        return result

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(item: Any) -> Optional[int]:
        """Извлекает match_id."""
        if item is None:
            return None

        if isinstance(item, int):
            return item if item > 0 else None

        if not isinstance(item, dict):
            return None

        value = item.get("match_id") or item.get("id")
        match_id = _safe_int(value)
        if match_id is None or match_id <= 0:
            return None

        return match_id

    # ========================================================
    # TX — MATCH PROCESSING MARKER
    # ========================================================

    def _record_match_processing_tx(self, match_id: int) -> Optional[int]:
        """
        Создаёт batch_learning marker (внутри транзакции).
        """
        try:
            memory_id = self.memory.record_batch_learning(
                match_id=match_id,
                reason="Матч успешно обработан ETC Learning Engine.",
                algorithm="ETC.LearningEngine",
                model_version=MODULE_VERSION,
            )

            if memory_id is None:
                raise RuntimeError("LearningMemory.record_batch_learning() не вернул memory_id.")

            return int(memory_id)

        except Exception as exc:
            logger.exception("ETC batch_learning marker failed | match_id=%s", match_id)
            raise RuntimeError(f"Не удалось создать batch_learning marker для match_id={match_id}: {exc}") from exc

    # ========================================================
    # CHECK PROCESSED
    # ========================================================

    def _is_match_processed(self, match_id: int) -> bool:
        """Проверяет наличие batch_learning marker."""
        rows = self.memory.get(event_type=PROCESSED_EVENT_TYPE, reference_id=match_id, limit=1)
        return bool(rows)

    # ========================================================
    # MEMORY EVENT BUILDER (ОСНОВНОЕ ИСПРАВЛЕНИЕ v2.1)
    # ========================================================

    def _build_memory_events(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Преобразует результат StatisticalAnalyzer v2.0 в memory events.

        Источники (в порядке приоритета):

            1. analysis["memory_events"]       — готовые события
            2. analysis["observations"]        — основной источник
            3. analysis["prediction_error"]    — готовый prediction_error (НОВОЕ)
            4. xG data                         — xg_calibration
            5. analysis_completed fallback
        """

        events: List[Dict[str, Any]] = []

        # ====================================================
        # 1. ГОТОВЫЕ MEMORY EVENTS
        # ====================================================

        existing_events = analysis.get("memory_events")
        if existing_events is not None:
            if isinstance(existing_events, list):
                for event in existing_events:
                    if isinstance(event, dict):
                        events.append(dict(event))
            elif isinstance(existing_events, dict):
                events.append(dict(existing_events))

        # ====================================================
        # 2. OBSERVATIONS (ОСНОВНОЙ ИСТОЧНИК)
        # ====================================================

        observations = analysis.get("observations", [])
        if isinstance(observations, (list, tuple)):
            for index, observation in enumerate(observations):
                event = self._observation_to_event(match_id=match_id, observation=observation, index=index)
                if event is not None:
                    events.append(event)
        elif observations:
            event = self._observation_to_event(match_id=match_id, observation=observations, index=0)
            if event is not None:
                events.append(event)

        # ====================================================
        # 3. PREDICTION ERROR (ГОТОВЫЙ ОТ АНАЛИЗАТОРА) — НОВОЕ v2.1
        # ====================================================

        prediction_error = analysis.get("prediction_error")
        if isinstance(prediction_error, dict):
            # Используем готовый prediction_error
            event = dict(prediction_error)
            event.setdefault("object_type", f"match:{match_id}")
            event.setdefault("reference_id", match_id)
            events.append(event)
            logger.info("ETC using ready prediction_error from analyzer | match_id=%s", match_id)

        # ====================================================
        # 4. XG CALIBRATION
        # ====================================================

        xg_events = self._build_xg_events(match_id=match_id, analysis=analysis)
        events.extend(xg_events)

        # ====================================================
        # 5. FALLBACK
        # ====================================================

        if not events:
            summary = analysis.get("summary", {})
            summary_text = f"match_id={match_id}, observations_count={summary.get('observations_count', 0)}"

            events.append({
                "event_type": "analysis_completed",
                "object_type": f"match:{match_id}",
                "feature": "statistical_analysis",
                "before_value": None,
                "after_value": summary_text,
                "delta": None,
                "reason": "StatisticalAnalyzer v2.0 успешно завершил анализ матча.",
                "confidence": 0.8,
                "impact": 0.1,
                "algorithm": "ETC.StatisticalAnalyzer",
                "model_version": MODULE_VERSION,
                "reference_id": match_id,
            })

            logger.info("ETC fallback event created | match_id=%s | event_type=analysis_completed", match_id)

        return events

    # ========================================================
    # OBSERVATION -> MEMORY EVENT
    # ========================================================

    def _observation_to_event(
        self,
        match_id: int,
        observation: Any,
        index: int,
    ) -> Optional[Dict[str, Any]]:
        """Преобразует observation в memory event."""
        if observation is None:
            return None

        if isinstance(observation, dict):
            event = dict(observation)
            event.setdefault("event_type", "observation")
            event.setdefault("object_type", f"match:{match_id}")
            event.setdefault("feature", _first(observation, ["feature", "type", "category", "name"], f"observation_{index + 1}"))
            event.setdefault("reason", _first(observation, ["reason", "description", "message", "observation"], ""))
            event.setdefault("confidence", _first(observation, ["confidence"], 1.0))
            event.setdefault("impact", _first(observation, ["impact"], 0.5))
            event.setdefault("algorithm", "ETC.StatisticalAnalyzer")
            event.setdefault("model_version", MODULE_VERSION)
            event.setdefault("reference_id", match_id)
            return event

        return {
            "event_type": "observation",
            "object_type": f"match:{match_id}",
            "feature": f"observation_{index + 1}",
            "before_value": None,
            "after_value": str(observation),
            "delta": None,
            "reason": str(observation),
            "confidence": 1.0,
            "impact": 0.5,
            "algorithm": "ETC.StatisticalAnalyzer",
            "model_version": MODULE_VERSION,
            "reference_id": match_id,
        }

    # ========================================================
    # XG EVENTS (СТРОГИЙ КОНТРАКТ v2.1)
    # ========================================================

    def _build_xg_events(
        self,
        match_id: int,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Создаёт xG events только если xG реально присутствует.

        НОВОЕ v2.1: строгие поля predicted_xg, actual_xg.
        """
        events: List[Dict[str, Any]] = []

        xg_data = analysis.get("xg")
        if not isinstance(xg_data, dict):
            return events

        # Строгий контракт: только predicted_xg и actual_xg
        predicted_home_xg = _safe_float(xg_data.get("predicted_home_xg"))
        predicted_away_xg = _safe_float(xg_data.get("predicted_away_xg"))
        actual_home_xg = _safe_float(xg_data.get("actual_home_xg"))
        actual_away_xg = _safe_float(xg_data.get("actual_away_xg"))

        # Home xG event
        if predicted_home_xg is not None and actual_home_xg is not None:
            deviation = predicted_home_xg - actual_home_xg
            events.append({
                "event_type": "xg_calibration",
                "object_type": f"match:{match_id}",
                "feature": "xg_home",
                "before_value": predicted_home_xg,
                "after_value": actual_home_xg,
                "delta": deviation,
                "reason": f"Home xG: predicted={predicted_home_xg:.3f}, actual={actual_home_xg:.3f}, deviation={deviation:+.3f}",
                "confidence": 0.85,
                "impact": min(1.0, abs(deviation) / 2.0),
                "algorithm": "ETC.XGCalibration",
                "model_version": MODULE_VERSION,
                "reference_id": match_id,
            })

        # Away xG event
        if predicted_away_xg is not None and actual_away_xg is not None:
            deviation = predicted_away_xg - actual_away_xg
            events.append({
                "event_type": "xg_calibration",
                "object_type": f"match:{match_id}",
                "feature": "xg_away",
                "before_value": predicted_away_xg,
                "after_value": actual_away_xg,
                "delta": deviation,
                "reason": f"Away xG: predicted={predicted_away_xg:.3f}, actual={actual_away_xg:.3f}, deviation={deviation:+.3f}",
                "confidence": 0.85,
                "impact": min(1.0, abs(deviation) / 2.0),
                "algorithm": "ETC.XGCalibration",
                "model_version": MODULE_VERSION,
                "reference_id": match_id,
            })

        return events

    # ========================================================
    # TX — STORE ANALYSIS MEMORY
    # ========================================================

    def _store_analysis_memory_tx(
        self,
        match_id: int,
        events: List[Dict[str, Any]],
    ) -> List[int]:
        """
        Сохраняет memory events (внутри транзакции).
        """
        memory_ids: List[int] = []

        for index, original_event in enumerate(events):
            if not isinstance(original_event, dict):
                raise ValueError(f"Некорректный memory event #{index} для match_id={match_id}.")

            event = dict(original_event)
            event_type = event.get("event_type", "learning_event")

            # Проверка дубликатов через count
            if event_type == "prediction_error":
                existing_count = self.memory.count(
                    event_type="prediction_error",
                    reference_id=match_id,
                )
                if existing_count > 0:
                    logger.info("prediction_error already exists for match_id=%s, skipping duplicate", match_id)
                    continue

            try:
                memory_id = self.memory.record(
                    event_type=event_type,
                    object_type=event.get("object_type", f"match:{match_id}"),
                    feature=event.get("feature", "unknown"),
                    before_value=event.get("before_value"),
                    after_value=event.get("after_value"),
                    delta=event.get("delta"),
                    reason=event.get("reason", ""),
                    confidence=event.get("confidence", 1.0),
                    impact=event.get("impact", 1.0),
                    algorithm=event.get("algorithm", "ETC.StatisticalAnalyzer"),
                    model_version=event.get("model_version", MODULE_VERSION),
                    reference_id=event.get("reference_id", match_id),
                )

                if memory_id is None:
                    raise RuntimeError("LearningMemory.record() вернул None.")

                memory_ids.append(int(memory_id))

            except Exception as exc:
                raise RuntimeError(f"Ошибка записи analysis memory event #{index} для match_id={match_id}: {exc}") from exc

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
        """Записывает fingerprint полностью завершённого batch."""
        if not fingerprint:
            return None

        try:
            memory_id = self.memory.record(
                event_type=PROCESSED_EVENT_TYPE,
                object_type=f"league:{league or 'unknown'}",
                feature="batch_fingerprint",
                before_value=None,
                after_value=fingerprint,
                delta=None,
                reason="ETC batch полностью и успешно обработан.",
                confidence=1.0,
                impact=0.0,
                algorithm="ETC.LearningEngine",
                model_version=MODULE_VERSION,
                reference_id=None,
            )

            if memory_id is None:
                raise RuntimeError("LearningMemory.record() не вернул memory_id для batch fingerprint.")

            return int(memory_id)

        except Exception as exc:
            logger.exception("ETC batch fingerprint write failed | league=%s | season=%s", league, season_id)
            return None

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """Read-only состояние ETC Learning Engine."""
        return {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "database": "FAJDatabase",
            "batch_controller": self.batch_controller.__class__.__name__,
            "analyzer": self.analyzer.__class__.__name__,
            "memory": self.memory.__class__.__name__,
            "append_only": True,
            "batch_controller_is_authority": True,
            "processed_marker": PROCESSED_EVENT_TYPE,
            "analysis_method": "process_match",
            "compatibility_method": "process_analysis",
            "memory_event_sources": [
                "analysis.memory_events",
                "analysis.observations",
                "analysis.prediction_error",
                "xg_data",
                "analysis_completed (fallback)",
            ],
            "historical_facts_modified": False,
            "model_parameters_modified": False,
            "faj_rating_modified": False,
            "predictions_modified": False,
            "calendar_modified": False,
            "delete_operations": False,
            "drop_operations": False,
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
    force: bool = False,
) -> Dict[str, Any]:
    """
    Официальная точка запуска ETC batch.
    """
    engine = ETCLearningEngine(db=db)
    return engine.run_batch(
        league=league,
        season_id=season_id,
        batch=batch,
        force=force,
    )


def process_learning_match(
    match_id: int,
    db: Optional[FAJDatabase] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Публичная точка обработки одного матча.
    """
    engine = ETCLearningEngine(db=db)
    return engine.process_match(match_id=match_id, force=force)


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

LearningEngine = ETCLearningEngine


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

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
            print(f"{key}: {value}")

        print()
        print("ETCLearningEngine v2.1 готов.")
        print()
        print("НОВОЕ В v2.1:")
        print("1. Убрана самостоятельная классификация prediction error")
        print("2. Строгий xG контракт (predicted_xg, actual_xg)")
        print("3. Транзакционная атомарность через db.transaction()")
        print("4. Защита от дублирования через force + count()")
        print("5. Разделены memory_ids и marker_id")
        print("6. Проверка существования match_id")
        print("7. Поддержка force в run_batch()")

    except Exception as exc:
        print(f"ETC Learning Engine initialization error: {exc}")

    print("=" * 70)
