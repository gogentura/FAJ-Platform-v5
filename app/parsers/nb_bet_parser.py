#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Парсер статистики матчей РПЛ с nb-bet.com
FAJ Platform v12.1
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
        
        # Маппинг ID матчей по турам (из ваших ссылок)
        self.round_matches = {
            1: [
                1612885,  # ЦСКА - Балтика
                1612882,  # Рубин - Краснодар
                1612883,  # Спартак - Родина
                1663973,  # Акрон - Зенит
                1612879,  # Динамо М - Крылья
                # остальные нужно добавить
            ],
            2: [
                1612871,  # Ахмат - Спартак
                1612874,  # Краснодар - Факел
                1612875,  # Оренбург - Зенит
                1663972,  # Балтика - Динамо М
                1612873,  # Динамо Мх - Локомотив
                1612877,  # ЦСКА - Крылья
                1612870,  # Акрон - Рубин
                1612876,  # Родина - Ростов
            ],
            3: [
                1612865,  # Локомотив - Акрон
                1612864,  # Крылья - Балтика
                1612862,  # Динамо М - Динамо Мх
                1681931,  # ЦСКА - Ростов
                1612863,  # Зенит - Родина
                1612868,  # Спартак - Краснодар
                1612867,  # Рубин - Оренбург
                1612869,  # Факел - Ахмат
            ]
        }
    
    def parse_match(self, match_id: int) -> Optional[Dict]:
        """
        Парсит страницу матча и возвращает статистику
        
        Returns:
            Dict: {
                'match_id': 1612885,
                'home_team': 'ЦСКА',
                'away_team': 'Балтика',
                'home_goals': 2,
                'away_goals': 1,
                'home_xg': 2.25,
                'away_xg': 1.52,
                'home_shots': 18,
                'away_shots': 14,
                'home_shots_on_target': 5,
                'away_shots_on_target': 3,
                'home_possession': 65,
                'away_possession': 35,
                'home_corners': 6,
                'away_corners': 2,
                'home_yellow_cards': 1,
                'away_yellow_cards': 1,
                'home_pass_accuracy': 83,
                'away_pass_accuracy': 66,
                'home_fouls': None,
                'away_fouls': None,
            }
        """
        url = f"{self.base_url}/Events/{match_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code} для матча {match_id}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Извлекаем названия команд из заголовка
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # "ЦСКА - Балтика - счет, прогноз, статистика"
                teams_part = title_text.split(' - счет')[0]
                if ' - ' in teams_part:
                    home_team, away_team = teams_part.split(' - ', 1)
                else:
                    home_team, away_team = "Unknown", "Unknown"
            else:
                home_team, away_team = "Unknown", "Unknown"
            
            # 2. Извлекаем счёт
            score_text = soup.find('div', class_=re.compile(r'score', re.I))
            home_goals, away_goals = 0, 0
            if score_text:
                score_match = re.search(r'(\d+)\s*[::]\s*(\d+)', score_text.get_text(strip=True))
                if score_match:
                    home_goals = int(score_match.group(1))
                    away_goals = int(score_match.group(2))
            
            # 3. Ищем блок "Основные показатели"
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
            
            # Ищем все строки с числами в основных показателях
            # На nb-bet.com статистика в таблице или div с классами
            stat_blocks = soup.find_all(['div', 'tr'], class_=re.compile(r'(stat|row|item)', re.I))
            
            for block in stat_blocks:
                text = block.get_text(strip=True)
                
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
                
                # Владение (ищем проценты)
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
            
            logger.info(f"✅ Матч {match_id}: {home_team} {home_goals}:{away_goals} {away_team}")
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка парсинга матча {match_id}: {e}")
            return None
    
    def parse_round(self, round_number: int) -> List[Dict]:
        """Парсит все матчи тура"""
        matches = []
        match_ids = self.round_matches.get(round_number, [])
        
        for match_id in match_ids:
            data = self.parse_match(match_id)
            if data:
                data['round'] = round_number
                matches.append(data)
        
        logger.info(f"Тур {round_number}: загружено {len(matches)} матчей")
        return matches
    
    def parse_all_rounds(self, rounds: List[int] = None) -> List[Dict]:
        """Парсит все туры"""
        if rounds is None:
            rounds = list(self.round_matches.keys())
        
        all_matches = []
        for round_num in rounds:
            matches = self.parse_round(round_num)
            all_matches.extend(matches)
        
        logger.info(f"Всего загружено: {len(all_matches)} матчей")
        return all_matches


# ============================================================
# ФУНКЦИЯ ДЛЯ ЗАГРУЗКИ В БД
# ============================================================

def load_match_stats_to_db(matches_data: List[Dict], db) -> int:
    """
    Загружает статистику матчей в БД
    
    Args:
        matches_data: список словарей от parse_all_rounds()
        db: объект FAJDatabase
    
    Returns:
        int: количество загруженных матчей
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
            cursor = db._get_connection().cursor()
            cursor.execute("""
                SELECT m.id 
                FROM matches m
                JOIN rounds r ON r.id = m.round_id
                WHERE r.round_number = ? 
                  AND m.home_team_id = ? 
                  AND m.away_team_id = ?
            """, (data['round'], home_team_id, away_team_id))
            
            match_row = cursor.fetchone()
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


if __name__ == "__main__":
    # Тест парсера
    parser = NBBetParser()
    
    # Проверяем 1 тур
    round_1_matches = parser.parse_round(1)
    print(f"\n📊 Тур 1: {len(round_1_matches)} матчей")
    for m in round_1_matches:
        print(f"  {m['home_team']} {m['home_goals']}:{m['away_goals']} {m['away_team']}")
        print(f"    xG: {m['home_xg']} - {m['away_xg']}")
        print(f"    Владение: {m['home_possession']}% - {m['away_possession']}%")
        print(f"    Удары: {m['home_shots']} - {m['away_shots']}")
        print()
