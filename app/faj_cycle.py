#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ CYCLE
============================================================

Главный оркестратор FAJ.

ЦИКЛ:

    FAJ Cycle
        │
        ├── 1. Проверка БД
        │
        ├── 2. Загрузка новых результатов
        │
        ├── 3. Обучение Learning Engine
        │
        ├── 4. Расчёт прогнозов
        │
        └── 5. Финальная диагностика

ВАЖНЫЕ ПРИНЦИПЫ:

    - SQLite
    - используется существующая БД
    - database.py НЕ изменяется
    - DELETE отсутствует
    - DROP отсутствует
    - календарь не создаётся
    - паспорта не создаются
    - динамические данные не уничтожаются
    - цикл максимально идемпотентен
    - каждый этап возвращает диагностику
    - ошибка одного этапа не маскируется
    - Streamlit получает единый результат

============================================================
"""

from __future__ import annotations

import logging
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# IMPORTS
# ============================================================

from app.database import get_connection
from app.core.prediction_manager import get_prediction_manager
from app.learning_engine import run_learning

try:
    from app.rpl_historical_importer import (
        load_rpl_historical_results,
        get_historical_import_status,
    )
except ImportError:
    load_rpl_historical_results = None
    get_historical_import_status = None


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

FAJ_CYCLE_VERSION = "12.1"

DEFAULT_LEAGUE = "РПЛ"
DEFAULT_SEASON = "2026-2027"

EXPECTED_HISTORICAL_RESULTS = 24
NEXT_PREDICTION_ROUND = 4


# ============================================================
# DATABASE TABLES
# ============================================================

EXPECTED_TABLES = (
    "teams",
    "seasons",
    "rounds",
    "matches",
    "match_results",
    "predictions",
    "prediction_scores",
    "prediction_distributions",
    "learning_memory",
    "model_parameters",
)


# ============================================================
# RESULT FACTORY
# ============================================================

def _new_result() -> Dict[str, Any]:
    """
    Единый формат результата FAJ Cycle.
    """

    return {
        "success": False,
        "ready": False,

        "cycle": FAJ_CYCLE_VERSION,

        "started_at": None,
        "finished_at": None,

        "duration_seconds": 0.0,

        "database": {
            "connected": False,
            "tables": {},
            "missing_tables": [],
        },

        "historical": {
            "available": False,
            "success": False,
            "expected": EXPECTED_HISTORICAL_RESULTS,
            "inserted": 0,
            "already_present": 0,
            "updated": 0,
            "errors": [],
        },

        "learning": {
            "started": False,
            "success": False,
            "result": None,
            "errors": [],
        },

        "predictions": {
            "started": False,
            "success": False,
            "count": 0,
            "result": None,
            "errors": [],
        },

        "final": {
            "teams": 0,
            "results": 0,
            "predictions": 0,
            "learning_records": 0,
            "model_parameters": 0,
        },

        "steps": [],

        "errors": [],

        "messages": [],
    }


# ============================================================
# LOGGING
# ============================================================

def _log_step(
    result: Dict[str, Any],
    step: str,
    status: str,
    message: str,
) -> None:

    entry = {
        "step": step,
        "status": status,
        "message": message,
        "time": datetime.now().isoformat(),
    }

    result["steps"].append(entry)
    result["messages"].append(message)

    if status == "success":
        logger.info(message)

    elif status == "warning":
        logger.warning(message)

    else:
        logger.error(message)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def _check_database(
    result: Dict[str, Any],
) -> bool:
    """
    Проверяет существующую БД.

    Ничего не создаёт и не изменяет.
    """

    _log_step(
        result,
        "database",
        "running",
        "🔌 Проверка подключения к FAJ Database...",
    )

    conn = None

    try:

        conn = get_connection()

        if conn is None:
            raise RuntimeError(
                "get_connection() вернул None"
            )

        result["database"]["connected"] = True

        _log_step(
            result,
            "database",
            "success",
            "✅ Подключение к БД успешно",
        )

        cursor = conn.cursor()

        existing_tables = {}

        for table in EXPECTED_TABLES:

            cursor.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                AND name = ?
                LIMIT 1
                """,
                (table,),
            )

            exists = cursor.fetchone() is not None

            existing_tables[table] = exists

            if not exists:
                result["database"][
                    "missing_tables"
                ].append(table)

        result["database"]["tables"] = existing_tables

        if result["database"]["missing_tables"]:

            missing = ", ".join(
                result["database"]["missing_tables"]
            )

            _log_step(
                result,
                "database",
                "warning",
                f"⚠️ Отсутствуют таблицы: {missing}",
            )

        else:

            _log_step(
                result,
                "database",
                "success",
                "✅ Все необходимые таблицы обнаружены",
            )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка подключения к БД: {exc}"
        )

        result["errors"].append(message)

        _log_step(
            result,
            "database",
            "error",
            message,
        )

        logger.exception(
            "FAJ Cycle database check failed"
        )

        return False

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# DATABASE COUNTS
# ============================================================

