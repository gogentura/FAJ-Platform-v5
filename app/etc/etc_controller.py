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

ETC — отдельный контур эволюции модели после появления
новых фактов матчей.

АРХИТЕКТУРНАЯ ЦЕПОЧКА
---------------------

    MATCH_RESULT + MATCH_STATISTICS
                    │
                    ▼
          ┌──────────────────┐
          │ BatchController  │
          └────────┬─────────┘
                   │
                   ▼
          завершённые матчи
                   │
                   ▼
          ┌──────────────────┐
          │ Statistical      │
          │ Analyzer         │
          └────────┬─────────┘
                   │
                   ▼
          объективные факты
                   │
                   ▼
          ┌──────────────────┐
          │ LearningEngine   │
          └────────┬─────────┘
                   │
          ┌────────┼──────────┐
          ▼        ▼          ▼
       ошибки    xG         rating /
       прогноза calibration  parameters
          │        │          │
          └────────┴──────────┘
                   │
                   ▼
          ┌──────────────────┐
          │ LearningMemory   │
          └────────┬─────────┘
                   │
                   ▼
              SQLite / DB

РОЛЬ
----
ETCController только координирует pipeline.

Он НЕ:

    - не считает xG;
    - не классифицирует ошибки;
    - не обновляет FAJ Rating;
    - не оптимизирует параметры;
    - не пишет learning_memory напрямую;
    - не изменяет predictions;
    - не изменяет match_results;
    - не изменяет match_statistics;
    - не управляет календарём;
    - не создаёт прогнозы;
    - не изменяет database.py;
    - не удаляет исторические данные.

ВСЕ ОПЕРАЦИИ С ДАННЫМИ ВЫПОЛНЯЮТСЯ
НИЖЕЛЕЖАЩИМИ ETC-МОДУЛЯМИ ЧЕРЕЗ FAJDatabase.

ВАЖНО
------
ETC работает только после появления фактов матча.

Цикл:

    PREDICTION
         ↓
       MATCH
         ↓
    IMPORT FACTS
         ↓
    MATCH_RESULT
    MATCH_STATISTICS
         ↓
       ETC
         ↓
      LEARNING
         ↓
    NEXT PREDICTION

ИДЕМПОТЕНТНОСТЬ
--------------
BatchController отвечает за то, какие матчи ещё не прошли ETC.

ETCController не должен повторно обрабатывать уже
закрытые batch-записи без force=True.

ОШИБКИ
------
Ошибка одного матча не должна уничтожать историю
остальных успешно обработанных матчей.

Успешно обработанные матчи помечаются processed.

Неуспешные матчи остаются доступными для следующего ETC-run.

============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.database import FAJDatabase

from app.etc.batch_controller import BatchController
from app.etc.statistical_analyzer import StatisticalAnalyzer
from app.etc.learning_engine import LearningEngine


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.0"
MODULE_NAME = "ETC Controller"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает timestamp текущего ETC-run.
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

        return int(value)

    except (TypeError, ValueError):
        return default


