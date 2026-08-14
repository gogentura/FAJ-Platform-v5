#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Passport Manager v2.1
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

ИСПРАВЛЕНИЯ v2.1:
    1. SERVICE_FIELS — убраны results_strength, opponent_strength, matches_count
    2. Эти поля теперь хранятся в team_passports как отдельные колонки
    3. matches_count передаётся как аргумент, а не через changes
    4. _absolute_form остаётся как служебное поле

ВАЖНО v2.0:

    1. PassportManager НЕ создаёт таблицы.
       Схема полностью принадлежит database.py.

    2. Sync и Learning разделены.

    3. create_passport()
       принимает АБСОЛЮТНЫЕ значения.

    4. update_passport()
       принимает DELTA и применяет LEARNING_RATE.

    5. Абсолютная форма хранится как абсолютное
       значение через _absolute_form.

    6. results_strength и opponent_strength —
       служебные значения для расчёта рейтинга.
       Они НЕ являются параметрами паспорта, но ХРАНЯТСЯ в БД.

    7. Служебные поля никогда не проходят
       через opponent_factor.

    8. FAJ Rating всегда пересчитывается
       из актуального паспорта.

    9. Повторная синхронизация исходного паспорта
       не должна выполнять обучение.

   10. SQLite / Streamlit Community Cloud.

