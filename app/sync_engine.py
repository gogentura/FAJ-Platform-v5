#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Sync Engine — Единый модуль синхронизации
Паспорта команд вшиты в код (НЕ JSON!)
Работает ТОЛЬКО через FAJDatabase
"""

from app.database import FAJDatabase
from app.passports.rpl_2026_27 import RPL_PASSPORTS_2026_27, normalize_team_name
from datetime import datetime
import os
import shutil


# ============================================================
# КОНФИГУРАЦИЯ ЛИГ
# ============================================================

LEAGUE_CONFIG = {
    "РПЛ": {
        "teams": 16,
        "rounds": 30,
        "country": "Россия",
        "format": "double_round_robin"
    },
    "АПЛ": {
        "teams": 20,
        "rounds": 38,
        "country": "Англия",
        "format": "double_round_robin"
    },
    "Ла Лига": {
        "teams": 20,
        "rounds": 38,
        "country": "Испания",
        "format": "double_round_robin"
    },
    "Лига чемпионов": {
        "teams": 36,
        "rounds": 8,
        "country": "Европа",
        "format": "swiss_system",
        "playoff_start": 9,
        "direct_qualification": 8
    }
}


LEAGUE_DNA = {
    "mean_xg": 1.35,
    "home_advantage": 0.12,
    "avg_tempo": 72,
    "avg_goals_min": 2.35,
    "avg_goals_max": 2.55,
    "derby_factor": 1.08,
    "newcomer_motivation": 1.05,
    "first_rounds_bonus": 5
}


class SyncEngine:
    def __init__(self):
        self.db = FAJDatabase()
        self.passports = RPL_PASSPORTS_2026_27
        self.league_dna = LEAGUE_DNA
        self.league = "РПЛ"
        self.config = LEAGUE_CONFIG

    def _backup_database(self):
        from app.database import DB_FILE
        if not os.path.exists(DB_FILE):
            return None
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        backup_file = os.path.join(backup_dir, f"faj_{timestamp}.db")
        shutil.copy2(DB_FILE, backup_file)
        return backup_file

    def get_status(self, league="РПЛ"):
        full_status = self.db.get_status()
        tables = full_status.get("tables", {})
        teams = self.db.get_teams(league=league)
        matches = self.db.get_matches()
        return {
            "league": league,
            "teams": len(teams) if teams else 0,
            "matches": len(matches) if matches else 0,
            "finished": sum(1 for m in matches if m['status'] == 'finished') if matches else 0,
            "gold_dataset": tables.get("gold_dataset", 0),
            "learning_records": tables.get("learning_records", 0)
        }

    def _get_or_create_season(self, league="РПЛ", year="2026/27"):
        seasons = self.db.get_seasons()
        for s in seasons:
            if s['league'] == league and s['year'] == year:
                return s['id']
        season_id = self.db.create_season(
            name=f"{league} {year}",
            league=league,
            year=year
        )
        rounds_count = self.config.get(league, {}).get("rounds", 30)
        for i in range(1, rounds_count + 1):
            self.db.create_round(season_id, i)
        return season_id

    # ============================================================
    # PASSPORT SYNC (FAJ v12 COMPATIBILITY) — НОВЫЙ МЕТОД
    # ============================================================
    def sync_passports(self, league="РПЛ"):
        """
        Синхронизация паспортов команд.
        Используется UI и Diagnostic Service.
        Источник: встроенные FAJ паспорта.
        Хранилище: SQLite.
        """
        try:
            result = self.load_passports(league)
            return {
                "status": "success",
                "league": league,
                "updated": result.get("updated", 0),
                "total": result.get("total", 0)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    # ------------------------------------------------------------
    # PASSPORT LOADER
    # ------------------------------------------------------------
    def load_passports(self, league="РПЛ"):
        """Загружает паспорта из вшитых данных в SQLite (с разделением по слоям)"""
        season_id = self._get_or_create_season(league)
        teams = self.db.get_teams(league=league)
        updated = 0

        for team in teams:
            passport = self.passports.get(team['name'])
            if not passport:
                continue

            # 1. BASE
            base = passport.get("BASE", {})
            self.db.update_base(
                team['id'], season_id,
                attack=base.get("attack", 50),
                defense=base.get("defense", 50),
                control=base.get("control", 50),
                press=base.get("press", 50),
                tempo=base.get("tempo", 50),
                transition=base.get("transition", 50),
                finishing=base.get("finishing", 50),
                goalkeeper=base.get("goalkeeper", 50),
                coach_factor=base.get("coach_factor", 50),
                squad_quality=base.get("squad_quality", 50),
                bench_quality=base.get("bench_quality", 50),
                home_advantage=base.get("home_advantage", 1.0)
            )

            # 2. IDENTITY
            identity = passport.get("IDENTITY", {})
            self.db.update_identity(
                team['id'], season_id,
                style=identity.get("style", "mixed"),
                tempo=identity.get("tempo_style", "medium"),
                pressing=identity.get("pressing", "medium"),
                transition=identity.get("transition", "medium"),
                risk_level=identity.get("risk", "medium")
            )

            # 3. DYNAMIC_INITIAL
            dynamic_initial = passport.get("DYNAMIC_INITIAL", {})
            existing_dynamic = self.db.get_dynamic(team['id'], season_id)
            if not existing_dynamic:
                self.db.update_dynamic(
                    team['id'], season_id,
                    form=dynamic_initial.get("form", 50),
                    fitness=dynamic_initial.get("fitness", 50),
                    morale=dynamic_initial.get("morale", 50),
                    fatigue=dynamic_initial.get("fatigue", 50),
                    injury_index=dynamic_initial.get("injury_index", 0),
                    passport_confidence=dynamic_initial.get("passport_confidence", 0.4)
                )

            # 4. EXPERT — ПРЕОБРАЗУЕМ DICT В СТРОКИ
            expert = passport.get("EXPERT", {})
            
            # Преобразуем dict в строки для SQLite
            strengths = expert.get("strengths", {})
            weaknesses = expert.get("weaknesses", {})
            
            # Превращаем dict в строку вида "key:value, key2:value2"
            strengths_str = ", ".join([f"{k}:{v}" for k, v in strengths.items()]) if strengths else ""
            weaknesses_str = ", ".join([f"{k}:{v}" for k, v in weaknesses.items()]) if weaknesses else ""
            
            self.db.save_passport_meta(
                team['id'], season_id,
                {
                    "style": identity.get("style", ""),
                    "dna": expert.get("dna", ""),
                    "strengths": strengths_str,
                    "weaknesses": weaknesses_str,
                    "class": expert.get("class", ""),
                    "version": passport.get("version", "1.0"),
                    "source": passport.get("author", "FAJ Expert Layer")
                }
            )

            updated += 1

        return {
            "status": "success",
            "updated": updated,
            "total": len(teams)
        }

    # ------------------------------------------------------------
    # LEGACY SYNC
    # ------------------------------------------------------------
    def sync_teams(self, league="РПЛ"):
        backup_file = self._backup_database()
        teams = list(self.passports.keys())
        created = 0
        updated = 0
        for name in teams:
            existing_id = self.db.get_team_id(name, league)
            if existing_id:
                updated += 1
            else:
                team_id = self.db.add_team(name, league=league, country="Россия")
                if team_id:
                    created += 1
        self._get_or_create_season(league)
        passport_count = self.load_passports(league)
        return {
            "status": "success",
            "created": created,
            "updated": updated,
            "total": len(teams),
            "passports": passport_count.get("updated", 0),
            "backup": backup_file
        }

    # ------------------------------------------------------------
    # MATCHES
    # ------------------------------------------------------------
    def sync_matches(self, league="РПЛ"):
        return {
            "status": "pending",
            "loaded": 0,
            "message": "Ожидание парсера РПЛ"
        }

    # ------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------
    def sync_results(self, league="РПЛ"):
        return {
            "status": "pending",
            "updated": 0,
            "message": "Ожидание парсера РПЛ"
        }

    # ------------------------------------------------------------
    # GOLD DATASET
    # ------------------------------------------------------------
    def build_gold_dataset(self):
        from app.config import config
        matches = self.db.get_matches()
        finished = [m for m in matches if m['status'] == 'finished']
        count = 0
        for m in finished:
            gold = self.db.get_gold_by_match(m['id'])
            if gold and not gold['actual_score']:
                self.db.update_gold_actual(gold['id'], {
                    'actual_score': f"{m['actual_home']}:{m['actual_away']}",
                    'actual_home_goals': m['actual_home'],
                    'actual_away_goals': m['actual_away']
                })
                count += 1
            elif not gold:
                home = self.db.get_team(m['home_team_id'])
                away = self.db.get_team(m['away_team_id'])
                if home and away:
                    self.db.add_to_gold({
                        'match_id': m['id'],
                        'home_team': home['name'],
                        'away_team': away['name'],
                        'match_date': m.get('date', ''),
                        'model_version': config.MODEL_VERSION,
                        'faj_score': f"{m['actual_home']}:{m['actual_away']}",
                        'actual_score': f"{m['actual_home']}:{m['actual_away']}",
                        'actual_home_goals': m['actual_home'],
                        'actual_away_goals': m['actual_away'],
                        'status': 'completed'
                    })
                    count += 1
        return {
            "status": "success",
            "loaded": count
        }

    # ------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------
    def run_audit(self):
        try:
            from app.audit_engine import audit_all_pending
            results = audit_all_pending()
            return {
                "status": "success",
                "processed": len(results) if results else 0
            }
        except ImportError:
            return {
                "status": "error",
                "message": "audit_engine.py не найден"
            }

    # ------------------------------------------------------------
    # LEARNING
    # ------------------------------------------------------------
    def run_learning(self):
        try:
            from app.learning_engine import get_learning_report
            report = get_learning_report()
            return {
                "status": "success" if report['status'] != 'no_errors' else "empty",
                "report": report
            }
        except ImportError:
            return {
                "status": "error",
                "message": "learning_engine.py не найден"
            }


if __name__ == "__main__":
    sync = SyncEngine()
    print("🏆 Тест SyncEngine")
    print("=" * 40)
    status = sync.get_status()
    print(f"Команды: {status['teams']}")
    print(f"Матчи: {status['matches']}")
    print(f"Gold Dataset: {status['gold_dataset']}")
    print(f"Learning Records: {status['learning_records']}")
    print("\n🔄 Загрузка паспортов РПЛ 2026/27...")
    result = sync.load_passports()
    print(f"✅ Обновлено паспортов: {result['updated']}")
    print(f"✅ Всего команд: {result['total']}")
