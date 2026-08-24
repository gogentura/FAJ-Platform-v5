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

Контракт:

    MATCH
      ↓
    IMPORT FACTS
      ↓
    SQLite
      ↓
    BatchController
      ↓
    READY / WAIT / ALREADY_PROCESSED /
    UNKNOWN_LEAGUE
      ↓
    get_learning_batch()
      ↓
    ETCLearningEngine.run_batch()
      ↓
    StatisticalAnalyzer
      ↓
    LearningMemory
      ↓
    SQLite

ГРАНИЦЫ ETCController:

    НЕ:
        - считает xG;
        - считает прогноз;
        - изменяет match_results;
        - изменяет match_statistics;
        - изменяет календарь;
        - изменяет predictions;
        - изменяет model_parameters;
        - пишет learning_memory напрямую;
        - выполняет DELETE;
        - выполняет DROP.

    ДЕЛАЕТ:
        1. вызывает BatchController.check();
        2. при READY получает get_learning_batch();
        3. передаёт batch ETCLearningEngine;
        4. агрегирует диагностический результат.

ЕДИНСТВЕННЫЕ API:

BatchController:
    check()
    get_learning_batch()

ETCLearningEngine:
    process_match()
    run_batch()

Старые:
    create_batch()
    mark_processed()

НЕ ИСПОЛЬЗУЮТСЯ.
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

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

