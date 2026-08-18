#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ Sync Engine v2.0
============================================================

РОЛЬ:
    Единый модуль синхронизации FAJ.

ЦЕПОЧКА:

    SyncEngine
        ↓
    FAJDatabase
        ↓
    SQLite

ПАСПОРТА:

    SyncEngine
        ↓
    PassportManager
        ↓
    team_passports

ПРИНЦИПЫ v2.0:

    1. SQLite only.

    2. SyncEngine НЕ работает с SQLite напрямую.
       Все операции идут через FAJDatabase,
       кроме backup физического файла БД.

    3. SyncEngine НЕ обучает паспорта.

    4. Синхронизация исходного паспорта работает
       с АБСОЛЮТНЫМИ значениями.

    5. update_passport() НЕ используется для
       первоначальной/экспертной синхронизации.

    6. Если паспорт уже существует и значения
       совпадают — новая версия НЕ создаётся.

    7. Если паспорт изменился — создаётся новая
       абсолютная версия через create_passport().

    8. Повторный запуск должен быть идемпотентным.

    9. Данные не удаляются.

   10. Перед изменением БД создаётся backup.

   11. Наличие команды не означает наличие паспорта.

   12. PassportManager является владельцем логики
       team_passports.

============================================================
"""

import logging
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any


from app.database import FAJDatabase

from app.passports.passport_manager import (
    PassportManager,
)

from app.passports.rpl_2026_27 import (
    RPL_PASSPORTS_2026_27,
    normalize_team_name,
)


logger = logging.getLogger(__name__)


# ============================================================
# ЛИГИ
# ============================================================

LEAGUE_CONFIG = {

    "РПЛ": {
        "teams": 16,
        "rounds": 30,
        "country": "Россия",
        "format": "double_round_robin",
    },

    "АПЛ": {
        "teams": 20,
        "rounds": 38,
        "country": "Англия",
        "format": "double_round_robin",
    },

    "Ла Лига": {
        "teams": 20,
        "rounds": 38,
        "country": "Испания",
        "format": "double_round_robin",
    },

    "Лига чемпионов": {
        "teams": 36,
        "rounds": 8,
        "country": "Европа",
        "format": "swiss_system",
        "playoff_start": 9,
        "direct_qualification": 8,
    },
}


# ============================================================
# LEAGUE DNA
# ============================================================

LEAGUE_DNA = {

    "mean_xg": 1.35,

    "home_advantage": 0.12,

    "avg_tempo": 72,

    "avg_goals_min": 2.35,

    "avg_goals_max": 2.55,

    "derby_factor": 1.08,

    "newcomer_motivation": 1.05,

    "first_rounds_bonus": 5,
}


# ============================================================
# SYNC ENGINE
# ============================================================

class SyncEngine:

    """
    FAJ Sync Engine v2.0.

    Главная задача:

        teams
        ↓
        season
        ↓
        passports
        ↓
        legacy passport structures

    Матчи, результаты, Gold Dataset и обучение
    остаются отдельными процессами.
    """

    VERSION = "2.0"

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        db: Optional[FAJDatabase] = None
    ):

        self.db = db or FAJDatabase()

        # ВАЖНО:
        #
        # Не используем get_passport_manager(),
        # потому что singleton может содержать
        # другой экземпляр FAJDatabase.
        #
        # SyncEngine и PassportManager должны
        # работать с одной DB-сессией/конфигурацией.

        self.passport_manager = PassportManager(
            self.db
        )

        self.passports = RPL_PASSPORTS_2026_27

        self.league_dna = LEAGUE_DNA

        self.league = "РПЛ"

        self.config = LEAGUE_CONFIG

        logger.info(
            "FAJ SyncEngine v%s initialized",
            self.VERSION
        )

    # ========================================================
    # DATABASE BACKUP
    # ========================================================

    def _backup_database(self):
        """
        Создаёт резервную копию faj.db.

        БД НЕ удаляется.

        Если файла ещё нет — backup не требуется.
        """

        from app.database import DB_FILE

        if not os.path.exists(DB_FILE):

            logger.warning(
                "Database file does not exist yet: %s",
                DB_FILE
            )

            return None

        backup_dir = "backup"

        os.makedirs(
            backup_dir,
            exist_ok=True
        )

        timestamp = datetime.now().strftime(
            "%Y_%m_%d_%H_%M_%S"
        )

        backup_file = os.path.join(
            backup_dir,
            f"faj_{timestamp}.db"
        )

        try:

            shutil.copy2(
                DB_FILE,
                backup_file
            )

            logger.info(
                "Database backup created: %s",
                backup_file
            )

            return backup_file

        except Exception:

            logger.exception(
                "Database backup failed"
            )

            raise

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Возвращает состояние системы.
        """

        full_status = self.db.get_status()

        teams = self.db.get_teams(
            league=league
        )

        matches = self.db.get_matches()

        finished = 0

        if matches:

            finished = sum(
                1
                for match in matches
                if match.get("status")
                == "finished"
            )

        return {

            "status":
                full_status.get(
                    "status",
                    "unknown"
                ),

            "league":
                league,

            "teams":
                len(teams)
                if teams
                else 0,

            "matches":
                len(matches)
                if matches
                else 0,

            "finished":
                finished,

            "gold_dataset":
                self.db.get_table_count(
                    "gold_dataset"
                ),

            "learning_records":
                self.db.get_table_count(
                    "learning_records"
                ),

            "learning_events":
                self.db.get_table_count(
                    "learning_events"
                ),

            "team_passports":
                self.db.get_table_count(
                    "team_passports"
                ),

            "team_passport_meta":
                self.db.get_table_count(
                    "team_passport_meta"
                ),

            "schema_version":
                full_status.get(
                    "schema_version"
                ),

            "database_file":
                full_status.get(
                    "file"
                ),

            "tables":
                full_status.get(
                    "tables",
                    []
                ),
        }

    # ========================================================
    # SEASON
    # ========================================================

    def _get_or_create_season(
        self,
        league="РПЛ",
        year="2026-2027"
    ):
        """
        Получает существующий сезон.

        Если сезона нет — создаёт.

        После создания/получения гарантирует
        наличие необходимых туров.
        """

        seasons = self.db.get_seasons()

        for season in seasons:

            # ✅ ИСПРАВЛЕНО: season.get() → season[]
            if (
                season["league"] == league
                and season["year"] == year
            ):

                season_id = season["id"]

                self._ensure_rounds(
                    season_id,
                    league
                )

                return season_id

        season_id = self.db.create_season(
            name=f"{league} {year}",
            league=league,
            year=year,
        )

        self._ensure_rounds(
            season_id,
            league
        )

        logger.info(
            "Season created | "
            "league=%s | year=%s | id=%s",
            league,
            year,
            season_id
        )

        return season_id

    # ========================================================
    # ENSURE ROUNDS
    # ========================================================

    def _ensure_rounds(
        self,
        season_id: int,
        league: str
    ) -> None:
        """
        Гарантирует наличие туров.

        create_round() должен быть идемпотентным.
        """

        rounds_count = (
            self.config
            .get(
                league,
                {}
            )
            .get(
                "rounds",
                30
            )
        )

        for round_number in range(
            1,
            rounds_count + 1
        ):

            self.db.create_round(
                season_id,
                round_number
            )

    # ========================================================
    # PASSPORT SYNC
    # ========================================================

    def sync_passports(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Публичная синхронизация паспортов.
        """

        try:

            result = self.load_passports(
                league
            )

            return {

                "status":
                    "success",

                "league":
                    league,

                "updated":
                    result.get(
                        "updated",
                        0
                    ),

                "created":
                    result.get(
                        "created",
                        0
                    ),

                "unchanged":
                    result.get(
                        "unchanged",
                        0
                    ),

                "total":
                    result.get(
                        "total",
                        0
                    ),

                "missing":
                    result.get(
                        "missing",
                        0
                    ),
            }

        except Exception as e:

            logger.exception(
                "Passport synchronization failed"
            )

            return {

                "status":
                    "error",

                "league":
                    league,

                "message":
                    str(e),
            }

    # ========================================================
    # PASSPORT SOURCE
    # ========================================================

    def _get_source_passport(
        self,
        team_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Находит исходный паспорт команды.
        """

        normalized = normalize_team_name(
            team_name
        )

        passport = self.passports.get(
            normalized
        )

        if passport:
            return passport

        passport = self.passports.get(
            team_name
        )

        return passport

    # ========================================================
    # BUILD PASSPORT DATA
    # ========================================================

    def _build_passport_data(
        self,
        passport: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Преобразует RPL passport source
        в плоскую структуру PassportManager.

        Все значения здесь АБСОЛЮТНЫЕ.
        """

        base = passport.get(
            "BASE",
            {}
        )

        identity = passport.get(
            "IDENTITY",
            {}
        )

        dynamic_initial = passport.get(
            "DYNAMIC_INITIAL",
            {}
        )

        # ----------------------------------------------------
        # HOME / AWAY
        # ----------------------------------------------------

        home_advantage = self._safe_float(
            base.get(
                "home_advantage",
                1.0
            ),
            1.0
        )

        # Не используем home_advantage
        # как самостоятельный рейтинг силы.
        #
        # Это отдельная характеристика команды.
        #
        # Поэтому базовые значения остаются
        # нейтральными, если отдельные поля
        # отсутствуют в source passport.

        home_strength = self._safe_float(
            base.get(
                "home_strength",
                50.0
            ),
            50.0
        )

        away_strength = self._safe_float(
            base.get(
                "away_strength",
                50.0
            ),
            50.0
        )

        # ----------------------------------------------------
        # INJURY
        # ----------------------------------------------------

        injury_index = self._safe_float(
            dynamic_initial.get(
                "injury_index",
                0
            ),
            0.0
        )

        # injury_factor:
        #
        # 100 = оптимальное состояние
        # 0   = максимальная проблема
        #
        # Если source уже содержит injury_factor,
        # используем его напрямую.

        if "injury_factor" in dynamic_initial:

            injury_factor = self._safe_float(
                dynamic_initial.get(
                    "injury_factor"
                ),
                100.0
            )

        else:

            injury_factor = max(
                0.0,
                min(
                    100.0,
                    100.0 - injury_index
                )
            )

        # ----------------------------------------------------
        # FORM
        # ----------------------------------------------------

        form = self._safe_float(
            dynamic_initial.get(
                "form",
                50
            ),
            50.0
        )

        # ----------------------------------------------------
        # PASSPORT
        # ----------------------------------------------------

        return {

            "attack":
                self._safe_float(
                    base.get(
                        "attack",
                        50
                    )
                ),

            "defense":
                self._safe_float(
                    base.get(
                        "defense",
                        50
                    )
                ),

            "control":
                self._safe_float(
                    base.get(
                        "control",
                        50
                    )
                ),

            "tempo":
                self._safe_float(
                    base.get(
                        "tempo",
                        50
                    )
                ),

            "press":
                self._safe_float(
                    base.get(
                        "press",
                        50
                    )
                ),

            "transition":
                self._safe_float(
                    base.get(
                        "transition",
                        50
                    )
                ),

            "finishing":
                self._safe_float(
                    base.get(
                        "finishing",
                        50
                    )
                ),

            "goalkeeper":
                self._safe_float(
                    base.get(
                        "goalkeeper",
                        50
                    )
                ),

            "discipline":
                self._safe_float(
                    base.get(
                        "discipline",
                        50
                    )
                ),

            "squad_quality":
                self._safe_float(
                    base.get(
                        "squad_quality",
                        50
                    )
                ),

            "bench_quality":
                self._safe_float(
                    base.get(
                        "bench_quality",
                        50
                    )
                ),

            "coach_factor":
                self._safe_float(
                    base.get(
                        "coach_factor",
                        50
                    )
                ),

            "mental":
                self._safe_float(
                    identity.get(
                        "mental",
                        50
                    )
                ),

            "home_strength":
                max(
                    0.0,
                    min(
                        100.0,
                        home_strength
                    )
                ),

            "away_strength":
                max(
                    0.0,
                    min(
                        100.0,
                        away_strength
                    )
                ),

            "injury_factor":
                injury_factor,

            "key_player_loss":
                self._safe_float(
                    dynamic_initial.get(
                        "key_player_loss",
                        0
                    )
                ),

            "league_adaptation":
                self._safe_float(
                    dynamic_initial.get(
                        "league_adaptation",
                        80
                    ),
                    80.0
                ),

            "form":
                form,

            # Служебные значения.
            #
            # На старте сезона результатов нет.

            "results_strength":
                self._safe_optional_float(
                    dynamic_initial.get(
                        "results_strength"
                    )
                ),

            "opponent_strength":
                self._safe_optional_float(
                    dynamic_initial.get(
                        "opponent_strength"
                    )
                ),

            "matches_count":
                0,

            "created_at":
                datetime.now().isoformat(),
        }

    # ========================================================
    # SAFE FLOAT
    # ========================================================

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 50.0
    ) -> float:

        try:

            return float(value)

        except (
            TypeError,
            ValueError
        ):

            return default

    # ========================================================
    # SAFE OPTIONAL FLOAT
    # ========================================================

    @staticmethod
    def _safe_optional_float(
        value: Any
    ) -> Optional[float]:

        if value is None:
            return None

        try:

            return float(value)

        except (
            TypeError,
            ValueError
        ):

            return None

    # ========================================================
    # COMPARE PASSPORT
    # ========================================================

    def _passport_matches(
        self,
        existing: Dict[str, Any],
        new_data: Dict[str, Any]
    ) -> bool:
        """
        Проверяет, совпадает ли существующий
        паспорт с новым абсолютным source passport.

        Сравниваются только реальные параметры
        паспорта.

        version/source/created_at/faj_rating/
        passport_confidence не участвуют.
        """

        fields = (
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
        )

        tolerance = 0.0001

        for field in fields:

            old_value = self._safe_float(
                existing.get(
                    field,
                    50.0
                ),
                50.0
            )

            new_value = self._safe_float(
                new_data.get(
                    field,
                    50.0
                ),
                50.0
            )

            if abs(
                old_value - new_value
            ) > tolerance:

                return False

        return True

    # ========================================================
    # LOAD PASSPORTS
    # ========================================================

    def load_passports(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Загружает паспорта всех существующих команд.

        ВАЖНО:

        Эта функция НЕ обучает паспорт.

        Сценарии:

            нет паспорта
                ↓
            create_passport()

            паспорт совпадает
                ↓
            ничего

            паспорт изменился
                ↓
            create_passport()
            новой абсолютной версией

        update_passport() здесь НЕ вызывается.
        """

        season_id = (
            self._get_or_create_season(
                league
            )
        )

        teams = self.db.get_teams(
            league=league
        )

        created = 0
        updated = 0
        unchanged = 0
        missing = 0

        for team in teams:

            team_id = team["id"]

            team_name = team["name"]

            # ------------------------------------------------
            # SOURCE PASSPORT
            # ------------------------------------------------

            passport = (
                self._get_source_passport(
                    team_name
                )
            )

            if not passport:

                logger.warning(
                    "Passport source not found | "
                    "team=%s",
                    team_name
                )

                missing += 1

                continue

            # ------------------------------------------------
            # BUILD ABSOLUTE DATA
            # ------------------------------------------------

            passport_data = (
                self._build_passport_data(
                    passport
                )
            )

            # ------------------------------------------------
            # CURRENT PASSPORT
            # ------------------------------------------------

            existing = (
                self.passport_manager
                .get_current_passport(
                    team_id,
                    season_id
                )
            )

            # ------------------------------------------------
            # CREATE
            # ------------------------------------------------

            if existing is None:

                self.passport_manager.create_passport(
                    team_id=team_id,
                    season_id=season_id,
                    data=passport_data,
                    source=passport.get(
                        "author",
                        "FAJ Expert Layer"
                    )
                )

                created += 1

                logger.info(
                    "Passport created | "
                    "team=%s",
                    team_name
                )

            # ------------------------------------------------
            # UNCHANGED
            # ------------------------------------------------

            elif self._passport_matches(
                existing,
                passport_data
            ):

                unchanged += 1

                logger.debug(
                    "Passport unchanged | "
                    "team=%s | version=%s",
                    team_name,
                    existing.get(
                        "version"
                    )
                )

            # ------------------------------------------------
            # UPDATED ABSOLUTE SOURCE
            # ------------------------------------------------

            else:

                self.passport_manager.create_passport(
                    team_id=team_id,
                    season_id=season_id,
                    data=passport_data,
                    source=passport.get(
                        "author",
                        "FAJ Expert Layer"
                    )
                )

                updated += 1

                logger.info(
                    "Passport absolute update | "
                    "team=%s",
                    team_name
                )

            # ------------------------------------------------
            # LEGACY BASE
            # ------------------------------------------------

            self._sync_team_base(
                team_id,
                season_id,
                passport
            )

            # ------------------------------------------------
            # LEGACY IDENTITY
            # ------------------------------------------------

            self._sync_team_identity(
                team_id,
                season_id,
                passport
            )

            # ------------------------------------------------
            # LEGACY DYNAMIC
            # ------------------------------------------------

            self._sync_team_dynamic(
                team_id,
                season_id,
                passport
            )

            # ------------------------------------------------
            # PASSPORT META
            # ------------------------------------------------

            self._sync_passport_meta(
                team_id,
                season_id,
                passport
            )

        total = len(teams)

        logger.info(
            "Passport sync completed | "
            "created=%s | updated=%s | "
            "unchanged=%s | missing=%s | total=%s",
            created,
            updated,
            unchanged,
            missing,
            total
        )

        return {

            "status":
                "success",

            "created":
                created,

            "updated":
                updated,

            "unchanged":
                unchanged,

            "missing":
                missing,

            "total":
                total,
        }

    # ========================================================
    # LEGACY BASE
    # ========================================================

    def _sync_team_base(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any]
    ) -> None:

        base = passport.get(
            "BASE",
            {}
        )

        self.db.update_base(
            team_id,
            season_id,

            attack=base.get(
                "attack",
                50
            ),

            defense=base.get(
                "defense",
                50
            ),

            control=base.get(
                "control",
                50
            ),

            press=base.get(
                "press",
                50
            ),

            tempo=base.get(
                "tempo",
                50
            ),

            transition=base.get(
                "transition",
                50
            ),

            finishing=base.get(
                "finishing",
                50
            ),

            goalkeeper=base.get(
                "goalkeeper",
                50
            ),

            discipline=base.get(
                "discipline",
                50
            ),

            coach_factor=base.get(
                "coach_factor",
                50
            ),

            squad_quality=base.get(
                "squad_quality",
                50
            ),

            bench_quality=base.get(
                "bench_quality",
                50
            ),

            home_advantage=base.get(
                "home_advantage",
                1.0
            ),
        )

    # ========================================================
    # LEGACY IDENTITY
    # ========================================================

    def _sync_team_identity(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any]
    ) -> None:

        identity = passport.get(
            "IDENTITY",
            {}
        )

        self.db.update_identity(
            team_id,
            season_id,

            style=identity.get(
                "style",
                "mixed"
            ),

            tempo=identity.get(
                "tempo_style",
                "medium"
            ),

            pressing=identity.get(
                "pressing",
                "medium"
            ),

            transition=identity.get(
                "transition",
                "medium"
            ),

            risk_level=identity.get(
                "risk",
                "medium"
            ),
        )

    # ========================================================
    # LEGACY DYNAMIC
    # ========================================================

    def _sync_team_dynamic(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any]
    ) -> None:

        dynamic_initial = (
            passport.get(
                "DYNAMIC_INITIAL",
                {}
            )
        )

        existing_dynamic = (
            self.db.get_dynamic(
                team_id,
                season_id
            )
        )

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Initial sync does not overwrite dynamic data
        # if it already exists.
        #
        # This protects future learned state.
        # ----------------------------------------------------

        if existing_dynamic:
            return

        self.db.update_dynamic(
            team_id,
            season_id,

            form=dynamic_initial.get(
                "form",
                50
            ),

            fitness=dynamic_initial.get(
                "fitness",
                50
            ),

            morale=dynamic_initial.get(
                "morale",
                50
            ),

            fatigue=dynamic_initial.get(
                "fatigue",
                50
            ),

            injury_index=dynamic_initial.get(
                "injury_index",
                0
            ),

            passport_confidence=
                dynamic_initial.get(
                    "passport_confidence",
                    0.4
                ),
        )

    # ========================================================
    # PASSPORT META
    # ========================================================

    def _sync_passport_meta(
        self,
        team_id: int,
        season_id: int,
        passport: Dict[str, Any]
    ) -> None:

        identity = passport.get(
            "IDENTITY",
            {}
        )

        expert = passport.get(
            "EXPERT",
            {}
        )

        strengths = expert.get(
            "strengths",
            {}
        )

        weaknesses = expert.get(
            "weaknesses",
            {}
        )

        strengths_str = ""

        if strengths:

            strengths_str = ", ".join(
                f"{key}:{value}"
                for key, value
                in strengths.items()
            )

        weaknesses_str = ""

        if weaknesses:

            weaknesses_str = ", ".join(
                f"{key}:{value}"
                for key, value
                in weaknesses.items()
            )

        self.db.save_passport_meta(
            team_id,
            season_id,

            {
                "style":
                    identity.get(
                        "style",
                        ""
                    ),

                "dna":
                    expert.get(
                        "dna",
                        ""
                    ),

                "strengths":
                    strengths_str,

                "weaknesses":
                    weaknesses_str,

                "class":
                    expert.get(
                        "class",
                        ""
                    ),

                "version":
                    passport.get(
                        "version",
                        "1.0"
                    ),

                "source":
                    passport.get(
                        "author",
                        "FAJ Expert Layer"
                    ),
            }
        )

    # ========================================================
    # TEAM SYNC
    # ========================================================

    def sync_teams(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Полная синхронизация команд + сезона +
        паспортов.

        ВАЖНО:

        Наличие команды НЕ является условием
        для пропуска passport sync.

        Всегда выполняется:

            teams
            ↓
            season
            ↓
            passports
        """

        backup_file = (
            self._backup_database()
        )

        teams_source = list(
            self.passports.keys()
        )

        created = 0
        existing = 0

        # ----------------------------------------------------
        # TEAMS
        # ----------------------------------------------------

        for name in teams_source:

            existing_id = (
                self.db.get_team_id(
                    name,
                    league
                )
            )

            if existing_id:

                existing += 1

                continue

            team_id = self.db.add_team(
                name,
                league=league,
                country=self.config
                .get(
                    league,
                    {}
                )
                .get(
                    "country",
                    "Россия"
                )
            )

            if team_id:

                created += 1

        # ----------------------------------------------------
        # SEASON
        # ----------------------------------------------------

        season_id = (
            self._get_or_create_season(
                league
            )
        )

        # ----------------------------------------------------
        # PASSPORTS
        # ----------------------------------------------------

        passport_result = (
            self.load_passports(
                league
            )
        )

        return {

            "status":
                "success",

            "created":
                created,

            "existing":
                existing,

            "total":
                len(teams_source),

            "season_id":
                season_id,

            "passports":
                passport_result.get(
                    "updated",
                    0
                ),

            "passport_created":
                passport_result.get(
                    "created",
                    0
                ),

            "passport_updated":
                passport_result.get(
                    "updated",
                    0
                ),

            "passport_unchanged":
                passport_result.get(
                    "unchanged",
                    0
                ),

            "passport_missing":
                passport_result.get(
                    "missing",
                    0
                ),

            "backup":
                backup_file,
        }

    # ========================================================
    # MATCHES
    # ========================================================

    def sync_matches(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Матчи пока загружаются отдельным парсером.
        """

        return {

            "status":
                "pending",

            "loaded":
                0,

            "message":
                "Ожидание парсера РПЛ",
        }

    # ========================================================
    # RESULTS
    # ========================================================

    def sync_results(
        self,
        league="РПЛ"
    ) -> Dict[str, Any]:
        """
        Результаты пока загружаются отдельным парсером.
        """

        return {

            "status":
                "pending",

            "updated":
                0,

            "message":
                "Ожидание парсера РПЛ",
        }

    # ========================================================
    # GOLD DATASET — ИСПРАВЛЕНО
    # ========================================================

    def build_gold_dataset(self):
        """
        Создаёт/обновляет Gold Dataset.

        ВАЖНО:

        Gold Dataset не считается автоматически
        полноценным FAJ prediction dataset.

        Prediction pipeline будет проверен отдельно.
        """

        from app.config import config

        matches = self.db.get_matches()

        finished = [

            match
            for match in matches

            if match.get(
                "status"
            ) == "finished"
        ]

        count = 0

        for match in finished:

            gold = self.db.get_gold_by_match(
                match["id"]
            )

            # ------------------------------------------------
            # GOLD EXISTS
            # ------------------------------------------------

            if gold:

                if not gold.get(
                    "actual_score"
                ):

                    self.db.update_gold_actual(
                        gold["id"],
                        {

                            "actual_score":
                                f"{match['actual_home']}:"
                                f"{match['actual_away']}",

                            "actual_home_goals":
                                match["actual_home"],

                            "actual_away_goals":
                                match["actual_away"],
                        }
                    )

                    count += 1

                continue

            # ------------------------------------------------
            # TEAMS
            # ------------------------------------------------

            home = self.db.get_team(
                match["home_team_id"]
            )

            away = self.db.get_team(
                match["away_team_id"]
            )

            if not home or not away:
                continue

            # ------------------------------------------------
            # GOLD
            # ------------------------------------------------

            self.db.add_to_gold(
                {

                    "match_id":
                        match["id"],

                    "home_team":
                        home["name"],

                    "away_team":
                        away["name"],

                    "match_date":
                        match.get(
                            "date",
                            ""
                        ),

                    "model_version":
                        config.MODEL_VERSION,

                    # ИСПРАВЛЕНО:
                    # Фактический счёт НЕ является прогнозом FAJ
                    "faj_score": None,

                    "actual_score":
                        f"{match['actual_home']}:"
                        f"{match['actual_away']}",

                    "actual_home_goals":
                        match["actual_home"],

                    "actual_away_goals":
                        match["actual_away"],

                    "status":
                        "completed",
                }
            )

            count += 1

        return {

            "status":
                "success",

            "loaded":
                count,
        }

    # ========================================================
    # AUDIT
    # ========================================================

    def run_audit(self):

        try:

            from app.audit_engine import (
                audit_all_pending
            )

            results = audit_all_pending()

            return {

                "status":
                    "success",

                "processed":
                    len(results)
                    if results
                    else 0,
            }

        except ImportError:

            return {

                "status":
                    "error",

                "message":
                    "audit_engine.py не найден",
            }

    # ========================================================
    # LEARNING
    # ========================================================

    def run_learning(self):

        try:

            from app.learning_engine import (
                get_learning_report
            )

            report = get_learning_report()

            return {

                "status":
                    "success"
                    if report["status"]
                    != "no_errors"
                    else "empty",

                "report":
                    report,
            }

        except ImportError:

            return {

                "status":
                    "error",

                "message":
                    "learning_engine.py не найден",
            }


# ============================================================
# DIRECT RUN
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    sync = SyncEngine()

    print(
        "🏆 FAJ SyncEngine v12.1 / v2.0"
    )

    print(
        "=" * 60
    )

    try:

        status = sync.get_status()

        print(
            f"Статус БД: "
            f"{status.get('status', 'unknown')}"
        )

        print(
            f"Команды: "
            f"{status.get('teams', 0)}"
        )

        print(
            f"Матчи: "
            f"{status.get('matches', 0)}"
        )

        print(
            f"Завершённые матчи: "
            f"{status.get('finished', 0)}"
        )

        print(
            f"Gold Dataset: "
            f"{status.get('gold_dataset', 0)}"
        )

        print(
            f"Learning Records: "
            f"{status.get('learning_records', 0)}"
        )

        print(
            f"Learning Events: "
            f"{status.get('learning_events', 0)}"
        )

        print(
            f"Team Passports: "
            f"{status.get('team_passports', 0)}"
        )

        print(
            f"Passport Meta: "
            f"{status.get('team_passport_meta', 0)}"
        )

        print(
            f"Schema: "
            f"{status.get('schema_version')}"
        )

        print(
            f"DB File: "
            f"{status.get('database_file')}"
        )

        print()

        print(
            "⚠️ Автоматическая синхронизация "
            "при запуске файла НЕ выполняется."
        )

        print()

        print(
            "Для синхронизации используйте:"
        )

        print(
            "  SyncEngine.sync_teams()"
        )

        print(
            "или:"
        )

        print(
            "  SyncEngine.load_passports()"
        )

    except Exception as e:

        logger.exception(
            "SyncEngine startup error"
        )

        print(
            f"❌ Ошибка: {e}"
        )
