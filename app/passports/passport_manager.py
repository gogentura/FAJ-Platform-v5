#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Passport Manager v1.5
=====================================================

РОЛЬ:
    Управление паспортами команд:
    - создание
    - получение
    - версионирование
    - обновление после матчей
    - расчёт FAJ Rating
    - расчёт Passport Confidence

КЛЮЧЕВЫЕ ИСПРАВЛЕНИЯ v1.5:

    1. Исправлено обучение через DELTA.
       changes теперь являются изменениями параметров,
       а не новыми абсолютными значениями.

    2. Исправлено влияние силы соперника.
       Рейтинг соперника 85 больше не умножает сигнал на 85.
       Используется нормализованный коэффициент.

    3. Единый механизм FAJ Rating.

    4. Первичный паспорт без истории получает
       рейтинг, основанный на самом паспорте,
       а не искусственно заниженный рейтинг.

    5. Отсутствующая форма является нейтральной,
       а не равной 0.

    6. FAJ Rating является производным показателем.
       Он пересчитывается, а не обучается как обычный
       параметр паспорта.

    7. fаj_rating НЕ используется как обычный
       обучаемый параметр.

    8. Сохранены:
       - Tournament DNA
       - Passport Confidence
       - versioning
       - SQLite
       - update_after_match()
       - get_current_passport_by_name()

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
    Passport Manager v1.5
    """

    VERSION = "1.5"

    # ============================================================
    # GLOBAL SETTINGS
    # ============================================================

    DEFAULT_VALUE = 50.0

    POWER_MIN = 0.0
    POWER_MAX = 100.0

    # Скорость обучения.
    #
    # Важно:
    # changes = DELTA, а не новое значение.
    #
    # Пример:
    # attack = 80
    # signal = +2
    # learning_rate = 0.10
    #
    # новое attack = 80 + 2 * 0.10 = 80.20
    #
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
        "league_adaptation": (0, 100)
    }

    # ============================================================
    # TOURNAMENT DNA
    # ============================================================

    TOURNAMENT_DNA = {
        "RPL": {
            "goal_factor": 0.95,
            "home_advantage": 1.10,
            "tempo": 0.90,
            "physicality": 1.05,
            "league_adaptation": 85
        },

        "EPL": {
            "goal_factor": 1.05,
            "home_advantage": 1.05,
            "tempo": 1.10,
            "physicality": 1.00,
            "league_adaptation": 90
        },

        "La Liga": {
            "goal_factor": 1.00,
            "home_advantage": 1.08,
            "tempo": 0.95,
            "technical": 1.10,
            "league_adaptation": 88
        },

        "UCL": {
            "goal_factor": 1.05,
            "home_advantage": 1.00,
            "tempo": 1.00,
            "experience": 1.10,
            "league_adaptation": 92
        }
    }

    # ============================================================
    # RATING WEIGHTS
    # ============================================================

    RATING_WEIGHTS = {
        "passport": 0.40,
        "results": 0.30,
        "opponent": 0.20,
        "form": 0.10
    }

    # ============================================================
    # PASSPORT RATING WEIGHTS
    # ============================================================

    PASSPORT_RATING_WEIGHTS = {
        "attack": 0.18,
        "defense": 0.18,
        "control": 0.10,
        "tempo": 0.08,
        "press": 0.08,
        "transition": 0.06,
        "finishing": 0.06,
        "squad_quality": 0.10,
        "coach_factor": 0.06,
        "mental": 0.06,
        "home_strength": 0.02,
        "league_adaptation": 0.02
    }

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, db: Optional[FAJDatabase] = None):

        self.db = db or FAJDatabase()

        self._version_cache = {}

        self._check_migration()

        logger.info(
            "Passport Manager v%s initialized",
            self.VERSION
        )

    # ============================================================
    # MIGRATION
    # ============================================================

    def _check_migration(self) -> None:
        """
        Проверка таблицы team_passports.
        """

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                AND name='team_passports'
            """)

            table_exists = cursor.fetchone()

            if not table_exists:

                logger.warning(
                    "Table team_passports does not exist. Creating..."
                )

                self._create_team_passports_table()

                return

            cursor.execute(
                "PRAGMA table_info(team_passports)"
            )

            columns = [
                row[1]
                for row in cursor.fetchall()
            ]

            required_columns = [
                "faj_rating",
                "passport_confidence",
                "injury_factor",
                "key_player_loss",
                "league_adaptation"
            ]

            missing_columns = [
                col
                for col in required_columns
                if col not in columns
            ]

            if missing_columns:

                logger.warning(
                    "Missing passport columns: %s",
                    missing_columns
                )

                for col in missing_columns:

                    if col == "passport_confidence":
                        col_type = "REAL DEFAULT 0.5"

                    elif col == "faj_rating":
                        col_type = "REAL DEFAULT 0.0"

                    else:
                        col_type = "REAL DEFAULT 50"

                    cursor.execute(
                        f"""
                        ALTER TABLE team_passports
                        ADD COLUMN {col} {col_type}
                        """
                    )

                conn.commit()

        finally:

            conn.close()

        logger.info(
            "Passport migration check completed"
        )

    # ============================================================
    # CREATE TABLE
    # ============================================================

    def _create_team_passports_table(self) -> None:

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_passports (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    team_id INTEGER,
                    season_id INTEGER,

                    attack REAL DEFAULT 50,
                    defense REAL DEFAULT 50,
                    control REAL DEFAULT 50,

                    tempo REAL DEFAULT 50,
                    press REAL DEFAULT 50,
                    transition REAL DEFAULT 50,

                    finishing REAL DEFAULT 50,
                    goalkeeper REAL DEFAULT 50,

                    discipline REAL DEFAULT 50,

                    squad_quality REAL DEFAULT 50,
                    bench_quality REAL DEFAULT 50,

                    coach_factor REAL DEFAULT 50,
                    mental REAL DEFAULT 50,

                    home_strength REAL DEFAULT 50,
                    away_strength REAL DEFAULT 50,

                    injury_factor REAL DEFAULT 50,
                    key_player_loss REAL DEFAULT 50,

                    league_adaptation REAL DEFAULT 80,

                    passport_confidence REAL DEFAULT 0.5,
                    faj_rating REAL DEFAULT 0.0,

                    version TEXT,
                    source TEXT,
                    created_at TEXT,

                    FOREIGN KEY(team_id)
                        REFERENCES teams(id),

                    FOREIGN KEY(season_id)
                        REFERENCES seasons(id),

                    UNIQUE(
                        team_id,
                        season_id,
                        version
                    )
                )
            """)

            conn.commit()

        finally:

            conn.close()

        logger.info(
            "Table team_passports created"
        )

    # ============================================================
    # GET CURRENT PASSPORT
    # ============================================================

    def get_current_passport(
        self,
        team_id: int,
        season_id: int
    ) -> Optional[Dict[str, Any]]:

        conn = self.db._get_connection()
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
                season_id
            ))

            row = cursor.fetchone()

            if row:
                return dict(row)

            return None

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

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                SELECT id
                FROM teams
                WHERE name = ?
                LIMIT 1
            """, (
                team_name,
            ))

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

        # --------------------------------------------------------
        # Определяем сезон
        # --------------------------------------------------------

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

        conn = self.db._get_connection()
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
                limit
            ))

            rows = cursor.fetchall()

            return [
                dict(row)
                for row in rows
            ]

        finally:

            conn.close()

    # ============================================================
    # VERSIONS
    # ============================================================

    def get_passport_versions(
        self,
        team_id: int,
        season_id: int
    ) -> list:

        conn = self.db._get_connection()
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
                season_id
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

        Если исторические данные отсутствуют,
        используется Passport Rating.

        Это важно для первичного паспорта.

        Полная модель:

            40% Passport
            30% Results
            20% Opponent
            10% Form

        Но отсутствующие компоненты НЕ должны
        автоматически превращаться в ноль.
        """

        passport_rating = self._calculate_passport_rating(
            passport
        )

        # --------------------------------------------------------
        # Нет истории
        # --------------------------------------------------------

        history_available = any([
            results_strength is not None,
            opponent_strength is not None,
            form is not None
        ])

        if not history_available:

            return round(
                passport_rating,
                1
            )

        # --------------------------------------------------------
        # Нормализация
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Итог
        # --------------------------------------------------------

        rating = (
            passport_rating
            * self.RATING_WEIGHTS["passport"]

            + results_value
            * self.RATING_WEIGHTS["results"]

            + opponent_value
            * self.RATING_WEIGHTS["opponent"]

            + form_value
            * self.RATING_WEIGHTS["form"]
        )

        return round(
            max(0.0, min(100.0, rating)),
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

        for key, weight in self.PASSPORT_RATING_WEIGHTS.items():

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
                min(self.POWER_MAX, value)
            )

            score += value * weight

        return round(
            max(0.0, min(100.0, score)),
            1
        )

    # ============================================================
    # CREATE PASSPORT
    # ============================================================

    def create_passport(
        self,
        team_id: int,
        season_id: int,
        data: Dict[str, Any],
        source: str = "manual"
    ) -> Optional[Dict[str, Any]]:

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:

            next_version = self._get_next_version(
                team_id,
                season_id
            )

            clamped_data = self._clamp_params(
                data
            )

            # ----------------------------------------------------
            # FAJ Rating
            # ----------------------------------------------------

            results_strength = data.get(
                "results_strength"
            )

            opponent_strength = data.get(
                "opponent_strength"
            )

            form = data.get(
                "form"
            )

            faj_rating = self.calculate_rating(
                clamped_data,
                results_strength=results_strength,
                opponent_strength=opponent_strength,
                form=form
            )

            # ----------------------------------------------------
            # Confidence
            # ----------------------------------------------------

            passport_confidence = (
                self._calculate_confidence(
                    clamped_data,
                    data.get(
                        "matches_count",
                        0
                    ),
                    data.get(
                        "created_at",
                        datetime.now().isoformat()
                    )
                )
            )

            created_at = datetime.now().isoformat()

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

                    passport_confidence,
                    faj_rating,

                    version,
                    source,
                    created_at

                )
                VALUES (
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
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
                    50.0
                ),

                clamped_data.get(
                    "league_adaptation",
                    80.0
                ),

                passport_confidence,
                faj_rating,

                next_version,
                source,
                created_at
            ))

            conn.commit()

            logger.info(
                "Passport created | "
                "team=%s | season=%s | "
                "version=%s | rating=%.1f | "
                "confidence=%.3f",
                team_id,
                season_id,
                next_version,
                faj_rating,
                passport_confidence
            )

        finally:

            conn.close()

        return self.get_current_passport(
            team_id,
            season_id
        )

    # ============================================================
    # UPDATE PASSPORT
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
        Обновление паспорта.

        ВАЖНО:

        changes = DELTA.

        Например:

            attack: +2.0

        означает:

            текущий attack + 2.0

        После Learning Rate:

            current + 2.0 * 0.10
        """

        current = self.get_current_passport(
            team_id,
            season_id
        )

        if not current:

            logger.warning(
                "No current passport for team %s. "
                "Creating initial passport.",
                team_id
            )

            return self.create_passport(
                team_id,
                season_id,
                changes,
                source
            )

        # --------------------------------------------------------
        # Weighted DELTA
        # --------------------------------------------------------

        weighted_changes = (
            self._apply_weighted_changes(
                changes,
                opponent_rating,
                tournament
            )
        )

        new_data = current.copy()

        # --------------------------------------------------------
        # Применяем DELTA
        # --------------------------------------------------------

        for key, delta in weighted_changes.items():

            if key not in self.PARAM_RANGES:
                continue

            # FAJ Rating не обучаем напрямую
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

            # ----------------------------------------------------
            # Learning Rate
            # ----------------------------------------------------

            learning_delta = (
                delta * self.LEARNING_RATE
            )

            new_value = (
                old_value
                + learning_delta
            )

            new_data[key] = self._clamp(
                new_value,
                key
            )

            logger.debug(
                "Passport learning | "
                "team=%s | %s | "
                "old=%.3f | delta=%.3f | "
                "weighted=%.3f | new=%.3f",
                team_id,
                key,
                old_value,
                delta,
                learning_delta,
                new_value
            )

        # --------------------------------------------------------
        # Confidence
        # --------------------------------------------------------

        new_data[
            "passport_confidence"
        ] = self._calculate_confidence(
            new_data,
            matches_count + 1,
            new_data.get(
                "created_at",
                datetime.now().isoformat()
            )
        )

        # --------------------------------------------------------
        # FAJ Rating
        # --------------------------------------------------------

        # Если изменения содержат форму,
        # используем её как новый сигнал.
        form = changes.get("form")

        # Если форма отсутствует,
        # НЕ превращаем её в 0.
        if form is None:
            form = None

        results_strength = (
            changes.get(
                "results_strength"
            )
        )

        opponent_strength = (
            changes.get(
                "opponent_strength",
                opponent_rating
            )
        )

        new_data["faj_rating"] = (
            self.calculate_rating(
                new_data,
                results_strength=results_strength,
                opponent_strength=opponent_strength,
                form=form
            )
        )

        # --------------------------------------------------------
        # Создаём новую версию
        # --------------------------------------------------------

        result = self.create_passport(
            team_id,
            season_id,
            new_data,
            source
        )

        if result:

            logger.info(
                "Passport updated | "
                "team=%s | rating=%.1f",
                team_id,
                result.get(
                    "faj_rating",
                    0.0
                )
            )

        return result

    # ============================================================
    # UPDATE AFTER MATCH
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

        changes = self._calculate_match_changes(
            match_data
        )

        if not changes:

            return current

        return self.update_passport(
            team_id,
            season_id,
            changes,
            source="match_update",
            opponent_rating=opponent_rating,
            tournament=tournament,
            matches_count=matches_count
        )

    # ============================================================
    # APPLY WEIGHTED CHANGES
    # ============================================================

    def _apply_weighted_changes(
        self,
        changes: Dict[str, Any],
        opponent_rating: float,
        tournament: str
    ) -> Dict[str, Any]:
        """
        Модификация DELTA.

        Критически важно:

        opponent_rating НЕ используется
        напрямую как множитель.

        Было:

            delta * 85

        Стало:

            delta * ~1.08
        """

        tournament_dna = (
            self.TOURNAMENT_DNA.get(
                tournament,
                self.TOURNAMENT_DNA["RPL"]
            )
        )

        # --------------------------------------------------------
        # Нормализованный коэффициент соперника
        # --------------------------------------------------------

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
            min(100.0, opponent_rating)
        )

        opponent_factor = (
            1.0
            + (
                opponent_rating - 70.0
            ) / 200.0
        )

        # Ограничение
        opponent_factor = max(
            0.85,
            min(1.15, opponent_factor)
        )

        # --------------------------------------------------------
        # Tournament DNA
        # --------------------------------------------------------

        goal_factor = float(
            tournament_dna.get(
                "goal_factor",
                1.0
            )
        )

        # --------------------------------------------------------
        # Итоговый коэффициент
        # --------------------------------------------------------

        total_factor = (
            opponent_factor
            * goal_factor
        )

        weighted = {}

        for key, value in changes.items():

            if key not in self.PARAM_RANGES:

                # Служебные данные
                # сохраняем без математической
                # трансформации.
                weighted[key] = value
                continue

            try:

                value = float(value)

            except (
                TypeError,
                ValueError
            ):

                continue

            # ----------------------------------------------------
            # ВАЖНО:
            #
            # value = DELTA
            #
            # а не абсолютное значение.
            # ----------------------------------------------------

            weighted[key] = (
                value
                * total_factor
            )

        logger.debug(
            "Weighted match signal | "
            "opponent_rating=%.1f | "
            "opponent_factor=%.3f | "
            "goal_factor=%.3f | "
            "total_factor=%.3f",
            opponent_rating,
            opponent_factor,
            goal_factor,
            total_factor
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

        Важно:
        эти значения НЕ являются новыми паспортными
        значениями.

        Это только сигналы изменения.
        """

        changes = {}

        # --------------------------------------------------------
        # Goals / xG
        # --------------------------------------------------------

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
        # Атака
        # --------------------------------------------------------

        attack_signal = (
            (xg_for - 1.35) * 0.6
            +
            (goals_for - 1.35) * 0.4
        )

        changes["attack"] = (
            attack_signal
            * 2.0
        )

        # --------------------------------------------------------
        # Защита
        # --------------------------------------------------------

        defense_signal = (
            (1.35 - xg_against) * 0.6
            +
            (1.35 - goals_against) * 0.4
        )

        changes["defense"] = (
            defense_signal
            * 2.0
        )

        # --------------------------------------------------------
        # Finishing
        # --------------------------------------------------------

        finishing_signal = (
            goals_for - xg_for
        )

        changes["finishing"] = (
            finishing_signal
            * 1.0
        )

        # --------------------------------------------------------
        # Mental
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

        # --------------------------------------------------------
        # Injury factor
        # --------------------------------------------------------

        if match_data.get(
            "is_win",
            False
        ):

            changes["injury_factor"] = 0.5

        elif not match_data.get(
            "is_draw",
            False
        ):

            changes["injury_factor"] = -0.3

        # --------------------------------------------------------
        # External form signal
        # --------------------------------------------------------

        if "form" in match_data:

            try:

                form_value = float(
                    match_data["form"]
                )

                # Центр формы = 50
                form_delta = (
                    form_value - 50.0
                ) / 10.0

                changes["form"] = (
                    form_delta
                )

            except (
                TypeError,
                ValueError
            ):

                pass

        logger.debug(
            "Match changes generated: %s",
            changes
        )

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
        """
        Passport Confidence.

        Состав:

        Data Quality
        +
        Match Count
        +
        Freshness
        """

        required_fields = [
            "attack",
            "defense",
            "control",
            "tempo",
            "press",
            "transition",
            "finishing",
            "squad_quality",
            "coach_factor"
        ]

        filled = 0

        for field in required_fields:

            value = passport.get(
                field
            )

            if value is not None:

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

        # --------------------------------------------------------
        # Match count
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Freshness
        # --------------------------------------------------------

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
                1.0 - (
                    days_old / 180.0
                )
            )

        except Exception:

            freshness_factor = 0.8

        # --------------------------------------------------------
        # Base
        # --------------------------------------------------------

        base_confidence = (
            0.2
            +
            data_quality * 0.4
        )

        confidence = (
            base_confidence
            +
            matches_factor
            * freshness_factor
        )

        return round(
            min(1.0, confidence),
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
                min(max_val, value)
            )

        return max(
            0.0,
            min(100.0, value)
        )

    # ------------------------------------------------------------

    def _clamp_params(
        self,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:

        result = {}

        for key, value in data.items():

            if key in self.PARAM_RANGES:

                try:

                    result[key] = self._clamp(
                        float(value),
                        key
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

        versions = self.get_passport_versions(
            team_id,
            season_id
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
                    int(match.group(1))
                )

        if not numbers:

            return "v1.0"

        next_num = (
            max(numbers)
            + 1
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
            min(100.0, value)
        )

    # ------------------------------------------------------------

    def _normalize_form_value(
        self,
        value: Any,
        fallback: float
    ) -> float:
        """
        Form может приходить как:

            0-100

        либо:

            None

        Отсутствие формы = нейтральное значение.
        """

        if value is None:

            return fallback

        try:

            value = float(value)

        except (
            TypeError,
            ValueError
        ):

            return fallback

        if value <= 0:

            return fallback

        return max(
            0.0,
            min(100.0, value)
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
        """
        Совместимость со старым кодом.

        Теперь весь расчёт проходит через
        единый calculate_rating().

        Нулевые значения считаются отсутствующими.
        """

        results = (
            None
            if results_strength in (
                None,
                0
            )
            else results_strength
        )

        opponent = (
            None
            if opponent_strength in (
                None,
                0
            )
            else opponent_strength
        )

        form_value = (
            None
            if form in (
                None,
                0
            )
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

_default_manager: Optional[
    PassportManager
] = None


def get_passport_manager(
    db: Optional[FAJDatabase] = None
) -> PassportManager:

    global _default_manager

    if _default_manager is None:

        _default_manager = PassportManager(
            db
        )

    return _default_manager
