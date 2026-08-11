import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ChampionatCalendarParser:
    """
    Парсер календаря РПЛ с сайта championat.com
    """

    BASE_URL = "https://www.championat.com/football/_russiapl/tournament/7096/calendar/"

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self.teams = [
            "Зенит", "Спартак", "ЦСКА", "Динамо Москва", "Локомотив",
            "Краснодар", "Ростов", "Ахмат", "Рубин", "Крылья Советов",
            "Оренбург", "Родина", "Факел", "Акрон", "Балтика", "Динамо Махачкала"
        ]

    def parse(self) -> List[Dict]:
        """
        Парсит страницу и возвращает список матчей.
        """
        try:
            response = requests.get(self.BASE_URL, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Ищем все строки таблицы
            rows = soup.find_all('tr')

            matches = []
            current_round = None

            for row in rows:
                row_text = row.get_text(strip=True)

                # Проверяем, содержит ли строка номер тура
                round_match = re.search(r'Тур\s*(\d+)', row_text)
                if round_match:
                    current_round = int(round_match.group(1))
                    continue

                # Если тур не определён, пропускаем
                if current_round is None:
                    continue

                # Проверяем, что строка содержит дату
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', row_text)
                if not date_match:
                    continue

                # Извлекаем данные матча
                match_data = self._extract_match_data(row_text, current_round)
                if match_data:
                    matches.append(match_data)

            logger.info(f"Найдено {len(matches)} матчей")
            return matches

        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return []

    def _extract_match_data(self, text: str, round_num: int) -> Optional[Dict]:
        """
        Извлекает данные матча из текста строки.
        """
        # Ищем дату
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
        if not date_match:
            return None
        date_str = date_match.group(1)

        # Ищем время
        time_match = re.search(r'(\d{2}:\d{2})', text)
        time_str = time_match.group(1) if time_match else "19:00"

        # Ищем счёт
        score_match = re.search(r'(\d+)\s*[:;]\s*(\d+)', text)
        if score_match:
            home_goals = int(score_match.group(1))
            away_goals = int(score_match.group(2))
        else:
            home_goals = None
            away_goals = None

        # Ищем команды
        clean_text = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', text)
        clean_text = re.sub(r'\d{2}:\d{2}', '', clean_text)
        if score_match:
            clean_text = re.sub(r'\d+\s*[:;]\s*\d+', '', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        home_team = None
        away_team = None

        for team in self.teams:
            if team in clean_text:
                if home_team is None:
                    home_team = team
                    clean_text = clean_text.replace(team, '').strip()
                else:
                    if team != home_team and team in clean_text:
                        away_team = team
                        break

        if not home_team or not away_team:
            return None

        # Преобразуем дату в формат YYYY-MM-DD
        day, month, year = date_str.split('.')
        date_formatted = f"{year}-{month}-{day}"

        return {
            "round": round_num,
            "home_team": home_team,
            "away_team": away_team,
            "match_date": date_formatted,
            "match_time": time_str,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "season": "2026-2027"
        }
