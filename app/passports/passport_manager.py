#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v11.3
Passport Manager v1.3 (ФИНАЛЬНАЯ ВЕРСИЯ)

РОЛЬ:
    Управление паспортами команд.
    Создание, обновление, версионирование.

ИЗМЕНЕНИЯ v1.3:
    - Правильная сортировка версий (CAST AS FLOAT)
    - FAJ Rating через результаты (Passport + Results + Opponent + Form)
    - Confidence через количество матчей и свежесть данных
    - xG в обучение
    - Добавлен injury_factor и key_player_loss
    - Добавлен Tournament DNA
    - Добавлена проверка миграции базы данных
=====================================================
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from app.database import FAJDatabase

logger = logging.getLogger(__name__)


class PassportManager:
    """
    Passport Manager v1.3 (ФИНАЛЬНАЯ ВЕРСИЯ)
    Управление паспортами команд
    """

    VERSION = "1.3"

    # Диапазоны параметров
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

    # Веса турниров (Tournament DNA)
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

    # Веса для FAJ Rating
    RATING_WEIGHTS = {
        "passport": 0.40,
        "results": 0.30,
        "opponent": 0.20,
        "form": 0.10
    }

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self._version_cache = {}

        # Проверяем наличие нужных колонок в БД
        self._check_migration()

        logger.info(f"Passport Manager v{self.VERSION} initialized")

    # ============================================================
    # MIGRATION CHECK
    # ============================================================

    def _check_migration(self) -> None:
        """Проверка наличия нужных колонок в таблице team_passports"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Проверяем существование таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='team_passports'
        """)
        table_exists = cursor.fetchone()

        if not table_exists:
            logger.warning("Table 'team_passports' does not exist. Creating...")
            self._create_team_passports_table()
            conn.close()
            return

        # Проверяем наличие колонок
        cursor.execute("PRAGMA table_info(team_passports)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = [
            'faj_rating', 'passport_confidence', 'injury_factor',
            'key_player_loss', 'league_adaptation'
        ]

        missing_columns = [col for col in required_columns if col not in columns]

        if missing_columns:
            logger.warning(f"Missing columns: {missing_columns}. Adding...")
            for col in missing_columns:
                col_type = "REAL"
                if col in ['injury_factor', 'key_player_loss', 'league_adaptation']:
                    col_type = "REAL DEFAULT 50"
                cursor.execute(f"ALTER TABLE team_passports ADD COLUMN {col} {col_type}")

        conn.commit()
        conn.close()
        logger.info("Migration check completed")

    def _create_team_passports_table(self) -> None:
        """Создание таблицы team_passports, если её нет"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

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
                FOREIGN KEY(team_id) REFERENCES teams(id),
                FOREIGN KEY(season_id) REFERENCES seasons(id),
                UNIQUE(team_id, season_id, version)
            )
        """)

        conn.commit()
        conn.close()
        logger.info("Table 'team_passports' created")

    # ============================================================
    # GET
    # ============================================================

    def get_current_passport(self, team_id: int, season_id: int) -> Optional[Dict[str, Any]]:
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM team_passports
            WHERE team_id = ? AND season_id = ?
            ORDER BY CAST(REPLACE(version, 'v', '') AS FLOAT) DESC
            LIMIT 1
        """, (team_id, season_id))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_passport_history(self, team_id: int, season_id: int, limit: int = 10) -> list:
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM team_passports
            WHERE team_id = ? AND season_id = ?
            ORDER BY CAST(REPLACE(version, 'v', '') AS FLOAT) DESC
            LIMIT ?
        """, (team_id, season_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_passport_versions(self, team_id: int, season_id: int) -> list:
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT version
            FROM team_passports
            WHERE team_id = ? AND season_id = ?
            ORDER BY CAST(REPLACE(version, 'v', '') AS FLOAT) DESC
        """, (team_id, season_id))

        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows]

    # ============================================================
    # CREATE
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

        # Определяем следующую версию
        next_version = self._get_next_version(team_id, season_id)

        # Кламп всех параметров
        clamped_data = self._clamp_params(data)

        # Рассчитываем FAJ Rating
        faj_rating = self._calculate_faj_rating(
            clamped_data,
            data.get('results_strength', 0),
            data.get('opponent_strength', 0),
            data.get('form', 0)
        )

        # Рассчитываем Confidence
        passport_confidence = self._calculate_confidence(
            clamped_data,
            data.get('matches_count', 0),
            data.get('created_at', datetime.now().isoformat())
        )

        cursor.execute("""
            INSERT INTO team_passports (
                team_id, season_id,
                attack, defense, control, tempo, press, transition,
                finishing, goalkeeper, discipline,
                squad_quality, bench_quality, coach_factor,
                mental, home_strength, away_strength,
                injury_factor, key_player_loss,
                league_adaptation,
                passport_confidence, faj_rating,
                version, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            team_id, season_id,
            clamped_data.get('attack', 50.0),
            clamped_data.get('defense', 50.0),
            clamped_data.get('control', 50.0),
            clamped_data.get('tempo', 50.0),
            clamped_data.get('press', 50.0),
            clamped_data.get('transition', 50.0),
            clamped_data.get('finishing', 50.0),
            clamped_data.get('goalkeeper', 50.0),
            clamped_data.get('discipline', 50.0),
            clamped_data.get('squad_quality', 50.0),
            clamped_data.get('bench_quality', 50.0),
            clamped_data.get('coach_factor', 50.0),
            clamped_data.get('mental', 50.0),
            clamped_data.get('home_strength', 50.0),
            clamped_data.get('away_strength', 50.0),
            clamped_data.get('injury_factor', 50.0),
            clamped_data.get('key_player_loss', 50.0),
            clamped_data.get('league_adaptation', 80.0),
            passport_confidence,
            faj_rating,
            next_version,
            source,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        logger.info(f"Passport created: team_id={team_id}, version={next_version}, rating={faj_rating}")
        return self.get_current_passport(team_id, season_id)

    # ============================================================
    # UPDATE
    # ============================================================

    def update_passport(
        self,
        team_id: int,
        season_id: int,
        changes: Dict[str, Any],
        source: str = "learning",
        opponent_rating: float = 1.0,
        tournament: str = "RPL",
        matches_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        current = self.get_current_passport(team_id, season_id)

        if not current:
            logger.warning(f"No current passport for team {team_id}")
            return self.create_passport(team_id, season_id, changes, source)

        # Применяем изменения с медленным обучением
        weighted_changes = self._apply_weighted_changes(changes, opponent_rating, tournament)

        new_data = current.copy()
        for key, value in weighted_changes.items():
            if key in new_data and key in self.PARAM_RANGES:
                old_value = new_data[key]
                # Медленное обучение: 90% старого + 10% нового сигнала
                new_data[key] = self._clamp(old_value * 0.9 + value * 0.1, key)

        # Обновляем confidence
        new_data['passport_confidence'] = self._calculate_confidence(
            new_data,
            matches_count + 1,
            new_data.get('created_at', datetime.now().isoformat())
        )

        # Обновляем FAJ Rating
        new_data['faj_rating'] = self._calculate_faj_rating(
            new_data,
            changes.get('results_strength', 0),
            changes.get('opponent_strength', opponent_rating),
            changes.get('form', 0)
        )

        return self.create_passport(team_id, season_id, new_data, source)

    def update_after_match(
        self,
        team_id: int,
        season_id: int,
        match_data: Dict[str, Any],
        opponent_rating: float = 1.0,
        tournament: str = "RPL",
        matches_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        current = self.get_current_passport(team_id, season_id)

        if not current:
            return None

        changes = self._calculate_match_changes(match_data)

        if changes:
            return self.update_passport(
                team_id,
                season_id,
                changes,
                source="match_update",
                opponent_rating=opponent_rating,
                tournament=tournament,
                matches_count=matches_count
            )

        return current

    # ============================================================
    # PRIVATE
    # ============================================================

    def _clamp(self, value: float, key: str) -> float:
        if key in self.PARAM_RANGES:
            min_val, max_val = self.PARAM_RANGES[key]
            return max(min_val, min(max_val, value))
        return max(0, min(100, value))

    def _clamp_params(self, data: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        for key, value in data.items():
            if key in self.PARAM_RANGES:
                result[key] = self._clamp(value, key)
            else:
                result[key] = value
        return result

    def _get_next_version(self, team_id: int, season_id: int) -> str:
        versions = self.get_passport_versions(team_id, season_id)

        if not versions:
            return "v1.0"

        numbers = []
        for v in versions:
            match = re.search(r'v(\d+)', v)
            if match:
                numbers.append(int(match.group(1)))

        if not numbers:
            return "v1.0"

        next_num = max(numbers) + 1
        return f"v{next_num}.0"

    def _apply_weighted_changes(
        self,
        changes: Dict[str, Any],
        opponent_rating: float,
        tournament: str
    ) -> Dict[str, Any]:
        tournament_dna = self.TOURNAMENT_DNA.get(tournament, self.TOURNAMENT_DNA["RPL"])
        base_weight = opponent_rating * tournament_dna.get('goal_factor', 1.0)

        weighted = {}
        for key, value in changes.items():
            if key in self.PARAM_RANGES:
                weighted[key] = value * base_weight
            else:
                weighted[key] = value

        return weighted

    def _calculate_match_changes(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}

        goals_for = match_data.get('goals_for', 0)
        goals_against = match_data.get('goals_against', 0)
        xg_for = match_data.get('xg_for', goals_for)
        xg_against = match_data.get('xg_against', goals_against)

        # Атака: 60% xG + 40% голы
        attack_signal = (xg_for - 1.35) * 0.6 + (goals_for - 1.35) * 0.4
        changes['attack'] = attack_signal * 0.5

        # Оборона: 60% xG против + 40% пропущенные
        defense_signal = (1.35 - xg_against) * 0.6 + (1.35 - goals_against) * 0.4
        changes['defense'] = defense_signal * 0.5

        # Реализация (finishing): разница между голами и xG
        finishing_signal = goals_for - xg_for
        changes['finishing'] = finishing_signal * 0.3

        # Менталитет
        if match_data.get('is_win', False):
            changes['mental'] = 1.0
            changes['injury_factor'] = 0.5
        elif match_data.get('is_draw', False):
            changes['mental'] = 0.3
        else:
            changes['mental'] = -0.5
            changes['injury_factor'] = -0.3

        return changes

    def _calculate_confidence(
        self,
        passport: Dict[str, Any],
        matches_count: int,
        created_at: str
    ) -> float:
        """Расчёт уверенности: Data Quality + Match Count + Freshness"""
        required_fields = [
            'attack', 'defense', 'control', 'tempo',
            'press', 'transition', 'finishing',
            'squad_quality', 'coach_factor'
        ]

        filled = 0
        for field in required_fields:
            if passport.get(field) is not None and passport.get(field) != 0:
                filled += 1

        data_quality = filled / len(required_fields)

        # Чем больше матчей, тем выше уверенность
        matches_factor = min(0.4, matches_count * 0.004)

        # Свежесть данных (чем старше, тем ниже уверенность)
        try:
            created = datetime.fromisoformat(created_at)
            days_old = (datetime.now() - created).days
            freshness_factor = max(0.0, 1.0 - (days_old / 180))  # 180 дней = полное старение
        except:
            freshness_factor = 0.8

        # Базовая уверенность от качества данных
        base_confidence = 0.2 + data_quality * 0.4

        return min(1.0, base_confidence + matches_factor * freshness_factor)

    def _calculate_faj_rating(
        self,
        passport: Dict[str, Any],
        results_strength: float = 0,
        opponent_strength: float = 0,
        form: float = 0
    ) -> float:
        """
        FAJ Rating:
        40% Passport + 30% Results + 20% Opponent + 10% Form
        """
        passport_weights = {
            'attack': 0.18,
            'defense': 0.18,
            'control': 0.10,
            'tempo': 0.08,
            'press': 0.08,
            'transition': 0.06,
            'finishing': 0.06,
            'squad_quality': 0.10,
            'coach_factor': 0.06,
            'mental': 0.06,
            'home_strength': 0.02,
            'league_adaptation': 0.02
        }

        passport_score = 0
        for key, weight in passport_weights.items():
            passport_score += passport.get(key, 50) * weight

        passport_score = passport_score / 100

        # Итоговый рейтинг (0-100)
        rating = (
            passport_score * 100 * self.RATING_WEIGHTS["passport"] +
            results_strength * self.RATING_WEIGHTS["results"] +
            opponent_strength * self.RATING_WEIGHTS["opponent"] +
            form * self.RATING_WEIGHTS["form"]
        )

        return round(max(0, min(100, rating)), 1)


# ============================================================
# SINGLETON
# ============================================================

_default_manager: Optional[PassportManager] = None


def get_passport_manager(db: Optional[FAJDatabase] = None) -> PassportManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = PassportManager(db)
    return _default_manager
