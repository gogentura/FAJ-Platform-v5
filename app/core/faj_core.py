import time
from app.config import Config
from app.models.match_context import MatchContext

class FAJCore:
    def __init__(self):
        self.version = Config.MODEL_VERSION

    def predict_match(self, home_team: str, away_team: str, league: str = "RPL") -> dict:
        start = time.time()

        context = MatchContext(
            match_id=f"{home_team}_{away_team}_{int(start)}",
            home_team=home_team,
            away_team=away_team,
            tournament=league
        )

        # TODO: загрузка паспортов, xG, симуляции (позже)
        context.xg_home = 1.3
        context.xg_away = 1.1
        context.processing_time = round(time.time() - start, 2)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "xg": {"home": context.xg_home, "away": context.xg_away},
            "processing_time": context.processing_time,
            "version": self.version
        }
