#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Passport Loader — Единый загрузчик паспортов
Загружает паспорта из вшитых данных в SQLite

Архитектура:
- Реестр лиг (PASSPORT_REGISTRY)
- Разделение на _save_base, _save_identity, _save_dynamic, _save_expert
- Журнал загрузки (passport_load_log)
- Контроль целостности после загрузки
"""

from app.database import FAJDatabase
from app.passports.rpl_2026_27 import RPL_PASSPORTS_2026_27, normalize_team_name
from app.passports.passport_schema import validate_passport
from datetime import datetime
import sqlite3


# ============================================================
# РЕЕСТР ЛИГ (расширяется без изменения кода)
# ============================================================

PASSPORT_REGISTRY = {
    "РПЛ": RPL_PASSPORTS_2026_27,
    # "АПЛ": EPL_PASSPORTS_2026_27,   # TODO: добавить позже
    # "Ла Лига": LALIGA_PASSPORTS_2026_27,
    # "Серия А": SERIEA_PASSPORTS_2026_27,
    # "Бундеслига": BUNDESLIGA_PASSPORTS_2026_27,
    # "Лига 1": LIGUE1_PASSPORTS_2026_27,
    # "Лига чемпионов": UCL_PASSPORTS_2026_27,
}


class PassportLoader:
    """
    Единый загрузчик паспортов для всех лиг
    """

    def __init__(self):
        self.db = FAJDatabase()
        self._cache = {}
        self._log = []

    # ============================================================
    # ПУБЛИЧНЫЙ ИНТЕРФЕЙС
    # ============================================================

    def get(self, league: str, team_name: str) -> dict:
        """Возвращает паспорт команды по названию лиги и команды"""
        normalized = normalize_team_name(team_name)
        cache_key = f"{league}:{normalized}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        passports = PASSPORT_REGISTRY.get(league)
        if not passports:
            return None

        passport = passports.get(normalized)
        if passport and validate_passport(passport, normalized):
            self._cache[cache_key] = passport
            return passport

        return None

    def load_league(self, league: str, season_id: int) -> dict:
        """Загружает все паспорта лиги в SQLite"""
        passports = PASSPORT_REGISTRY.get(league)
        if not passports:
            return {"status": "error", "message": f"Лига {league} не поддерживается"}

        teams = self.db.get_teams(league=league)
        if not teams:
            return {"status": "error", "message": f"Команды лиги {league} не найдены в БД"}

        updated = 0
        errors = []

        for team in teams:
            normalized = normalize_team_name(team['name'])
            passport = passports.get(normalized)

            if not passport:
                errors.append(f"Паспорт для {normalized} не найден")
                continue

            try:
                # 1. BASE
                self._save_base(team['id'], season_id, passport)

                # 2. IDENTITY
                self._save_identity(team['id'], season_id, passport)

                # 3. DYNAMIC_INITIAL (только если нет существующей динамики)
                self._save_dynamic(team['id'], season_id, passport)

                # 4. EXPERT
                self._save_expert(team['id'], season_id, passport)

                updated += 1
                self._add_log(league, team['name'], passport.get("version", "1.0"), "success")

            except Exception as e:
                errors.append(f"Ошибка загрузки {normalized}: {e}")
                self._add_log(league, team['name'], passport.get("version", "1.0"), "error")

        # Контроль целостности
        integrity = self._check_integrity(league, season_id, len(teams))

        return {
            "status": "success" if not errors else "partial",
            "updated": updated,
            "total": len(teams),
            "errors": errors,
            "integrity": integrity,
            "log": self._log
        }

    # ============================================================
    # ВНУТРЕННИЕ МЕТОДЫ ДЛЯ СОХРАНЕНИЯ СЛОЁВ
    # ============================================================

    def _save_base(self, team_id: int, season_id: int, passport: dict):
        """Сохраняет BASE слой"""
        base = passport.get("BASE", {})
        self.db.update_base(
            team_id, season_id,
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

    def _save_identity(self, team_id: int, season_id: int, passport: dict):
        """Сохраняет IDENTITY слой"""
        identity = passport.get("IDENTITY", {})
        self.db.update_identity(
            team_id, season_id,
            style=identity.get("style", "mixed"),
            tempo=identity.get("tempo_style", "medium"),
            pressing=identity.get("pressing", "medium"),
            transition=identity.get("transition", "medium"),
            risk_level=identity.get("risk", "medium")
        )

    def _save_dynamic(self, team_id: int, season_id: int, passport: dict):
        """Сохраняет DYNAMIC_INITIAL (только если нет существующей динамики)"""
        dynamic = passport.get("DYNAMIC_INITIAL", {})
        existing = self.db.get_dynamic(team_id, season_id)
        if not existing:
            self.db.update_dynamic(
                team_id, season_id,
                form=dynamic.get("form", 50),
                fitness=dynamic.get("fitness", 50),
                morale=dynamic.get("morale", 50),
                fatigue=dynamic.get("fatigue", 50),
                injury_index=dynamic.get("injury_index", 0),
                passport_confidence=dynamic.get("passport_confidence", 0.4)
            )

    def _save_expert(self, team_id: int, season_id: int, passport: dict):
        """Сохраняет EXPERT слой"""
        expert = passport.get("EXPERT", {})
        identity = passport.get("IDENTITY", {})
        self.db.save_passport_meta(
            team_id, season_id,
            {
                "style": identity.get("style", ""),
                "dna": expert.get("dna", ""),
                "strengths": expert.get("strengths", {}),
                "weaknesses": expert.get("weaknesses", {}),
                "class": expert.get("class", ""),
                "version": passport.get("version", "1.0"),
                "source": passport.get("author", "FAJ Expert Layer")
            }
        )

    # ============================================================
    # ЖУРНАЛ ЗАГРУЗКИ
    # ============================================================

    def _add_log(self, league: str, team_name: str, version: str, status: str):
        """Добавляет запись в журнал загрузки"""
        self._log.append({
            "league": league,
            "team": team_name,
            "version": version,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })

    def save_log(self):
        """Сохраняет журнал в БД (таблица passport_load_log)"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS passport_load_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT,
                team_name TEXT,
                passport_version TEXT,
                status TEXT,
                loaded_at TEXT
            )
        """)

        for entry in self._log:
            cursor.execute("""
                INSERT INTO passport_load_log
                (league, team_name, passport_version, status, loaded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entry["league"],
                entry["team"],
                entry["version"],
                entry["status"],
                entry["timestamp"]
            ))

        conn.commit()
        conn.close()

    # ============================================================
    # КОНТРОЛЬ ЦЕЛОСТНОСТИ
    # ============================================================

    def _check_integrity(self, league: str, season_id: int, expected: int) -> dict:
        """Проверяет, что все слои загружены корректно"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Считаем количество записей в каждом слое
        cursor.execute("""
            SELECT COUNT(*) FROM team_base tb
            JOIN teams t ON tb.team_id = t.id
            WHERE t.league = ? AND tb.season_id = ?
        """, (league, season_id))
        base_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM team_identity ti
            JOIN teams t ON ti.team_id = t.id
            WHERE t.league = ? AND ti.season_id = ?
        """, (league, season_id))
        identity_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM team_dynamic td
            JOIN teams t ON td.team_id = t.id
            WHERE t.league = ? AND td.season_id = ?
        """, (league, season_id))
        dynamic_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM team_passport_meta tpm
            JOIN teams t ON tpm.team_id = t.id
            WHERE t.league = ? AND tpm.season_id = ?
        """, (league, season_id))
        expert_count = cursor.fetchone()[0]

        conn.close()

        return {
            "expected": expected,
            "base": base_count,
            "identity": identity_count,
            "dynamic": dynamic_count,
            "expert": expert_count,
            "all_ok": all([
                base_count == expected,
                identity_count == expected,
                dynamic_count == expected,
                expert_count == expected
            ])
        }


