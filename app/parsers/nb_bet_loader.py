import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional
import time

logger = logging.getLogger(__name__)

class NBBetLoader:
    """
    Загрузчик статистики матчей с nb-bet.com по ссылкам.
    """
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    
    def parse_match(self, url: str) -> Optional[Dict]:
        """
        Парсит одну страницу матча.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logger.error(f"HTTP {response.status_code} для {url}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Извлекаем названия команд и счёт
            home_team, away_team = self._extract_teams_and_score(soup)
            if not home_team or not away_team:
                logger.warning(f"Не удалось определить команды для {url}")
                return None
            
            home_goals, away_goals = self._extract_score(soup)
            
            # 2. Извлекаем статистику
            stats = self._extract_statistics(soup)
            
            return {
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": home_goals,
                "away_goals": away_goals,
                **stats
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга {url}: {e}")
            return None
    
    def _extract_teams_and_score(self, soup: BeautifulSoup) -> tuple:
        """Извлекает названия команд и счёт из заголовка."""
        try:
            # Ищем заголовок с названиями
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # Формат: "ЦСКА - Балтика - счет, прогноз, статистика"
                parts = title_text.split(' - счет')[0]
                if ' - ' in parts:
                    return parts.split(' - ', 1)
            return None, None
        except:
            return None, None
    
    def _extract_score(self, soup: BeautifulSoup) -> tuple:
        """Извлекает счёт матча."""
        try:
            # Ищем блок со счётом
            score_div = soup.find('div', class_=re.compile(r'score', re.I))
            if not score_div:
                return 0, 0
            
            score_text = score_div.get_text(strip=True)
            match = re.search(r'(\d+)\s*[:;]\s*(\d+)', score_text)
            if match:
                return int(match.group(1)), int(match.group(2))
            return 0, 0
        except:
            return 0, 0
    
    def _extract_statistics(self, soup: BeautifulSoup) -> Dict:
        """Извлекает все статистические показатели."""
        stats = {
            "home_xg": None,
            "away_xg": None,
            "home_shots": None,
            "away_shots": None,
            "home_shots_on_target": None,
            "away_shots_on_target": None,
            "home_possession": None,
            "away_possession": None,
            "home_corners": None,
            "away_corners": None,
            "home_yellow_cards": None,
            "away_yellow_cards": None,
            "home_pass_accuracy": None,
            "away_pass_accuracy": None,
        }
        
        try:
            # Находим все строки с показателями
            rows = soup.find_all('div', class_=re.compile(r'(stat|row|item)', re.I))
            if not rows:
                rows = soup.find_all('tr', class_=re.compile(r'(stat|row|item)', re.I))
            
            for row in rows:
                text = row.get_text(strip=True)
                
                # xG
                if 'Ожидаемые голы' in text or 'xG' in text:
                    numbers = re.findall(r'(\d+\.\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_xg'] = float(numbers[0])
                        stats['away_xg'] = float(numbers[1])
                
                # Удары
                if 'Удары' in text and 'в створ' not in text:
                    numbers = re.findall(r'(\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_shots'] = int(numbers[0])
                        stats['away_shots'] = int(numbers[1])
                
                # Удары в створ
                if 'Удары в створ' in text:
                    numbers = re.findall(r'(\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_shots_on_target'] = int(numbers[0])
                        stats['away_shots_on_target'] = int(numbers[1])
                
                # Владение
                if 'Владение' in text:
                    numbers = re.findall(r'(\d+)%', text)
                    if len(numbers) >= 2:
                        stats['home_possession'] = int(numbers[0])
                        stats['away_possession'] = int(numbers[1])
                
                # Угловые
                if 'Угловые' in text:
                    numbers = re.findall(r'(\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_corners'] = int(numbers[0])
                        stats['away_corners'] = int(numbers[1])
                
                # Жёлтые карточки
                if 'Желтые' in text or 'ЖК' in text:
                    numbers = re.findall(r'(\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_yellow_cards'] = int(numbers[0])
                        stats['away_yellow_cards'] = int(numbers[1])
                
                # Точность передач
                if 'Точность передач' in text or 'Передачи' in text:
                    numbers = re.findall(r'(\d+)%', text)
                    if len(numbers) >= 2:
                        stats['home_pass_accuracy'] = int(numbers[0])
                        stats['away_pass_accuracy'] = int(numbers[1])
            
        except Exception as e:
            logger.error(f"Ошибка извлечения статистики: {e}")
        
        return stats
