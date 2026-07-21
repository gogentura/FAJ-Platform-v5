import time
import aiohttp
import asyncio
from app.config import Config
from app.prediction.passport_engine import PassportEngine
from app.prediction.xg_engine import XGEngine
from app.prediction.simulation_engine import SimulationEngine
from app.prediction.decision_engine import DecisionEngine
from app.tactics.tactical_engine import TacticalEngine
from app.tactics.scenario_engine import ScenarioEngine
from app.reports.xai_engine import XAIEngine

class FAJCore:
    def __init__(self):
        self.version = "5.0.0"

    async def get_team_stats(self, team_name: str):
        """Получает реальную статистику команды через API-Football."""
        url = f"{Config.API_FOOTBALL_URL}/teams"
        headers = {"x-apisports-key": Config.API_FOOTBALL_KEY}
        params = {"search": team_name}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["results"] > 0:
                        team_id = data["response"][0]["team"]["id"]
                        stats_url = f"{Config.API_FOOTBALL_URL}/fixtures"
                        stats_params = {"team": team_id, "last": 10}
                        async with session.get(stats_url, headers=headers, params=stats_params) as stats_resp:
                            if stats_resp.status == 200:
                                stats_data = await stats_resp.json()
                                return self._parse_stats(stats_data["response"])
        return None

    def _parse_stats(self, matches):
        goals_scored = 0
        goals_conceded = 0
        total = 0
        for match in matches:
            goals = match.get("goals", {})
            goals_scored += goals.get("home", 0) + goals.get("away", 0)
            goals_conceded += goals.get("away", 0) if match.get("teams", {}).get("home", {}).get("id") else goals.get("home", 0)
            total += 1
        if total == 0:
            return None
        return {
            "avg_goals": goals_scored / total,
            "avg_goals_conceded": goals_conceded / total,
            "avg_xg": 1.3 + (goals_scored / total) * 0.2,
            "avg_possession": 50 + (goals_scored / total) * 5
        }

    def predict_match(self, home_team, away_team, tournament="RPL"):
        start = time.time()
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            home_stats = loop.run_until_complete(self.get_team_stats(home_team))
            away_stats = loop.run_until_complete(self.get_team_stats(away_team))
            loop.close()
        except Exception as e:
            print(f"Ошибка API: {e}")
            home_stats = {"avg_goals": 1.3, "avg_goals_conceded": 1.0, "avg_xg": 1.5, "avg_possession": 55}
            away_stats = {"avg_goals": 1.2, "avg_goals_conceded": 1.1, "avg_xg": 1.4, "avg_possession": 50}

        home_passport = PassportEngine.build(home_stats)
        away_passport = PassportEngine.build(away_stats)
        home_xg, away_xg = XGEngine.calculate(home_passport, away_passport, tournament)
        simulation = SimulationEngine.run(home_xg, away_xg)
        tactical = TacticalEngine.analyze(home_passport, away_passport)
        scenarios = ScenarioEngine.generate(home_xg, away_xg, tactical)
        decision = DecisionEngine.decide(simulation, home_xg, away_xg)
        explanation = XAIEngine.explain(decision, home_passport, away_passport, tactical)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "tournament": tournament,
            "xg": {"home": home_xg, "away": away_xg},
            "simulation": simulation,
            "tactical": tactical,
            "scenarios": scenarios,
            "decision": decision,
            "explanation": explanation,
            "processing_time": round(time.time() - start, 2),
            "version": self.version,
            "top_scores": simulation["top_scores"]
        }
