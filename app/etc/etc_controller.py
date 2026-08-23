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

АКТУАЛЬНАЯ АРХИТЕКТУРА:

    MATCH
      ↓
    IMPORT FACTS
      ↓
    match_results / match_statistics
      ↓
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
       ETCLearningEngine.run_batch()
              │
              ▼
       StatisticalAnalyzer
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


ВАЖНО
------

Контроллер согласован с РЕАЛЬНЫМ API:

BatchController:

    check()
    get_learning_batch()

ETCLearningEngine:

    process_match()
    run_batch()

НЕ ИСПОЛЬЗУЮТСЯ:

    create_batch()
    mark_processed()

Эти методы отсутствуют в текущем контракте
BatchController и не должны искусственно добавляться.


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

    1. получает решение BatchController;
    2. при READY получает batch;
    3. передаёт выполнение ETCLearningEngine;
    4. возвращает единый результат ETC.

ВАЖНО
------

ETCLearningEngine является владельцем процесса:

    StatisticalAnalyzer
        ↓
    analysis memory
        ↓
    batch_learning
        ↓
    LearningMemory

Поэтому ETCController НЕ должен повторно
вызывать StatisticalAnalyzer.

Также ETCController НЕ должен самостоятельно
создавать batch_learning и НЕ должен самостоятельно
помечать матч обработанным.

ИДЕМПОТЕНТНОСТЬ
---------------

BatchController является владельцем решения:

    READY / WAIT / ALREADY_PROCESSED

ETCLearningEngine является владельцем факта:

    batch_learning

ETCController не хранит собственный список
обработанных матчей.


============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase

from app.etc.batch_controller import (
    BatchController,
    STATUS_READY,
    STATUS_WAIT,
    STATUS_ALREADY_PROCESSED,
    STATUS_UNKNOWN_LEAGUE,
    BATCH_RULES,
)

from app.etc.learning_engine import (
    ETCLearningEngine,
)


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.2"
MODULE_NAME = "ETC Controller"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Текущее локальное время в ISO-формате.
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


