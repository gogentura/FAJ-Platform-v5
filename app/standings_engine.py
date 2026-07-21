import aiohttp
from app.config import Config

class StandingsEngine:
    def __init__(self):
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {"X-Auth-Token": Config.FOOTBALL_DATA_KEY}

    async def get_team_standing(self, team_name: str, league: str = "RPL"):
        league_id = self._get_league_id(league)
        if not league_id:
            return None
        url = f"{self.base_url}/competitions/{league_id}/standings"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for table in data.get("standings", []):
                        for entry in table.get("table", []):
                            if entry["team"]["name"].lower() == team_name.lower():
                                return {
                                    "position": entry["position"],
                                    "played": entry["playedGames"],
                                    "points": entry["points"],
                                    "goals_diff": entry["goalDifference"]
                                }
        return None

    def _get_league_id(self, league: str) -> str:
        mapping = {
            "EPL": "PL",
            "LaLiga": "PD",
            "Bundesliga": "BL1",
            "SerieA": "SA",
            "Ligue1": "FL1",
            "UCL": "CL",
            "RPL": "RPL"  # может не работать в бесплатной версии
        }
        return mapping.get(league, "")
