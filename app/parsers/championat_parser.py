import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ChampionatParser:
    """
    Парсер календаря и результатов РПЛ с championat.com
    """
    
    BASE_URL = "https://www.championat.com/football/_russiapl/tournament/7096/calendar/"
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        # Маппинг коротких названий из URL к полным
        self.team_mapping = {
            # Здесь нужно будет добавить соответствие названий
            # Пока оставляем как есть, будем определять из контекста
        }
    
    def parse(self) -> List[Dict]:
        """
        Парсит страницу календаря и возвращает список матчей.
        """
        try:
            response = requests.get(self.BASE_URL, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем все строки таблицы
            rows = soup.find_all('tr', class_=re.compile(r'^[a-z]+-line'))
            
            if not rows:
                logger.warning("Не найдены строки с матчами на странице")
                return []
            
            matches = []
            current_round = None
            
            for row in rows:
                # Определяем тур
                round_cell = row.find('td', class_=re.compile(r'round'))
                if round_cell:
                    round_text = round_cell.get_text(strip=True)
                    match = re.search(r'(\d+)', round_text)
                    if match:
                        current_round = int(match.group(1))
                    continue
                
                if current_round is None:
                    continue
                
                # Парсим матч
                match_data = self._parse_match_row(row, current_round)
                if match_data:
                    matches.append(match_data)
            
            logger.info(f"Найдено {len(matches)} матчей")
            return matches
            
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return []
    
    def _parse_match_row(self, row, round_num: int) -> Optional[Dict]:
        """Парсит одну строку матча"""
        try:
            cells = row.find_all('td')
            if len(cells) < 3:
                return None
            
            # Дата и время
            datetime_cell = cells[0] if len(cells) > 0 else None
            datetime_text = datetime_cell.get_text(strip=True) if datetime_cell else ""
            match_date, match_time = self._parse_datetime(datetime_text)
            
            # Команды и счёт
            teams_cell = cells[1] if len(cells) > 1 else None
            score_cell = cells[2] if len(cells) > 2 else None
            
            if not teams_cell:
                return None
            
            # Извлекаем команды и счёт
            teams_text = teams_cell.get_text(strip=True)
            score_text = score_cell.get_text(strip=True) if score_cell else ""
            
            home, away = self._parse_teams(teams_text)
            home_goals, away_goals = self._parse_score(score_text)
            
            if not home or not away:
                return None
            
            return {
                "round": round_num,
                "home_team": home,
                "away_team": away,
                "match_date": match_date,
                "match_time": match_time,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "season": "2026-2027"
            }
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга строки: {e}")
            return None
    
    def _parse_datetime(self, text: str) -> tuple:
        """Парсит дату и время"""
        date_pattern = r'(\d{2})\.(\d{2})\.(\d{4})'
        time_pattern = r'(\d{2}):(\d{2})'
        
        date_match = re.search(date_pattern, text)
        time_match = re.search(time_pattern, text)
        
        if date_match:
            day, month, year = date_match.groups()
            date_str = f"{year}-{month}-{day}"
        else:
            date_str = "2026-08-14"  # fallback для 4-го тура
        
        if time_match:
            time_str = f"{time_match.group(1)}:{time_match.group(2)}"
        else:
            time_str = "19:00"
        
        return date_str, time_str
    
    def _parse_teams(self, text: str) -> tuple:
        """Парсит названия команд"""
        # Убираем эмодзи и лишние символы
        clean_text = re.sub(r'[^\w\s\-\.]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Находим разделитель (обычно пробел, но может быть и эмодзи)
        parts = clean_text.split()
        
        # Ищем названия команд по известному списку
        from app.config import RPL_TEAMS
        team_names = RPL_TEAMS
        
        home, away = None, None
        for team in team_names:
            if team in clean_text:
                if not home:
                    home = team
                    # Удаляем найденную команду из текста и ищем вторую
                    rest = clean_text.replace(team, '').strip()
                    for team2 in team_names:
                        if team2 != team and team2 in rest:
                            away = team2
                            break
                    if away:
                        break
        
        if not home or not away:
            # Fallback: пытаемся разделить по пробелам
            words = clean_text.split()
            if len(words) >= 2:
                # Пробуем найти первые два слова как команды
                for i in range(len(words)):
                    for j in range(i+1, len(words)):
                        candidate_home = ' '.join(words[:i+1])
                        candidate_away = ' '.join(words[i+1:j+1])
                        if candidate_home in team_names and candidate_away in team_names:
                            return candidate_home, candidate_away
        
        return home, away
    
    def _parse_score(self, text: str) -> tuple:
        """Парсит счёт матча"""
        if not text or text == "– : –" or text == "–:–":
            return None, None
        
        match = re.search(r'(\d+)\s*[:;]\s*(\d+)', text)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        return None, None


# Список команд РПЛ для парсинга
RPL_TEAMS = [
    "Зенит", "Спартак", "ЦСКА", "Динамо Москва", "Локомотив",
    "Краснодар", "Ростов", "Ахмат", "Рубин", "Крылья Советов",
    "Оренбург", "Родина", "Факел", "Акрон", "Балтика", "Динамо Махачкала"
]
