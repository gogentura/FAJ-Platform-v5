#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
MATCH MANAGER
============================================================

НАЗНАЧЕНИЕ:
    Управление календарём матчей FAJ.

ОТВЕТСТВЕННОСТЬ:
    - создание/обновление матчей;
    - привязка матча к туру;
    - идемпотентное сохранение календаря;
    - получение матчей;
    - проверка существования матча;
    - получение матчей тура;
    - получение предстоящих/завершённых матчей.

НЕ ОТВЕЧАЕТ ЗА:
    - результаты матчей;
    - статистику после матча;
    - прогнозирование;
    - обучение;
    - паспорта;
    - изменение структуры БД;
    - удаление матчей.

ПРИНЦИП:
    database.py = единственный источник схемы.

    MatchManager НЕ работает с SQL-схемой напрямую.
    Все операции записи проходят через FAJDatabase.

ВАЖНЫЕ ПРАВИЛА:
    - SQLite only
    - никаких DELETE
    - никаких DROP
    - никаких очисток таблицы matches
    - повторный импорт календаря безопасен
    - существующий match_id сохраняется
============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


class MatchManager:
    """
    Основной менеджер календаря FAJ.
    """

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()

    # ========================================================
    # NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_match_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует входные данные матча.

        Ничего не удаляет из БД.
        Только приводит входной словарь к безопасному виду.
        """

        if not isinstance(data, dict):
            raise TypeError("Match data must be a dictionary")

        result = dict(data)

        # ----------------------------------------------------
        # REQUIRED FIELDS
        # ----------------------------------------------------

        if result.get("home_team_id") is None:
            raise ValueError("home_team_id is required")

        if result.get("away_team_id") is None:
            raise ValueError("away_team_id is required")

        if result.get("date") is None:
            raise ValueError("date is required")

        # ----------------------------------------------------
        # NORMALIZE DATE
        # ----------------------------------------------------

        result["date"] = str(result["date"]).strip()

        if not result["date"]:
            raise ValueError("date cannot be empty")

        # ----------------------------------------------------
        # DEFAULTS
        # ----------------------------------------------------

        result.setdefault("competition", "RPL")
        result.setdefault("status", "scheduled")
        result.setdefault("data_quality", 1.0)

        # ----------------------------------------------------
        # TEAM VALIDATION
        # ----------------------------------------------------

        if result["home_team_id"] == result["away_team_id"]:
            raise ValueError(
                "home_team_id and away_team_id cannot be identical"
            )

        return result

    # ========================================================
    # SAVE / UPSERT
    # ========================================================

    def save_match(self, data: Dict[str, Any]) -> int:
        """
        Идемпотентно сохраняет матч.

        Повторный импорт того же матча не создаёт новый матч,
        если database.py может идентифицировать его по match_uuid
        либо по:
            round_id
            home_team_id
            away_team_id
            date

        Возвращает существующий или новый match_id.
        """

        match_data = self._normalize_match_data(data)

        match_id = self.db.upsert_match(match_data)

        if not match_id:
            raise RuntimeError(
                "Database returned invalid match_id"
            )

        logger.info(
            "Match saved: id=%s, home=%s, away=%s, date=%s",
            match_id,
            match_data.get("home_team_id"),
            match_data.get("away_team_id"),
            match_data.get("date"),
        )

        return match_id

    # ========================================================
    # SAVE MANY
    # ========================================================

    def save_matches(
        self,
        matches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Идемпотентно сохраняет список матчей.

        ВАЖНО:
            Никакой предварительной очистки matches нет.

        Каждый матч сохраняется отдельно через database.py.

        Один ошибочный матч не должен приводить к удалению
        уже сохранённых матчей.

        Возвращает статистику операции.
        """

        if matches is None:
            raise ValueError("matches cannot be None")

        if not isinstance(matches, list):
            raise TypeError("matches must be a list")

        saved = 0
        failed = 0
        match_ids = []
        errors = []

        for index, match_data in enumerate(matches):

            try:
                match_id = self.save_match(match_data)

                saved += 1
                match_ids.append(match_id)

            except Exception as exc:
                failed += 1

                error = {
                    "index": index,
                    "error": str(exc),
                    "match": match_data,
                }

                errors.append(error)

                logger.error(
                    "Failed to save match at index %s: %s",
                    index,
                    exc,
                )

        return {
            "success": failed == 0,
            "total": len(matches),
            "saved": saved,
            "failed": failed,
            "match_ids": match_ids,
            "errors": errors,
        }

    # ========================================================
    # GET MATCH
    # ========================================================

    def get_match(self, match_id: int):
        """
        Получает матч по ID.

        FAJDatabase v12.1 пока не содержит отдельного
        get_match_by_id(), поэтому читаем через get_connection.
        Это READ-only операция.
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
        """
        Получает матч по внешнему UUID.
        """

        if not match_uuid:
            return None

        return self.db.get_match_by_uuid(match_uuid)

    # ========================================================
    # GET ROUND MATCHES
    # ========================================================

    def get_round_matches(
        self,
        round_id: int,
    ):
        """
        Возвращает все матчи тура.
        """

        if round_id is None:
            return []

        return self.db.get_matches(round_id=round_id)

    # ========================================================
    # GET ALL MATCHES
    # ========================================================

    def get_matches(self, round_id: Optional[int] = None):
        """
        Возвращает матчи.

        Если указан round_id — только матчи тура.
        Иначе — все матчи.
        """

        return self.db.get_matches(round_id=round_id)

    # ========================================================
    # EXISTENCE
    # ========================================================

    def match_exists(
        self,
        match_id: Optional[int] = None,
        match_uuid: Optional[str] = None,
    ) -> bool:
        """
        Проверяет существование матча.
        """

        if match_id is not None:
            return self.get_match(match_id) is not None

        if match_uuid:
            return self.get_match_by_uuid(match_uuid) is not None

        return False

    # ========================================================
    # ROUND COUNT
    # ========================================================

    def count_round_matches(
        self,
        round_id: int,
    ) -> int:
        """
        Количество матчей в туре.
        """

        if round_id is None:
            return 0

        matches = self.db.get_matches(round_id=round_id)

        return len(matches)

    # ========================================================
    # MATCH STATUS
    # ========================================================

    def get_scheduled_matches(
        self,
        round_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает запланированные матчи.
        """

        rows = self.db.get_matches(round_id=round_id)

        return [
            dict(row)
            for row in rows
            if str(row["status"]).lower()
            in ("scheduled", "upcoming", "pending")
        ]

    def get_finished_matches(
        self,
        round_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Возвращает завершённые матчи.

        Результат здесь только читается.
        Изменением результатов занимается result_manager.py.
        """

        rows = self.db.get_matches(round_id=round_id)

        return [
            dict(row)
            for row in rows
            if str(row["status"]).lower()
            in ("finished", "completed")
        ]

    # ========================================================
    # CALENDAR VALIDATION
    # ========================================================

    def validate_match(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверяет матч до записи в БД.

        Ничего не изменяет.
        """

        errors = []
        warnings = []

        if not isinstance(data, dict):
            return {
                "valid": False,
                "errors": ["Match data must be a dictionary"],
                "warnings": [],
            }

        home_team_id = data.get("home_team_id")
        away_team_id = data.get("away_team_id")
        round_id = data.get("round_id")
        date = data.get("date")

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
            warnings.append("round_id is missing")

        if not date:
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
        """
        Основная точка импорта календаря.

        Это НЕ полная синхронизация базы.

        Метод:
            - не удаляет существующие матчи;
            - не очищает matches;
            - не меняет результаты;
            - не запускает прогнозирование;
            - не запускает обучение.

        Он только сохраняет календарь через database.py.
        """

        if not isinstance(matches, list):
            raise TypeError("matches must be a list")

        validated = []
        rejected = []

        for index, match_data in enumerate(matches):

            validation = self.validate_match(match_data)

            if validation["valid"]:
                validated.append(match_data)
            else:
                rejected.append(
                    {
                        "index": index,
                        "match": match_data,
                        "errors": validation["errors"],
                    }
                )

        save_result = self.save_matches(validated)

        return {
            "success": (
                save_result["failed"] == 0
                and len(rejected) == 0
            ),
            "received": len(matches),
            "validated": len(validated),
            "rejected": len(rejected),
            "saved": save_result["saved"],
            "failed": save_result["failed"],
            "match_ids": save_result["match_ids"],
            "errors": save_result["errors"],
            "rejected_matches": rejected,
        }

    # ========================================================
    # DATABASE STATUS
    # ========================================================

    def get_calendar_status(self) -> Dict[str, Any]:
        """
        Возвращает состояние календаря.
        """

        total = self.db.get_table_count("matches")

        scheduled = len(self.get_scheduled_matches())
        finished = len(self.get_finished_matches())

        return {
            "total_matches": total,
            "scheduled": scheduled,
            "finished": finished,
            "database": "online",
        }


# ============================================================
# FACTORY
# ============================================================

def get_match_manager() -> MatchManager:
    """
    Возвращает экземпляр MatchManager.
    """

    return MatchManager()


# ============================================================
# SELF CHECK
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    try:
        manager = MatchManager()

        status = manager.get_calendar_status()

        print("============================================")
        print(" FAJ MATCH MANAGER v12.1")
        print("============================================")
        print(
            f"Матчей в БД: {status['total_matches']}"
        )
        print(
            f"Предстоящих: {status['scheduled']}"
        )
        print(
            f"Завершённых: {status['finished']}"
        )
        print("============================================")
        print("✅ Match Manager доступен")

    except Exception as exc:

        logger.exception(
            "Match Manager self-check failed"
        )

        print(
            f"❌ Ошибка Match Manager: {exc}"
        )
