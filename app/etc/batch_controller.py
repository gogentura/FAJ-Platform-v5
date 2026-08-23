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
Контроллер пакетного обучения ETC.

ОТВЕТСТВЕННОСТЬ
---------------
BatchController отвечает только за:

    1. определение размера batch;
    2. поиск завершённых матчей;
    3. определение уже обработанных матчей;
    4. выбор следующего batch;
    5. создание fingerprint текущего batch;
    6. решение READY / WAIT / ALREADY_PROCESSED.

BatchController НЕ:

    - обучает модель;
    - изменяет FAJ Rating;
    - изменяет model_parameters;
    - рассчитывает xG;
    - изменяет фактические результаты;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - удаляет данные;
    - записывает learning_memory.

ПРАВИЛА BATCH v12.1
-------------------

    РПЛ       → 5 новых завершённых матчей
    АПЛ       → 3 новых завершённых матча
    Ла Лига   → 3 новых завершённых матча
    ЛЧ        → 2 новых завершённых матча

ОСНОВНОЙ КОНТРАКТ
-----------------

    FACTS
      ↓
    BatchController
      ↓
    WAIT / READY / ALREADY_PROCESSED
      ↓
    get_learning_batch()
      ↓
    ETC Learning Engine

ВАЖНО
------

BatchController не считает матч обученным просто потому,
что он завершён.

Матч считается обработанным только если в learning_memory
существует ETC event:

    event_type = 'batch_learning'

с соответствующим:

    reference_id = match_id

Таким образом:

    match_results
        ≠
    learning_memory

Завершённый матч становится "processed" только после
успешного завершения ETC Learning Engine.

DATABASE CONTRACT
-----------------

database.py v12.1 остаётся единственным источником схемы.

Используются существующие:

    matches
    match_results
    learning_memory

Никаких изменений схемы здесь нет.

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


MODULE_VERSION = "1.1"
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
    # RPL
    "rpl": "РПЛ",
    "russia premier league": "РПЛ",
    "russian premier league": "РПЛ",
    "россия": "РПЛ",
    "российская премьер-лига": "РПЛ",
    "российская премьер лига": "РПЛ",

    # EPL
    "epl": "АПЛ",
    "premier league": "АПЛ",
    "english premier league": "АПЛ",
    "england premier league": "АПЛ",
    "англия": "АПЛ",
    "английская премьер-лига": "АПЛ",
    "английская премьер лига": "АПЛ",

    # La Liga
    "la liga": "Ла Лига",
    "laliga": "Ла Лига",
    "spain la liga": "Ла Лига",
    "spanish la liga": "Ла Лига",
    "испания": "Ла Лига",
    "ла лига": "Ла Лига",

    # Champions League
    "ucl": "ЛЧ",
    "champions league": "ЛЧ",
    "uefa champions league": "ЛЧ",
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

# Этот event создаётся НЕ BatchController.
#
# Его создаёт ETCLearningEngine после успешной обработки
# конкретного матча.
#
# BatchController только читает эти события.
PROCESSED_EVENT_TYPE = "batch_learning"


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    """
    Возвращает текущее локальное время в ISO формате.
    """
    return datetime.now().isoformat()


def _normalize_league(league: str) -> str:
    """
    Нормализует название турнира.

    Примеры:

        rpl
        Russia Premier League
        РПЛ

    становятся:

        РПЛ
    """

    if league is None:
        return ""

    value = str(league).strip()

    if not value:
        return ""

    if value in BATCH_RULES:
        return value

    normalized = value.lower()

    return LEAGUE_ALIASES.get(
        normalized,
        value,
    )


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


# ============================================================
# MAIN CLASS
# ============================================================