=====================================================
"""

import logging
import re

from typing import Dict, Any, Optional
from datetime import datetime

from app.database import FAJDatabase


logger = logging.getLogger(__name__)


class PassportManager:

    """
    Passport Manager v2.1
    """

    VERSION = "2.1"

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
    # SERVICE FIELDS (исправлено v2.1)
    # ============================================================

    # Только _absolute_form — временное служебное поле,
    # которое не хранится в БД.
    #
    # results_strength, opponent_strength, matches_count
    # теперь хранятся в team_passports как отдельные колонки.
    SERVICE_FIELDS = {
        "_absolute_form",
    }

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

    def __init__(
        self,
        db: Optional[FAJDatabase] = None
    ):

        self.db = db or FAJDatabase()

        self._version_cache = {}

        self._check_migration()

        logger.info(
            "Passport Manager v%s initialized",
            self.VERSION
        )

    # ============================================================
    # SCHEMA CHECK
    # ============================================================

    def _check_migration(self) -> None:
        """
        Только проверка существующей схемы.

        PassportManager НЕ создаёт таблицы.
        """

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'team_passports'
            """)

            if cursor.fetchone() is None:

                raise RuntimeError(
                    "FAJ database schema error: "
                    "table 'team_passports' does not exist. "
                    "Fix database.py before using PassportManager."
                )

            cursor.execute("""
                PRAGMA table_info(team_passports)
            """)

            columns = {
                row[1]
                for row in cursor.fetchall()
            }

            required_columns = {
                "team_id",
                "season_id",
                "attack",
                "defense",
                "control",
                "tempo",
                "press",
                "transition",
                "finishing",
                "goalkeeper",
                "discipline",
                "squad_quality",
                "bench_quality",
                "coach_factor",
                "mental",
                "home_strength",
                "away_strength",
                "injury_factor",
                "key_player_loss",
                "league_adaptation",
                "form",
                "passport_confidence",
                "faj_rating",
                "version",
                "source",
                "created_at",
                "results_strength",    # НОВОЕ v2.1
                "opponent_strength",   # НОВОЕ v2.1
                "matches_count",       # НОВОЕ v2.1
            }

            missing = required_columns - columns

            if missing:

                raise RuntimeError(
                    "FAJ database schema error: "
                    "team_passports is missing columns: "
                    f"{sorted(missing)}"
                )

            logger.info(
                "Passport schema check completed"
            )

        finally:

            conn.close()

    # ============================================================
    # GET CURRENT PASSPORT
    # ============================================================

    def get_current_passport(
        self,
        team_id: int,
        season_id: int
    ) -> Optional[Dict[str, Any]]:

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT *
                FROM team_passports

                WHERE team_id = ?
                  AND season_id = ?

                ORDER BY
                    CAST(
                        REPLACE(version, 'v', '')
                        AS FLOAT
                    ) DESC

                LIMIT 1
            """, (
                team_id,
                season_id,
            ))

            row = cursor.fetchone()

            return dict(row) if row else None

        finally:

            conn.close()

    # ============================================================
    # GET CURRENT BY NAME
    # ============================================================

    def get_current_passport_by_name(
        self,
        team_name: str,
        season_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT id
                FROM teams
                WHERE name = ?
                LIMIT 1
            """, (team_name,))

            row = cursor.fetchone()

            if not row:

                logger.warning(
                    "Team not found: %s",
                    team_name
                )

                return None

            team_id = row[0]

        finally:

            conn.close()

        if season_id is None:

            seasons = self.db.get_seasons()

            if not seasons:

                logger.warning(
                    "No seasons found"
                )

                return None

            season_id = max(
                int(s["id"])
                for s in seasons
            )

        return self.get_current_passport(
            team_id,
            season_id
        )

    # ============================================================
    # HISTORY
    # ============================================================

    def get_passport_history(
        self,
        team_id: int,
        season_id: int,
        limit: int = 10
    ) -> list:

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT *
                FROM team_passports

                WHERE team_id = ?
                  AND season_id = ?

                ORDER BY
                    CAST(
                        REPLACE(version, 'v', '')
                        AS FLOAT
                    ) DESC

                LIMIT ?
            """, (
                team_id,
                season_id,
                limit,
            ))

            rows = cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            conn.close()

    # ============================================================
    # PASSPORT VERSIONS
    # ============================================================

    def get_passport_versions(
        self,
        team_id: int,
        season_id: int
    ) -> list:

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT version
                FROM team_passports

                WHERE team_id = ?
                  AND season_id = ?

                ORDER BY
                    CAST(
                        REPLACE(version, 'v', '')
                        AS FLOAT
                    ) DESC
            """, (
                team_id,
                season_id,
            ))

            rows = cursor.fetchall()

            return [
                row[0]
                for row in rows
            ]

        finally:

            conn.close()

    # ============================================================
    # PUBLIC RATING
    # ============================================================

    def calculate_rating(
        self,
        passport: Dict[str, Any],
        results_strength: Optional[float] = None,
        opponent_strength: Optional[float] = None,
        form: Optional[float] = None
    ) -> float:
        """
        Единый публичный расчёт FAJ Rating.
        """

        passport_rating = (
            self._calculate_passport_rating(
                passport
            )
        )

        history_available = any(
            value is not None
            for value in (
                results_strength,
                opponent_strength,
                form,
            )
        )

        if not history_available:

            return round(
                passport_rating,
                1
            )

        results_value = (
            passport_rating
            if results_strength is None
            else self._normalize_rating_value(
                results_strength,
                passport_rating
            )
        )

        opponent_value = (
            passport_rating
            if opponent_strength is None
            else self._normalize_rating_value(
                opponent_strength,
                passport_rating
            )
        )

        form_value = (
            passport_rating
            if form is None
            else self._normalize_form_value(
                form,
                passport_rating
            )
        )

        rating = (

            passport_rating
            * self.RATING_WEIGHTS["passport"]

            +

            results_value
            * self.RATING_WEIGHTS["results"]

            +

            opponent_value
            * self.RATING_WEIGHTS["opponent"]

            +

            form_value
            * self.RATING_WEIGHTS["form"]
        )

        return round(
            max(
                0.0,
                min(
                    100.0,
                    rating
                )
            ),
            1
        )

    # ============================================================
    # PASSPORT RATING
    # ============================================================

    def _calculate_passport_rating(
        self,
        passport: Dict[str, Any]
    ) -> float:

        score = 0.0

        for key, weight in (
            self.PASSPORT_RATING_WEIGHTS.items()
        ):

            value = passport.get(
                key,
                self.DEFAULT_VALUE
            )

            try:

                value = float(value)

            except (
                TypeError,
                ValueError
            ):

                value = self.DEFAULT_VALUE

            value = max(
                self.POWER_MIN,
                min(
                    self.POWER_MAX,
                    value
                )
            )

            score += value * weight

        return round(
            max(
                0.0,
                min(
                    100.0,
                    score
                )
            ),
            1
        )

    # ============================================================
    # CREATE PASSPORT (исправлено v2.1)
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

        ВАЖНО:

        data содержит АБСОЛЮТНЫЕ значения.

        Этот метод НЕ применяет LEARNING_RATE.

        ИСПРАВЛЕНО v2.1:
            results_strength, opponent_strength, matches_count
            теперь сохраняются в team_passports.
        """

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:

            next_version = (
                self._get_next_version(
                    team_id,
                    season_id
                )
            )

            clamped_data = (
                self._clamp_params(data)
            )

            # ----------------------------------------------------
            # Служебные значения (теперь хранятся в БД)
            # ----------------------------------------------------

            results_strength = (
                data.get("results_strength")
            )

            opponent_strength = (
                data.get("opponent_strength")
            )

            matches_count = (
                data.get("matches_count", 0)
            )

            form = clamped_data.get(
                "form",
                self.DEFAULT_VALUE
            )

            # ----------------------------------------------------
            # RATING
            # ----------------------------------------------------

            faj_rating = self.calculate_rating(
                clamped_data,
                results_strength=results_strength,
                opponent_strength=opponent_strength,
                form=form
            )

            # ----------------------------------------------------
            # CONFIDENCE
            # ----------------------------------------------------

            created_at = (
                data.get(
                    "created_at"
                )
                or datetime.now().isoformat()
            )

            passport_confidence = (
                self._calculate_confidence(
                    clamped_data,
                    matches_count,
                    created_at
                )
            )

            # ----------------------------------------------------
            # INSERT (с новыми колонками)
            # ----------------------------------------------------

            cursor.execute("""
                INSERT INTO team_passports (

                    team_id,
                    season_id,

                    attack,
                    defense,
                    control,

                    tempo,
                    press,
                    transition,

                    finishing,
                    goalkeeper,

                    discipline,

                    squad_quality,
                    bench_quality,

                    coach_factor,
                    mental,

                    home_strength,
                    away_strength,

                    injury_factor,
                    key_player_loss,

                    league_adaptation,

                    form,

                    passport_confidence,
                    faj_rating,

                    version,
                    source,
                    created_at,

                    results_strength,
                    opponent_strength,
                    matches_count
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?
                )
            """, (

                team_id,
                season_id,

                clamped_data.get(
                    "attack",
                    50.0
                ),

                clamped_data.get(
                    "defense",
                    50.0
                ),

                clamped_data.get(
                    "control",
                    50.0
                ),

                clamped_data.get(
                    "tempo",
                    50.0
                ),

                clamped_data.get(
                    "press",
                    50.0
                ),

                clamped_data.get(
                    "transition",
                    50.0
                ),

                clamped_data.get(
                    "finishing",
                    50.0
                ),

                clamped_data.get(
                    "goalkeeper",
                    50.0
                ),

                clamped_data.get(
                    "discipline",
                    50.0
                ),

                clamped_data.get(
                    "squad_quality",
                    50.0
                ),

                clamped_data.get(
                    "bench_quality",
                    50.0
                ),

                clamped_data.get(
                    "coach_factor",
                    50.0
                ),

                clamped_data.get(
                    "mental",
                    50.0
                ),

                clamped_data.get(
                    "home_strength",
                    50.0
                ),

                clamped_data.get(
                    "away_strength",
                    50.0
                ),

                clamped_data.get(
                    "injury_factor",
                    50.0
                ),

                clamped_data.get(
                    "key_player_loss",
                    0.0
                ),

                clamped_data.get(
                    "league_adaptation",
                    80.0
                ),

                form,

                passport_confidence,

                faj_rating,

                next_version,

                source,

                created_at,

                results_strength,
                opponent_strength,
                matches_count
            ))

            conn.commit()

            logger.info(
                "Passport created | "
                "team=%s | season=%s | "
                "version=%s | rating=%.1f | source=%s | "
                "matches=%s",
                team_id,
                season_id,
                next_version,
                faj_rating,
                source,
                matches_count
            )

        finally:

            conn.close()

        return self.get_current_passport(
            team_id,
            season_id
        )

    # ============================================================
    # UPDATE PASSPORT — LEARNING (исправлено v2.1)
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
        """
        Обновление паспорта через DELTA.

        changes = DELTA.

        Формула:

            weighted_delta =
                delta * opponent_factor

            learning_delta =
                weighted_delta * LEARNING_RATE

            new =
                old + learning_delta

        Служебные поля:
            _absolute_form (временное, не хранится в БД)

        ИСПРАВЛЕНО v2.1:
            matches_count передаётся как аргумент, а не через changes
            results_strength и opponent_strength сохраняются в БД
        """

        current = self.get_current_passport(
            team_id,
            season_id
        )

        if not current:

            logger.warning(
                "No current passport for team %s. "
                "Cannot learn without initial passport.",
                team_id
            )

            return None

        weighted_changes = (
            self._apply_weighted_changes(
                changes,
                opponent_rating
            )
        )

        new_data = current.copy()

        # --------------------------------------------------------
        # SERVICE FIELDS
        # --------------------------------------------------------

        absolute_form = (
            weighted_changes.pop(
                "_absolute_form",
                None
            )
        )

        # --------------------------------------------------------
        # Служебные поля из current (сохраняются)
        # --------------------------------------------------------

        results_strength = (
            weighted_changes.pop(
                "results_strength",
                current.get("results_strength")
            )
        )

        opponent_strength = (
            weighted_changes.pop(
                "opponent_strength",
                current.get("opponent_strength")
            )
        )

        # --------------------------------------------------------
        # matches_count (ТОЛЬКО из аргумента)
        # --------------------------------------------------------

        new_matches_count = matches_count

        # --------------------------------------------------------
        # ABSOLUTE FORM
        # --------------------------------------------------------

        if absolute_form is not None:

            try:

                new_data["form"] = (
                    self._clamp(
                        float(absolute_form),
                        "form"
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                logger.warning(
                    "Invalid absolute form "
                    "for team %s: %s",
                    team_id,
                    absolute_form
                )

        # --------------------------------------------------------
        # DELTA
        # --------------------------------------------------------

        for key, delta in weighted_changes.items():

            if key not in self.PARAM_RANGES:
                continue

            if key == "faj_rating":
                continue

            try:

                old_value = float(
                    new_data.get(
                        key,
                        self.DEFAULT_VALUE
                    )
                )

                delta = float(delta)

            except (
                TypeError,
                ValueError
            ):

                continue

            learning_delta = (
                delta
                * self.LEARNING_RATE
            )

            new_value = (
                old_value
                + learning_delta
            )

            new_data[key] = (
                self._clamp(
                    new_value,
                    key
                )
            )

        # --------------------------------------------------------
        # CONFIDENCE
        # --------------------------------------------------------

        new_data["passport_confidence"] = (
            self._calculate_confidence(
                new_data,
                new_matches_count,
                new_data.get(
                    "created_at",
                    datetime.now().isoformat()
                )
            )
        )

        # --------------------------------------------------------
        # RATING
        # --------------------------------------------------------

        new_data["faj_rating"] = (
            self.calculate_rating(
                new_data,
                results_strength=results_strength,
                opponent_strength=opponent_strength,
                form=new_data.get("form")
            )
        )

        # --------------------------------------------------------
        # СОХРАНЯЕМ СЛУЖЕБНЫЕ ПОЛЯ В new_data
        # --------------------------------------------------------

        new_data["results_strength"] = (
            results_strength
        )

        new_data["opponent_strength"] = (
            opponent_strength
        )

        new_data["matches_count"] = (
            new_matches_count
        )

        return self.create_passport(
            team_id,
            season_id,
            new_data,
            source
        )

    # ============================================================
    # UPDATE AFTER MATCH (исправлено v2.1)
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

        current = self.get_current_passport(
            team_id,
            season_id
        )

        if not current:

            logger.warning(
                "Cannot update team %s: "
                "passport does not exist.",
                team_id
            )

            return None

        changes = (
            self._calculate_match_changes(
                match_data
            )
        )

        # --------------------------------------------------------
        # ABSOLUTE FORM
        # --------------------------------------------------------

        if "form" in match_data:

            try:

                changes["_absolute_form"] = (
                    float(
                        match_data["form"]
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                pass

        # --------------------------------------------------------
        # RESULTS STRENGTH
        # --------------------------------------------------------

        if "results_strength" in match_data:

            changes["results_strength"] = (
                match_data[
                    "results_strength"
                ]
            )

        # --------------------------------------------------------
        # OPPONENT STRENGTH
        # --------------------------------------------------------

        changes["opponent_strength"] = (
            opponent_rating
        )

        # --------------------------------------------------------
        # match_count передаётся как аргумент
        # НЕ через changes (ИСПРАВЛЕНО v2.1)
        # --------------------------------------------------------

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
    # APPLY WEIGHTED CHANGES
    # ============================================================

    def _apply_weighted_changes(
        self,
        changes: Dict[str, Any],
        opponent_rating: float
    ) -> Dict[str, Any]:
        """
        Применяет opponent_factor только
        к математическим DELTA.

        Служебные поля не изменяются.
        """

        try:

            opponent_rating = float(
                opponent_rating
            )

        except (
            TypeError,
            ValueError
        ):

            opponent_rating = 70.0

        opponent_rating = max(
            0.0,
            min(
                100.0,
                opponent_rating
            )
        )

        opponent_factor = (
            1.0
            + (
                opponent_rating - 70.0
            ) / 200.0
        )

        opponent_factor = max(
            0.85,
            min(
                1.15,
                opponent_factor
            )
        )

        weighted = {}

        for key, value in changes.items():

            # ----------------------------------------------------
            # SERVICE FIELD (только _absolute_form)
            # ----------------------------------------------------

            if key in self.SERVICE_FIELDS:

                weighted[key] = value

                continue

            # ----------------------------------------------------
            # UNKNOWN FIELD
            # ----------------------------------------------------

            if key not in self.PARAM_RANGES:
                continue

            # ----------------------------------------------------
            # RATING IS CALCULATED
            # ----------------------------------------------------

            if key == "faj_rating":
                continue

            try:

                value = float(value)

            except (
                TypeError,
                ValueError
            ):

                continue

            weighted[key] = (
                value
                * opponent_factor
            )

        return weighted

    # ============================================================
    # MATCH SIGNALS
    # ============================================================

    def _calculate_match_changes(
        self,
        match_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Формирование DELTA после матча.

        form здесь НЕ считается DELTA.
        """

        changes = {}

        try:

            goals_for = float(
                match_data.get(
                    "goals_for",
                    0
                )
            )

            goals_against = float(
                match_data.get(
                    "goals_against",
                    0
                )
            )

            xg_for = float(
                match_data.get(
                    "xg_for",
                    goals_for
                )
            )

            xg_against = float(
                match_data.get(
                    "xg_against",
                    goals_against
                )
            )

        except (
            TypeError,
            ValueError
        ):

            logger.warning(
                "Invalid match data"
            )

            return {}

        # --------------------------------------------------------
        # ATTACK
        # --------------------------------------------------------

        attack_signal = (

            (xg_for - 1.35)
            * 0.6

            +

            (goals_for - 1.35)
            * 0.4
        )

        changes["attack"] = (
            attack_signal * 2.0
        )

        # --------------------------------------------------------
        # DEFENSE
        # --------------------------------------------------------

        defense_signal = (

            (1.35 - xg_against)
            * 0.6

            +

            (1.35 - goals_against)
            * 0.4
        )

        changes["defense"] = (
            defense_signal * 2.0
        )

        # --------------------------------------------------------
        # FINISHING
        # --------------------------------------------------------

        finishing_signal = (
            goals_for - xg_for
        )

        changes["finishing"] = (
            finishing_signal
        )

        # --------------------------------------------------------
        # MENTAL
        # --------------------------------------------------------

        if match_data.get(
            "is_win",
            False
        ):

            changes["mental"] = 1.0

        elif match_data.get(
            "is_draw",
            False
        ):

            changes["mental"] = 0.3

        else:

            changes["mental"] = -0.5

        return changes

    # ============================================================
    # CONFIDENCE
    # ============================================================

    def _calculate_confidence(
        self,
        passport: Dict[str, Any],
        matches_count: int,
        created_at: str
    ) -> float:

        required_fields = [

            "attack",
            "defense",
            "control",
            "tempo",
            "press",
            "transition",
            "finishing",
            "squad_quality",
            "coach_factor",
        ]

        filled = 0

        for field in required_fields:

            value = passport.get(
                field
            )

            if value is None:
                continue

            try:

                if float(value) != 0:
                    filled += 1

            except (
                TypeError,
                ValueError
            ):

                pass

        data_quality = (
            filled
            / len(required_fields)
        )

        try:

            matches_count = int(
                matches_count
            )

        except (
            TypeError,
            ValueError
        ):

            matches_count = 0

        matches_factor = min(
            0.4,
            matches_count * 0.004
        )

        try:

            created = datetime.fromisoformat(
                created_at
            )

            days_old = (
                datetime.now()
                - created
            ).days

            freshness_factor = max(
                0.0,
                1.0
                - (
                    days_old
                    / 180.0
                )
            )

        except Exception:

            freshness_factor = 0.8

        base_confidence = (
            0.2
            + data_quality * 0.4
        )

        confidence = (
            base_confidence
            + matches_factor
            * freshness_factor
        )

        return round(
            min(
                1.0,
                confidence
            ),
            4
        )

    # ============================================================
    # CLAMP
    # ============================================================

    def _clamp(
        self,
        value: float,
        key: str
    ) -> float:

        if key in self.PARAM_RANGES:

            min_val, max_val = (
                self.PARAM_RANGES[key]
            )

            return max(
                min_val,
                min(
                    max_val,
                    value
                )
            )

        return max(
            0.0,
            min(
                100.0,
                value
            )
        )

    # ============================================================
    # CLAMP PARAMS
    # ============================================================

    def _clamp_params(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:

        result = {}

        for key, value in data.items():

            if key in self.PARAM_RANGES:

                try:

                    result[key] = (
                        self._clamp(
                            float(value),
                            key
                        )
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    result[key] = (
                        self.DEFAULT_VALUE
                    )

            else:

                result[key] = value

        return result

    # ============================================================
    # VERSION
    # ============================================================

    def _get_next_version(
        self,
        team_id: int,
        season_id: int
    ) -> str:

        versions = (
            self.get_passport_versions(
                team_id,
                season_id
            )
        )

        if not versions:
            return "v1.0"

        numbers = []

        for version in versions:

            match = re.search(
                r"v(\d+)",
                str(version)
            )

            if match:

                numbers.append(
                    int(
                        match.group(1)
                    )
                )

        if not numbers:
            return "v1.0"

        next_num = (
            max(numbers) + 1
        )

        return f"v{next_num}.0"

    # ============================================================
    # RATING HELPERS
    # ============================================================

    def _normalize_rating_value(
        self,
        value: Any,
        fallback: float
    ) -> float:

        try:

            value = float(value)

        except (
            TypeError,
            ValueError
        ):

            return fallback

        return max(
            0.0,
            min(
                100.0,
                value
            )
        )

    def _normalize_form_value(
        self,
        value: Any,
        fallback: float
    ) -> float:

        if value is None:
            return fallback

        try:

            value = float(value)

        except (
            TypeError,
            ValueError
        ):

            return fallback

        return max(
            0.0,
            min(
                100.0,
                value
            )
        )

    # ============================================================
    # LEGACY COMPATIBILITY
    # ============================================================

    def _calculate_faj_rating(
        self,
        passport: Dict[str, Any],
        results_strength: float = 0,
        opponent_strength: float = 0,
        form: float = 0
    ) -> float:

        results = (
            None
            if results_strength in (None, 0)
            else results_strength
        )

        opponent = (
            None
            if opponent_strength in (None, 0)
            else opponent_strength
        )

        form_value = (
            None
            if form in (None, 0)
            else form
        )

        return self.calculate_rating(
            passport,
            results_strength=results,
            opponent_strength=opponent,
            form=form_value
        )


# ================================================================
# SINGLETON
# ================================================================

_default_manager: Optional[PassportManager] = None


def get_passport_manager(
    db: Optional[FAJDatabase] = None
) -> PassportManager:

    global _default_manager

    if _default_manager is None:

        _default_manager = PassportManager(
            db
        )

    return _default_manager
