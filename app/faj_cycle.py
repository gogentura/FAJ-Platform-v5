#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ CYCLE — CENTRAL ORCHESTRATOR
============================================================

Новая архитектура:

    FAJ CYCLE
        │
        ├── DATABASE
        │
        ├── MATCH MANAGER
        │      └── календарь / матчи
        │
        ├── RESULT MANAGER
        │      └── фактические результаты
        │
        ├── LEARNING ENGINE
        │      └── обучение только по новым фактам
        │
        ├── PREDICTION MANAGER
        │      └── прогнозы будущих матчей
        │
        └── FINAL STATE

ПРИНЦИПЫ:

    - database.py = единый источник схемы
    - FAJ Cycle = только оркестрация
    - Match Manager = календарь и матчи
    - Result Manager = фактические результаты
    - Learning Engine = обучение
    - Prediction Manager = прогнозирование
    - никаких DELETE
    - никаких DROP
    - исторические результаты не уничтожаются
    - предматчевые прогнозы не перезаписываются
    - идемпотентность обязательна
    - ошибка зависимого этапа останавливает последующие этапы
============================================================
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional


# ============================================================
# IMPORTS
# ============================================================

from app.database import get_connection

from app.match_manager import MatchManager
from app.result_manager import ResultManager

from app.learning_engine import run_learning
from app.core.prediction_manager import get_prediction_manager


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

FAJ_CYCLE_VERSION = "12.1"

