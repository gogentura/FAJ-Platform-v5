# app/parsers/soccerland_parser.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SoccerlandParser:
    def __init__(self):
        self.base_url = "https://soccerland.ru"
        self.calendar_url = f"{self.base_url}/russia/premier-liga/2026-2027/calendar"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        self.teams = self._get_rpl_teams()
    
    def _get_rpl_teams(self) -> List[str]:
        """Список команд РПЛ сезона 2026-2027"""
        return [
            "Зенит", "Спартак", "ЦСКА", "Динамо", "Локомотив",
            "Краснодар", "Ростов", "Ахмат", "Рубин", "Крылья Советов",
            "Оренбург", "Пари НН", "Факел", "Химки", "Динамо Мх", "Акрон"
        ]
    
    def parse_fixtures(self) -> List[Dict]:
        """
        Парсит календарь с Soccerland
        
        Returns:
            List[Dict]: список матчей
        """
        matches = []
        
        try:
            # Загружаем страницу
            response = requests.get(
                self.calendar_url,
                headers=self.headers,
                timeout=15,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code}: {self.calendar_url}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем блоки с турами
            # На Soccerland туры обычно в div с классом "round" или "tour"
            tour_blocks = soup.find_all('div', class_=re.compile(r'(tour|round)', re.I))
            
            if not tour_blocks:
                # Альтернативный поиск: таблица
                tables = soup.find_all('table')
                if tables:
                    tour_blocks = tables
            
            current_round = 1
            
            for block in tour_blocks:
                # Ищем номер тура
                round_text = block.get_text(strip=True)
                round_match = re.search(r'Тур\s*(\d+)', round_text)
                
                if round_match:
                    current_round = int(round_match.group(1))
                
                # Ищем строки с матчами
                rows = block.find_all('tr')
                for row in rows:
                    match_data = self._parse_match_row(row, current_round)
                    if match_data:
                        matches.append(match_data)
            
            logger.info(f"Найдено {len(matches)} матчей")
            
            # Валидация
            if len(matches) < 200:
                logger.warning(f"Найдено только {len(matches)} матчей")
            else:
                logger.info(f"✅ Успешно загружено {len(matches)} матчей")
                
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            return []
        
        return matches
    
    def _parse_match_row(self, row, round_num: int) -> Optional[Dict]:
        """Парсит строку матча из HTML"""
        try:
            cells = row.find_all('td')
            
            if len(cells) < 3:
                return None
            
            # Извлекаем текст из ячеек
            text_cells = [cell.get_text(strip=True) for cell in cells]
            
            # Ищем команды в строке
            teams_found = []
            for team in self.teams:
                for cell_text in text_cells:
                    if team in cell_text:
                        teams_found.append(team)
            
            # Если нашли ровно 2 команды - это матч
            if len(teams_found) == 2:
                home = teams_found[0]
                away = teams_found[1]
                
                # Ищем дату и время
                date_text = " ".join(text_cells)
                match_date = self._parse_date(date_text)
                match_time = self._parse_time(date_text)
                
                return {
                    "round": round_num,
                    "home_team": home,
                    "away_team": away,
                    "match_date": match_date,
                    "match_time": match_time,
                    "season": "2026-2027"
                }
                
        except Exception as e:
            logger.debug(f"Ошибка парсинга строки: {e}")
        
        return None
    
    def _parse_date(self, text: str) -> str:
        """Парсит дату из текста"""
        patterns = [
            r'(\d{2})\.(\d{2})\.(\d{4})',  # DD.MM.YYYY
            r'(\d{4})-(\d{2})-(\d{2})',    # YYYY-MM-DD
            r'(\d{2})/(\d{2})/(\d{4})',    # DD/MM/YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if '.' in pattern:
                    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
                elif '/' in pattern:
                    return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
                else:
                    return match.group(0)
        
        return "2026-07-20"  # fallback
    
    def _parse_time(self, text: str) -> str:
        """Парсит время из текста"""
        match = re.search(r'(\d{2}):(\d{2})', text)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
        return "19:00"  # fallback

# Функция для тестирования
def test_parser():
    parser = SoccerlandParser()
    matches = parser.parse_fixtures()
    
    print(f"📊 Найдено матчей: {len(matches)}")
    
    if matches:
        print("\n📋 Первые 5 матчей:")
        for i, match in enumerate(matches[:5], 1):
            print(f"{i}. Тур {match['round']}: {match['home_team']} vs {match['away_team']}")
            print(f"   📅 {match['match_date']} {match['match_time']}")
            print()
        
        # Статистика по турам
        rounds = {}
        for match in matches:
            rounds[match['round']] = rounds.get(match['round'], 0) + 1
        
        print(f"📊 Туров: {len(rounds)}")
        print(f"📊 Среднее матчей в туре: {sum(rounds.values()) / len(rounds):.1f}")
        
        if len(matches) >= 240:
            print("✅ Парсер работает корректно!")
        else:
            print(f"⚠️ Найдено {len(matches)} матчей (ожидается ~240)")
    else:
        print("❌ Матчи не найдены")

if __name__ == "__main__":
    test_parser()
