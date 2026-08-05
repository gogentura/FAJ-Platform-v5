#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Passport Manager v2.3.2

РОЛЬ:
    Управление паспортами команд через SQLite.
    Хранитель памяти FAJ Platform.

ИЗМЕНЕНИЯ v2.3.2:
    - Сезон вынесен в паспорт (не в поиск команды)
    - Исправлен compare_passports() для FAJ Rating
    - Добавлен passport_status (DRAFT, ACTIVE, OUTDATED, ARCHIVED)
    - Добавлен last_validation_date
    - Подготовка к passport_id (в будущем)
=====================================================
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field, asdict

from app.database import get_db

logger = logging.getLogger(__name__)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PassportMetadata:
    """Метаданные паспорта"""
    # Версии
    passport_version: int = 1
    manager_version: str = "2.3.2"

    # Временные метки
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_update_date: Optional[str] = None
    last_validation_date: Optional[str] = None

    # Сезон (принадлежит паспорту, а не команде)
    season: str = "2026/27"

    # Статус паспорта
    passport_status: str = "DRAFT"  # DRAFT, ACTIVE, OUTDATED, ARCHIVED

    # Доверие
    data_confidence: float = 0.0
    api_confidence: float = 0.0
    expert_confidence: float = 0.0

    # Статистика
    matches_analyzed: int = 0
    last_match_date: Optional[str] = None

    # Источник
    source_name: str = "manual"
    update_type: str = "initial"  # initial, api_update, manual_edit, learning_update


