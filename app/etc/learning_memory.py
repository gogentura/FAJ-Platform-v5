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
    ETC LEARNING ENGINE
      ↓
    EVOLUTION EVENT
      ↓
    LearningMemory
      ↓
    FAJDatabase.add_learning_memory()
      ↓
    SQLite / learning_memory


ОТВЕТСТВЕННОСТЬ
---------------

LearningMemory отвечает только за:

    1. валидацию ETC-события;
    2. сериализацию значений;
    3. передачу события в FAJDatabase;
    4. чтение истории learning_memory;
    5. специализированные ETC API.


ВАЖНО
------

Этот модуль НЕ:

    - обучает модель;
    - рассчитывает xG;
    - рассчитывает прогноз;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - изменяет исторические факты;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - выполняет DELETE;
    - выполняет UPDATE;
    - изменяет database.py;
    - самостоятельно принимает решения об эволюции модели.


APPEND-ONLY
-----------

Каждое ETC-событие является новой записью.

Существующие записи:

    НЕ изменяются;
    НЕ удаляются;
    НЕ переписываются.


DATABASE CONTRACT
-----------------

database.py v12.1 является единственным источником
схемы базы данных.

Запись выполняется ТОЛЬКО через:

    FAJDatabase.add_learning_memory(data)

Чтение выполняется ТОЛЬКО через:

    FAJDatabase.get_learning_memory()
    FAJDatabase.get_learning_memory_count()

LearningMemory не содержит INSERT SQL.
LearningMemory не содержит SELECT SQL.


PAGINATION CONTRACT (НОВОЕ v3.1)
--------------------------------

LearningMemory.get() поддерживает:
    limit
    offset

Но offset является API адаптера LearningMemory.

Он НЕ передаётся напрямую в database.py.

Это важно, потому что database.py остаётся единственным
владельцем SQL и не обязан поддерживать offset.

Пагинация выполняется поверх существующего
FAJDatabase.get_learning_memory().

    database.get_learning_memory(limit=offset + limit)
    rows[offset:offset + limit]


BATCH LEARNING CONTRACT
-----------------------

После успешной обработки конкретного матча
ETCLearningEngine должен создать событие:

    event_type = "batch_learning"
    object = "match:<match_id>"
    reference_id = <match_id>

Именно это событие используется BatchController
для определения уже обработанного матча.

Canonical identity processed-state:
    event_type + reference_id

Поле object НЕ используется BatchController
для определения processed-state.


PRINCIPLE
---------

    FACTS
      ↓
    ANALYSIS
      ↓
    ETC DECISION
      ↓
    LEARNING MEMORY
      ↓
    APPEND-ONLY HISTORY


============================================================
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


MODULE_VERSION = "3.1"
MODULE_NAME = "FAJ ETC Learning Memory"

DEFAULT_MODEL_VERSION = "v12.1"
DEFAULT_ALGORITHM = "ETC"

BATCH_LEARNING_EVENT = "batch_learning"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает локальное время создания события
    в ISO формате.
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
    Безопасное представление значения
    для TEXT-поля learning_memory.

    Правила:

        None
            → NULL

        bool
            → "1" / "0"

        dict/list/tuple
            → JSON

        остальные значения
            → строка
    """

    if value is None:

        return None

    if isinstance(value, bool):

        return "1" if value else "0"

    if isinstance(
        value,
        (
            dict,
            list,
            tuple,
        ),
    ):

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    return str(value)


def _deserialize(
    value: Any,
) -> Any:
    """
    Десериализация значения.

    ВАЖНО:
    Исторические значения bool сохраняются как:
        "1"
        "0"
    и восстанавливаются обратно:
        True
        False

    JSON-объекты и массивы также восстанавливаются.
    Обычные строки остаются строками.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        return value

    text = value.strip()

    if not text:
        return value

    # --------------------------------------------------------
    # BOOL
    # --------------------------------------------------------
    if text == "1":
        return True
    if text == "0":
        return False

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------
    try:
        decoded = json.loads(text)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return value

    return decoded


