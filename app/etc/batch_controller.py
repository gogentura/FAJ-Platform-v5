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

МОДУЛЬ НЕ:
    - обучает модель;
    - изменяет параметры модели;
    - изменяет FAJ Rating;
    - рассчитывает xG;
    - изменяет фактические результаты;
    - удаляет данные.

МОДУЛЬ:
    - определяет минимальный размер батча;
    - определяет, готов ли турнир к обучению;
    - считает новые завершённые матчи;
    - предотвращает повторный запуск одного и того же батча;
    - возвращает решение READY / WAIT / ALREADY_PROCESSED.

ПРАВИЛА v12.1:

    РПЛ       → после 5 новых матчей
    АПЛ       → после 3 новых матчей
    Ла Лига   → после 3 новых матчей
    ЛЧ        → после 2 новых матчей

ВАЖНО:
    BatchController ничего не обучает.

    Он только отвечает на вопрос:

        "Можно ли сейчас запускать LEARNING?"

Архитектура:

    FACTS
      ↓
    BatchController
      ↓
    READY / WAIT
      ↓
    ETC
      ↓
    LEARNING
============================================================
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)

MODULE_VERSION = "1.0"
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


# Дополнительные варианты названий турниров.
# Они только нормализуют входное значение.
LEAGUE_ALIASES: Dict[str, str] = {
    "rpl": "РПЛ",
    "russia premier league": "РПЛ",
    "россия": "РПЛ",
    "российская премьер-лига": "РПЛ",

    "epl": "АПЛ",
    "premier league": "АПЛ",
    "england premier league": "АПЛ",
    "англия": "АПЛ",

    "la liga": "Ла Лига",
    "laliga": "Ла Лига",
    "spain la liga": "Ла Лига",
    "испания": "Ла Лига",

    "ucl": "ЛЧ",
    "champions league": "ЛЧ",
    "uefa champions league": "ЛЧ",
    "лига чемпионов": "ЛЧ",
}


# ============================================================
# HELPERS
# ============================================================

def _now() -> str:
    return datetime.now().isoformat()


def _normalize_league(league: str) -> str:
    """
    Нормализует название турнира.
    """

    if not league:
        return ""

    value = str(league).strip()

    if value in BATCH_RULES:
        return value

    alias = LEAGUE_ALIASES.get(value.lower())

    return alias or value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


# ============================================================
# MAIN CLASS
# ============================================================