MODULE_NAME = "ETC Controller"
MODULE_VERSION = "2.3"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
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

    ETCController НЕ содержит математической логики.
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
        Read-only проверка ETC API.
        """

        required = {
            "BatchController.check": getattr(
                self.batch_controller,
                "check",
                None,
            ),
            "BatchController.get_learning_batch": getattr(
                self.batch_controller,
                "get_learning_batch",
                None,
            ),
            "ETCLearningEngine.run_batch": getattr(
                self.learning_engine,
                "run_batch",
                None,
            ),
            "ETCLearningEngine.process_match": getattr(
                self.learning_engine,
                "process_match",
                None,
            ),
        }

        missing = [
            name
            for name, method in required.items()
            if not callable(method)
        ]

        return {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": (
                "ready"
                if not missing
                else "degraded"
            ),
            "timestamp": _now(),

            "batch_controller": (
                self.batch_controller.__class__.__name__
            ),

            "learning_engine": (
                self.learning_engine.__class__.__name__
            ),

            "api_contract": {
                name: callable(method)
                for name, method in required.items()
            },

            "legacy_api_used": False,

            "forbidden_methods": [
                "create_batch",
                "mark_processed",
            ],

            "missing_api": missing,
        }

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

            # ------------------------------------------------
            # API CONTRACT
            # ------------------------------------------------

            api_status = self.status()

            if api_status["status"] != "ready":

                result["status"] = "failed"
                result["errors"] = 1

                result["message"] = (
                    "ETC API contract incomplete: "
                    f"{api_status['missing_api']}"
                )

                result["finished_at"] = _now()

                return result

            # ------------------------------------------------
            # LEAGUES
            # ------------------------------------------------

            if league:

                leagues = [league]

            else:

                leagues = list(
                    BATCH_RULES.keys()
                )

            if not leagues:

                result["status"] = "failed"
                result["errors"] = 1

                result["message"] = (
                    "Не определены турниры ETC."
                )

                result["finished_at"] = _now()

                return result

            # ------------------------------------------------
            # EACH LEAGUE
            # ------------------------------------------------

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

                result["batch_size"] += _safe_count(
                    league_result.get("batch_size")
                )

                result["analyzed"] += _safe_count(
                    league_result.get("analyzed")
                )

                result["learned"] += _safe_count(
                    league_result.get("learned")
                )

                result["processed"] += _safe_count(
                    league_result.get("processed")
                )

                result["learning_events"] += _safe_count(
                    league_result.get("learning_events")
                )

                result["memory_events"] += _safe_count(
                    league_result.get("memory_events")
                )

                result["errors"] += _safe_count(
                    league_result.get("errors")
                )

                result["processed_match_ids"].extend(
                    league_result.get(
                        "processed_match_ids",
                        [],
                    ) or []
                )

                result["failed_matches"].extend(
                    league_result.get(
                        "failed_matches",
                        [],
                    ) or []
                )

            # ------------------------------------------------
            # FINAL STATUS
            # ------------------------------------------------

            result["finished_at"] = _now()

            statuses = [
                batch.get("status")
                for batch in result["batches"]
            ]

            processing_statuses = {
                "completed",
                "partial",
                "completed_with_errors",
            }

            waiting_statuses = {
                STATUS_WAIT,
                STATUS_ALREADY_PROCESSED,
                STATUS_UNKNOWN_LEAGUE,
                "nothing_to_process",
                "empty",
            }

            has_completed = any(
                status in processing_statuses
                for status in statuses
            )

            has_errors = result["errors"] > 0

            all_waiting = (
                bool(statuses)
                and all(
                    status in waiting_statuses
                    for status in statuses
                )
            )

            # ------------------------------------------------
            # NOTHING TO PROCESS
            # ------------------------------------------------

            if all_waiting:

                result["status"] = (
                    "nothing_to_process"
                )

                result["message"] = (
                    "Нет нового готового ETC batch."
                )

            # ------------------------------------------------
            # SUCCESS WITHOUT ERRORS
            # ------------------------------------------------

            elif has_completed and not has_errors:

                result["status"] = "completed"

                result["message"] = (
                    "ETC успешно обработал "
                    "доступные batch."
                )

            # ------------------------------------------------
            # PARTIAL
            # ------------------------------------------------

            elif has_completed and has_errors:

                result["status"] = (
                    "completed_with_errors"
                )

                result["message"] = (
                    "ETC обработал доступные batch. "
                    "Некоторые матчи завершились ошибкой "
                    "и остаются доступными для повторной "
                    "обработки."
                )

            # ------------------------------------------------
            # FAILED
            # ------------------------------------------------

            else:

                result["status"] = "failed"

                result["message"] = (
                    "ETC не смог обработать "
                    "готовый batch."
                )

            logger.info(
                "ETC RUN FINISHED | "
                "status=%s | processed=%s | errors=%s",
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
                "ETC RUN FAILED"
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
        # 1. CHECK
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

        except Exception as exc:

            result["status"] = "failed"
            result["errors"] = 1
            result["message"] = str(exc)

            logger.exception(
                "BatchController.check failed | league=%s",
                league,
            )

            return result

        if not isinstance(
            batch_check,
            dict,
        ):

            result["status"] = "failed"
            result["errors"] = 1

            result["message"] = (
                "BatchController.check() "
                "вернул не-dict."
            )

            return result

        result["batch_check"] = batch_check

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
                    batch_check.get(
                        "message",
                        "Batch не готов.",
                    ),
                )
            )

            logger.info(
                "ETC [%s] batch status=%s | %s",
                league,
                result["status"],
                result["message"],
            )

            return result

        # =====================================================
        # 2. GET BATCH
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
                "get_learning_batch failed | league=%s",
                league,
            )

            return result

        if not selected_batch:

            result["status"] = "empty"
            result["errors"] = 1

            result["message"] = (
                "BatchController сообщил READY, "
                "но get_learning_batch() "
                "вернул пустой batch."
            )

            logger.error(
                "ETC CONTRACT ERROR | "
                "READY + empty batch | league=%s",
                league,
            )

            return result

        result["batch_size"] = len(
            selected_batch
        )

        result["selected_match_ids"] = [
            match_id
            for match_id in (
                self._extract_match_id(item)
                for item in selected_batch
            )
            if match_id is not None
        ]

        # =====================================================
        # 3. LEARNING ENGINE
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

        except Exception as exc:

            result["status"] = "failed"
            result["errors"] = 1
            result["message"] = str(exc)

            logger.exception(
                "LearningEngine.run_batch failed | league=%s",
                league,
            )

            return result

        if not isinstance(
            learning_result,
            dict,
        ):

            result["status"] = "failed"
            result["errors"] = 1

            result["message"] = (
                "ETCLearningEngine.run_batch() "
                "вернул не-dict."
            )

            return result

        result["learning_result"] = (
            learning_result
        )

        # =====================================================
        # COUNTERS
        # =====================================================

        result["processed"] = _safe_count(
            learning_result.get(
                "processed",
                0,
            )
        )

        result["analyzed"] = _safe_count(
            learning_result.get(
                "analyzed",
                learning_result.get(
                    "processed",
                    0,
                ),
            )
        )

        result["learned"] = _safe_count(
            learning_result.get(
                "learned",
                learning_result.get(
                    "processed",
                    0,
                ),
            )
        )

        result["learning_events"] = _safe_count(
            learning_result.get(
                "learning_events",
                0,
            )
        )

        memory_ids = learning_result.get(
            "memory_ids",
            [],
        )

        if isinstance(
            memory_ids,
            list,
        ):

            result["memory_events"] = len(
                memory_ids
            )

        result["processed_match_ids"] = (
            learning_result.get(
                "processed_match_ids",
                [],
            )
            or []
        )

        # =====================================================
        # ERRORS
        # =====================================================

        learning_errors = learning_result.get(
            "errors",
            [],
        )

        if isinstance(
            learning_errors,
            list,
        ):

            normalized_errors = (
                learning_errors
            )

        elif isinstance(
            learning_errors,
            int,
        ):

            normalized_errors = []

            if learning_errors > 0:

                normalized_errors = [
                    {
                        "match_id": None,
                        "stage": "learning",
                        "error": (
                            f"{learning_errors} "
                            "learning errors"
                        ),
                    }
                ]

        elif learning_errors:

            normalized_errors = [
                {
                    "match_id": None,
                    "stage": "learning",
                    "error": str(
                        learning_errors
                    ),
                }
            ]

        else:

            normalized_errors = []

        result["errors"] = len(
            normalized_errors
        )

        result["failed_matches"] = [
            error
            if isinstance(error, dict)
            else {
                "match_id": None,
                "stage": "learning",
                "error": str(error),
            }
            for error in normalized_errors
        ]

        # =====================================================
        # FINAL STATUS
        # =====================================================

        learning_status = learning_result.get(
            "status"
        )

        if learning_status == "completed":

            result["status"] = "completed"

            result["message"] = (
                "ETC batch полностью обработан."
            )

        elif learning_status in {
            "partial",
            "completed_with_errors",
        }:

            result["status"] = "partial"

            result["message"] = (
                "ETC batch обработан частично. "
                "Неуспешные матчи не считаются "
                "успешно закрытыми."
            )

        elif learning_status in {
            STATUS_WAIT,
            STATUS_ALREADY_PROCESSED,
            STATUS_UNKNOWN_LEAGUE,
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

            result["status"] = "failed"

            error_text = (
                learning_result.get("error")
                or learning_result.get("message")
                or learning_status
                or "processing_failed"
            )

            result["message"] = (
                f"ETC learning failed: {error_text}"
            )

            if result["errors"] == 0:
                result["errors"] = 1

        logger.info(
            "ETC [%s] FINISHED | "
            "status=%s | processed=%s | errors=%s",
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

        normalized_match_id = _safe_int(
            match_id,
            default=0,
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

        if normalized_match_id <= 0:

            result["status"] = "invalid_match_id"
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
                    "LearningEngine вернул не-dict."
                )

            if not learning.get(
                "success",
                False,
            ):

                learning_error = (
                    learning.get("error")
                    or learning.get("message")
                    or learning.get("status")
                    or "processing_failed"
                )

                raise ValueError(
                    "LearningEngine неуспешен: "
                    f"{learning_error}"
                )

            result["status"] = "completed"

            return result

        except Exception as exc:

            result["status"] = "failed"
            result["error"] = str(exc)

            logger.exception(
                "ETC single match failed | match_id=%s",
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

            value = (
                item.get("match_id")
                or item.get("id")
            )

            normalized = _safe_int(
                value,
                default=0,
            )

            return (
                normalized
                if normalized > 0
                else None
            )

        for key in (
            "match_id",
            "id",
        ):

            try:

                value = item[key]

                normalized = _safe_int(
                    value,
                    default=0,
                )

                if normalized > 0:
                    return normalized

            except Exception:
                pass

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
                    value,
                    default=0,
                )

                if normalized > 0:
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

        status = controller.status()

        print()
        print("ETC STATUS")
        print("-" * 70)

        for key, value in status.items():
            print(f"{key}: {value}")

        print()
        print("ETC Controller готов.")
        print("BatchController:")
        print("  check()")
        print("  get_learning_batch()")
        print("LearningEngine:")
        print("  process_match()")
        print("  run_batch()")
        print()
        print("create_batch() НЕ используется.")
        print("mark_processed() НЕ используется.")
        print("LearningMemory записывается LearningEngine.")

    except Exception as exc:

        print(
            f"ETC Controller unavailable: {exc}"
        )

    print("=" * 70)
