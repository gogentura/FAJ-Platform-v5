import aiohttp
import logging

from app.config import Config


print("DEBUG: Новый APIClient загружен")


logger = logging.getLogger("FAJ.API")


TEAM_MAP = {
    "Спартак": "Spartak Moscow",
    "Spartak": "Spartak Moscow",

    "Зенит": "Zenit St Petersburg",
    "Zenit": "Zenit St Petersburg",

    "Реал": "Real Madrid",
    "Real": "Real Madrid",

    "Барселона": "Barcelona",
    "Barcelona": "Barcelona",

    "ЦСКА": "CSKA Moscow",
    "CSKA": "CSKA Moscow",
}


class APIClient:

    def __init__(self):
        self.api_key = Config.API_FOOTBALL_KEY
        self.base_url = "https://v3.football.api-sports.io"

        self.headers = {
            "x-apisports-key": self.api_key
        }


    async def get_team_stats(self, team_name: str):

        search_name = TEAM_MAP.get(team_name, team_name)

        logger.info(
            f"API-Football поиск: {search_name}"
        )

        url = f"{self.base_url}/teams"

        params = {
            "search": search_name
        }


        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                headers=self.headers,
                params=params
            ) as response:

                print("API STATUS:", response.status)

                data = await response.json()

                print("API RESPONSE:", data)


                if response.status != 200:
                    return None


                if data.get("results", 0) == 0:
                    return None


                team = data["response"][0]["team"]

                return {

                    "team": team["name"],

                    "avg_goals": {
                        "value": 1.5,
                        "source": "api-football"
                    },

                    "avg_goals_conceded": {
                        "value": 1.0,
                        "source": "api-football"
                    },

                    "avg_possession": {
                        "value": 50,
                        "source": "api-football"
                    },

                    "historical_xg": {
                        "value": 1.4,
                        "source": "faj"
                    },

                    "api_id": team["id"]
                }
