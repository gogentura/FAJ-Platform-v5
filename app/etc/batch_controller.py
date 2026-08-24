#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center

app/etc/batch_controller.py
============================================================

НАЗНАЧЕНИЕ
-----------

BatchController — владелец ПРАВИЛ ВЫБОРА ETC BATCH.

Он определяет:

    FACTS
      ↓
    какие матчи завершены
      ↓
    какие уже обработаны ETC
      ↓
    сколько матчей требуется
      ↓
    READY / WAIT / ALREADY_PROCESSED
      ↓
    конкретный batch

BatchController НЕ выполняет обучение.

BatchController НЕ записывает learning_memory.

BatchController НЕ изменяет БД.

============================================================
ПУБЛИЧНЫЙ КОНТРАКТ
============================================================

Разрешены только:

    check()

    get_learning_batch()

Других публичных API BatchController
для ETC-контракта нет.

============================================================
АРХИТЕКТУРНЫЙ КОНТРАКТ
============================================================

MATCH
  ↓
IMPORT FACTS
  ↓
match_results / match_statistics
  ↓
BatchController
  ↓
ETCController
  ↓
ETCLearningEngine
  ↓
StatisticalAnalyzer
  ↓
LearningMemory
  ↓
batch_learning marker
  ↓
следующий ETC batch

============================================================
ВАЖНО
============================================================

BatchController НЕ создаёт:

    event_type = 'batch_learning'

Этот marker создаётся только после успешного
обучения через ETCLearningEngine.

BatchController только читает marker.

============================================================
DATABASE CONTRACT
============================================================

database.py v12.1 — единственный источник схемы.

Используются:

    matches
    match_results
    learning_memory

Никакой собственной схемы здесь нет.

Никаких:

    INSERT
    UPDATE
    DELETE
    DROP

============================================================
PROCESSED CONTRACT
============================================================

Единственный canonical processed marker:

    learning_memory.event_type = 'batch_learning'

Идентификатор матча:

    learning_memory.reference_id = match_id

Поле:

    object

НЕ используется.

Fallback:

    object = 'match:<id>'

полностью запрещён.

============================================================
BATCH RULES
============================================================

РПЛ       → 5
АПЛ       → 3
Ла Лига   → 3
ЛЧ        → 2

============================================================
FORCE
============================================================

BatchController не реализует force.

Почему:

    force — это orchestration policy,

а не правило выбора нормального ETC batch.

Неполный batch не является READY.

============================================================
READ ONLY
============================================================

Все операции BatchController используют только SELECT
через существующий FAJDatabase API.

Никаких изменений базы данных.
============================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


from app.database import FAJDatabase


logger = logging.getLogger(__name__)


# ============================================================
# MODULE
# ============================================================

MODULE_VERSION = "1.3"
MODULE_NAME = "ETC Batch Controller"


# ============================================================
# BATCH RULES
# ============================================================

BATCH_RULES: Dict[str, int] = {
    "РПЛ": 5,
    "АПЛ": 3,
    "Ла Лига": 3,
    "ЛЧ": 2,
}


# ============================================================
# LEAGUE ALIASES
# ============================================================

LEAGUE_ALIASES: Dict[str, str] = {

    # --------------------------------------------------------
    # RPL
    # --------------------------------------------------------

    "rpl": "РПЛ",
    "russia premier league": "РПЛ",
    "russian premier league": "РПЛ",
    "russia premier liga": "РПЛ",
    "россия": "РПЛ",
    "российская премьер-лига": "РПЛ",
    "российская премьер лига": "РПЛ",

    # --------------------------------------------------------
    # EPL
    # --------------------------------------------------------

    "epl": "АПЛ",
    "premier league": "АПЛ",
    "english premier league": "АПЛ",
    "england premier league": "АПЛ",
    "англия": "АПЛ",
    "английская премьер-лига": "АПЛ",
    "английская премьер лига": "АПЛ",

    # --------------------------------------------------------
    # LA LIGA
    # --------------------------------------------------------

    "la liga": "Ла Лига",
    "laliga": "Ла Лига",
    "spain la liga": "Ла Лига",
    "spanish la liga": "Ла Лига",
    "испания": "Ла Лига",
    "ла лига": "Ла Лига",

    # --------------------------------------------------------
    # CHAMPIONS LEAGUE
    # --------------------------------------------------------

    "ucl": "ЛЧ",
    "champions league": "ЛЧ",
    "uefa champions league": "ЛЧ",
    "лига чемпионов": "ЛЧ",
    "лига чемпионов уефа": "ЛЧ",
}