# ============================================================
# ETC CONTROLLER
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center.

    Никакой математической логики внутри класса нет.

    Его задача:

        1. получить batch;
        2. передать матч StatisticalAnalyzer;
        3. передать результат LearningEngine;
        4. собрать итог;
        5. закрыть только успешно обработанные записи batch.

    Все реальные изменения выполняются ETC-модулями ниже.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.batch_controller = BatchController(
            db=self.db
        )

        self.statistical_analyzer = StatisticalAnalyzer(
            db=self.db
        )

        self.learning_engine = LearningEngine(
            db=self.db
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        """
        Возвращает текущее состояние ETC.

        Метод read-only.

        Никаких изменений SQLite не выполняется.
        """

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "ready",
            "timestamp": _now(),
            "pending_matches": None,
        }

        try:

            pending = (
                self.batch_controller.get_pending_count()
            )

            result["pending_matches"] = _safe_count(
                pending,
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
        Выполняет один полный ETC-run.

        PIPELINE:

            STEP 1
                BatchController

            STEP 2
                StatisticalAnalyzer

            STEP 3
                LearningEngine

            STEP 4
                BatchController.mark_processed()

        ВАЖНО:

            processed != batch_size

        если часть матчей завершилась ошибкой.

        Только реально успешно обработанные матчи
        передаются в mark_processed().
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

            "errors": 0,

            "learning_events": 0,
            "memory_events": 0,

            "failed_matches": [],

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
                "ETC STEP 1/4 — BUILD BATCH"
            )

            batch = self.batch_controller.create_batch(
                limit=limit,
                force=force,
            )

            if not batch:

                result["status"] = (
                    "nothing_to_process"
                )

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
            # STEP 2 — STATISTICAL ANALYSIS
            # =================================================

            logger.info(
                "ETC STEP 2/4 — STATISTICAL ANALYSIS"
            )

            successful_analysis: List[
                Tuple[Any, int, Dict[str, Any]]
            ] = []

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

                    analysis = (
                        self.statistical_analyzer
                        .analyze_match(
                            match_id
                        )
                    )

                    # -----------------------------------------
                    # Статистический анализ обязан сообщить,
                    # действительно ли факт пригоден.
                    # -----------------------------------------

                    if not isinstance(
                        analysis,
                        dict,
                    ):

                        raise ValueError(
                            "StatisticalAnalyzer "
                            "вернул не-dict"
                        )

                    if not analysis.get(
                        "success",
                        False,
                    ):

                        errors = analysis.get(
                            "errors",
                            [],
                        )

                        raise ValueError(
                            "Статистический анализ "
                            f"неуспешен: {errors}"
                        )

                    successful_analysis.append(
                        (
                            batch_item,
                            match_id,
                            analysis,
                        )
                    )

                    result["analyzed"] += 1

                    logger.info(
                        "ETC analysis OK: match_id=%s",
                        match_id,
                    )

                except Exception as exc:

                    result["errors"] += 1

                    result["failed_matches"].append(
                        {
                            "match_id": match_id,
                            "stage": "statistical_analysis",
                            "error": str(exc),
                        }
                    )

                    logger.exception(
                        "ETC statistical analysis failed: "
                        "match_id=%s",
                        match_id,
                    )

                    # -----------------------------------------
                    # force НЕ превращает неуспешный матч
                    # в успешный.
                    #
                    # force означает:
                    # продолжить обработку остальных матчей.
                    # -----------------------------------------

                    if not force:

                        raise

            # =================================================
            # STEP 3 — LEARNING ENGINE
            # =================================================

            logger.info(
                "ETC STEP 3/4 — LEARNING ENGINE"
            )

            successful_learning: List[Any] = []

            for (
                batch_item,
                match_id,
                analysis,
            ) in successful_analysis:

                try:

                    learning_result = (
                        self.learning_engine
                        .process_analysis(
                            match_id=match_id,
                            analysis=analysis,
                        )
                    )

                    # -----------------------------------------
                    # LearningEngine должен вернуть dict.
                    # -----------------------------------------

                    if not isinstance(
                        learning_result,
                        dict,
                    ):

                        raise ValueError(
                            "LearningEngine "
                            "вернул не-dict"
                        )

                    # -----------------------------------------
                    # Если LearningEngine явно сообщает
                    # success=False — матч НЕ закрываем.
                    # -----------------------------------------

                    if (
                        "success" in learning_result
                        and not learning_result.get(
                            "success"
                        )
                    ):

                        raise ValueError(
                            "LearningEngine "
                            f"неуспешен: "
                            f"{learning_result.get('errors', [])}"
                        )

                    successful_learning.append(
                        batch_item
                    )

                    result["learned"] += 1

                    # -----------------------------------------
                    # Счётчики ETC
                    # -----------------------------------------

                    result["learning_events"] += (
                        self._extract_learning_count(
                            learning_result,
                            "learning_events",
                            "events",
                        )
                    )

                    result["memory_events"] += (
                        self._extract_learning_count(
                            learning_result,
                            "memory_events",
                            "memory",
                        )
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
                        "ETC learning failed: "
                        "match_id=%s",
                        match_id,
                    )

                    if not force:

                        raise

            # =================================================
            # STEP 4 — MARK SUCCESSFULLY PROCESSED
            # =================================================

            logger.info(
                "ETC STEP 4/4 — MARK PROCESSED"
            )

            # -------------------------------------------------
            # КРИТИЧЕСКОЕ ПРАВИЛО:
            #
            # Нельзя закрывать весь batch.
            #
            # Закрываем только те элементы,
            # которые прошли StatisticalAnalyzer
            # И LearningEngine.
            # -------------------------------------------------

            if successful_learning:

                processed = (
                    self.batch_controller
                    .mark_processed(
                        successful_learning
                    )
                )

                result["processed"] = _safe_count(
                    processed,
                    len(successful_learning),
                )

            else:

                result["processed"] = 0

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

                result["status"] = (
                    "completed_with_errors"
                )

                result["message"] = (
                    "ETC обработал часть batch. "
                    "Ошибочные матчи оставлены "
                    "для последующей обработки."
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
        Обрабатывает один матч через ETC.

        Используется:

            - Match Laboratory;
            - диагностика;
            - ручная проверка ETC;
            - разработка.

        ВАЖНО:

        Этот метод не закрывает batch-запись автоматически.

        Для пакетной обработки жизненным циклом управляет
        run().
        """

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "match_id": match_id,

            "status": "started",

            "analysis": None,
            "learning": None,

            "error": None,
        }

        try:

            # =================================================
            # ANALYSIS
            # =================================================

            logger.info(
                "ETC single match analysis: match_id=%s",
                match_id,
            )

            analysis = (
                self.statistical_analyzer
                .analyze_match(
                    match_id
                )
            )

            result["analysis"] = analysis

            if not isinstance(
                analysis,
                dict,
            ):

                raise ValueError(
                    "StatisticalAnalyzer "
                    "вернул не-dict"
                )

            if not analysis.get(
                "success",
                False,
            ):

                raise ValueError(
                    "Статистический анализ "
                    f"неуспешен: "
                    f"{analysis.get('errors', [])}"
                )

            # =================================================
            # LEARNING
            # =================================================

            logger.info(
                "ETC single match learning: match_id=%s",
                match_id,
            )

            learning = (
                self.learning_engine
                .process_analysis(
                    match_id=match_id,
                    analysis=analysis,
                )
            )

            result["learning"] = learning

            if not isinstance(
                learning,
                dict,
            ):

                raise ValueError(
                    "LearningEngine "
                    "вернул не-dict"
                )

            if (
                "success" in learning
                and not learning.get("success")
            ):

                raise ValueError(
                    "LearningEngine "
                    f"неуспешен: "
                    f"{learning.get('errors', [])}"
                )

            result["status"] = "completed"

            logger.info(
                "ETC single match completed: "
                "match_id=%s",
                match_id,
            )

            return result

        except Exception as exc:

            result["status"] = "failed"
            result["error"] = str(exc)

            logger.exception(
                "ETC single match failed: "
                "match_id=%s",
                match_id,
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
            sqlite3.Row
            объекты с attribute match_id
            объекты с attribute id
        """

        if item is None:
            return None

        # ----------------------------------------------------
        # INT
        # ----------------------------------------------------

        if isinstance(item, int):
            return item

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(item, dict):

            value = item.get(
                "match_id"
            )

            if value is None:
                value = item.get("id")

            return _safe_int(value)

        # ----------------------------------------------------
        # SQLITE ROW / MAPPING
        # ----------------------------------------------------

        try:

            value = item["match_id"]

            return _safe_int(value)

        except (
            KeyError,
            TypeError,
            IndexError,
        ):

            pass

        except Exception:

            pass

        try:

            value = item["id"]

            return _safe_int(value)

        except (
            KeyError,
            TypeError,
            IndexError,
        ):

            pass

        except Exception:

            pass

        # ----------------------------------------------------
        # OBJECT ATTRIBUTE
        # ----------------------------------------------------

        try:

            value = getattr(
                item,
                "match_id",
                None,
            )

            if value is not None:

                return _safe_int(value)

        except Exception:

            pass

        try:

            value = getattr(
                item,
                "id",
                None,
            )

            if value is not None:

                return _safe_int(value)

        except Exception:

            pass

        return None

    # ========================================================
    # LEARNING COUNTERS
    # ========================================================

    @staticmethod
    def _extract_learning_count(
        learning_result: Dict[str, Any],
        primary_key: str,
        fallback_key: str,
    ) -> int:
        """
        Извлекает количество событий из ответа
        LearningEngine.

        Основные ключи:

            learning_events
            memory_events

        Допускаются legacy aliases:

            events
            memory
        """

        value = learning_result.get(
            primary_key
        )

        if value is None:

            value = learning_result.get(
                fallback_key
            )

        return _safe_count(
            value,
            0,
        )


# ============================================================
# PUBLIC API
# ============================================================

def run_etc(
    db: Optional[FAJDatabase] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Главная публичная точка входа ETC.

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
    Публичная точка входа для обработки одного матча.

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
    Публичная read-only точка получения состояния ETC.
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

        status = controller.status()

        print()
        print("ETC STATUS")
        print("-" * 70)

        for key, value in status.items():
            print(
                f"{key}: {value}"
            )

    except Exception as exc:

        print(
            f"ETC controller unavailable: {exc}"
        )

    print("=" * 70)
