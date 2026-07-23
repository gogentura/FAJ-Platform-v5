from pathlib import Path


class Config:

    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    DATA_DIR = PROJECT_ROOT / "data"

    PASSPORT_DIR = DATA_DIR / "passports"

    ALIASES_DIR = DATA_DIR / "aliases"

    ALIASES_FILE = ALIASES_DIR / "teams.json"



    SUPPORTED_LEAGUES = {

        "RPL": "api-football",

        "EPL": "football-data",

        "LaLiga": "football-data",

        "SerieA": "football-data",

        "Bundesliga": "football-data",

        "Ligue1": "football-data"

    }



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
