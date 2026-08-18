#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1 — MEMORY HARDENED
Passport Manager v2.2
=====================================================

РОЛЬ:
    Управление паспортами команд.

ОТВЕТСТВЕННОСТЬ:
    - создание паспорта
    - получение текущего паспорта
    - история версий
    - обновление после матчей
    - обучение паспорта
    - расчёт FAJ Rating
    - расчёт Passport Confidence

ИСПРАВЛЕНИЯ v2.2:
    1. Убраны все прямые SQL-запросы — только через FAJDatabase
    2. get_current_passport() — через db.get_team_passport()
    3. create_passport() — через db.save_team_passport()
    4. Добавлен passport_uuid для уникальной идентификации версии
    5. get_passport_history() — через db.get_team_passport() с фильтрацией
    6. get_passport_versions() — через db.get_team_passport() с фильтрацией
"""

import logging
import re
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


class PassportManager:
    """Passport Manager v2.2 — Memory Hardened"""

    VERSION = "2.2"

    # ============================================================
    # GLOBAL SETTINGS
    # ============================================================

    DEFAULT_VALUE = 50.0
    POWER_MIN = 0.0
    POWER_MAX = 100.0
    LEARNING_RATE = 0.10

    # ============================================================
    # PARAMETER RANGES
    # ============================================================

    PARAM_RANGES = {
        "attack": (0, 100),
        "defense": (0, 100),
        "control": (0, 100),
        "tempo": (0, 100),
        "press": (0, 100),
        "transition": (0, 100),
        "finishing": (0, 100),
        "goalkeeper": (0, 100),
        "discipline": (0, 100),
        "squad_quality": (0, 100),
        "bench_quality": (0, 100),
        "coach_factor": (0, 100),
        "mental": (0, 100),
        "home_strength": (0, 100),
        "away_strength": (0, 100),
        "injury_factor": (0, 100),
        "key_player_loss": (0, 100),
        "passport_confidence": (0, 1),
        "league_adaptation": (0, 100),
        "form": (0, 100),
    }

    # ============================================================
    # SERVICE FIELDS
    # ============================================================

    SERVICE_FIELDS = {"_absolute_form"}

    # ============================================================
    # PASSPORT RATING WEIGHTS
    # ============================================================

    PASSPORT_RATING_WEIGHTS = {
        "attack": 0.17,
        "defense": 0.17,
        "control": 0.10,
        "tempo": 0.07,
        "press": 0.07,
        "transition": 0.06,
        "finishing": 0.06,
        "goalkeeper": 0.08,
        "squad_quality": 0.09,
        "coach_factor": 0.05,
        "mental": 0.05,
        "league_adaptation": 0.03,
    }

    # ============================================================
    # FINAL RATING WEIGHTS
    # ============================================================

    RATING_WEIGHTS = {
        "passport": 0.40,
        "results": 0.30,
        "opponent": 0.20,
        "form": 0.10,
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self._version_cache = {}

        logger.info("Passport Manager v%s initialized", self.VERSION)

    # ============================================================
    # GET CURRENT PASSPORT (через FAJDatabase)
    # ============================================================

    def get_current_passport(
        self,
        team_id: int,
        season_id: int
    ) -> Optional[Dict[str, Any]]:
        """Возвращает текущий паспорт команды через FAJDatabase."""
        return self.db.get_team_passport(team_id, season_id)

    # ============================================================
    # GET CURRENT BY NAME
    # ============================================================

    def get_current_passport_by_name(
        self,
        team_name: str,
        season_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Возвращает текущий паспорт по названию команды."""
        # Получаем team_id
        teams = self.db.get_teams()
        team_id = None

        for team in teams:
            if team["name"] == team_name:
                team_id = team["id"]
                break

        if team_id is None:
            logger.warning("Team not found: %s", team_name)
            return None

        # Определяем season_id
        if season_id is None:
            seasons = self.db.get_seasons()
            if not seasons:
                logger.warning("No seasons found")
                return None
            season_id = max(int(s["id"]) for s in seasons)

        return self.get_current_passport(team_id, season_id)

    # ============================================================
    # HISTORY (через FAJDatabase)
    # ============================================================

    def get_passport_history(
        self,
        team_id: int,
        season_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Возвращает историю паспортов команды."""
        # Получаем все версии паспорта
        passports = []
        version_num = 1

        while len(passports) < limit:
            passport = self.db.get_team_passport(
                team_id,
                season_id,
                version=f"v{version_num}.0"
            )
            if passport is None:
                break
            passports.append(passport)
            version_num += 1

        return passports

    # ============================================================
    # PASSPORT VERSIONS (через FAJDatabase)
    # ============================================================

    def get_passport_versions(
        self,
        team_id: int,
        season_id: int
    ) -> List[str]:
        """Возвращает список версий паспортов команды."""
        versions = []
        version_num = 1

        while True:
            passport = self.db.get_team_passport(
                team_id,
                season_id,
                version=f"v{version_num}.0"
            )
            if passport is None:
                break
            versions.append(f"v{version_num}.0")
            version_num += 1

        return versions

    # ============================================================
    # PUBLIC RATING (без изменений)
    # ============================================================

    def calculate_rating(
        self,
        passport: Dict[str, Any],
        results_strength: Optional[float] = None,
        opponent_strength: Optional[float] = None,
        form: Optional[float] = None
    ) -> float:
        """Единый публичный расчёт FAJ Rating."""
        passport_rating = self._calculate_passport_rating(passport)

        history_available = any(
            value is not None
            for value in (results_strength, opponent_strength, form)
        )

        if not history_available:
            return round(passport_rating, 1)

        results_value = (
            passport_rating
            if results_strength is None
            else self._normalize_rating_value(results_strength, passport_rating)
        )

        opponent_value = (
            passport_rating
            if opponent_strength is None
            else self._normalize_rating_value(opponent_strength, passport_rating)
        )

        form_value = (
            passport_rating
            if form is None
            else self._normalize_form_value(form, passport_rating)
        )

        rating = (
            passport_rating * self.RATING_WEIGHTS["passport"]
            + results_value * self.RATING_WEIGHTS["results"]
            + opponent_value * self.RATING_WEIGHTS["opponent"]
            + form_value * self.RATING_WEIGHTS["form"]
        )

        return round(max(0.0, min(100.0, rating)), 1)

    # ============================================================
    # PASSPORT RATING (без изменений)
    # ============================================================

    def _calculate_passport_rating(self, passport: Dict[str, Any]) -> float:
        score = 0.0

        for key, weight in self.PASSPORT_RATING_WEIGHTS.items():
            value = passport.get(key, self.DEFAULT_VALUE)
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = self.DEFAULT_VALUE
            value = max(self.POWER_MIN, min(self.POWER_MAX, value))
            score += value * weight

        return round(max(0.0, min(100.0, score)), 1)

    # ============================================================
    # CREATE PASSPORT (через FAJDatabase)
    # ============================================================

    def create_passport(
        self,
        team_id: int,
        season_id: int,
        data: Dict[str, Any],
        source: str = "manual"
    ) -> Optional[Dict[str, Any]]:
        """
        Создание НОВОЙ версии паспорта.

        data содержит АБСОЛЮТНЫЕ значения.
        Этот метод НЕ применяет LEARNING_RATE.
        """
        next_version = self._get_next_version(team_id, season_id)
        clamped_data = self._clamp_params(data)

        # Извлекаем служебные значения
        results_strength = data.get("results_strength")
        opponent_strength = data.get("opponent_strength")
        matches_count = data.get("matches_count", 0)
        form = clamped_data.get("form", self.DEFAULT_VALUE)

        # Расчёт рейтинга и confidence
        faj_rating = self.calculate_rating(
            clamped_data,
            results_strength=results_strength,
            opponent_strength=opponent_strength,
            form=form
        )

        created_at = data.get("created_at") or datetime.now().isoformat()
        passport_confidence = self._calculate_confidence(
            clamped_data,
            matches_count,
            created_at
        )

        # Добавляем служебные поля в данные
        passport_data = clamped_data.copy()
        passport_data["results_strength"] = results_strength
        passport_data["opponent_strength"] = opponent_strength
        passport_data["matches_count"] = matches_count
        passport_data["faj_rating"] = faj_rating
        passport_data["passport_confidence"] = passport_confidence
        passport_data["passport_uuid"] = str(uuid.uuid4())

        # Сохраняем через FAJDatabase
        passport_id = self.db.save_team_passport(
            team_id=team_id,
            season_id=season_id,
            data=passport_data,
            version=next_version,
            source=source
        )

        if passport_id is None:
            logger.error("Failed to create passport for team %s", team_id)
            return None

        logger.info(
            "Passport created | team=%s | season=%s | version=%s | rating=%.1f | source=%s | matches=%s",
            team_id, season_id, next_version, faj_rating, source, matches_count
        )

        return self.get_current_passport(team_id, season_id)

    # ============================================================
    # UPDATE PASSPORT — LEARNING (без изменений)
    # ============================================================

    def update_passport(
        self,
        team_id: int,
        season_id: int,
        changes: Dict[str, Any],
        source: str = "learning",
        opponent_rating: float = 70.0,
        tournament: str = "RPL",
        matches_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """Обновление паспорта через DELTA."""
        current = self.get_current_passport(team_id, season_id)

        if not current:
            logger.warning("No current passport for team %s. Cannot learn.", team_id)
            return None

        weighted_changes = self._apply_weighted_changes(changes, opponent_rating)
        new_data = current.copy()

        # SERVICE FIELDS
        absolute_form = weighted_changes.pop("_absolute_form", None)

        results_strength = weighted_changes.pop(
            "results_strength",
            current.get("results_strength")
        )
        opponent_strength = weighted_changes.pop(
            "opponent_strength",
            current.get("opponent_strength")
        )

        new_matches_count = matches_count

        # ABSOLUTE FORM
        if absolute_form is not None:
            try:
                new_data["form"] = self._clamp(float(absolute_form), "form")
            except (TypeError, ValueError):
                logger.warning("Invalid absolute form for team %s: %s", team_id, absolute_form)

        # DELTA
        for key, delta in weighted_changes.items():
            if key not in self.PARAM_RANGES or key == "faj_rating":
                continue

            try:
                old_value = float(new_data.get(key, self.DEFAULT_VALUE))
                delta = float(delta)
            except (TypeError, ValueError):
                continue

            learning_delta = delta * self.LEARNING_RATE
            new_value = old_value + learning_delta
            new_data[key] = self._clamp(new_value, key)

        # CONFIDENCE
        new_data["passport_confidence"] = self._calculate_confidence(
            new_data,
            new_matches_count,
            new_data.get("created_at", datetime.now().isoformat())
        )

        # RATING
        new_data["faj_rating"] = self.calculate_rating(
            new_data,
            results_strength=results_strength,
            opponent_strength=opponent_strength,
            form=new_data.get("form")
        )

        new_data["results_strength"] = results_strength
        new_data["opponent_strength"] = opponent_strength
        new_data["matches_count"] = new_matches_count

        return self.create_passport(team_id, season_id, new_data, source)

    # ============================================================
    # UPDATE AFTER MATCH (без изменений)
    # ============================================================

    def update_after_match(
        self,
        team_id: int,
        season_id: int,
        match_data: Dict[str, Any],
        opponent_rating: float = 70.0,
        tournament: str = "RPL",
        matches_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        current = self.get_current_passport(team_id, season_id)

        if not current:
            logger.warning("Cannot update team %s: passport does not exist.", team_id)
            return None

        changes = self._calculate_match_changes(match_data)

        if "form" in match_data:
            try:
                changes["_absolute_form"] = float(match_data["form"])
            except (TypeError, ValueError):
                pass

        if "results_strength" in match_data:
            changes["results_strength"] = match_data["results_strength"]

        changes["opponent_strength"] = opponent_rating

        return self.update_passport(
            team_id=team_id,
            season_id=season_id,
            changes=changes,
            source="match_update",
            opponent_rating=opponent_rating,
            tournament=tournament,
            matches_count=matches_count + 1
        )

    # ============================================================
    # APPLY WEIGHTED CHANGES (без изменений)
    # ============================================================

    def _apply_weighted_changes(
        self,
        changes: Dict[str, Any],
        opponent_rating: float
    ) -> Dict[str, Any]:
        try:
            opponent_rating = float(opponent_rating)
        except (TypeError, ValueError):
            opponent_rating = 70.0

        opponent_rating = max(0.0, min(100.0, opponent_rating))
        opponent_factor = 1.0 + (opponent_rating - 70.0) / 200.0
        opponent_factor = max(0.85, min(1.15, opponent_factor))

        weighted = {}

        for key, value in changes.items():
            if key in self.SERVICE_FIELDS:
                weighted[key] = value
                continue

            if key not in self.PARAM_RANGES or key == "faj_rating":
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            weighted[key] = value * opponent_factor

        return weighted

    # ============================================================
    # MATCH SIGNALS (без изменений)
    # ============================================================

    def _calculate_match_changes(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}

        try:
            goals_for = float(match_data.get("goals_for", 0))
            goals_against = float(match_data.get("goals_against", 0))
            xg_for = float(match_data.get("xg_for", goals_for))
            xg_against = float(match_data.get("xg_against", goals_against))
        except (TypeError, ValueError):
            logger.warning("Invalid match data")
            return {}

        attack_signal = (xg_for - 1.35) * 0.6 + (goals_for - 1.35) * 0.4
        changes["attack"] = attack_signal * 2.0

        defense_signal = (1.35 - xg_against) * 0.6 + (1.35 - goals_against) * 0.4
        changes["defense"] = defense_signal * 2.0

        changes["finishing"] = goals_for - xg_for

        if match_data.get("is_win", False):
            changes["mental"] = 1.0
        elif match_data.get("is_draw", False):
            changes["mental"] = 0.3
        else:
            changes["mental"] = -0.5

        return changes

    # ============================================================
    # CONFIDENCE (без изменений)
    # ============================================================

    def _calculate_confidence(
        self,
        passport: Dict[str, Any],
        matches_count: int,
        created_at: str
    ) -> float:
        required_fields = [
            "attack", "defense", "control", "tempo", "press",
            "transition", "finishing", "squad_quality", "coach_factor"
        ]

        filled = 0
        for field in required_fields:
            value = passport.get(field)
            if value is None:
                continue
            try:
                if float(value) != 0:
                    filled += 1
            except (TypeError, ValueError):
                pass

        data_quality = filled / len(required_fields)

        try:
            matches_count = int(matches_count)
        except (TypeError, ValueError):
            matches_count = 0

        matches_factor = min(0.4, matches_count * 0.004)

        try:
            created = datetime.fromisoformat(created_at)
            days_old = (datetime.now() - created).days
            freshness_factor = max(0.0, 1.0 - (days_old / 180.0))
        except Exception:
            freshness_factor = 0.8

        base_confidence = 0.2 + data_quality * 0.4
        confidence = base_confidence + matches_factor * freshness_factor

        return round(min(1.0, confidence), 4)

    # ============================================================
    # CLAMP (без изменений)
    # ============================================================

    def _clamp(self, value: float, key: str) -> float:
        if key in self.PARAM_RANGES:
            min_val, max_val = self.PARAM_RANGES[key]
            return max(min_val, min(max_val, value))
        return max(0.0, min(100.0, value))

    def _clamp_params(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in data.items():
            if key in self.PARAM_RANGES:
                try:
                    result[key] = self._clamp(float(value), key)
                except (TypeError, ValueError):
                    result[key] = self.DEFAULT_VALUE
            else:
                result[key] = value
        return result

    # ============================================================
    # VERSION (без изменений)
    # ============================================================

    def _get_next_version(self, team_id: int, season_id: int) -> str:
        versions = self.get_passport_versions(team_id, season_id)

        if not versions:
            return "v1.0"

        numbers = []
        for version in versions:
            match = re.search(r"v(\d+)", str(version))
            if match:
                numbers.append(int(match.group(1)))

        if not numbers:
            return "v1.0"

        next_num = max(numbers) + 1
        return f"v{next_num}.0"

    # ============================================================
    # RATING HELPERS (без изменений)
    # ============================================================

    def _normalize_rating_value(self, value: Any, fallback: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(0.0, min(100.0, value))

    def _normalize_form_value(self, value: Any, fallback: float) -> float:
        if value is None:
            return fallback
        try:
            value = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(0.0, min(100.0, value))


# ================================================================
# SINGLETON
# ================================================================

_default_manager: Optional[PassportManager] = None


def get_passport_manager(db: Optional[FAJDatabase] = None) -> PassportManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PassportManager(db)
    return _default_manager
