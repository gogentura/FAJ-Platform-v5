#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ CYCLE — Главный оркестратор
============================================================

Файл:
    app/faj_cycle.py

НАЗНАЧЕНИЕ
----------

FAJ Cycle — верхний оркестратор жизненного цикла FAJ.

FAJ Cycle НЕ содержит математической логики модели.

Его задача — правильно связать:

    DATABASE
        ↓
    CALENDAR / MATCHES
        ↓
    FACTS
        ↓
    ETC
        ↓
    PREDICTIONS

============================================================

ЖИЗНЕННЫЙ ЦИКЛ
==============

    MATCH
      │
      ▼
    MATCH RESULT / STATISTICS
      │
      ▼
    SQLite
      │
      ▼
    BatchController
      │
      ▼
    ETCController
      │
      ▼
    ETCLearningEngine
      │
      ▼
    StatisticalAnalyzer
      │
      ▼
    LearningMemory
      │
      ▼
    NEXT PREDICTION
      │
      ▼
    PredictionManager

============================================================

АРХИТЕКТУРНЫЙ КОНТРАК
======================

1. SQLite only.

2. database.py — единый источник схемы.

3. Исторические факты не удаляются.

4. match_results не изменяются ETC.

5. match_statistics не изменяются ETC.

6. Старые predictions не переписываются ETC.

7. ETC не создаёт прогнозы.

8. ETC не управляет календарём.

9. FAJ Cycle не содержит xG / Poisson /
   Monte Carlo расчётов.

10. Старый:

        app.learning_engine.py

    НЕ используется.

11. Единственный learning pipeline:

        app/etc/learning_engine.py

12. BatchController является владельцем решения:

        READY
        WAIT
        ALREADY_PROCESSED
        UNKNOWN_LEAGUE

13. ETCLearningEngine является владельцем
    фактического обучения.

14. LearningMemory остаётся владельцем
    записи learning memory.

15. Ошибка одного матча не должна уничтожать
    уже успешно обработанные матчи.

============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from datetime import datetime
from typing import Any, Dict, List, Optional


from app.database import FAJDatabase

from app.match_manager import MatchManager

from app.etc.etc_controller import (
    run_etc,
)

