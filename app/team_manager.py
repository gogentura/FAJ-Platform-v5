#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11
Team Manager

Управление командами в базе данных:
- добавление команд
- получение команд
- обновление информации о команде
"""

from app.storage import get_storage


class TeamManager:
    """Управление командами FAJ"""

    def __init__(self):
        self.storage = get_storage()

    def add_team(self, name, league, country=""):
        """Добавить команду в базу"""
        # Проверяем, не существует ли уже
        existing = self.storage.get_team_id(name)
        if existing:
            return {"status": "exists", "team_id": existing}

        team_id = self.storage.add_team(name, league, country)
        return {"status": "created", "team_id": team_id}

    def get_team(self, name):
        """Получить команду по названию"""
        team_id = self.storage.get_team_id(name)
        if not team_id:
            return None

        # Получаем все команды и ищем нужную
        teams = self.storage.get_teams()
        for team in teams:
            if team['id'] == team_id:
                return dict(team)
        return None

    def get_all_teams(self, league=None):
        """Получить все команды (по лиге или все)"""
        return self.storage.get_teams(league)

    def get_teams_by_league(self, league):
        """Получить команды по лиге"""
        return self.storage.get_teams(league)

    def update_team(self, team_id, **kwargs):
        """Обновить информацию о команде"""
        # TODO: добавить метод обновления в storage
        pass

    def add_default_teams(self):
        """Добавить стандартный набор команд для РПЛ"""
        rpl_teams = [
            ("Зенит", "RPL", "Россия"),
            ("Спартак", "RPL", "Россия"),
            ("ЦСКА", "RPL", "Россия"),
            ("Динамо М", "RPL", "Россия"),
            ("Краснодар", "RPL", "Россия"),
            ("Локомотив", "RPL", "Россия"),
            ("Ростов", "RPL", "Россия"),
            ("Рубин", "RPL", "Россия"),
            ("Ахмат", "RPL", "Россия"),
            ("Оренбург", "RPL", "Россия"),
            ("Крылья Советов", "RPL", "Россия"),
            ("Факел", "RPL", "Россия"),
            ("Балтика", "RPL", "Россия"),
            ("Динамо Мх", "RPL", "Россия"),
            ("Акрон", "RPL", "Россия"),
            ("Родина", "RPL", "Россия"),
        ]

        results = []
        for name, league, country in rpl_teams:
            result = self.add_team(name, league, country)
            results.append({"team": name, "result": result})

        return results


# =========================================================
# КОМАНДЫ ДЛЯ ДРУГИХ ЛИГ
# =========================================================

EPL_TEAMS = [
    ("Arsenal", "EPL", "Англия"),
    ("Liverpool", "EPL", "Англия"),
    ("Manchester City", "EPL", "Англия"),
    ("Chelsea", "EPL", "Англия"),
    ("Manchester United", "EPL", "Англия"),
    ("Tottenham", "EPL", "Англия"),
    ("Newcastle", "EPL", "Англия"),
    ("Aston Villa", "EPL", "Англия"),
]

LALIGA_TEAMS = [
    ("Real Madrid", "LaLiga", "Испания"),
    ("Barcelona", "LaLiga", "Испания"),
    ("Atletico Madrid", "LaLiga", "Испания"),
    ("Athletic Bilbao", "LaLiga", "Испания"),
    ("Real Sociedad", "LaLiga", "Испания"),
    ("Sevilla", "LaLiga", "Испания"),
    ("Valencia", "LaLiga", "Испания"),
    ("Betis", "LaLiga", "Испания"),
]


# =========================================================
# ИСПОЛЬЗОВАНИЕ
# =========================================================

if __name__ == "__main__":
    tm = TeamManager()

    # Добавляем РПЛ
    print("Добавление команд РПЛ...")
    results = tm.add_default_teams()
    for r in results:
        print(f"  {r['team']}: {r['result']['status']}")

    # Показываем все команды
    print("\nВсе команды в БД:")
    teams = tm.get_all_teams()
    for t in teams:
        print(f"  {t['name']} ({t['league']})")
