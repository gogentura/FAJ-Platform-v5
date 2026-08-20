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

ЦЕПОЧКА:

    ETC Controller
         ↓
    Batch Controller
         ↓
    Observed XG
         ↓
    Statistical Analyzer
         ↓
    ETC Learning Engine
         ↓
    Learning Memory
         ↓
    SQLite / database.py

ПРИНЦИПЫ
--------
- database.py НЕ изменяется этим модулем;
- старые факты НЕ удаляются;
- learning_memory append-only;
- ETC работает только с завершёнными матчами;
- ошибки одного этапа останавливают текущий ETC-run;
- каждый запуск имеет собственный статус;
- ETC не управляет календарём;
- ETC не создаёт прогнозы;
- ETC не заменяет основной app/learning_engine.py.

РОЛЬ
----
Это координатор ETC, а не математический движок.
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.database import FAJDatabase

from app.etc.batch_controller import BatchController
from app.etc.statistical_analyzer import StatisticalAnalyzer
from app.etc.learning_engine import LearningEngine


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Controller"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


# ============================================================
# ETC CONTROLLER
# ============================================================

class ETCController:
    """
    Главный оркестратор Evolution Training Center.

    ETCController не содержит математическую логику.
    Его задача — правильно организовать ETC pipeline.
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

        Метод специально не изменяет БД.
        """

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "ready",
            "timestamp": _now(),
        }

        try:
            pending = self.batch_controller.get_pending_count()

            result["pending_matches"] = int(
                pending if pending is not None else 0
            )

        except Exception as exc:
            logger.warning(
                "Unable to determine ETC pending count: %s",
                exc,
            )

            result["pending_matches"] = None
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

        Порядок:

            1. Формирование batch
            2. Статистический анализ
            3. Обучение
            4. Сохранение памяти
            5. Завершение batch
        """

        started_at = _now()

        result: Dict[str, Any] = {
            "module": MODULE_NAME,
            "version": MODULE_VERSION,
            "status": "started",
            "started_at": started_at,
            "finished_at": None,
            "batch_size": 0,
            "processed": 0,
            "errors": 0,
            "learning_events": 0,
            "memory_events": 0,
            "message": "",
        }

        logger.info(
            "ETC run started: limit=%s force=%s",
            limit,
            force,
        )

        try:

            # =================================================
            # STEP 1 — BATCH
            # =================================================

            logger.info("ETC STEP 1: building learning batch")

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
                    "ETC finished: nothing to process"
                )

                return result

            result["batch_size"] = len(batch)

            # =================================================
            # STEP 2 — STATISTICAL ANALYSIS
            # =================================================

            logger.info(
                "ETC STEP 2: statistical analysis, batch=%s",
                len(batch),
            )

            analysis_results = []

            for item in batch:

                match_id = self._extract_match_id(item)

                if match_id is None:
                    logger.warning(
                        "ETC batch item without match_id: %s",
                        item,
                    )
                    result["errors"] += 1
                    continue

                try:

                    analysis = (
                        self.statistical_analyzer.analyze_match(
                            match_id
                        )
                    )

                    analysis_results.append({
                        "match_id": match_id,
                        "analysis": analysis,
                    })

                except Exception as exc:

                    result["errors"] += 1

                    logger.exception(
                        "Statistical analysis failed "
                        "for match_id=%s: %s",
                        match_id,
                        exc,
                    )

                    if not force:
                        raise

            # =================================================
            # STEP 3 — LEARNING
            # =================================================

            logger.info(
                "ETC STEP 3: learning, analyses=%s",
                len(analysis_results),
            )

            for item in analysis_results:

                match_id = item["match_id"]
                analysis = item["analysis"]

                try:

                    learning_result = (
                        self.learning_engine.process_analysis(
                            match_id=match_id,
                            analysis=analysis,
                        )
                    )

                    if isinstance(
                        learning_result,
                        dict,
                    ):
                        result["learning_events"] += int(
                            learning_result.get(
                                "learning_events",
                                learning_result.get(
                                    "events",
                                    0,
                                ),
                            )
                            or 0
                        )

                        result["memory_events"] += int(
                            learning_result.get(
                                "memory_events",
                                learning_result.get(
                                    "memory",
                                    0,
                                ),
                            )
                            or 0
                        )

                except Exception as exc:

                    result["errors"] += 1

                    logger.exception(
                        "ETC learning failed "
                        "for match_id=%s: %s",
                        match_id,
                        exc,
                    )

                    if not force:
                        raise

            # =================================================
            # STEP 4 — MARK BATCH
            # =================================================

            logger.info(
                "ETC STEP 4: marking batch processed"
            )

            processed = self.batch_controller.mark_processed(
                batch
            )

            result["processed"] = int(
                processed
                if processed is not None
                else len(batch)
            )

            # =================================================
            # COMPLETE
            # =================================================

            result["status"] = (
                "completed"
                if result["errors"] == 0
                else "completed_with_errors"
            )

            result["message"] = (
                "ETC успешно обработал batch."
                if result["errors"] == 0
                else "ETC завершён с ошибками."
            )

            result["finished_at"] = _now()

            logger.info(
                "ETC run finished: status=%s "
                "processed=%s errors=%s",
                result["status"],
                result["processed"],
                result["errors"],
            )

            return result

        except Exception as exc:

            result["status"] = "failed"
            result["message"] = str(exc)
            result["finished_at"] = _now()

            logger.exception(
                "ETC run failed: %s",
                exc,
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
        Обрабатывает один завершённый матч через ETC.

        Используется для диагностики и Match Laboratory.
        """

        result: Dict[str, Any] = {
            "match_id": match_id,
            "status": "started",
            "analysis": None,
            "learning": None,
        }

        try:

            analysis = (
                self.statistical_analyzer.analyze_match(
                    match_id
                )
            )

            result["analysis"] = analysis

            learning = (
                self.learning_engine.process_analysis(
                    match_id=match_id,
                    analysis=analysis,
                )
            )

            result["learning"] = learning
            result["status"] = "completed"

            return result

        except Exception as exc:

            logger.exception(
                "ETC single-match processing failed "
                "for match_id=%s: %s",
                match_id,
                exc,
            )

            result["status"] = "failed"
            result["error"] = str(exc)

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
        Унифицированно извлекает match_id
        из элемента batch.

        Поддерживает:

            int
            dict
            sqlite3.Row
            объекты с attribute match_id
        """

        if item is None:
            return None

        if isinstance(item, int):
            return item

        if isinstance(item, dict):
            value = item.get("match_id")

            if value is None:
                value = item.get("id")

            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        try:
            value = item["match_id"]

            return (
                int(value)
                if value is not None
                else None
            )

        except (KeyError, TypeError, IndexError):
            pass

        except Exception:
            pass

        try:
            value = getattr(item, "match_id", None)

            return (
                int(value)
                if value is not None
                else None
            )

        except (TypeError, ValueError):
            return None


# ============================================================
# MODULE-LEVEL HELPER
# ============================================================

def run_etc(
    db: Optional[FAJDatabase] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Удобная точка входа для faj_cycle.py
    и Streamlit ETC страницы.
    """

    controller = ETCController(db=db)

    return controller.run(
        limit=limit,
        force=force,
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
    print("FAJ Platform v12.1")
    print("ETC — Evolution Training Center")
    print("ETC Controller")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    try:

        controller = ETCController()

        status = controller.status()

        print("ETC status:")
        print(status)

    except Exception as exc:

        print(
            f"ETC controller unavailable: {exc}"
        )

    print("=" * 70)
