#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Passport Manager v2.3.3 (SQLite Edition)

РОЛЬ:
    Управление паспортами команд через SQLite.
    Хранитель памяти FAJ Platform.

ИЗМЕНЕНИЯ v2.3.3:
    - Полная совместимость с SQLite (без PostgreSQL)
    - row_value() helper для безопасного чтения
    - Добавлен save_learning_event() для learning_history
    - Исправлена сезонность (season в запросах)
    - Исправлен _load_from_db() для SQLite Row
    - Исправлен get_all_passports() для tuple-строк
=====================================================
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field, asdict

from app.database import get_db

logger = logging.getLogger(__name__)


# ============================================================
# SQLITE HELPER
# ============================================================

def row_value(row, key: str, default=None):
    """
    Универсальное чтение SQLite Row
    Поддерживает как dict-подобные row, так и tuple
    """
    if row is None:
        return default

    try:
        if hasattr(row, 'keys'):
            return row[key] if key in row.keys() else default
        elif hasattr(row, '__getitem__') and not hasattr(row, 'keys'):
            if hasattr(row, 'description'):
                for idx, desc in enumerate(row.description):
                    if desc[0] == key:
                        return row[idx]
            return default
        else:
            return default
    except Exception:
        return default


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PassportMetadata:
    passport_version: int = 1
    manager_version: str = "2.3.3"

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_update_date: Optional[str] = None
    last_validation_date: Optional[str] = None

    season: str = "2026/27"
    passport_status: str = "ACTIVE"

    data_confidence: float = 0.0
    api_confidence: float = 0.0
    expert_confidence: float = 0.0

    matches_analyzed: int = 0
    last_match_date: Optional[str] = None

    source_name: str = "manual"
    update_type: str = "initial"


@dataclass
class TeamPassport:
    team_id: int
    team_name: str
    league: str

    attack: float = 70.0
    defense: float = 70.0
    control: float = 70.0
    efficiency: float = 70.0
    mentality: float = 70.0
    tempo: float = 70.0
    press: float = 70.0
    transition: float = 70.0

    coach: float = 70.0
    squad_strength: float = 70.0
    form: float = 70.0

    xg_for: float = 1.35
    xg_against: float = 1.35

    injury_index: float = 0.0
    fatigue_index: float = 0.0
    transfer_index: float = 0.0

    style_identity: str = "balanced"
    predictability: float = 70.0
    big_match_factor: float = 70.0
    home_strength: float = 70.0
    away_strength: float = 70.0
    tournament_factor: float = 70.0
    opposition_quality: float = 70.0

    metadata: PassportMetadata = field(default_factory=PassportMetadata)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_rating(self) -> float:
        return calculate_faj_rating_from_passport(self)

    def get_quality(self) -> float:
        return calculate_passport_quality(self)


# ============================================================
# MAIN CLASS
# ============================================================

