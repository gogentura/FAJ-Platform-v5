#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
FAJ CYCLE
===========================================================

НАЗНАЧЕНИЕ
    Центральный оркестратор рабочего цикла FAJ.

ЦЕПОЧКА

    завершённые факты
            ↓
    Learning Engine
            ↓
    обновлённые параметры
            ↓
    Prediction Manager
            ↓
    прогноз следующего тура

ВАЖНО

    Этот модуль НЕ является:
        - моделью прогнозирования;
        - XG Engine;
        - Poisson Engine;
        - Learning Engine;
        - загрузчиком данных.

    Он только связывает существующие компоненты.

ПРИНЦИПЫ

    - SQLite only;
    - не удаляет данные;
    - не делает DELETE;
    - не делает DROP;
    - не изменяет календарь;
    - обучение пакетное;
    - прогноз создаётся только после обучения;
    - исторические факты не изменяются;
    - существующие прогнозы не удаляются;
    - ошибки останавливают цикл;
    - каждый этап возвращает диагностический результат.

РАБОЧИЙ ЦИКЛ

    1. Проверить БД.
    2. Запустить Learning Engine.
    3. Если обучение успешно — запустить Prediction Manager.
    4. Вернуть единый результат цикла.

===========================================================
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONFIG
# ============================================================

CYCLE_VERSION = "12.1"
CYCLE_NAME = "FAJ Cycle"

DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "faj.db"
)


# ============================================================
# UTILS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _base_result() -> Dict[str, Any]:
    return {
        "success": False,
        "cycle": CYCLE_NAME,
        "version": CYCLE_VERSION,
        "started_at": _now(),
        "finished_at": None,

        "database": {
            "ok": False,
            "path": None,
        },

        "learning": {
            "started": False,
            "success": False,
            "result": None,
        },

        "prediction": {
            "started": False,
            "success": False,
            "result": None,
        },

        "errors": [],
    }


# ============================================================
# DATABASE CHECK
# ============================================================

def _check_database(
    db_path: Path,
) -> Dict[str, Any]:

    result = {
        "ok": False,
        "path": str(db_path),
    }

    if not db_path.exists():
        result["error"] = (
            f"База данных не найдена: {db_path}"
        )
        return result

    try:
        conn = sqlite3.connect(
            str(db_path)
        )

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        tables = {
            row[0]
            for row in cursor.fetchall()
        }

        required = {
            "teams",
            "rounds",
            "matches",
            "match_results",
        }

        missing = sorted(
            required - tables
        )

        if missing:
            result["error"] = (
                "В БД отсутствуют обязательные таблицы: "
                + ", ".join(missing)
            )
            result["tables"] = sorted(tables)
            conn.close()
            return result

        result["ok"] = True
        result["tables"] = sorted(tables)

        conn.close()

        return result

    except Exception as exc:

        result["error"] = str(exc)

        try:
            conn.close()
        except Exception:
            pass

        return result


# ============================================================
# LEARNING
# ============================================================

def _run_learning(
    db_path: Path,
    force: bool = False,
) -> Dict[str, Any]:

    """
    Запускает уже существующий Learning Engine.

    Никакой собственной логики обучения здесь нет.
    """

    try:

        from app.learning_engine import (
            run_learning,
        )

    except Exception as exc:

        return {
            "success": False,
            "errors": [
                "Не удалось импортировать "
                "app.learning_engine: "
                f"{exc}"
            ],
        }

    try:

        return run_learning(
            db_path=str(db_path),
            force=force,
        )

    except Exception as exc:

        logger.exception(
            "Learning Engine failed"
        )

        return {
            "success": False,
            "errors": [str(exc)],
        }


# ============================================================
# PREDICTION MANAGER
# ============================================================

