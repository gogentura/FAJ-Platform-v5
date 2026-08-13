#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ Cycle — Main Orchestrator
============================================================

Назначение:
    Безопасный полный цикл FAJ:

        1. Bootstrap
        2. Sync teams + passports
        3. Parse / validate fixtures
        4. Load results
        5. Learning
        6. Prediction

КРИТИЧЕСКИЕ ПРИНЦИПЫ:

    - SQLite only
    - НЕ удаляет данные
    - НЕ делает DELETE
    - НЕ делает DROP
    - Не пересоздаёт существующие сезоны / туры / матчи
    - Парсеры не изменяют БД
    - Ошибка критической фазы останавливает последующие фазы
    - Повторный запуск должен быть безопасным
============================================================
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("FAJ.Cycle")

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | FAJ.CYCLE | %(message)s",
    )


# ============================================================
# CONFIG
# ============================================================

CYCLE_VERSION = "12.1"

LEAGUE_NAME = "РПЛ"
SEASON_NAME = "РПЛ 2026-2027"

EXPECTED_TEAMS = 16
EXPECTED_ROUNDS = 30
EXPECTED_MATCHES = 240


# ============================================================
# IMPORTS
# ============================================================

from app.bootstrap import bootstrap_faj
from app.sync_engine import SyncEngine
from app.parsers.rpl_fixtures_parser import parse_rpl_fixtures
from app.parsers.rpl_results_parser import parse_rpl_results
from app.learning_engine import run_learning
from app.core.prediction_manager import PredictionManager


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """Текущее время в ISO формате."""
    return datetime.utcnow().isoformat()


