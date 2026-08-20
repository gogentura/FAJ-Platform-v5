#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ CYCLE — Главный оркестратор
============================================================

НАЗНАЧЕНИЕ:
    FAJ Cycle — главный оркестратор платформы.

    Запускает полный цикл FAJ:

        1. Проверка БД
        2. Загрузка матчей
        3. Обновление результатов
        4. Основное обучение (app/learning_engine.py)
        5. ETC — Evolution Training Center
        6. Прогнозирование

    Используется:
        - faj_cycle.py --match <match_id>
        - faj_cycle.py --round <round_id>
        - faj_cycle.py --season <season_id>
        - faj_cycle.py --match <match_id> --force

    ETC:
        - работает только с завершёнными матчами;
        - использует append-only learning_memory;
        - не управляет календарём;
        - не создаёт прогнозы;
        - не заменяет основной Learning Engine.
============================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.result_manager import ResultManager
from app.learning_engine import run_learning
from app.etc.etc_controller import run_etc
from app.core.prediction_manager import get_prediction_manager


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
FAJ_CYCLE_VERSION = "1.0"


def _now() -> str:
    return datetime.now().isoformat()


# ============================================================
# RESULT MANAGER HELPERS
# ============================================================

def _update_results(result_mgr: ResultManager) -> Dict[str, Any]:
    """Обновляет результаты матчей."""
    return result_mgr.update_all()


# ============================================================
# FAJ CYCLE
# ============================================================

