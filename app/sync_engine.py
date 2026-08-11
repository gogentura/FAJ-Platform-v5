#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ Sync Engine
============================================================

РОЛЬ:
    Единый модуль синхронизации FAJ.

ПРИНЦИП:
    SyncEngine НЕ работает с SQLite напрямую.
    Все операции с БД идут через FAJDatabase.

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

ВАЖНО:
    - Не удаляет данные.
    - Повторный запуск должен быть идемпотентным.
    - Перед изменением БД создаётся backup.
    - Наличие команды НЕ означает наличие паспорта.
      Паспорта синхронизируются отдельно.
"""

from app.database import FAJDatabase
from app.passports.passport_manager import get_passport_manager
from app.passports.rpl_2026_27 import (
    RPL_PASSPORTS_2026_27,
    normalize_team_name,
)

from datetime import datetime
import os
import shutil
import logging


logger = logging.getLogger(__name__)


# ============================================================
# КОНФИГУРАЦИЯ ЛИГ
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


class SyncEngine:

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self):
        self.db = FAJDatabase()

        self.passport_manager = get_passport_manager()

        self.passports = RPL_PASSPORTS_2026_27

        self.league_dna = LEAGUE_DNA

        self.league = "РПЛ"

        self.config = LEAGUE_CONFIG

    # ========================================================
    # DATABASE BACKUP
    # ========================================================

    def _backup_database(self):
        """
        Создаёт резервную копию faj.db перед синхронизацией.

        ВАЖНО:
            Никакого удаления старой БД.
            Backup создаётся только если файл существует.
        """

        from app.database import DB_FILE

        if not os.path.exists(DB_FILE):
            logger.warning(
                f"Database file does not exist yet: {DB_FILE}"
            )
            return None

        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime(
            "%Y_%m_%d_%H_%M_%S"
        )

        backup_file = os.path.join(
            backup_dir,
            f"faj_{timestamp}.db"
        )

        try:
            shutil.copy2(DB_FILE, backup_file)

            logger.info(
                f"Database backup created: {backup_file}"
            )

            return backup_file

        except Exception as e:
            logger.error(
                f"Database backup failed: {e}"
            )
            raise

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(self, league="РПЛ"):
        """
        Возвращает текущее состояние синхронизации.

        ВАЖНО:
            database.get_status()["tables"] является списком
            названий таблиц, а НЕ словарём с количеством записей.

            Поэтому количество записей получаем через
            FAJDatabase.get_table_count().
        """

        full_status = self.db.get_status()

        teams = self.db.get_teams(league=league)
        matches = self.db.get_matches()

        finished = 0

        if matches:
            finished = sum(
                1
                for match in matches
                if match["status"] == "finished"
            )

        return {
            "status": full_status.get(
                "status",
                "unknown"
            ),

            "league": league,

            "teams": len(teams) if teams else 0,

            "matches": len(matches) if matches else 0,

            "finished": finished,

            "gold_dataset": self.db.get_table_count(
                "gold_dataset"
            ),

            "learning_records": self.db.get_table_count(
                "learning_records"
            ),

            "learning_events": self.db.get_table_count(
                "learning_events"
            ),

            "team_passports": self.db.get_table_count(
                "team_passports"
            ),

            "team_passport_meta": self.db.get_table_count(
                "team_passport_meta"
            ),

            "schema_version": full_status.get(
                "schema_version"
            ),

            "database_file": full_status.get(
                "file"
            ),

            "tables": full_status.get(
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
        Получает существующий сезон либо создаёт его.

        После создания сезона создаются необходимые туры.

        create_round() в database.py идемпотентен,
        поэтому повторный запуск не должен создавать дубли.
        """

        seasons = self.db.get_seasons()

        for season in seasons:

            if (
                season["league"] == league
                and season["year"] == year
            ):
                return season["id"]

        season_id = self.db.create_season(
            name=f"{league} {year}",
            league=league,
            year=year,
        )

        rounds_count = self.config.get(
            league,
            {}
        ).get(
            "rounds",
            30
        )

        for round_number in range(
            1,
            rounds_count + 1
        ):
            self.db.create_round(
                season_id,
                round_number
            )

        logger.info(
            f"Season created: "
            f"{league} {year}, "
            f"season_id={season_id}"
        )

        return season_id

    # ========================================================
    # PASSPORT SYNC
    # ========================================================

    def sync_passports(self, league="РПЛ"):
        """
        Публичный метод синхронизации паспортов.
        """

        try:

            result = self.load_passports(
                league
            )

            return {
                "status": "success",
                "league": league,
                "updated": result.get(
                    "updated",
                    0
                ),
                "total": result.get(
                    "total",
                    0
                ),
            }

        except Exception as e:

            logger.exception(
                "Passport synchronization failed"
            )

            return {
                "status": "error",
                "league": league,
                "message": str(e),
            }

    # ========================================================
    # LOAD PASSPORTS
    # ========================================================

    def load_passports(self, league="РПЛ"):
        """
        Загружает паспорта через PassportManager.

        ВАЖНО:

        Наличие команды в teams НЕ означает,
        что паспорт существует.

        Поэтому паспорт проверяется для КАЖДОЙ команды.
        """

        season_id = self._get_or_create_season(
            league
        )

        teams = self.db.get_teams(
            league=league
        )

        updated = 0

        for team in teams:

            team_name = team["name"]

            # ------------------------------------------------
            # Нормализация названия
            # ------------------------------------------------

            team_name_normalized = normalize_team_name(
                team_name
            )

            passport = self.passports.get(
                team_name_normalized
            )

            if not passport:

                passport = self.passports.get(
                    team_name
                )

            if not passport:

                logger.warning(
                    f"Паспорт не найден для команды: "
                    f"{team_name}"
                )

                continue

            # ------------------------------------------------
            # Разделы паспорта
            # ------------------------------------------------

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

            expert = passport.get(
                "EXPERT",
                {}
            )

            # ------------------------------------------------
            # PASSPORT DATA
            # ------------------------------------------------

            passport_data = {

                "attack": base.get(
                    "attack",
                    50
                ),

                "defense": base.get(
                    "defense",
                    50
                ),

                "control": base.get(
                    "control",
                    50
                ),

                "tempo": base.get(
                    "tempo",
                    50
                ),

                "press": base.get(
                    "press",
                    50
                ),

                "transition": base.get(
                    "transition",
                    50
                ),

                "finishing": base.get(
                    "finishing",
                    50
                ),

                "goalkeeper": base.get(
                    "goalkeeper",
                    50
                ),

                "discipline": base.get(
                    "discipline",
                    50
                ),

                "squad_quality": base.get(
                    "squad_quality",
                    50
                ),

                "bench_quality": base.get(
                    "bench_quality",
                    50
                ),

                "coach_factor": base.get(
                    "coach_factor",
                    50
                ),

                "mental": identity.get(
                    "mental",
                    50
                ),

                "home_strength":
                    base.get(
                        "home_advantage",
                        1.0
                    ) * 50,

                "away_strength":
                    base.get(
                        "home_advantage",
                        1.0
                    ) * 40,

                "injury_factor":
                    dynamic_initial.get(
                        "injury_index",
                        0
                    ),

                "key_player_loss": 0,

                "league_adaptation": 80,

                "form":
                    dynamic_initial.get(
                        "form",
                        50
                    ),

                "results_strength": 0,

                "opponent_strength": 0,

                "matches_count": 0,

                "created_at":
                    datetime.now().isoformat(),
            }

            # ------------------------------------------------
            # PASSPORT MANAGER
            # ------------------------------------------------

            existing_passport = (
                self.passport_manager
                .get_current_passport(
                    team["id"],
                    season_id
                )
            )

            if existing_passport:

                # ВАЖНО:
                #
                # Здесь пока сохраняем существующую
                # архитектуру update_passport().
                #
                # Перед изменением этой логики необходимо
                # проверить passport_manager.py,
                # потому что неизвестно, ожидает ли
                # update_passport абсолютные значения
                # или delta.

                changes = {}

                for key in passport_data:

                    if (
                        key in existing_passport
                        and isinstance(
                            passport_data[key],
                            (int, float)
                        )
                        and isinstance(
                            existing_passport[key],
                            (int, float)
                        )
                    ):

                        if (
                            passport_data[key]
                            != existing_passport[key]
                        ):

                            changes[key] = (
                                passport_data[key]
                                - existing_passport[key]
                            )

                if changes:

                    self.passport_manager.update_passport(
                        team_id=team["id"],
                        season_id=season_id,
                        changes=changes,
                        source="sync",
                        opponent_rating=70,
                        matches_count=0
                    )

            else:

                self.passport_manager.create_passport(
                    team_id=team["id"],
                    season_id=season_id,
                    data=passport_data,
                    source=passport.get(
                        "author",
                        "sync"
                    )
                )

            # ------------------------------------------------
            # LEGACY TEAM BASE
            # ------------------------------------------------

            self.db.update_base(
                team["id"],
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

            # ------------------------------------------------
            # LEGACY TEAM IDENTITY
            # ------------------------------------------------

            self.db.update_identity(
                team["id"],
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

            # ------------------------------------------------
            # LEGACY TEAM DYNAMIC
            # ------------------------------------------------

            existing_dynamic = (
                self.db.get_dynamic(
                    team["id"],
                    season_id
                )
            )

            if not existing_dynamic:

                self.db.update_dynamic(
                    team["id"],
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

            # ------------------------------------------------
            # TEAM PASSPORT META
            # ------------------------------------------------

            strengths = expert.get(
                "strengths",
                {}
            )

            weaknesses = expert.get(
                "weaknesses",
                {}
            )

            strengths_str = (
                ", ".join(
                    f"{key}:{value}"
                    for key, value in strengths.items()
                )
                if strengths
                else ""
            )

            weaknesses_str = (
                ", ".join(
                    f"{key}:{value}"
                    for key, value in weaknesses.items()
                )
                if weaknesses
                else ""
            )

            self.db.save_passport_meta(
                team["id"],
                season_id,
                {
                    "style": identity.get(
                        "style",
                        ""
                    ),

                    "dna": expert.get(
                        "dna",
                        ""
                    ),

                    "strengths": strengths_str,

                    "weaknesses": weaknesses_str,

                    "class": expert.get(
                        "class",
                        ""
                    ),

                    "version": passport.get(
                        "version",
                        "1.0"
                    ),

                    "source": passport.get(
                        "author",
                        "FAJ Expert Layer"
                    ),
                }
            )

            updated += 1

            logger.info(
                f"Passport synchronized: "
                f"{team_name}"
            )

        logger.info(
            f"Загружено паспортов: "
            f"{updated} из {len(teams)}"
        )

        return {
            "updated": updated,
            "total": len(teams)
        }

    # ========================================================
    # TEAM SYNC
    # ========================================================

    def sync_teams(self, league="РПЛ"):
        """
        Синхронизация команд.

        ВАЖНО:
            Существующая команда не пропускает
            паспортную синхронизацию.

        Сначала команды,
        затем отдельная синхронизация паспортов.
        """

        backup_file = self._backup_database()

        teams = list(
            self.passports.keys()
        )

        created = 0
        updated = 0

        for name in teams:

            existing_id = self.db.get_team_id(
                name,
                league
            )

            if existing_id:

                updated += 1

            else:

                team_id = self.db.add_team(
                    name,
                    league=league,
                    country=self.config.get(
                        league,
                        {}
                    ).get(
                        "country",
                        "Россия"
                    )
                )

                if team_id:
                    created += 1

        # ----------------------------------------------------
        # Season + rounds
        # ----------------------------------------------------

        self._get_or_create_season(
            league
        )

        # ----------------------------------------------------
        # Passports
        # ----------------------------------------------------

        passport_count = self.load_passports(
            league
        )

        return {
            "status": "success",

            "created": created,

            "updated": updated,

            "total": len(teams),

            "passports": passport_count.get(
                "updated",
                0
            ),

            "backup": backup_file,
        }

    # ========================================================
    # MATCHES
    # ========================================================

    def sync_matches(self, league="РПЛ"):
        """
        Матчи пока загружаются отдельным парсером.
        """

        return {
            "status": "pending",
            "loaded": 0,
            "message": "Ожидание парсера РПЛ",
        }

    # ========================================================
    # RESULTS
    # ========================================================

    def sync_results(self, league="РПЛ"):
        """
        Результаты пока загружаются отдельным парсером.
        """

        return {
            "status": "pending",
            "updated": 0,
            "message": "Ожидание парсера РПЛ",
        }

    # ========================================================
    # GOLD DATASET
    # ========================================================

    def build_gold_dataset(self):
        """
        Создаёт/обновляет Gold Dataset.

        ВАЖНО:
            Этот метод пока НЕ используется как источник
            обучения модели.

            Нельзя считать фактический результат
            прогнозом FAJ.

            Полная корректировка Gold Dataset будет
            выполняться после проверки prediction pipeline.
        """

        from app.config import config

        matches = self.db.get_matches()

        finished = [
            match
            for match in matches
            if match["status"] == "finished"
        ]

        count = 0

        for match in finished:

            gold = self.db.get_gold_by_match(
                match["id"]
            )

            # ------------------------------------------------
            # Gold уже существует
            # ------------------------------------------------

            if gold:

                if not gold["actual_score"]:

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
            # Новый Gold
            #
            # ВАЖНО:
            # Пока сохраняем существующую архитектуру.
            # Перед включением обучения необходимо
            # связать Gold с реальным prediction_id.
            # ------------------------------------------------

            home = self.db.get_team(
                match["home_team_id"]
            )

            away = self.db.get_team(
                match["away_team_id"]
            )

            if not home or not away:
                continue

            self.db.add_to_gold(
                {
                    "match_id": match["id"],

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

                    # ВНИМАНИЕ:
                    # Это временная legacy-логика.
                    # Не считать данный результат
                    # полноценным FAJ-прогнозом.

                    "faj_score":
                        f"{match['actual_home']}:"
                        f"{match['actual_away']}",

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
            "status": "success",
            "loaded": count,
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
                "status": "success",
                "processed":
                    len(results)
                    if results
                    else 0,
            }

        except ImportError:

            return {
                "status": "error",
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
                    if report["status"] != "no_errors"
                    else "empty",

                "report": report,
            }

        except ImportError:

            return {
                "status": "error",
                "message":
                    "learning_engine.py не найден",
            }


# ============================================================
# DIRECT RUN
# ============================================================

if __name__ == "__main__":

    sync = SyncEngine()

    print("🏆 FAJ SyncEngine v12.1")
    print("=" * 50)

    status = sync.get_status()

    print(
        f"Статус БД: "
        f"{status.get('status', 'unknown')}"
    )

    print(
        f"Команды: "
        f"{status['teams']}"
    )

    print(
        f"Матчи: "
        f"{status['matches']}"
    )

    print(
        f"Завершённые матчи: "
        f"{status['finished']}"
    )

    print(
        f"Gold Dataset: "
        f"{status['gold_dataset']}"
    )

    print(
        f"Learning Records: "
        f"{status['learning_records']}"
    )

    print(
        f"Learning Events: "
        f"{status['learning_events']}"
    )

    print(
        f"Team Passports: "
        f"{status['team_passports']}"
    )

    print(
        f"Passport Meta: "
        f"{status['team_passport_meta']}"
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

    print(
        "Для загрузки паспортов используйте "
        "SyncEngine.sync_teams() или "
        "SyncEngine.load_passports()."
    )
