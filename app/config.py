import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent.parent

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

    # API-Football
    API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
    API_FOOTBALL_URL = "https://v3.football.api-sports.io"

    # Football-Data.org
    FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")

    # Администратор
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

    # Версии
    MODEL_VERSION = "5.0.1"
    DATA_VERSION = "2026.07"

    # Симуляции
    SIMULATION_COUNT = 10000

    @classmethod
    def ensure_directories(cls):
        (cls.BASE_DIR / "data").mkdir(exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(exist_ok=True)
        (cls.BASE_DIR / "data" / "passports").mkdir(exist_ok=True)
