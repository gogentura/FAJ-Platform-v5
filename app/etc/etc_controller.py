#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/etc_controller.py
============================================================

ETC CONTROLLER v3.0
============================================================

НАЗНАЧЕНИЕ
-----------

Верхний оркестратор ETC.

КОНТРАКТ v3.0:

    MATCH
      ↓
    IMPORT FACTS
      ↓
    SQLite
      ↓
    BatchController v2.0
      │
      ├── check()
      └── get_learning_batch()
      ↓
    ETCController v3.0
      │
      ├── BEFORE snapshot (параметры до)
      ├── ETCLearningEngine v2.0
      │   ├── process_match()
      │   └── run_batch()
      ├── AFTER snapshot (параметры после)
      └── parameter_history
      ↓
    LEARNING MEMORY
      ↓
    SQLite


ГРАНИЦЫ ETCController v3.0
============================================================

ETCController — ОРКЕСТРАТОР.

Он НЕ является:
    - Prediction Model;
    - xG Engine;
    - Statistical Analyzer;
    - Error Classifier;
    - Club Rating Updater;
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
    - изменяет календарь;
    - выполняет DELETE;
    - выполняет DROP.

ETCController ТОЛЬКО:
    1. получает batch от BatchController;
    2. записывает BEFORE состояние параметров;
    3. передаёт batch в ETCLearningEngine;
    4. получает результат;
    5. записывает AFTER состояние параметров;
    6. записывает parameter_history;
    7. агрегирует результат.


НОВОЕ В v3.0: BEFORE ≠ AFTER
============================================================

Перед запуском обучения:

    BEFORE = текущие параметры модели

После успешного обучения:

    AFTER = новые параметры модели

Оба состояния записываются в learning_memory
с event_type = "parameter_before" и "parameter_after".

Все изменения параметров записываются
в parameter_history через:

    FAJDatabase.record_parameter_history()


СТАТУСНАЯ МОДЕЛЬ (v3.0)
============================================================

При запуске ETC Controller определяет статус каждого матча:

    DISCOVERED  → матч найден в batch
    NEW         → ещё не обработан ETC
    PROCESSING  → в процессе обработки
    COMPLETED   → успешно обработан
    ALREADY_PROCESSED → уже был обработан ранее
    SKIPPED     → пропущен (нет данных)
    FAILED      → ошибка обработки

Запускаются только NEW матчи.

============================================================
"""

from __future__ import annotations

import json
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

from app.etc.learning_memory import (
    LearningMemory,
)


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

MODULE_NAME = "ETC Controller"
MODULE_VERSION = "3.0"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Текущее локальное время.
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


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Безопасное преобразование в float.
    """

    try:

        if value is None:
            return default

        return float(value)

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
    Получает диагностическое сообщение.
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


def _serialize_params(
    params: Any,
) -> str:
    """
    Сериализует параметры модели в JSON.
    """

    if params is None:
        return "{}"

    if isinstance(
        params,
        dict,
    ):

        return json.dumps(
            params,
            ensure_ascii=False,
            sort_keys=True,
        )

    if hasattr(
        params,
        "__dict__",
    ):

        return json.dumps(
            params.__dict__,
            ensure_ascii=False,
            sort_keys=True,
        )

    return str(
        params
    )