def _run_prediction(
    db_path: Path,
    round_number: Optional[int] = None,
) -> Dict[str, Any]:

    """
    Запускает существующий Prediction Manager.

    Этот модуль не реализует математическую модель.
    """

    try:

        from app.prediction_manager import (
            PredictionManager,
        )

    except Exception as exc:

        return {
            "success": False,
            "errors": [
                "Не удалось импортировать "
                "app.prediction_manager: "
                f"{exc}"
            ],
        }

    try:

        manager = PredictionManager(
            db_path=str(db_path)
        )

    except TypeError:

        try:

            manager = PredictionManager()

        except Exception as exc:

            return {
                "success": False,
                "errors": [
                    f"Не удалось создать "
                    f"PredictionManager: {exc}"
                ],
            }

    except Exception as exc:

        return {
            "success": False,
            "errors": [
                f"Не удалось создать "
                f"PredictionManager: {exc}"
            ],
        }

    # --------------------------------------------------------
    # Возможные публичные API существующего менеджера.
    #
    # Мы НЕ создаём новый Prediction Engine.
    # Используем уже существующий метод.
    # --------------------------------------------------------

    candidates = []

    if round_number is not None:

        candidates.extend([
            (
                "generate_predictions",
                {
                    "round_number": round_number,
                },
            ),
            (
                "calculate_predictions",
                {
                    "round_number": round_number,
                },
            ),
            (
                "predict_round",
                {
                    "round_number": round_number,
                },
            ),
            (
                "run",
                {
                    "round_number": round_number,
                },
            ),
        ])

    candidates.extend([
        (
            "generate_predictions",
            {},
        ),
        (
            "calculate_predictions",
            {},
        ),
        (
            "predict",
            {},
        ),
        (
            "run",
            {},
        ),
    ])

    errors = []

    for method_name, kwargs in candidates:

        method = getattr(
            manager,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = method(
                **kwargs
            )

            if isinstance(
                result,
                dict,
            ):
                return result

            return {
                "success": True,
                "result": result,
                "method": method_name,
            }

        except TypeError as exc:

            # Метод существует, но его сигнатура
            # не совпала с переданными аргументами.
            errors.append(
                f"{method_name}: {exc}"
            )

            # Если метод был вызван с аргументом
            # round_number, пробуем без него.
            if kwargs:

                try:

                    result = method()

                    if isinstance(
                        result,
                        dict,
                    ):
                        return result

                    return {
                        "success": True,
                        "result": result,
                        "method": method_name,
                    }

                except Exception as retry_exc:

                    errors.append(
                        f"{method_name} retry: "
                        f"{retry_exc}"
                    )

        except Exception as exc:

            logger.exception(
                "Prediction method failed: %s",
                method_name,
            )

            return {
                "success": False,
                "method": method_name,
                "errors": [str(exc)],
            }

    return {
        "success": False,
        "errors": [
            "PredictionManager не содержит "
            "поддерживаемого публичного метода "
            "для расчёта прогнозов.",
            *errors,
        ],
    }


# ============================================================
# PUBLIC CYCLE
# ============================================================

def run_faj_cycle(
    db_path: Optional[str] = None,
    round_number: Optional[int] = None,
    force_learning: bool = False,
) -> Dict[str, Any]:

    """
    Полный рабочий цикл FAJ.

    Порядок строго фиксирован:

        DB check
            ↓
        Learning
            ↓
        Prediction

    Если Learning Engine завершился ошибкой,
    Prediction Manager НЕ запускается.
    """

    result = _base_result()

    path = (
        Path(db_path)
        if db_path
        else DEFAULT_DB_PATH
    )

    result["database"]["path"] = str(path)

    # ========================================================
    # 1. DATABASE
    # ========================================================

    database = _check_database(
        path
    )

    result["database"] = database

    if not database["ok"]:

        result["errors"].append(
            database.get(
                "error",
                "Ошибка базы данных.",
            )
        )

        result["finished_at"] = _now()

        return result

    # ========================================================
    # 2. LEARNING
    # ========================================================

    result["learning"]["started"] = True

    learning_result = _run_learning(
        db_path=path,
        force=force_learning,
    )

    result["learning"]["result"] = (
        learning_result
    )

    result["learning"]["success"] = bool(
        learning_result.get(
            "success",
            False,
        )
    )

    if not result["learning"]["success"]:

        result["errors"].extend(
            learning_result.get(
                "errors",
                [
                    "Learning Engine "
                    "завершился неуспешно."
                ],
            )
        )

        result["finished_at"] = _now()

        return result

    # ========================================================
    # 3. PREDICTION
    # ========================================================

    result["prediction"]["started"] = True

    prediction_result = _run_prediction(
        db_path=path,
        round_number=round_number,
    )

    result["prediction"]["result"] = (
        prediction_result
    )

    result["prediction"]["success"] = bool(
        prediction_result.get(
            "success",
            False,
        )
    )

    if not result["prediction"]["success"]:

        result["errors"].extend(
            prediction_result.get(
                "errors",
                [
                    "Prediction Manager "
                    "завершился неуспешно."
                ],
            )
        )

        result["finished_at"] = _now()

        return result

    # ========================================================
    # SUCCESS
    # ========================================================

    result["success"] = True
    result["finished_at"] = _now()

    logger.info(
        "FAJ cycle completed successfully."
    )

    return result


# ============================================================
# CONVENIENCE API
# ============================================================

def run_cycle(
    db_path: Optional[str] = None,
    round_number: Optional[int] = None,
    force_learning: bool = False,
) -> Dict[str, Any]:

    return run_faj_cycle(
        db_path=db_path,
        round_number=round_number,
        force_learning=force_learning,
    )


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

    print()
    print("=" * 70)
    print("FAJ CYCLE v12.1")
    print("=" * 70)

    result = run_faj_cycle()

    print()
    print(
        f"Цикл: "
        f"{'OK' if result['success'] else 'ERROR'}"
    )

    print(
        f"БД: "
        f"{'OK' if result['database']['ok'] else 'ERROR'}"
    )

    print(
        f"Обучение: "
        f"{'OK' if result['learning']['success'] else 'ERROR'}"
    )

    print(
        f"Прогноз: "
        f"{'OK' if result['prediction']['success'] else 'ERROR'}"
    )

    if result["errors"]:

        print()
        print("ОШИБКИ:")

        for error in result["errors"]:
            print(
                f"  ❌ {error}"
            )

    print("=" * 70)
