#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/learning_memory.py
============================================================

НАЗНАЧЕНИЕ
-----------

Единый адаптер ETC для работы с таблицей learning_memory.

АРХИТЕКТУРА:

    FACTS
      ↓
    ANALYSIS
      ↓
    ETC
      ↓
    EVOLUTION EVENT
      ↓
    LearningMemory
      ↓
    database.py
      ↓
    SQLite

ВАЖНО
------

Этот модуль НЕ:

    - обучает модель;
    - рассчитывает xG;
    - рассчитывает прогноз;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - изменяет исторические факты;
    - удаляет память;
    - выполняет DELETE;
    - изменяет database.py.

Этот модуль ТОЛЬКО:

    1. принимает уже рассчитанное ETC-событие;
    2. сохраняет его в learning_memory;
    3. читает историю памяти;
    4. предоставляет единый API для ETC.

ПРИНЦИП:

    LearningMemory = APP/ETC → DATABASE → SQLite

Память является APPEND-ONLY.

Существующие записи не удаляются
и не переписываются.

============================================================
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


MODULE_VERSION = "2.0"
MODULE_NAME = "FAJ ETC Learning Memory"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает локальное время создания события.
    """
    return datetime.now().isoformat()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Безопасное преобразование в float.
    """
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


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

    except (TypeError, ValueError):
        return default


def _serialize(
    value: Any,
) -> Optional[str]:
    """
    Безопасное представление значения для TEXT-поля.

    Числа и строки сохраняются как строки.

    dict/list/tuple → JSON.

    None → NULL.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    return str(value)


def _deserialize(
    value: Any,
) -> Any:
    """
    Пытается восстановить JSON-значение.

    Если значение не является JSON,
    возвращается исходная строка.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        return value

    text = value.strip()

    if not text:
        return value

    try:
        return json.loads(text)

    except (TypeError, ValueError, json.JSONDecodeError):
        return value


# ============================================================
# MAIN CLASS
# ============================================================

