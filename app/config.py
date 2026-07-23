import os
from pathlib import Path


class Config:

    # ==========================
    # PROJECT
    # ==========================

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    DATA_DIR = PROJECT_ROOT / "data"

    PASSPORT_DIR = DATA_DIR / "passports"

    ALIASES_DIR = DATA_DIR / "aliases"

    ALIASES_FILE = ALIASES_DIR / "teams.json"

    # ==========================
    # TOKENS (Railway Variables)
    # ==========================

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")

    FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")

    # ==========================
    # LEAGUES
    # ==========================

    SUPPORTED_LEAGUES = {

        "RPL": "api-football",

        "EPL": "football-data",

        "LaLiga": "football-data",

        "SerieA": "football-data",

        "Bundesliga": "football-data",

        "Ligue1": "football-data"

    }

    # ==========================
    # TEAMS
    # ==========================

    LEAGUE_TEAMS = {

        "RPL": [

            "Зенит",

            "Спартак",

            "ЦСКА",

            "Краснодар",

            "Динамо",

            "Локомотив",

            "Ростов",

            "Рубин",

            "Крылья Советов",

            "Ахмат",

            "Акрон",

            "Балтика",

            "Факел",

            "Пари НН",

            "Оренбург",

            "Сочи"

        ]

    }
