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

ОТВЕТСТВЕННОСТЬ
---------------

BatchController отвечает только за:

    1. размер batch;
    2. поиск завершённых матчей;
    3. чтение processed markers;
    4. исключение уже обработанных матчей;
    5. выбор следующего batch;
    6. создание fingerprint;
    7. решение READY / WAIT /
       UNKNOWN_LEAGUE / ALREADY_PROCESSED;
    8. совместимый API create_batch();
    9. совместимый API mark_processed().

============================================================

АРХИТЕКТУРНЫЙ КОНТРАК
----------------------

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
------

BatchController НЕ создаёт:

    event_type = 'batch_learning'

Этот marker создаётся только после успешной
обработки матча через ETCLearningEngine.

BatchController только читает его.

============================================================

DATABASE CONTRACT
-----------------

database.py v12.1 — единственный источник схемы.

Используются:

    matches
    match_results
    learning_memory

Никакой собственной схемы здесь нет.

Никаких:

    DELETE
    DROP
    INSERT
    UPDATE

============================================================

FORCE
-----

force=False:

    запускается только полный batch.

force=True:

    разрешается обработать доступный неполный batch.

НО:

    force НЕ отменяет processed marker.

Уже обработанный матч никогда не возвращается
в новый batch только из-за force=True.

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


MODULE_VERSION = "1.2"
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
# ETC MEMORY CONTRACT
# ============================================================

PROCESSED_EVENT_TYPE = "batch_learning"


