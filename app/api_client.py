import aiohttp
import logging
from app.config import Config

logger = logging.getLogger("FAJ.API")


TEAM_MAP = {
    "Зенит": "Zenit St Petersburg",
    "Zenit": "Zenit St Petersburg",

    "Спартак": "Spartak Moscow",
    "Spartak": "Spartak Moscow",

    "ЦСКА": "CSKA Moscow",
    "CSKA": "CSKA Moscow",

    "Динамо": "Dynamo Moscow",
    "Dynamo": "Dynamo Moscow",

    "Краснодар": "Krasnodar",
    "Krasnodar": "Krasnodar",

    "Реал": "Real Madrid",
    "Real": "Real Madrid",

    "Барселона": "Barcelona",
    "Barcelona": "Barcelona",
}


class APIClient:

    def __init__(self):
        self.api_key = Config.API_FOOTBALL_KEY
        self.base_url = Config.API_FOOTBALL_URL

        self.headers = {
            "x-apisports-key": self.api_key
        }


    async def get_team_stats(self, team_name: str):

        search_name = TEAM_MAP.get(team_name, team_name)

        logger.info(f"API-Football поиск команды: {search_name}")

        team_id = await self._get_team_id(search_name)

        if not team_id:
            logger.error(f"Команда не найдена: {search_name}")
            return None

        matches = await self._get_recent_matches(team_id)

        if not matches:
            logger.error("Матчи не найдены")
            return None

        return self._aggregate_stats(matches, team_id)



    async def _get_team_id(self, name: str):

        url = f"{self.base_url}/teams"

        params = {
            "search": name
        }


        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                headers=self.headers,
                params=params
            ) as resp:

                logger.info(f"API STATUS: {resp.status}")

                data = await resp.json()

                logger.info(f"API RESPONSE: {data}")


                if resp.status == 200:

                    if data.get("results", 0) > 0:

                        return data["response"][0]["team"]["id"]


        return None



    async def _get_recent_matches(self, team_id: int):

        url = f"{self.base_url}/fixtures"

        params = {
            "team": team_id,
            "last": 10
        }


        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                headers=self.headers,
                params=params
            ) as resp:

                logger.info(f"FIXTURES STATUS: {resp.status}")

                data = await resp.json()

                logger.info(f"FIXTURES RESPONSE: {data}")


                if resp.status == 200:

                    return data.get("response", [])


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

            "team": team_id,

            "avg_goals": goals_scored / total,

            "avg_goals_conceded": goals_conceded / total,

            "avg_xg": 1.3,

            "avg_possession": 50,

            "form_index": 70

        }