# ============================================================
# ETC CONTROLLER v3.0
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center v3.0.

    Контроллер не содержит математической логики.

    Новое в v3.0:
        - BEFORE/AFTER запись параметров
        - parameter_history
        - Полная поддержка BEFORE ≠ AFTER
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
        learning_memory: Optional[
            LearningMemory
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

        self.learning_memory = (
            learning_memory
            or LearningMemory(
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

            "LearningMemory.record": getattr(
                self.learning_memory,
                "record",
                None,
            ),

            "FAJDatabase.record_parameter_history": getattr(
                self.db,
                "record_parameter_history",
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

            "learning_memory": (
                self.learning_memory
                .__class__.__name__
            ),

            "features": {
                "before_after_snapshot": True,
                "parameter_history": True,
                "append_only": True,
            },

            "api_contract": {
                name: callable(method)
                for name, method in required.items()
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
        Запускает ETC batch pipeline с BEFORE/AFTER.

        НОВОЕ v3.0:
            - BEFORE: запись параметров до обучения
            - AFTER: запись параметров после обучения
            - parameter_history: все изменения
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

            # НОВОЕ v3.0
            "parameter_before": None,
            "parameter_after": None,
            "parameter_changes": [],
            "parameter_history_ids": [],
        }

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC RUN STARTED v3.0 | "
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

                # ---------------------------------------------
                # PARAMETER HISTORY (НОВОЕ v3.0)
                # ---------------------------------------------

                param_before = (
                    league_result.get(
                        "parameter_before"
                    )
                )

                param_after = (
                    league_result.get(
                        "parameter_after"
                    )
                )

                if param_before is not None:

                    result[
                        "parameter_before"
                    ] = param_before

                if param_after is not None:

                    result[
                        "parameter_after"
                    ] = param_after

                result[
                    "parameter_changes"
                ].extend(
                    league_result.get(
                        "parameter_changes",
                        [],
                    )
                )

                result[
                    "parameter_history_ids"
                ].extend(
                    league_result.get(
                        "parameter_history_ids",
                        [],
                    )
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
                "ETC RUN FINISHED v3.0 | "
                "status=%s | "
                "processed=%s | "
                "already_processed=%s | "
                "failed=%s | "
                "learned=%s | "
                "memory=%s | "
                "parameter_changes=%s | "
                "errors=%s",
                result["status"],
                result["processed"],
                result["already_processed"],
                result["failed"],
                result["learned"],
                result["memory_events"],
                len(result["parameter_changes"]),
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
        Полный цикл одного турнира с BEFORE/AFTER.
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

            # НОВОЕ v3.0
            "parameter_before": None,
            "parameter_after": None,
            "parameter_changes": [],
            "parameter_history_ids": [],
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
        # EXTRACT IDS FOR DIAGNOSTICS
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
        # STEP 3 — BEFORE SNAPSHOT (НОВОЕ v3.0)
        # =====================================================

        logger.info(
            "ETC [%s] STEP 3 — BEFORE snapshot",
            league,
        )

        before_params = self.db.get_current_parameters()

        result["parameter_before"] = {
            "alpha": getattr(before_params, "alpha", 0.0),
            "beta": getattr(before_params, "beta", 0.0),
            "gamma": getattr(before_params, "gamma", 0.0),
            "delta": getattr(before_params, "delta", 0.0),
            "version": getattr(before_params, "version", 0),
        }

        # Записываем BEFORE в learning_memory
        try:

            before_memory_id = self.learning_memory.record(
                event_type="parameter_before",
                object_type=f"league:{league}",
                feature="model_parameters",
                before_value=None,
                after_value=result["parameter_before"],
                delta=None,
                reason=f"Параметры до обучения ETC batch (league={league})",
                confidence=1.0,
                impact=0.0,
                algorithm="ETC.Controller",
                model_version=MODULE_VERSION,
                reference_id=None,
            )

            if before_memory_id is not None:

                result["parameter_history_ids"].append(
                    before_memory_id
                )

        except Exception as exc:

            logger.warning(
                "BEFORE snapshot write failed: %s",
                exc,
            )

        # =====================================================
        # STEP 4 — LEARNING ENGINE
        # =====================================================

        logger.info(
            "ETC [%s] STEP 4 — "
            "ETCLearningEngine.run_batch() | "
            "batch_size=%s",
            league,
            len(selected_batch),
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

        already_processed = _safe_count(
            learning_result.get(
                "already_processed",
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
            "already_processed"
        ] = already_processed

        result[
            "learning_events"
        ] = learning_events

        result[
            "learned"
        ] = processed

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

        result[
            "errors"
        ] = max(
            failed,
            len(normalized_errors),
        )

        # =====================================================
        # STEP 5 — AFTER SNAPSHOT (НОВОЕ v3.0)
        # =====================================================

        logger.info(
            "ETC [%s] STEP 5 — AFTER snapshot",
            league,
        )

        after_params = self.db.get_current_parameters()

        # Проверяем, изменились ли параметры
        before_values = result.get("parameter_before", {})
        after_values = {
            "alpha": getattr(after_params, "alpha", 0.0),
            "beta": getattr(after_params, "beta", 0.0),
            "gamma": getattr(after_params, "gamma", 0.0),
            "delta": getattr(after_params, "delta", 0.0),
            "version": getattr(after_params, "version", 0),
        }

        result["parameter_after"] = after_values

        # Записываем AFTER в learning_memory
        try:

            after_memory_id = self.learning_memory.record(
                event_type="parameter_after",
                object_type=f"league:{league}",
                feature="model_parameters",
                before_value=result["parameter_before"],
                after_value=after_values,
                delta=None,
                reason=f"Параметры после обучения ETC batch (league={league})",
                confidence=1.0,
                impact=0.0,
                algorithm="ETC.Controller",
                model_version=MODULE_VERSION,
                reference_id=None,
            )

            if after_memory_id is not None:

                result["parameter_history_ids"].append(
                    after_memory_id
                )

        except Exception as exc:

            logger.warning(
                "AFTER snapshot write failed: %s",
                exc,
            )

        # =====================================================
        # STEP 6 — PARAMETER HISTORY (НОВОЕ v3.0)
        # =====================================================

        logger.info(
            "ETC [%s] STEP 6 — parameter_history",
            league,
        )

        # Сравниваем и записываем изменения
        param_names = ["alpha", "beta", "gamma", "delta"]

        for param_name in param_names:

            old_val = before_values.get(param_name, 0.0)
            new_val = after_values.get(param_name, 0.0)

            if old_val != new_val:

                try:

                    history_id = self.db.record_parameter_history(
                        parameter_name=param_name,
                        group_name="learning",
                        model_version=str(before_values.get("version", 0)),
                        old_value=float(old_val),
                        new_value=float(new_val),
                        delta=float(new_val) - float(old_val),
                        reason=f"ETC learning cycle (league={league})",
                        confidence=1.0,
                        reference_match_id=selected_ids[0] if selected_ids else None,
                    )

                    if history_id is not None:

                        result["parameter_changes"].append({
                            "parameter": param_name,
                            "old_value": old_val,
                            "new_value": new_val,
                            "delta": new_val - old_val,
                            "history_id": history_id,
                        })

                        result["parameter_history_ids"].append(
                            history_id
                        )

                        logger.info(
                            "ETC [%s] parameter changed: %s %.4f → %.4f",
                            league,
                            param_name,
                            old_val,
                            new_val,
                        )

                except Exception as exc:

                    logger.warning(
                        "parameter_history write failed for %s: %s",
                        param_name,
                        exc,
                    )

        # =====================================================
        # SUCCESS FLAG
        # =====================================================        engine_success = (
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
                "ETC batch полностью обработан. "
                f"Изменено параметров: {len(result['parameter_changes'])}"
            )

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
                f"Изменено параметров: {len(result['parameter_changes'])}"
            )

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
            "ETC [%s] FINISHED v3.0 | "
            "status=%s | "
            "batch=%s | "
            "total=%s | "
            "processed=%s | "
            "already=%s | "
            "failed=%s | "
            "learned=%s | "
            "memory=%s | "
            "param_changes=%s | "
            "batch_completed=%s | "
            "errors=%s",
            league,
            result["status"],
            result["batch_size"],
            total,
            processed,
            already_processed,
            failed,
            result["learned"],
            result["memory_events"],
            len(result["parameter_changes"]),
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

            # НОВОЕ v3.0
            "parameter_before": None,
            "parameter_after": None,
            "parameter_changes": [],
        }

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
        # BEFORE
        # =====================================================

        before_params = self.db.get_current_parameters()

        result["parameter_before"] = {
            "alpha": getattr(before_params, "alpha", 0.0),
            "beta": getattr(before_params, "beta", 0.0),
            "gamma": getattr(before_params, "gamma", 0.0),
            "delta": getattr(before_params, "delta", 0.0),
            "version": getattr(before_params, "version", 0),
        }

        # =====================================================
        # LEARNING
        # =====================================================

        logger.info(
            "ETC SINGLE MATCH STARTED v3.0 | "
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

            # =================================================
            # AFTER
            # =================================================

            after_params = self.db.get_current_parameters()

            result["parameter_after"] = {
                "alpha": getattr(after_params, "alpha", 0.0),
                "beta": getattr(after_params, "beta", 0.0),
                "gamma": getattr(after_params, "gamma", 0.0),
                "delta": getattr(after_params, "delta", 0.0),
                "version": getattr(after_params, "version", 0),
            }

            # =================================================
            # PARAMETER CHANGES
            # =================================================

            param_names = ["alpha", "beta", "gamma", "delta"]

            for param_name in param_names:

                old_val = result["parameter_before"].get(param_name, 0.0)
                new_val = result["parameter_after"].get(param_name, 0.0)

                if old_val != new_val:

                    try:

                        history_id = self.db.record_parameter_history(
                            parameter_name=param_name,
                            group_name="learning",
                            model_version=str(result["parameter_before"].get("version", 0)),
                            old_value=float(old_val),
                            new_value=float(new_val),
                            delta=float(new_val) - float(old_val),
                            reason=f"ETC single match learning (match_id={normalized_match_id})",
                            confidence=1.0,
                            reference_match_id=normalized_match_id,
                        )

                        if history_id is not None:

                            result["parameter_changes"].append({
                                "parameter": param_name,
                                "old_value": old_val,
                                "new_value": new_val,
                                "delta": new_val - old_val,
                                "history_id": history_id,
                            })

                    except Exception as exc:

                        logger.warning(
                            "parameter_history write failed for %s: %s",
                            param_name,
                            exc,
                        )

            # =================================================
            # SUCCESS
            # =================================================

            result[
                "status"
            ] = "completed"

            logger.info(
                "ETC SINGLE MATCH FINISHED v3.0 | "
                "match_id=%s | param_changes=%s",
                normalized_match_id,
                len(result["parameter_changes"]),
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
    Публичный batch API ETC v3.0.
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
    Публичный single-match API ETC v3.0.
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
            "ETC STATUS v3.0"
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
            "НОВОЕ В v3.0: BEFORE ≠ AFTER"
        )

        print(
            "-" * 70
        )

        print(
            "1. BEFORE — запись параметров до обучения"
        )

        print(
            "2. AFTER — запись параметров после обучения"
        )

        print(
            "3. parameter_history — все изменения"
        )

        print()
        print(
            "BEFORE ≠ AFTER соблюдается."
        )

        print()
        print(
            "ETC Controller v3.0 готов."
        )

    except Exception as exc:

        print(
            "ETC Controller unavailable: "
            f"{exc}"
        )

    print(
        "=" * 70
    )
