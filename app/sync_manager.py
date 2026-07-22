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



    async def update_team(
        self,
        team_name: str,
        league: str = "RPL"
    ):

        if is_updated_today(team_name):

            cached = load_passport(team_name)

            if cached:

                return {
                    "status": "ok",
                    "team": team_name,
                    "league": league,
                    "source": cached.get("source", "local"),
                    "passport": cached,
                    "message": "Паспорт уже существует"
                }



        source = self.league_source.get(
            league,
            "api-football"
        )


        try:

            if source == "api-football":

                raw_data = await self.api_football.get_team_stats(
                    team_name
                )


                if not raw_data:

                    return {
                        "status": "error",
                        "message": f"{team_name} не найден в API"
                    }


                increment_usage()



            elif source == "football-data":

                raw_data = await self.football_data.get_team_stats(
                    team_name,
                    league
                )


            else:

                return {
                    "status": "error",
                    "message": "Источник не найден"
                }



            normalized = normalize_team_data(
                raw_data,
                source
            )



            passport = {

                "team": team_name,

                "league": league,

                "source": source,

                "attack": normalized.get("attack", 70),

                "defense": normalized.get("defense", 70),

                "control": normalized.get("control", 70),

                "form_index": normalized.get("form", 70),

                "historical_xg_value": normalized.get(
                    "historical_xg",
                    1.35
                )

            }



            save_passport(
                team_name,
                passport
            )


            return {

                "status": "ok",

                "team": team_name,

                "league": league,

                "source": source,

                "passport": passport,

                "message": "Паспорт создан"

            }



        except Exception as e:


            return {

                "status": "error",

                "message": f"{type(e).__name__}: {e}"

            }



    async def update_rpl(self):

        results = []


        teams = self.league_teams.get(
            "RPL",
            []
        )


        for team in teams:

            result = await self.update_team(
                team,
                "RPL"
            )


            results.append(result)

            await asyncio.sleep(0.2)



        return {

            "status": "done",

            "results": results

        }



    def get_api_status(self):

        return get_api_status()
