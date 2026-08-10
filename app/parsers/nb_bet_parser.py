#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Парсер статистики матчей РПЛ с nb-bet.com
FAJ Platform v12.1
АВТОМАТИЧЕСКИЙ ПОИСК ВСЕХ МАТЧЕЙ
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class NBBetParser:
    def __init__(self):
        self.base_url = "https://nb-bet.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        
        # Список команд РПЛ для поиска
        self.rpl_teams = [
            "Зенит", "Спартак", "ЦСКА", "Динамо", "Локомотив",
            "Краснодар", "Ростов", "Ахмат", "Рубин", "Крылья Советов",
            "Оренбург", "Пари НН", "Факел", "Химки", "Динамо Мх", "Акрон"
        ]
        
        # Варианты названий команд на сайте
        self.team_variants = {
            "Зенит": ["Зенит", "Зенит Санкт-Петербург"],
            "Спартак": ["Спартак", "Спартак Москва"],
            "ЦСКА": ["ЦСКА", "ЦСКА Москва"],
            "Динамо": ["Динамо", "Динамо Москва"],
            "Локомотив": ["Локомотив", "Локомотив Москва"],
            "Краснодар": ["Краснодар"],
            "Ростов": ["Ростов"],
            "Ахмат": ["Ахмат", "Ахмат Грозный"],
            "Рубин": ["Рубин", "Рубин Казань"],
            "Крылья Советов": ["Крылья Советов", "Крылья Советов Самара"],
            "Оренбург": ["Оренбург"],
            "Пари НН": ["Пари НН", "Пари Нижний Новгород", "Нижний Новгород"],
            "Факел": ["Факел", "Факел Воронеж"],
            "Химки": ["Химки"],
            "Динамо Мх": ["Динамо Махачкала", "Динамо Мх"],
            "Акрон": ["Акрон", "Акрон Тольятти"],
        }
    
    def find_match_ids(self, round_number: int) -> List[int]:
        """
        Находит ID всех матчей тура через поиск на сайте
        
        Returns:
            List[int]: список ID матчей
        """
        match_ids = []
        
        # Пробуем найти страницу с календарём тура
        search_urls = [
            f"{self.base_url}/russia/premier-liga/2026-2027/round-{round_number}",
            f"{self.base_url}/russia/premier-liga/2026-2027/tour-{round_number}",
            f"{self.base_url}/russia/premier-liga/2026-2027/tour/{round_number}",
            f"{self.base_url}/sport/football/russia/premier-league/round-{round_number}",
        ]
        
        for url in search_urls:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Ищем ссылки на матчи
                    # На nb-bet.com ссылки на матчи обычно в формате /Events/1234567-...
                    links = soup.find_all('a', href=re.compile(r'/Events/\d+'))
                    
                    for link in links:
                        href = link.get('href', '')
                        match_id_match = re.search(r'/Events/(\d+)', href)
                        if match_id_match:
                            match_id = int(match_id_match.group(1))
                            if match_id not in match_ids:
                                match_ids.append(match_id)
                    
                    if match_ids:
                        logger.info(f"Найдено {len(match_ids)} матчей в туре {round_number}")
                        break
            except Exception as e:
                logger.debug(f"Ошибка поиска тура {round_number}: {e}")
                continue
        
        return match_ids
    
    def find_match_ids_by_teams(self, round_number: int, home_team: str, away_team: str) -> Optional[int]:
        """
        Находит ID конкретного матча по командам через поиск на сайте
        """
        # Ищем все матчи тура
        all_ids = self.find_match_ids(round_number)
        
        for match_id in all_ids:
            # Получаем информацию о матче
            match_info = self.get_match_teams(match_id)
            if match_info:
                if (match_info['home_team'] == home_team and match_info['away_team'] == away_team) or \
                   (match_info['home_team'] == away_team and match_info['away_team'] == home_team):
                    return match_id
        
        return None
    
    def get_match_teams(self, match_id: int) -> Optional[Dict]:
        """
        Получает названия команд по ID матча
        """
        url = f"{self.base_url}/Events/{match_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем названия команд в заголовке
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # "ЦСКА - Балтика - счет, прогноз, статистика"
                teams_part = title_text.split(' - счет')[0]
                if ' - ' in teams_part:
                    home_team, away_team = teams_part.split(' - ', 1)
                    # Проверяем, что это команды РПЛ
                    if self._is_rpl_team(home_team) and self._is_rpl_team(away_team):
                        return {
                            'home_team': self._normalize_team_name(home_team),
                            'away_team': self._normalize_team_name(away_team),
                            'match_id': match_id
                        }
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка получения команд для матча {match_id}: {e}")
            return None
    
    def _is_rpl_team(self, team_name: str) -> bool:
        """Проверяет, является ли команда командой РПЛ"""
        for rpl_team in self.rpl_teams:
            if rpl_team in team_name or team_name in rpl_team:
                return True
        return False
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Приводит название команды к стандартному виду"""
        for rpl_team, variants in self.team_variants.items():
            for variant in variants:
                if variant in team_name or team_name in variant:
                    return rpl_team
        return team_name
    
    def parse_match(self, match_id: int) -> Optional[Dict]:
        """
        Парсит страницу матча и возвращает статистику
        """
        url = f"{self.base_url}/Events/{match_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code} для матча {match_id}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Получаем названия команд
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                teams_part = title_text.split(' - счет')[0]
                if ' - ' in teams_part:
                    home_team_raw, away_team_raw = teams_part.split(' - ', 1)
                    home_team = self._normalize_team_name(home_team_raw)
                    away_team = self._normalize_team_name(away_team_raw)
                else:
                    home_team, away_team = "Unknown", "Unknown"
            else:
                home_team, away_team = "Unknown", "Unknown"
            
            # Проверяем, что это матч РПЛ
            if not (self._is_rpl_team(home_team) and self._is_rpl_team(away_team)):
                logger.debug(f"Матч {match_id} не РПЛ: {home_team} vs {away_team}")
                return None
            
            # Извлекаем счёт
            score_text = soup.find('div', class_=re.compile(r'score', re.I))
            home_goals, away_goals = 0, 0
            if score_text:
                score_match = re.search(r'(\d+)\s*[::]\s*(\d+)', score_text.get_text(strip=True))
                if score_match:
                    home_goals = int(score_match.group(1))
                    away_goals = int(score_match.group(2))
            
            # Инициализируем статистику
            stats = {
                'match_id': match_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'home_xg': None,
                'away_xg': None,
                'home_shots': None,
                'away_shots': None,
                'home_shots_on_target': None,
                'away_shots_on_target': None,
                'home_possession': None,
                'away_possession': None,
                'home_corners': None,
                'away_corners': None,
                'home_yellow_cards': None,
                'away_yellow_cards': None,
                'home_pass_accuracy': None,
                'away_pass_accuracy': None,
                'home_fouls': None,
                'away_fouls': None,
            }
            
            # Парсим основные показатели
            # Ищем блок с классом, содержащим "stat" или "row"
            stat_blocks = soup.find_all(['div', 'tr'], class_=re.compile(r'(stat|row|item|info)', re.I))
            
            for block in stat_blocks:
                text = block.get_text(strip=True)
                
                # xG (ожидаемые голы)
                if 'Ожидаемые голы' in text or 'xG' in text:
                    numbers = re.findall(r'(\d+\.\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_xg'] = float(numbers[0])
                        stats['away_xg'] = float(numbers[1])
                    elif len(numbers) == 1:
                        # Может быть только одно значение xG
                        if 'xG' in text:
                            stats['home_xg'] = float(numbers[0])
                
                # Удары
                if 'Удары' in text and 'в створ' not in text:
                    numbers = re.findall(r'(\d+)', text)
                    if len(numbers) >= 2:
                        stats['home_shots'] = int(numbers[0])
                        stats['away_shots'] = int(numbers[1])
                
                # Удары в створ
                if 'Удары в створ' in text or 'Удары в створ' in text:
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
                    elif len(numbers) == 1:
                        # Может быть только одно значение
                        if 'home' in text.lower() or 'хозя' in text:
                            stats['home_possession'] = int(numbers[0])
                        else:
                            stats['away_possession'] = int(numbers[0])
                
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
            
            logger.info(f"✅ Матч {match_id}: {home_team} {home_goals}:{away_goals} {away_team}")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка парсинга матча {match_id}: {e}")
            return None
    
    def parse_round(self, round_number: int) -> List[Dict]:
        """
        Парсит все матчи тура - АВТОМАТИЧЕСКИ НАХОДИТ ID
        """
        matches = []
        
        # Находим ID всех матчей тура
        match_ids = self.find_match_ids(round_number)
        
        if not match_ids:
            logger.warning(f"Не найдены матчи для тура {round_number}")
            return []
        
        # Ограничиваем количество попыток (не больше 20 матчей в туре)
        match_ids = match_ids[:20]
        
        for match_id in match_ids:
            data = self.parse_match(match_id)
            if data:
                # Проверяем, что это действительно матч РПЛ
                if self._is_rpl_team(data['home_team']) and self._is_rpl_team(data['away_team']):
                    data['round'] = round_number
                    matches.append(data)
        
        logger.info(f"Тур {round_number}: загружено {len(matches)} матчей РПЛ")
        return matches
    
    def parse_all_rounds(self, rounds: List[int] = None) -> List[Dict]:
        """Парсит все туры"""
        if rounds is None:
            rounds = list(range(1, 31))  # 1-30 туры
        
        all_matches = []
        for round_num in rounds:
            matches = self.parse_round(round_num)
            all_matches.extend(matches)
        
        logger.info(f"Всего загружено: {len(all_matches)} матчей")
        return all_matches
    
    def parse_round_from_teams(self, round_number: int, matches_list: List[Tuple[str, str]]) -> List[Dict]:
        """
        Парсит тур по списку пар команд (для точного поиска)
        
        Args:
            round_number: номер тура
            matches_list: список кортежей (home_team, away_team)
        
        Returns:
            List[Dict]: список статистики матчей
        """
        matches = []
        
        for home_team, away_team in matches_list:
            # Ищем ID матча
            match_id = self.find_match_ids_by_teams(round_number, home_team, away_team)
            
            if match_id:
                data = self.parse_match(match_id)
                if data:
                    data['round'] = round_number
                    matches.append(data)
            else:
                logger.warning(f"Матч не найден: {home_team} vs {away_team} (тур {round_number})")
        
        return matches


# ============================================================
# ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ В БД
# ============================================================

def load_match_stats_to_db(matches_data: List[Dict], db) -> int:
    """
    Загружает статистику матчей в БД
    """
    loaded = 0
    
    for data in matches_data:
        try:
            # Находим команды в БД
            home_team_id = db.get_team_id(data['home_team'], 'RPL')
            away_team_id = db.get_team_id(data['away_team'], 'RPL')
            
            if not home_team_id or not away_team_id:
                logger.warning(f"Команда не найдена: {data['home_team']} vs {data['away_team']}")
                continue
            
            # Находим матч в БД
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id 
                FROM matches m
                JOIN rounds r ON r.id = m.round_id
                WHERE r.round_number = ? 
                  AND m.home_team_id = ? 
                  AND m.away_team_id = ?
            """, (data['round'], home_team_id, away_team_id))
            
            match_row = cursor.fetchone()
            conn.close()
            
            if not match_row:
                logger.warning(f"Матч не найден в БД: {data['home_team']} vs {data['away_team']} (тур {data['round']})")
                continue
            
            match_id = match_row['id']
            
            # 1. Сохраняем результат
            db.save_match_result(
                match_id=match_id,
                home_goals=data['home_goals'],
                away_goals=data['away_goals']
            )
            
            # 2. Сохраняем статистику для хозяев
            db.save_match_statistics(
                match_id=match_id,
                team_id=home_team_id,
                stats={
                    'possession': data['home_possession'],
                    'shots': data['home_shots'],
                    'shots_on_target': data['home_shots_on_target'],
                    'corners': data['home_corners'],
                    'fouls': data.get('home_fouls'),
                    'yellow_cards': data['home_yellow_cards'],
                    'red_cards': 0,
                    'xg': data['home_xg'],
                    'pass_accuracy': data['home_pass_accuracy'],
                }
            )
            
            # 3. Сохраняем статистику для гостей
            db.save_match_statistics(
                match_id=match_id,
                team_id=away_team_id,
                stats={
                    'possession': data['away_possession'],
                    'shots': data['away_shots'],
                    'shots_on_target': data['away_shots_on_target'],
                    'corners': data['away_corners'],
                    'fouls': data.get('away_fouls'),
                    'yellow_cards': data['away_yellow_cards'],
                    'red_cards': 0,
                    'xg': data['away_xg'],
                    'pass_accuracy': data['away_pass_accuracy'],
                }
            )
            
            # 4. Обновляем матч (xG в matches)
            db.update_match_stats(match_id, {
                'home_xg': data['home_xg'],
                'away_xg': data['away_xg'],
                'home_possession': data['home_possession'],
                'away_possession': data['away_possession'],
                'home_shots': data['home_shots'],
                'away_shots': data['away_shots'],
                'home_shots_on_target': data['home_shots_on_target'],
                'away_shots_on_target': data['away_shots_on_target'],
                'parser_source': 'nb-bet.com',
                'parser_version': '1.0',
                'data_quality': 1.0,
            })
            
            loaded += 1
            logger.info(f"✅ Загружен матч {loaded}: {data['home_team']} {data['home_goals']}:{data['away_goals']} {data['away_team']}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки матча: {e}")
            continue
    
    return loaded


# ============================================================
# ТЕСТ
# ============================================================

if __name__ == "__main__":
    parser = NBBetParser()
    
    # Тестируем поиск матчей для 1 тура
    print("\n🔍 Поиск матчей 1 тура...")
    match_ids = parser.find_match_ids(1)
    print(f"Найдено ID: {match_ids}")
    
    # Парсим первые 3 матча
    print("\n📊 Парсинг матчей...")
    for match_id in match_ids[:3]:
        data = parser.parse_match(match_id)
        if data:
            print(f"\n{data['home_team']} {data['home_goals']}:{data['away_goals']} {data['away_team']}")
            print(f"  xG: {data['home_xg']} - {data['away_xg']}")
            print(f"  Владение: {data['home_possession']}% - {data['away_possession']}%")