def _count_table(
    cursor: sqlite3.Cursor,
    table: str,
) -> int:

    try:

        cursor.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        )

        row = cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])

    except Exception:

        return 0


def _read_final_state(
    result: Dict[str, Any],
) -> None:
    """
    Читает фактическое состояние БД.

    Только SELECT.
    """

    conn = None

    try:

        conn = get_connection()
        cursor = conn.cursor()

        result["final"]["teams"] = _count_table(
            cursor,
            "teams",
        )

        result["final"]["results"] = _count_table(
            cursor,
            "match_results",
        )

        result["final"]["predictions"] = _count_table(
            cursor,
            "predictions",
        )

        result["final"]["learning_records"] = (
            _count_table(
                cursor,
                "learning_memory",
            )
        )

        result["final"]["model_parameters"] = (
            _count_table(
                cursor,
                "model_parameters",
            )
        )

    except Exception as exc:

        logger.warning(
            "Unable to read final FAJ state: %s",
            exc,
        )

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# HISTORICAL RESULTS
# ============================================================

def _run_historical_import(
    result: Dict[str, Any],
) -> bool:
    """
    Загружает проверенные исторические результаты.

    Импортёр сам отвечает за:
        - идемпотентность
        - транзакцию
        - конфликт результатов
        - отсутствие DELETE
    """

    _log_step(
        result,
        "historical",
        "running",
        "📥 Проверка исторических результатов...",
    )

    if load_rpl_historical_results is None:

        message = (
            "⚠️ Historical Importer не подключён"
        )

        result["historical"]["errors"].append(
            message
        )

        _log_step(
            result,
            "historical",
            "warning",
            message,
        )

        return True

    try:

        status = None

        if get_historical_import_status:

            try:
                status = (
                    get_historical_import_status()
                )
            except Exception as exc:

                logger.warning(
                    "Historical status failed: %s",
                    exc,
                )

        if status:

            result["historical"][
                "available"
            ] = True

            if status.get("conflicts", 0) > 0:

                conflicts = status[
                    "conflicts"
                ]

                message = (
                    "❌ Обнаружены конфликты "
                    f"исторических результатов: "
                    f"{conflicts}"
                )

                result["historical"][
                    "errors"
                ].append(message)

                _log_step(
                    result,
                    "historical",
                    "error",
                    message,
                )

                return False

        import_result = (
            load_rpl_historical_results()
        )

        if not isinstance(
            import_result,
            dict,
        ):

            raise RuntimeError(
                "Historical Importer "
                "вернул некорректный результат"
            )

        result["historical"][
            "available"
        ] = True

        result["historical"][
            "success"
        ] = bool(
            import_result.get(
                "success",
                False,
            )
        )

        result["historical"][
            "inserted"
        ] = int(
            import_result.get(
                "inserted_results",
                0,
            )
            or 0
        )

        result["historical"][
            "already_present"
        ] = int(
            import_result.get(
                "already_present",
                0,
            )
            or 0
        )

        result["historical"][
            "updated"
        ] = int(
            import_result.get(
                "updated_matches",
                0,
            )
            or 0
        )

        errors = import_result.get(
            "errors",
            [],
        )

        if errors:
            result["historical"][
                "errors"
            ].extend(
                [str(x) for x in errors]
            )

        if not result["historical"]["success"]:

            message = (
                "❌ Исторический импорт "
                "завершился ошибкой"
            )

            _log_step(
                result,
                "historical",
                "error",
                message,
            )

            return False

        message = (
            "✅ Исторические результаты: "
            f"добавлено="
            f"{result['historical']['inserted']}, "
            f"уже было="
            f"{result['historical']['already_present']}"
        )

        _log_step(
            result,
            "historical",
            "success",
            message,
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка исторического импорта: "
            f"{exc}"
        )

        result["historical"][
            "errors"
        ].append(message)

        result["errors"].append(message)

        _log_step(
            result,
            "historical",
            "error",
            message,
        )

        logger.exception(
            "Historical import failed"
        )

        return False


# ============================================================
# LEARNING ENGINE
# ============================================================

