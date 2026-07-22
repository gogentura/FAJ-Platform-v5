print("DEBUG: FootballDataClient загружен")

"""
Football-Data.org Client
FAJ Platform v5
"""

from app.config import Config

class FootballDataClient:
    def __init__(self):
        self.api_key = Config.FOOTBALL_DATA_KEY

    async def get_team_stats(self, team_name: str, league: str):
        return {
            "team": team_name,
            "league": league,
            "avg_goals": {
                "value": 1.50,
                "source": "football-data"
            },
            "avg_goals_conceded": {
                "value": 1.00,
                "source": "football-data"
            },
            "avg_possession": {
                "value": 52,
                "source": "football-data"
            },
            "historical_xg": {
                "value": 1.42,
                "source": "football-data"
            },
            "predicted_xg": {
                "value": None,
                "source": "faj"
            }
        }