@dataclass
class TeamPassport:
    """
    Полный паспорт команды FAJ v12
    """
    team_id: int
    team_name: str
    league: str

    # Игровые параметры (0-100)
    attack: float = 70.0
    defense: float = 70.0
    control: float = 70.0
    efficiency: float = 70.0
    mentality: float = 70.0
    tempo: float = 70.0
    press: float = 70.0
    transition: float = 70.0

    # Тренерский штаб
    coach: float = 70.0

    # Состав и форма
    squad_strength: float = 70.0
    form: float = 70.0

    # Ожидаемые голы
    xg_for: float = 1.35
    xg_against: float = 1.35

    # Физическое состояние (0-1)
    injury_index: float = 0.0
    fatigue_index: float = 0.0

    # Трансферы (0-1)
    transfer_index: float = 0.0

    # FAJ Advanced Layer
    style_identity: str = "balanced"
    predictability: float = 70.0
    big_match_factor: float = 70.0
    home_strength: float = 70.0
    away_strength: float = 70.0
    tournament_factor: float = 70.0
    opposition_quality: float = 70.0

    # Метаданные
    metadata: PassportMetadata = field(default_factory=PassportMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь (для Streamlit)"""
        return asdict(self)

    def get_rating(self) -> float:
        return calculate_faj_rating_from_passport(self)

    def get_quality(self) -> float:
        return calculate_passport_quality(self)


# ============================================================
# MAIN CLASS
# ============================================================

class PassportManager:
    """
    Passport Manager v2.3.2
    Хранитель памяти FAJ Platform
    """

    VERSION = "2.3.2"

    # Веса для FAJ Rating
    RATING_WEIGHTS = {
        "attack": 0.15,
        "defense": 0.15,
        "control": 0.10,
        "efficiency": 0.10,
        "mentality": 0.10,
        "tempo": 0.05,
        "press": 0.05,
        "transition": 0.05,
        "coach": 0.05,
        "form": 0.05,
        "predictability": 0.05,
        "big_match_factor": 0.03,
        "home_strength": 0.02,
        "opposition_quality": 0.05
    }

    STYLES = ["balanced", "attacking", "defensive", "counter", "possession", "direct"]
    UPDATE_TYPES = ["initial", "api_update", "manual_edit", "learning_update"]
    PASSPORT_STATUSES = ["DRAFT", "ACTIVE", "OUTDATED", "ARCHIVED"]

    def __init__(self):
        self.version = self.VERSION
        self._cache: Dict[int, TeamPassport] = {}
        logger.info(f"Passport Manager v{self.VERSION} initialized")

    # ============================================================
    # GET
    # ============================================================

    def get_passport(self, team_id: int) -> Optional[TeamPassport]:
        if team_id in self._cache:
            return self._cache[team_id]

        passport = self._load_from_db(team_id)
        if passport:
            self._cache[team_id] = passport
        return passport

    def get_passport_by_name(self, team_name: str, season: Optional[str] = None) -> Optional[TeamPassport]:
        """Поиск паспорта по названию команды и сезону (сезон в паспорте)"""
        conn = get_db()
        cursor = conn.cursor()

        # Сначала получаем team_id
        cursor.execute("SELECT id FROM teams WHERE name = ?", (team_name,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        team_id = row[0]

        # Затем ищем паспорт с нужным сезоном
        if season:
            cursor.execute(
                "SELECT team_id FROM team_passports WHERE team_id = ? AND season = ?",
                (team_id, season)
            )
        else:
            cursor.execute(
                "SELECT team_id FROM team_passports WHERE team_id = ?",
                (team_id,)
            )

        passport_row = cursor.fetchone()
        conn.close()

        if not passport_row:
            return None

        return self.get_passport(passport_row[0])

    def get_all_passports(self, league: Optional[str] = None, season: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()

        query = """
            SELECT t.id, t.name, t.league,
                   p.season, p.passport_status,
                   p.attack, p.defense, p.control, p.form,
                   p.xg_for, p.xg_against,
                   p.passport_quality, p.faj_rating,
                   p.data_confidence, p.passport_version,
                   p.updated_at, p.matches_analyzed,
                   p.source_name, p.update_type,
                   p.last_validation_date
            FROM teams t
            LEFT JOIN team_passports p ON t.id = p.team_id
            WHERE 1=1
        """
        params = []

        if league:
            query += " AND t.league = ?"
            params.append(league)

        if season:
            query += " AND p.season = ?"
            params.append(season)

        query += " ORDER BY p.faj_rating DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        result = []
        for row in rows:
            data = dict(row)
            quality = data.get("passport_quality", 0.0)

            if quality >= 0.8:
                data["status"] = "FULL"
            elif quality >= 0.5:
                data["status"] = "PARTIAL"
            else:
                data["status"] = "MINIMAL"

            result.append(data)

        return result

    def get_passport_history(self, team_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM passport_history
            WHERE team_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (team_id, limit)
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_versions(self, team_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT version, attack, defense, control, form,
                   faj_rating, passport_quality,
                   change_reason, created_at
            FROM passport_history
            WHERE team_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (team_id, limit)
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def compare_versions(
        self,
        team_id: int,
        version_old: int,
        version_new: int
    ) -> Dict[str, Any]:
        """Сравнение двух версий паспорта из истории"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT version, attack, defense, control, form,
                   faj_rating, passport_quality, change_reason, created_at
            FROM passport_history
            WHERE team_id = ? AND version IN (?, ?)
            ORDER BY version
            """,
            (team_id, version_old, version_new)
        )

        rows = cursor.fetchall()
        conn.close()

        if len(rows) != 2:
            return {"error": "Версии не найдены"}

        old = dict(rows[0])
        new = dict(rows[1])

        changes = {}
        for field in ["attack", "defense", "control", "form", "faj_rating"]:
            old_val = old.get(field, 0)
            new_val = new.get(field, 0)
            diff = round(new_val - old_val, 1)
            changes[field] = {
                "old": old_val,
                "new": new_val,
                "diff": diff
            }

        return {
            "team_id": team_id,
            "version_old": version_old,
            "version_new": version_new,
            "changes": changes,
            "reason": new.get("change_reason", "Обновление паспорта"),
            "date": new.get("created_at")
        }

    def compare_passports(
        self,
        old_passport: TeamPassport,
        new_passport: TeamPassport
    ) -> Dict[str, Any]:
        """Сравнение двух объектов паспортов (исправлено)"""
        changes = {}
        fields = ["attack", "defense", "control", "form"]

        for field in fields:
            old_val = getattr(old_passport, field, 0)
            new_val = getattr(new_passport, field, 0)
            diff = round(new_val - old_val, 1)
            changes[field] = {
                "old": old_val,
                "new": new_val,
                "diff": diff
            }

        # FAJ Rating отдельно (метод, не поле)
        old_rating = old_passport.get_rating()
        new_rating = new_passport.get_rating()
        changes["faj_rating"] = {
            "old": old_rating,
            "new": new_rating,
            "diff": round(new_rating - old_rating, 1)
        }

        return {
            "team_name": new_passport.team_name,
            "version_old": old_passport.metadata.passport_version,
            "version_new": new_passport.metadata.passport_version,
            "changes": changes
        }

    def get_recent_updates(self, limit: int = 20) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.name, p.season, p.passport_version, p.passport_status,
                   p.updated_at, p.faj_rating, p.passport_quality,
                   p.source_name, p.update_type,
                   p.change_reason, p.last_validation_date
            FROM team_passports p
            JOIN teams t ON p.team_id = t.id
            ORDER BY p.updated_at DESC
            LIMIT ?
            """,
            (limit,)
        )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ============================================================
    # UPDATE (с версионированием)
    # ============================================================

    def update_passport(
        self,
        passport: TeamPassport,
        change_reason: Optional[str] = None
    ) -> Optional[TeamPassport]:
        try:
            old_passport = self.get_passport(passport.team_id)

            new_version = 1
            if old_passport:
                new_version = old_passport.metadata.passport_version + 1
                # Старый паспорт становится ARCHIVED
                old_passport.metadata.passport_status = "ARCHIVED"
                self._save_to_db(old_passport)

            passport.metadata.passport_version = new_version
            passport.metadata.passport_status = "ACTIVE"
            passport.metadata.updated_at = datetime.now().isoformat()
            passport.metadata.last_validation_date = datetime.now().isoformat()

            if not self._save_to_db(passport):
                return None

            self._save_history(passport, old_passport, change_reason)

            self._cache[passport.team_id] = passport

            logger.info(
                f"Passport updated: {passport.team_name} "
                f"(v{new_version}, {passport.metadata.passport_status})"
            )

            return passport

        except Exception as e:
            logger.error(f"Update passport error: {e}")
            return None

    # ============================================================
    # LEARNING
    # ============================================================

    def save_learning_event(
        self,
        team_id: int,
        event_type: str,
        old_value: float,
        new_value: float,
        reason: str,
        field_name: Optional[str] = None,
        match_id: Optional[int] = None
    ) -> bool:
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO learning_history (
                    team_id, event_type, field_name,
                    old_value, new_value, reason, match_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    event_type,
                    field_name or event_type,
                    old_value,
                    new_value,
                    reason,
                    match_id,
                    datetime.now().isoformat()
                )
            )

            conn.commit()
            conn.close()

            logger.info(f"Learning event saved: {event_type} for team {team_id}")
            return True

        except Exception as e:
            logger.error(f"Save learning event error: {e}")
            return False

    def get_learning_events(
        self,
        team_id: Optional[int] = None,
        match_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        conn = get_db()
        cursor = conn.cursor()

        if team_id:
            cursor.execute(
                """
                SELECT *
                FROM learning_history
                WHERE team_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (team_id, limit)
            )
        elif match_id:
            cursor.execute(
                """
                SELECT *
                FROM learning_history
                WHERE match_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (match_id, limit)
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM learning_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ============================================================
    # STATUS & DIAGNOSTICS
    # ============================================================

    def passport_status(self, team_id: int) -> Dict[str, Any]:
        passport = self.get_passport(team_id)
        if not passport:
            return {"exists": False, "message": "Паспорт не найден"}

        quality = passport.get_quality()
        rating = passport.get_rating()

        if quality >= 0.8:
            status = "FULL"
        elif quality >= 0.5:
            status = "PARTIAL"
        else:
            status = "MINIMAL"

        return {
            "exists": True,
            "team_name": passport.team_name,
            "season": passport.metadata.season,
            "passport_status": passport.metadata.passport_status,
            "status": status,
            "quality": quality,
            "rating": rating,
            "version": passport.metadata.passport_version,
            "style": passport.style_identity,
            "source": passport.metadata.source_name,
            "update_type": passport.metadata.update_type,
            "matches_analyzed": passport.metadata.matches_analyzed,
            "data_confidence": passport.metadata.data_confidence,
            "api_confidence": passport.metadata.api_confidence,
            "expert_confidence": passport.metadata.expert_confidence,
            "last_updated": passport.metadata.updated_at,
            "last_validated": passport.metadata.last_validation_date,
            "last_match": passport.metadata.last_match_date
        }

    def dashboard_summary(self, season: Optional[str] = None) -> Dict[str, Any]:
        passports = self.get_all_passports(season=season)

        if not passports:
            return {
                "teams": 0,
                "average_rating": 0,
                "full_passports": 0,
                "partial_passports": 0,
                "active_passports": 0,
                "updated": datetime.now().isoformat()
            }

        ratings = [p.get("faj_rating", 0) for p in passports if p.get("faj_rating")]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

        full = sum(1 for p in passports if p.get("status") == "FULL")
        partial = sum(1 for p in passports if p.get("status") == "PARTIAL")
        active = sum(1 for p in passports if p.get("passport_status") == "ACTIVE")

        return {
            "teams": len(passports),
            "average_rating": avg_rating,
            "full_passports": full,
            "partial_passports": partial,
            "active_passports": active,
            "updated": datetime.now().isoformat()
        }

    def get_rating(self, team_id: int) -> Optional[float]:
        passport = self.get_passport(team_id)
        return passport.get_rating() if passport else None

    def get_quality(self, team_id: int) -> Optional[float]:
        passport = self.get_passport(team_id)
        return passport.get_quality() if passport else None

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.info("Cache cleared")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _load_from_db(self, team_id: int) -> Optional[TeamPassport]:
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT t.id, t.name, t.league,
                       p.season, p.passport_status,
                       p.attack, p.defense, p.control, p.efficiency,
                       p.mentality, p.tempo, p.press, p.transition,
                       p.coach, p.squad_strength, p.form,
                       p.xg_for, p.xg_against,
                       p.injury_index, p.fatigue_index, p.transfer_index,
                       p.style_identity,
                       p.predictability, p.big_match_factor,
                       p.home_strength, p.away_strength,
                       p.tournament_factor, p.opposition_quality,
                       p.passport_quality, p.faj_rating,
                       p.matches_analyzed, p.data_confidence,
                       p.api_confidence, p.expert_confidence,
                       p.passport_version, p.manager_version,
                       p.source_name, p.update_type,
                       p.source_update_date, p.last_match_date,
                       p.last_validation_date,
                       p.created_at, p.updated_at
                FROM teams t
                LEFT JOIN team_passports p ON t.id = p.team_id
                WHERE t.id = ?
                """,
                (team_id,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            metadata = PassportMetadata(
                passport_version=row.get("passport_version", 1),
                manager_version=row.get("manager_version", self.VERSION),
                created_at=row.get("created_at") or datetime.now().isoformat(),
                updated_at=row.get("updated_at") or datetime.now().isoformat(),
                source_update_date=row.get("source_update_date"),
                last_validation_date=row.get("last_validation_date"),
                season=row.get("season", "2026/27"),
                passport_status=row.get("passport_status", "DRAFT"),
                data_confidence=row.get("data_confidence", 0.0),
                api_confidence=row.get("api_confidence", 0.0),
                expert_confidence=row.get("expert_confidence", 0.0),
                matches_analyzed=row.get("matches_analyzed", 0),
                last_match_date=row.get("last_match_date"),
                source_name=row.get("source_name", "manual"),
                update_type=row.get("update_type", "initial")
            )

            return TeamPassport(
                team_id=row["id"],
                team_name=row["name"],
                league=row["league"],
                attack=row.get("attack", 70.0),
                defense=row.get("defense", 70.0),
                control=row.get("control", 70.0),
                efficiency=row.get("efficiency", 70.0),
                mentality=row.get("mentality", 70.0),
                tempo=row.get("tempo", 70.0),
                press=row.get("press", 70.0),
                transition=row.get("transition", 70.0),
                coach=row.get("coach", 70.0),
                squad_strength=row.get("squad_strength", 70.0),
                form=row.get("form", 70.0),
                xg_for=row.get("xg_for", 1.35),
                xg_against=row.get("xg_against", 1.35),
                injury_index=row.get("injury_index", 0.0),
                fatigue_index=row.get("fatigue_index", 0.0),
                transfer_index=row.get("transfer_index", 0.0),
                style_identity=row.get("style_identity", "balanced"),
                predictability=row.get("predictability", 70.0),
                big_match_factor=row.get("big_match_factor", 70.0),
                home_strength=row.get("home_strength", 70.0),
                away_strength=row.get("away_strength", 70.0),
                tournament_factor=row.get("tournament_factor", 70.0),
                opposition_quality=row.get("opposition_quality", 70.0),
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Load from DB error: {e}")
            return None

    def _save_to_db(self, passport: TeamPassport) -> bool:
        try:
            quality = passport.get_quality()
            rating = passport.get_rating()

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT team_id FROM team_passports WHERE team_id = ?",
                (passport.team_id,)
            )
            exists = cursor.fetchone() is not None

            if exists:
                cursor.execute(
                    """
                    UPDATE team_passports SET
                        season=?, passport_status=?,
                        attack=?, defense=?, control=?, efficiency=?,
                        mentality=?, tempo=?, press=?, transition=?,
                        coach=?, squad_strength=?, form=?,
                        xg_for=?, xg_against=?,
                        injury_index=?, fatigue_index=?, transfer_index=?,
                        style_identity=?,
                        predictability=?, big_match_factor=?,
                        home_strength=?, away_strength=?,
                        tournament_factor=?, opposition_quality=?,
                        passport_quality=?, faj_rating=?,
                        matches_analyzed=?, data_confidence=?,
                        api_confidence=?, expert_confidence=?,
                        passport_version=?, manager_version=?,
                        source_name=?, update_type=?,
                        source_update_date=?, last_match_date=?,
                        last_validation_date=?,
                        updated_at=?
                    WHERE team_id = ?
                    """,
                    (
                        passport.metadata.season,
                        passport.metadata.passport_status,
                        passport.attack, passport.defense, passport.control, passport.efficiency,
                        passport.mentality, passport.tempo, passport.press, passport.transition,
                        passport.coach, passport.squad_strength, passport.form,
                        passport.xg_for, passport.xg_against,
                        passport.injury_index, passport.fatigue_index, passport.transfer_index,
                        passport.style_identity,
                        passport.predictability, passport.big_match_factor,
                        passport.home_strength, passport.away_strength,
                        passport.tournament_factor, passport.opposition_quality,
                        quality, rating,
                        passport.metadata.matches_analyzed, passport.metadata.data_confidence,
                        passport.metadata.api_confidence, passport.metadata.expert_confidence,
                        passport.metadata.passport_version, self.VERSION,
                        passport.metadata.source_name, passport.metadata.update_type,
                        passport.metadata.source_update_date, passport.metadata.last_match_date,
                        passport.metadata.last_validation_date,
                        passport.metadata.updated_at,
                        passport.team_id
                    )
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO team_passports (
                        team_id, season, passport_status,
                        attack, defense, control, efficiency,
                        mentality, tempo, press, transition,
                        coach, squad_strength, form,
                        xg_for, xg_against,
                        injury_index, fatigue_index, transfer_index,
                        style_identity,
                        predictability, big_match_factor,
                        home_strength, away_strength,
                        tournament_factor, opposition_quality,
                        passport_quality, faj_rating,
                        matches_analyzed, data_confidence,
                        api_confidence, expert_confidence,
                        passport_version, manager_version,
                        source_name, update_type,
                        source_update_date, last_match_date,
                        last_validation_date,
                        created_at, updated_at
                    ) VALUES (
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?
                    )
                    """,
                    (
                        passport.team_id,
                        passport.metadata.season,
                        passport.metadata.passport_status,
                        passport.attack, passport.defense, passport.control, passport.efficiency,
                        passport.mentality, passport.tempo, passport.press, passport.transition,
                        passport.coach, passport.squad_strength, passport.form,
                        passport.xg_for, passport.xg_against,
                        passport.injury_index, passport.fatigue_index, passport.transfer_index,
                        passport.style_identity,
                        passport.predictability, passport.big_match_factor,
                        passport.home_strength, passport.away_strength,
                        passport.tournament_factor, passport.opposition_quality,
                        quality, rating,
                        passport.metadata.matches_analyzed, passport.metadata.data_confidence,
                        passport.metadata.api_confidence, passport.metadata.expert_confidence,
                        passport.metadata.passport_version, self.VERSION,
                        passport.metadata.source_name, passport.metadata.update_type,
                        passport.metadata.source_update_date, passport.metadata.last_match_date,
                        passport.metadata.last_validation_date,
                        passport.metadata.created_at, passport.metadata.updated_at
                    )
                )

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Save to DB error: {e}")
            return False

    def _save_history(
        self,
        passport: TeamPassport,
        old_passport: Optional[TeamPassport],
        change_reason: Optional[str] = None
    ) -> bool:
        try:
            conn = get_db()
            cursor = conn.cursor()

            reason = change_reason or f"Обновление паспорта (v{passport.metadata.passport_version})"

            cursor.execute(
                """
                INSERT INTO passport_history (
                    team_id, version,
                    attack, defense, control, form,
                    faj_rating, passport_quality,
                    change_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    passport.team_id,
                    passport.metadata.passport_version,
                    passport.attack,
                    passport.defense,
                    passport.control,
                    passport.form,
                    passport.get_rating(),
                    passport.get_quality(),
                    reason,
                    datetime.now().isoformat()
                )
            )

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Save history error: {e}")
            return False


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def calculate_faj_rating_from_passport(passport: TeamPassport) -> float:
    weights = PassportManager.RATING_WEIGHTS

    rating = (
        passport.attack * weights["attack"] +
        passport.defense * weights["defense"] +
        passport.control * weights["control"] +
        passport.efficiency * weights["efficiency"] +
        passport.mentality * weights["mentality"] +
        passport.tempo * weights["tempo"] +
        passport.press * weights["press"] +
        passport.transition * weights["transition"] +
        passport.coach * weights["coach"] +
        passport.form * weights["form"] +
        passport.predictability * weights["predictability"] +
        passport.big_match_factor * weights["big_match_factor"] +
        passport.home_strength * weights["home_strength"] +
        passport.opposition_quality * weights["opposition_quality"]
    )

    return round(rating, 1)


def calculate_passport_quality(passport: TeamPassport) -> float:
    fields = [
        "attack", "defense", "control", "efficiency",
        "mentality", "tempo", "press", "transition",
        "coach", "squad_strength", "form",
        "xg_for", "xg_against"
    ]

    filled = 0
    for field in fields:
        value = getattr(passport, field, None)
        if value is not None and value != 0:
            filled += 1

    return round(filled / len(fields), 2)


# ============================================================
# SINGLETON
# ============================================================

_default_manager: Optional[PassportManager] = None


def get_passport_manager() -> PassportManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PassportManager()
    return _default_manager


# ============================================================
# SELF-TEST
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("⚽ Passport Manager v2.3.2 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    manager = get_passport_manager()

    print(f"\n📊 Version: {manager.VERSION}")
    print(f"📊 Rating Weights: {manager.RATING_WEIGHTS}")
    print(f"📊 Styles: {manager.STYLES}")
    print(f"📊 Update Types: {manager.UPDATE_TYPES}")
    print(f"📊 Passport Statuses: {manager.PASSPORT_STATUSES}")

    print("\n📋 Dashboard Summary:")
    summary = manager.dashboard_summary()
    print(f"  Команды: {summary.get('teams', 0)}")
    print(f"  Средний рейтинг: {summary.get('average_rating', 0)}")
    print(f"  Полных паспортов: {summary.get('full_passports', 0)}")
    print(f"  Активных паспортов: {summary.get('active_passports', 0)}")

    print("\n📋 Последние обновления:")
    updates = manager.get_recent_updates(5)
    for u in updates:
        print(f"  - {u.get('name')} (v{u.get('passport_version')}, {u.get('passport_status')}) — {u.get('updated_at')[:10]}")

    print("\n" + "=" * 60)
    print("✅ Passport Manager v2.3.2 готов к работе.")
    print("=" * 60)
