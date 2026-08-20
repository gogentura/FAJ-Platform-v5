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
Единый слой работы ETC с таблицей learning_memory.

МОДУЛЬ НЕ:
    - обучает модель;
    - рассчитывает xG;
    - изменяет FAJ Rating;
    - изменяет database.py;
    - удаляет старую память.

МОДУЛЬ:
    - сохраняет события эволюции модели;
    - фиксирует before / after / delta;
    - хранит причину изменения;
    - хранит confidence и impact;
    - позволяет читать историю ETC;
    - обеспечивает единый формат памяти.

ПРИНЦИП:
    APP/ETC → LearningMemory → database.py → SQLite

learning_memory является append-only памятью:
старые записи НЕ удаляются и НЕ переписываются.
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
MODULE_NAME = "ETC Learning Memory"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _serialize(value: Any) -> Optional[str]:
    """
    Приводит значение к безопасному строковому представлению
    для TEXT-полей learning_memory.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, (dict, list, tuple)):
        import json

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    return str(value)


# ============================================================
# MAIN CLASS
# ============================================================

class LearningMemory:
    """
    ETC Learning Memory.

    Отвечает только за память эволюции модели.
    """

    def __init__(self, db: Optional[FAJDatabase] = None) -> None:
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
        Создаёт одну запись в learning_memory.

        Пример:

            memory.record(
                event_type="xg_calibration",
                object_type="team",
                feature="attack_xg_deviation",
                before_value=0.12,
                after_value=0.08,
                delta=-0.04,
                reason="Observed xG систематически ниже Predictive xG",
                confidence=0.82,
                impact=0.60,
                reference_id=123,
            )
        """

        if not event_type:
            raise ValueError("event_type обязателен")

        if not object_type:
            raise ValueError("object_type обязателен")

        if not feature:
            raise ValueError("feature обязателен")

        confidence = max(0.0, min(1.0, _safe_float(confidence, 1.0)))
        impact = _safe_float(impact, 1.0)

        data: Dict[str, Any] = {
            "event_type": event_type,
            "object": object_type,
            "feature": feature,
            "before_value": _serialize(before_value),
            "after_value": _serialize(after_value),
            "delta": _serialize(delta),
            "reason": reason,
            "confidence": confidence,
            "impact": impact,
            "algorithm": algorithm,
            "model_version": model_version,
            "reference_id": reference_id,
            "created_at": _now(),
        }

        memory_id = self.db.add_learning_memory(data)

        logger.info(
            "ETC learning memory saved: id=%s type=%s object=%s feature=%s",
            memory_id,
            event_type,
            object_type,
            feature,
        )

        return int(memory_id)

    # ========================================================
    # CONVENIENCE METHODS
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
        Записывает изменение xG-калибровки команды.
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
        Записывает изменение FAJ Club Rating.
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
        Записывает изменение параметра модели.
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
        Записывает обнаруженную ошибку прогноза.

        Важно:
        это память о событии.
        Само подробное описание ошибки должно храниться
        в learning_records / learning_events.
        """

        return self.record(
            event_type="prediction_error",
            object_type=f"match:{match_id}",
            feature=error_type,
            before_value=None,
            after_value=severity,
            delta=None,
            reason=(
                f"{cause_type}: {reason}"
                if cause_type
                else reason
            ),
            confidence=confidence,
            impact=impact,
            algorithm="ETC.PredictionErrorAnalyzer",
            model_version=model_version,
            reference_id=match_id,
        )

    # ========================================================
    # READ
    # ========================================================

    def get(
        self,
        object_type: Optional[str] = None,
        feature: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Читает историю learning_memory.

        Фильтры можно комбинировать.
        """

        limit = max(1, int(limit))

        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()

            conditions = []
            params: List[Any] = []

            if object_type is not None:
                conditions.append("object = ?")
                params.append(object_type)

            if feature is not None:
                conditions.append("feature = ?")
                params.append(feature)

            if event_type is not None:
                conditions.append("event_type = ?")
                params.append(event_type)

            where = ""

            if conditions:
                where = "WHERE " + " AND ".join(conditions)

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
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
            """

            params.append(limit)

            cursor.execute(query, tuple(params))

            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    # ========================================================
    # SPECIALIZED READS
    # ========================================================

    def get_team_memory(
        self,
        team_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История эволюции конкретной команды.
        """

        return self.get(
            object_type=f"team:{team_id}",
            limit=limit,
        )

    def get_match_memory(
        self,
        match_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История событий конкретного матча.
        """

        return self.get(
            object_type=f"match:{match_id}",
            limit=limit,
        )

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

    def get_xg_memory_history(
        self,
        team_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История xG-калибровки команды.
        """

        return self.get(
            object_type=f"team:{team_id}",
            event_type="xg_calibration",
            limit=limit,
        )

    # ========================================================
    # LATEST
    # ========================================================

    def get_latest(
        self,
        object_type: str,
        feature: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Возвращает последнюю запись памяти.
        """

        rows = self.get(
            object_type=object_type,
            feature=feature,
            limit=1,
        )

        return rows[0] if rows else None


# ============================================================
# MODULE-LEVEL HELPERS
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
    Удобная функция для ETC-модулей.
    """

    memory = LearningMemory(db)

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
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Удобная функция чтения памяти ETC.
    """

    memory = LearningMemory(db)

    return memory.get(
        object_type=object_type,
        feature=feature,
        event_type=event_type,
        limit=limit,
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
    print("FAJ ETC — Learning Memory")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)
    print("Модуль предназначен для работы через FAJDatabase.")
    print("Запись и чтение памяти выполняются без DELETE/перезаписи.")
    print("=" * 70)