def _run_learning(
    result: Dict[str, Any],
) -> bool:
    """
    Запускает LearningEngine.
    """

    _log_step(
        result,
        "learning",
        "running",
        "🧠 Запуск Learning Engine...",
    )

    result["learning"]["started"] = True

    try:

        # Используем run_learning() из learning_engine.py
        learning_result = run_learning()

        result["learning"]["result"] = learning_result

        if isinstance(
            learning_result,
            dict,
        ):

            result["learning"]["success"] = bool(
                learning_result.get(
                    "success",
                    True,
                )
            )

            errors = learning_result.get(
                "errors",
                [],
            )

            if errors:
                result["learning"]["errors"].extend(
                    [str(x) for x in errors]
                )

        else:

            result["learning"]["success"] = True

        if not result["learning"]["success"]:

            message = (
                "❌ Learning Engine "
                "вернул success=False"
            )

            result["learning"][
                "errors"
            ].append(message)

            _log_step(
                result,
                "learning",
                "error",
                message,
            )

            return False

        _log_step(
            result,
            "learning",
            "success",
            "✅ Learning Engine завершил работу",
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Learning Engine: {exc}"
        )

        result["learning"][
            "errors"
        ].append(message)

        result["errors"].append(message)

        _log_step(
            result,
            "learning",
            "error",
            message,
        )

        logger.exception(
            "Learning Engine failed"
        )

        return False


# ============================================================
# PREDICTION MANAGER
# ============================================================

def _run_predictions(
    result: Dict[str, Any],
) -> bool:
    """
    Запускает PredictionManager.
    """

    _log_step(
        result,
        "predictions",
        "running",
        "🔮 Запуск Prediction Manager...",
    )

    result["predictions"][
        "started"
    ] = True

    try:

        manager = get_prediction_manager()

        # Используем predict_round() для 4-го тура
        prediction_result = manager.predict_round(4)

        result["predictions"][
            "result"
        ] = prediction_result

        if isinstance(
            prediction_result,
            (list, tuple),
        ):

            result["predictions"][
                "count"
            ] = len(prediction_result)

            result["predictions"][
                "success"
            ] = True

        elif isinstance(
            prediction_result,
            dict,
        ):

            result["predictions"][
                "count"
            ] = prediction_result.get(
                "count",
                0,
            )

            result["predictions"][
                "success"
            ] = bool(
                prediction_result.get(
                    "success",
                    True,
                )
            )

        else:

            result["predictions"][
                "success"
            ] = True

        if not result["predictions"]["success"]:

            message = (
                "❌ Prediction Manager "
                "вернул success=False"
            )

            result["predictions"][
                "errors"
            ].append(message)

            _log_step(
                result,
                "predictions",
                "error",
                message,
            )

            return False

        _log_step(
            result,
            "predictions",
            "success",
            "✅ Prediction Manager завершил работу",
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Prediction Manager: {exc}"
        )

        result["predictions"][
            "errors"
        ].append(message)

        result["errors"].append(message)

        _log_step(
            result,
            "predictions",
            "error",
            message,
        )

        logger.exception(
            "Prediction Manager failed"
        )

        return False


# ============================================================
# FINAL VALIDATION
# ============================================================

def _final_validation(
    result: Dict[str, Any],
) -> bool:
    """
    Финальная проверка состояния системы.
    """

    _log_step(
        result,
        "final",
        "running",
        "🔍 Финальная проверка FAJ Cycle...",
    )

    _read_final_state(result)

    database_ok = (
        result["database"]["connected"]
        and not result["database"][
            "missing_tables"
        ]
    )

    historical_ok = (
        result["historical"]["success"]
    )

    learning_ok = (
        result["learning"]["success"]
    )

    predictions_ok = (
        result["predictions"]["success"]
    )

    result["ready"] = (
        database_ok
        and historical_ok
        and learning_ok
        and predictions_ok
    )

    if result["ready"]:

        _log_step(
            result,
            "final",
            "success",
            (
                "✅ FAJ Cycle полностью завершён: "
                f"результаты="
                f"{result['final']['results']}, "
                f"прогнозы="
                f"{result['final']['predictions']}, "
                f"learning="
                f"{result['final']['learning_records']}"
            ),
        )

        return True

    _log_step(
        result,
        "final",
        "error",
        "❌ FAJ Cycle не прошёл финальную проверку",
    )

    return False


# ============================================================
# PUBLIC API
# ============================================================

