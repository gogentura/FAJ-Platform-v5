#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Парсер soccerland.ru + championat.com
Сбор данных по РПЛ: таблица, матчи, бомбардиры, календарь
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from typing import Dict, List, Optional


class SoccerlandParser:
    """Парсер для сбора данных с soccerland.ru и championat.com"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.base_url = "https://soccerland.ru/russia/premier-liga/2026-2027"
        self.calendar_url = "https://www.championat.com/football/_russiapl/tournament/7096/calendar/"
    
    # =========================================================
    # 1. ТАБЛИЦА (soccerland.ru)
    # =========================================================
    
    def get_standings(self) -> List[Dict]:
        """Парсинг турнирной таблицы"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            standings = []
            # Ищем таблицу
            table = soup.find('table')
            if not table:
                tables = soup.find_all('table')
                for t in tables:
                    if 'команда' in t.text.lower():
                        table = t
                        break
            
            if table:
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        try:
                            standings.append({
                                "place": cols[0].text.strip(),
                                "team": cols[1].text.strip(),
                                "games": cols[2].text.strip(),
                                "wins": cols[3].text.strip(),
                                "draws": cols[4].text.strip(),
                                "losses": cols[5].text.strip(),
                                "goals": cols[6].text.strip(),
                                "points": cols[7].text.strip() if len(cols) > 7 else ""
                            })
                        except:
                            continue
            
            return standings
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 2. РЕЗУЛЬТАТЫ МАТЧЕЙ (soccerland.ru)
    # =========================================================
    
    def get_matches_with_goals(self) -> List[Dict]:
        """Парсинг матчей с голами и минутами"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            matches = []
            # Ищем блоки с матчами на soccerland.ru
            # Обычно там есть список матчей
            match_blocks = soup.find_all('div', class_=re.compile(r'match|game|fixture|result'))
            
            for block in match_blocks:
                try:
                    # Извлекаем название матча
                    home = block.find('span', class_=re.compile(r'home|team1')).text.strip()
                    away = block.find('span', class_=re.compile(r'away|team2')).text.strip()
                    
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
                            goals.append({"player": player, "minute": minute, "team": team})
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
    # 3. КАЛЕНДАРЬ (championat.com) — ПРЕДСТОЯЩИЕ МАТЧИ
    # =========================================================
    
    def get_upcoming_matches(self) -> List[Dict]:
        """Парсинг календаря с championat.com"""
        try:
            response = requests.get(self.calendar_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            upcoming = []
            # Ищем таблицу с матчами
            table = soup.find('table')
            if not table:
                tables = soup.find_all('table')
                for t in tables:
                    if 'Тур' in t.text or 'Дата' in t.text:
                        table = t
                        break
            
            if table:
                rows = table.find_all('tr')
                current_tour = None
                
                for row in rows:
                    cols = row.find_all('td')
                    
                    # Пропускаем заголовки
                    if not cols or len(cols) < 3:
                        continue
                    
                    # Проверяем, не является ли строка заголовком тура
                    if len(cols) == 1:
                        try:
                            tour_text = cols[0].text.strip()
                            if 'Тур' in tour_text:
                                current_tour = tour_text
                        except:
                            continue
                        continue
                    
                    # Парсим матч
                    try:
                        # Дата/время
                        date_time = cols[1].text.strip() if len(cols) > 1 else ""
                        
                        # Счёт
                        score_text = cols[2].text.strip() if len(cols) > 2 else ""
                        
                        # Если счёт "– : –" или пустой — матч ещё не сыгран
                        if score_text in ["– : –", "0 : 0", "0-0"] or not score_text:
                            # Пробуем извлечь команды из текста
                            match_text = row.text.strip()
                            # Ищем названия команд
                            teams = re.findall(r'[А-Я][а-я]+(?:\s[А-Я][а-я]+)?', match_text)
                            if len(teams) >= 2:
                                # Убираем названия туров и дат
                                home_team = teams[0]
                                away_team = teams[1]
                                
                                if home_team and away_team:
                                    upcoming.append({
                                        "home": home_team,
                                        "away": away_team,
                                        "date": date_time,
                                        "tour": current_tour,
                                        "status": "NS"
                                    })
                    except:
                        continue
            
            return upcoming
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 4. БОМБАРДИРЫ (soccerland.ru)
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
                # Ищем по тексту
                for div in soup.find_all('div'):
                    if 'бомбардир' in div.text.lower():
                        scorer_section = div
                        break
            
            if scorer_section:
                items = scorer_section.find_all('div', class_=re.compile(r'item|row|player'))
                for item in items:
                    try:
                        name = item.find('span', class_=re.compile(r'name')).text.strip()
                        team = item.find('span', class_=re.compile(r'team')).text.strip()
                        goals = item.find('span', class_=re.compile(r'goal|count')).text.strip()
                        scorers.append({"player": name, "team": team, "goals": goals})
                    except:
                        continue
            
            return scorers
        except Exception as e:
            return {"error": str(e)}
    
    # =========================================================
    # 5. ПОЛНОЕ ОБНОВЛЕНИЕ
    # =========================================================
    
    def update_all(self) -> Dict:
        """Полное обновление данных с сайтов"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "standings": [],
            "matches": [],
            "upcoming": [],
            "scorers": []
        }
        
        # 1. Таблица
        standings = self.get_standings()
        if isinstance(standings, list) and not isinstance(standings, dict):
            results["standings"] = standings
        
        # 2. Сыгранные матчи
        matches = self.get_matches_with_goals()
        if isinstance(matches, list) and not isinstance(matches, dict):
            results["matches"] = matches
        
        # 3. Предстоящие матчи (календарь)
        upcoming = self.get_upcoming_matches()
        if isinstance(upcoming, list) and not isinstance(upcoming, dict):
            results["upcoming"] = upcoming
        
        # 4. Бомбардиры
        scorers = self.get_top_scorers()
        if isinstance(scorers, list) and not isinstance(scorers, dict):
            results["scorers"] = scorers
        
        # Сохраняем в файл
        with open("data/rpl_live_data.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        return results
