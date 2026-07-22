"""
Клиент для работы с Football-Data.org
"""

import aiohttp
from app.config import Config

class FootballDataClient:
    def __init__(self):
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {"X-Auth-Token": Config.FOOTBALL_DATA_KEY}

    async def get_team_stats(self, team_name: str, league: str) -> dict:
        """
        Получает статистику команды из Football-Data.org.
        Сейчас возвращает демо-данные, чтобы бот работал.
        """
        # В будущем здесь будет реальный запрос к API
        # Пока возвращаем тестовые данные
        return {
            "team": team_name,
            "league": league,
            "avg_goals": 1.5,
            "avg_goals_conceded": 1.0,
            "avg_possession": 52,
            "form_index": 75,
            "faj_xg": 1.4  # будет использоваться как predicted_xg
        }
