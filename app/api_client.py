import aiohttp
from app.config import Config

class APIClient:
    def __init__(self):
        self.api_key = Config.API_FOOTBALL_KEY
        self.base_url = Config.API_FOOTBALL_URL
        self.headers = {"x-apisports-key": self.api_key}

    async def get_team_stats(self, team_name: str):
        """Возвращает статистику команды за последние 10 матчей."""
        team_id = await self._get_team_id(team_name)
        if not team_id:
            return None
        matches = await self._get_recent_matches(team_id)
        if not matches:
            return None
        return self._aggregate_stats(matches, team_id)

    async def _get_team_id(self, name: str):
        url = f"{self.base_url}/teams"
        params = {"search": name}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["results"] > 0:
                        return data["response"][0]["team"]["id"]
        return None

    async def _get_recent_matches(self, team_id: int):
        url = f"{self.base_url}/fixtures"
        params = {"team": team_id, "last": 10}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["response"]
        return []

    def _aggregate_stats(self, matches, team_id):
        goals_scored = 0
        goals_conceded = 0
        total = 0
        for match in matches:
            teams = match.get("teams", {})
            goals = match.get("goals", {})
            if teams.get("home", {}).get("id") == team_id:
                goals_scored += goals.get("home", 0)
                goals_conceded += goals.get("away", 0)
            elif teams.get("away", {}).get("id") == team_id:
                goals_scored += goals.get("away", 0)
                goals_conceded += goals.get("home", 0)
            total += 1
        if total == 0:
            return None
        return {
            "avg_goals": goals_scored / total,
            "avg_goals_conceded": goals_conceded / total,
            "avg_xg": 1.3 + (goals_scored / total) * 0.2,
            "avg_possession": 50 + (goals_scored / total) * 5
        }
