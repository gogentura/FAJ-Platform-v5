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

КОНТРАКТ:

    MATCH
      ↓
    IMPORT FACTS
      ↓
    SQLite
      ↓
    BatchController
      │
      ├── check()
      └── get_learning_batch()
      ↓
    ETCController
      ↓
    ETCLearningEngine
      │
      ├── process_match()
      └── run_batch(
              league=...,
              season_id=...,
              batch=...
          )
      ↓
    LEARNING PIPELINE
      ↓
    LEARNING MEMORY
      ↓
    SQLite

============================================================

ГРАНИЦЫ ETCController
============================================================

ETCController — ОРКЕСТРАТОР.

Он НЕ является:

    - Prediction Model;
    - xG Engine;
    - Statistical Analyzer;
    - Error Classifier;
    - Club Rating Updater;
    - Learning Memory writer;
    - Model Parameter trainer;
    - Batch storage;
    - Match Result importer.

ETCController НЕ:

    - считает xG;
    - считает прогноз;
    - классифицирует ошибки матча;
    - изменяет Club Rating;
    - изменяет passports;
    - изменяет team_history;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет predictions;
    - изменяет model_parameters;
    - пишет learning_memory напрямую;
    - создаёт batch;
    - помечает batch как processed;
    - изменяет календарь;
    - выполняет DELETE;
    - выполняет DROP.

ETCController ТОЛЬКО:

    1. проверяет API ETC;
    2. вызывает BatchController.check();
    3. если batch READY —
       вызывает get_learning_batch();
    4. передаёт ПОЛУЧЕННЫЙ batch
       ETCLearningEngine;
    5. получает результат Engine;
    6. нормализует диагностический результат;
    7. агрегирует результат;
    8. возвращает его UI / вызывающему коду.

============================================================

ФАКТИЧЕСКИЙ КОНТРАКТ BatchController v1.3
============================================================

    check(
        league,
        season_id=None
    )

    get_learning_batch(
        league,
        season_id=None,
        limit=None
    )

BatchController возвращает:

    get_learning_batch()
        ↓
    List[Dict[str, Any]]

Controller НЕ преобразует batch
в отдельный контракт match_ids
для LearningEngine.

============================================================

ФАКТИЧЕСКИЙ КОНТРАКТ ETCLearningEngine v1.5
============================================================

run_batch():

    run_batch(
        league=None,
        season_id=None,
        batch=None
    )

Возвращает:

    {
        "success": bool,
        "status": str,
        "league": Optional[str],
        "season_id": Optional[int],
        "processed": int,
        "failed": int,
        "total": int,
        "learning_events": int,
        "processed_match_ids": List[int],
        "memory_ids": List[int],
        "batch_memory_ids": List[int],
        "batch_completed": bool,
        "batch_check": Optional[Dict],
        "errors": List[Dict],
        "started_at": str,
        "created_at": str
    }

process_match():

    process_match(
        match_id
    )

Возвращает:

    {
        "success": bool,
        "status": str,
        "match_id": int,
        "analysis": Optional[Dict],
        "memory_ids": List[int],
        "learning_events": int,
        "marker_id": Optional[int],
        "error": Optional[str],
        "created_at": str
    }

============================================================

ВАЖНО
============================================================

Controller НЕ требует от LearningEngine полей:

    already_processed
    learned
    analyzed
    memory_events

которых нет в его фактическом API.

Вместо этого:

    analyzed
        ← total

    learned
        ← processed

только как UI-нормализация результата
текущего Engine.

    memory_events
        ← количество batch_memory_ids

    already_processed
        ← 0 на уровне текущего batch Engine.

Состояние уже обработанных матчей
определяет BatchController через:

    learning_memory.event_type
        = 'batch_learning'

    learning_memory.reference_id
        = match_id

============================================================

АРХИТЕКТУРНОЕ ПРАВИЛО
============================================================

ErrorClassifier и ClubRatingUpdater НЕ вызываются
непосредственно из ETCController.

Они принадлежат внутреннему learning pipeline.

Правильная цепочка:

    ETCController
          ↓
    ETCLearningEngine
          ↓
    ErrorClassifier
          ↓
    ClubRatingUpdater
          ↓
    Statistical Analysis
          ↓
    LearningMemory
          ↓
    SQLite

