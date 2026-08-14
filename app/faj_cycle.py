#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
FAJ Cycle v1.0
=====================================================

ЦЕНТРАЛЬНЫЙ ОРКЕСТРАТОР ПОЛНОГО ЦИКЛА FAJ.

ЦЕПОЧКА:

    1. Bootstrap / Database
            ↓
    2. System Status
            ↓
    3. Teams + Passports
            ↓
    4. Calendar
            ↓
    5. Historical Results
            ↓
    6. Learning
            ↓
    7. Find Next Round
            ↓
    8. Predictions
            ↓
    9. Final Report

ВАЖНО:

    faj_cycle.py НЕ:
        - считает xG
        - считает Poisson
        - запускает Monte Carlo напрямую
        - изменяет схему БД
        - удаляет данные
        - создаёт календарь самостоятельно
        - дублирует PredictionManager
        - дублирует PassportManager
        - дублирует LearningEngine

    Все специализированные операции выполняют
    соответствующие модули.

=====================================================
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple

from app.bootstrap import bootstrap_faj
from app.sync_engine import SyncEngine
from app.passport_manager import PassportManager
from app.prediction_manager import PredictionManager
from app.learning_engine import LearningEngine
from app.database import get_database

logger = logging.getLogger(__name__)


class FAJCycle:
    """
    Центральный оркестратор полного FAJ Cycle v1.0.
    """

    VERSION = "1.0"
    LEAGUE = "РПЛ"

    def __init__(
        self,
        db=None,
        sync_engine=None,
        passport_manager=None,
        prediction_manager=None,
        learning_engine=None,
    ):
        self.version = self.VERSION

        # --------------------------------------------------------
        # DATABASE
        # --------------------------------------------------------

        self.db = db or get_database()

        # --------------------------------------------------------
        # SPECIALIZED MANAGERS
        # --------------------------------------------------------

        self.sync_engine = (
            sync_engine
            or SyncEngine(db=self.db)
        )

        self.passport_manager = (
            passport_manager
            or PassportManager(db=self.db)
        )

        self.prediction_manager = (
            prediction_manager
            or PredictionManager(
                passport_manager=self.passport_manager,
                db=self.db,
            )
        )

        self.learning_engine = (
            learning_engine
            or LearningEngine(db=self.db)
        )

        logger.info(
            "FAJ Cycle v%s initialized | league=%s",
            self.VERSION,
            self.LEAGUE,
        )

    # ============================================================
    # PUBLIC API
    # ============================================================

    def run(
        self,
        *,
        results_start_round: int = 1,
        results_end_round: int = 3,
        learning_force: bool = False,
        prediction_round_id: Optional[int] = None,
        include_finished: bool = False,
    ) -> Dict[str, Any]:
        """
        Запускает полный FAJ Cycle.

        Порядок:

            bootstrap
            → status
            → teams/passports
            → calendar
            → historical results
            → learning
            → next round
            → predictions
            → report

        Returns:
            Полный отчёт цикла.
        """

        started = time.perf_counter()

        report = {
            "status": "running",
            "cycle_version": self.VERSION,
            "league": self.LEAGUE,
            "phases": {},
        }

        logger.info("=" * 70)
        logger.info("🚀 FAJ CYCLE START")
        logger.info("=" * 70)

        try:

            # ====================================================
            # 1. BOOTSTRAP
            # ====================================================

            report["phases"]["bootstrap"] = self.bootstrap()

            if not report["phases"]["bootstrap"].get(
                "success",
                False
            ):
                return self._finish(
                    report,
                    started,
                    "bootstrap_failed",
                )

            # ====================================================
            # 2. SYSTEM STATUS
            # ====================================================

            status = self.system_status()

            report["phases"]["system_status"] = status

            if not status.get("success", False):
                return self._finish(
                    report,
                    started,
                    "system_status_failed",
                )

            # ====================================================
            # 3. TEAMS + PASSPORTS
            # ====================================================

            teams_result = self.sync()

            report["phases"]["teams_passports"] = teams_result

            if not teams_result.get("success", False):
                return self._finish(
                    report,
                    started,
                    "teams_passports_failed",
                )

            # ====================================================
            # 4. CALENDAR
            # ====================================================

            calendar_result = self.load_calendar()

            report["phases"]["calendar"] = calendar_result

            if not calendar_result.get("success", False):
                return self._finish(
                    report,
                    started,
                    "calendar_failed",
                )

            # ====================================================
            # 5. HISTORICAL RESULTS
            # ====================================================

            results_result = self.load_results(
                start_round=results_start_round,
                end_round=results_end_round,
            )

            report["phases"]["historical_results"] = results_result

            if not results_result.get("success", False):
                return self._finish(
                    report,
                    started,
                    "historical_results_failed",
                )

            # ====================================================
            # 6. LEARNING
            # ====================================================

            learning_result = self.learn(
                force=learning_force
            )

            report["phases"]["learning"] = learning_result

            if not learning_result.get("success", False):
                return self._finish(
                    report,
                    started,
                    "learning_failed",
                )

            # ====================================================
            # 7. FIND NEXT ROUND
            # ====================================================

            next_round = self._find_next_round_without_predictions()

            report["phases"]["next_round"] = next_round

            if not next_round.get("success", False):
                return self._finish(
                    report,
                    started,
                    "next_round_not_found",
                )

            selected_round_id = (
                prediction_round_id
                if prediction_round_id is not None
                else next_round.get("round_id")
            )

            if selected_round_id is None:
                return self._finish(
                    report,
                    started,
                    "prediction_round_id_missing",
                )

            # ====================================================
            # 8. PREDICTIONS
            # ====================================================

            prediction_result = self.predict(
                round_id=selected_round_id,
                include_finished=include_finished,
            )

            report["phases"]["predictions"] = prediction_result

            if not prediction_result.get("success", False):
                return self._finish(
                    report,
                    started,
                    "prediction_failed",
                )

            # ====================================================
            # 9. FINAL REPORT
            # ====================================================

            report["summary"] = {
                "round_id": selected_round_id,
                "predictions_created":
                    prediction_result.get(
                        "predictions_created",
                        0,
                    ),
                "historical_results":
                    results_result.get(
                        "results_loaded",
                        0,
                    ),
            }

            return self._finish(
                report,
                started,
                "success",
            )

        except Exception as exc:

            logger.exception(
                "❌ FAJ CYCLE ERROR"
            )

            report["error"] = str(exc)

            return self._finish(
                report,
                started,
                "exception",
            )

    # ============================================================
    # PHASE 1
    # ============================================================

    def bootstrap(self) -> Dict[str, Any]:
        """
        Инициализация / проверка БД.
        """

        logger.info("🔧 PHASE 1 — BOOTSTRAP")

        try:

            result = bootstrap_faj()

            if isinstance(result, dict):

                return {
                    "success": True,
                    "result": result,
                }

            return {
                "success": True,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Bootstrap failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 2
    # ============================================================

    def system_status(self) -> Dict[str, Any]:
        """
        Проверка состояния системы.
        """

        logger.info("🔎 PHASE 2 — SYSTEM STATUS")

        try:

            status = {}

            # ----------------------------------------------------
            # Database status
            # ----------------------------------------------------

            if hasattr(
                self.db,
                "get_database_status"
            ):
                status["database"] = (
                    self.db.get_database_status()
                )

            # ----------------------------------------------------
            # Sync status
            # ----------------------------------------------------

            status["sync"] = (
                self.sync_engine.get_status(
                    league=self.LEAGUE
                )
            )

            return {
                "success": True,
                "status": status,
            }

        except Exception as exc:

            logger.exception(
                "System status failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 3
    # ============================================================

    def sync(self) -> Dict[str, Any]:
        """
        Синхронизация команд и паспортов.

        Важно:
        если команды уже существуют, паспорта всё равно
        должны быть обработаны.
        """

        logger.info(
            "🏟️ PHASE 3 — TEAMS + PASSPORTS"
        )

        try:

            teams = self.sync_engine.sync_teams(
                league=self.LEAGUE
            )

            passports = self.sync_engine.load_passports(
                league=self.LEAGUE
            )

            return {
                "success": True,
                "teams": teams,
                "passports": passports,
            }

        except Exception as exc:

            logger.exception(
                "Teams/passports sync failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 4
    # ============================================================

    def load_calendar(self) -> Dict[str, Any]:
        """
        Загрузка / синхронизация календаря.

        Календарь загружается специализированным
        load_calendar.py / SyncEngine.

        Здесь не создаём матчи вручную.
        """

        logger.info("📅 PHASE 4 — CALENDAR")

        try:

            result = self.sync_engine.sync_matches(
                league=self.LEAGUE
            )

            return {
                "success": True,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Calendar loading failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 5
    # ============================================================

    def load_results(
        self,
        start_round: int = 1,
        end_round: int = 3,
    ) -> Dict[str, Any]:
        """
        Загрузка исторических результатов.

        Используется существующий загрузочный слой.
        """

        logger.info(
            "📥 PHASE 5 — HISTORICAL RESULTS | "
            "rounds=%s-%s",
            start_round,
            end_round,
        )

        try:

            # ----------------------------------------------------
            # Предпочтительный API load_all
            # ----------------------------------------------------

            from app.load_all import load_all

            result = load_all(
                start_round=start_round,
                end_round=end_round,
            )

            if isinstance(result, dict):

                return {
                    "success": True,
                    "result": result,
                    "results_loaded":
                        result.get(
                            "results_loaded",
                            result.get(
                                "matches_loaded",
                                0,
                            ),
                        ),
                }

            return {
                "success": True,
                "result": result,
                "results_loaded": 0,
            }

        except ImportError:

            logger.exception(
                "load_all.py API unavailable"
            )

            return {
                "success": False,
                "error":
                    "load_all API unavailable",
            }

        except Exception as exc:

            logger.exception(
                "Historical results loading failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 6
    # ============================================================

    def learn(
        self,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Запуск Learning Engine.
        """

        logger.info("🧠 PHASE 6 — LEARNING")

        try:

            # Поддерживаем основной API LearningEngine,
            # если он присутствует.

            if hasattr(
                self.learning_engine,
                "run"
            ):

                result = self.learning_engine.run(
                    force=force
                )

            elif hasattr(
                self.learning_engine,
                "train"
            ):

                result = self.learning_engine.train(
                    force=force
                )

            elif hasattr(
                self.learning_engine,
                "learn"
            ):

                result = self.learning_engine.learn(
                    force=force
                )

            else:

                raise AttributeError(
                    "LearningEngine has no supported "
                    "run/train/learn method"
                )

            return {
                "success": True,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Learning failed"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 7
    # ============================================================

    def _find_next_round_without_predictions(
        self,
    ) -> Dict[str, Any]:
        """
        Находит следующий тур, в котором есть матчи
        без сохранённых прогнозов.

        ВАЖНО:
        PredictionManager.predict_round() получает
        round_id, а не round_number.
        """

        logger.info(
            "🔍 PHASE 7 — FIND NEXT ROUND"
        )

        try:

            # ----------------------------------------------------
            # Получаем туры из БД.
            # ----------------------------------------------------

            if not hasattr(
                self.db,
                "get_connection"
            ):
                raise AttributeError(
                    "Database.get_connection() unavailable"
                )

            connection = self.db.get_connection()

            try:

                cursor = connection.cursor()

                cursor.execute(
                    """
                    SELECT
                        r.id,
                        r.round_number
                    FROM rounds r
                    JOIN seasons s
                        ON s.id = r.season_id
                    WHERE s.league = ?
                    ORDER BY r.round_number ASC
                    """,
                    (self.LEAGUE,),
                )

                rounds = cursor.fetchall()

            finally:

                connection.close()

            if not rounds:

                return {
                    "success": False,
                    "error": "No rounds found",
                }

            # ----------------------------------------------------
            # Ищем первый тур с матчами без прогнозов.
            # ----------------------------------------------------

            for row in rounds:

                if isinstance(row, dict):

                    round_id = row["id"]
                    round_number = row[
                        "round_number"
                    ]

                else:

                    round_id = row[0]
                    round_number = row[1]

                if not hasattr(
                    self.db,
                    "get_connection"
                ):
                    continue

                connection = self.db.get_connection()

                try:

                    cursor = connection.cursor()

                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM matches m
                        LEFT JOIN match_predictions mp
                            ON mp.match_id = m.id
                        WHERE m.round_id = ?
                          AND (
                              mp.id IS NULL
                              OR mp.status = 'error'
                          )
                        """,
                        (round_id,),
                    )

                    result = cursor.fetchone()

                    missing_predictions = (
                        result[0]
                        if not isinstance(result, dict)
                        else next(
                            iter(result.values())
                        )
                    )

                finally:

                    connection.close()

                if missing_predictions > 0:

                    return {
                        "success": True,
                        "round_id": round_id,
                        "round_number":
                            round_number,
                        "missing_predictions":
                            missing_predictions,
                    }

            return {
                "success": False,
                "error":
                    "All rounds already have predictions",
            }

        except Exception as exc:

            logger.exception(
                "Cannot find next round"
            )

            return {
                "success": False,
                "error": str(exc),
            }

    # ============================================================
    # PHASE 8
    # ============================================================

    def predict(
        self,
        round_id: int,
        include_finished: bool = False,
    ) -> Dict[str, Any]:
        """
        Создание прогнозов для тура.

        PredictionManager является единственным владельцем
        prediction pipeline.
        """

        logger.info(
            "🔮 PHASE 8 — PREDICTIONS | round_id=%s",
            round_id,
        )

        try:

            result = (
                self.prediction_manager.predict_round(
                    round_id=round_id,
                    include_finished=include_finished,
                )
            )

            predictions_created = 0

            if isinstance(result, dict):

                predictions_created = result.get(
                    "predictions_created",
                    result.get(
                        "created",
                        result.get(
                            "count",
                            0,
                        ),
                    ),
                )

            elif isinstance(result, list):

                predictions_created = len(result)

            return {
                "success": True,
                "round_id": round_id,
                "predictions_created":
                    predictions_created,
                "result": result,
            }

        except Exception as exc:

            logger.exception(
                "Prediction phase failed"
            )

            return {
                "success": False,
                "round_id": round_id,
                "error": str(exc),
            }

    # ============================================================
    # FINAL
    # ============================================================

    def _finish(
        self,
        report: Dict[str, Any],
        started: float,
        status: str,
    ) -> Dict[str, Any]:
        """
        Формирует финальный отчёт.
        """

        elapsed = round(
            (
                time.perf_counter()
                - started
            ) * 1000,
            2,
        )

        report["status"] = status

        report["processing_time_ms"] = elapsed

        logger.info("=" * 70)

        if status == "success":

            logger.info(
                "✅ FAJ CYCLE COMPLETE | %.2f ms",
                elapsed,
            )

        else:

            logger.error(
                "❌ FAJ CYCLE STOPPED | "
                "status=%s | %.2f ms",
                status,
                elapsed,
            )

        logger.info("=" * 70)

        return report


# ================================================================
# PUBLIC FUNCTION
# ================================================================

def run_faj_cycle(
    db_path: Optional[str] = None,
    results_rounds: Tuple[int, int] = (1, 3),
    force_learning: bool = False,
    prediction_round: Optional[int] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Удобная точка входа для Streamlit / CLI.

    Args:
        db_path:
            Оставлен для совместимости интерфейса.
            SQLite остаётся единственной БД FAJ.

        results_rounds:
            Диапазон исторических туров.

        force_learning:
            Принудительное обучение.

        prediction_round:
            ID тура для прогнозирования.
            Если None — ищется автоматически.

        dry_run:
            В текущем варианте только сохраняется
            в отчёте; сам цикл не переводится
            в альтернативный режим.

    Returns:
        Полный отчёт FAJ Cycle.
    """

    start_round, end_round = results_rounds

    cycle = FAJCycle()

    result = cycle.run(
        results_start_round=start_round,
        results_end_round=end_round,
        learning_force=force_learning,
        prediction_round_id=prediction_round,
        include_finished=False,
    )

    result["dry_run"] = dry_run
    result["db_path"] = db_path

    return result


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    print()
    print("=" * 70)
    print("FAJ PLATFORM v12.1")
    print("FAJ CYCLE v1.0")
    print("=" * 70)
    print()

    result = run_faj_cycle(
        results_rounds=(1, 3),
        force_learning=False,
        prediction_round=None,
        dry_run=False,
    )

    print()
    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    print(
        f"Status: "
        f"{result.get('status')}"
    )

    print(
        f"Processing: "
        f"{result.get('processing_time_ms')} ms"
    )

    summary = result.get(
        "summary",
        {}
    )

    if summary:

        print(
            f"Round ID: "
            f"{summary.get('round_id')}"
        )

        print(
            f"Predictions: "
            f"{summary.get('predictions_created', 0)}"
        )

        print(
            f"Historical results: "
            f"{summary.get('historical_results', 0)}"
        )

    print("=" * 70)
