#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Database Bridge
===================

Единая точка доступа страницы FAJ Predictor
к базе данных.

UI не должен знать детали SQLite.

UI говорит:

    "Создай матч"

    "Сохрани историю"

    "Сохрани статистику"

    "Сохрани прогноз"

А bridge работает с FAJDatabase.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.database import FAJDatabase

logger = logging.getLogger(__name__)


class FAJDatabaseBridge:

    def __init__(
        self,
        db: Optional[FAJDatabase] = None,
    ):
        self.db = db or FAJDatabase()

    # ========================================================
    # SESSION
    # ========================================================

    def create_session(
        self,
        competition_id: Optional[int],
        title: str,
        notes: Optional[str] = None,
    ) -> int:

        return self.db.create_analysis_session(
            competition_id=competition_id,
            title=title,
            notes=notes,
        )

    # ========================================================
    # ANALYSIS MATCH
    # ========================================================

    def create_analysis_match(
        self,
        session_id: int,
        home_team_id: int,
        away_team_id: int,
        match_date: Optional[str] = None,
    ) -> int:

        return self.db.add_analysis_match(
            session_id=session_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            match_date=match_date,
        )

    # ========================================================
    # SOURCE
    # ========================================================

    def create_source(
        self,
        analysis_match_id: int,
        team_id: int,
        source_url: Optional[str],
        parser_version: Optional[str],
        source_name: str = "Soccer365",
    ) -> int:

        return self.db.add_source(
            analysis_match_id=analysis_match_id,
            team_id=team_id,
            source_type="soccer365",
            source_name=source_name,
            source_url=source_url,
            parser_version=parser_version,
        )

    # ========================================================
    # HISTORICAL MATCH
    # ========================================================

    def save_historical_match(
        self,
        analysis_match_id: int,
        team_id: int,
        opponent_team_id: Optional[int],
        source_id: Optional[int],
        match_date: Optional[str],
        is_home: bool,
        goals_for: Optional[int],
        goals_against: Optional[int],
        result: Optional[str],
        external_match_id: Optional[str] = None,
        raw_metadata: Optional[Dict[str, Any]] = None,
    ) -> int:

        return self.db.save_historical_match(
            analysis_match_id=analysis_match_id,
            team_id=team_id,
            opponent_team_id=opponent_team_id,
            source_id=source_id,
            match_date=match_date,
            is_home=is_home,
            goals_for=goals_for,
            goals_against=goals_against,
            result=result,
            external_match_id=external_match_id,
            raw_metadata=raw_metadata,
        )

    # ========================================================
    # HISTORICAL STATS
    # ========================================================

    def save_historical_stats(
        self,
        historical_match_id: int,
        stats: Dict[str, Any],
    ) -> int:

        return self.db.save_historical_stats(
            historical_match_id=historical_match_id,
            stats=stats,
        )

    # ========================================================
    # PREDICTION
    # ========================================================

    def save_prediction(
        self,
        analysis_match_id: int,
        prediction: Dict[str, Any],
        model_version: str,
    ) -> int:

        return self.db.save_prediction(
            analysis_match_id=analysis_match_id,
            prediction=prediction,
            model_version=model_version,
        )

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:

        return self.db.get_status()