# ============================================================
# STATUS CONSTANTS
# ============================================================

STATUS_READY = "READY"
STATUS_WAIT = "WAIT"
STATUS_UNKNOWN_LEAGUE = "UNKNOWN_LEAGUE"
STATUS_ALREADY_PROCESSED = "ALREADY_PROCESSED"


# ============================================================
# LEARNING MEMORY CONTRACT
# ============================================================

PROCESSED_EVENT_TYPE = "batch_learning"


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _now() -> str:
    """
    Текущее локальное время в ISO-формате.
    """

    return datetime.now().isoformat()


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Безопасное преобразование значения в int.
    """

    try:

        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):

        return default


def _safe_string(
    value: Any,
) -> str:
    """
    Безопасное строковое представление.
    """

    if value is None:
        return ""

    return str(value).strip()


def _normalize_league(
    league: Any,
) -> str:
    """
    Нормализует название турнира.
    """

    if league is None:
        return ""

    value = str(
        league
    ).strip()

    if not value:
        return ""

    if value in BATCH_RULES:
        return value

    normalized = value.lower()

    return LEAGUE_ALIASES.get(
        normalized,
        value,
    )


# ============================================================
# MAIN CLASS
# ============================================================

class BatchController:
    """
    Контроллер ETC batch.

    ПУБЛИЧНЫЕ МЕТОДЫ:

        check()
        get_learning_batch()

    Всё остальное — внутренние implementation details.

    Контроллер строго READ ONLY.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC API
    # ========================================================

    def check(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет готовность следующего ETC batch.

        Возможные состояния:

            READY
            WAIT
            UNKNOWN_LEAGUE
            ALREADY_PROCESSED

        Ничего в БД не изменяет.

        ВАЖНО:

        check() только проверяет состояние.

        Он НЕ выполняет обучение.
        Он НЕ создаёт marker.
        """

        normalized_league = _normalize_league(
            league
        )

        required = self.get_batch_size(
            normalized_league
        )

        result: Dict[str, Any] = {

            "success": True,

            "module": MODULE_NAME,
            "version": MODULE_VERSION,

            "league": normalized_league,
            "season_id": season_id,

            "status": STATUS_WAIT,

            "completed_matches": 0,
            "processed_matches": 0,
            "new_matches": 0,

            "required_matches": required,
            "remaining_matches": required,

            "match_ids": [],

            "batch_fingerprint": None,

            "checked_at": _now(),

            "reason": "",
        }

        # ----------------------------------------------------
        # UNKNOWN LEAGUE
        # ----------------------------------------------------

        if required <= 0:

            result["success"] = False

            result["status"] = (
                STATUS_UNKNOWN_LEAGUE
            )

            result["reason"] = (
                f"Для турнира '{league}' "
                f"не задано правило ETC batch."
            )

            return result

        # ----------------------------------------------------
        # READ COMPLETED MATCHES
        # ----------------------------------------------------

        completed = (
            self._get_finished_matches(
                league=normalized_league,
                season_id=season_id,
            )
        )

        result["completed_matches"] = len(
            completed
        )

        if not completed:

            result["status"] = STATUS_WAIT

            result["remaining_matches"] = required

            result["reason"] = (
                "Нет завершённых матчей "
                "с доступным фактическим результатом."
            )

            return result

        # ----------------------------------------------------
        # READ PROCESSED MARKERS
        # ----------------------------------------------------

        processed_ids = (
            self._get_processed_match_ids()
        )

        result["processed_matches"] = len(
            processed_ids
        )

        # ----------------------------------------------------
        # FIND NEW MATCHES
        # ----------------------------------------------------

        new_matches = [
            match
            for match in completed
            if _safe_int(
                match.get("id")
            ) > 0
            and _safe_int(
                match.get("id")
            ) not in processed_ids
        ]

        result["new_matches"] = len(
            new_matches
        )

        # ----------------------------------------------------
        # NOTHING NEW
        # ----------------------------------------------------

        if not new_matches:

            result["status"] = (
                STATUS_ALREADY_PROCESSED
            )

            result["remaining_matches"] = required

            result["reason"] = (
                "Все доступные завершённые "
                "матчи уже обработаны ETC."
            )

            return result

        # ----------------------------------------------------
        # NOT ENOUGH FOR FULL BATCH
        # ----------------------------------------------------

        if len(new_matches) < required:

            result["status"] = STATUS_WAIT

            result["remaining_matches"] = (
                required - len(new_matches)
            )

            result["reason"] = (
                "Недостаточно новых завершённых "
                "матчей для полного ETC batch: "
                f"{len(new_matches)}/{required}."
            )

            return result

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        current_batch = new_matches[
            :required
        ]

        match_ids = [
            _safe_int(
                match.get("id")
            )
            for match in current_batch
        ]

        fingerprint = (
            self._build_fingerprint(
                current_batch
            )
        )

        result["status"] = STATUS_READY

        result["match_ids"] = match_ids

        result["batch_fingerprint"] = (
            fingerprint
        )

        result["remaining_matches"] = 0

        result["reason"] = (
            f"Батч готов: выбрано "
            f"{len(current_batch)} матчей "
            f"из требуемых {required}."
        )

        logger.info(
            "ETC batch READY | "
            "league=%s | season=%s | "
            "matches=%s | required=%s | "
            "fingerprint=%s",
            normalized_league,
            season_id,
            match_ids,
            required,
            fingerprint[:12],
        )

        return result

    # ========================================================

    def get_learning_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает следующий готовый ETC batch.

        ВАЖНО:

        Метод НЕ вызывает check().

        Все данные читаются один раз:

            matches
            ↓
            match_results
            ↓
            learning_memory
            ↓
            фильтрация
            ↓
            сортировка
            ↓
            limit
            ↓
            batch

        Это исключает двойной проход:

            check()
                +
            повторное чтение matches.

        Неполный обычный batch НЕ возвращается.

        Если limit задан:

            limit является только верхней границей
            возвращаемого batch.

        Основное правило турнира сохраняется.

        Например:

            РПЛ = 5

        limit=3

            максимум 3 матча.

        limit=10

            максимум 5 матчей.
        """

        normalized_league = _normalize_league(
            league
        )

        required = self.get_batch_size(
            normalized_league
        )

        if required <= 0:
            return []

        # ----------------------------------------------------
        # LIMIT
        # ----------------------------------------------------

        target_size = required

        if limit is not None:

            safe_limit = _safe_int(
                limit
            )

            if safe_limit <= 0:
                return []

            target_size = min(
                required,
                safe_limit,
            )

        # ----------------------------------------------------
        # READ COMPLETED MATCHES
        # ----------------------------------------------------

        completed = (
            self._get_finished_matches(
                league=normalized_league,
                season_id=season_id,
            )
        )

        if not completed:
            return []

        # ----------------------------------------------------
        # READ PROCESSED MARKERS
        # ----------------------------------------------------

        processed_ids = (
            self._get_processed_match_ids()
        )

        # ----------------------------------------------------
        # FILTER NEW
        # ----------------------------------------------------

        new_matches = [
            match
            for match in completed
            if _safe_int(
                match.get("id")
            ) > 0
            and _safe_int(
                match.get("id")
            ) not in processed_ids
        ]

        # ----------------------------------------------------
        # FULL BATCH READINESS
        # ----------------------------------------------------

        if len(new_matches) < required:

            logger.info(
                "ETC batch WAIT | "
                "league=%s | season=%s | "
                "available=%s | required=%s",
                normalized_league,
                season_id,
                len(new_matches),
                required,
            )

            return []

        # ----------------------------------------------------
        # DIRECT SELECTION
        # ----------------------------------------------------

        selected = new_matches[
            :target_size
        ]

        logger.info(
            "ETC learning batch selected | "
            "league=%s | season=%s | "
            "size=%s | required=%s | limit=%s",
            normalized_league,
            season_id,
            len(selected),
            required,
            limit,
        )

        return selected

    # ========================================================
    # INTERNAL — BATCH SIZE
    # ========================================================

    def get_batch_size(
        self,
        league: str,
    ) -> int:
        """
        Внутреннее получение размера batch.

        Метод технически публично доступен Python,
        но не является ETC API.

        Используется только самим контроллером.
        """

        normalized = _normalize_league(
            league
        )

        return BATCH_RULES.get(
            normalized,
            0,
        )

    # ========================================================
    # INTERNAL — FINISHED MATCHES
    # ========================================================

    def _get_finished_matches(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает завершённые матчи.

        Источник календаря:

            matches

        Источник факта:

            match_results

        Никаких изменений БД.
        """

        try:

            matches = self.db.get_matches()

        except Exception as exc:

            logger.exception(
                "Unable to read matches: %s",
                exc,
            )

            return []

        finished: List[
            Dict[str, Any]
        ] = []

        normalized_league = (
            _normalize_league(
                league
            )
        )

        for match in matches:

            if not isinstance(
                match,
                dict,
            ):
                continue

            if not self._match_belongs_to_league(
                match=match,
                league=normalized_league,
                season_id=season_id,
            ):
                continue

            match_id = _safe_int(
                match.get("id")
            )

            if match_id <= 0:
                continue

            try:

                fact = self.db.get_match_result(
                    match_id
                )

            except Exception as exc:

                logger.warning(
                    "Unable to read result "
                    "for match_id=%s: %s",
                    match_id,
                    exc,
                )

                continue

            if not fact:
                continue

            home_goals = fact.get(
                "home_goals"
            )

            away_goals = fact.get(
                "away_goals"
            )

            # ------------------------------------------------
            # 0:0 является валидным результатом.
            #
            # None означает отсутствие факта.
            # ------------------------------------------------

            if (
                home_goals is None
                or away_goals is None
            ):
                continue

            enriched = dict(
                match
            )

            enriched[
                "result_home_goals"
            ] = home_goals

            enriched[
                "result_away_goals"
            ] = away_goals

            finished.append(
                enriched
            )

        # ----------------------------------------------------
        # ДЕТЕРМИНИРОВАННЫЙ ПОРЯДОК
        #
        # ТОЛЬКО:
        #
        #     match_date
        #     match_id
        #
        # Никаких date fallback.
        # ----------------------------------------------------

        finished.sort(
            key=lambda item: (
                _safe_string(
                    item.get("match_date")
                ),
                _safe_int(
                    item.get("id")
                ),
            )
        )

        return finished

    # ========================================================
    # INTERNAL — LEAGUE / SEASON
    # ========================================================

    def _match_belongs_to_league(
        self,
        match: Dict[str, Any],
        league: str,
        season_id: Optional[int],
    ) -> bool:
        """
        Проверяет принадлежность матча
        турниру и сезону.

        Если season_id указан,
        отсутствие season_id у матча означает:

            матч НЕ принадлежит сезону.

        Это запрещает смешивание сезонов.
        """

        normalized_league = (
            _normalize_league(
                league
            )
        )

        # ----------------------------------------------------
        # SEASON
        # ----------------------------------------------------

        if season_id is not None:

            possible_season = (
                match.get("season_id")
            )

            if possible_season is None:

                possible_season = (
                    match.get("season")
                )

            if possible_season is None:
                return False

            if _safe_int(
                possible_season,
                -1,
            ) != _safe_int(
                season_id,
                -2,
            ):

                return False

        # ----------------------------------------------------
        # LEAGUE
        # ----------------------------------------------------

        possible_values = [

            match.get("league"),

            match.get("competition"),

            match.get(
                "competition_name"
            ),

            match.get(
                "tournament"
            ),

            match.get(
                "league_name"
            ),
        ]

        normalized_values: Set[
            str
        ] = set()

        for value in possible_values:

            if value is None:
                continue

            normalized_value = (
                _normalize_league(
                    value
                )
            )

            if normalized_value:

                normalized_values.add(
                    normalized_value
                )

        # ----------------------------------------------------
        # НЕЛЬЗЯ УГАДЫВАТЬ ТУРНИР
        # ----------------------------------------------------

        if not normalized_values:
            return False

        return (
            normalized_league
            in normalized_values
        )

    # ========================================================
    # INTERNAL — PROCESSED MARKERS
    # ========================================================

    def _get_processed_match_ids(
        self,
    ) -> Set[int]:
        """
        Читает processed markers из learning_memory.

        CANONICAL CONTRACT:

            event_type = 'batch_learning'
            reference_id = match_id

        Поле object НЕ используется.

        Fallback object=match:<id> отсутствует.

        Метод только читает БД.
        """

        processed: Set[int] = set()

        try:

            conn = self.db.get_connection()

            try:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT reference_id
                    FROM learning_memory
                    WHERE event_type = ?
                    ORDER BY id ASC
                    """,
                    (
                        PROCESSED_EVENT_TYPE,
                    ),
                )

                rows = cursor.fetchall()

            finally:

                conn.close()

        except Exception as exc:

            logger.warning(
                "Unable to read ETC processed "
                "matches from learning_memory: %s",
                exc,
            )

            return processed

        for row in rows:

            reference_id = (
                self._row_reference_id(
                    row
                )
            )

            match_id = _safe_int(
                reference_id
            )

            if match_id > 0:

                processed.add(
                    match_id
                )

        return processed

    # ========================================================
    # INTERNAL — ROW REFERENCE ID
    # ========================================================

    @staticmethod
    def _row_reference_id(
        row: Any,
    ) -> Any:
        """
        Извлекает reference_id из sqlite3.Row,
        dict или tuple-like результата.

        SELECT содержит только reference_id,
        поэтому tuple fallback использует индекс 0.
        """

        if row is None:
            return None

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(
            row,
            dict,
        ):

            return row.get(
                "reference_id"
            )

        # ----------------------------------------------------
        # SQLITE ROW / MAPPING
        # ----------------------------------------------------

        try:

            return row[
                "reference_id"
            ]

        except Exception:
            pass

        # ----------------------------------------------------
        # TUPLE
        # ----------------------------------------------------

        if isinstance(
            row,
            (tuple, list),
        ):

            if len(row) > 0:
                return row[0]

        return None

    # ========================================================
    # INTERNAL — FINGERPRINT
    # ========================================================

    @staticmethod
    def _build_fingerprint(
        matches: List[
            Dict[str, Any]
        ],
    ) -> str:
        """
        Создаёт SHA-256 fingerprint
        конкретного batch.

        В fingerprint входят:

            match_id
            home_team_id
            away_team_id
            result_home_goals
            result_away_goals

        Fingerprint относится только
        к выбранному batch.
        """

        rows: List[
            Dict[str, Any]
        ] = []

        for match in matches:

            rows.append(
                {
                    "id": _safe_int(
                        match.get("id")
                    ),

                    "home_team_id": _safe_int(
                        match.get(
                            "home_team_id"
                        )
                    ),

                    "away_team_id": _safe_int(
                        match.get(
                            "away_team_id"
                        )
                    ),

                    "home_goals": match.get(
                        "result_home_goals"
                    ),

                    "away_goals": match.get(
                        "result_away_goals"
                    ),
                }
            )

        rows.sort(
            key=lambda row: _safe_int(
                row.get("id")
            )
        )

        encoded = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

        return hashlib.sha256(
            encoded.encode(
                "utf-8"
            )
        ).hexdigest()


# ============================================================
# MODULE-LEVEL PUBLIC API
# ============================================================

def check_batch(
    league: str,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Удобная module-level обёртка для check().

    Это не отдельная логика.
    """

    controller = BatchController(
        db=db
    )

    return controller.check(
        league=league,
        season_id=season_id,
    )


def get_learning_batch(
    league: str,
    season_id: Optional[int] = None,
    limit: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[
    Dict[str, Any]
]:
    """
    Module-level API для ETC Learning Engine.

    Вся логика находится в BatchController.
    """

    controller = BatchController(
        db=db
    )

    return controller.get_learning_batch(
        league=league,
        season_id=season_id,
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
    print("FAJ Platform v12.1")
    print("ETC — Evolution Training Center")
    print("Batch Controller")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    print()
    print("BATCH RULES")
    print("-" * 70)

    for league, size in BATCH_RULES.items():

        print(
            f"{league}: {size} матчей"
        )

    print()
    print("PUBLIC ETC API")
    print("-" * 70)

    print(
        "BatchController.check()"
    )

    print(
        "BatchController.get_learning_batch()"
    )

    print()
    print("PROCESSED MARKER")
    print("-" * 70)

    print(
        f"event_type = {PROCESSED_EVENT_TYPE}"
    )

    print(
        "identity = learning_memory.reference_id"
    )

    print(
        "object fallback = DISABLED"
    )

    print()
    print("ARCHITECTURAL RULES")
    print("-" * 70)

    print(
        "BatchController: READ ONLY"
    )

    print(
        "LearningMemory: append-only"
    )

    print(
        "batch_learning marker: "
        "создаётся ETCLearningEngine"
    )

    print(
        "DELETE/DROP: отсутствуют"
    )

    print(
        "INSERT/UPDATE: отсутствуют"
    )

    print(
        "matches: не изменяются"
    )

    print(
        "match_results: не изменяются"
    )

    print(
        "match_statistics: не изменяются"
    )

    print(
        "database.py: не изменяется"
    )

    print()
    print("SORT CONTRACT")
    print("-" * 70)

    print(
        "1. match_date"
    )

    print(
        "2. match_id"
    )

    print()
    print("ETC Batch Controller готов.")
    print("=" * 70)