# ============================================================
# HELPERS
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
    Безопасное преобразование в int.
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

    Например:

        rpl
        Russia Premier League
        РПЛ

    → РПЛ
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

    НЕ выполняет обучение.

    НЕ пишет learning_memory.

    Только определяет:

        можно ли запускать ETC;

        какие матчи входят
        в текущий batch.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # BATCH SIZE
    # ========================================================

    def get_batch_size(
        self,
        league: str,
    ) -> int:
        """
        Возвращает требуемый размер batch.

        Неизвестный турнир:

            0
        """

        normalized = _normalize_league(
            league
        )

        return BATCH_RULES.get(
            normalized,
            0,
        )

    # ========================================================
    # CHECK
    # ========================================================

    def check(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет готовность турнира к ETC.

        Возможные состояния:

            READY
            WAIT
            UNKNOWN_LEAGUE
            ALREADY_PROCESSED

        Ничего в БД не изменяет.
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
        # COMPLETED MATCHES
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
        # PROCESSED
        # ----------------------------------------------------

        processed_ids = (
            self._get_processed_match_ids(
                league=normalized_league,
                season_id=season_id,
            )
        )

        result["processed_matches"] = len(
            processed_ids
        )

        # ----------------------------------------------------
        # NEW
        # ----------------------------------------------------

        new_matches: List[
            Dict[str, Any]
        ] = []

        for match in completed:

            match_id = _safe_int(
                match.get("id")
            )

            if match_id <= 0:
                continue

            if match_id in processed_ids:
                continue

            new_matches.append(
                match
            )

        result["new_matches"] = len(
            new_matches
        )

        # ----------------------------------------------------
        # NO NEW MATCHES
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
        # NOT ENOUGH
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
    # CREATE BATCH
    # ========================================================

    def create_batch(
        self,
        limit: Optional[int] = None,
        force: bool = False,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Совместимый контракт ETCController.

        ВАЖНО:

        Если league не передан, BatchController пытается
        определить единственный доступный турнир.

        Однако основной ETC-контракт может передавать
        league/season_id явно.

        force=True:

            разрешает неполный batch.

        force НЕ:

            возвращает уже обработанные матчи.
        """

        if league:

            normalized_league = (
                _normalize_league(
                    league
                )
            )

            return self._create_batch_for_league(
                league=normalized_league,
                season_id=season_id,
                limit=limit,
                force=force,
            )

        # ----------------------------------------------------
        # Автоматический режим.
        #
        # Используем известные турниры.
        # Берём первый READY.
        #
        # Это не меняет БД.
        # ----------------------------------------------------

        for known_league in BATCH_RULES:

            selected = (
                self._create_batch_for_league(
                    league=known_league,
                    season_id=season_id,
                    limit=limit,
                    force=force,
                )
            )

            if selected:

                return selected

        return []

    # ========================================================
    # CREATE BATCH — INTERNAL
    # ========================================================

    def _create_batch_for_league(
        self,
        league: str,
        season_id: Optional[int],
        limit: Optional[int],
        force: bool,
    ) -> List[Dict[str, Any]]:
        """
        Формирует batch конкретного турнира.
        """

        required = self.get_batch_size(
            league
        )

        if required <= 0:
            return []

        completed = (
            self._get_finished_matches(
                league=league,
                season_id=season_id,
            )
        )

        if not completed:
            return []

        processed_ids = (
            self._get_processed_match_ids(
                league=league,
                season_id=season_id,
            )
        )

        new_matches: List[
            Dict[str, Any]
        ] = []

        for match in completed:

            match_id = _safe_int(
                match.get("id")
            )

            if match_id <= 0:
                continue

            if match_id in processed_ids:
                continue

            new_matches.append(
                match
            )

        if not new_matches:
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
                target_size,
                safe_limit,
            )

        # ----------------------------------------------------
        # NORMAL MODE
        # ----------------------------------------------------

        if not force:

            if len(new_matches) < target_size:

                return []

        # ----------------------------------------------------
        # FORCE MODE
        # ----------------------------------------------------

        selected = new_matches[
            :target_size
        ]

        if not selected:
            return []

        logger.info(
            "ETC batch created | "
            "league=%s | season=%s | "
            "size=%s | required=%s | force=%s",
            league,
            season_id,
            len(selected),
            required,
            force,
        )

        return selected

    # ========================================================
    # GET LEARNING BATCH
    # ========================================================

    def get_learning_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Официальный контракт LearningEngine.

        Возвращает только READY batch.

        Если batch не готов:

            []

        Этот метод НЕ использует force.
        """

        check = self.check(
            league=league,
            season_id=season_id,
        )

        if check.get("status") != STATUS_READY:

            return []

        required = _safe_int(
            check.get(
                "required_matches"
            )
        )

        if required <= 0:
            return []

        if limit is not None:

            safe_limit = _safe_int(
                limit
            )

            if safe_limit <= 0:
                return []

            required = min(
                required,
                safe_limit,
            )

        match_ids = check.get(
            "match_ids",
            [],
        )

        if not match_ids:
            return []

        selected_ids = {
            _safe_int(match_id)
            for match_id in match_ids
        }

        matches = (
            self._get_finished_matches(
                league=_normalize_league(
                    league
                ),
                season_id=season_id,
            )
        )

        selected: List[
            Dict[str, Any]
        ] = []

        for match in matches:

            match_id = _safe_int(
                match.get("id")
            )

            if match_id not in selected_ids:
                continue

            selected.append(
                match
            )

            if len(selected) >= required:
                break

        return selected

    # ========================================================
    # SELECT BATCH
    # ========================================================

    def select_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compatibility API.
        """

        return self.get_learning_batch(
            league=league,
            season_id=season_id,
        )

    # ========================================================
    # MARK PROCESSED
    # ========================================================

    def mark_processed(
        self,
        items: List[Any],
    ) -> int:
        """
        Совместимый API ETCController.

        КРИТИЧЕСКОЕ ПРАВИЛО:

        BatchController НЕ пишет learning_memory.

        Поэтому этот метод НЕ создаёт marker.

        Marker уже должен быть создан
        ETCLearningEngine после успешной обработки.

        Метод только проверяет, сколько переданных
        матчей действительно имеют processed marker.

        Это позволяет ETCController использовать:

            mark_processed(successful_items)

        без двойной записи в learning_memory.

        Возвращается количество матчей,
        подтверждённых memory marker.

        Никаких изменений БД.
        """

        if not items:
            return 0

        processed_count = 0

        for item in items:

            match_id = (
                self._extract_match_id(
                    item
                )
            )

            if match_id is None:
                continue

            if self._has_processed_marker(
                match_id
            ):
                processed_count += 1

        logger.info(
            "ETC mark_processed verification | "
            "requested=%s | confirmed=%s",
            len(items),
            processed_count,
        )

        return processed_count

    # ========================================================
    # FINISHED MATCHES
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

        Фактический счёт читается через:

            FAJDatabase.get_match_result()

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
            # 0 — валидный счёт.
            # None — факта нет.
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
        # ----------------------------------------------------

        finished.sort(
            key=lambda item: (
                _safe_string(
                    item.get("date")
                    or item.get("match_date")
                ),
                _safe_int(
                    item.get("id")
                ),
            )
        )

        return finished

    # ========================================================
    # LEAGUE / SEASON
    # ========================================================

    def _match_belongs_to_league(
        self,
        match: Dict[str, Any],
        league: str,
        season_id: Optional[int],
    ) -> bool:
        """
        Проверяет турнир и сезон.

        Если season_id указан,
        отсутствие season_id у матча означает
        НЕ принадлежит сезону.

        Это предотвращает смешивание сезонов.
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
    # PROCESSED MATCH IDS
    # ========================================================

    def _get_processed_match_ids(
        self,
        league: str,
        season_id: Optional[int],
    ) -> Set[int]:
        """
        Читает обработанные матчи из learning_memory.

        Контракт:

            event_type = 'batch_learning'
            reference_id = match_id

        Дополнительный fallback:

            object = 'match:<id>'

        ВАЖНО:

        Фильтрация league/season здесь НЕ производится
        по memory, потому что canonical processed identity
        — это match_id.

        При этом сами кандидаты уже отфильтрованы
        по league/season в _get_finished_matches().
        """

        processed: Set[int] = set()

        try:

            conn = self.db.get_connection()

            try:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        event_type,
                        object,
                        reference_id
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

            # ------------------------------------------------
            # reference_id — canonical marker
            # ------------------------------------------------

            reference_id = (
                self._row_value(
                    row,
                    "reference_id",
                )
            )

            match_id = _safe_int(
                reference_id
            )

            if match_id > 0:

                processed.add(
                    match_id
                )

                continue

            # ------------------------------------------------
            # fallback object=match:<id>
            # ------------------------------------------------

            object_value = (
                self._row_value(
                    row,
                    "object",
                )
            )

            object_value = _safe_string(
                object_value
            )

            if object_value.startswith(
                "match:"
            ):

                match_id = _safe_int(
                    object_value[
                        len("match:"):
                    ]
                )

                if match_id > 0:

                    processed.add(
                        match_id
                    )

        return processed

    # ========================================================
    # HAS MARKER
    # ========================================================

    def _has_processed_marker(
        self,
        match_id: int,
    ) -> bool:
        """
        Проверяет один processed marker.

        Только SELECT.
        """

        try:

            conn = self.db.get_connection()

            try:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id
                    FROM learning_memory
                    WHERE event_type = ?
                      AND reference_id = ?
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (
                        PROCESSED_EVENT_TYPE,
                        match_id,
                    ),
                )

                row = cursor.fetchone()

                return row is not None

            finally:

                conn.close()

        except Exception as exc:

            logger.warning(
                "Unable to verify processed "
                "marker | match_id=%s | error=%s",
                match_id,
                exc,
            )

            return False

    # ========================================================
    # ROW VALUE
    # ========================================================

    @staticmethod
    def _row_value(
        row: Any,
        key: str,
    ) -> Any:
        """
        Унифицированное чтение sqlite3.Row,
        dict или tuple-like результата.
        """

        if row is None:
            return None

        # dict
        if isinstance(
            row,
            dict,
        ):

            return row.get(
                key
            )

        # sqlite3.Row / mapping-like
        try:

            return row[key]

        except Exception:
            pass

        # fallback tuple
        if isinstance(
            row,
            (tuple, list),
        ):

            mapping = {
                0: "event_type",
                1: "object",
                2: "reference_id",
            }

            index = None

            for idx, name in mapping.items():

                if name == key:

                    index = idx
                    break

            if (
                index is not None
                and index < len(row)
            ):

                return row[index]

        return None

    # ========================================================
    # MATCH ID
    # ========================================================

    @staticmethod
    def _extract_match_id(
        item: Any,
    ) -> Optional[int]:
        """
        Унифицированное извлечение match_id.

        Поддерживаются:

            int
            dict
            sqlite3.Row / Mapping
            object.match_id
            object.id
        """

        if item is None:
            return None

        # ----------------------------------------------------
        # INT
        # ----------------------------------------------------

        if isinstance(
            item,
            int,
        ):

            return (
                item
                if item > 0
                else None
            )

        # ----------------------------------------------------
        # DICT
        # ----------------------------------------------------

        if isinstance(
            item,
            dict,
        ):

            value = item.get(
                "match_id"
            )

            if value is None:

                value = item.get(
                    "id"
                )

            normalized = _safe_int(
                value
            )

            return (
                normalized
                if normalized > 0
                else None
            )

        # ----------------------------------------------------
        # MAPPING / SQLITE ROW
        # ----------------------------------------------------

        for key in (
            "match_id",
            "id",
        ):

            try:

                value = item[key]

                normalized = _safe_int(
                    value
                )

                if normalized > 0:

                    return normalized

            except Exception:
                pass

        # ----------------------------------------------------
        # OBJECT ATTRIBUTE
        # ----------------------------------------------------

        for attribute in (
            "match_id",
            "id",
        ):

            try:

                value = getattr(
                    item,
                    attribute,
                    None,
                )

                normalized = _safe_int(
                    value
                )

                if normalized > 0:

                    return normalized

            except Exception:
                pass

        return None

    # ========================================================
    # FINGERPRINT
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

        Fingerprint не строится по всему турниру.
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

    # ========================================================
    # BATCH INFO
    # ========================================================

    def get_batch_info(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Диагностическая информация
        о текущем batch.

        Ничего не изменяет.
        """

        check = self.check(
            league=league,
            season_id=season_id,
        )

        if check.get(
            "status"
        ) != STATUS_READY:

            return check

        batch = (
            self.get_learning_batch(
                league=league,
                season_id=season_id,
            )
        )

        result = dict(
            check
        )

        result[
            "selected_matches"
        ] = len(
            batch
        )

        result[
            "selected_match_ids"
        ] = [

            _safe_int(
                match.get("id")
            )

            for match in batch
        ]

        result[
            "selected_batch_fingerprint"
        ] = (

            self._build_fingerprint(
                batch
            )

            if batch

            else None
        )

        return result

    # ========================================================
    # PENDING COUNT
    # ========================================================

    def get_pending_count(
        self,
        league: Optional[str] = None,
        season_id: Optional[int] = None,
    ) -> int:
        """
        Read-only количество новых завершённых матчей.

        Если league не указан:

            считается сумма по известным турнирам.

        Этот метод нужен исключительно
        для диагностики/status().
        """

        if league:

            normalized = (
                _normalize_league(
                    league
                )
            )

            completed = (
                self._get_finished_matches(
                    league=normalized,
                    season_id=season_id,
                )
            )

            processed = (
                self._get_processed_match_ids(
                    league=normalized,
                    season_id=season_id,
                )
            )

            return sum(
                1
                for match in completed
                if _safe_int(
                    match.get("id")
                ) > 0
                and _safe_int(
                    match.get("id")
                ) not in processed
            )

        total = 0

        for known_league in BATCH_RULES:

            total += self.get_pending_count(
                league=known_league,
                season_id=season_id,
            )

        return total


# ============================================================
# MODULE-LEVEL API
# ============================================================

def check_batch(
    league: str,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Удобная функция проверки batch.
    """

    controller = BatchController(
        db=db
    )

    return controller.check(
        league=league,
        season_id=season_id,
    )


def get_batch_size(
    league: str,
) -> int:
    """
    Возвращает размер batch.
    """

    return BATCH_RULES.get(
        _normalize_league(
            league
        ),
        0,
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
    Официальный module-level API.
    """

    controller = BatchController(
        db=db
    )

    return controller.get_learning_batch(
        league=league,
        season_id=season_id,
        limit=limit,
    )


def select_batch(
    league: str,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[
    Dict[str, Any]
]:
    """
    Compatibility API.
    """

    return get_learning_batch(
        league=league,
        season_id=season_id,
        db=db,
    )


def create_batch(
    limit: Optional[int] = None,
    force: bool = False,
    league: Optional[str] = None,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[
    Dict[str, Any]
]:
    """
    Официальный module-level API
    для ETCController.
    """

    controller = BatchController(
        db=db
    )

    return controller.create_batch(
        limit=limit,
        force=force,
        league=league,
        season_id=season_id,
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
    print("STATUS CONTRACT")
    print("-" * 70)

    print(
        f"READY             = {STATUS_READY}"
    )

    print(
        f"WAIT              = {STATUS_WAIT}"
    )

    print(
        f"UNKNOWN_LEAGUE    = {STATUS_UNKNOWN_LEAGUE}"
    )

    print(
        f"ALREADY_PROCESSED = {STATUS_ALREADY_PROCESSED}"
    )

    print()
    print("PROCESSED EVENT")
    print("-" * 70)

    print(
        f"event_type = {PROCESSED_EVENT_TYPE}"
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
    print("ETC Batch Controller готов.")
    print("=" * 70)
