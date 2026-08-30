#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/etc_controller.py
============================================================

ETC CONTROLLER v4.1 (E-FINAL)
============================================================

ИСПРАВЛЕНИЯ v4.1 (E-FINAL):
    1. Добавлен Signal Adapter — _normalize_optimizer_signals()
    2. Унифицирован applied_count во всех уровнях
    3. Исправлена revision chain — последовательное применение
    4. Review Gate — ВСЕ proposals → pending (НЕТ auto-apply)
    5. Убраны parameter_before/parameter_after из LearningMemory
    6. process_match() оставлен без оптимизации (фактическое обучение)
    7. Версия обновлена до 4.1

ИСПРАВЛЕНИЯ v4.0:
    1. Подключен LearningAnalyzer для генерации signals
    2. Подключен ParameterOptimizer для создания proposals
    3. Добавлен Review Gate (approved/rejected/pending)
    4. Применение только approved proposals через Parameter State API
    5. Убрана самостоятельная запись parameter_history (делегировано в State API)
    6. Убраны жёсткие alpha/beta/gamma/delta — используется get_current_parameter_state()
    7. BEFORE/AFTER — только как snapshots (без сравнения и записи history)
    8. learned = количество реально применённых изменений
    9. Добавлены секции analysis, optimization, review, apply в результат

НАЗНАЧЕНИЕ
-----------

Верхний оркестратор ETC v4.1.

КОНТРАКТ v4.1:

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
    ETCController v4.1
      │
      ├── BEFORE snapshot (параметры до) — только диагностика
      ├── ETCLearningEngine v2.0
      │   ├── process_match()
      │   └── run_batch()
      ├── LearningAnalyzer v2.2
      │   └── signals
      ├── Signal Adapter (НОВОЕ v4.1)
      │   └── normalized signals
      ├── ParameterOptimizer v2.3
      │   └── proposals
      ├── Review Gate (v4.1 — ВСЕ → pending)
      │   ├── approved → []
      │   ├── rejected → []
      │   └── pending → все proposals
      ├── Apply (только для approved — но их нет)
      ├── AFTER snapshot (параметры после) — только диагностика
      └── parameter_revision — из State API
      ↓
    LEARNING MEMORY (только learning events, НЕ snapshots)
      ↓
    SQLite

ГРАНИЦЫ ETCController v4.1
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
    - выполняет DROP;
    - пишет SQL напрямую;
    - записывает parameter_history самостоятельно;
    - пишет parameter_before/after в LearningMemory.

ETCController ТОЛЬКО:
    1. получает batch от BatchController;
    2. записывает BEFORE snapshot в результат (НЕ в LearningMemory);
    3. передаёт batch в ETCLearningEngine;
    4. получает результат;
    5. вызывает LearningAnalyzer для анализа;
    6. адаптирует signals через Signal Adapter;
    7. вызывает ParameterOptimizer для создания proposals;
    8. применяет Review Gate (ВСЕ → pending);
    9. записывает AFTER snapshot в результат (НЕ в LearningMemory);
    10. агрегирует результат.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


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

from app.etc.learning_analyzer import (
    LearningAnalyzer,
)

from app.etc.parameter_optimizer import (
    ParameterOptimizer,
)


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