class LearningMemory:
    """
    Единый слой памяти ETC.

    Никакой бизнес-логики обучения здесь нет.

    ETC рассчитывает изменение.

    LearningMemory только фиксирует его.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # WRITE
    # ========================================================

    def record(
        self,
        event_type: str,
        object_type: str,
        feature: str,
        before_value: Any = None,
        after_value: Any = None,
        delta: Any = None,
        reason: str = "",
        confidence: float = 1.0,
        impact: float = 1.0,
        algorithm: str = "ETC",
        model_version: str = "v12.1",
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Записывает одно эволюционное событие.

        ВАЖНО:

        Метод ничего не изменяет в модели.

        Он только создаёт новую запись памяти.

        Пример:

            memory.record(
                event_type="prediction_error",
                object_type="match:123",
                feature="xg",
                before_value=1.72,
                after_value=0.94,
                delta=-0.78,
                reason="Observed xG ниже прогнозного",
                confidence=0.86,
                impact=0.65,
                algorithm="ETC.StatisticalAnalyzer",
                reference_id=123,
            )
        """

        if not event_type:
            raise ValueError(
                "event_type обязателен"
            )

        if not object_type:
            raise ValueError(
                "object_type обязателен"
            )

        if not feature:
            raise ValueError(
                "feature обязателен"
            )

        confidence = max(
            0.0,
            min(
                1.0,
                _safe_float(
                    confidence,
                    1.0,
                ),
            ),
        )

        impact = _safe_float(
            impact,
            1.0,
        )

        data: Dict[str, Any] = {
            "event_type": str(event_type),
            "object": str(object_type),
            "feature": str(feature),

            "before_value": _serialize(
                before_value
            ),

            "after_value": _serialize(
                after_value
            ),

            "delta": _serialize(
                delta
            ),

            "reason": str(reason or ""),

            "confidence": confidence,

            "impact": impact,

            "algorithm": str(
                algorithm or "ETC"
            ),

            "model_version": str(
                model_version or "v12.1"
            ),

            "reference_id": reference_id,

            "created_at": _now(),
        }

        memory_id = self.db.add_learning_memory(
            data
        )

        if memory_id is None:
            raise RuntimeError(
                "database.py не вернул ID записи learning_memory."
            )

        memory_id = _safe_int(
            memory_id
        )

        logger.info(
            "ETC MEMORY APPEND | "
            "id=%s | "
            "event=%s | "
            "object=%s | "
            "feature=%s",
            memory_id,
            event_type,
            object_type,
            feature,
        )

        return memory_id

    # ========================================================
    # GENERIC EVENT
    # ========================================================

    def record_event(
        self,
        event_type: str,
        object_type: str,
        feature: str,
        *,
        before_value: Any = None,
        after_value: Any = None,
        delta: Any = None,
        reason: str = "",
        confidence: float = 1.0,
        impact: float = 1.0,
        algorithm: str = "ETC",
        model_version: str = "v12.1",
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Явный API для ETC event pipeline.

        Это основной рекомендуемый интерфейс
        для новых ETC-модулей.
        """

        return self.record(
            event_type=event_type,
            object_type=object_type,
            feature=feature,
            before_value=before_value,
            after_value=after_value,
            delta=delta,
            reason=reason,
            confidence=confidence,
            impact=impact,
            algorithm=algorithm,
            model_version=model_version,
            reference_id=reference_id,
        )

    # ========================================================
    # XG CALIBRATION
    # ========================================================

    def record_xg_calibration(
        self,
        team_id: int,
        feature: str,
        before_value: Any,
        after_value: Any,
        delta: Any,
        reason: str,
        confidence: float = 1.0,
        impact: float = 1.0,
        model_version: str = "v12.1",
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует событие xG-калибровки.

        ВАЖНО:

        Само изменение xG здесь НЕ выполняется.

        Здесь только память о решении ETC.
        """

        return self.record(
            event_type="xg_calibration",
            object_type=f"team:{team_id}",
            feature=feature,
            before_value=before_value,
            after_value=after_value,
            delta=delta,
            reason=reason,
            confidence=confidence,
            impact=impact,
            algorithm="ETC.xGCalibration",
            model_version=model_version,
            reference_id=reference_id,
        )

    # ========================================================
    # RATING EVENT
    # ========================================================

    def record_rating_update(
        self,
        team_id: int,
        before_value: Any,
        after_value: Any,
        delta: Any,
        reason: str,
        confidence: float = 1.0,
        impact: float = 1.0,
        model_version: str = "v12.1",
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует событие изменения Club Rating.

        Сам updater находится в другом ETC-модуле.

        LearningMemory только сохраняет историю.
        """

        return self.record(
            event_type="club_rating_update",
            object_type=f"team:{team_id}",
            feature="faj_rating",
            before_value=before_value,
            after_value=after_value,
            delta=delta,
            reason=reason,
            confidence=confidence,
            impact=impact,
            algorithm="ETC.ClubRatingUpdater",
            model_version=model_version,
            reference_id=reference_id,
        )

    # ========================================================
    # PARAMETER EVENT
    # ========================================================

    def record_parameter_update(
        self,
        parameter_name: str,
        before_value: Any,
        after_value: Any,
        delta: Any,
        reason: str,
        confidence: float = 1.0,
        impact: float = 1.0,
        model_version: str = "v12.1",
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует изменение параметра модели.

        Само изменение параметра выполняется
        отдельным ETC-компонентом.
        """

        return self.record(
            event_type="parameter_update",
            object_type="model",
            feature=parameter_name,
            before_value=before_value,
            after_value=after_value,
            delta=delta,
            reason=reason,
            confidence=confidence,
            impact=impact,
            algorithm="ETC.ParameterUpdater",
            model_version=model_version,
            reference_id=reference_id,
        )

    # ========================================================
    # PREDICTION ERROR
    # ========================================================

    def record_prediction_error(
        self,
        match_id: int,
        error_type: str,
        cause_type: str,
        severity: Any,
        reason: str,
        confidence: float = 1.0,
        impact: float = 1.0,
        model_version: str = "v12.1",
    ) -> int:
        """
        Фиксирует ошибку прогноза.

        Это событие анализа.

        Оно НЕ исправляет прогноз
        и НЕ изменяет модель.
        """

        full_reason = (
            f"{cause_type}: {reason}"
            if cause_type
            else reason
        )

        return self.record(
            event_type="prediction_error",
            object_type=f"match:{match_id}",
            feature=error_type,
            before_value=None,
            after_value=severity,
            delta=None,
            reason=full_reason,
            confidence=confidence,
            impact=impact,
            algorithm="ETC.PredictionErrorAnalyzer",
            model_version=model_version,
            reference_id=match_id,
        )

    # ========================================================
    # ANALYSIS EVENT
    # ========================================================

    def record_analysis(
        self,
        object_type: str,
        feature: str,
        observed_value: Any,
        expected_value: Any = None,
        deviation: Any = None,
        reason: str = "",
        confidence: float = 1.0,
        impact: float = 1.0,
        reference_id: Optional[int] = None,
        model_version: str = "v12.1",
    ) -> int:
        """
        Фиксирует аналитическое наблюдение ETC.

        Используется StatisticalAnalyzer,
        prediction diagnostics и другими
        аналитическими компонентами.
        """

        return self.record(
            event_type="analysis",
            object_type=object_type,
            feature=feature,
            before_value=expected_value,
            after_value=observed_value,
            delta=deviation,
            reason=reason,
            confidence=confidence,
            impact=impact,
            algorithm="ETC.Analysis",
            model_version=model_version,
            reference_id=reference_id,
        )

    # ========================================================
    # READ
    # ========================================================

    def get(
        self,
        object_type: Optional[str] = None,
        feature: Optional[str] = None,
        event_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Читает историю ETC.

        Только SELECT.

        Никаких UPDATE / DELETE.
        """

        limit = max(
            1,
            _safe_int(
                limit,
                100,
            ),
        )

        conn = self.db.get_connection()

        try:

            cursor = conn.cursor()

            conditions: List[str] = []
            params: List[Any] = []

            if object_type is not None:

                conditions.append(
                    "object = ?"
                )

                params.append(
                    object_type
                )

            if feature is not None:

                conditions.append(
                    "feature = ?"
                )

                params.append(
                    feature
                )

            if event_type is not None:

                conditions.append(
                    "event_type = ?"
                )

                params.append(
                    event_type
                )

            if reference_id is not None:

                conditions.append(
                    "reference_id = ?"
                )

                params.append(
                    reference_id
                )

            where = ""

            if conditions:

                where = (
                    "WHERE "
                    + " AND ".join(
                        conditions
                    )
                )

            query = f"""
                SELECT
                    id,
                    event_type,
                    object,
                    feature,
                    before_value,
                    after_value,
                    delta,
                    reason,
                    confidence,
                    impact,
                    algorithm,
                    model_version,
                    reference_id,
                    created_at
                FROM learning_memory
                {where}
                ORDER BY
                    datetime(created_at) DESC,
                    id DESC
                LIMIT ?
            """

            params.append(
                limit
            )

            cursor.execute(
                query,
                tuple(params),
            )

            rows = cursor.fetchall()

            result: List[Dict[str, Any]] = []

            for row in rows:

                item = dict(row)

                item["before_value"] = _deserialize(
                    item.get("before_value")
                )

                item["after_value"] = _deserialize(
                    item.get("after_value")
                )

                item["delta"] = _deserialize(
                    item.get("delta")
                )

                result.append(
                    item
                )

            return result

        finally:

            conn.close()

    # ========================================================
    # TEAM MEMORY
    # ========================================================

    def get_team_memory(
        self,
        team_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История ETC конкретной команды.
        """

        return self.get(
            object_type=f"team:{team_id}",
            limit=limit,
        )

    # ========================================================
    # MATCH MEMORY
    # ========================================================

    def get_match_memory(
        self,
        match_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История ETC конкретного матча.
        """

        return self.get(
            object_type=f"match:{match_id}",
            limit=limit,
        )

    # ========================================================
    # PARAMETER MEMORY
    # ========================================================

    def get_parameter_memory(
        self,
        parameter_name: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История изменения конкретного параметра.
        """

        return self.get(
            object_type="model",
            feature=parameter_name,
            limit=limit,
        )

    # ========================================================
    # XG MEMORY
    # ========================================================

    def get_xg_memory_history(
        self,
        team_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История xG-событий команды.
        """

        return self.get(
            object_type=f"team:{team_id}",
            event_type="xg_calibration",
            limit=limit,
        )

    # ========================================================
    # PREDICTION ERRORS
    # ========================================================

    def get_prediction_errors(
        self,
        match_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает ошибки прогнозов.
        """

        return self.get(
            object_type=(
                f"match:{match_id}"
                if match_id is not None
                else None
            ),
            event_type="prediction_error",
            limit=limit,
        )

    # ========================================================
    # LATEST
    # ========================================================

    def get_latest(
        self,
        object_type: str,
        feature: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Последнее событие для объекта.
        """

        rows = self.get(
            object_type=object_type,
            feature=feature,
            event_type=event_type,
            limit=1,
        )

        return rows[0] if rows else None


# ============================================================
# MODULE LEVEL API
# ============================================================

def save_learning_memory(
    db: FAJDatabase,
    event_type: str,
    object_type: str,
    feature: str,
    before_value: Any = None,
    after_value: Any = None,
    delta: Any = None,
    reason: str = "",
    confidence: float = 1.0,
    impact: float = 1.0,
    algorithm: str = "ETC",
    model_version: str = "v12.1",
    reference_id: Optional[int] = None,
) -> int:
    """
    Единая функция записи памяти ETC.
    """

    memory = LearningMemory(
        db=db
    )

    return memory.record(
        event_type=event_type,
        object_type=object_type,
        feature=feature,
        before_value=before_value,
        after_value=after_value,
        delta=delta,
        reason=reason,
        confidence=confidence,
        impact=impact,
        algorithm=algorithm,
        model_version=model_version,
        reference_id=reference_id,
    )


def get_learning_memory(
    db: FAJDatabase,
    object_type: Optional[str] = None,
    feature: Optional[str] = None,
    event_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Единая функция чтения памяти ETC.
    """

    memory = LearningMemory(
        db=db
    )

    return memory.get(
        object_type=object_type,
        feature=feature,
        event_type=event_type,
        reference_id=reference_id,
        limit=limit,
    )


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
    print("FAJ ETC — LEARNING MEMORY")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)
    print()
    print("Режим: APPEND-ONLY")
    print("Обучение: НЕТ")
    print("Изменение модели: НЕТ")
    print("Изменение фактов: НЕТ")
    print("DELETE: НЕТ")
    print()
    print(
        "Модуль предназначен для работы "
        "через FAJDatabase."
    )
    print("=" * 70)