============================================================

FORCE
============================================================

force является параметром уровня Controller.

BatchController НЕ поддерживает force.

Поэтому Controller НЕ передаёт force
в LearningEngine.

force не используется для обхода правила:

    неполный batch != READY

============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional


from app.database import FAJDatabase

from app.etc.batch_controller import (
    BATCH_RULES,
    STATUS_ALREADY_PROCESSED,
    STATUS_READY,
    STATUS_UNKNOWN_LEAGUE,
    STATUS_WAIT,
    BatchController,
)

from app.etc.learning_engine import (
    ETCLearningEngine,
)


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

MODULE_NAME = "ETC Controller"
MODULE_VERSION = "2.6"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Текущее локальное время.

    Используется только для диагностического результата.
    """

    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
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
    Безопасный неотрицательный счётчик.
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


def _normalize_errors(
    errors: Any,
) -> List[Dict[str, Any]]:
    """
    Приводит различные форматы ошибок
    к единому списку словарей.
    """

    if not errors:
        return []

    if isinstance(
        errors,
        list,
    ):

        normalized: List[
            Dict[str, Any]
        ] = []

        for error in errors:

            if isinstance(
                error,
                dict,
            ):

                normalized.append(
                    error
                )

            else:

                normalized.append(
                    {
                        "match_id": None,
                        "stage": "learning",
                        "error": str(error),
                    }
                )

        return normalized

    if isinstance(
        errors,
        int,
    ):

        if errors <= 0:
            return []

        return [
            {
                "match_id": None,
                "stage": "learning",
                "error": (
                    f"{errors} learning errors"
                ),
            }
        ]

    return [
        {
            "match_id": None,
            "stage": "learning",
            "error": str(errors),
        }
    ]


def _normalize_match_ids(
    values: Any,
) -> List[int]:
    """
    Нормализует список match_id.

    Controller не создаёт идентификаторы.
    Он только нормализует значения,
    полученные от других компонентов.
    """

    if values is None:
        return []

    if not isinstance(
        values,
        (list, tuple, set),
    ):

        values = [values]

    result: List[int] = []

    for value in values:

        normalized = _safe_int(
            value,
            default=0,
        )

        if normalized > 0:

            result.append(
                normalized
            )

    unique: List[int] = []
    seen = set()

    for match_id in result:

        if match_id in seen:
            continue

        seen.add(
            match_id
        )

        unique.append(
            match_id
        )

    return unique


def _extract_status(
    payload: Any,
) -> Optional[str]:
    """
    Получает status из dict.
    """

    if not isinstance(
        payload,
        dict,
    ):
        return None

    value = payload.get(
        "status"
    )

    if value is None:
        return None

    return str(
        value
    ).strip()


def _extract_message(
    payload: Any,
) -> str:
    """
    Получает диагностическое сообщение
    из результата компонента.
    """

    if not isinstance(
        payload,
        dict,
    ):
        return ""

    value = (
        payload.get("message")
        or payload.get("reason")
        or payload.get("error")
        or payload.get("status")
    )

    if value is None:
        return ""

    return str(
        value
    )


# ============================================================
# ETC CONTROLLER
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center.

    Контроллер не содержит математической логики.

    Его задача:

        BatchController
              ↓
        готовый batch
              ↓
        LearningEngine
              ↓
        нормализация результата
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

        self.db = (
            db
            or FAJDatabase()
        )

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

    def status(
        self,
    ) -> Dict[str, Any]:
        """
        Read-only проверка ETC API.

        Никаких изменений базы данных.
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
                self.batch_controller
                .__class__.__name__
            ),

            "learning_engine": (
                self.learning_engine
                .__class__.__name__
            ),

            "api_contract": {
                name: callable(method)
                for name, method in required.items()
            },

            "legacy_api_used": False,

            "legacy_api": {
                "create_batch": False,
                "mark_processed": False,
            },

            "forbidden_operations": [
                "DELETE",
                "DROP",
                "direct_learning_memory_write",
                "direct_match_result_mutation",
                "direct_prediction_mutation",
                "direct_model_parameter_mutation",
                "direct_calendar_mutation",
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
        """
        Запускает ETC batch pipeline.

        ВАЖНО:

        force является orchestration policy.

        Он НЕ передаётся BatchController,
        потому что BatchController его не поддерживает.

        Он НЕ передаётся LearningEngine,
        потому что LearningEngine v1.5
        его не принимает.

        force НЕ позволяет обойти READY-контракт.
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

            "limit": limit,

            "force": bool(force),

            "leagues_checked": [],

            "batch_size": 0,

            "analyzed": 0,

            "learned": 0,

            "processed": 0,

            "failed": 0,

            "already_processed": 0,

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
            # LIMIT VALIDATION
            # =================================================

            if limit is not None:

                normalized_limit = _safe_int(
                    limit,
                    default=0,
                )

                if normalized_limit <= 0:

                    result["status"] = (
                        "invalid_limit"
                    )

                    result["errors"] = 1

                    result["message"] = (
                        "limit должен быть "
                        "положительным числом."
                    )

                    result["finished_at"] = _now()

                    return result

                result["limit"] = (
                    normalized_limit
                )

            # =================================================
            # API CONTRACT
            # =================================================

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

            # =================================================
            # LEAGUES
            # =================================================

            if league:

                leagues = [
                    str(league).strip()
                ]

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

            # =================================================
            # EACH LEAGUE
            # =================================================

            for current_league in leagues:

                if not current_league:
                    continue

                result[
                    "leagues_checked"
                ].append(
                    current_league
                )

                league_result = (
                    self._run_league(
                        league=current_league,
                        season_id=season_id,
                        limit=result["limit"],
                        force=force,
                    )
                )

                result[
                    "batches"
                ].append(
                    league_result
                )

                # ---------------------------------------------
                # AGGREGATION
                # ---------------------------------------------

                result[
                    "batch_size"
                ] += _safe_count(
                    league_result.get(
                        "batch_size"
                    )
                )

                result[
                    "analyzed"
                ] += _safe_count(
                    league_result.get(
                        "analyzed"
                    )
                )

                result[
                    "learned"
                ] += _safe_count(
                    league_result.get(
                        "learned"
                    )
                )

                result[
                    "processed"
                ] += _safe_count(
                    league_result.get(
                        "processed"
                    )
                )

                result[
                    "failed"
                ] += _safe_count(
                    league_result.get(
                        "failed"
                    )
                )

                result[
                    "already_processed"
                ] += _safe_count(
                    league_result.get(
                        "already_processed"
                    )
                )

                result[
                    "learning_events"
                ] += _safe_count(
                    league_result.get(
                        "learning_events"
                    )
                )

                result[
                    "memory_events"
                ] += _safe_count(
                    league_result.get(
                        "memory_events"
                    )
                )

                result[
                    "errors"
                ] += _safe_count(
                    league_result.get(
                        "errors"
                    )
                )

                result[
                    "processed_match_ids"
                ].extend(
                    _normalize_match_ids(
                        league_result.get(
                            "processed_match_ids"
                        )
                    )
                )

                failed_matches = (
                    league_result.get(
                        "failed_matches",
                        [],
                    )
                    or []
                )

                if isinstance(
                    failed_matches,
                    list,
                ):

                    result[
                        "failed_matches"
                    ].extend(
                        failed_matches
                    )

            # =================================================
            # UNIQUE IDS
            # =================================================

            result[
                "processed_match_ids"
            ] = _normalize_match_ids(
                result[
                    "processed_match_ids"
                ]
            )

            # =================================================
            # FINAL STATUS
            # =================================================

            result["finished_at"] = _now()

            statuses = [
                _extract_status(
                    batch
                )
                for batch in result["batches"]
            ]

            statuses = [
                status
                for status in statuses
                if status
            ]

            completed_statuses = {
                "completed",
            }

            partial_statuses = {
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
                status in completed_statuses
                for status in statuses
            )

            has_partial = any(
                status in partial_statuses
                for status in statuses
            )

            has_errors = (
                result["errors"] > 0
            )

            all_waiting = (
                bool(statuses)
                and all(
                    status in waiting_statuses
                    for status in statuses
                )
            )

            if all_waiting:

                result["status"] = (
                    "nothing_to_process"
                )

                result["message"] = (
                    "Нет нового готового ETC batch."
                )

            elif has_completed and not has_errors:

                result["status"] = (
                    "completed"
                )

                result["message"] = (
                    "ETC успешно обработал "
                    "доступные batch."
                )

            elif (
                has_completed
                or has_partial
            ):

                result["status"] = (
                    "completed_with_errors"
                )

                result["message"] = (
                    "ETC обработал доступные batch. "
                    "Некоторые матчи завершились "
                    "ошибкой."
                )

            else:

                result["status"] = "failed"

                result["message"] = (
                    "ETC не смог обработать "
                    "готовый batch."
                )

            logger.info(
                "ETC RUN FINISHED | "
                "status=%s | "
                "processed=%s | "
                "failed=%s | "
                "learned=%s | "
                "memory=%s | "
                "errors=%s",
                result["status"],
                result["processed"],
                result["failed"],
                result["learned"],
                result["memory_events"],
                result["errors"],
            )

            logger.info(
                "=================================================="
            )

            return result

        except Exception as exc:

            result["status"] = "failed"

            result["errors"] = (
                _safe_count(
                    result.get("errors")
                )
                + 1
            )

            result["message"] = str(
                exc
            )

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
        """
        Полный цикл одного турнира:

            check()
              ↓
            READY?
              ↓
            get_learning_batch()
              ↓
            LearningEngine.run_batch(
                league=...,
                season_id=...,
                batch=...
            )
        """

        result: Dict[str, Any] = {

            "league": league,

            "season_id": season_id,

            "status": "started",

            "batch_size": 0,

            "analyzed": 0,

            "learned": 0,

            "processed": 0,

            "failed": 0,

            "already_processed": 0,

            "learning_events": 0,

            "memory_events": 0,

            "errors": 0,

            "failed_matches": [],

            "processed_match_ids": [],

            "batch_check": None,

            "selected_match_ids": [],

            "learning_result": None,

            "message": "",

            "force": bool(force),
        }

        # =====================================================
        # STEP 1 — CHECK
        # =====================================================

        logger.info(
            "ETC [%s] STEP 1 — "
            "BatchController.check()",
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

            result["message"] = str(
                exc
            )

            logger.exception(
                "BatchController.check failed | "
                "league=%s",
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

        result[
            "batch_check"
        ] = batch_check

        controller_status = (
            _extract_status(
                batch_check
            )
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
                _extract_message(
                    batch_check
                )
                or "Batch не готов."
            )

            logger.info(
                "ETC [%s] batch status=%s | %s",
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

            result["message"] = str(
                exc
            )

            logger.exception(
                "get_learning_batch failed | "
                "league=%s",
                league,
            )

            return result

        # =====================================================
        # EMPTY BATCH
        # =====================================================

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
                "READY + empty batch | "
                "league=%s",
                league,
            )

            return result

        # =====================================================
        # BATCH NORMALIZATION
        # =====================================================

        if isinstance(
            selected_batch,
            dict,
        ):

            selected_batch = [
                selected_batch
            ]

        elif not isinstance(
            selected_batch,
            (list, tuple),
        ):

            result["status"] = "failed"

            result["errors"] = 1

            result["message"] = (
                "get_learning_batch() "
                "вернул неподдерживаемый тип: "
                f"{type(selected_batch).__name__}"
            )

            return result

        selected_batch = list(
            selected_batch
        )

        if not selected_batch:

            result["status"] = "empty"

            result["errors"] = 1

            result["message"] = (
                "Batch после нормализации пуст."
            )

            return result

        # =====================================================
        # BATCH SIZE
        # =====================================================

        result[
            "batch_size"
        ] = len(
            selected_batch
        )

        # =====================================================
        # EXTRACT IDS ONLY FOR DIAGNOSTICS
        #
        # ВАЖНО:
        #
        # Эти IDs НЕ передаются в run_batch().
        #
        # LearningEngine получает исходный batch.
        # =====================================================

        selected_ids: List[int] = []

        for item in selected_batch:

            match_id = (
                self._extract_match_id(
                    item
                )
            )

            if match_id is not None:

                selected_ids.append(
                    match_id
                )

        result[
            "selected_match_ids"
        ] = _normalize_match_ids(
            selected_ids
        )

        # =====================================================
        # CONTRACT CHECK
        # =====================================================

        if not selected_ids:

            result["status"] = "failed"

            result["errors"] = 1

            result["message"] = (
                "Batch содержит объекты, "
                "но ни один объект не содержит "
                "валидный match_id."
            )

            return result

        # =====================================================
        # STEP 3 — LEARNING ENGINE
        # =====================================================

        logger.info(
            "ETC [%s] STEP 3 — "
            "ETCLearningEngine.run_batch() | "
            "batch_size=%s",
            league,
            len(selected_batch),
        )

        try:

            # =================================================
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ
            #
            # ФАКТИЧЕСКИЙ API LearningEngine v1.5:
            #
            # run_batch(
            #     league=None,
            #     season_id=None,
            #     batch=None
            # )
            #
            # Поэтому передаём batch,
            # а НЕ match_ids.
            # =================================================

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

            result["message"] = str(
                exc
            )

            logger.exception(
                "LearningEngine.run_batch failed | "
                "league=%s",
                league,
            )

            return result

        # =====================================================
        # RESULT TYPE
        # =====================================================

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

        result[
            "learning_result"
        ] = learning_result

        # =====================================================
        # FACTUAL ENGINE COUNTERS
        # =====================================================

        total = _safe_count(
            learning_result.get(
                "total",
                0,
            )
        )

        processed = _safe_count(
            learning_result.get(
                "processed",
                0,
            )
        )

        failed = _safe_count(
            learning_result.get(
                "failed",
                0,
            )
        )

        learning_events = _safe_count(
            learning_result.get(
                "learning_events",
                0,
            )
        )

        result[
            "analyzed"
        ] = total

        result[
            "processed"
        ] = processed

        result[
            "failed"
        ] = failed

        result[
            "learning_events"
        ] = learning_events

        # =====================================================
        # LEARNED
        #
        # Engine v1.5 не возвращает отдельный "learned".
        #
        # В Controller это только UI-нормализация:
        #
        # successfully processed matches
        # = learned matches
        #
        # Никакой собственной математики здесь нет.
        # =====================================================

        result[
            "learned"
        ] = processed

        # =====================================================
        # ALREADY PROCESSED
        #
        # LearningEngine v1.5 НЕ возвращает
        # already_processed для batch.
        #
        # BatchController отвечает за фильтрацию
        # уже обработанных матчей ДО запуска Engine.
        #
        # Поэтому не выдумываем значение.
        # =====================================================

        result[
            "already_processed"
        ] = 0

        # =====================================================
        # MEMORY IDS
        # =====================================================

        memory_ids = (
            learning_result.get(
                "memory_ids",
                [],
            )
        )

        batch_memory_ids = (
            learning_result.get(
                "batch_memory_ids",
                [],
            )
        )

        # -----------------------------------------------------
        # Текущий batch имеет собственный набор memory IDs.
        # -----------------------------------------------------

        if isinstance(
            batch_memory_ids,
            (list, tuple, set),
        ):

            result[
                "memory_events"
            ] = len(
                batch_memory_ids
            )

        elif isinstance(
            memory_ids,
            (list, tuple, set),
        ):

            result[
                "memory_events"
            ] = len(
                memory_ids
            )

        else:

            result[
                "memory_events"
            ] = 0

        # =====================================================
        # PROCESSED MATCH IDS
        # =====================================================

        engine_processed_ids = (
            learning_result.get(
                "processed_match_ids",
                [],
            )
        )

        result[
            "processed_match_ids"
        ] = _normalize_match_ids(
            engine_processed_ids
        )

        # =====================================================
        # ERRORS
        # =====================================================

        normalized_errors = (
            _normalize_errors(
                learning_result.get(
                    "errors",
                    [],
                )
            )
        )

        result[
            "failed_matches"
        ] = normalized_errors

        # Engine является источником
        # failed counter.

        result[
            "errors"
        ] = max(
            failed,
            len(normalized_errors),
        )

        # =====================================================
        # SINGLE ERROR FALLBACK
        # =====================================================

        if (
            result["errors"] == 0
            and learning_result.get(
                "error"
            )
        ):

            result[
                "errors"
            ] = 1

            result[
                "failed_matches"
            ] = [
                {
                    "match_id": None,
                    "stage": "learning",
                    "error": str(
                        learning_result.get(
                            "error"
                        )
                    ),
                }
            ]

        # =====================================================
        # SUCCESS FLAG
        # =====================================================

        engine_success = (
            learning_result.get(
                "success"
            )
        )

        if engine_success is False:

            if result["errors"] == 0:

                result[
                    "errors"
                ] = 1

        # =====================================================
        # BATCH COMPLETED
        # =====================================================

        batch_completed = (
            learning_result.get(
                "batch_completed"
            )
        )

        # =====================================================
        # FINAL STATUS
        # =====================================================

        learning_status = (
            _extract_status(
                learning_result
            )
        )

        # -----------------------------------------------------
        # COMPLETED
        # -----------------------------------------------------

        if (
            learning_status == "completed"
            and result["errors"] == 0
        ):

            result[
                "status"
            ] = "completed"

            result[
                "message"
            ] = (
                "ETC batch полностью обработан."
            )

        # -----------------------------------------------------
        # PARTIAL
        # -----------------------------------------------------

        elif learning_status in {
            "partial",
            "completed_with_errors",
        }:

            result[
                "status"
            ] = "partial"

            result[
                "message"
            ] = (
                "ETC batch обработан частично. "
                "Неуспешные матчи не считаются "
                "успешно обученными."
            )

        # -----------------------------------------------------
        # EMPTY
        # -----------------------------------------------------

        elif learning_status == "empty":

            result[
                "status"
            ] = "empty"

            result[
                "message"
            ] = (
                "Learning Engine получил "
                "пустой batch."
            )

        # -----------------------------------------------------
        # WAITING / ALREADY PROCESSED
        # -----------------------------------------------------

        elif learning_status in {
            STATUS_WAIT,
            STATUS_ALREADY_PROCESSED,
            STATUS_UNKNOWN_LEAGUE,
        }:

            result[
                "status"
            ] = learning_status

            result[
                "message"
            ] = (
                _extract_message(
                    learning_result
                )
                or learning_status
            )

        # -----------------------------------------------------
        # FAILED
        # -----------------------------------------------------

        elif (
            learning_status == "failed"
            or engine_success is False
            or result["errors"] > 0
        ):

            result[
                "status"
            ] = "failed"

            result[
                "message"
            ] = (
                _extract_message(
                    learning_result
                )
                or "ETC learning failed."
            )

            if result["errors"] == 0:

                result[
                    "errors"
                ] = 1

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        else:

            result[
                "status"
            ] = "failed"

            result[
                "message"
            ] = (
                "Неизвестный статус "
                "ETCLearningEngine: "
                f"{learning_status}"
            )

            if result["errors"] == 0:

                result[
                    "errors"
                ] = 1

        # =====================================================
        # DIAGNOSTIC LOG
        # =====================================================

        logger.info(
            "ETC [%s] FINISHED | "
            "status=%s | "
            "batch=%s | "
            "total=%s | "
            "processed=%s | "
            "failed=%s | "
            "learned=%s | "
            "memory=%s | "
            "batch_completed=%s | "
            "errors=%s",
            league,
            result["status"],
            result["batch_size"],
            total,
            processed,
            failed,
            result["learned"],
            result["memory_events"],
            batch_completed,
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
        Запускает ETC для одного матча.

        Controller только передаёт match_id
        в LearningEngine.
        """

        normalized_match_id = (
            _safe_int(
                match_id,
                default=0,
            )
        )

        result: Dict[str, Any] = {

            "module": MODULE_NAME,

            "version": MODULE_VERSION,

            "match_id": (
                normalized_match_id
            ),

            "status": "started",

            "learning": None,

            "error": None,

            "force": bool(force),
        }

        # =====================================================
        # VALIDATION
        # =====================================================

        if normalized_match_id <= 0:

            result[
                "status"
            ] = "invalid_match_id"

            result[
                "error"
            ] = (
                "Некорректный match_id."
            )

            if force:

                return result

            raise ValueError(
                "Некорректный match_id."
            )

        # =====================================================
        # LEARNING ENGINE
        # =====================================================

        logger.info(
            "ETC SINGLE MATCH STARTED | "
            "match_id=%s | force=%s",
            normalized_match_id,
            force,
        )

        try:

            learning = (
                self.learning_engine
                .process_match(
                    match_id=(
                        normalized_match_id
                    )
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
                    "вернул не-dict."
                )

            # -------------------------------------------------
            # SUCCESS CONTRACT
            # -------------------------------------------------

            if not learning.get(
                "success",
                False,
            ):

                learning_error = (
                    learning.get(
                        "error"
                    )
                    or learning.get(
                        "message"
                    )
                    or learning.get(
                        "status"
                    )
                    or "processing_failed"
                )

                raise ValueError(
                    "LearningEngine "
                    "неуспешен: "
                    f"{learning_error}"
                )

            result[
                "status"
            ] = "completed"

            logger.info(
                "ETC SINGLE MATCH FINISHED | "
                "match_id=%s",
                normalized_match_id,
            )

            return result

        except Exception as exc:

            result[
                "status"
            ] = "failed"

            result[
                "error"
            ] = str(
                exc
            )

            logger.exception(
                "ETC single match failed | "
                "match_id=%s",
                normalized_match_id,
            )

            if force:

                return result

            raise

    # ========================================================
    # MATCH ID EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Any,
    ) -> Optional[int]:
        """
        Извлекает match_id из элемента batch.

        Поддерживает:

            int
            dict
            mapping-like objects
            object attributes

        Используется только для диагностики
        и проверки batch.

        В LearningEngine передаётся
        исходный объект batch.
        """

        if item is None:
            return None

        # ----------------------------------------------------
        # INTEGER
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

            value = (
                item.get(
                    "match_id"
                )
                or item.get(
                    "id"
                )
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

        # ----------------------------------------------------
        # MAPPING-LIKE
        # ----------------------------------------------------

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

            except (
                KeyError,
                IndexError,
                TypeError,
                AttributeError,
            ):

                pass

        # ----------------------------------------------------
        # OBJECT ATTRIBUTES
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
    """
    Публичный batch API ETC.
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
    Публичный single-match API ETC.
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
    Публичный read-only API статуса ETC.
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

    print(
        "FAJ Platform v12.1"
    )

    print(
        "ETC — Evolution Training Center"
    )

    print(
        "ETC Controller"
    )

    print(
        f"Version: {MODULE_VERSION}"
    )

    print("=" * 70)

    try:

        controller = ETCController()

        status = (
            controller.status()
        )

        print()
        print(
            "ETC STATUS"
        )

        print(
            "-" * 70
        )

        for key, value in status.items():

            print(
                f"{key}: {value}"
            )

        print()
        print(
            "ETC Controller готов."
        )

        print()
        print(
            "BatchController:"
        )

        print(
            "  check("
            "league, season_id=None)"
        )

        print(
            "  get_learning_batch("
            "league, season_id=None, limit=None)"
        )

        print()
        print(
            "LearningEngine:"
        )

        print(
            "  process_match(match_id)"
        )

        print(
            "  run_batch("
            "league=None, "
            "season_id=None, "
            "batch=None)"
        )

        print()
        print(
            "ВАЖНО:"
        )

        print(
            "  run_batch() получает batch,"
        )

        print(
            "  а НЕ match_ids."
        )

        print()
        print(
            "Legacy API:"
        )

        print(
            "  create_batch() НЕ используется."
        )

        print(
            "  mark_processed() НЕ используется."
        )

        print()
        print(
            "Controller:"
        )

        print(
            "  не пишет LearningMemory напрямую;"
        )

        print(
            "  не изменяет match_results;"
        )

        print(
            "  не изменяет predictions;"
        )

        print(
            "  не изменяет model_parameters;"
        )

        print(
            "  не изменяет календарь;"
        )

        print(
            "  не выполняет DELETE;"
        )

        print(
            "  не выполняет DROP."
        )

        print()
        print(
            "Counter contract:"
        )

        print(
            "  analyzed <- Engine.total"
        )

        print(
            "  processed <- Engine.processed"
        )

        print(
            "  learned <- Engine.processed"
        )

        print(
            "  failed <- Engine.failed"
        )

        print(
            "  learning_events <- Engine.learning_events"
        )

        print(
            "  memory_events <- "
            "len(Engine.batch_memory_ids)"
        )

        print(
            "  already_processed <- 0"
        )

        print()
        print(
            "ETC Controller готов."
        )

    except Exception as exc:

        print(
            "ETC Controller unavailable: "
            f"{exc}"
        )

    print(
        "=" * 70
    )