class BatchController:
    """
    Контроллер пакетного обучения ETC.

    Не выполняет обучение.

    Только определяет готовность батча.
    """

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ) -> None:

        self.db = db or FAJDatabase()

    # ========================================================
    # PUBLIC
    # ========================================================

    def get_batch_size(self, league: str) -> int:
        """
        Возвращает минимальный размер батча для турнира.
        """

        normalized = _normalize_league(league)

        return BATCH_RULES.get(normalized, 0)

    # ========================================================

    def check(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Проверяет готовность турнира к обучению.

        Возвращает:

            status:
                READY
                WAIT
                UNKNOWN_LEAGUE
                ALREADY_PROCESSED

            completed_matches
            required_matches
            new_matches
            batch_fingerprint
        """

        normalized_league = _normalize_league(league)

        required = self.get_batch_size(normalized_league)

        result: Dict[str, Any] = {
            "success": True,
            "league": normalized_league,
            "season_id": season_id,
            "status": "WAIT",
            "completed_matches": 0,
            "processed_matches": 0,
            "new_matches": 0,
            "required_matches": required,
            "remaining_matches": required,
            "batch_fingerprint": None,
            "match_ids": [],
            "checked_at": _now(),
            "reason": "",
        }

        # ----------------------------------------------------
        # UNKNOWN LEAGUE
        # ----------------------------------------------------

        if required <= 0:

            result["success"] = False
            result["status"] = "UNKNOWN_LEAGUE"
            result["reason"] = (
                f"Для турнира '{league}' не задано правило батча."
            )

            return result

        # ----------------------------------------------------
        # GET FINISHED MATCHES
        # ----------------------------------------------------

        matches = self._get_finished_matches(
            league=normalized_league,
            season_id=season_id,
        )

        result["completed_matches"] = len(matches)

        if not matches:

            result["status"] = "WAIT"
            result["remaining_matches"] = required
            result["reason"] = (
                "Нет завершённых матчей для обучения."
            )

            return result

        # ----------------------------------------------------
        # FINGERPRINT
        # ----------------------------------------------------

        fingerprint = self._build_fingerprint(matches)

        result["batch_fingerprint"] = fingerprint

        # ----------------------------------------------------
        # ALREADY PROCESSED
        # ----------------------------------------------------

        processed = self._get_processed_match_ids(
            league=normalized_league,
            season_id=season_id,
        )

        result["processed_matches"] = len(processed)

        new_matches = [
            match
            for match in matches
            if _safe_int(match.get("id")) not in processed
        ]

        result["new_matches"] = len(new_matches)

        new_ids = [
            _safe_int(match.get("id"))
            for match in new_matches
            if match.get("id") is not None
        ]

        result["match_ids"] = new_ids

        # ----------------------------------------------------
        # CHECK BATCH
        # ----------------------------------------------------

        if len(new_matches) < required:

            result["status"] = "WAIT"

            result["remaining_matches"] = max(
                0,
                required - len(new_matches),
            )

            result["reason"] = (
                f"Недостаточно новых завершённых матчей: "
                f"{len(new_matches)}/{required}."
            )

            return result

        # ----------------------------------------------------
        # READY
        # ----------------------------------------------------

        result["status"] = "READY"
        result["remaining_matches"] = 0

        result["reason"] = (
            f"Батч готов: {len(new_matches)} новых матчей "
            f"при минимуме {required}."
        )

        logger.info(
            "ETC batch READY: league=%s new=%s required=%s",
            normalized_league,
            len(new_matches),
            required,
        )

        return result

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

        Фактический результат берётся только через FAJDatabase.

        Никакие данные матчей не изменяются.
        """

        matches = self.db.get_matches()

        finished: List[Dict[str, Any]] = []

        for match in matches:

            if not self._match_belongs_to_league(
                match,
                league,
                season_id,
            ):
                continue

            match_id = match.get("id")

            if match_id is None:
                continue

            fact = self.db.get_match_result(match_id)

            if not fact:
                continue

            home_goals = fact.get("home_goals")
            away_goals = fact.get("away_goals")

            if home_goals is None or away_goals is None:
                continue

            enriched = dict(match)

            enriched["result_home_goals"] = home_goals
            enriched["result_away_goals"] = away_goals

            finished.append(enriched)

        finished.sort(
            key=lambda item: (
                str(item.get("match_date") or ""),
                _safe_int(item.get("id")),
            )
        )

        return finished

    # ========================================================
    # LEAGUE FILTER
    # ========================================================

    def _match_belongs_to_league(
        self,
        match: Dict[str, Any],
        league: str,
        season_id: Optional[int],
    ) -> bool:
        """
        Проверяет принадлежность матча турниру.

        database.py остаётся единственным источником данных.

        Метод специально терпим к разным названиям колонок,
        поскольку календарные поля могут различаться между
        версиями FAJ.
        """

        # ----------------------------------------------------
        # SEASON
        # ----------------------------------------------------

        if season_id is not None:

            match_season = (
                match.get("season_id")
                or match.get("season")
            )

            if match_season is not None:

                if _safe_int(match_season, -1) != _safe_int(
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

        values = [
            _normalize_league(str(value))
            for value in possible_values
            if value is not None
        ]

        # Если в записи нет поля турнира, не делаем ложного
        # утверждения о принадлежности.
        if not values:
            return False

        return league in values

    # ========================================================
    # PROCESSED MATCHES
    # ========================================================

    def _get_processed_match_ids(
        self,
        league: str,
        season_id: Optional[int],
    ) -> set[int]:
        """
        Возвращает ID матчей, которые уже были использованы
        в ETC batch learning.

        В текущей версии источник — learning_memory.

        Старые записи не изменяются.
        """

        processed: set[int] = set()

        try:

            conn = self.db.get_connection()

            try:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT
                        object,
                        reference_id
                    FROM learning_memory
                    WHERE event_type = 'batch_learning'
                    ORDER BY id ASC
                    """
                )

                rows = cursor.fetchall()

                for row in rows:

                    reference_id = row["reference_id"]

                    if reference_id is not None:
                        processed.add(
                            _safe_int(reference_id)
                        )

            finally:
                conn.close()

        except Exception as exc:

            logger.warning(
                "Unable to read processed ETC batches: %s",
                exc,
            )

        return processed

    # ========================================================
    # FINGERPRINT
    # ========================================================

    @staticmethod
    def _build_fingerprint(
        matches: List[Dict[str, Any]],
    ) -> str:
        """
        Создаёт стабильный fingerprint набора матчей.

        Используется только для идентификации батча.
        """

        rows = []

        for match in matches:

            rows.append(
                {
                    "id": match.get("id"),
                    "home_team_id": match.get(
                        "home_team_id"
                    ),
                    "away_team_id": match.get(
                        "away_team_id"
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
            key=lambda row: _safe_int(row.get("id"))
        )

        encoded = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
        )

        return hashlib.sha256(
            encoded.encode("utf-8")
        ).hexdigest()

    # ========================================================
    # BATCH SELECTION
    # ========================================================

    def select_batch(
        self,
        league: str,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает только матчи текущего готового батча.

        Если батч не готов — возвращает [].

        Важно:
        здесь выбираются первые N новых матчей,
        где N = правило конкретного турнира.
        """

        check = self.check(
            league=league,
            season_id=season_id,
        )

        if check["status"] != "READY":
            return []

        required = check["required_matches"]
        match_ids = check["match_ids"]

        if not match_ids:
            return []

        matches = self._get_finished_matches(
            league=_normalize_league(league),
            season_id=season_id,
        )

        selected = []

        for match in matches:

            match_id = _safe_int(match.get("id"))

            if match_id in match_ids:

                selected.append(match)

            if len(selected) >= required:
                break

        return selected


# ============================================================
# MODULE-LEVEL API
# ============================================================

def check_batch(
    league: str,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> Dict[str, Any]:
    """
    Удобная функция проверки батча.
    """

    controller = BatchController(db=db)

    return controller.check(
        league=league,
        season_id=season_id,
    )


def get_batch_size(league: str) -> int:
    """
    Возвращает размер батча для турнира.
    """

    return BATCH_RULES.get(
        _normalize_league(league),
        0,
    )


def select_batch(
    league: str,
    season_id: Optional[int] = None,
    db: Optional[FAJDatabase] = None,
) -> List[Dict[str, Any]]:
    """
    Возвращает текущий готовый батч матчей.
    """

    controller = BatchController(db=db)

    return controller.select_batch(
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
    print("FAJ ETC — Batch Controller")
    print(f"Version: {MODULE_VERSION}")
    print("=" * 70)

    for league, size in BATCH_RULES.items():
        print(f"{league}: {size} матчей")

    print("=" * 70)