from app.core.prediction_manager import (
    get_prediction_manager,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
FAJ_CYCLE_VERSION = "2.1"


# ============================================================
# TIME
# ============================================================

def _now() -> str:
    """
    Текущее локальное время.
    """
    return datetime.now().isoformat()


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Безопасное преобразование в int.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


# ============================================================
# FAJ CYCLE
# ============================================================

class FAJCycle:
    """
    Главный оркестратор FAJ.

    Контур:

        DATABASE
            ↓
        MATCHES
            ↓
        FACTS ALREADY IN DB
            ↓
        ETC
            ↓
        PREDICTIONS

    ВАЖНО:

    FAJCycle НЕ реализует обучение.

    FAJCycle только запускает ETC.

    Единственный learning pipeline:

        app/etc/learning_engine.py
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

        self.match_mgr = MatchManager(
            self.db
        )

        self.pred_mgr = get_prediction_manager()

    # ========================================================
    # MAIN CYCLE
    # ========================================================

    def run(
        self,
        match_id: Optional[int] = None,
        round_id: Optional[int] = None,
        season_id: Optional[int] = None,
        force: bool = False,
        run_predictions: bool = True,
    ) -> Dict[str, Any]:
        """
        Запускает полный FAJ Cycle.

        Порядок:

            1. DATABASE
            2. MATCHES
            3. ETC
            4. PREDICTIONS

        Факты здесь не создаются.

        ETC сам обнаруживает готовые факты
        через BatchController.
        """

        started = _now()

        result = self._new_result(
            started
        )

        logger.info(
            "=================================================="
        )

        logger.info(
            "FAJ CYCLE STARTED | "
            "version=%s | "
            "match=%s | "
            "round=%s | "
            "season=%s | "
            "force=%s",
            FAJ_CYCLE_VERSION,
            match_id,
            round_id,
            season_id,
            force,
        )

        # ====================================================
        # 1. DATABASE
        # ====================================================

        if not self._check_database(
            result
        ):

            return self._finish(
                result,
                started,
            )

        # ====================================================
        # 2. MATCHES
        # ====================================================

        if not self._load_matches(
            result=result,
            match_id=match_id,
            round_id=round_id,
            season_id=season_id,
        ):

            return self._finish(
                result,
                started,
            )

        # ====================================================
        # 3. ETC
        # ====================================================

        if not self._run_etc(
            result=result,
            season_id=season_id,
            force=force,
        ):

            return self._finish(
                result,
                started,
            )

        # ====================================================
        # 4. PREDICTIONS
        # ====================================================

        if run_predictions:

            if not self._run_predictions(
                result=result,
                round_id=round_id,
            ):

                return self._finish(
                    result,
                    started,
                )

        else:

            result["predictions"]["skipped"] = True

            self._add_step(
                result,
                "predictions",
                "skipped",
                "⏭️ Прогнозирование отключено.",
            )

        # ====================================================
        # FINISH
        # ====================================================

        return self._finish(
            result,
            started,
        )

    # ========================================================
    # DATABASE
    # ========================================================

    def _check_database(
        self,
        result: Dict[str, Any],
    ) -> bool:
        """
        Проверяет доступность SQLite.

        Только read-only.
        """

        self._add_step(
            result,
            "database",
            "running",
            "📁 Проверка базы данных...",
        )

        try:

            status = self.db.get_status()

            if not isinstance(
                status,
                dict,
            ):

                message = (
                    "❌ FAJDatabase.get_status() "
                    "вернул некорректный результат."
                )

                result["database"]["error"] = (
                    message
                )

                result["errors"].append(
                    message
                )

                self._add_step(
                    result,
                    "database",
                    "error",
                    message,
                )

                return False

            if status.get("status") == "online":

                result["database"]["ok"] = True

                self._add_step(
                    result,
                    "database",
                    "success",
                    (
                        "✅ База данных доступна: "
                        f"{status.get('file', 'unknown')}"
                    ),
                )

                return True

            message = (
                "❌ База данных недоступна: "
                f"{status.get('error', 'unknown error')}"
            )

            result["database"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "database",
                "error",
                message,
            )

            return False

        except Exception as exc:

            message = (
                f"❌ Ошибка проверки БД: {exc}"
            )

            result["database"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "database",
                "error",
                message,
            )

            logger.exception(
                "Database check failed"
            )

            return False

    # ========================================================
    # MATCHES
    # ========================================================

    def _load_matches(
        self,
        result: Dict[str, Any],
        match_id: Optional[int] = None,
        round_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> bool:
        """
        Определяет область текущего запуска.

        Никаких изменений календаря или фактов
        здесь не производится.
        """

        self._add_step(
            result,
            "matches",
            "running",
            "📋 Проверка матчей...",
        )

        try:

            matches: List[Any] = []

            # =================================================
            # SINGLE MATCH
            # =================================================

            if match_id is not None:

                match = self.db.get_match_by_uuid(
                    str(match_id)
                )

                if not match:

                    match = self.db.get_match_by_uuid(
                        f"match_{match_id}"
                    )

                if match:

                    matches.append(
                        match
                    )

                else:

                    message = (
                        f"Матч {match_id} не найден"
                    )

                    result["matches"]["error"] = (
                        message
                    )

                    result["errors"].append(
                        message
                    )

                    self._add_step(
                        result,
                        "matches",
                        "error",
                        f"❌ {message}",
                    )

                    return False

            # =================================================
            # ROUND
            # =================================================

            elif round_id is not None:

                matches = self.db.get_matches(
                    round_id
                )

                if not matches:

                    message = (
                        f"Тур {round_id} "
                        "не найден или не содержит матчей"
                    )

                    result["matches"]["error"] = (
                        message
                    )

                    result["errors"].append(
                        message
                    )

                    self._add_step(
                        result,
                        "matches",
                        "error",
                        f"❌ {message}",
                    )

                    return False

            # =================================================
            # SEASON
            # =================================================

            elif season_id is not None:

                rounds = self.db.get_rounds(
                    season_id
                )

                for round_item in rounds:

                    round_data = (
                        dict(round_item)
                        if round_item
                        else {}
                    )

                    current_round_id = (
                        round_data.get("id")
                    )

                    if current_round_id is None:
                        continue

                    round_matches = (
                        self.db.get_matches(
                            current_round_id
                        )
                    )

                    if round_matches:

                        matches.extend(
                            round_matches
                        )

                if not matches:

                    message = (
                        f"Сезон {season_id} "
                        "не содержит матчей"
                    )

                    result["matches"]["error"] = (
                        message
                    )

                    result["errors"].append(
                        message
                    )

                    self._add_step(
                        result,
                        "matches",
                        "error",
                        f"❌ {message}",
                    )

                    return False

            # =================================================
            # ALL
            # =================================================

            else:

                matches = self.db.get_matches()

            result["matches"]["total"] = (
                len(matches)
            )

            if matches:

                result["matches"]["success"] = True

                self._add_step(
                    result,
                    "matches",
                    "success",
                    (
                        "✅ Матчи доступны: "
                        f"{len(matches)}"
                    ),
                )

                return True

            message = (
                "Матчи не найдены"
            )

            result["matches"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "matches",
                "error",
                f"❌ {message}",
            )

            return False

        except Exception as exc:

            message = (
                f"❌ Ошибка проверки матчей: {exc}"
            )

            result["matches"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "matches",
                "error",
                message,
            )

            logger.exception(
                "Matches loading failed"
            )

            return False

    # ========================================================
    # ETC
    # ========================================================

    def _run_etc(
        self,
        result: Dict[str, Any],
        season_id: Optional[int] = None,
        force: bool = False,
    ) -> bool:
        """
        Запускает ETC.

        КРИТИЧЕСКИ ВАЖНО:

        FAJ Cycle НЕ передаёт ETC факты.

        ETC самостоятельно получает их из SQLite
        через BatchController.

        Контур:

            SQLite
              ↓
            BatchController
              ↓
            ETCController
              ↓
            ETCLearningEngine
              ↓
            LearningMemory

        Старый app.learning_engine.py
        здесь не используется.
        """

        self._add_step(
            result,
            "etc",
            "running",
            "🧬 Запуск ETC — Evolution Training Center...",
        )

        result["etc"]["started"] = True

        try:

            etc_result = run_etc(
                db=self.db,
                season_id=season_id,
                force=force,
            )

            result["etc"]["result"] = (
                etc_result
            )

            if not isinstance(
                etc_result,
                dict,
            ):

                message = (
                    "ETC вернул некорректный результат."
                )

                result["etc"]["errors"].append(
                    message
                )

                result["errors"].append(
                    message
                )

                self._add_step(
                    result,
                    "etc",
                    "error",
                    f"❌ {message}",
                )

                return False

            status = etc_result.get(
                "status",
                "",
            )

            processed = _safe_int(
                etc_result.get(
                    "processed",
                    0,
                )
            )

            analyzed = _safe_int(
                etc_result.get(
                    "analyzed",
                    0,
                )
            )

            learned = _safe_int(
                etc_result.get(
                    "learned",
                    0,
                )
            )

            errors = _safe_int(
                etc_result.get(
                    "errors",
                    0,
                )
            )

            result["etc"]["processed"] = (
                processed
            )

            result["etc"]["analyzed"] = (
                analyzed
            )

            result["etc"]["learned"] = (
                learned
            )

            result["etc"]["errors_count"] = (
                errors
            )

            result["etc"]["message"] = (
                etc_result.get(
                    "message",
                    "",
                )
            )

            # =================================================
            # NOTHING TO PROCESS
            # =================================================

            if status == "nothing_to_process":

                result["etc"]["success"] = True
                result["etc"]["skipped"] = True

                self._add_step(
                    result,
                    "etc",
                    "skipped",
                    (
                        "⏭️ ETC: новых завершённых "
                        "фактов для обучения нет."
                    ),
                )

                return True

            # =================================================
            # COMPLETED
            # =================================================

            if (
                status == "completed"
                and errors == 0
            ):

                result["etc"]["success"] = True

                self._add_step(
                    result,
                    "etc",
                    "success",
                    (
                        "✅ ETC завершён: "
                        f"analyzed={analyzed}, "
                        f"learned={learned}, "
                        f"processed={processed}"
                    ),
                )

                return True

            # =================================================
            # PARTIAL
            # =================================================

            if status == "completed_with_errors":

                message = (
                    "⚠️ ETC завершён с ошибками: "
                    f"processed={processed}, "
                    f"errors={errors}"
                )

                result["etc"]["errors"].append(
                    message
                )

                result["errors"].append(
                    message
                )

                self._add_step(
                    result,
                    "etc",
                    "error",
                    message,
                )

                # Уже успешно обработанные матчи
                # ETC не откатывает.
                #
                # FAJ Cycle также ничего не удаляет.

                return False

            # =================================================
            # FAILED
            # =================================================

            if status == "failed":

                message = (
                    "❌ ETC завершился критической "
                    "ошибкой: "
                    f"{etc_result.get('message', 'unknown error')}"
                )

                result["etc"]["errors"].append(
                    message
                )

                result["errors"].append(
                    message
                )

                self._add_step(
                    result,
                    "etc",
                    "error",
                    message,
                )

                return False

            # =================================================
            # UNKNOWN
            # =================================================

            message = (
                "❌ ETC вернул неизвестный статус: "
                f"{status}"
            )

            result["etc"]["errors"].append(
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "etc",
                "error",
                message,
            )

            return False

        except Exception as exc:

            message = (
                f"❌ Ошибка ETC: {exc}"
            )

            result["etc"]["errors"].append(
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "etc",
                "error",
                message,
            )

            logger.exception(
                "ETC failed"
            )

            return False

    # ========================================================
    # PREDICTIONS
    # ========================================================

    def _run_predictions(
        self,
        result: Dict[str, Any],
        round_id: Optional[int] = None,
    ) -> bool:
        """
        Запускает PredictionManager.

        ETC не создаёт прогнозы.
        """

        self._add_step(
            result,
            "predictions",
            "running",
            "🔮 Прогнозирование...",
        )

        result["predictions"]["started"] = True

        try:

            # =================================================
            # ROUND
            # =================================================

            if round_id is not None:

                matches = self.db.get_matches(
                    round_id
                )

                if not matches:

                    message = (
                        f"Тур {round_id} "
                        "не содержит матчей "
                        "для прогнозирования"
                    )

                    result["predictions"]["error"] = (
                        message
                    )

                    result["errors"].append(
                        message
                    )

                    self._add_step(
                        result,
                        "predictions",
                        "error",
                        f"❌ {message}",
                    )

                    return False

                predictions_result = (
                    self.pred_mgr.predict_round(
                        round_id
                    )
                )

            # =================================================
            # ALL
            # =================================================

            else:

                predictions_result = (
                    self.pred_mgr.predict_all()
                )

            if not isinstance(
                predictions_result,
                dict,
            ):

                result["predictions"]["success"] = True

                self._add_step(
                    result,
                    "predictions",
                    "success",
                    "✅ Прогнозы созданы.",
                )

                return True

            status = predictions_result.get(
                "status",
                "",
            )

            total = _safe_int(
                predictions_result.get(
                    "total",
                    0,
                )
            )

            predicted = _safe_int(
                predictions_result.get(
                    "predicted",
                    0,
                )
            )

            errors = _safe_int(
                predictions_result.get(
                    "errors",
                    0,
                )
            )

            skipped = _safe_int(
                predictions_result.get(
                    "skipped",
                    0,
                )
            )

            result["predictions"]["total"] = (
                total
            )

            result["predictions"]["predicted"] = (
                predicted
            )

            result["predictions"]["errors"] = (
                errors
            )

            result["predictions"]["skipped_count"] = (
                skipped
            )

            # =================================================
            # COMPLETED
            # =================================================

            if (
                status == "completed"
                and errors == 0
            ):

                result["predictions"]["success"] = True

                self._add_step(
                    result,
                    "predictions",
                    "success",
                    (
                        "✅ Прогнозы созданы: "
                        f"created={predicted}, "
                        f"skipped={skipped}"
                    ),
                )

                return True

            # =================================================
            # NOTHING
            # =================================================

            if status == "nothing_to_predict":

                result["predictions"]["success"] = True
                result["predictions"]["skipped"] = True

                self._add_step(
                    result,
                    "predictions",
                    "skipped",
                    "⏭️ Новых прогнозов нет.",
                )

                return True

            # =================================================
            # PARTIAL
            # =================================================

            if status == "completed_with_errors":

                message = (
                    "⚠️ Прогнозы созданы с ошибками: "
                    f"created={predicted}, "
                    f"errors={errors}"
                )

                result["predictions"]["error"] = (
                    message
                )

                result["errors"].append(
                    message
                )

                self._add_step(
                    result,
                    "predictions",
                    "error",
                    message,
                )

                return False

            # =================================================
            # UNKNOWN
            # =================================================

            message = (
                "❌ Неизвестный статус "
                "прогнозирования: "
                f"{status}"
            )

            result["predictions"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "predictions",
                "error",
                message,
            )

            return False

        except Exception as exc:

            message = (
                f"❌ Ошибка прогнозирования: {exc}"
            )

            result["predictions"]["error"] = (
                message
            )

            result["errors"].append(
                message
            )

            self._add_step(
                result,
                "predictions",
                "error",
                message,
            )

            logger.exception(
                "Predictions failed"
            )

            return False

    # ========================================================
    # RESULT STRUCTURE
    # ========================================================

    def _new_result(
        self,
        started: str,
    ) -> Dict[str, Any]:

        return {
            "module": "FAJ Cycle",
            "version": FAJ_CYCLE_VERSION,

            "started_at": started,
            "finished_at": None,
            "elapsed_seconds": None,

            "ready": False,
            "status": "started",

            "errors": [],
            "steps": [],

            "database": {
                "ok": False,
                "error": None,
                "steps": [],
            },

            "matches": {
                "success": False,
                "total": 0,
                "error": None,
                "steps": [],
            },

            "etc": {
                "started": False,
                "success": False,
                "skipped": False,

                "result": None,

                "analyzed": 0,
                "learned": 0,
                "processed": 0,
                "errors_count": 0,

                "errors": [],
                "message": "",
                "steps": [],
            },

            "predictions": {
                "started": False,
                "success": False,
                "skipped": False,

                "total": 0,
                "predicted": 0,
                "errors": 0,
                "skipped_count": 0,

                "error": None,
                "steps": [],
            },
        }

    # ========================================================
    # STEP
    # ========================================================

    def _add_step(
        self,
        result: Dict[str, Any],
        section: str,
        status: str,
        message: str,
    ) -> None:
        """
        Добавляет диагностический шаг.
        """

        step = {
            "section": section,
            "status": status,
            "message": message,
            "timestamp": _now(),
        }

        result["steps"].append(
            step
        )

        if section in result:

            if "steps" not in result[section]:

                result[section]["steps"] = []

            result[section]["steps"].append(
                step
            )

    # ========================================================
    # FINISH
    # ========================================================

    def _finish(
        self,
        result: Dict[str, Any],
        started: str,
    ) -> Dict[str, Any]:
        """
        Финализирует цикл.
        """

        finished_at = _now()

        result["finished_at"] = (
            finished_at
        )

        try:

            started_dt = datetime.fromisoformat(
                started
            )

            finished_dt = datetime.fromisoformat(
                finished_at
            )

            result["elapsed_seconds"] = round(
                (
                    finished_dt - started_dt
                ).total_seconds(),
                2,
            )

        except Exception:

            result["elapsed_seconds"] = None

        # =====================================================
        # READY
        # =====================================================

        result["ready"] = (
            result["database"]["ok"]
            and result["matches"]["success"]
            and (
                result["etc"]["success"]
                or result["etc"]["skipped"]
            )
            and (
                result["predictions"]["success"]
                or result["predictions"]["skipped"]
            )
        )

        result["status"] = (
            "completed"
            if result["ready"]
            else "failed"
        )

        logger.info(
            "FAJ CYCLE FINISHED | "
            "status=%s | "
            "elapsed=%s | "
            "errors=%s",
            result["status"],
            result["elapsed_seconds"],
            len(result["errors"]),
        )

        logger.info(
            "=================================================="
        )

        return result


# ============================================================
# PUBLIC API
# ============================================================

def run_faj_cycle(
    db: Optional[FAJDatabase] = None,
    match_id: Optional[int] = None,
    round_id: Optional[int] = None,
    season_id: Optional[int] = None,
    force: bool = False,
    run_predictions: bool = True,
) -> Dict[str, Any]:
    """
    Публичная точка входа FAJ Cycle.
    """

    cycle = FAJCycle(
        db=db
    )

    return cycle.run(
        match_id=match_id,
        round_id=round_id,
        season_id=season_id,
        force=force,
        run_predictions=run_predictions,
    )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "FAJ Cycle — главный "
            "оркестратор FAJ Platform"
        ),
        formatter_class=(
            argparse.RawDescriptionHelpFormatter
        ),
        epilog="""
Примеры:

    python app/faj_cycle.py --match 123

    python app/faj_cycle.py --round 5

    python app/faj_cycle.py --season 1

    python app/faj_cycle.py --match 123 --force

    python app/faj_cycle.py --round 5 --no-predictions

        """,
    )

    parser.add_argument(
        "--match",
        type=int,
        dest="match_id",
        help="ID матча",
    )

    parser.add_argument(
        "--round",
        type=int,
        dest="round_id",
        help="ID тура",
    )

    parser.add_argument(
        "--season",
        type=int,
        dest="season_id",
        help="ID сезона",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Продолжать ETC при частичных ошибках",
    )

    parser.add_argument(
        "--no-predictions",
        action="store_true",
        help="Не запускать прогнозирование",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробный вывод",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=(
            logging.DEBUG
            if args.verbose
            else logging.INFO
        ),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    cycle = FAJCycle()

    result = cycle.run(
        match_id=args.match_id,
        round_id=args.round_id,
        season_id=args.season_id,
        force=args.force,
        run_predictions=(
            not args.no_predictions
        ),
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "FAJ CYCLE — RESULT"
    )

    print(
        "=" * 70
    )

    print(
        f"Status: {result.get('status', 'unknown')}"
    )

    print(
        "Ready: "
        + (
            "✅"
            if result.get("ready")
            else "❌"
        )
    )

    print(
        "Elapsed: "
        f"{result.get('elapsed_seconds', 'N/A')} sec"
    )

    errors = result.get(
        "errors",
        [],
    )

    if errors:

        print(
            "\nErrors:"
        )

        for error in errors:

            print(
                f"  ❌ {error}"
            )

    print(
        "\nSections:"
    )

    for section in (
        "database",
        "matches",
        "etc",
        "predictions",
    ):

        data = result.get(
            section,
            {},
        )

        success = data.get(
            "success",
            False,
        )

        skipped = data.get(
            "skipped",
            False,
        )

        if success:

            print(
                f"  ✅ {section}"
            )

        elif skipped:

            print(
                f"  ⏭️ {section}"
            )

        else:

            print(
                f"  ❌ {section}"
            )

    print(
        "=" * 70
    )

    if args.verbose:

        print(
            "\nFull result:"
        )

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
                ensure_ascii=False,
            )
        )

    sys.exit(
        0
        if result.get("ready")
        else 1
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