class FAJCycle:
    """
    Главный оркестратор FAJ.

    Запускает полный цикл:
        Database → Matches → Results → Learning → ETC → Predictions
    """

    def __init__(self):
        self.db = FAJDatabase()
        self.match_mgr = MatchManager(self.db)
        self.result_mgr = ResultManager(self.db)
        self.pred_mgr = get_prediction_manager()

    # ========================================================
    # CYCLE
    # ========================================================

    def run(
        self,
        match_id: Optional[int] = None,
        round_id: Optional[int] = None,
        season_id: Optional[int] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Запускает полный FAJ Cycle.

        Аргументы:
            match_id: ID матча для обработки
            round_id: ID тура для обработки
            season_id: ID сезона для обработки
            force: принудительный запуск даже при ошибках

        Возвращает:
            dict: результат выполнения цикла
        """
        started = _now()

        result = self._new_result(started)

        logger.info("FAJ Cycle started: %s", started)

        # =====================================================
        # 1. DATABASE
        # =====================================================

        if not self._check_database(result):
            return self._finish(result, started)

        # =====================================================
        # 2. MATCHES
        # =====================================================

        if not self._load_matches(result, match_id, round_id, season_id):
            return self._finish(result, started)

        # =====================================================
        # 3. RESULTS
        # =====================================================

        if not self._update_results(result):
            return self._finish(result, started)

        # =====================================================
        # 4. LEARNING
        # =====================================================

        if not self._run_learning(result):
            return self._finish(result, started)

        # =====================================================
        # 5. ETC — EVOLUTION TRAINING CENTER
        # =====================================================

        if not self._run_etc(result):
            return self._finish(result, started)

        # =====================================================
        # 6. PREDICTIONS
        # =====================================================

        if not self._run_predictions(result, round_id=round_id):
            return self._finish(result, started)

        # =====================================================
        # COMPLETE
        # =====================================================

        return self._finish(result, started)

    # ========================================================
    # STEPS
    # ========================================================

    def _check_database(self, result: Dict[str, Any]) -> bool:
        """Проверяет состояние базы данных."""
        self._add_step(
            result,
            "database",
            "running",
            "📁 Проверка базы данных..."
        )

        try:
            status = self.db.get_status()

            if status.get("status") == "online":
                result["database"]["ok"] = True
                self._add_step(
                    result,
                    "database",
                    "success",
                    f"✅ База данных доступна: {status.get('file', 'unknown')}"
                )
                return True

            message = f"❌ База данных недоступна: {status.get('error', 'unknown error')}"
            result["database"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "database",
                "error",
                message
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка проверки БД: {exc}"
            result["database"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "database",
                "error",
                message
            )
            logger.exception("Database check failed")
            return False

    def _load_matches(
        self,
        result: Dict[str, Any],
        match_id: Optional[int] = None,
        round_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> bool:
        """Загружает матчи."""
        self._add_step(
            result,
            "matches",
            "running",
            "📋 Загрузка матчей..."
        )

        try:
            matches: List[Dict[str, Any]] = []

            if match_id is not None:
                match = self.db.get_match_by_uuid(str(match_id))
                if match:
                    matches.append(match)
                else:
                    match = self.db.get_match_by_uuid(f"match_{match_id}")
                    if match:
                        matches.append(match)
                    else:
                        message = f"Матч {match_id} не найден"
                        result["matches"]["error"] = message
                        result["errors"].append(message)
                        self._add_step(
                            result,
                            "matches",
                            "error",
                            f"❌ {message}"
                        )
                        return False

            elif round_id is not None:
                matches = self.db.get_matches(round_id)
                if not matches:
                    message = f"Тур {round_id} не найден или не содержит матчей"
                    result["matches"]["error"] = message
                    result["errors"].append(message)
                    self._add_step(
                        result,
                        "matches",
                        "error",
                        f"❌ {message}"
                    )
                    return False

            elif season_id is not None:
                rounds = self.db.get_rounds(season_id)
                for round_item in rounds:
                    round_data = dict(round_item) if round_item else {}
                    round_id_value = round_data.get("id")
                    if round_id_value is not None:
                        round_matches = self.db.get_matches(round_id_value)
                        if round_matches:
                            matches.extend(round_matches)
                if not matches:
                    message = f"Сезон {season_id} не содержит матчей"
                    result["matches"]["error"] = message
                    result["errors"].append(message)
                    self._add_step(
                        result,
                        "matches",
                        "error",
                        f"❌ {message}"
                    )
                    return False

            else:
                # Без фильтра — все матчи
                matches = self.db.get_matches()

            result["matches"]["total"] = len(matches)

            if matches:
                result["matches"]["success"] = True
                self._add_step(
                    result,
                    "matches",
                    "success",
                    f"✅ Загружено матчей: {len(matches)}"
                )
                return True

            message = "Матчи не найдены"
            result["matches"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "matches",
                "error",
                f"❌ {message}"
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка загрузки матчей: {exc}"
            result["matches"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "matches",
                "error",
                message
            )
            logger.exception("Matches loading failed")
            return False

    def _update_results(self, result: Dict[str, Any]) -> bool:
        """Обновляет результаты матчей."""
        self._add_step(
            result,
            "results",
            "running",
            "📊 Обновление результатов..."
        )

        try:
            update_result = _update_results(self.result_mgr)

            if not isinstance(update_result, dict):
                result["results"]["success"] = True
                self._add_step(
                    result,
                    "results",
                    "success",
                    "✅ Результаты обновлены"
                )
                return True

            status = update_result.get("status")
            processed = update_result.get("processed", 0) or 0
            errors = update_result.get("errors", 0) or 0
            updated = update_result.get("updated", 0) or 0

            result["results"]["processed"] = int(processed)
            result["results"]["updated"] = int(updated)
            result["results"]["errors"] = int(errors)

            if status == "completed" and errors == 0:
                result["results"]["success"] = True
                self._add_step(
                    result,
                    "results",
                    "success",
                    f"✅ Результаты обновлены: обновлено={updated}, всего={processed}"
                )
                return True

            if status == "completed_with_errors":
                message = f"⚠️ Результаты обновлены с ошибками: обновлено={updated}, ошибок={errors}"
                result["results"]["error"] = message
                result["errors"].append(message)
                self._add_step(
                    result,
                    "results",
                    "error",
                    message
                )
                return False

            if status == "nothing_to_update":
                result["results"]["success"] = True
                self._add_step(
                    result,
                    "results",
                    "skipped",
                    "⏭️ Новых результатов для обновления нет"
                )
                return True

            message = f"❌ Неизвестный статус обновления результатов: {status}"
            result["results"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "results",
                "error",
                message
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка обновления результатов: {exc}"
            result["results"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "results",
                "error",
                message
            )
            logger.exception("Results update failed")
            return False

    # ========================================================
    # 4. LEARNING
    # ========================================================

    def _run_learning(self, result: Dict[str, Any]) -> bool:
        """Запускает основной Learning Engine."""
        self._add_step(
            result,
            "learning",
            "running",
            "🧠 Запуск основного обучения FAJ..."
        )
        result["learning"]["started"] = True

        try:
            learning_result = run_learning(force=False)

            if not isinstance(learning_result, dict):
                result["learning"]["success"] = True
                self._add_step(
                    result,
                    "learning",
                    "success",
                    "✅ Обучение завершено"
                )
                return True

            status = learning_result.get("status", "")
            processed = learning_result.get("processed", 0) or 0
            errors = learning_result.get("errors", 0) or 0

            result["learning"]["processed"] = int(processed)
            result["learning"]["result"] = learning_result

            if status == "nothing_to_process":
                result["learning"]["skipped"] = True
                self._add_step(
                    result,
                    "learning",
                    "skipped",
                    "⏭️ Обучение: новых данных нет"
                )
                return True

            if status == "completed" and errors == 0:
                result["learning"]["success"] = True
                self._add_step(
                    result,
                    "learning",
                    "success",
                    f"✅ Обучение завершено: обработано={processed}"
                )
                return True

            if status == "completed_with_errors":
                message = f"❌ Обучение завершено с ошибками: обработано={processed}, ошибок={errors}"
                result["learning"]["error"] = message
                result["errors"].append(message)
                self._add_step(
                    result,
                    "learning",
                    "error",
                    message
                )
                return False

            if status == "failed":
                message = f"❌ Обучение завершилось критической ошибкой: {learning_result.get('message', 'unknown error')}"
                result["learning"]["error"] = message
                result["errors"].append(message)
                self._add_step(
                    result,
                    "learning",
                    "error",
                    message
                )
                return False

            message = f"❌ Неизвестный статус обучения: {status}"
            result["learning"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "learning",
                "error",
                message
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка основного обучения: {exc}"
            result["learning"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "learning",
                "error",
                message
            )
            logger.exception("Learning failed")
            return False

    # ========================================================
    # 5. ETC — EVOLUTION TRAINING CENTER
    # ========================================================

    def _run_etc(self, result: Dict[str, Any]) -> bool:
        """
        Запускает ETC после основного Learning Engine.

        ETC:
            - работает только с завершёнными матчами;
            - использует append-only learning_memory;
            - не управляет календарём;
            - не создаёт прогнозы;
            - не заменяет основной Learning Engine.
        """
        self._add_step(
            result,
            "etc",
            "running",
            "🧬 Запуск ETC — Evolution Training Center..."
        )
        result["etc"]["started"] = True

        try:
            etc_result = run_etc()
            result["etc"]["result"] = etc_result

            if not isinstance(etc_result, dict):
                result["etc"]["success"] = True
                self._add_step(
                    result,
                    "etc",
                    "success",
                    "✅ ETC завершён"
                )
                return True

            status = etc_result.get("status", "")
            processed = etc_result.get("processed", 0) or 0
            errors = etc_result.get("errors", 0) or 0
            result["etc"]["processed"] = int(processed)

            # ETC не нашёл новых матчей
            if status == "nothing_to_process":
                result["etc"]["skipped"] = True
                self._add_step(
                    result,
                    "etc",
                    "skipped",
                    "⏭️ ETC: новых завершённых матчей для эволюции нет"
                )
                return True

            # ETC завершился полностью
            if status == "completed" and errors == 0:
                result["etc"]["success"] = True
                self._add_step(
                    result,
                    "etc",
                    "success",
                    f"✅ ETC завершён: обработано матчей={processed}"
                )
                return True

            # ETC завершился с ошибками
            if status == "completed_with_errors":
                message = (
                    f"❌ ETC завершён с ошибками: "
                    f"обработано={processed}, ошибок={errors}"
                )
                result["etc"]["errors"].append(message)
                result["errors"].append(message)
                self._add_step(
                    result,
                    "etc",
                    "error",
                    message
                )
                return False

            # Явный failed
            if status == "failed":
                message = (
                    "❌ ETC завершился критической ошибкой: "
                    f"{etc_result.get('message', 'unknown error')}"
                )
                result["etc"]["errors"].append(message)
                result["errors"].append(message)
                self._add_step(
                    result,
                    "etc",
                    "error",
                    message
                )
                return False

            # Неизвестный статус считаем ошибкой
            message = f"❌ ETC вернул неизвестный статус: {status}"
            result["etc"]["errors"].append(message)
            result["errors"].append(message)
            self._add_step(
                result,
                "etc",
                "error",
                message
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка ETC: {exc}"
            result["etc"]["errors"].append(message)
            result["errors"].append(message)
            self._add_step(
                result,
                "etc",
                "error",
                message
            )
            logger.exception("ETC failed")
            return False

    # ========================================================
    # 6. PREDICTIONS
    # ========================================================

    def _run_predictions(
        self,
        result: Dict[str, Any],
        round_id: Optional[int] = None,
    ) -> bool:
        """Запускает прогнозирование."""
        self._add_step(
            result,
            "predictions",
            "running",
            "🔮 Прогнозирование..."
        )
        result["predictions"]["started"] = True

        try:
            if round_id is not None:
                # Прогнозируем конкретный тур
                matches = self.db.get_matches(round_id)
                if not matches:
                    message = f"Тур {round_id} не содержит матчей для прогнозирования"
                    result["predictions"]["error"] = message
                    result["errors"].append(message)
                    self._add_step(
                        result,
                        "predictions",
                        "error",
                        f"❌ {message}"
                    )
                    return False

                predictions_result = self.pred_mgr.predict_round(round_id)

            else:
                # Прогнозируем все матчи без прогнозов
                predictions_result = self.pred_mgr.predict_all()

            if not isinstance(predictions_result, dict):
                result["predictions"]["success"] = True
                self._add_step(
                    result,
                    "predictions",
                    "success",
                    "✅ Прогнозы созданы"
                )
                return True

            status = predictions_result.get("status", "")
            total = predictions_result.get("total", 0) or 0
            predicted = predictions_result.get("predicted", 0) or 0
            errors = predictions_result.get("errors", 0) or 0
            skipped = predictions_result.get("skipped", 0) or 0

            result["predictions"]["total"] = int(total)
            result["predictions"]["predicted"] = int(predicted)
            result["predictions"]["errors"] = int(errors)
            result["predictions"]["skipped"] = int(skipped)

            if status == "completed" and errors == 0:
                result["predictions"]["success"] = True
                self._add_step(
                    result,
                    "predictions",
                    "success",
                    f"✅ Прогнозы созданы: создано={predicted}, пропущено={skipped}"
                )
                return True

            if status == "completed_with_errors":
                message = f"⚠️ Прогнозы созданы с ошибками: создано={predicted}, ошибок={errors}"
                result["predictions"]["error"] = message
                result["errors"].append(message)
                self._add_step(
                    result,
                    "predictions",
                    "error",
                    message
                )
                return False

            if status == "nothing_to_predict":
                result["predictions"]["success"] = True
                self._add_step(
                    result,
                    "predictions",
                    "skipped",
                    "⏭️ Прогнозов для создания нет"
                )
                return True

            message = f"❌ Неизвестный статус прогнозирования: {status}"
            result["predictions"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "predictions",
                "error",
                message
            )
            return False

        except Exception as exc:
            message = f"❌ Ошибка прогнозирования: {exc}"
            result["predictions"]["error"] = message
            result["errors"].append(message)
            self._add_step(
                result,
                "predictions",
                "error",
                message
            )
            logger.exception("Predictions failed")
            return False

    # ========================================================
    # HELPERS
    # ========================================================

    def _new_result(self, started: str) -> Dict[str, Any]:
        return {
            "started_at": started,
            "finished_at": None,
            "elapsed_seconds": None,
            "ready": False,
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
            "results": {
                "success": False,
                "processed": 0,
                "updated": 0,
                "errors": 0,
                "error": None,
                "steps": [],
            },
            "learning": {
                "started": False,
                "success": False,
                "skipped": False,
                "error": None,
                "errors": [],
                "processed": 0,
                "message": "",
                "steps": [],
            },
            "etc": {
                "started": False,
                "success": False,
                "skipped": False,
                "result": None,
                "processed": 0,
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
                "error": None,
                "steps": [],
            },
        }

    def _add_step(
        self,
        result: Dict[str, Any],
        section: str,
        status: str,
        message: str,
    ) -> None:
        """Добавляет шаг в результат."""
        step = {
            "section": section,
            "status": status,
            "message": message,
            "timestamp": _now(),
        }
        result["steps"].append(step)

        if section in result:
            if "steps" not in result[section]:
                result[section]["steps"] = []
            result[section]["steps"].append(step)

    def _finish(
        self,
        result: Dict[str, Any],
        started: str,
    ) -> Dict[str, Any]:
        """Завершает цикл."""
        finished_at = _now()
        result["finished_at"] = finished_at

        try:
            started_dt = datetime.fromisoformat(started)
            finished_dt = datetime.fromisoformat(finished_at)
            result["elapsed_seconds"] = round(
                (finished_dt - started_dt).total_seconds(),
                2,
            )
        except Exception:
            result["elapsed_seconds"] = None

        result["ready"] = (
            result["database"]["ok"]
            and result["matches"]["success"]
            and result["results"]["success"]
            and (result["learning"]["success"] or result["learning"]["skipped"])
            and (result["etc"]["success"] or result["etc"]["skipped"])
            and (result["predictions"]["success"] or result["predictions"]["skipped"])
        )

        status = "completed" if result["ready"] else "failed"
        logger.info(
            "FAJ Cycle finished: status=%s, elapsed=%s, errors=%s",
            status,
            result["elapsed_seconds"],
            len(result["errors"]),
        )

        result["status"] = status
        return result


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="FAJ Cycle — главный оркестратор FAJ Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
    faj_cycle.py --match 123
    faj_cycle.py --round 5
    faj_cycle.py --season 1
    faj_cycle.py --match 123 --force
    faj_cycle.py --round 5 --force
        """,
    )

    parser.add_argument(
        "--match",
        type=int,
        help="ID матча для обработки",
        dest="match_id",
    )

    parser.add_argument(
        "--round",
        type=int,
        help="ID тура для обработки",
        dest="round_id",
    )

    parser.add_argument(
        "--season",
        type=int,
        help="ID сезона для обработки",
        dest="season_id",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительный запуск даже при ошибках",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробный вывод",
    )

    args = parser.parse_args()

    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    # Запуск цикла
    cycle = FAJCycle()
    result = cycle.run(
        match_id=args.match_id,
        round_id=args.round_id,
        season_id=args.season_id,
        force=args.force,
    )

    # Вывод результата
    print("\n" + "=" * 70)
    print("FAJ CYCLE — RESULT")
    print("=" * 70)

    status = result.get("status", "unknown")
    ready = result.get("ready", False)

    print(f"Status: {status}")
    print(f"Ready: {'✅' if ready else '❌'}")
    print(f"Elapsed: {result.get('elapsed_seconds', 'N/A')} sec")

    errors = result.get("errors", [])
    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  ❌ {error}")

    print("\nSections:")
    for section in ["database", "matches", "results", "learning", "etc", "predictions"]:
        data = result.get(section, {})
        success = data.get("success", False)
        skipped = data.get("skipped", False)
        if success or skipped:
            status_text = "✅" if success else "⏭️" if skipped else "❌"
            print(f"  {status_text} {section}")

    print("=" * 70)

    if args.verbose:
        print("\nFull result:")
        import json
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))

    sys.exit(0 if ready else 1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
