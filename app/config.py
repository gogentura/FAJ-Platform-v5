import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent.parent

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
    API_FOOTBALL_URL = "https://v3.football.api-sports.io"
    FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

    MODEL_VERSION = "5.1"
    DATA_VERSION = "2026.07"
    SIMULATION_COUNT = 10000

    SUPPORTED_LEAGUES = {
        "RPL": "api-football",
        "EPL": "football-data",
        "LaLiga": "football-data",
        "Bundesliga": "football-data",
        "SerieA": "football-data",
        "Ligue1": "football-data",
        "UCL": "football-data",
    }

    LEAGUE_TEAMS = {
        "RPL": ["Зенит", "Спартак", "ЦСКА", "Динамо М", "Локомотив", "Краснодар",
                "Ростов", "Ахмат", "Рубин", "Крылья Советов", "Факел", "Оренбург",
                "Балтика", "Акрон", "Динамо Мх", "Родина"],
        "EPL": [],
        "LaLiga": [],
        "Bundesliga": [],
        "SerieA": [],
        "Ligue1": [],
        "UCL": [],
    }

    @classmethod
    def ensure_directories(cls):
        (cls.BASE_DIR / "data").mkdir(exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(exist_ok=True)
        (cls.BASE_DIR / "data" / "passports").mkdir(exist_ok=True)
