"""
SyncManager — управляет синхронизацией данных из разных источников
"""

import asyncio
from datetime import datetime
from app.api_client import APIClient
from app.football_data_client import FootballDataClient
from app.data_fusion import normalize_team_data
from app.passport_manager import save_passport, load_passport, is_updated_today
from app.api_tracker import increment_usage, get_api_status
from app.config import Config

class SyncManager:
    def __init__(self):
        self.api_football = APIClient()
        self.football_data = FootballDataClient()
        self.league_source = Config.SUPPORTED_LEAGUES
        self.league_teams = Config.LEAGUE_TEAMS

    async def update_team(self, team_name: str, league: str = "RPL") -> dict:
        # Определяем источник
        source = self.league_source.get(league)
        if not source:
            return {"status": "error", "message": f"Неизвестная лига: {league}"}

        # Проверяем, обновлялась ли команда сегодня
        if is_updated_today(team_name):
            cached = load_passport(team_name)
            if cached:
                return {
                    "status": "cached",
                    "team": team_name,
                    "passport": cached,
                    "source": "cache",
                    "message": "Использован локальный паспорт (обновлён сегодня)"
                }

        # Запрос к API
        if source == "api-football":
            raw_data = await self.api_football.get_team_stats(team_name)
            if not raw_data:
                cached = load_passport(team_name)
                if cached:
                    return {
                        "status": "cached",
                        "team": team_name,
                        "passport": cached,
                        "source": "cache",
                        "message": "Использован локальный паспорт (API недоступен)"
                    }
                return {"status": "error", "message": f"Команда {team_name} не найдена в API-Football"}
            # Увеличиваем счётчик только при успешном запросе
            increment_usage()
        elif source == "football-data":
            raw_data = await self.football_data.get_team_stats(team_name, league)
            if not raw_data:
                cached = load_passport(team_name)
                if cached:
                    return {
                        "status": "cached",
                        "team": team_name,
                        "passport": cached,
                        "source": "cache",
                        "message": "Использован локальный паспорт (API недоступен)"
                    }
                return {"status": "error", "message": f"Команда {team_name} не найдена в Football-Data.org"}
        else:
            return {"status": "error", "message": f"Неизвестный источник: {source}"}

        # Нормализуем данные
        normalized = normalize_team_data(raw_data, source)

        # Строим паспорт (без predicted_xg, только исторический)
        passport = self._build_passport(normalized)

        # Сохраняем паспорт
        version = save_passport(team_name, passport)

        # Автоматическая перекалибровка (заглушка)
        # Здесь можно вызвать Rating Engine, Passport Optimizer, FAJ Calibration
        # Пока просто логируем
        print(f"[SyncManager] Паспорт {team_name} v{version} сохранён и перекалиброван")

        return {
            "status": "ok",
            "team": team_name,
            "league": league,
            "source": source,
            "version": version,
            "passport": passport,
            "historical_xg": passport["xg"]["historical"]["value"],
            "message": f"Паспорт {team_name} обновлён (v{version})"
        }

    def _build_passport(self, data: dict) -> dict:
        # Извлекаем данные из нормализованной структуры
        goals_scored = data["goals"]["scored"]["value"]
        goals_conceded = data["goals"]["conceded"]["value"]
        possession = data["possession"]["value"]
        hist_xg = data["xg"]["historical"]["value"]
        form = data["form"]

        # attack будет пересчитан в save_passport с учётом historical_xg
        # Здесь сохраняем все сырые данные
        return {
            "xg": data["xg"],  # historical + predicted (predicted пока None)
            "goals": data["goals"],
            "possession": data["possession"],
            "form": form,
            "avg_goals": data["goals"]["scored"],
            "avg_goals_conceded": data["goals"]["conceded"],
            "avg_possession": data["possession"],
            "historical_xg": data["xg"]["historical"],  # для совместимости
        }

    async def update_rpl(self):
        teams = self.league_teams.get("RPL", [])
        results = []
        for team in teams:
            if is_updated_today(team):
                results.append({
                    "team": team,
                    "status": "skipped",
                    "reason": "уже обновлён сегодня"
                })
                continue
            result = await self.update_team(team, "RPL")
            results.append(result)
            await asyncio.sleep(0.2)
        return {"status": "done", "results": results}

    def get_api_status(self):
        return get_api_status()