def _normalize_confidence(
    value: Any,
) -> float:
    """
    Нормализует confidence в диапазон 0..1.
    """

    confidence = _safe_float(
        value,
        1.0,
    )

    return max(
        0.0,
        min(
            1.0,
            confidence,
        ),
    )


# ============================================================
# MAIN CLASS
# ============================================================

class LearningMemory:
    """
    Единый слой памяти ETC.

    LearningMemory НЕ содержит бизнес-логику обучения.

    ETC рассчитывает событие.

    LearningMemory только фиксирует его
    через FAJDatabase.add_learning_memory().

    Чтение выполняется через FAJDatabase.get_learning_memory()
    и FAJDatabase.get_learning_memory_count().

    ПОДДЕРЖИВАЕТ ПАГИНАЦИЮ (НОВОЕ v3.1):
        get(limit=..., offset=...)

    offset НЕ передаётся в database.py.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # WRITE — GENERIC
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
        algorithm: str = DEFAULT_ALGORITHM,
        model_version: str = DEFAULT_MODEL_VERSION,
        reference_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """
        Записывает одно эволюционное событие.

        Только APPEND.

        Реальная запись выполняется database.py:

            FAJDatabase.add_learning_memory()
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

        normalized_reference_id = None

        if reference_id is not None:

            normalized_reference_id = _safe_int(
                reference_id
            )

            if normalized_reference_id <= 0:

                raise ValueError(
                    "reference_id должен быть "
                    "положительным integer"
                )

        confidence = _normalize_confidence(
            confidence
        )

        impact = _safe_float(
            impact,
            1.0,
        )

        data: Dict[str, Any] = {

            "event_type": str(
                event_type
            ),

            "object": str(
                object_type
            ),

            "feature": str(
                feature
            ),

            "before_value": _serialize(
                before_value
            ),

            "after_value": _serialize(
                after_value
            ),

            "delta": _serialize(
                delta
            ),

            "reason": str(
                reason or ""
            ),

            "confidence": confidence,

            "impact": impact,

            "algorithm": str(
                algorithm or DEFAULT_ALGORITHM
            ),

            "model_version": str(
                model_version or DEFAULT_MODEL_VERSION
            ),

            "reference_id":
                normalized_reference_id,

            "created_at":
                str(
                    created_at
                    or _now()
                ),
        }

        # ----------------------------------------------------
        # DATABASE CONTRACT
        # ----------------------------------------------------
        #
        # Никакого SQL здесь нет.
        #
        # database.py является единственным
        # владельцем схемы и операции INSERT.
        #

        memory_id = (
            self.db.add_learning_memory(
                data
            )
        )

        if memory_id is None:

            raise RuntimeError(
                "database.py не вернул ID "
                "записи learning_memory."
            )

        memory_id = _safe_int(
            memory_id
        )

        if memory_id <= 0:

            raise RuntimeError(
                "database.py вернул некорректный "
                "ID записи learning_memory."
            )

        logger.info(
            "ETC MEMORY APPEND | "
            "id=%s | "
            "event=%s | "
            "object=%s | "
            "feature=%s | "
            "reference_id=%s",
            memory_id,
            event_type,
            object_type,
            feature,
            normalized_reference_id,
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
        algorithm: str = DEFAULT_ALGORITHM,
        model_version: str = DEFAULT_MODEL_VERSION,
        reference_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """
        Явный универсальный API ETC events.

        Рекомендуемый интерфейс для новых ETC-модулей.
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
            created_at=created_at,
        )

    # ========================================================
    # BATCH LEARNING EVENT
    # ========================================================

    def record_batch_learning(
        self,
        match_id: int,
        *,
        feature: str = "etc_batch_processed",
        before_value: Any = None,
        after_value: Any = "processed",
        delta: Any = None,
        reason: str = "Матч успешно обработан ETC Learning Engine",
        confidence: float = 1.0,
        impact: float = 1.0,
        algorithm: str = "ETC.LearningEngine",
        model_version: str = DEFAULT_MODEL_VERSION,
        created_at: Optional[str] = None,
    ) -> int:
        """
        Фиксирует успешную обработку конкретного матча
        ETC Learning Engine.

        КРИТИЧЕСКИЙ КОНТРАК:

            event_type
                = "batch_learning"

            object
                = "match:<match_id>"

            reference_id
                = match_id

        Именно этот event читается BatchController
        для определения уже обработанного матча.

        ВАЖНО:

        Метод НЕ выполняет обучение.

        Он только фиксирует факт того,
        что ETC Learning Engine успешно завершил
        обработку данного матча.
        """

        normalized_match_id = _safe_int(
            match_id
        )

        if normalized_match_id <= 0:

            raise ValueError(
                "match_id должен быть "
                "положительным integer"
            )

        # ----------------------------------------------------
        # IDEMPOTENCY
        # ----------------------------------------------------
        #
        # Проверяем, не существует ли уже marker
        # для этого match_id.
        #
        # Используем count для быстрой проверки.
        #

        existing_count = self.db.get_learning_memory_count(
            event_type=BATCH_LEARNING_EVENT,
            reference_id=normalized_match_id,
        )

        if existing_count > 0:

            # Получаем существующий ID
            existing_rows = self.db.get_learning_memory(
                event_type=BATCH_LEARNING_EVENT,
                reference_id=normalized_match_id,
                limit=1,
            )

            if existing_rows:

                row = existing_rows[0]
                existing_id = row.get("id")

                if existing_id is not None:

                    logger.debug(
                        "BATCH_LEARNING marker already exists | "
                        "match_id=%s | "
                        "existing_id=%s",
                        normalized_match_id,
                        existing_id,
                    )

                    return _safe_int(
                        existing_id
                    )

        # ----------------------------------------------------
        # APPEND
        # ----------------------------------------------------

        return self.record(
            event_type=BATCH_LEARNING_EVENT,

            object_type=(
                f"match:{normalized_match_id}"
            ),

            feature=feature,

            before_value=before_value,

            after_value=after_value,

            delta=delta,

            reason=reason,

            confidence=confidence,

            impact=impact,

            algorithm=algorithm,

            model_version=model_version,

            reference_id=(
                normalized_match_id
            ),

            created_at=created_at,
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
        model_version: str = DEFAULT_MODEL_VERSION,
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует событие xG-калибровки.

        Само изменение xG здесь НЕ выполняется.

        Здесь только память о решении ETC.
        """

        normalized_team_id = _safe_int(
            team_id
        )

        if normalized_team_id <= 0:

            raise ValueError(
                "team_id должен быть "
                "положительным integer"
            )

        return self.record(
            event_type="xg_calibration",

            object_type=(
                f"team:{normalized_team_id}"
            ),

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
        model_version: str = DEFAULT_MODEL_VERSION,
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует событие изменения Club Rating.

        Сам updater находится в другом ETC-модуле.

        LearningMemory только сохраняет историю.
        """

        normalized_team_id = _safe_int(
            team_id
        )

        if normalized_team_id <= 0:

            raise ValueError(
                "team_id должен быть "
                "положительным integer"
            )

        return self.record(
            event_type="club_rating_update",

            object_type=(
                f"team:{normalized_team_id}"
            ),

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
        model_version: str = DEFAULT_MODEL_VERSION,
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Фиксирует изменение параметра модели.

        Само изменение параметра выполняется
        отдельным ETC-компонентом.
        """

        if not parameter_name:

            raise ValueError(
                "parameter_name обязателен"
            )

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
        model_version: str = DEFAULT_MODEL_VERSION,
    ) -> int:
        """
        Фиксирует ошибку прогноза.

        Это событие анализа.

        Оно НЕ исправляет прогноз
        и НЕ изменяет модель.
        """

        normalized_match_id = _safe_int(
            match_id
        )

        if normalized_match_id <= 0:

            raise ValueError(
                "match_id должен быть "
                "положительным integer"
            )

        if not error_type:

            raise ValueError(
                "error_type обязателен"
            )

        full_reason = (
            f"{cause_type}: {reason}"
            if cause_type
            else reason
        )

        return self.record(
            event_type="prediction_error",

            object_type=(
                f"match:{normalized_match_id}"
            ),

            feature=error_type,

            before_value=None,

            after_value=severity,

            delta=None,

            reason=full_reason,

            confidence=confidence,

            impact=impact,

            algorithm="ETC.PredictionErrorAnalyzer",

            model_version=model_version,

            reference_id=(
                normalized_match_id
            ),
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
        model_version: str = DEFAULT_MODEL_VERSION,
    ) -> int:
        """
        Фиксирует аналитическое наблюдение ETC.

        Используется StatisticalAnalyzer,
        prediction diagnostics и другими
        аналитическими компонентами.

        ВАЖНО:

        Это ещё НЕ означает изменение модели.
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
    # READ (С ПАГИНАЦИЕЙ — НОВОЕ v3.1)
    # ========================================================

    def get(
        self,
        object_type: Optional[str] = None,
        feature: Optional[str] = None,
        event_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Читает историю ETC.

        Поддерживает:
            limit
            offset

        ВАЖНО (НОВОЕ v3.1):
        offset является частью API LearningMemory.

        Он НЕ передаётся в database.py.

        Поэтому существующий database.py v12.1
        менять не требуется.

        Реализация:
            database.get_learning_memory(limit=offset + limit)
        затем:
            rows[offset:offset + limit]

        Это сохраняет database.py единственным
        владельцем SQL.

        При ошибке database.py исключение
        НЕ скрывается.
        """

        safe_limit = _safe_int(
            limit,
            100,
        )

        safe_offset = _safe_int(
            offset,
            0,
        )

        if safe_limit <= 0:
            return []

        if safe_offset < 0:
            raise ValueError(
                "offset не может быть отрицательным"
            )

        # ----------------------------------------------------
        # Защита от потенциально бессмысленного offset.
        # ----------------------------------------------------

        fetch_limit = (
            safe_offset + safe_limit
        )

        if fetch_limit <= 0:
            return []

        # ----------------------------------------------------
        # DATABASE CONTRACT
        # ----------------------------------------------------
        #
        # В database.py передаём только те аргументы,
        # которые являются частью его существующего
        # контракта.
        #
        # offset НЕ передаётся.
        #

        rows = self.db.get_learning_memory(
            event_type=event_type,
            object_type=object_type,
            feature=feature,
            reference_id=reference_id,
            limit=fetch_limit,
        )

        if rows is None:
            rows = []

        # ----------------------------------------------------
        # ADAPTER PAGINATION
        # ----------------------------------------------------

        page = list(
            rows[
                safe_offset:
                safe_offset + safe_limit
            ]
        )

        result: List[
            Dict[str, Any]
        ] = []

        for row in page:

            if not isinstance(
                row,
                dict,
            ):
                continue

            item = dict(
                row
            )

            item[
                "before_value"
            ] = _deserialize(
                item.get(
                    "before_value"
                )
            )

            item[
                "after_value"
            ] = _deserialize(
                item.get(
                    "after_value"
                )
            )

            item[
                "delta"
            ] = _deserialize(
                item.get(
                    "delta"
                )
            )

            result.append(
                item
            )

        return result

    # ========================================================
    # COUNT (ДЕЛЕГИРОВАНИЕ В DATABASE.PY)
    # ========================================================

    def count(
        self,
        event_type: Optional[str] = None,
        reference_id: Optional[int] = None,
    ) -> int:
        """
        Быстрый подсчёт записей в learning_memory.

        Используется для processed-state / idempotency.

        ВСЯ ЛОГИКА ПОДСЧЁТА ДЕЛЕГИРОВАНА В DATABASE.PY:

            FAJDatabase.get_learning_memory_count()

        SQL принадлежит database.py.
        """

        return self.db.get_learning_memory_count(
            event_type=event_type,
            reference_id=reference_id,
        )

    # ========================================================
    # BATCH MEMORY
    # ========================================================

    def get_batch_learning_memory(
        self,
        match_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает события batch_learning.

        Если match_id указан,
        возвращается память конкретного матча.

        Только SELECT.
        """

        normalized_match_id = None

        if match_id is not None:

            normalized_match_id = _safe_int(
                match_id
            )

            if normalized_match_id <= 0:
                return []

        return self.get(
            object_type=(
                f"match:{normalized_match_id}"
                if normalized_match_id is not None
                else None
            ),
            event_type=BATCH_LEARNING_EVENT,
            limit=limit,
            offset=offset,
        )

    # ========================================================
    # IS PROCESSED
    # ========================================================

    def is_match_processed(
        self,
        match_id: int,
    ) -> bool:
        """
        Быстрая проверка, обработан ли матч ETC.

        Использует count для производительности.
        """

        normalized_match_id = _safe_int(
            match_id
        )

        if normalized_match_id <= 0:

            return False

        return (
            self.db.get_learning_memory_count(
                event_type=BATCH_LEARNING_EVENT,
                reference_id=normalized_match_id,
            )
            > 0
        )

    # ========================================================
    # TEAM MEMORY
    # ========================================================

    def get_team_memory(
        self,
        team_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        История ETC конкретной команды.
        """

        normalized_team_id = _safe_int(
            team_id
        )

        if normalized_team_id <= 0:

            return []

        return self.get(
            object_type=(
                f"team:{normalized_team_id}"
            ),
            limit=limit,
            offset=offset,
        )

    # ========================================================
    # MATCH MEMORY
    # ========================================================

    def get_match_memory(
        self,
        match_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        История ETC конкретного матча.
        """

        normalized_match_id = _safe_int(
            match_id
        )

        if normalized_match_id <= 0:

            return []

        return self.get(
            object_type=(
                f"match:{normalized_match_id}"
            ),
            limit=limit,
            offset=offset,
        )

    # ========================================================
    # PARAMETER MEMORY
    # ========================================================

    def get_parameter_memory(
        self,
        parameter_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        История изменения конкретного параметра.
        """

        if not parameter_name:

            return []

        return self.get(
            object_type="model",
            feature=parameter_name,
            limit=limit,
            offset=offset,
        )

    # ========================================================
    # XG MEMORY
    # ========================================================

    def get_xg_memory_history(
        self,
        team_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        История xG-событий команды.
        """

        normalized_team_id = _safe_int(
            team_id
        )

        if normalized_team_id <= 0:

            return []

        return self.get(
            object_type=(
                f"team:{normalized_team_id}"
            ),
            event_type="xg_calibration",
            limit=limit,
            offset=offset,
        )

    # ========================================================
    # PREDICTION ERRORS
    # ========================================================

    def get_prediction_errors(
        self,
        match_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает ошибки прогнозов.
        """

        normalized_match_id = None

        if match_id is not None:

            normalized_match_id = _safe_int(
                match_id
            )

            if normalized_match_id <= 0:

                return []

        return self.get(
            object_type=(
                f"match:{normalized_match_id}"
                if normalized_match_id is not None
                else None
            ),
            event_type="prediction_error",
            limit=limit,
            offset=offset,
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

        if not object_type:

            return None

        rows = self.get(
            object_type=object_type,
            feature=feature,
            event_type=event_type,
            limit=1,
            offset=0,
        )

        return (
            rows[0]
            if rows
            else None
        )


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
    algorithm: str = DEFAULT_ALGORITHM,
    model_version: str = DEFAULT_MODEL_VERSION,
    reference_id: Optional[int] = None,
    created_at: Optional[str] = None,
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
        created_at=created_at,
    )


def record_batch_learning(
    db: FAJDatabase,
    match_id: int,
    *,
    feature: str = "etc_batch_processed",
    before_value: Any = None,
    after_value: Any = "processed",
    delta: Any = None,
    reason: str = "Матч успешно обработан ETC Learning Engine",
    confidence: float = 1.0,
    impact: float = 1.0,
    algorithm: str = "ETC.LearningEngine",
    model_version: str = DEFAULT_MODEL_VERSION,
    created_at: Optional[str] = None,
) -> int:
    """
    Module-level API для фиксации успешного
    ETC batch learning события.

    Это официальный контракт для ETCLearningEngine.
    """

    memory = LearningMemory(
        db=db
    )

    return memory.record_batch_learning(
        match_id=match_id,
        feature=feature,
        before_value=before_value,
        after_value=after_value,
        delta=delta,
        reason=reason,
        confidence=confidence,
        impact=impact,
        algorithm=algorithm,
        model_version=model_version,
        created_at=created_at,
    )


def get_learning_memory(
    db: FAJDatabase,
    object_type: Optional[str] = None,
    feature: Optional[str] = None,
    event_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Единая функция чтения памяти ETC.

    Поддерживает пагинацию через offset.
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
        offset=offset,
    )


def get_batch_learning_memory(
    db: FAJDatabase,
    match_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Module-level API для чтения batch_learning events.
    """

    memory = LearningMemory(
        db=db
    )

    return memory.get_batch_learning_memory(
        match_id=match_id,
        limit=limit,
        offset=offset,
    )


def is_match_processed(
    db: FAJDatabase,
    match_id: int,
) -> bool:
    """
    Module-level API для быстрой проверки
    обработан ли матч ETC.
    """

    memory = LearningMemory(
        db=db
    )

    return memory.is_match_processed(
        match_id=match_id
    )


# ============================================================
# STATUS
# ============================================================

def get_memory_status() -> Dict[str, Any]:
    """
    Технический статус LearningMemory.
    """

    return {
        "module": MODULE_NAME,

        "version": MODULE_VERSION,

        "role": "ETC_MEMORY_ADAPTER",

        "append_only": True,

        "writes_database": True,

        "writes_learning_memory": True,

        "reads_database": True,

        "reads_learning_memory": True,

        "changes_model": False,

        "changes_rating": False,

        "changes_parameters": False,

        "changes_facts": False,

        "deletes_data": False,

        "updates_data": False,

        "batch_learning_event": (
            BATCH_LEARNING_EVENT
        ),

        "database_layer": "FAJDatabase",

        "database_write_method": (
            "add_learning_memory"
        ),

        "database_read_method": (
            "get_learning_memory"
        ),

        "database_count_method": (
            "get_learning_memory_count"
        ),

        "adapter_pagination": True,
    }


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

    print(
        "FAJ ETC — LEARNING MEMORY"
    )

    print(
        f"Version: {MODULE_VERSION}"
    )

    print("=" * 70)

    print()

    print(
        "Режим: APPEND-ONLY"
    )

    print(
        "Обучение: НЕТ"
    )

    print(
        "Изменение модели: НЕТ"
    )

    print(
        "Изменение рейтинга: НЕТ"
    )

    print(
        "Изменение параметров: НЕТ"
    )

    print(
        "Изменение фактов: НЕТ"
    )

    print(
        "UPDATE: НЕТ"
    )

    print(
        "DELETE: НЕТ"
    )

    print()

    print(
        "Batch event:"
    )

    print(
        f"event_type = {BATCH_LEARNING_EVENT}"
    )

    print(
        "object = match:<match_id>"
    )

    print(
        "reference_id = match_id"
    )

    print()

    print(
        "Запись выполняется только через:"
    )

    print(
        "FAJDatabase.add_learning_memory()"
    )

    print()

    print(
        "Чтение выполняется только через:"
    )

    print(
        "FAJDatabase.get_learning_memory()"
    )

    print(
        "FAJDatabase.get_learning_memory_count()"
    )

    print()

    print(
        "НОВОЕ В v3.1:"
    )

    print(
        "1. get() поддерживает offset"
    )

    print(
        "2. offset НЕ передаётся в database.py"
    )

    print(
        "3. Пагинация выполняется адаптером (slice)"
    )

    print(
        "4. _deserialize() корректно восстанавливает bool из '1'/'0'"
    )

    print()

    print(
        "LearningMemory v3.1 готов."
    )

    print("=" * 70)
