#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Team Registry Bridge
========================

Мост между:

    app/faj_club_ratings.py
                ↓
            SQLite
                ↓
        FAJ Predictor

ВАЖНО:

FAJ_CLUB_RATINGS является источником START_RATING
и списка команд.

SQLite хранит рабочие идентификаторы и связи.

Этот файл НЕ содержит собственную копию списка команд.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.faj_club_ratings import (
    FAJ_CLUB_RATINGS,
    get_all_teams,
    get_all_tournaments,
    get_team_rating,
)

from app.database import FAJDatabase, transaction

logger = logging.getLogger(__name__)


class TeamRegistryBridge:
    """
    Синхронизация FAJ Club Ratings ↔ SQLite.
    """

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()

    # ========================================================
    # COMPETITION
    # ========================================================

    def ensure_competition(
        self,
        tournament: str,
    ) -> int:
        """
        Получить или создать соревнование.
        """

        with transaction() as conn:

            row = conn.execute(
                """
                SELECT id
                FROM competitions
                WHERE name = ?
                ORDER BY id
                LIMIT 1
                """,
                (tournament,),
            ).fetchone()

            if row:
                return int(row["id"])

            cursor = conn.execute(
                """
                INSERT INTO competitions (
                    name,
                    country,
                    competition_type,
                    season,
                    active
                )
                VALUES (?, ?, ?, ?, 1)
                """,
                (
                    tournament,
                    self._country_for_tournament(tournament),
                    self._type_for_tournament(tournament),
                    "2026/27",
                ),
            )

            return int(cursor.lastrowid)

    # ========================================================
    # TEAM
    # ========================================================

    def ensure_team(
        self,
        team_name: str,
        tournament: str,
    ) -> int:
        """
        Получить настоящий SQLite ID команды.

        Сначала ищем существующую команду по имени.
        Это важно для команд, которые участвуют
        одновременно в чемпионате и Лиге чемпионов.
        """

        with transaction() as conn:

            # ------------------------------------------------
            # 1. Ищем уже существующую команду
            # ------------------------------------------------

            row = conn.execute(
                """
                SELECT id
                FROM teams
                WHERE name = ?
                ORDER BY id
                LIMIT 1
                """,
                (team_name,),
            ).fetchone()

            if row:
                team_id = int(row["id"])

            else:

                # --------------------------------------------
                # 2. Создаём команду
                # --------------------------------------------

                cursor = conn.execute(
                    """
                    INSERT INTO teams (
                        name,
                        league,
                        country,
                        active
                    )
                    VALUES (?, ?, ?, 1)
                    """,
                    (
                        team_name,
                        tournament,
                        self._country_for_tournament(tournament),
                    ),
                )

                team_id = int(cursor.lastrowid)

            # ------------------------------------------------
            # 3. Создаём соревнование
            # ------------------------------------------------

            competition_row = conn.execute(
                """
                SELECT id
                FROM competitions
                WHERE name = ?
                ORDER BY id
                LIMIT 1
                """,
                (tournament,),
            ).fetchone()

            if competition_row:
                competition_id = int(
                    competition_row["id"]
                )
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO competitions (
                        name,
                        country,
                        competition_type,
                        season,
                        active
                    )
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (
                        tournament,
                        self._country_for_tournament(
                            tournament
                        ),
                        self._type_for_tournament(
                            tournament
                        ),
                        "2026/27",
                    ),
                )

                competition_id = int(cursor.lastrowid)

            # ------------------------------------------------
            # 4. Связываем команду и соревнование
            # ------------------------------------------------

            conn.execute(
                """
                INSERT OR IGNORE INTO team_competitions (
                    team_id,
                    competition_id
                )
                VALUES (?, ?)
                """,
                (
                    team_id,
                    competition_id,
                ),
            )

            return team_id

    # ========================================================
    # TOURNAMENT
    # ========================================================

    def sync_tournament(
        self,
        tournament: str,
    ) -> Dict[str, Any]:
        """
        Синхронизировать весь турнир.
        """

        competition_id = self.ensure_competition(
            tournament
        )

        teams = get_all_teams(tournament)

        synced = []

        for team_name in teams:

            team_id = self.ensure_team(
                team_name,
                tournament,
            )

            synced.append(
                {
                    "id": team_id,
                    "name": team_name,
                    "tournament": tournament,
                    "rating": get_team_rating(
                        team_name,
                        tournament,
                    ),
                    "competition_id": competition_id,
                }
            )

        return {
            "tournament": tournament,
            "competition_id": competition_id,
            "teams": synced,
            "count": len(synced),
        }

    # ========================================================
    # ALL TOURNAMENTS
    # ========================================================

    def sync_all(self) -> Dict[str, Any]:
        """
        Полная синхронизация реестра FAJ.
        """

        result = {}

        for tournament in get_all_tournaments():

            result[tournament] = self.sync_tournament(
                tournament
            )

        return result

    # ========================================================
    # UI DATA
    # ========================================================

    def get_tournament_teams(
        self,
        tournament: str,
    ) -> List[Dict[str, Any]]:
        """
        Вернуть команды турнира с настоящими SQLite ID.
        """

        self.sync_tournament(tournament)

        competition = self.db.get_competitions()

        competition_id = None

        for item in competition:

            if item["name"] == tournament:

                competition_id = item["id"]
                break

        if competition_id is None:
            return []

        with self.db.get_connection() as conn:

            rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.name,
                    t.league,
                    t.country,
                    t.api_id,
                    t.logo_url,
                    t.active
                FROM teams t
                JOIN team_competitions tc
                    ON tc.team_id = t.id
                WHERE tc.competition_id = ?
                  AND t.active = 1
                ORDER BY t.name
                """,
                (competition_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _country_for_tournament(
        tournament: str,
    ) -> Optional[str]:

        mapping = {
            "РПЛ": "Россия",
            "АПЛ": "Англия",
            "Ла Лига": "Испания",
            "Лига чемпионов": "Европа",
        }

        return mapping.get(tournament)

    @staticmethod
    def _type_for_tournament(
        tournament: str,
    ) -> str:

        if tournament == "Лига чемпионов":
            return "cup"

        return "league"
