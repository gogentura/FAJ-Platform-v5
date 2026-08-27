#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Team Mapping Service v1.0
============================================================

НАЗНАЧЕНИЕ:
    Сопоставление внутреннего имени команды FAJ
    с внешним API team_id.

АРХИТЕКТУРА:
    FAJ_CLUB_RATINGS
            ↓
    TeamMappingService
            ↓
    DataFootballAPI
            ↓
    external team_id

ВАЖНО:
    - SQLite НЕ используется
    - FAJDatabase НЕ используется
    - PredictionManager НЕ используется
    - паспорта НЕ изменяются
    - рейтинги НЕ изменяются
    - обучение НЕ изменяется
    - FAJ-прогноз НЕ изменяется
    - только READ-ONLY API mapping
    - используется локальный runtime-кэш

ИСТОЧНИК ИМЁН:
    FAJ Club Ratings / FAJ_CLUB_RATINGS

СЕРВИС НЕ СОХРАНЯЕТ ДАННЫЕ В БД.
============================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any

from app.parsers.data_football_api import (
    DataFootballAPI,
    get_data_football_api,
)


logger = logging.getLogger(__name__)


class TeamMappingService:
    """
    Read-only сервис сопоставления:

        FAJ team name → external API team_id
    """

    VERSION = "1.0"

    # Сопоставление FAJ лиг со странами для API поиска
    LEAGUE_COUNTRY_MAP = {
        "РПЛ": "Russia",
        "АПЛ": "England",
        "Ла Лига": "Spain",
        "Бундеслига": "Germany",
        "Серия А": "Italy",
        "Лига 1": "France",
        "Лига чемпионов": None,  # не используем страну
        "Чемпионшип": "England",
        "Эредивизи": "Netherlands",
    }

    def __init__(
        self,
        api: Optional[DataFootballAPI] = None,
    ):
        self.api = api or get_data_football_api()

        # Runtime cache.
        # Никакого SQLite / файлового сохранения.
        self._cache: Dict[str, int] = {}

        logger.info(
            "Team Mapping Service v%s initialized",
            self.VERSION,
        )

    # ========================================================
    # CACHE
    # ========================================================

    def _cache_key(
        self,
        team_name: str,
        league: Optional[str] = None,
    ) -> str:
        team_name = str(team_name or "").strip()
        league = str(league or "").strip()

        if league:
            return f"{league}:{team_name}"

        return team_name

    def clear_cache(self) -> None:
        """Очищает runtime-кэш."""
        self._cache.clear()

        logger.info("Team mapping cache cleared")

    # ========================================================
    # HELPERS
    # ========================================================

    @classmethod
    def _get_country(cls, league: Optional[str]) -> Optional[str]:
        """Преобразует FAJ лигу в страну для API поиска."""
        if not league:
            return None

        league = str(league).strip()

        return cls.LEAGUE_COUNTRY_MAP.get(league)

    # ========================================================
    # MAIN API
    # ========================================================

    def get_api_id(
        self,
        team_name: str,
        league: Optional[str] = None,
    ) -> Optional[int]:
        """
        Возвращает внешний API team_id.

        Сначала проверяется runtime-кэш.
        Если значения нет — выполняется read-only поиск
        через DataFootballAPI.
        """

        if not team_name:
            return None

        team_name = str(team_name).strip()

        if not team_name:
            return None

        cache_key = self._cache_key(
            team_name,
            league,
        )

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Преобразуем FAJ лигу в страну для API
        country = self._get_country(league)

        try:
            results = self.api.search_team(
                team_name,
                country=country,  # ✅ теперь country — это страна или None
            )

        except Exception as exc:
            logger.warning(
                "Team mapping API error | team=%s | league=%s | country=%s | error=%s",
                team_name,
                league,
                country,
                exc,
            )
            return None

        if not results:
            logger.warning(
                "External team not found | team=%s | league=%s | country=%s",
                team_name,
                league,
                country,
            )
            return None

        # API может вернуть разные структуры.
        for item in results:

            if not isinstance(item, dict):
                continue

            team_data = item.get("team", {})

            if not isinstance(team_data, dict):
                continue

            team_id = team_data.get("id")

            if team_id is None:
                continue

            try:
                team_id = int(team_id)
            except (TypeError, ValueError):
                continue

            self._cache[cache_key] = team_id

            logger.info(
                "TEAM MAPPED | FAJ=%s | league=%s | country=%s | API_ID=%s",
                team_name,
                league,
                country,
                team_id,
            )

            return team_id

        logger.warning(
            "API search returned no valid team ID | team=%s",
            team_name,
        )

        return None

    # ========================================================
    # EXPLICIT ALIAS
    # ========================================================

    def get_team_id(
        self,
        team_name: str,
        league: Optional[str] = None,
    ) -> Optional[int]:
        """Совместимый алиас для get_api_id()."""
        return self.get_api_id(
            team_name=team_name,
            league=league,
        )

    # ========================================================
    # CACHE INSPECTION
    # ========================================================

    def get_cached_mapping(self) -> Dict[str, int]:
        """
        Возвращает копию текущего runtime-кэша.
        """
        return dict(self._cache)

    # ========================================================
    # STATUS
    # ========================================================

    def status(self) -> Dict[str, Any]:
        return {
            "service": "Team Mapping Service",
            "version": self.VERSION,
            "status": "READY",
            "cached_teams": len(self._cache),
            "read_only": True,
        }


# ============================================================
# SINGLETON
# ============================================================

_default_mapping_service: Optional[TeamMappingService] = None


def get_team_mapping_service() -> TeamMappingService:
    global _default_mapping_service

    if _default_mapping_service is None:
        _default_mapping_service = TeamMappingService()

    return _default_mapping_service