LEAGUE = "РПЛ"
SEASON = "2026-2027"

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
            "ok": False,
            "tables": {},
            "missing_tables": [],
        },

        "matches": {
            "started": False,
            "success": False,
            "skipped": False,
            "result": None,
            "count": 0,
            "errors": [],
        },

        "results": {
            "started": False,
            "success": False,
            "skipped": False,
            "result": None,
            "inserted": 0,
            "already_present": 0,
            "updated": 0,
            "count": 0,
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
            "skipped": False,
            "result": None,
            "count": 0,
            "round": None,
            "errors": [],
        },

        "final": {
            "teams": 0,
            "matches": 0,
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
# STEP LOGGER
# ============================================================

def _add_step(
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

    elif status == "skipped":
        logger.info("⏭️ %s", message)

    elif status == "warning":
        logger.warning(message)

    elif status == "running":
        logger.info(message)

    else:
        logger.error(message)


# ============================================================
# 1. DATABASE
# ============================================================

def _check_database(result: Dict[str, Any]) -> bool:

    _add_step(
        result,
        "database",
        "running",
        "🔌 Проверка FAJ Database...",
    )

    conn = None

    try:

        conn = get_connection()

        if conn is None:
            raise RuntimeError(
                "get_connection() вернул None"
            )

        result["database"]["connected"] = True

        cursor = conn.cursor()

        missing = []
        existing = {}

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

            existing[table] = exists

            if not exists:
                missing.append(table)

        result["database"]["tables"] = existing
        result["database"]["missing_tables"] = missing

        if missing:

            message = (
                "❌ В базе отсутствуют необходимые таблицы: "
                + ", ".join(missing)
            )

            result["errors"].append(message)

            _add_step(
                result,
                "database",
                "error",
                message,
            )

            return False

        result["database"]["ok"] = True

        _add_step(
            result,
            "database",
            "success",
            "✅ Database OK — все необходимые таблицы присутствуют",
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка проверки Database: {exc}"
        )

        result["errors"].append(message)

        _add_step(
            result,
            "database",
            "error",
            message,
        )

        logger.exception(
            "Database check failed"
        )

        return False

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# 2. MATCH MANAGER
# ============================================================

def _run_match_manager(
    result: Dict[str, Any]
) -> bool:

    _add_step(
        result,
        "matches",
        "running",
        "📅 Запуск Match Manager...",
    )

    result["matches"]["started"] = True

    try:

        manager = MatchManager()

        # ----------------------------------------------------
        # Основной API Match Manager
        # ----------------------------------------------------

        if hasattr(manager, "sync"):

            match_result = manager.sync(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "sync_matches"):

            match_result = manager.sync_matches(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "load"):

            match_result = manager.load(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "run"):

            match_result = manager.run()

        else:

            raise AttributeError(
                "MatchManager не имеет метода "
                "sync(), sync_matches(), load() или run()"
            )

        result["matches"]["result"] = match_result

        count = _extract_count(
            match_result,
            (
                "count",
                "matches",
                "inserted",
                "created",
                "total",
            ),
        )

        result["matches"]["count"] = count

        success = _extract_success(
            match_result
        )

        if not success:

            message = (
                "❌ Match Manager завершился с ошибкой"
            )

            result["matches"]["errors"].append(
                message
            )

            result["errors"].append(
                message
            )

            _add_step(
                result,
                "matches",
                "error",
                message,
            )

            return False

        result["matches"]["success"] = True

        _add_step(
            result,
            "matches",
            "success",
            f"✅ Match Manager завершён: матчей={count}",
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Match Manager: {exc}"
        )

        result["matches"]["errors"].append(
            message
        )

        result["errors"].append(
            message
        )

        _add_step(
            result,
            "matches",
            "error",
            message,
        )

        logger.exception(
            "Match Manager failed"
        )

        return False


# ============================================================
# 3. RESULT MANAGER
# ============================================================

def _run_result_manager(
    result: Dict[str, Any]
) -> bool:

    _add_step(
        result,
        "results",
        "running",
        "⚽ Запуск Result Manager...",
    )

    result["results"]["started"] = True

    try:

        manager = ResultManager()

        # ----------------------------------------------------
        # Основной API Result Manager
        # ----------------------------------------------------

        if hasattr(manager, "sync"):

            result_data = manager.sync(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "sync_results"):

            result_data = manager.sync_results(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "load"):

            result_data = manager.load(
                league=LEAGUE,
                season=SEASON,
            )

        elif hasattr(manager, "run"):

            result_data = manager.run()

        else:

            raise AttributeError(
                "ResultManager не имеет метода "
                "sync(), sync_results(), load() или run()"
            )

        result["results"]["result"] = result_data

        # ----------------------------------------------------
        # Разбираем результат
        # ----------------------------------------------------

        result["results"]["inserted"] = _extract_count(
            result_data,
            (
                "inserted",
                "inserted_results",
                "created",
                "new_results",
            ),
        )

        result["results"]["already_present"] = _extract_count(
            result_data,
            (
                "already_present",
                "existing",
                "skipped",
                "already_loaded",
            ),
        )

        result["results"]["updated"] = _extract_count(
            result_data,
            (
                "updated",
                "updated_results",
            ),
        )

        result["results"]["count"] = _extract_count(
            result_data,
            (
                "count",
                "results",
                "total",
                "processed",
            ),
        )

        success = _extract_success(
            result_data
        )

        if not success:

            message = (
                "❌ Result Manager завершился с ошибкой"
            )

            result["results"]["errors"].append(
                message
            )

            result["errors"].append(
                message
            )

            _add_step(
                result,
                "results",
                "error",
                message,
            )

            return False

        # ----------------------------------------------------
        # Определяем, были ли новые факты
        # ----------------------------------------------------

        if (
            result["results"]["inserted"] == 0
            and result["results"]["updated"] == 0
        ):

            result["results"]["skipped"] = True

            _add_step(
                result,
                "results",
                "skipped",
                (
                    "⏭️ Новых результатов нет — "
                    "все факты уже находятся в базе"
                ),
            )

        else:

            _add_step(
                result,
                "results",
                "success",
                (
                    "✅ Result Manager завершён: "
                    f"новых={result['results']['inserted']}, "
                    f"обновлено={result['results']['updated']}"
                ),
            )

        result["results"]["success"] = True

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Result Manager: {exc}"
        )

        result["results"]["errors"].append(
            message
        )

        result["errors"].append(
            message
        )

        _add_step(
            result,
            "results",
            "error",
            message,
        )

        logger.exception(
            "Result Manager failed"
        )

        return False


# ============================================================
# 4. LEARNING
# ============================================================

def _run_learning(
    result: Dict[str, Any]
) -> bool:

    new_facts = (
        result["results"]["inserted"]
        + result["results"]["updated"]
    )

    # --------------------------------------------------------
    # Ничего нового → обучение не запускаем
    # --------------------------------------------------------

    if new_facts == 0:

        result["learning"]["skipped"] = True

        _add_step(
            result,
            "learning",
            "skipped",
            (
                "⏭️ Новых фактических результатов нет — "
                "Learning Engine не запускается"
            ),
        )

        return True

    # --------------------------------------------------------
    # Запуск обучения
    # --------------------------------------------------------

    _add_step(
        result,
        "learning",
        "running",
        "🧠 Запуск Learning Engine...",
    )

    result["learning"]["started"] = True

    try:

        learning_result = run_learning()

        result["learning"]["result"] = learning_result

        if isinstance(
            learning_result,
            dict,
        ):

            if learning_result.get(
                "skipped",
                False,
            ):

                result["learning"]["skipped"] = True

                _add_step(
                    result,
                    "learning",
                    "skipped",
                    "⏭️ Learning Engine пропустил обучение",
                )

                return True

            if not learning_result.get(
                "success",
                True,
            ):

                errors = learning_result.get(
                    "errors",
                    [],
                )

                if isinstance(
                    errors,
                    list,
                ):

                    result["learning"]["errors"].extend(
                        errors
                    )

                message = (
                    "❌ Learning Engine завершился с ошибкой"
                )

                result["errors"].append(
                    message
                )

                _add_step(
                    result,
                    "learning",
                    "error",
                    message,
                )

                return False

        result["learning"]["success"] = True

        _add_step(
            result,
            "learning",
            "success",
            (
                "✅ Learning Engine завершён: "
                f"обработано новых фактов={new_facts}"
            ),
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Learning Engine: {exc}"
        )

        result["learning"]["errors"].append(
            message
        )

        result["errors"].append(
            message
        )

        _add_step(
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
# 5. PREDICTIONS
# ============================================================

def _run_predictions(
    result: Dict[str, Any],
    round_id: Optional[int] = None,
) -> bool:

    _add_step(
        result,
        "predictions",
        "running",
        "🔮 Запуск Prediction Manager...",
    )

    result["predictions"]["started"] = True

    try:

        manager = get_prediction_manager()

        # ----------------------------------------------------
        # Если round_id не передан — определяем будущий тур
        # ----------------------------------------------------

        if round_id is None:

            conn = get_connection()

            try:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT MIN(r.id)
                    FROM rounds r
                    JOIN seasons s
                      ON s.id = r.season_id
                    WHERE (
                        s.name = ?
                        OR s.name = ?
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM matches m
                        WHERE m.round_id = r.id
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM match_results mr
                        JOIN matches m2
                          ON m2.id = mr.match_id
                        WHERE m2.round_id = r.id
                    )
                    """,
                    (
                        "РПЛ 2026-2027",
                        SEASON,
                    ),
                )

                row = cursor.fetchone()

                if row and row[0] is not None:
                    round_id = int(row[0])

            finally:

                conn.close()

        # ----------------------------------------------------
        # Нет тура
        # ----------------------------------------------------

        if round_id is None:

            result["predictions"]["skipped"] = True

            _add_step(
                result,
                "predictions",
                "skipped",
                (
                    "⏭️ Подходящий будущий тур "
                    "для прогнозирования не найден"
                ),
            )

            return True

        result["predictions"]["round"] = round_id

        # ----------------------------------------------------
        # Prediction Manager
        # ----------------------------------------------------

        if hasattr(
            manager,
            "predict_round",
        ):

            prediction_result = manager.predict_round(
                round_id
            )

        elif hasattr(
            manager,
            "generate_predictions",
        ):

            prediction_result = manager.generate_predictions(
                round_id
            )

        elif hasattr(
            manager,
            "run",
        ):

            prediction_result = manager.run(
                round_id
            )

        else:

            raise AttributeError(
                "PredictionManager не имеет "
                "predict_round(), "
                "generate_predictions() или run()"
            )

        result["predictions"]["result"] = (
            prediction_result
        )

        # ----------------------------------------------------
        # Обработка ответа
        # ----------------------------------------------------

        count = _extract_count(
            prediction_result,
            (
                "count",
                "predictions",
                "generated",
                "created",
                "total",
            ),
        )

        if isinstance(
            prediction_result,
            (list, tuple),
        ):

            count = len(
                prediction_result
            )

        result["predictions"]["count"] = count

        success = _extract_success(
            prediction_result
        )

        if not success:

            message = (
                "❌ Prediction Manager завершился с ошибкой"
            )

            result["predictions"]["errors"].append(
                message
            )

            result["errors"].append(
                message
            )

            _add_step(
                result,
                "predictions",
                "error",
                message,
            )

            return False

        result["predictions"]["success"] = True

        _add_step(
            result,
            "predictions",
            "success",
            (
                "✅ Prediction Manager завершён: "
                f"создано прогнозов={count}"
            ),
        )

        return True

    except Exception as exc:

        message = (
            f"❌ Ошибка Prediction Manager: {exc}"
        )

        result["predictions"]["errors"].append(
            message
        )

        result["errors"].append(
            message
        )

        _add_step(
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
# 6. FINAL DATABASE STATE
# ============================================================

def _read_final_state(
    result: Dict[str, Any]
) -> None:

    conn = None

    try:

        conn = get_connection()

        cursor = conn.cursor()

        counters = (
            "teams",
            "matches",
            "match_results",
            "predictions",
            "learning_memory",
            "model_parameters",
        )

        for table in counters:

            try:

                cursor.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                )

                row = cursor.fetchone()

                if row:
                    result["final"][table] = int(
                        row[0]
                    )

            except Exception as exc:

                logger.warning(
                    "Unable to count %s: %s",
                    table,
                    exc,
                )

    except Exception as exc:

        logger.warning(
            "Unable to read final database state: %s",
            exc,
        )

    finally:

        if conn is not None:

            try:
                conn.close()
            except Exception:
                pass


# ============================================================
# HELPERS
# ============================================================

def _extract_success(
    value: Any,
) -> bool:

    if value is None:
        return True

    if isinstance(
        value,
        dict,
    ):

        if value.get(
            "status"
        ) == "error":

            return False

        if "success" in value:

            return bool(
                value["success"]
            )

        return True

    return True


def _extract_count(
    value: Any,
    keys: tuple,
) -> int:

    if isinstance(
        value,
        (list, tuple),
    ):

        return len(value)

    if not isinstance(
        value,
        dict,
    ):

        return 0

    for key in keys:

        raw = value.get(key)

        if isinstance(
            raw,
            bool,
        ):
            continue

        if isinstance(
            raw,
            int,
        ):

            return raw

        if isinstance(
            raw,
            (list, tuple),
        ):

            return len(raw)

    return 0


# ============================================================
# FINISH
# ============================================================

def _finish(
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
        "FAJ CYCLE FINISHED | success=%s | duration=%.3fs",
        result["success"],
        result["duration_seconds"],
    )

    logger.info(
        "=" * 70
    )

    return result


# ============================================================
# PUBLIC API
# ============================================================

def run_faj_cycle(
    round_id: Optional[int] = None,
) -> Dict[str, Any]:

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

        # ====================================================
        # 1. DATABASE
        # ====================================================

        if not _check_database(
            result
        ):

            return _finish(
                result,
                started,
            )

        # ====================================================
        # 2. MATCH MANAGER
        # ====================================================

        if not _run_match_manager(
            result
        ):

            return _finish(
                result,
                started,
            )

        # ====================================================
        # 3. RESULT MANAGER
        # ====================================================

        if not _run_result_manager(
            result
        ):

            return _finish(
                result,
                started,
            )

        # ====================================================
        # 4. LEARNING
        # ====================================================

        if not _run_learning(
            result
        ):

            return _finish(
                result,
                started,
            )

        # ====================================================
        # 5. PREDICTIONS
        # ====================================================

        if not _run_predictions(
            result,
            round_id=round_id,
        ):

            return _finish(
                result,
                started,
            )

        # ====================================================
        # 6. FINAL
        # ====================================================

        _read_final_state(
            result
        )

        result["ready"] = (
            result["database"]["ok"]
            and result["matches"]["success"]
            and result["results"]["success"]
            and (
                result["learning"]["success"]
                or result["learning"]["skipped"]
            )
            and (
                result["predictions"]["success"]
                or result["predictions"]["skipped"]
            )
        )

        if result["ready"]:

            _add_step(
                result,
                "final",
                "success",
                (
                    "✅ FAJ CYCLE полностью завершён: "
                    f"матчей={result['final']['matches']}, "
                    f"результатов={result['final']['match_results']}, "
                    f"прогнозов={result['final']['predictions']}"
                ),
            )

        else:

            _add_step(
                result,
                "final",
                "warning",
                "⚠️ FAJ CYCLE завершён с предупреждениями",
            )

        return _finish(
            result,
            started,
        )

    except Exception as exc:

        message = (
            f"❌ Критическая ошибка FAJ CYCLE: {exc}"
        )

        result["errors"].append(
            message
        )

        _add_step(
            result,
            "cycle",
            "error",
            message,
        )

        logger.error(
            traceback.format_exc()
        )

        return _finish(
            result,
            started,
        )


# ============================================================
# CLASS API FOR STREAMLIT
# ============================================================

class FAJCycle:

    VERSION = FAJ_CYCLE_VERSION

    def __init__(self):

        self.version = self.VERSION

    def run(
        self,
        round_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        return run_faj_cycle(
            round_id=round_id
        )

    def run_cycle(
        self,
        round_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        return run_faj_cycle(
            round_id=round_id
        )

    def execute(
        self,
        round_id: Optional[int] = None,
    ) -> Dict[str, Any]:

        return run_faj_cycle(
            round_id=round_id
        )

    def status(
        self,
    ) -> Dict[str, Any]:

        return {
            "version": self.VERSION,
            "available": True,
            "status": "READY",
        }


# ============================================================
# CLI
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

    result = run_faj_cycle()

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
        f"Время:       {result['duration_seconds']} сек."
    )

    print()

    print(
        "Матчи:       "
        f"{result['final']['matches']}"
    )

    print(
        "Результаты:  "
        f"{result['final']['match_results']}"
    )

    print(
        "Прогнозы:    "
        f"{result['final']['predictions']}"
    )

    print(
        "Обучение:    "
        + (
            "✅"
            if result["learning"]["success"]
            else "⏭️"
            if result["learning"]["skipped"]
            else "❌"
        )
    )

    if result["errors"]:

        print()
        print("ОШИБКИ:")

        for error in result["errors"]:

            print(
                f"  ❌ {error}"
            )

    print(
        "=" * 70
    )
