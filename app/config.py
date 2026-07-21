import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent.parent

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "1234567890")

    # API-Football
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
    API_FOOTBALL_URL = "https://v3.football.api-sports.io"

    # Модель
    MODEL_VERSION = "5.0.0"

    @classmethod
    def ensure_directories(cls):
        (cls.BASE_DIR / "data").mkdir(exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(exist_ok=True)
