#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Match Bridge
================

Главный мост управления матчем.

Связывает:

    FAJ Predictor
         ↓
    Team Registry
         ↓
    Database
         ↓
    Soccer365
         ↓
    FAJ Brain

Это основа будущего Match Manager.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.database import FAJDatabase
from app.services.team_registry_bridge import (
    TeamRegistryBridge,
)
from app.services.faj_database_bridge import (
    FAJDatabaseBridge,
)


class FAJMatchBridge:

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ):

        self.db = db or FAJDatabase()

        self.registry = TeamRegistryBridge(
            self.db
        )

        self.database = FAJDatabaseBridge(
            self.db
        )

    # ========================================================
    # PREPARE TOURNAMENT
    # ========================================================

    def prepare_tournament(
        self,
        tournament: str,
    ) -> Dict[str, Any]:

        return self.registry.sync_tournament(
            tournament
        )

    # ========================================================
    # GET TEAMS
    # ========================================================

    def get_teams(
        self,
        tournament: str,
    ):

        return self.registry.get_tournament_teams(
            tournament
        )

    # ========================================================
    # PREPARE MATCH
    # ========================================================

    def prepare_match(
        self,
        tournament: str,
        home_team_id: int,
        away_team_id: int,
    ) -> Dict[str, Any]:

        if home_team_id == away_team_id:
            raise ValueError(
                "Хозяева и гости не могут быть одной командой."
            )

        competition_id = (
            self.registry.ensure_competition(
                tournament
            )
        )

        session_id = (
            self.database.create_session(
                competition_id=competition_id,
                title=(
                    f"FAJ | "
                    f"{tournament}"
                ),
                notes=(
                    "Персональная "
                    "аналитическая сессия FAJ."
                ),
            )
        )

        analysis_match_id = (
            self.database.create_analysis_match(
                session_id=session_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
            )
        )

        return {
            "tournament": tournament,
            "competition_id": competition_id,
            "session_id": session_id,
            "analysis_match_id": analysis_match_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
        }

    # ========================================================
    # STATUS
    # ========================================================

    def status(self):

        return self.database.status()
