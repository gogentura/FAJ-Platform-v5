#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11
Passport Manager

Управление паспортами команд:
- создание паспортов
- обновление показателей
- получение паспортов
"""

from app.storage import get_storage


class PassportManager:
    """Управление паспортами команд FAJ"""

    def __init__(self):
        self.storage = get_storage()

    def create_passport(self, team_id, **kwargs):
        """
        Создать паспорт для команды

        Args:
            team_id: ID команды
            **kwargs: Показатели (attack, defense, control, и т.д.)
        """
        default_passport = {
            "attack": kwargs.get("attack", 50),
            "defense": kwargs.get("defense", 50),
            "control": kwargs.get("control", 50),
            "press": kwargs.get("press", 50),
            "tempo": kwargs.get("tempo", 50),
            "transition": kwargs.get("transition", 50),
            "fitness": kwargs.get("fitness", 50),
            "mentality": kwargs.get("mentality", 50),
            "coach_factor": kwargs.get("coach_factor", 50),
        }

        self.storage.update_passport(team_id, **default_passport)
        return {"status": "created", "team_id": team_id}

    def get_passport(self, team_id):
        """Получить паспорт команды"""
        return self.storage.get_passport(team_id)

    def get_passport_by_name(self, team_name):
        """Получить паспорт по названию команды"""
        team_id = self.storage.get_team_id(team_name)
        if not team_id:
            return None
        return self.get_passport(team_id)

    def update_passport(self, team_id, **kwargs):
        """Обновить показатели паспорта"""
        # Проверяем, существует ли паспорт
        existing = self.get_passport(team_id)
        if not existing:
            # Если нет — создаём
            return self.create_passport(team_id, **kwargs)

        # Обновляем существующий
        self.storage.update_passport(team_id, **kwargs)
        return {"status": "updated", "team_id": team_id}

    def get_all_passports(self, league=None):
        """Получить все паспорта (по лиге или все)"""
        teams = self.storage.get_teams(league)
        passports = []
        for team in teams:
            passport = self.get_passport(team["id"])
            if passport:
                passports.append({
                    "team": team["name"],
                    "league": team["league"],
                    **passport
                })
        return passports

    def create_passports_for_league(self, league):
        """Создать паспорта для всех команд в лиге"""
        teams = self.storage.get_teams(league)
        results = []
        for team in teams:
            result = self.create_passport(team["id"])
            results.append({"team": team["name"], "result": result})
        return results


# =========================================================
# ИСПОЛЬЗОВАНИЕ
# =========================================================

if __name__ == "__main__":
    pm = PassportManager()

    # Создаём паспорта для всех команд РПЛ
    print("Создание паспортов для РПЛ...")
    results = pm.create_passports_for_league("RPL")
    for r in results:
        print(f"  {r['team']}: {r['result']['status']}")

    # Показываем все паспорта
    print("\nВсе паспорта:")
    passports = pm.get_all_passports()
    for p in passports:
        print(f"  {p['team']}: attack={p['attack']}, defense={p['defense']}")