class BatchController:
    """
    Контроллер пакетного обучения ETC.

    Только определяет:

        можно ли запускать обучение;

        какие именно матчи входят
        в следующий batch.

    Никакого обучения внутри класса нет.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC — BATCH SIZE
    # ========================================================

    def get_batch_size(
        self,
        league: str,
    ) -> int:
        """
        Возвращает минимальный размер batch
        для указанного турнира.

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
    # PUBLIC — CHECK
    # ========================================================

    def check(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет готовность турнира к ETC learning.

        Возможные статусы:

            READY
            WAIT
            UNKNOWN_LEAGUE
            ALREADY_PROCESSED

        Возвращает также:

            completed_matches
            processed_matches
            new_matches
            required_matches
            remaining_matches
            match_ids
            batch_fingerprint
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

            result["status"] = STATUS_UNKNOWN_LEAGUE

            result["reason"] = (
                f"Для турнира '{league}' "
                f"не задано правило ETC batch."
            )

            return result

        # ----------------------------------------------------
        # GET COMPLETED MATCHES
        # ----------------------------------------------------

        completed = self._get_finished_matches(
            league=normalized_league,
            season_id=season_id,
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
        # GET PROCESSED MATCHES
        # ----------------------------------------------------

        processed_ids = self._get_processed_match_ids(
            league=normalized_league,
            season_id=season_id,
        )

        result["processed_matches"] = len(
            processed_ids
        )

        # ----------------------------------------------------
        # FIND NEW MATCHES
        # ----------------------------------------------------

        new_matches: List[Dict[str, Any]] = []

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
                "Все доступные завершённые матчи "
                "уже обработаны ETC."
            )

            return result

        # ----------------------------------------------------
        # NOT ENOUGH FOR BATCH
        # ----------------------------------------------------

        if len(new_matches) < required:

            result["status"] = STATUS_WAIT

            result["remaining_matches"] = (
                required - len(new_matches)
            )

            result["reason"] = (
                "Недостаточно новых завершённых "
                "матчей для запуска ETC: "
                f"{len(new_matches)}/{required}."
            )

            return result

        # ----------------------------------------------------
        # CURRENT BATCH
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

        fingerprint = self._build_fingerprint(
            current_batch
        )

        result["status"] = STATUS_READY

        result["match_ids"] = match_ids

        result["batch_fingerprint"] = (
            fingerprint
        )

        result["remaining_matches"] = 0

        result["reason"] = (
            f"Батч готов: выбрано "
            f"{len(current_batch)} новых матчей "
            f"из требуемых {required}."
        )

        logger.info(
            "ETC batch READY | "
            "league=%s | "
            "season=%s | "
            "matches=%s | "
            "required=%s | "
            "fingerprint=%s",
            normalized_league,
            season_id,
            match_ids,
            required,
            fingerprint[:12],
        )

        return result

    # ========================================================
    # PUBLIC — OFFICIAL ETC CONTRACT
    # ========================================================

    def get_learning_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Официальный контракт BatchController
        для ETCLearningEngine.

        Возвращает текущий готовый batch.

        Если batch ещё не готов:

            []

        ВАЖНО:

        Метод ничего не записывает в БД.

        Он только:

            FACTS
              ↓
            CHECK
              ↓
            SELECT
        """

        check = self.check(
            league=league,
            season_id=season_id,
        )

        if check["status"] != STATUS_READY:

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

        matches = self._get_finished_matches(
            league=_normalize_league(
                league
            ),
            season_id=season_id,
        )

        selected: List[
            Dict[str, Any]
        ] = []

        selected_ids = set(
            _safe_int(match_id)
            for match_id in match_ids
        )

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
    # PUBLIC — SELECT BATCH
    # ========================================================

    def select_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает текущий готовый batch.

        Это публичный метод совместимости.

        Для ETC Learning Engine рекомендуется:

            get_learning_batch()
        """

        return self.get_learning_batch(
            league=league,
            season_id=season_id,
        )

    # ========================================================
    # FINISHED MATCHES
    # ========================================================

    def _get_finished_matches(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает завершённые матчи конкретного турнира.

        Источники:

            matches
            match_results

        Фактический счёт берётся ТОЛЬКО
        через FAJDatabase.get_match_result().

        Метод ничего не изменяет.
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

        normalized_league = _normalize_league(
            league
        )

        for match in matches:

            if not isinstance(match, dict):
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
            # Результат обязан содержать оба значения.
            # 0 — валидное значение.
            # None — отсутствие результата.
            # ------------------------------------------------

            if (
                home_goals is None
                or away_goals is None
            ):
                continue

            enriched = dict(match)

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
        # Хронологический порядок.
        #
        # Старые необученные матчи идут первыми.
        # Это обеспечивает детерминированное
        # формирование последовательных batch.
        #
        # ИСПРАВЛЕНО: используется date из database.py
        # с fallback на match_date
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
    # LEAGUE / SEASON FILTER
    # ========================================================

    def _match_belongs_to_league(
        self,
        match: Dict[str, Any],
        league: str,
        season_id: Optional[int],
    ) -> bool:
        """
        Проверяет принадлежность матча:

            турниру
            сезону

        ВАЖНО:

        Если season_id передан, матч обязан содержать
        соответствующий season_id.

        Если поле отсутствует — матч НЕ считается
        принадлежащим указанному сезону.

        Это предотвращает смешивание сезонов.
        """

        normalized_league = _normalize_league(
            league
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
            match.get("competition_name"),
            match.get("tournament"),
            match.get("league_name"),
        ]

        normalized_values: Set[str] = set()

        for value in possible_values:

            if value is None:
                continue

            normalized_value = (
                _normalize_league(
                    str(value)
                )
            )

            if normalized_value:

                normalized_values.add(
                    normalized_value
                )

        # Нет информации о турнире —
        # нельзя делать предположение.
        if not normalized_values:

            return False

        return (
            normalized_league
            in normalized_values
        )

    # ========================================================
    # PROCESSED MATCHES
    # ========================================================

    def _get_processed_match_ids(
        self,
        league: str,
        season_id: Optional[int],
    ) -> Set[int]:
        """
        Возвращает ID матчей, которые уже были
        успешно проведены через ETC batch.

        Источник:

            learning_memory

        Контракт:

            event_type = 'batch_learning'
            reference_id = match_id

        Дополнительно допускается object:

            match:<match_id>

        для большей надёжности.

        НИКАКИХ изменений БД здесь нет.
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

        # ----------------------------------------------------
        # Из memory берём только те записи,
        # которые однозначно указывают на match.
        # ----------------------------------------------------

        for row in rows:

            try:

                reference_id = row[
                    "reference_id"
                ]

            except (KeyError, TypeError):

                reference_id = None

            match_id = _safe_int(
                reference_id
            )

            if match_id > 0:

                processed.add(
                    match_id
                )

                continue

            # ------------------------------------------------
            # Fallback:
            #
            # object = match:<id>
            # ------------------------------------------------

            try:

                object_value = row[
                    "object"
                ]

            except (KeyError, TypeError):

                object_value = None

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
    # FINGERPRINT
    # ========================================================

    @staticmethod
    def _build_fingerprint(
        matches: List[
            Dict[str, Any]
        ],
    ) -> str:
        """
        Создаёт стабильный fingerprint
        КОНКРЕТНОГО текущего batch.

        В fingerprint входят:

            match_id
            home_team_id
            away_team_id
            result_home_goals
            result_away_goals

        Fingerprint НЕ строится по всем
        завершённым матчам турнира.

        Это важно:

            Batch #1
                M1 M2 M3 M4 M5

            Batch #2
                M6 M7 M8 M9 M10

        имеют разные fingerprints.
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
            encoded.encode("utf-8")
        ).hexdigest()

    # ========================================================
    # PUBLIC — BATCH INFO
    # ========================================================

    def get_batch_info(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Удобный диагностический метод.

        Возвращает полную информацию о текущем
        состоянии batch.

        Сам batch не запускает.
        """

        check = self.check(
            league=league,
            season_id=season_id,
        )

        if check["status"] != STATUS_READY:

            return check

        batch = self.get_learning_batch(
            league=league,
            season_id=season_id,
        )

        result = dict(check)

        result["selected_matches"] = len(
            batch
        )

        result["selected_match_ids"] = [
            _safe_int(
                match.get("id")
            )
            for match in batch
        ]

        result[
            "selected_batch_fingerprint"
        ] = self._build_fingerprint(
            batch
        ) if batch else None

        return result


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
    Возвращает размер batch для турнира.
    """

    return BATCH_RULES.get(
        _normalize_league(league),
        0,
    )


def get_learning_batch(
    league: str,
    season_id: Optional[int] = None,
    limit: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[Dict[str, Any]]:
    """
    Официальный module-level API ETC.

    Возвращает текущий готовый batch.

    Если batch не готов:

        []
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
) -> List[Dict[str, Any]]:
    """
    Совместимый module-level API.

    Использует тот же официальный механизм,
    что и get_learning_batch().
    """

    return get_learning_batch(
        league=league,
        season_id=season_id,
        db=db,
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
    print("FAJ ETC — Batch Controller")
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
        f"READY              = {STATUS_READY}"
    )

    print(
        f"WAIT               = {STATUS_WAIT}"
    )

    print(
        f"UNKNOWN_LEAGUE     = {STATUS_UNKNOWN_LEAGUE}"
    )

    print(
        f"ALREADY_PROCESSED  = {STATUS_ALREADY_PROCESSED}"
    )

    print()
    print("PROCESSED EVENT")
    print("-" * 70)

    print(
        f"event_type = {PROCESSED_EVENT_TYPE}"
    )

    print()
    print("ETC Batch Controller готов.")
    print("=" * 70)
