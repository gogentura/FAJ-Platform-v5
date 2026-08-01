#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Парсер soccerland.ru
Сбор данных по РПЛ: таблица, матчи, бомбардиры
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from typing import Dict, List, Optional


class SoccerlandParser:
    """Парсер для сбора данных с soccerland.ru"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.base_url = "https://soccerland.ru/russia/premier-liga/2026-2027"
    
    # =========================================================
    # 1. ТАБЛИЦА
    # =========================================================
    
    def get_standings(self) -> List[Dict]:
        """Парсинг турнирной таблицы"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            standings = []
            # Ищем таблицу по классам (нужно подобрать)
            table = soup.find('table', class_=re.compile(r'table|standings|rating'))
            if not table:
                # Пробуем найти любую таблицу с данными
                tables = soup.find_all('table')
                for t in tables:
                    if 'команда' in t.text.lower():
                        table = t
                        break
            
            if table:
                rows = table.find_all('tr')[1:]  # Пропускаем заголовок
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        try:
                            place = cols[0].text.strip()
                            team = cols[1].text.strip()
                            games = cols[2].text.strip()
                            wins = cols[3].text.strip()
                            draws = cols[4].text.strip()
                            losses = cols[5].text.strip()
                            goals = cols[6].text.strip()
                            points = cols[7].text.strip() if len(cols) > 7 else ""
                            
                            standings.append({
                                "place": place,
                                "team": team,
                                "games": games,
                                "wins": wins,
                                "draws": draws,
                                "losses": losses,
                                "goals": goals,
                                "points": points
                            })
                        except:
                            continue
            
            return standings
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 2. МАТЧИ С ГОЛАМИ
    # =========================================================
    
    def get_matches_with_goals(self) -> List[Dict]:
        """Парсинг матчей с голами и минутами"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            matches = []
            # Ищем блоки с матчами
            # На soccerland.ru обычно есть список матчей с голам
            match_blocks = soup.find_all('div', class_=re.compile(r'match|game|fixture'))
            
            for block in match_blocks:
                try:
                    # Извлекаем название матча
                    teams = block.find_all('span', class_=re.compile(r'team|name'))
                    if len(teams) >= 2:
                        home = teams[0].text.strip()
                        away = teams[1].text.strip()
                    else:
                        continue
                    
                    # Счёт
                    score_elem = block.find('span', class_=re.compile(r'score|result'))
                    if score_elem:
                        score = score_elem.text.strip()
                    else:
                        score = "– : –"
                    
                    # Голы
                    goals = []
                    goal_items = block.find_all('div', class_=re.compile(r'goal|event'))
                    for goal in goal_items:
                        try:
                            player = goal.find('span', class_=re.compile(r'player')).text.strip()
                            minute = goal.find('span', class_=re.compile(r'minute|time')).text.strip()
                            team = goal.find('span', class_=re.compile(r'team')).text.strip()
                            goals.append({
                                "player": player,
                                "minute": minute,
                                "team": team
                            })
                        except:
                            continue
                    
                    matches.append({
                        "home": home,
                        "away": away,
                        "score": score,
                        "goals": goals,
                        "status": "FT" if ":" in score and score != "– : –" else "NS"
                    })
                except:
                    continue
            
            return matches
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 3. БОМБАРДИРЫ
    # =========================================================
    
    def get_top_scorers(self) -> List[Dict]:
        """Парсинг списка бомбардиров"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            scorers = []
            # Ищем блок бомбардиров
            scorer_section = soup.find('div', class_=re.compile(r'scorer|top|bombardir'))
            if not scorer_section:
                return scorers
            
            items = scorer_section.find_all('div', class_=re.compile(r'item|row|player'))
            for item in items:
                try:
                    name = item.find('span', class_=re.compile(r'name')).text.strip()
                    team = item.find('span', class_=re.compile(r'team')).text.strip()
                    goals = item.find('span', class_=re.compile(r'goal|count')).text.strip()
                    
                    scorers.append({
                        "player": name,
                        "team": team,
                        "goals": goals
                    })
                except:
                    continue
            
            return scorers
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 4. ПОЛНОЕ ОБНОВЛЕНИЕ
    # =========================================================
    
    def update_all(self) -> Dict:
        """Полное обновление данных с soccerland.ru"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "standings": [],
            "matches": [],
            "scorers": []
        }
        
        # 1. Таблица
        standings = self.get_standings()
        if isinstance(standings, list) and not isinstance(standings, dict):
            results["standings"] = standings
        
        # 2. Матчи с голами
        matches = self.get_matches_with_goals()
        if isinstance(matches, list) and not isinstance(matches, dict):
            results["matches"] = matches
        
        # 3. Бомбардиры
        scorers = self.get_top_scorers()
        if isinstance(scorers, list) and not isinstance(scorers, dict):
            results["scorers"] = scorers
        
        # Сохраняем в файл
        with open("data/rpl_live_data.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results
