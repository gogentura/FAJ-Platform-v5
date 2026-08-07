#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Soccerland Adapter — адаптер для soccerland.ru
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from datetime import datetime

from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class SoccerlandAdapter(BaseAdapter):
    """Адаптер для парсинга soccerland.ru"""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.base_url = "https://soccerland.ru/russia/premier-liga/2026-2027"
        self._source = "soccerland"
        self._version = "1.0"
        self.enabled = True  # ← Флаг включения

    def get_source_name(self) -> str:
        return self._source

    def get_source_version(self) -> str:
        return self._version

    def get_matches(self, league: str = "РПЛ") -> List[Dict]:
        """Получение сыгранных матчей с soccerland.ru"""
        if not self.enabled:
            logger.info("ℹ️ Soccerland adapter отключён")
            return []

        logger.info(f"📡 Парсинг матчей с soccerland.ru...")
        
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            
            if not response.ok:
                logger.error(f"❌ Источник недоступен: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            matches = []
            match_blocks = soup.find_all('div', class_=re.compile(r'match|game|fixture|result'))

            for block in match_blocks:
                try:
                    home_elem = block.find('span', class_=re.compile(r'home|team1'))
                    away_elem = block.find('span', class_=re.compile(r'away|team2'))
                    
                    if not home_elem or not away_elem:
                        continue

                    home_name = home_elem.text.strip()
                    away_name = away_elem.text.strip()

                    score_elem = block.find('span', class_=re.compile(r'score|result'))
                    home_goals, away_goals = None, None
                    status = self.STATUS_SCHEDULED

                    if score_elem:
                        score_text = score_elem.text.strip()
                        if score_text and score_text not in ['– : –', '–', '']:
                            home_goals, away_goals = self._parse_score(score_text)
                            if home_goals is not None and away_goals is not None:
                                status = self.STATUS_FINISHED

                    # Дата — парсим реальную, если нет — None
                    date_elem = block.find('span', class_=re.compile(r'date|time'))
                    date = None
                    if date_elem:
                        date_text = date_elem.text.strip()
                        if date_text:
                            date = date_text

                    # Тур
                    round_elem = block.find('span', class_=re.compile(r'round|tour'))
                    round_num = None
                    if round_elem:
                        try:
                            round_text = round_elem.text.strip()
                            round_match = re.search(r'(\d+)', round_text)
                            if round_match:
                                round_num = int(round_match.group(1))
                        except:
                            pass

                    # xG
                    home_xg, away_xg = None, None
                    xg_elem = block.find('span', class_=re.compile(r'xg|xG'))
                    if xg_elem:
                        xg_text = xg_elem.text.strip()
                        xg_parts = re.split(r'[–\-:]', xg_text)
                        if len(xg_parts) == 2:
                            try:
                                home_xg = float(xg_parts[0].strip())
                                away_xg = float(xg_parts[1].strip())
                            except:
                                pass

                    raw_data = {
                        "home_team": home_name,
                        "away_team": away_name,
                        "home_goals": home_goals,
                        "away_goals": away_goals,
                        "date": date,
                        "round": round_num,
                        "status": status,
                        "home_xg": home_xg,
                        "away_xg": away_xg,
                        "source": self._source,
                        "source_version": self._version
                    }

                    validated = self.validate_match(raw_data)
                    if validated:
                        matches.append(validated)

                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга матча: {e}")
                    continue

            logger.info(f"✅ Получено {len(matches)} матчей")
            return matches

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки матчей: {e}")
            return []

    def get_fixtures(self, league: str = "РПЛ") -> List[Dict]:
        """Получение календаря с soccerland.ru"""
        if not self.enabled:
            logger.info("ℹ️ Soccerland adapter отключён")
            return []

        logger.info(f"📡 Парсинг календаря с soccerland.ru...")
        
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            
            if not response.ok:
                logger.error(f"❌ Источник недоступен: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            fixtures = []
            fixture_blocks = soup.find_all('div', class_=re.compile(r'fixture|upcoming|schedule'))

            for block in fixture_blocks:
                try:
                    home_elem = block.find('span', class_=re.compile(r'home|team1'))
                    away_elem = block.find('span', class_=re.compile(r'away|team2'))
                    
                    if not home_elem or not away_elem:
                        continue

                    home_name = home_elem.text.strip()
                    away_name = away_elem.text.strip()

                    date_elem = block.find('span', class_=re.compile(r'date|time'))
                    date = None
                    if date_elem:
                        date_text = date_elem.text.strip()
                        if date_text:
                            date = date_text

                    round_elem = block.find('span', class_=re.compile(r'round|tour'))
                    round_num = None
                    if round_elem:
                        try:
                            round_text = round_elem.text.strip()
                            round_match = re.search(r'(\d+)', round_text)
                            if round_match:
                                round_num = int(round_match.group(1))
                        except:
                            pass

                    raw_data = {
                        "home_team": home_name,
                        "away_team": away_name,
                        "date": date,
                        "round": round_num,
                        "status": self.STATUS_SCHEDULED,
                        "source": self._source,
                        "source_version": self._version
                    }

                    validated = self.validate_match(raw_data)
                    if validated:
                        fixtures.append(validated)

                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга календаря: {e}")
                    continue

            logger.info(f"✅ Получено {len(fixtures)} матчей календаря")
            return fixtures

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки календаря: {e}")
            return []

    def get_standings(self, league: str = "РПЛ") -> List[Dict]:
        """Получение турнирной таблицы с soccerland.ru"""
        if not self.enabled:
            logger.info("ℹ️ Soccerland adapter отключён")
            return []

        logger.info(f"📡 Парсинг таблицы с soccerland.ru...")
        
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=15)
            
            if not response.ok:
                logger.error(f"❌ Источник недоступен: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')

            standings = []
            table = soup.find('table')
            if not table:
                tables = soup.find_all('table')
                for t in tables:
                    if 'команда' in t.text.lower() or 'team' in t.text.lower():
                        table = t
                        break

            if table:
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 7:
                        try:
                            team_name = cols[1].text.strip()
                            normalized_team = self.normalize_team_name(team_name)
                            
                            if normalized_team:
                                goals_for, goals_against = self._parse_goals(cols[6].text.strip())
                                
                                standings.append({
                                    "team": normalized_team,
                                    "place": int(cols[0].text.strip()),
                                    "games": int(cols[2].text.strip()),
                                    "wins": int(cols[3].text.strip()),
                                    "draws": int(cols[4].text.strip()),
                                    "losses": int(cols[5].text.strip()),
                                    "goals_for": goals_for,
                                    "goals_against": goals_against,
                                    "points": int(cols[7].text.strip()) if len(cols) > 7 else 0,
                                    "source": self._source,
                                    "source_version": self._version
                                })
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка парсинга строки таблицы: {e}")
                            continue

            logger.info(f"✅ Получено {len(standings)} записей таблицы")
            return standings

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки таблицы: {e}")
            return []
