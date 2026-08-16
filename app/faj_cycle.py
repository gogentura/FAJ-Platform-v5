#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ CYCLE — ЖЁСТКИЙ ОРКЕСТРАТОР
============================================================

ЦИКЛ:

    FAJ Cycle
        │
        ├── 1. DATABASE CHECK
        │      │
        │      └── ошибка → STOP
        │
        ├── 2. HISTORICAL RESULTS
        │      │
        │      ├── новые результаты → RUN
        │      ├── уже существуют → SKIP
        │      └── конфликт → STOP
        │
        ├── 3. LEARNING
        │      │
        │      ├── new_results > 0 → RUN
        │      └── new_results = 0 → SKIP
        │
        ├── 4. PREDICTIONS
        │      │
        │      └── только если этапы 1-3 OK
        │
        └── 5. FINAL DIAGNOSTIC

ПРИНЦИПЫ:
    - ошибка останавливает зависимые этапы
    - Learning только при новых фактах
    - Prediction только после успешного Learning (или если Learning SKIPPED)
    - отсутствие таблиц → STOP
    - конфликт исторических данных → STOP
    - никаких DELETE/DROP
============================================================
"""

from __future__ import annotations

import logging
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# IMPORTS
# ============================================================

from app.database import get_connection
from app.core.prediction_manager import get_prediction_manager
from app.learning_engine import run_learning

from app.loaders.rpl_historical_importer import (
    load_rpl_historical_results,
    get_historical_import_status,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

FAJ_CYCLE_VERSION = "12.1"

LEAGUE = "РПЛ"
SEASON = "2026-2027"

EXPECTED_INITIAL_HISTORICAL = 24  # 1-3 туры
NEXT_PREDICTION_ROUND = 5         # 5-й тур (4-й уже сыгран)

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
# RESULT
# ============================================================

def _new_result() -> Dict[str, Any]:
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
            "ok": False,
        },
        "historical": {
            "available": False,
            "success": False,
            "skipped": False,
            "conflict": False,
            "expected": EXPECTED_INITIAL_HISTORICAL,
            "inserted": 0,
            "already_present": 0,
            "updated": 0,
            "errors": [],
        },
        "learning": {
            "started": False,
            "success": False,
            "skipped": False,
            "result": None,
            "errors": [],
        },
        "predictions": {
            "started": False,
            "success": False,
            "round": NEXT_PREDICTION_ROUND,
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


def _add_step(result: Dict[str, Any], step: str, status: str, message: str) -> None:
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
    elif status == "skipped":
        logger.info(f"⏭️ {message}")
    elif status == "warning":
        logger.warning(message)
    else:
        logger.error(message)


# ============================================================
# 1. DATABASE CHECK
# ============================================================

def _check_database(result: Dict[str, Any]) -> bool:
    _add_step(result, "database", "running", "🔌 Проверка подключения к FAJ Database...")

    conn = None
    try:
        conn = get_connection()
        if conn is None:
            raise RuntimeError("get_connection() вернул None")

        result["database"]["connected"] = True
        _add_step(result, "database", "success", "✅ Подключение к БД успешно")

        cursor = conn.cursor()
        existing_tables = {}
        missing = []

        for table in EXPECTED_TABLES:
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
            exists = cursor.fetchone() is not None
            existing_tables[table] = exists
            if not exists:
                missing.append(table)

        result["database"]["tables"] = existing_tables
        result["database"]["missing_tables"] = missing

        if missing:
            msg = f"❌ Отсутствуют таблицы: {', '.join(missing)}"
            _add_step(result, "database", "error", msg)
            result["errors"].append(msg)
            result["database"]["ok"] = False
            return False

        result["database"]["ok"] = True
        _add_step(result, "database", "success", "✅ Все необходимые таблицы обнаружены")
        return True

    except Exception as e:
        msg = f"❌ Ошибка подключения к БД: {e}"
        result["errors"].append(msg)
        _add_step(result, "database", "error", msg)
        result["database"]["ok"] = False
        return False

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 2. HISTORICAL RESULTS
# ============================================================

def _run_historical(result: Dict[str, Any]) -> bool:
    _add_step(result, "historical", "running", "📥 Проверка исторических результатов...")

    try:
        # Получаем статус
        status = get_historical_import_status()

        if not status.get("success", False):
            result["historical"]["errors"].extend(status.get("errors", []))
            msg = "❌ Не удалось получить статус исторических данных"
            _add_step(result, "historical", "error", msg)
            result["errors"].append(msg)
            return False

        result["historical"]["available"] = True
        result["historical"]["conflict"] = status.get("conflicts", 0) > 0

        # Конфликт → STOP
        if result["historical"]["conflict"]:
            conflicts = status.get("conflicts", 0)
            msg = f"❌ Обнаружены конфликты исторических результатов: {conflicts}"
            _add_step(result, "historical", "error", msg)
            result["errors"].append(msg)
            return False

        # Уже есть все 24 результата
        if status.get("present", 0) >= EXPECTED_INITIAL_HISTORICAL:
            result["historical"]["success"] = True
            result["historical"]["skipped"] = True
            result["historical"]["already_present"] = status.get("present", 0)
            _add_step(result, "historical", "skipped", f"⏭️ Исторические результаты уже загружены: {status['present']}/{EXPECTED_INITIAL_HISTORICAL}")
            return True

        # Нужно импортировать
        import_result = load_rpl_historical_results()

        if not import_result.get("success", False):
            result["historical"]["errors"].extend(import_result.get("errors", []))
            msg = "❌ Исторический импорт завершился ошибкой"
            _add_step(result, "historical", "error", msg)
            result["errors"].append(msg)
            return False

        result["historical"]["success"] = True
        result["historical"]["inserted"] = import_result.get("inserted_results", 0)
        result["historical"]["already_present"] = import_result.get("already_present", 0)
        result["historical"]["updated"] = import_result.get("updated_matches", 0)

        _add_step(
            result,
            "historical",
            "success",
            f"✅ Исторические результаты: добавлено={result['historical']['inserted']}, уже было={result['historical']['already_present']}"
        )

        return True

    except Exception as e:
        msg = f"❌ Ошибка исторического импорта: {e}"
        result["errors"].append(msg)
        _add_step(result, "historical", "error", msg)
        logger.exception("Historical import failed")
        return False


# ============================================================
# 3. LEARNING
# ============================================================

def _run_learning(result: Dict[str, Any]) -> bool:
    # Проверяем, есть ли новые результаты
    has_new_results = (
        result["historical"]["inserted"] > 0
        or result["historical"]["updated"] > 0
    )

    if not has_new_results and result["historical"]["success"]:
        result["learning"]["skipped"] = True
        _add_step(result, "learning", "skipped", "⏭️ Новых результатов нет — обучение пропущено")
        return True

    _add_step(result, "learning", "running", "🧠 Запуск Learning Engine...")
    result["learning"]["started"] = True

    try:
        learning_result = run_learning()
        result["learning"]["result"] = learning_result

        if isinstance(learning_result, dict):
            success = learning_result.get("success", False)
            skipped = learning_result.get("skipped", False)

            if skipped:
                result["learning"]["skipped"] = True
                _add_step(result, "learning", "skipped", "⏭️ Learning Engine: обучение пропущено (набор уже изучен)")
                return True

            if not success:
                errors = learning_result.get("errors", [])
                result["learning"]["errors"].extend(errors)
                msg = "❌ Learning Engine вернул success=False"
                _add_step(result, "learning", "error", msg)
                result["errors"].append(msg)
                return False

            result["learning"]["success"] = True
            _add_step(result, "learning", "success", f"✅ Learning Engine завершил работу")
            return True

        result["learning"]["success"] = True
        _add_step(result, "learning", "success", "✅ Learning Engine завершил работу")
        return True

    except Exception as e:
        msg = f"❌ Ошибка Learning Engine: {e}"
        result["learning"]["errors"].append(msg)
        result["errors"].append(msg)
        _add_step(result, "learning", "error", msg)
        logger.exception("Learning Engine failed")
        return False


# ============================================================
# 4. PREDICTIONS
# ============================================================

def _run_predictions(result: Dict[str, Any]) -> bool:
    _add_step(result, "predictions", "running", f"🔮 Запуск Prediction Manager для тура {NEXT_PREDICTION_ROUND}...")
    result["predictions"]["started"] = True

    try:
        manager = get_prediction_manager()
        prediction_result = manager.predict_round(NEXT_PREDICTION_ROUND)

        result["predictions"]["result"] = prediction_result

        if isinstance(prediction_result, (list, tuple)):
            result["predictions"]["count"] = len(prediction_result)
            result["predictions"]["success"] = True
            _add_step(result, "predictions", "success", f"✅ Прогнозы рассчитаны: {len(prediction_result)} матчей")
            return True

        if isinstance(prediction_result, dict):
            result["predictions"]["count"] = prediction_result.get("count", 0)
            result["predictions"]["success"] = bool(prediction_result.get("success", False))
            if result["predictions"]["success"]:
                _add_step(result, "predictions", "success", f"✅ Прогнозы рассчитаны: {result['predictions']['count']} матчей")
            else:
                errors = prediction_result.get("errors", [])
                result["predictions"]["errors"].extend(errors)
                msg = "❌ Prediction Manager вернул success=False"
                _add_step(result, "predictions", "error", msg)
                result["errors"].append(msg)
            return result["predictions"]["success"]

        result["predictions"]["success"] = True
        _add_step(result, "predictions", "success", "✅ Прогнозы рассчитаны")
        return True

    except Exception as e:
        msg = f"❌ Ошибка Prediction Manager: {e}"
        result["predictions"]["errors"].append(msg)
        result["errors"].append(msg)
        _add_step(result, "predictions", "error", msg)
        logger.exception("Prediction Manager failed")
        return False


# ============================================================
# 5. FINAL
# ============================================================

def _read_final_state(result: Dict[str, Any]) -> None:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        tables = {
            "teams": "teams",
            "match_results": "match_results",
            "predictions": "predictions",
            "learning_memory": "learning_memory",
            "model_parameters": "model_parameters",
        }
        for key, table in tables.items():
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                row = cursor.fetchone()
                result["final"][key] = row[0] if row else 0
            except Exception:
                result["final"][key] = 0
    except Exception as e:
        logger.warning("Unable to read final state: %s", e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# PUBLIC API
# ============================================================

def run_faj_cycle() -> Dict[str, Any]:
    result = _new_result()
    started = datetime.now()
    result["started_at"] = started.isoformat()

    logger.info("=" * 70)
    logger.info("🚀 FAJ CYCLE v%s START", FAJ_CYCLE_VERSION)
    logger.info("=" * 70)

    try:
        # ====================================================
        # 1. DATABASE
        # ====================================================
        if not _check_database(result):
            return _finish(result, started)

        # ====================================================
        # 2. HISTORICAL
        # ====================================================
        if not _run_historical(result):
            return _finish(result, started)

        # ====================================================
        # 3. LEARNING (только если есть новые факты)
        # ====================================================
        if not _run_learning(result):
            return _finish(result, started)

        # ====================================================
        # 4. PREDICTIONS (если learning ok или пропущен)
        # ====================================================
        if not _run_predictions(result):
            return _finish(result, started)

        # ====================================================
        # 5. FINAL
        # ====================================================
        _read_final_state(result)

        result["ready"] = (
            result["database"]["ok"]
            and result["historical"]["success"]
            and (result["learning"]["success"] or result["learning"]["skipped"])
            and result["predictions"]["success"]
        )

        if result["ready"]:
            _add_step(
                result,
                "final",
                "success",
                f"✅ FAJ Cycle полностью завершён: результаты={result['final']['match_results']}, прогнозы={result['final']['predictions']}"
            )
        else:
            _add_step(result, "final", "warning", "⚠️ FAJ Cycle завершён с предупреждениями")

        return _finish(result, started)

    except Exception as e:
        msg = f"❌ Критическая ошибка FAJ Cycle: {e}"
        result["errors"].append(msg)
        _add_step(result, "cycle", "error", msg)
        logger.error(traceback.format_exc())
        return _finish(result, started)


def _finish(result: Dict[str, Any], started: datetime) -> Dict[str, Any]:
    finished = datetime.now()
    result["finished_at"] = finished.isoformat()
    result["duration_seconds"] = round((finished - started).total_seconds(), 3)
    result["success"] = result["ready"]

    logger.info("=" * 70)
    logger.info("FAJ CYCLE FINISHED | success=%s | duration=%.3fs", result["success"], result["duration_seconds"])
    logger.info("=" * 70)

    return result


# ============================================================
# CLASS ДЛЯ STREAMLIT
# ============================================================

class FAJCycle:
    VERSION = FAJ_CYCLE_VERSION

    def __init__(self):
        self.version = self.VERSION

    def run(self) -> Dict[str, Any]:
        return run_faj_cycle()

    def run_cycle(self) -> Dict[str, Any]:
        return run_faj_cycle()

    def execute(self) -> Dict[str, Any]:
        return run_faj_cycle()

    def status(self) -> Dict[str, Any]:
        return {"version": self.VERSION, "available": True, "status": "READY"}


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    result = run_faj_cycle()
    print("\n" + "=" * 70)
    print("FAJ CYCLE v12.1")
    print("=" * 70)
    print(f"Успех:       {result['success']}")
    print(f"Готов:       {result['ready']}")
    print(f"Время:       {result['duration_seconds']} сек.")
    print(f"\nИсторические: добавлено={result['historical']['inserted']}, уже было={result['historical']['already_present']}")
    print(f"Обучение:    {'✅' if result['learning']['success'] else '⏭️' if result['learning']['skipped'] else '❌'}")
    print(f"Прогнозы:    {result['predictions']['count']} матчей")
    if result["errors"]:
        print("\nОШИБКИ:")
        for e in result["errors"]:
            print(f"  ❌ {e}")
    print("=" * 70)