def _new_cycle_id() -> str:
    """Уникальный ID запуска цикла."""
    return f"cycle_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _phase_result(
    phase: str,
    success: bool,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Унифицированный результат фазы.
    """
    result = {
        "phase": phase,
        "success": success,
        "timestamp": _now(),
    }

    result.update(kwargs)

    return result


# ============================================================
# FAJ CYCLE
# ============================================================

class FAJCycle:
    """
    Главный оркестратор FAJ Platform.

    ВАЖНО:

    Этот класс НЕ реализует бизнес-логику отдельных модулей.

    Он только управляет порядком:

        Bootstrap
            ↓
        Sync
            ↓
        Fixtures
            ↓
        Results
            ↓
        Learning
            ↓
        Prediction
    """

    def __init__(self):
        self.cycle_id = _new_cycle_id()

        self.results: Dict[str, Any] = {
            "success": False,
            "cycle_id": self.cycle_id,
            "version": CYCLE_VERSION,
            "started_at": _now(),
            "finished_at": None,
            "phases": {},
            "errors": [],
            "warnings": [],
        }

        logger.info(
            "FAJ Cycle %s started",
            self.cycle_id,
        )

    # ========================================================
    # 1. BOOTSTRAP
    # ========================================================

    def bootstrap(self) -> Dict[str, Any]:
        """
        Проверка состояния FAJ.

        Bootstrap НЕ должен считаться ошибкой только потому,
        что календарь ещё отсутствует.

        Это важно для восстановления БД.
        """

        logger.info("PHASE 1: Bootstrap")

        try:
            result = bootstrap_faj()

            if not isinstance(result, dict):
                return _phase_result(
                    "bootstrap",
                    False,
                    error="bootstrap_faj() returned invalid result",
                )

            teams = result.get("teams", 0)
            passports = result.get("passports", 0)
            season = result.get("season", False)
            db_exists = result.get("db_exists", False)

            # Критические условия
            critical_errors = []

            if not db_exists:
                critical_errors.append("Database does not exist")

            if teams < EXPECTED_TEAMS:
                critical_errors.append(
                    f"Not enough teams: {teams}/{EXPECTED_TEAMS}"
                )

            if passports < EXPECTED_TEAMS:
                critical_errors.append(
                    f"Not enough passports: {passports}/{EXPECTED_TEAMS}"
                )

            if not season:
                critical_errors.append(
                    f"Season '{SEASON_NAME}' is missing"
                )

            if critical_errors:
                phase = _phase_result(
                    "bootstrap",
                    False,
                    details=result,
                    errors=critical_errors,
                )

                self.results["errors"].extend(critical_errors)

                return phase

            return _phase_result(
                "bootstrap",
                True,
                details=result,
                note=(
                    "Existing matches are not required for bootstrap. "
                    "Calendar may be loaded in the next phase."
                ),
            )

        except Exception as exc:
            logger.exception("Bootstrap failed")

            error = f"Bootstrap exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "bootstrap",
                False,
                error=error,
            )

    # ========================================================
    # 2. SYNC
    # ========================================================

    def sync(self) -> Dict[str, Any]:
        """
        Синхронизация команд и паспортов.

        Не запускаем sync без необходимости.
        """

        logger.info("PHASE 2: Sync")

        try:
            sync_engine = SyncEngine()

            status = sync_engine.get_status(
                league=LEAGUE_NAME
            )

            teams = status.get("teams", 0)
            passports = status.get(
                "team_passports",
                status.get("passports", 0),
            )

            logger.info(
                "Current state: teams=%s passports=%s",
                teams,
                passports,
            )

            # Полная синхронизация требуется,
            # если отсутствует часть команд/паспортов.
            if (
                teams < EXPECTED_TEAMS
                or passports < EXPECTED_TEAMS
            ):
                logger.info(
                    "Synchronization required"
                )

                sync_result = sync_engine.sync_teams(
                    league=LEAGUE_NAME
                )

                return _phase_result(
                    "sync",
                    True,
                    action="sync_teams",
                    details=sync_result,
                )

            logger.info(
                "Teams and passports already exist. "
                "Synchronization skipped."
            )

            return _phase_result(
                "sync",
                True,
                action="skipped",
                teams=teams,
                passports=passports,
            )

        except Exception as exc:
            logger.exception("Sync failed")

            error = f"Sync exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "sync",
                False,
                error=error,
            )

    # ========================================================
    # 3. FIXTURES
    # ========================================================

    def load_calendar(self) -> Dict[str, Any]:
        """
        Парсинг и валидация календаря.

        ВАЖНО:
        parser НЕ должен непосредственно менять БД.

        Поэтому на этом этапе мы только получаем
        и проверяем календарь.

        Реальная запись должна выполняться через
        существующий database/load_calendar механизм.
        """

        logger.info("PHASE 3: Fixtures")

        try:
            fixtures = parse_rpl_fixtures()

            if not isinstance(fixtures, dict):
                error = (
                    "parse_rpl_fixtures() returned invalid result"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "calendar",
                    False,
                    error=error,
                )

            if not fixtures.get("calendar_valid", False):

                validation_errors = fixtures.get(
                    "validation_errors",
                    [],
                )

                error = (
                    "RPL calendar validation failed"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "calendar",
                    False,
                    error=error,
                    validation_errors=validation_errors,
                    details=fixtures,
                )

            matches = fixtures.get("matches", [])

            if len(matches) != EXPECTED_MATCHES:
                error = (
                    f"Invalid number of fixtures: "
                    f"{len(matches)}/{EXPECTED_MATCHES}"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "calendar",
                    False,
                    error=error,
                    matches=len(matches),
                )

            logger.info(
                "Calendar validated successfully: %s matches",
                len(matches),
            )

            return _phase_result(
                "calendar",
                True,
                matches=len(matches),
                rounds=EXPECTED_ROUNDS,
                details=fixtures,
                note=(
                    "Parser validated the calendar. "
                    "Database loading must use an idempotent loader."
                ),
            )

        except Exception as exc:
            logger.exception("Calendar phase failed")

            error = f"Calendar exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "calendar",
                False,
                error=error,
            )

    # ========================================================
    # 4. RESULTS
    # ========================================================

    def load_results(
        self,
        start_round: int = 1,
        end_round: int = 30,
    ) -> Dict[str, Any]:
        """
        Получение фактических результатов.

        По умолчанию проверяем весь сезон.

        ВАЖНО:
        parser только получает данные.
        Запись должна выполняться idempotent loader'ом.
        """

        logger.info(
            "PHASE 4: Results (%s-%s)",
            start_round,
            end_round,
        )

        try:
            results = parse_rpl_results(
                start_round=start_round,
                end_round=end_round,
            )

            if results is None:
                results = []

            if not isinstance(results, list):
                error = (
                    "parse_rpl_results() returned invalid result"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "results",
                    False,
                    error=error,
                )

            logger.info(
                "Parsed %s finished matches",
                len(results),
            )

            if not results:
                return _phase_result(
                    "results",
                    True,
                    matches=0,
                    action="no_results",
                    note=(
                        "No finished results available. "
                        "Learning will be handled separately."
                    ),
                )

            return _phase_result(
                "results",
                True,
                matches=len(results),
                start_round=start_round,
                end_round=end_round,
                details=results,
                note=(
                    "Results parsed successfully. "
                    "Database persistence must be idempotent."
                ),
            )

        except Exception as exc:
            logger.exception("Results phase failed")

            error = f"Results exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "results",
                False,
                error=error,
            )

    # ========================================================
    # 5. LEARNING
    # ========================================================

    def learn(self, force: bool = False) -> Dict[str, Any]:
        """
        Пакетное обучение.

        LearningEngine самостоятельно решает,
        достаточно ли фактических матчей.
        """

        logger.info(
            "PHASE 5: Learning (force=%s)",
            force,
        )

        try:
            result = run_learning(
                force=force
            )

            if not isinstance(result, dict):
                error = (
                    "run_learning() returned invalid result"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "learning",
                    False,
                    error=error,
                )

            if not result.get("success", False):

                # Недостаточно данных для обучения —
                # это не обязательно авария всего цикла.
                matches_analyzed = result.get(
                    "matches_analyzed",
                    0,
                )

                if matches_analyzed < 8:

                    warning = (
                        "Not enough matches for learning: "
                        f"{matches_analyzed}/8"
                    )

                    self.results["warnings"].append(
                        warning
                    )

                    return _phase_result(
                        "learning",
                        True,
                        action="skipped",
                        reason=warning,
                        details=result,
                    )

                error = (
                    "Learning engine returned success=False"
                )

                self.results["errors"].append(error)

                return _phase_result(
                    "learning",
                    False,
                    error=error,
                    details=result,
                )

            return _phase_result(
                "learning",
                True,
                details=result,
            )

        except Exception as exc:
            logger.exception("Learning failed")

            error = f"Learning exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "learning",
                False,
                error=error,
            )

    # ========================================================
    # 6. PREDICTION
    # ========================================================

    def predict(
        self,
        round_id: Optional[int] = None,
        include_finished: bool = False,
    ) -> Dict[str, Any]:
        """
        Генерация прогнозов.

        Если round_id не передан, автоматический поиск
        следующего тура здесь НЕ выполняем через догадки.

        Сначала получаем состояние БД через PredictionManager.
        """

        logger.info(
            "PHASE 6: Prediction"
        )

        try:
            manager = PredictionManager()

            status = manager.status()

            logger.info(
                "PredictionManager status: %s",
                status,
            )

            if round_id is None:
                return _phase_result(
                    "prediction",
                    True,
                    action="skipped",
                    reason=(
                        "round_id was not provided. "
                        "No round was guessed automatically."
                    ),
                    manager_status=status,
                )

            predictions = manager.predict_round(
                round_id=round_id,
                include_finished=include_finished,
            )

            if predictions is None:
                predictions = []

            return _phase_result(
                "prediction",
                True,
                round_id=round_id,
                predictions=predictions,
                count=len(predictions),
                manager_status=status,
            )

        except Exception as exc:
            logger.exception("Prediction failed")

            error = f"Prediction exception: {exc}"

            self.results["errors"].append(error)

            return _phase_result(
                "prediction",
                False,
                error=error,
            )

    # ========================================================
    # FULL CYCLE
    # ========================================================

    def run(
        self,
        *,
        results_start_round: int = 1,
        results_end_round: int = 30,
        learning_force: bool = False,
        prediction_round_id: Optional[int] = None,
        include_finished: bool = False,
    ) -> Dict[str, Any]:
        """
        Полный FAJ Cycle.

        Порядок:

            Bootstrap
            ↓
            Sync
            ↓
            Fixtures
            ↓
            Results
            ↓
            Learning
            ↓
            Prediction
        """

        logger.info(
            "================================================"
        )
        logger.info(
            "FAJ CYCLE v%s START",
            CYCLE_VERSION,
        )
        logger.info(
            "Cycle ID: %s",
            self.cycle_id,
        )
        logger.info(
            "================================================"
        )

        # ----------------------------------------------------
        # PHASE 1
        # ----------------------------------------------------

        bootstrap = self.bootstrap()

        self.results["phases"]["bootstrap"] = bootstrap

        if not bootstrap["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # PHASE 2
        # ----------------------------------------------------

        sync = self.sync()

        self.results["phases"]["sync"] = sync

        if not sync["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # PHASE 3
        # ----------------------------------------------------

        calendar = self.load_calendar()

        self.results["phases"]["calendar"] = calendar

        if not calendar["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # PHASE 4
        # ----------------------------------------------------

        results = self.load_results(
            start_round=results_start_round,
            end_round=results_end_round,
        )

        self.results["phases"]["results"] = results

        if not results["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # PHASE 5
        # ----------------------------------------------------

        learning = self.learn(
            force=learning_force
        )

        self.results["phases"]["learning"] = learning

        if not learning["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # PHASE 6
        # ----------------------------------------------------

        prediction = self.predict(
            round_id=prediction_round_id,
            include_finished=include_finished,
        )

        self.results["phases"]["prediction"] = prediction

        if not prediction["success"]:
            return self._finish(False)

        # ----------------------------------------------------
        # COMPLETE
        # ----------------------------------------------------

        return self._finish(True)

    # ========================================================
    # FINISH
    # ========================================================

    def _finish(
        self,
        success: bool,
    ) -> Dict[str, Any]:
        """
        Завершение цикла.
        """

        self.results["success"] = success
        self.results["finished_at"] = _now()

        if success:
            logger.info(
                "FAJ Cycle %s COMPLETED",
                self.cycle_id,
            )
        else:
            logger.error(
                "FAJ Cycle %s FAILED",
                self.cycle_id,
            )

        return self.results


# ============================================================
# CONVENIENCE API
# ============================================================

def run_faj_cycle(
    *,
    results_start_round: int = 1,
    results_end_round: int = 30,
    learning_force: bool = False,
    prediction_round_id: Optional[int] = None,
    include_finished: bool = False,
) -> Dict[str, Any]:
    """
    Удобный публичный API FAJ Cycle.
    """

    cycle = FAJCycle()

    return cycle.run(
        results_start_round=results_start_round,
        results_end_round=results_end_round,
        learning_force=learning_force,
        prediction_round_id=prediction_round_id,
        include_finished=include_finished,
    )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    result = run_faj_cycle(
        results_start_round=1,
        results_end_round=30,
        learning_force=False,
        prediction_round_id=None,
        include_finished=False,
    )

    print()
    print("=" * 60)
    print("FAJ CYCLE RESULT")
    print("=" * 60)

    print(
        f"Success: {result['success']}"
    )

    print(
        f"Cycle ID: {result['cycle_id']}"
    )

    print(
        f"Started: {result['started_at']}"
    )

    print(
        f"Finished: {result['finished_at']}"
    )

    print()

    for phase_name, phase_result in result[
        "phases"
    ].items():

        print(
            f"[{phase_name.upper()}] "
            f"{'OK' if phase_result.get('success') else 'FAILED'}"
        )

    if result["warnings"]:
        print()
        print("WARNINGS:")

        for warning in result["warnings"]:
            print(
                f"  - {warning}"
            )

    if result["errors"]:
        print()
        print("ERRORS:")

        for error in result["errors"]:
            print(
                f"  - {error}"
            )

    print("=" * 60)
