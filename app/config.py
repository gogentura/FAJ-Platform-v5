import os
from pathlib import Path

class Config:
    # Корневая директория проекта
    BASE_DIR = Path(__file__).parent.parent

    # === Telegram ===
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

    # === API-Football ===
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
    API_FOOTBALL_URL = "https://v3.football.api-sports.io"

    # === Версия модели ===
    MODEL_VERSION = "5.0.0"

    # === Параметры симуляций ===
    SIMULATION_COUNT = 10000

    # === Коэффициенты для лиг (средний xG) ===
    LEAGUE_AVG_XG = {
        "EPL": 1.42,
        "LaLiga": 1.35,
        "Bundesliga": 1.40,
        "SerieA": 1.32,
        "Ligue1": 1.30,
        "UCL": 1.38,
        "RPL": 1.25,
        "default": 1.30
    }

    # === Коэффициенты домашнего преимущества ===
    HOME_ADV = {
        "EPL": 1.18,
        "LaLiga": 1.16,
        "Bundesliga": 1.20,
        "SerieA": 1.15,
        "Ligue1": 1.14,
        "UCL": 1.10,
        "RPL": 1.12,
        "default": 1.15
    }

    @classmethod
    def ensure_directories(cls):
        """Создаёт необходимые папки, если их нет."""
        (cls.BASE_DIR / "data").mkdir(exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(exist_ok=True)
