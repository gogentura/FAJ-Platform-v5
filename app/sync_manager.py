import asyncio
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
        source = self.league_source.get(league)
        if not source:
            return {"status": "error", "message": f"Неизвестная лига: {league}"}

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

        normalized = normalize_team_data(raw_data, source)
        # добавляем новые поля (пока по умолчанию, позже будут из экспертного слоя)
        normalized["efficiency"] = 50
        normalized["mentality"] = 50
        normalized["home_rating"] = 50
        normalized["away_rating"] = 50
        normalized["coach_factor"] = 0
        normalized["injury_index"] = 0
        normalized["fatigue_index"] = 0
        normalized["league"] = league

        passport = self._build_passport(normalized)
        for key in ["efficiency", "mentality", "home_rating", "away_rating", "coach_factor", "injury_index", "fatigue_index", "league"]:
            passport[key] = normalized.get(key)

        version = save_passport(team_name, passport)

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
        return {
            "xg": data["xg"],
            "goals": data["goals"],
            "possession": data["possession"],
            "form": data["form"],
            "avg_goals": data["goals"]["scored"],
            "avg_goals_conceded": data["goals"]["conceded"],
            "avg_possession": data["possession"],
            "historical_xg": data["xg"]["historical"],
        }

    async def update_rpl(self):
        teams = self.league_teams.get("RPL", [])
        results = []
        for team in teams:
            if is_updated_today(team):
                results.append({"team": team, "status": "skipped", "reason": "уже обновлён сегодня"})
                continue
            result = await self.update_team(team, "RPL")
            results.append(result)
            await asyncio.sleep(0.2)
        return {"status": "done", "results": results}

    def get_api_status(self):
        return get_api_status()