class PassportManager:
    VERSION = "2.3.3"

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

    def get_passport(self, team_id: int, season: Optional[str] = None) -> Optional[TeamPassport]:
        if team_id in self._cache:
            return self._cache[team_id]

        passport = self._load_from_db(team_id, season)
        if passport:
            self._cache[team_id] = passport
        return passport

    def get_passport_by_name(self, team_name: str, season: Optional[str] = None) -> Optional[TeamPassport]:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM teams WHERE name = ?", (team_name,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        team_id = row[0] if isinstance(row, (tuple, list)) else row.get("id", 0)
        conn.close()

        return self.get_passport(team_id, season)

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
            if isinstance(row, (tuple, list)):
                data = {
                    "id": row[0],
                    "name": row[1],
                    "league": row[2],
                    "season": row[3],
                    "passport_status": row[4],
                    "attack": row[5],
                    "defense": row[6],
                    "control": row[7],
                    "form": row[8],
                    "xg_for": row[9],
                    "xg_against": row[10],
                    "passport_quality": row[11],
                    "faj_rating": row[12],
                    "data_confidence": row[13],
                    "passport_version": row[14],
                    "updated_at": row[15],
                    "matches_analyzed": row[16],
                    "source_name": row[17],
                    "update_type": row[18],
                    "last_validation_date": row[19]
                }
            else:
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

        result = []
        for row in rows:
            if isinstance(row, (tuple, list)):
                result.append({})
            else:
                result.append(dict(row))

        return result

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

        result = []
        for row in rows:
            if isinstance(row, (tuple, list)):
                data = {
                    "version": row[0],
                    "attack": row[1],
                    "defense": row[2],
                    "control": row[3],
                    "form": row[4],
                    "faj_rating": row[5],
                    "passport_quality": row[6],
                    "change_reason": row[7],
                    "created_at": row[8]
                }
            else:
                data = dict(row)
            result.append(data)

        return result

    def compare_versions(
        self,
        team_id: int,
        version_old: int,
        version_new: int
    ) -> Dict[str, Any]:
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

        old_data = rows[0] if isinstance(rows[0], (tuple, list)) else dict(rows[0])
        new_data = rows[1] if isinstance(rows[1], (tuple, list)) else dict(rows[1])

        if isinstance(old_data, (tuple, list)):
            old = {
                "version": old_data[0],
                "attack": old_data[1],
                "defense": old_data[2],
                "control": old_data[3],
                "form": old_data[4],
                "faj_rating": old_data[5],
                "passport_quality": old_data[6],
                "change_reason": old_data[7],
                "created_at": old_data[8]
            }
            new = {
                "version": new_data[0],
                "attack": new_data[1],
                "defense": new_data[2],
                "control": new_data[3],
                "form": new_data[4],
                "faj_rating": new_data[5],
                "passport_quality": new_data[6],
                "change_reason": new_data[7],
                "created_at": new_data[8]
            }
        else:
            old = old_data
            new = new_data

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

        result = []
        for row in rows:
            if isinstance(row, (tuple, list)):
                data = {
                    "name": row[0],
                    "season": row[1],
                    "passport_version": row[2],
                    "passport_status": row[3],
                    "updated_at": row[4],
                    "faj_rating": row[5],
                    "passport_quality": row[6],
                    "source_name": row[7],
                    "update_type": row[8],
                    "change_reason": row[9],
                    "last_validation_date": row[10]
                }
            else:
                data = dict(row)
            result.append(data)

        return result

    # ============================================================
    # SAVE / UPDATE
    # ============================================================

    def save_passport(self, passport: TeamPassport) -> bool:
        try:
            quality = passport.get_quality()
            rating = passport.get_rating()

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT team_id FROM team_passports WHERE team_id = ? AND season = ?",
                (passport.team_id, passport.metadata.season)
            )
            exists = cursor.fetchone() is not None

            if exists:
                cursor.execute(
                    """
                    UPDATE team_passports SET
                        passport_status=?,
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
                    WHERE team_id = ? AND season = ?
                    """,
                    (
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
                        passport.team_id,
                        passport.metadata.season
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

            self._cache[passport.team_id] = passport
            return True

        except Exception as e:
            logger.error(f"Save passport error: {e}")
            return False

    def update_passport(
        self,
        passport: TeamPassport,
        change_reason: Optional[str] = None
    ) -> Optional[TeamPassport]:
        try:
            old_passport = self.get_passport(passport.team_id, passport.metadata.season)

            new_version = 1
            if old_passport:
                new_version = old_passport.metadata.passport_version + 1
                old_passport.metadata.passport_status = "ARCHIVED"
                self.save_passport(old_passport)

            passport.metadata.passport_version = new_version
            passport.metadata.passport_status = "ACTIVE"
            passport.metadata.updated_at = datetime.now().isoformat()
            passport.metadata.last_validation_date = datetime.now().isoformat()

            if not self.save_passport(passport):
                return None

            self._save_history(passport, old_passport, change_reason)

            self._cache[passport.team_id] = passport

            logger.info(
                f"Passport updated: {passport.team_name} "
                f"(v{new_version}, {passport.metadata.season}, {passport.metadata.passport_status})"
            )

            return passport

        except Exception as e:
            logger.error(f"Update passport error: {e}")
            return None

    # ============================================================
    # HISTORY
    # ============================================================

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
    # LEARNING HISTORY
    # ============================================================

    def save_learning_event(
        self,
        team_id: int,
        event_type: str,
        old_value: float,
        new_value: float,
        reason: str,
        field_name: Optional[str] = None
    ) -> bool:
        """
        Сохранение события обучения в learning_history

        Args:
            team_id: ID команды
            event_type: тип события (rating, attack, defense, etc.)
            old_value: старое значение
            new_value: новое значение
            reason: причина изменения
            field_name: название поля (опционально)

        Returns:
            bool: успешно ли сохранено
        """
        try:
            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO learning_history (
                    team_id, event_type, field_name,
                    old_value, new_value, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    team_id,
                    event_type,
                    field_name or event_type,
                    old_value,
                    new_value,
                    reason,
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
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получение событий обучения"""
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

        result = []
        for row in rows:
            if isinstance(row, (tuple, list)):
                result.append({})
            else:
                result.append(dict(row))

        return result

    # ============================================================
    # STATUS & DIAGNOSTICS
    # ============================================================

    def passport_status(self, team_id: int, season: Optional[str] = None) -> Dict[str, Any]:
        passport = self.get_passport(team_id, season)
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

    def get_rating(self, team_id: int, season: Optional[str] = None) -> Optional[float]:
        passport = self.get_passport(team_id, season)
        return passport.get_rating() if passport else None

    def get_quality(self, team_id: int, season: Optional[str] = None) -> Optional[float]:
        passport = self.get_passport(team_id, season)
        return passport.get_quality() if passport else None

    def clear_cache(self) -> None:
        self._cache.clear()
        logger.info("Cache cleared")

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _load_from_db(self, team_id: int, season: Optional[str] = None) -> Optional[TeamPassport]:
        try:
            conn = get_db()
            cursor = conn.cursor()

            if season:
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
                    WHERE t.id = ? AND p.season = ?
                    """,
                    (team_id, season)
                )
            else:
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
                    ORDER BY p.created_at DESC
                    LIMIT 1
                    """,
                    (team_id,)
                )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            passport_version = row_value(row, "passport_version", 1)
            manager_version = row_value(row, "manager_version", self.VERSION)
            created_at = row_value(row, "created_at", datetime.now().isoformat())
            updated_at = row_value(row, "updated_at", datetime.now().isoformat())
            source_update_date = row_value(row, "source_update_date")
            last_validation_date = row_value(row, "last_validation_date")
            passport_season = row_value(row, "season", "2026/27")
            passport_status = row_value(row, "passport_status", "ACTIVE")
            data_confidence = row_value(row, "data_confidence", 0.0)
            api_confidence = row_value(row, "api_confidence", 0.0)
            expert_confidence = row_value(row, "expert_confidence", 0.0)
            matches_analyzed = row_value(row, "matches_analyzed", 0)
            last_match_date = row_value(row, "last_match_date")
            source_name = row_value(row, "source_name", "manual")
            update_type = row_value(row, "update_type", "initial")

            metadata = PassportMetadata(
                passport_version=passport_version,
                manager_version=manager_version,
                created_at=created_at,
                updated_at=updated_at,
                source_update_date=source_update_date,
                last_validation_date=last_validation_date,
                season=passport_season,
                passport_status=passport_status,
                data_confidence=data_confidence,
                api_confidence=api_confidence,
                expert_confidence=expert_confidence,
                matches_analyzed=matches_analyzed,
                last_match_date=last_match_date,
                source_name=source_name,
                update_type=update_type
            )

            return TeamPassport(
                team_id=row_value(row, "id", team_id),
                team_name=row_value(row, "name", ""),
                league=row_value(row, "league", ""),
                attack=row_value(row, "attack", 70.0),
                defense=row_value(row, "defense", 70.0),
                control=row_value(row, "control", 70.0),
                efficiency=row_value(row, "efficiency", 70.0),
                mentality=row_value(row, "mentality", 70.0),
                tempo=row_value(row, "tempo", 70.0),
                press=row_value(row, "press", 70.0),
                transition=row_value(row, "transition", 70.0),
                coach=row_value(row, "coach", 70.0),
                squad_strength=row_value(row, "squad_strength", 70.0),
                form=row_value(row, "form", 70.0),
                xg_for=row_value(row, "xg_for", 1.35),
                xg_against=row_value(row, "xg_against", 1.35),
                injury_index=row_value(row, "injury_index", 0.0),
                fatigue_index=row_value(row, "fatigue_index", 0.0),
                transfer_index=row_value(row, "transfer_index", 0.0),
                style_identity=row_value(row, "style_identity", "balanced"),
                predictability=row_value(row, "predictability", 70.0),
                big_match_factor=row_value(row, "big_match_factor", 70.0),
                home_strength=row_value(row, "home_strength", 70.0),
                away_strength=row_value(row, "away_strength", 70.0),
                tournament_factor=row_value(row, "tournament_factor", 70.0),
                opposition_quality=row_value(row, "opposition_quality", 70.0),
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Load from DB error: {e}")
            return None


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
    print("⚽ Passport Manager v2.3.3 — САМОТЕСТИРОВАНИЕ")
    print("=" * 60)

    manager = get_passport_manager()

    print(f"\n📊 Version: {manager.VERSION}")
    print(f"📊 Rating Weights: {manager.RATING_WEIGHTS}")

    print("\n📋 Dashboard Summary:")
    summary = manager.dashboard_summary()
    print(f"  Команды: {summary.get('teams', 0)}")
    print(f"  Средний рейтинг: {summary.get('average_rating', 0)}")

    print("\n" + "=" * 60)
    print("✅ Passport Manager v2.3.3 готов к работе.")
    print("=" * 60)