def run_faj_cycle() -> Dict[str, Any]:
    """
    Главная функция FAJ.
    """

    result = _new_result()

    started = datetime.now()

    result["started_at"] = (
        started.isoformat()
    )

    logger.info(
        "=" * 70
    )

    logger.info(
        "🚀 FAJ CYCLE v%s START",
        FAJ_CYCLE_VERSION,
    )

    logger.info(
        "=" * 70
    )

    try:

        if not _check_database(result):
            return _finish_result(
                result,
                started,
            )

        if not _run_historical_import(result):
            return _finish_result(
                result,
                started,
            )

        if not _run_learning(result):
            return _finish_result(
                result,
                started,
            )

        if not _run_predictions(result):
            return _finish_result(
                result,
                started,
            )

        _final_validation(result)

        return _finish_result(
            result,
            started,
        )

    except Exception as exc:

        message = (
            f"❌ Критическая ошибка FAJ Cycle: "
            f"{exc}"
        )

        result["errors"].append(message)

        _log_step(
            result,
            "cycle",
            "error",
            message,
        )

        logger.error(
            traceback.format_exc()
        )

        return _finish_result(
            result,
            started,
        )


# ============================================================
# FINISH
# ============================================================

def _finish_result(
    result: Dict[str, Any],
    started: datetime,
) -> Dict[str, Any]:

    finished = datetime.now()

    result["finished_at"] = (
        finished.isoformat()
    )

    result["duration_seconds"] = round(
        (
            finished - started
        ).total_seconds(),
        3,
    )

    result["success"] = bool(
        result["ready"]
    )

    logger.info(
        "=" * 70
    )

    logger.info(
        "FAJ CYCLE FINISHED | success=%s "
        "| duration=%.3fs",
        result["success"],
        result["duration_seconds"],
    )

    logger.info(
        "=" * 70
    )

    return result


# ============================================================
# FAJ CYCLE CLASS (для Streamlit)
# ============================================================

class FAJCycle:
    """
    Класс-обёртка для FAJ Cycle.
    
    Используется в streamlit_app.py для мягкого подключения.
    """
    
    VERSION = FAJ_CYCLE_VERSION
    
    def __init__(self):
        self.version = self.VERSION
    
    def run(self) -> Dict[str, Any]:
        """
        Запуск FAJ Cycle.
        
        Returns:
            Dict с полной диагностикой цикла.
        """
        return run_faj_cycle()
    
    def run_cycle(self) -> Dict[str, Any]:
        """
        Альтернативный метод для совместимости.
        """
        return run_faj_cycle()
    
    def execute(self) -> Dict[str, Any]:
        """
        Альтернативный метод для совместимости.
        """
        return run_faj_cycle()
    
    def status(self) -> Dict[str, Any]:
        """
        Диагностический статус.
        """
        return {
            "version": self.VERSION,
            "available": True,
            "status": "READY",
        }


# ============================================================
# ALIASES
# ============================================================

def run_cycle() -> Dict[str, Any]:
    """
    Короткий alias для Streamlit.
    """

    return run_faj_cycle()


def execute_faj_cycle() -> Dict[str, Any]:
    """
    Дополнительный совместимый alias.
    """

    return run_faj_cycle()


# ============================================================
# CLI
# ============================================================

def _print_result(
    result: Dict[str, Any],
) -> None:

    print()
    print("=" * 70)
    print("FAJ CYCLE v12.1")
    print("=" * 70)

    print(
        f"Успех:       {result['success']}"
    )

    print(
        f"Готов:       {result['ready']}"
    )

    print(
        f"Время:       "
        f"{result['duration_seconds']} сек."
    )

    print()
    print("DATABASE")
    print(
        f"  connected: "
        f"{result['database']['connected']}"
    )

    print()
    print("HISTORICAL")
    print(
        f"  inserted: "
        f"{result['historical']['inserted']}"
    )

    print(
        f"  already: "
        f"{result['historical']['already_present']}"
    )

    print()
    print("LEARNING")
    print(
        f"  success: "
        f"{result['learning']['success']}"
    )

    print()
    print("PREDICTIONS")
    print(
        f"  success: "
        f"{result['predictions']['success']}"
    )

    print(
        f"  count: "
        f"{result['predictions']['count']}"
    )

    print()
    print("FINAL DATABASE STATE")

    for key, value in result[
        "final"
    ].items():

        print(
            f"  {key}: {value}"
        )

    print()

    if result["errors"]:

        print("ERRORS:")

        for error in result["errors"]:

            print(
                f"  ❌ {error}"
            )

    print()
    print("STEPS:")

    for step in result["steps"]:

        print(
            f"  [{step['status']}] "
            f"{step['step']}: "
            f"{step['message']}"
        )

    print("=" * 70)


# ============================================================
# MAIN
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

    cycle_result = run_faj_cycle()

    _print_result(
        cycle_result
    )
