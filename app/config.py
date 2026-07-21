import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent.parent
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    MODEL_VERSION = "5.0.0"
    
    @classmethod
    def ensure_directories(cls):
        (cls.BASE_DIR / "data").mkdir(exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(exist_ok=True)
