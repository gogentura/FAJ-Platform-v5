#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Result Manager
============================================================

НАЗНАЧЕНИЕ:
    Управление фактическими результатами матчей.

ПРИНЦИПЫ:
    - SQLite only
    - database.py — единственный источник схемы
    - никаких DELETE
    - никаких DROP
    - идемпотентная запись результата
    - предматчевые прогнозы НЕ изменяются
    - результат хранится как исторический факт
    - повторный импорт одного результата безопасен

ЦЕПОЧКА:

    Result Manager
          ↓
    match_results
          ↓
    факты матча
          ↓
    Learning Engine
          ↓
    обучение FAJ
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.database import get_connection


logger = logging.getLogger(__name__)


class ResultManager:
    """
    Менеджер фактических результатов матчей.

    Отвечает только за факт результата.
    Не занимается:
        - календарём;
        - прогнозами;
        - паспортами;
        - обучением;
        - удалением истории.
    """

    def __init__(self, db_path: str = "data/faj.db"):
        self.db_path = db_path

    # ========================================================
    # CONNECTION
    # ========================================================

    def _connection(self):
        """
        Получить соединение с БД через database.py.
        """
        return get_connection(self.db_path)

    # ========================================================
    # SAVE RESULT
    # ========================================================

    def save_result(
        self,
        match_id: int,
        home_goals: int,
        away_goals: int,
        status: str = "finished",
        result_date: Optional[str] = None,
        source: str = "result_manager",
        raw_data: Optional[str] = None,
    ) -> bool:
        """
        Сохраняет фактический результат матча.

        Повторная запись того же match_id:
            обновляет ФАКТИЧЕСКИЙ результат,
            но НЕ трогает predictions.

        Возвращает:
            True  — результат сохранён
            False — ошибка
        """

        if match_id is None:
            logger.error("match_id не указан")
            return False

        if home_goals is None or away_goals is None:
            logger.error(
                "Не указан счёт: match_id=%s",
                match_id,
            )
            return False

        try:
            home_goals = int(home_goals)
            away_goals = int(away_goals)
        except (TypeError, ValueError):
            logger.error(
                "Некорректный счёт: match_id=%s, %s:%s",
                match_id,
                home_goals,
                away_goals,
            )
            return False

        if home_goals < 0 or away_goals < 0:
            logger.error(
                "Отрицательный счёт недопустим: match_id=%s",
                match_id,
            )
            return False

        if result_date is None:
            result_date = datetime.utcnow().isoformat()

        conn = None

        try:
            conn = self._connection()
            cursor = conn.cursor()

            # ------------------------------------------------
            # Проверяем существование матча
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM matches
                WHERE id = ?
                """,
                (match_id,),
            )

            match = cursor.fetchone()

            if match is None:
                logger.error(
                    "Матч не найден: match_id=%s",
                    match_id,
                )
                conn.rollback()
                return False

            # ------------------------------------------------
            # Проверяем существующий результат
            # ------------------------------------------------

            cursor.execute(
                """
                SELECT id, home_goals, away_goals
                FROM match_results
                WHERE match_id = ?
                """,
                (match_id,),
            )

            existing = cursor.fetchone()

            if existing:
                existing_id = existing[0]

                # --------------------------------------------
                # Идемпотентность:
                # если результат тот же — ничего не делаем
                # --------------------------------------------

                if (
                    int(existing[1]) == home_goals
                    and int(existing[2]) == away_goals
                ):
                    logger.info(
                        "Результат уже существует: match_id=%s, %s:%s",
                        match_id,
                        home_goals,
                        away_goals,
                    )

                    conn.rollback()
                    return True

                # --------------------------------------------
                # Если источник прислал исправленный факт,
                # обновляем именно ФАКТ.
                #
                # Прогнозы НЕ затрагиваются.
                # --------------------------------------------

                cursor.execute(
                    """
                    UPDATE match_results
                    SET
                        home_goals = ?,
                        away_goals = ?,
                        status = ?,
                        result_date = ?,
                        source = ?,
                        raw_data = ?
                    WHERE id = ?
                    """,
                    (
                        home_goals,
                        away_goals,
                        status,
                        result_date,
                        source,
                        raw_data,
                        existing_id,
                    ),
                )

            else:

                # ------------------------------------------------
                # Первичная запись результата
                # ------------------------------------------------

                cursor.execute(
                    """
                    INSERT INTO match_results (
                        match_id,
                        home_goals,
                        away_goals,
                        status,
                        result_date,
                        source,
                        raw_data
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        match_id,
                        home_goals,
                        away_goals,
                        status,
                        result_date,
                        source,
                        raw_data,
                    ),
                )

            # ------------------------------------------------
            # Обновляем только факт в matches.
            #
            # Это НЕ прогноз.
            # ------------------------------------------------

            cursor.execute(
                """
                UPDATE matches
                SET
                    actual_home = ?,
                    actual_away = ?
                WHERE id = ?
                """,
                (
                    home_goals,
                    away_goals,
                    match_id,
                ),
            )

            conn.commit()

            logger.info(
                "Результат сохранён: match_id=%s, %s:%s",
                match_id,
                home_goals,
                away_goals,
            )

            return True

        except Exception:
            if conn is not None:
                conn.rollback()

            logger.exception(
                "Ошибка сохранения результата: match_id=%s",
                match_id,
            )

            return False

        finally:
            if conn is not None:
                conn.close()

    # ========================================================
    # GET RESULT
    # ========================================================

    def get_result(self, match_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить фактический результат матча.
        """

        conn = None

        try:
            conn = self._connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM match_results
                WHERE match_id = ?
                """,
                (match_id,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            columns = [
                description[0]
                for description in cursor.description
            ]

            return dict(zip(columns, row))

        except Exception:
            logger.exception(
                "Ошибка чтения результата: match_id=%s",
                match_id,
            )
            return None

        finally:
            if conn is not None:
                conn.close()

    # ========================================================
    # RESULT EXISTS
    # ========================================================

    def result_exists(self, match_id: int) -> bool:
        """
        Проверяет наличие фактического результата.
        """

        conn = None

        try:
            conn = self._connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 1
                FROM match_results
                WHERE match_id = ?
                LIMIT 1
                """,
                (match_id,),
            )

            return cursor.fetchone() is not None

        except Exception:
            logger.exception(
                "Ошибка проверки результата: match_id=%s",
                match_id,
            )
            return False

        finally:
            if conn is not None:
                conn.close()

    # ========================================================
    # GET FINISHED RESULTS
    # ========================================================

    def get_results(
        self,
        limit: Optional[int] = None,
    ) -> list[Dict[str, Any]]:
        """
        Получить сохранённые фактические результаты.
        """

        conn = None

        try:
            conn = self._connection()
            cursor = conn.cursor()

            sql = """
                SELECT *
                FROM match_results
                ORDER BY match_id
            """

            params = ()

            if limit is not None:
                sql += " LIMIT ?"
                params = (int(limit),)

            cursor.execute(sql, params)

            rows = cursor.fetchall()

            columns = [
                description[0]
                for description in cursor.description
            ]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

        except Exception:
            logger.exception("Ошибка получения результатов")
            return []

        finally:
            if conn is not None:
                conn.close()

    # ========================================================
    # GET UNPROCESSED RESULTS
    # ========================================================

    def get_unprocessed_results(self) -> list[Dict[str, Any]]:
        """
        Возвращает результаты, которые есть в match_results.

        Используется как основа для последующего
        обучения Learning Engine.
        """

        conn = None

        try:
            conn = self._connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT mr.*
                FROM match_results mr
                ORDER BY mr.match_id
                """
            )

            rows = cursor.fetchall()

            columns = [
                description[0]
                for description in cursor.description
            ]

            return [
                dict(zip(columns, row))
                for row in rows
            ]

        except Exception:
            logger.exception(
                "Ошибка получения результатов для обучения"
            )
            return []

        finally:
            if conn is not None:
                conn.close()


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================

_default_manager = ResultManager()


def save_result(
    match_id: int,
    home_goals: int,
    away_goals: int,
    status: str = "finished",
    result_date: Optional[str] = None,
    source: str = "result_manager",
    raw_data: Optional[str] = None,
) -> bool:
    """
    Удобная функция для других модулей FAJ.
    """

    return _default_manager.save_result(
        match_id=match_id,
        home_goals=home_goals,
        away_goals=away_goals,
        status=status,
        result_date=result_date,
        source=source,
        raw_data=raw_data,
    )


def get_result(match_id: int) -> Optional[Dict[str, Any]]:
    """
    Получить результат матча.
    """

    return _default_manager.get_result(match_id)


def result_exists(match_id: int) -> bool:
    """
    Проверить наличие результата.
    """

    return _default_manager.result_exists(match_id)
