#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Passport Builder v1.1.1

РОЛЬ:
    Завод по созданию паспортов команд.

ИЗМЕНЕНИЯ v1.1.1:
    - Правильное создание v1 без ложного архива
    - save_passport() для первого создания, update_passport() для обновления
    - Учёт сезона
=====================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.passports.passport_manager import (
    TeamPassport,
    PassportMetadata,
    get_passport_manager)

logger = logging.getLogger(__name__)


class PassportBuilder:
    VERSION = "1.1.1"

    LEAGUE_DEFAULTS = {
        "RPL": {
            "attack": 70, "defense": 70, "control": 68,
            "efficiency": 68, "mentality": 72, "tempo": 65,
            "press": 68, "transition": 66, "coach": 70,
            "squad_strength": 68, "form": 70,
            "xg_for": 1.35, "xg_against": 1.35,
            "style_identity": "balanced"
        },
        "EPL": {
            "attack": 75, "defense": 72, "control": 72,
            "efficiency": 70, "mentality": 75, "tempo": 78,
            "press": 72, "transition": 70, "coach": 75,
            "squad_strength": 75, "form": 72,
            "xg_for": 1.45, "xg_against": 1.30,
            "style_identity": "attacking"
        },
        "La Liga": {
            "attack": 73, "defense": 70, "control": 78,
            "efficiency": 72, "mentality": 70, "tempo": 68,
            "press": 68, "transition": 65, "coach": 72,
            "squad_strength": 72, "form": 70,
            "xg_for": 1.40, "xg_against": 1.30,
            "style_identity": "possession"
        },
        "UCL": {
            "attack": 78, "defense": 75, "control": 75,
            "efficiency": 75, "mentality": 80, "tempo": 72,
            "press": 72, "transition": 70, "coach": 78,
            "squad_strength": 78, "form": 75,
            "xg_for": 1.50, "xg_against": 1.20,
            "style_identity": "balanced"
        }
    }

    def __init__(self):
        self.version = self.VERSION
        self.manager = get_passport_manager()
        logger.info(f"Passport Builder v{self.VERSION} initialized")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def build(
        self,
        team_id: int,
        team_name: str,
        league: str,
        season: str = "2026/27",
        source_data: Optional[Dict[str, Any]] = None,
        source_name: str = "manual",
        update_type: str = "initial"
    ) -> Optional[TeamPassport]:
        try:
            defaults = self.LEAGUE_DEFAULTS.get(league, self.LEAGUE_DEFAULTS["RPL"])

            if source_data:
                params = self._parse_source_data(source_data, defaults, league)
            else:
                params = defaults.copy()

            params = self._normalize_params(params)

            metadata = PassportMetadata(
                passport_version=1,
                manager_version=self.manager.VERSION,
                season=season,
                passport_status="ACTIVE",
                source_name=source_name,
                update_type=update_type,
                data_confidence=self._calculate_data_confidence(source_data),
                matches_analyzed=source_data.get("matches_analyzed", 0) if source_data else 0,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

            passport = TeamPassport(
                team_id=team_id,
                team_name=team_name,
                league=league,
                attack=params.get("attack", 70.0),
                defense=params.get("defense", 70.0),
                control=params.get("control", 70.0),
                efficiency=params.get("efficiency", 70.0),
                mentality=params.get("mentality", 70.0),
                tempo=params.get("tempo", 70.0),
                press=params.get("press", 70.0),
                transition=params.get("transition", 70.0),
                coach=params.get("coach", 70.0),
                squad_strength=params.get("squad_strength", 70.0),
                form=params.get("form", 70.0),
                xg_for=params.get("xg_for", 1.35),
                xg_against=params.get("xg_against", 1.35),
                injury_index=params.get("injury_index", 0.0),
                fatigue_index=params.get("fatigue_index", 0.0),
                transfer_index=params.get("transfer_index", 0.0),
                style_identity=params.get("style_identity", "balanced"),
                predictability=params.get("predictability", 70.0),
                big_match_factor=params.get("big_match_factor", 70.0),
                home_strength=params.get("home_strength", 70.0),
                away_strength=params.get("away_strength", 70.0),
                tournament_factor=params.get("tournament_factor", 70.0),
                opposition_quality=params.get("opposition_quality", 70.0),
                metadata=metadata
            )

            from app.passports.passport_validator import get_passport_validator
            validator = get_passport_validator()
            validation = validator.validate(passport)

            if not validation.is_valid:
                logger.warning(
                    f"Passport validation failed for {team_name}: {validation.errors}"
                )
                passport.metadata.data_confidence = max(
                    passport.metadata.data_confidence,
                    validation.quality_score * 0.5
                )

            # Правильное создание: save для первого раза, update для обновления
            existing = self.manager.get_passport(team_id, season)

            if existing:
                result = self.manager.update_passport(
                    passport,
                    f"Обновление паспорта ({source_name})"
                )
            else:
                result = self.manager.save_passport(passport)

            if result:
                logger.info(f"Passport built: {team_name} ({league}, {season})")
                return passport

            return None

        except Exception as e:
            logger.error(f"Build passport error: {e}")
            return None

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _normalize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = params.copy()

        for key, value in params.items():
            if key in ["xg_for", "xg_against", "injury_index", "fatigue_index", "transfer_index"]:
                continue
            if isinstance(value, (int, float)):
                result[key] = self._normalize(value)

        return result

    def _normalize(self, value: float, min_val: float = 0, max_val: float = 100) -> float:
        return round(max(min_val, min(max_val, value)), 1)

    def _parse_source_data(
        self,
        source_data: Dict[str, Any],
        defaults: Dict[str, Any],
        league: str
    ) -> Dict[str, Any]:
        params = defaults.copy()
        data_type = source_data.get("type", "stats")

        if data_type == "stats":
            stats = source_data.get("stats", {})
            params.update(self._parse_stats(stats, params, league))
        elif data_type == "squad":
            squad = source_data.get("squad", {})
            params.update(self._parse_squad(squad, params))
        elif data_type == "mixed":
            stats = source_data.get("stats", {})
            squad = source_data.get("squad", {})
            params.update(self._parse_stats(stats, params, league))
            params.update(self._parse_squad(squad, params))

        return params

    def _parse_stats(
        self,
        stats: Dict[str, Any],
        defaults: Dict[str, Any],
        league: str
    ) -> Dict[str, Any]:
        result = {}
        league_mean = 1.4

        goals_per_match = stats.get("goals_per_match")
        if goals_per_match:
            result["attack"] = defaults.get("attack", 70) + (goals_per_match - league_mean) * 10
            result["attack"] = self._normalize(result["attack"])

        goals_against = stats.get("goals_against_per_match")
        if goals_against:
            result["defense"] = defaults.get("defense", 70) - (goals_against - 1.2) * 10
            result["defense"] = self._normalize(result["defense"])

        possession = stats.get("possession")
        if possession:
            result["control"] = defaults.get("control", 70) + (possession - 50) * 0.3
            result["control"] = self._normalize(result["control"])

        points_last_5 = stats.get("points_last_5")
        if points_last_5:
            result["form"] = defaults.get("form", 70) + (points_last_5 - 6) * 3
            result["form"] = self._normalize(result["form"])

        xg_for = stats.get("xg_for")
        if xg_for:
            result["xg_for"] = round(xg_for, 2)

        xg_against = stats.get("xg_against")
        if xg_against:
            result["xg_against"] = round(xg_against, 2)

        wins_pct = stats.get("wins_pct")
        if wins_pct:
            result["mentality"] = defaults.get("mentality", 70) + (wins_pct - 0.4) * 50
            result["mentality"] = self._normalize(result["mentality"])

        avg_speed = stats.get("avg_speed")
        if avg_speed:
            result["tempo"] = defaults.get("tempo", 70) + (avg_speed - 50) * 0.3
            result["tempo"] = self._normalize(result["tempo"])

        return result

    def _parse_squad(
        self,
        squad: Dict[str, Any],
        defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = {}

        avg_rating = squad.get("avg_rating")
        if avg_rating:
            result["squad_strength"] = self._normalize(avg_rating)

        injured_players = squad.get("injured_players", 0)
        total_players = squad.get("total_players", 25)
        if total_players > 0:
            result["injury_index"] = round(injured_players / total_players, 2)

        depth = squad.get("depth_rating")
        if depth:
            current = result.get("squad_strength", defaults.get("squad_strength", 70))
            result["squad_strength"] = self._normalize((current + depth) / 2)

        return result

    def _calculate_data_confidence(
        self,
        source_data: Optional[Dict[str, Any]]
    ) -> float:
        if not source_data:
            return 0.3

        sources = source_data.get("sources", [])
        matches = source_data.get("matches_analyzed", 0)

        confidence = 0.3
        confidence += min(len(sources) * 0.15, 0.4)
        confidence += min(matches / 20 * 0.3, 0.3)

        return round(min(1.0, confidence), 2)


# ============================================================
# SINGLETON
# ============================================================

_default_builder: Optional[PassportBuilder] = None


def get_passport_builder() -> PassportBuilder:
    global _default_builder
    if _default_builder is None:
        _default_builder = PassportBuilder()
    return _default_builder


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ Passport Builder v1.1.1 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    builder = get_passport_builder()
    print(f"\n📊 Version: {builder.VERSION}")
    print(f"📊 Leagues: {list(builder.LEAGUE_DEFAULTS.keys())}")

    print("\n" + "=" * 60)
    print("✅ Passport Builder v1.1.1 готов к работе.")
    print("=" * 60)