def _safe_count(
    value: Any,
    default: int = 0,
) -> int:
    """
    Безопасное преобразование счётчика.
    """

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

    АКТУАЛЬНАЯ ЦЕПОЧКА:

        BatchController.check()
                ↓
        get_learning_batch()
                ↓
        ETCLearningEngine.run_batch()
                ↓
        StatisticalAnalyzer
                ↓
        LearningMemory

    ETCController не содержит бизнес-математики.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
        batch_controller: Optional[BatchController] = None,
        learning_engine: Optional[ETCLearningEngine] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.batch_controller = (
            batch_controller
            or BatchController(
                db=self.db
            )
        )

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
        """

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "ready",
            "timestamp": _now(),

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

            "api_contract": {
                "batch_check": hasattr(
                    self.batch_controller,
                    "check",
                ),

                "batch_get_learning_batch": hasattr(
                    self.batch_controller,
                    "get_learning_batch",
                ),

                "learning_run_batch": hasattr(
                    self.learning_engine,
                    "run_batch",
                ),

                "learning_process_match": hasattr(
                    self.learning_engine,
                    "process_match",
                ),
            },

            "legacy_api_used": False,

            "forbidden_methods": [
                "create_batch",
                "mark_processed",
            ],
        }

        # ----------------------------------------------------
        # Проверяем только наличие реального API.
        # Никаких изменений БД.
        # ----------------------------------------------------

        required_methods = [
            (
                "BatchController.check",
                getattr(
                    self.batch_controller,
                    "check",
                    None,
                ),
            ),
            (
                "BatchController.get_learning_batch",
                getattr(
                    self.batch_controller,
                    "get_learning_batch",
                    None,
                ),
            ),
            (
                "ETCLearningEngine.run_batch",
                getattr(
                    self.learning_engine,
                    "run_batch",
                    None,
                ),
            ),
            (
                "ETCLearningEngine.process_match",
                getattr(
                    self.learning_engine,
                    "process_match",
                    None,
                ),
            ),
        ]

        missing = [
            name
            for name, method in required_methods
            if not callable(method)
        ]

        if missing:

            result["status"] = "degraded"

            result["missing_api"] = missing

        else:

            result["missing_api"] = []

        return result

    # ========================================================
    # RUN
    # ========================================================

    def run(
        self,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Выполняет ETC.

        Если league указан:

            проверяется только этот турнир.

        Если league=None:

            ETC последовательно проверяет все турниры,
            для которых существуют правила BATCH_RULES.

        force НЕ изменяет архитектурное решение
        BatchController.

        Он только передаётся в результат как
        диагностический флаг и не превращает WAIT
        или ошибку в успех.
        """

        started_at = _now()

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "status": "started",

            "started_at": started_at,
            "finished_at": None,

            "league": league,
            "season_id": season_id,
            "force": bool(force),

            "leagues_checked": [],

            "batch_size": 0,
            "analyzed": 0,
            "learned": 0,
            "processed": 0,

            "learning_events": 0,
            "memory_events": 0,

            "errors": 0,

            "failed_matches": [],
            "processed_match_ids": [],

            "batches": [],

            "message": "",
        }

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC RUN STARTED | "
            "league=%s | season=%s | limit=%s | force=%s",
            league,
            season_id,
            limit,
            force,
        )

        try:

            # =================================================
            # API VALIDATION
            # =================================================

            api_status = self.status()

            if api_status.get("status") == "degraded":

                result["status"] = "failed"

                result["errors"] += 1

                result["message"] = (
                    "ETC API contract is incomplete: "
                    f"{api_status.get('missing_api', [])}"
                )

                result["finished_at"] = _now()

                return result

            # =================================================
            # LEAGUES
            # =================================================

            if league:

                leagues = [league]

            else:

                leagues = list(
                    BATCH_RULES.keys()
                )

            if not leagues:

                result["status"] = "failed"
                result["errors"] += 1
                result["message"] = (
                    "Не определён ни один турнир ETC."
                )
                result["finished_at"] = _now()

                return result

            # =================================================
            # PROCESS EACH LEAGUE
            # =================================================

            for current_league in leagues:

                result["leagues_checked"].append(
                    current_league
                )

                league_result = self._run_league(
                    league=current_league,
                    season_id=season_id,
                    limit=limit,
                    force=force,
                )

                result["batches"].append(
                    league_result
                )

                # ------------------------------------------------
                # Aggregate counters
                # ------------------------------------------------

                result["batch_size"] += _safe_count(
                    league_result.get(
                        "batch_size",
                        0,
                    )
                )

                result["analyzed"] += _safe_count(
                    league_result.get(
                        "analyzed",
                        0,
                    )
                )

                result["learned"] += _safe_count(
                    league_result.get(
                        "learned",
                        0,
                    )
                )

                result["processed"] += _safe_count(
                    league_result.get(
                        "processed",
                        0,
                    )
                )

                result["learning_events"] += _safe_count(
                    league_result.get(
                        "learning_events",
                        0,
                    )
                )

                result["memory_events"] += _safe_count(
                    league_result.get(
                        "memory_events",
                        0,
                    )
                )

                result["errors"] += _safe_count(
                    league_result.get(
                        "errors",
                        0,
                    )
                )

                result["processed_match_ids"].extend(
                    league_result.get(
                        "processed_match_ids",
                        [],
                    )
                )

                result["failed_matches"].extend(
                    league_result.get(
                        "failed_matches",
                        [],
                    )
                )

            # =================================================
            # FINAL STATUS
            # =================================================

            result["finished_at"] = _now()

            statuses = [
                batch.get(
                    "status"
                )
                for batch in result["batches"]
            ]

            successful = [
                status == "completed"
                for status in statuses
            ]

            has_processing = (
                result["processed"] > 0
            )

            has_errors = (
                result["errors"] > 0
            )

            # -------------------------------------------------
            # NOTHING READY
            # -------------------------------------------------

            if all(
                status in {
                    STATUS_WAIT,
                    STATUS_ALREADY_PROCESSED,
                    STATUS_UNKNOWN_LEAGUE,
                    "nothing_to_process",
                    "empty",
                }
                for status in statuses
            ):

                result["status"] = "nothing_to_process"

                result["message"] = (
                    "Нет готового ETC batch."
                )

            # -------------------------------------------------
            # ALL COMPLETED
            # -------------------------------------------------

            elif all(successful):

                result["status"] = "completed"

                result["message"] = (
                    "ETC успешно завершил "
                    "готовые batch."
                )

            # -------------------------------------------------
            # PARTIAL
            # -------------------------------------------------

            elif has_processing:

                result["status"] = (
                    "completed_with_errors"
                )

                result["message"] = (
                    "ETC обработал доступные batch "
                    "частично или с ошибками."
                )

            # -------------------------------------------------
            # FAILED
            # -------------------------------------------------

            else:

                result["status"] = "failed"

                result["message"] = (
                    "ETC не смог успешно обработать "
                    "готовый batch."
                )

            logger.info(
                "ETC RUN FINISHED | "
                "status=%s | "
                "processed=%s | "
                "errors=%s",
                result["status"],
                result["processed"],
                result["errors"],
            )

            logger.info(
                "=================================================="
            )

            return result

        except Exception as exc:

            result["status"] = "failed"

            result["errors"] += 1

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
    # SINGLE LEAGUE
    # ========================================================

    def _run_league(
        self,
        league: str,
        season_id: Optional[int],
        limit: Optional[int],
        force: bool,
    ) -> Dict[str, Any]:
        """
        Выполняет один ETC batch для одного турнира.

        КРИТИЧЕСКИЙ КОНТРАК:

            check()
                ↓
            READY
                ↓
            get_learning_batch()
                ↓
            learning_engine.run_batch()

        ETCController не создаёт batch самостоятельно.
        """

        result: Dict[str, Any] = {
            "league": league,
            "season_id": season_id,

            "status": "started",

            "batch_size": 0,
            "analyzed": 0,
            "learned": 0,
            "processed": 0,

            "learning_events": 0,
            "memory_events": 0,

            "errors": 0,

            "failed_matches": [],
            "processed_match_ids": [],

            "batch_check": None,
            "selected_match_ids": [],

            "learning_result": None,

            "message": "",
        }

        # =====================================================
        # STEP 1 — CHECK
        # =====================================================

        logger.info(
            "ETC [%s] STEP 1 — BatchController.check()",
            league,
        )

        try:

            batch_check = (
                self.batch_controller.check(
                    league=league,
                    season_id=season_id,
                )
            )

            result["batch_check"] = batch_check

        except Exception as exc:

            result["status"] = "failed"
            result["errors"] = 1
            result["message"] = str(exc)

            logger.exception(
                "ETC BatchController.check failed | "
                "league=%s",
                league,
            )

            return result

        controller_status = batch_check.get(
            "status"
        )

        # =====================================================
        # NOT READY
        # =====================================================

        if controller_status != STATUS_READY:

            result["status"] = (
                controller_status
                or STATUS_WAIT
            )

            result["message"] = (
                batch_check.get(
                    "reason",
                    "Batch не готов.",
                )
            )

            logger.info(
                "ETC [%s] batch status: %s | %s",
                league,
                result["status"],
                result["message"],
            )

            return result

        # =====================================================
        # STEP 2 — GET BATCH
        # =====================================================

        logger.info(
            "ETC [%s] STEP 2 — "
            "BatchController.get_learning_batch()",
            league,
        )

        try:

            selected_batch = (
                self.batch_controller
                .get_learning_batch(
                    league=league,
                    season_id=season_id,
                    limit=limit,
                )
            )

        except Exception as exc:

            result["status"] = "failed"
            result["errors"] = 1
            result["message"] = str(exc)

            logger.exception(
                "ETC get_learning_batch failed | "
                "league=%s",
                league,
            )

            return result

        if not selected_batch:

            result["status"] = "empty"

            result["message"] = (
                "BatchController сообщил READY, "
                "но get_learning_batch() вернул пустой batch."
            )

            result["errors"] = 1

            logger.error(
                "ETC CONTRACT ERROR | "
                "READY but empty batch | league=%s",
                league,
            )

            return result

        result["batch_size"] = len(
            selected_batch
        )

        result["selected_match_ids"] = [
            self._extract_match_id(item)
            for item in selected_batch
            if self._extract_match_id(item)
            is not None
        ]

        logger.info(
            "ETC [%s] batch selected | "
            "size=%s | matches=%s",
            league,
            len(selected_batch),
            result["selected_match_ids"],
        )

        # =====================================================
        # STEP 3 — LEARNING ENGINE
        # =====================================================

        logger.info(
            "ETC [%s] STEP 3 — "
            "ETCLearningEngine.run_batch()",
            league,
        )

        try:

            learning_result = (
                self.learning_engine.run_batch(
                    league=league,
                    season_id=season_id,
                    batch=selected_batch,
                )
            )

            result["learning_result"] = (
                learning_result
            )

        except Exception as exc:

            result["status"] = "failed"
            result["errors"] = 1
            result["message"] = str(exc)

            logger.exception(
                "ETC LearningEngine.run_batch failed | "
                "league=%s",
                league,
            )

            return result

        # =====================================================
        # AGGREGATE LEARNING RESULT
        # =====================================================

        result["analyzed"] = _safe_count(
            learning_result.get(
                "processed",
                0,
            )
        )

        result["learned"] = _safe_count(
            learning_result.get(
                "processed",
                0,
            )
        )

        result["processed"] = _safe_count(
            learning_result.get(
                "processed",
                0,
            )
        )

        result["memory_events"] = len(
            learning_result.get(
                "memory_ids",
                [],
            )
            or []
        )

        result["learning_events"] = _safe_count(
            learning_result.get(
                "learning_events",
                0,
            )
        )

        result["processed_match_ids"] = (
            learning_result.get(
                "processed_match_ids",
                [],
            )
            or []
        )

        learning_errors = (
            learning_result.get(
                "errors",
                [],
            )
            or []
        )

        result["errors"] = len(
            learning_errors
        )

        # =====================================================
        # FAILED MATCHES
        # =====================================================

        for error in learning_errors:

            if isinstance(
                error,
                dict,
            ):

                result["failed_matches"].append(
                    error
                )

            else:

                result["failed_matches"].append(
                    {
                        "match_id": None,
                        "stage": "learning",
                        "error": str(error),
                    }
                )

        # =====================================================
        # FINAL LEAGUE STATUS
        # =====================================================

        learning_status = learning_result.get(
            "status"
        )

        if learning_status == "completed":

            result["status"] = "completed"

            result["message"] = (
                "ETC batch полностью "
                "обработан."
            )

        elif learning_status == "partial":

            result["status"] = "partial"

            result["message"] = (
                "ETC batch обработан частично. "
                "Неуспешные матчи не считаются "
                "успешно закрытыми."
            )

        elif learning_status in {
            "WAIT",
            "ALREADY_PROCESSED",
            "UNKNOWN_LEAGUE",
        }:

            result["status"] = learning_status

            result["message"] = (
                learning_result.get(
                    "message",
                    learning_status,
                )
            )

        elif learning_status == "empty":

            result["status"] = "empty"

            result["message"] = (
                "Learning Engine получил "
                "пустой batch."
            )

        else:

            result["status"] = (
                "failed"
            )

            if not result["message"]:

                result["message"] = (
                    learning_result.get(
                        "errors",
                        learning_result.get(
                            "status",
                            "ETC learning failed.",
                        ),
                    )
                )

        logger.info(
            "ETC [%s] FINISHED | "
            "status=%s | "
            "processed=%s | "
            "errors=%s",
            league,
            result["status"],
            result["processed"],
            result["errors"],
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

        Использует только:

            ETCLearningEngine.process_match()

        Никакого прямого обращения
        к StatisticalAnalyzer.

        ВАЖНО:

        process_match() является диагностическим
        single-match режимом.

        Он НЕ является batch commit.
        """

        normalized_match_id = _safe_int(
            match_id
        )

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "match_id": normalized_match_id,

            "status": "started",

            "learning": None,
            "error": None,

            "force": bool(force),
        }

        if (
            normalized_match_id is None
            or normalized_match_id <= 0
        ):

            result["status"] = (
                "invalid_match_id"
            )

            result["error"] = (
                "Некорректный match_id."
            )

            if force:
                return result

            raise ValueError(
                "Некорректный match_id."
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
                    "LearningEngine вернул "
                    "не-dict."
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

            result["status"] = (
                "completed"
            )

            return result

        except Exception as exc:

            result["status"] = "failed"

            result["error"] = str(exc)

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
        Унифицированно извлекает match_id.

        Поддерживает:

            int
            dict
            sqlite3.Row / Mapping
            object.match_id
            object.id
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
        # Mapping / sqlite3.Row
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
        # Object attributes
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
    league: Optional[str] = None,
    season_id: Optional[int] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Главная публичная точка запуска ETC.

    Пример:

        run_etc(
            db=db,
            league="РПЛ",
            season_id=1,
        )

    Если league не указан,
    ETC последовательно проверит все турниры
    из BATCH_RULES.
    """

    controller = ETCController(
        db=db
    )

    return controller.run(
        league=league,
        season_id=season_id,
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
            "BatchController API:"
        )

        print(
            "  check()"
        )

        print(
            "  get_learning_batch()"
        )

        print(
            "LearningEngine API:"
        )

        print(
            "  process_match()"
        )

        print(
            "  run_batch()"
        )

        print()
        print(
            "create_batch() НЕ используется."
        )

        print(
            "mark_processed() НЕ используется."
        )

        print(
            "LearningMemory остаётся "
            "единственным механизмом записи памяти."
        )

    except Exception as exc:

        print(
            "ETC Controller unavailable: "
            f"{exc}"
        )

    print("=" * 70)
