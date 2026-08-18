#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1 — MEMORY HARDENED
MATCH MANAGER v3.0
============================================================

НАЗНАЧЕНИЕ:
    Управление матчами календаря FAJ.

ОТВЕТСТВЕННОСТЬ:
    - создание матча;
    - получение матчей;
    - получение матча по ID;
    - получение матчей тура;
    - проверка дублей;
    - удаление отдельного матча;
    - удаление тура;
    - базовая валидация.

НЕ ОТВЕЧАЕТ ЗА:
    - прогнозирование;
    - результаты;
    - парсинг статистики;
    - обучение;
    - паспорта;
    - структуру БД.

ПРИНЦИП:
    database.py = единственный источник работы с БД.

    MatchManager работает только через FAJDatabase.

ВАЖНО:
    SQLite only.
    Никаких очисток таблиц.
    Никаких DELETE напрямую отсюда.
============================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


class MatchManager:
    """Менеджер матчей FAJ v3.0."""

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_match_data(data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise TypeError("Match data must be a dictionary")

        result = dict(data)

        home_team_id = result.get("home_team_id")
        away_team_id = result.get("away_team_id")
        match_date = result.get("date")

        if home_team_id is None:
            raise ValueError("home_team_id is required")

        if away_team_id is None:
            raise ValueError("away_team_id is required")

        if home_team_id == away_team_id:
            raise ValueError(
                "home_team_id and away_team_id cannot be identical"
            )

        if not match_date:
            raise ValueError("date is required")

        result["date"] = str(match_date).strip()

        if not result["date"]:
            raise ValueError("date cannot be empty")

        result.setdefault("competition", "RPL")
        result.setdefault("status", "scheduled")
        result.setdefault("fact_status", "scheduled")
        result.setdefault("data_quality", 1.0)

        return result

    # ========================================================
    # SAVE
    # ========================================================

    def save_match(self, data: Dict[str, Any]) -> int:
        """
        Создаёт или обновляет матч через FAJDatabase.
        """

        match_data = self._normalize_match_data(data)

        match_id = self.db.upsert_match(match_data)

        if not match_id:
            raise RuntimeError(
                "FAJDatabase.upsert_match() не вернул match_id"
            )

        logger.info(
            "MATCH SAVED | id=%s | home=%s | away=%s | round=%s",
            match_id,
            match_data.get("home_team_id"),
            match_data.get("away_team_id"),
            match_data.get("round_id"),
        )

        return int(match_id)

    # ========================================================
    # GET ONE
    # ========================================================

    def get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает один матч.

        Прямой READ-only SQL оставлен здесь только потому,
        что database.py пока не содержит get_match_by_id().
        """

        if match_id is None:
            return None

        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM matches
                WHERE id = ?
                LIMIT 1
                """,
                (match_id,),
            )

            row = cursor.fetchone()

            return dict(row) if row else None

        finally:
            conn.close()

    # ========================================================
    # GET BY UUID
    # ========================================================

    def get_match_by_uuid(
        self,
        match_uuid: str,
    ) -> Optional[Dict[str, Any]]:
        if not match_uuid:
            return None

        row = self.db.get_match_by_uuid(match_uuid)

        return dict(row) if row else None

    # ========================================================
    # GET MATCHES
    # ========================================================

    def get_matches(
        self,
        round_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        rows = self.db.get_matches(round_id=round_id)

        return [dict(row) for row in rows]

    # ========================================================
    # GET ROUND MATCHES
    # ========================================================

    def get_round_matches(
        self,
        round_id: Optional[int],
    ) -> List[Dict[str, Any]]:

        if round_id is None:
            return []

        return self.get_matches(round_id=round_id)

    # ========================================================
    # EXISTENCE
    # ========================================================

    def match_exists(
        self,
        match_id: Optional[int] = None,
        match_uuid: Optional[str] = None,
    ) -> bool:

        if match_id is not None:
            return self.get_match(match_id) is not None

        if match_uuid:
            return self.get_match_by_uuid(match_uuid) is not None

        return False

    # ========================================================
    # DUPLICATE CHECK
    # ========================================================

    def find_duplicate(
        self,
        round_id: int,
        home_team_id: int,
        away_team_id: int,
        date: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Ищет точно такой же матч внутри тура.
        """

        matches = self.get_round_matches(round_id)

        for match in matches:
            if (
                int(match["home_team_id"]) == int(home_team_id)
                and int(match["away_team_id"]) == int(away_team_id)
                and str(match["date"]) == str(date)
            ):
                return match

        return None

    # ========================================================
    # DELETE MATCH
    # ========================================================

    def delete_match(self, match_id: int) -> bool:
        """
        Удаляет один матч через FAJDatabase.
        """

        if match_id is None:
            return False

        existing = self.get_match(match_id)

        if not existing:
            logger.warning(
                "DELETE MATCH: match_id=%s not found",
                match_id,
            )
            return False

        deleted = self.db.delete_match(int(match_id))

        if deleted:
            logger.info(
                "MATCH DELETED | id=%s",
                match_id,
            )

        return bool(deleted)

    # ========================================================
    # DELETE ROUND
    # ========================================================

    def delete_round(self, round_id: int) -> bool:
        """
        Удаляет тур через FAJDatabase.
        """

        if round_id is None:
            return False

        deleted = self.db.delete_round(int(round_id))

        if deleted:
            logger.info(
                "ROUND DELETED | id=%s",
                round_id,
            )

        return bool(deleted)

    # ========================================================
    # STATUS
    # ========================================================

    def get_scheduled_matches(
        self,
        round_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        matches = self.get_matches(round_id)

        return [
            match
            for match in matches
            if str(match.get("status", "")).lower()
            in {
                "scheduled",
                "upcoming",
                "pending",
            }
        ]

    def get_finished_matches(
        self,
        round_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:

        matches = self.get_matches(round_id)

        return [
            match
            for match in matches
            if str(match.get("status", "")).lower()
            in {
                "finished",
                "completed",
            }
        ]

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate_match(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        errors: List[str] = []
        warnings: List[str] = []

        if not isinstance(data, dict):
            return {
                "valid": False,
                "errors": ["Match data must be a dictionary"],
                "warnings": [],
            }

        home_team_id = data.get("home_team_id")
        away_team_id = data.get("away_team_id")
        round_id = data.get("round_id")
        match_date = data.get("date")

        if home_team_id is None:
            errors.append("home_team_id is missing")

        if away_team_id is None:
            errors.append("away_team_id is missing")

        if (
            home_team_id is not None
            and away_team_id is not None
            and home_team_id == away_team_id
        ):
            errors.append(
                "home_team_id and away_team_id are identical"
            )

        if round_id is None:
            errors.append("round_id is missing")

        if not match_date:
            errors.append("date is missing")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    # ========================================================
    # CALENDAR IMPORT
    # ========================================================

    def import_calendar(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not isinstance(matches, list):
            raise TypeError("matches must be a list")

        saved = 0
        rejected = 0
        errors = []
        match_ids = []

        for index, data in enumerate(matches):

            validation = self.validate_match(data)

            if not validation["valid"]:
                rejected += 1

                errors.append(
                    {
                        "index": index,
                        "match": data,
                        "errors": validation["errors"],
                    }
                )

                continue

            try:
                match_id = self.save_match(data)

                saved += 1
                match_ids.append(match_id)

            except Exception as exc:
                logger.exception(
                    "Calendar import failed at index %s",
                    index,
                )

                errors.append(
                    {
                        "index": index,
                        "match": data,
                        "errors": [str(exc)],
                    }
                )

        return {
            "success": len(errors) == 0,
            "received": len(matches),
            "saved": saved,
            "rejected": rejected,
            "match_ids": match_ids,
            "errors": errors,
        }

    # ========================================================
    # STATUS
    # ========================================================

    def get_calendar_status(self) -> Dict[str, Any]:

        matches = self.get_matches()

        scheduled = 0
        finished = 0

        for match in matches:

            status = str(
                match.get("status", "")
            ).lower()

            if status in {
                "scheduled",
                "upcoming",
                "pending",
            }:
                scheduled += 1

            elif status in {
                "finished",
                "completed",
            }:
                finished += 1

        return {
            "total_matches": len(matches),
            "scheduled": scheduled,
            "finished": finished,
            "database": "online",
        }


def get_match_manager() -> MatchManager:
    return MatchManager()


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:

        manager = MatchManager()
        status = manager.get_calendar_status()

        print("=" * 50)
        print(" FAJ MATCH MANAGER v3.0")
        print("=" * 50)
        print(f"Матчей:      {status['total_matches']}")
        print(f"Предстоящих: {status['scheduled']}")
        print(f"Завершённых: {status['finished']}")
        print("=" * 50)
        print("✅ Match Manager доступен")

    except Exception as exc:

        logger.exception(
            "Match Manager self-check failed"
        )

        print(
            f"❌ Ошибка Match Manager: {exc}"
        )