# ============================================================
# ТЕСТОВЫЙ ЗАПУСК
# ============================================================

if __name__ == "__main__":
    loader = PassportLoader()
    db = FAJDatabase()

    # Находим сезон РПЛ
    seasons = db.get_seasons()
    season_id = None
    for s in seasons:
        if s['league'] == "РПЛ":
            season_id = s['id']
            break

    if not season_id:
        print("❌ Сезон РПЛ не найден. Сначала создайте сезон через SyncEngine.")
    else:
        print("🚀 Загрузка паспортов РПЛ 2026/27...")
        result = loader.load_league("РПЛ", season_id)

        print(f"\n✅ Обновлено паспортов: {result['updated']}")
        print(f"✅ Всего команд: {result['total']}")

        if result.get("errors"):
            print("\n⚠️ Ошибки:")
            for err in result["errors"]:
                print(f"  {err}")

        integrity = result.get("integrity", {})
        if integrity.get("all_ok"):
            print("\n✅ Контроль целостности пройден:")
            print(f"  BASE: {integrity['base']}/{integrity['expected']}")
            print(f"  IDENTITY: {integrity['identity']}/{integrity['expected']}")
            print(f"  DYNAMIC: {integrity['dynamic']}/{integrity['expected']}")
            print(f"  EXPERT: {integrity['expert']}/{integrity['expected']}")
        else:
            print("\n❌ Ошибка целостности:")
            print(f"  BASE: {integrity.get('base', 0)}/{integrity.get('expected', 0)}")
            print(f"  IDENTITY: {integrity.get('identity', 0)}/{integrity.get('expected', 0)}")
            print(f"  DYNAMIC: {integrity.get('dynamic', 0)}/{integrity.get('expected', 0)}")
            print(f"  EXPERT: {integrity.get('expert', 0)}/{integrity.get('expected', 0)}")

        # Сохраняем журнал
        loader.save_log()
        print("\n✅ Журнал загрузки сохранён")