MODULE_NAME = "ETC Controller"
MODULE_VERSION = "4.1"


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
# ETC CONTROLLER v4.1
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center v4.1.

    Контроллер не содержит математической логики.

    Новое в v4.1:
        - Signal Adapter
        - Review Gate — ВСЕ → pending (НЕТ auto-apply)
        - Snapshots НЕ пишутся в LearningMemory
        - Исправлена revision chain
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
        learning_analyzer: Optional[
            LearningAnalyzer
        ] = None,
        optimizer: Optional[
            ParameterOptimizer
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

        self.learning_analyzer = (
            learning_analyzer
            or LearningAnalyzer(
                db=self.db
            )
        )

        self.optimizer = (
            optimizer
            or ParameterOptimizer()
        )

        # Храним ID последнего batch для status()
        self._last_batch_id: Optional[str] = None

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

            "LearningAnalyzer.analyze": getattr(
                self.learning_analyzer,
                "analyze",
                None,
            ),

            "ParameterOptimizer.run": getattr(
                self.optimizer,
                "run",
                None,
            ),

            "FAJDatabase.get_current_parameter_state": getattr(
                self.db,
                "get_current_parameter_state",
                None,
            ),

            "FAJDatabase.apply_parameter_change": getattr(
                self.db,
                "apply_parameter_change",
                None,
            ),
        }

        missing = [
            name
            for name, method in required.items()
            if not callable(method)
        ]

        # Получаем pending_matches из BatchController
        pending = 0
        try:
            for league in BATCH_RULES.keys():
                check_result = self.batch_controller.check(league)
                if check_result.get("status") == STATUS_READY:
                    pending += check_result.get("new_matches", 0)
        except Exception:
            pass

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

            "learning_analyzer": (
                self.learning_analyzer
                .__class__.__name__
            ),

            "optimizer": (
                self.optimizer
                .__class__.__name__
            ),

            "pending_matches": pending,

            "last_batch_id": self._last_batch_id,

            "features": {
                "learning_analyzer": True,
                "parameter_optimizer": True,
                "review_gate": True,
                "signal_adapter": True,
                "parameter_state_api": True,
                "append_only": True,
                "snapshots_in_learning_memory": False,  # НОВОЕ v4.1
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
                "direct_parameter_history_write",
                "snapshots_in_learning_memory",  # НОВОЕ v4.1
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
        Запускает ETC batch pipeline с новым потоком v4.1.
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

            "already_processed_match_ids": [],

            "batches": [],

            "message": "",

            # Анализ и оптимизация
            "analysis": None,
            "optimization": None,
            "review": None,
            "apply": None,

            # BEFORE/AFTER (только диагностика, НЕ в LearningMemory)
            "parameter_before": None,
            "parameter_after": None,
            "parameter_revision_before": 0,
            "parameter_revision_after": 0,

            # ID для диагностики (только learning events)
            "memory_ids": [],
            "batch_memory_ids": [],
        }

        logger.info(
            "=================================================="
        )

        logger.info(
            "ETC RUN STARTED v4.1 | "
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

                result[
                    "already_processed_match_ids"
                ].extend(
                    _normalize_match_ids(
                        league_result.get(
                            "already_processed_match_ids"
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
                # PARAMETER STATE (диагностика)
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
                    result["parameter_before"] = param_before

                if param_after is not None:
                    result["parameter_after"] = param_after

                revision_before = league_result.get("parameter_revision_before", 0)
                revision_after = league_result.get("parameter_revision_after", 0)

                if revision_before > 0:
                    result["parameter_revision_before"] = revision_before

                if revision_after > 0:
                    result["parameter_revision_after"] = revision_after

                # ---------------------------------------------
                # АНАЛИЗ / ОПТИМИЗАЦИЯ / REVIEW
                # ---------------------------------------------

                analysis = league_result.get("analysis")
                if analysis:
                    result["analysis"] = analysis

                optimization = league_result.get("optimization")
                if optimization:
                    result["optimization"] = optimization

                review = league_result.get("review")
                if review:
                    result["review"] = review

                apply_result = league_result.get("apply")
                if apply_result:
                    result["apply"] = apply_result

                # ---------------------------------------------
                # MEMORY IDS (только learning events)
                # ---------------------------------------------

                result["memory_ids"].extend(
                    league_result.get("memory_ids", [])
                )

                result["batch_memory_ids"].extend(
                    league_result.get("batch_memory_ids", [])
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

            result[
                "already_processed_match_ids"
            ] = _normalize_match_ids(
                result[
                    "already_processed_match_ids"
                ]
            )

            # Сохраняем ID последнего batch
            if result["batches"]:
                last_batch = result["batches"][-1]
                self._last_batch_id = last_batch.get("batch_check", {}).get("batch_fingerprint")

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
                "ETC RUN FINISHED v4.1 | "
                "status=%s | "
                "processed=%s | "
                "already_processed=%s | "
                "failed=%s | "
                "learned=%s | "
                "memory=%s | "
                "revision=%s→%s | "
                "errors=%s",
                result["status"],
                result["processed"],
                result["already_processed"],
                result["failed"],
                result["learned"],
                result["memory_events"],
                result["parameter_revision_before"],
                result["parameter_revision_after"],
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
    # SIGNAL ADAPTER (НОВОЕ v4.1)
    # ========================================================

    def _normalize_optimizer_signals(
        self,
        signals: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Адаптирует signals от LearningAnalyzer к формату ParameterOptimizer.

        LearningAnalyzer (v2.2):
            {
                "signal_type": str,
                "error_type": str,
                "cause_type": str,
                "matches": List[int],
                "event_count": int,
                "unique_match_count": int,
                "average_severity": float,
                "average_xg_error": Optional[float],
                "average_confidence": float,
                "average_impact": float,
                "signal_strength": float,
                "priority": str,
                "recommendations": List[str],
            }

        ParameterOptimizer (v2.3):
            {
                "error_type": str,
                "cause_type": str,
                "matches": List[int],
                "count": int,           # ← unique_match_count
                "confidence": float,    # ← average_confidence
                "signal_strength": float,
                "average_severity": float,
            }
        """
        normalized = []

        for signal in signals:
            if not isinstance(signal, dict):
                continue

            # Базовая нормализация
            normalized_signal = {
                "error_type": signal.get("error_type", "unknown"),
                "cause_type": signal.get("cause_type", "unknown"),
                "matches": signal.get("matches", []),
                "count": signal.get("unique_match_count", 0),
                "confidence": signal.get("average_confidence", 0.0),
                "signal_strength": signal.get("signal_strength", 0.0),
                "average_severity": signal.get("average_severity", 0.0),
            }

            # Опциональные поля
            if "average_xg_error" in signal:
                normalized_signal["average_xg_error"] = signal["average_xg_error"]

            if "priority" in signal:
                normalized_signal["priority"] = signal["priority"]

            if "event_count" in signal:
                normalized_signal["event_count"] = signal["event_count"]

            normalized.append(normalized_signal)

        return normalized

    # ========================================================
    # REVIEW GATE (НОВОЕ v4.1 — ВСЕ → pending)
    # ========================================================

    def _review_proposals(
        self,
        proposals: List[Dict[str, Any]],
        league: str,
    ) -> Dict[str, Any]:
        """
        Review Gate — ВСЕ proposals требуют ручного review.

        ВАЖНО:
            - НЕТ автоматического одобрения.
            - Никаких auto-apply, пока не накоплена статистика.

        Returns:
            {
                "approved": List[Dict],   # всегда []
                "rejected": List[Dict],
                "pending": List[Dict],
                "total": int,
            }
        """
        rejected = []
        pending = []

        for proposal in proposals:
            # Конфликтные → pending (требуют ручного review)
            if proposal.get("status") == "conflict_review":
                pending.append(proposal)
                continue

            # ВСЕ proposals → pending
            # Никакого auto-approve, даже для high/medium
            pending.append(proposal)

        logger.info(
            "REVIEW GATE v4.1 | league=%s | pending=%s | rejected=%s",
            league,
            len(pending),
            len(rejected),
        )

        return {
            "approved": [],   # всегда пусто
            "rejected": rejected,
            "pending": pending,
            "total": len(proposals),
        }

    # ========================================================
    # APPLY (v4.1 — с revision chain)
    # ========================================================

    def _apply_proposals(
        self,
        proposals: List[Dict[str, Any]],
        league: str,
        expected_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Применяет approved proposals через Parameter State API.

        ВАЖНО v4.1:
            - revision chain поддерживается корректно
            - после каждого применения обновляется expected_revision
            - applied_count унифицирован

        Returns:
            {
                "attempted": int,
                "applied_count": int,
                "failed_count": int,
                "history_ids": List[int],
                "results": List[Dict],
            }
        """
        applied_count = 0
        failed_count = 0
        history_ids = []
        results = []

        # Текущая ревизия для chain
        current_expected = expected_revision

        for proposal in proposals:
            parameter_name = proposal.get("parameter_name")
            proposed_value = proposal.get("proposed_value")
            confidence = proposal.get("confidence", 1.0)
            reason = proposal.get("reason", f"ETC batch (league={league})")

            if not parameter_name or proposed_value is None:
                failed_count += 1
                results.append({
                    "parameter": parameter_name,
                    "status": "failed",
                    "reason": "Missing parameter_name or proposed_value",
                })
                continue

            try:
                apply_result = self.db.apply_parameter_change(
                    parameter_name=parameter_name,
                    new_value=float(proposed_value),
                    reason=reason,
                    confidence=confidence,
                    expected_revision=current_expected,  # ← актуальная revision
                    reference_match_id=None,
                    group_name="learning",
                    category="etc",
                )

                if apply_result.get("status") == "applied":
                    applied_count += 1
                    results.append({
                        "parameter": parameter_name,
                        "status": "applied",
                        "old_value": apply_result.get("old_value"),
                        "new_value": apply_result.get("new_value"),
                        "delta": apply_result.get("delta"),
                        "revision": apply_result.get("revision"),
                        "history_id": apply_result.get("history_id"),
                    })

                    if apply_result.get("history_id"):
                        history_ids.append(apply_result["history_id"])

                    # Обновляем revision для следующего proposal
                    current_expected = apply_result.get("revision")

                    logger.info(
                        "ETC proposal APPLIED | league=%s | %s: %s → %s | revision=%s",
                        league,
                        parameter_name,
                        apply_result.get("old_value"),
                        apply_result.get("new_value"),
                        apply_result.get("revision"),
                    )

                elif apply_result.get("status") == "no_change":
                    # Значение не изменилось — считаем успешным
                    results.append({
                        "parameter": parameter_name,
                        "status": "no_change",
                        "old_value": apply_result.get("old_value"),
                        "new_value": apply_result.get("new_value"),
                    })
                    # revision не меняется

                else:
                    failed_count += 1
                    results.append({
                        "parameter": parameter_name,
                        "status": "failed",
                        "reason": apply_result.get("message", "Unknown error"),
                    })

            except Exception as exc:
                failed_count += 1
                results.append({
                    "parameter": parameter_name,
                    "status": "failed",
                    "reason": str(exc),
                })
                logger.exception(
                    "ETC proposal APPLY FAILED | league=%s | %s",
                    league,
                    parameter_name,
                )

        return {
            "attempted": len(proposals),
            "applied_count": applied_count,  # ← унифицировано
            "failed_count": failed_count,
            "history_ids": history_ids,
            "results": results,
        }

    # ========================================================
    # SINGLE LEAGUE (v4.1 — НЕ пишет snapshots в LearningMemory)
    # ========================================================

    def _run_league(
        self,
        league: str,
        season_id: Optional[int],
        limit: Optional[int],
        force: bool,
    ) -> Dict[str, Any]:
        """
        Полный цикл одного турнира с BEFORE/AFTER и анализом.

        ВАЖНО v4.1:
            - BEFORE/AFTER — ТОЛЬКО диагностика (НЕ в LearningMemory)
            - Сигналы проходят через Signal Adapter
            - Review Gate — ВСЕ → pending
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

            "already_processed_match_ids": [],

            "batch_check": None,

            "selected_match_ids": [],

            "learning_result": None,

            "message": "",

            "force": bool(force),

            # Анализ и оптимизация
            "analysis": None,
            "optimization": None,
            "review": None,
            "apply": None,

            # BEFORE/AFTER (только диагностика)
            "parameter_before": None,
            "parameter_after": None,
            "parameter_revision_before": 0,
            "parameter_revision_after": 0,

            # Memory IDs (только learning events)
            "memory_ids": [],
            "batch_memory_ids": [],
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
            "ETC [%s] STEP 2 — BatchController.get_learning_batch()",
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
        # STEP 3 — BEFORE SNAPSHOT (ТОЛЬКО ДИАГНОСТИКА)
        # =====================================================

        logger.info(
            "ETC [%s] STEP 3 — BEFORE snapshot (diagnostic only)",
            league,
        )

        before_state = self.db.get_current_parameter_state()

        result["parameter_before"] = before_state.get("parameters", {})
        result["parameter_revision_before"] = before_state.get("revision", 0)

        # ⚠️ НЕ пишем parameter_before в LearningMemory

        # =====================================================
        # STEP 4 — LEARNING ENGINE
        # =====================================================

        logger.info(
            "ETC [%s] STEP 4 — ETCLearningEngine.run_batch() | batch_size=%s",
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

        already_processed_ids = learning_result.get("already_processed_match_ids", [])

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

        # =====================================================
        # MEMORY IDS (только learning events)
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

        result[
            "already_processed_match_ids"
        ] = _normalize_match_ids(
            already_processed_ids
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
        # STEP 5 — LEARNING ANALYZER
        # =====================================================

        engine_success = (
            learning_result.get(
                "success"
            )
        )

        if engine_success is True:

            logger.info(
                "ETC [%s] STEP 5 — LearningAnalyzer.analyze()",
                league,
            )

            try:

                analysis_result = self.learning_analyzer.analyze(
                    limit=1000,
                )

                result["analysis"] = analysis_result

                # Получаем raw signals
                raw_signals = analysis_result.get("signals", [])

                # =====================================================
                # STEP 5.5 — SIGNAL ADAPTER (НОВОЕ v4.1)
                # =====================================================

                signals = self._normalize_optimizer_signals(raw_signals)

                logger.info(
                    "ETC [%s] Signals normalized | raw=%s | normalized=%s",
                    league,
                    len(raw_signals),
                    len(signals),
                )

                # =====================================================
                # STEP 6 — PARAMETER OPTIMIZER
                # =====================================================

                if signals:

                    logger.info(
                        "ETC [%s] STEP 6 — ParameterOptimizer.run() | signals=%s",
                        league,
                        len(signals),
                    )

                    current_params = result["parameter_before"]

                    optimization_result = self.optimizer.run(
                        signals=signals,
                        current_parameters=current_params,
                    )

                    result["optimization"] = optimization_result

                    proposals = optimization_result.get("proposals", [])

                    logger.info(
                        "ETC [%s] ParameterOptimizer | signals=%s | proposals=%s | conflicts=%s",
                        league,
                        len(signals),
                        len(proposals),
                        optimization_result.get("conflict_count", 0),
                    )

                    # =====================================================
                    # STEP 7 — REVIEW GATE (v4.1 — ВСЕ → pending)
                    # =====================================================

                    if proposals:

                        logger.info(
                            "ETC [%s] STEP 7 — Review Gate (v4.1 — all → pending)",
                            league,
                            len(proposals),
                        )

                        review_result = self._review_proposals(
                            proposals,
                            league=league,
                        )

                        result["review"] = review_result

                        # Применяем approved (но их нет — все pending)
                        # Код apply остаётся для будущего использования
                        approved = review_result.get("approved", [])

                        if approved:
                            # Этот блок не будет выполняться (approved всегда [])
                            apply_result = self._apply_proposals(
                                approved,
                                league=league,
                                expected_revision=result["parameter_revision_before"],
                            )
                            result["apply"] = apply_result

                            # Обновляем learned
                            result["learned"] = apply_result.get("applied_count", 0)

                            # Обновляем memory_ids
                            history_ids = apply_result.get("history_ids", [])
                            if history_ids:
                                result["memory_ids"].extend(history_ids)

                            # AFTER snapshot
                            after_state = self.db.get_current_parameter_state()
                            result["parameter_after"] = after_state.get("parameters", {})
                            result["parameter_revision_after"] = after_state.get("revision", 0)

                    # Нет approved — parameter_after = parameter_before
                    if not result.get("parameter_after"):
                        result["parameter_after"] = result["parameter_before"]
                        result["parameter_revision_after"] = result["parameter_revision_before"]

                else:
                    result["parameter_after"] = result["parameter_before"]
                    result["parameter_revision_after"] = result["parameter_revision_before"]

            except Exception as exc:

                logger.exception(
                    "ETC [%s] Analysis/Optimization failed: %s",
                    league,
                    exc,
                )

                result["errors"] += 1
                result["message"] = f"Analysis/Optimization failed: {exc}"

                result["parameter_after"] = result["parameter_before"]
                result["parameter_revision_after"] = result["parameter_revision_before"]

        else:

            logger.info(
                "ETC [%s] SKIPPED analysis (learning success=False)",
                league,
            )

            result["parameter_after"] = result["parameter_before"]
            result["parameter_revision_after"] = result["parameter_revision_before"]

        # =====================================================
        # STEP 8 — FINAL STATUS
        # =====================================================

        batch_completed = (
            learning_result.get(
                "batch_completed"
            )
        )

        learning_status = (
            _extract_status(
                learning_result
            )
        )

        applied_changes = result.get("learned", 0)

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
                f"ETC batch полностью обработан. "
                f"Создано proposals: {len(result.get('optimization', {}).get('proposals', []))} "
                f"(все ожидают review)"
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
                f"ETC batch обработан частично. "
                f"Создано proposals: {len(result.get('optimization', {}).get('proposals', []))} "
                f"(все ожидают review)"
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
            "ETC [%s] FINISHED v4.1 | "
            "status=%s | "
            "batch=%s | "
            "total=%s | "
            "processed=%s | "
            "already=%s | "
            "failed=%s | "
            "learned=%s | "
            "memory=%s | "
            "revision=%s→%s | "
            "proposals=%s | "
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
            result["parameter_revision_before"],
            result["parameter_revision_after"],
            len(result.get("optimization", {}).get("proposals", [])),
            batch_completed,
            result["errors"],
        )

        return result

    # ========================================================
    # SINGLE MATCH (v4.1 — без оптимизации)
    # ========================================================

    def process_match(
        self,
        match_id: int,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Запускает ETC для одного матча.

        ВАЖНО:
            - Только фактическое обучение
            - БЕЗ ParameterOptimizer
            - БЕЗ Review Gate
            - БЕЗ Apply
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

            # Только learning events
            "memory_ids": [],
            "marker_id": None,

            "parameter_before": None,
            "parameter_after": None,
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
        # BEFORE (диагностика)
        # =====================================================

        before_state = self.db.get_current_parameter_state()
        result["parameter_before"] = before_state.get("parameters", {})

        # =====================================================
        # LEARNING
        # =====================================================

        logger.info(
            "ETC SINGLE MATCH STARTED v4.1 | "
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
            # AFTER (диагностика)
            # =================================================

            after_state = self.db.get_current_parameter_state()
            result["parameter_after"] = after_state.get("parameters", {})

            # =================================================
            # SUCCESS
            # =================================================

            result[
                "status"
            ] = "completed"

            logger.info(
                "ETC SINGLE MATCH FINISHED v4.1 | "
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
    Публичный batch API ETC v4.1.
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
    Публичный single-match API ETC v4.1.
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
            "ETC STATUS v4.1 (E-FINAL)"
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
            "НОВОЕ В v4.1 (E-FINAL):"
        )

        print(
            "-" * 70
        )

        print(
            "1. Signal Adapter — нормализация signals"
        )

        print(
            "2. Review Gate — ВСЕ → pending (НЕТ auto-apply)"
        )

        print(
            "3. Snapshots НЕ пишутся в LearningMemory"
        )

        print(
            "4. Исправлена revision chain"
        )

        print(
            "5. applied_count унифицирован"
        )

        print()
        print(
            "ETC Controller v4.1 (E-FINAL) готов."
        )

    except Exception as exc:

        print(
            "ETC Controller unavailable: "
            f"{exc}"
        )

    print(
        "=" * 70
    )
