#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Adapter — единый интерфейс для всех источников данных
"""

import hashlib
import re
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

# ============================================================
# ЕДИНЫЙ СПИСОК КОМАНД РПЛ 2026/27
# ============================================================

RPL_TEAMS_2026_27 = [
    "Зенит",
    "Спартак",
    "ЦСКА",
    "Динамо Москва",
    "Локомотив",
    "Краснодар",
    "Ростов",
    "Рубин",
    "Ахмат",
    "Крылья Советов",
    "Акрон",
    "Балтика",
    "Оренбург",
    "Факел",
    "Динамо Махачкала",
    "Родина"
]

# ============================================================
# НОРМАЛИЗАЦИЯ НАЗВАНИЙ КОМАНД
# ============================================================

TEAM_ALIASES = {
    "Зенит (СПб)": "Зенит",
    "Зенит СПб": "Зенит",
    "Спартак М": "Спартак",
    "Спартак (М)": "Спартак",
    "Спартак Москва": "Спартак",
    "ЦСКА М": "ЦСКА",
    "ЦСКА (М)": "ЦСКА",
    "Динамо (М)": "Динамо Москва",
    "Динамо М": "Динамо Москва",
    "Динамо Москва": "Динамо Москва",
    "Динамо Мх": "Динамо Махачкала",
    "Динамо (Мх)": "Динамо Махачкала",
    "Динамо Махачкала": "Динамо Махачкала",
    "Локомотив М": "Локомотив",
    "Локомотив (М)": "Локомотив",
    "Краснодар (Кр)": "Краснодар",
    "Ростов (РнД)": "Ростов",
    "Рубин (Кз)": "Рубин",
    "Ахмат (Гр)": "Ахмат",
    "Крылья Советов (С)": "Крылья Советов",
    "Крылья": "Крылья Советов",
    "Акрон (Тл)": "Акрон",
    "Балтика (Кл)": "Балтика",
    "Оренбург (Ор)": "Оренбург",
    "Факел (Вр)": "Факел",
    "Родина (М)": "Родина",
    "Пари НН": None,  # Исключаем — нет в РПЛ 2026/27
    "Пари Нижний Новгород": None,
}


class BaseAdapter(ABC):
    """Базовый класс для всех адаптеров источников данных"""

    # ============================================================
    # СТАТУСЫ МАТЧЕЙ (ЕДИНЫЙ СТАНДАРТ)
    # ============================================================

    STATUS_SCHEDULED = "SCHEDULED"
    STATUS_LIVE = "LIVE"
    STATUS_FINISHED = "FINISHED"
    STATUS_POSTPONED = "POSTPONED"
    STATUS_CANCELLED = "CANCELLED"

    @abstractmethod
    def get_matches(self, league: str = "РПЛ") -> List[Dict]:
        """
        Получение сыгранных матчей с результатами
        
        Returns:
            List[Dict]: [
                {
                    "home_team": str,
                    "away_team": str,
                    "home_goals": int,
                    "away_goals": int,
                    "date": str,
                    "round": int,
                    "status": str,
                    "home_xg": Optional[float],
                    "away_xg": Optional[float],
                    "home_possession": Optional[int],
                    "away_possession": Optional[int],
                    "home_shots": Optional[int],
                    "away_shots": Optional[int],
                    "home_shots_on_target": Optional[int],
                    "away_shots_on_target": Optional[int],
                    "source": str,
                    "source_version": str,
                    "data_quality": float
                }
            ]
        """
        pass

    @abstractmethod
    def get_fixtures(self, league: str = "РПЛ") -> List[Dict]:
        """
        Получение предстоящих матчей (календарь)
        
        Returns:
            List[Dict]: [
                {
                    "home_team": str,
                    "away_team": str,
                    "date": str,
                    "round": int,
                    "status": str,
                    "source": str,
                    "source_version": str
                }
            ]
        """
        pass

    @abstractmethod
    def get_standings(self, league: str = "РПЛ") -> List[Dict]:
        """
        Получение турнирной таблицы
        
        Returns:
            List[Dict]: [
                {
                    "team": str,
                    "place": int,
                    "games": int,
                    "wins": int,
                    "draws": int,
                    "losses": int,
                    "goals_for": int,
                    "goals_against": int,
                    "points": int,
                    "source": str,
                    "source_version": str
                }
            ]
        """
        pass

    def get_scorers(self, league: str = "РПЛ") -> List[Dict]:
        """Получение списка бомбардиров (опционально)"""
        return []

    # ============================================================
    # ОБЩИЕ МЕТОДЫ ДЛЯ ВСЕХ АДАПТЕРОВ
    # ============================================================

    def get_source_name(self) -> str:
        return self.__class__.__name__.replace("Adapter", "").lower()

    def get_source_version(self) -> str:
        return "1.0"

    def normalize_team_name(self, name: str) -> Optional[str]:
        """Приводит название команды к единому стандарту"""
        if not name:
            return None
        
        name = name.strip()
        
        # Прямое совпадение
        if name in RPL_TEAMS_2026_27:
            return name
        
        # Поиск по алиасам
        if name in TEAM_ALIASES:
            return TEAM_ALIASES[name]
        
        # Поиск по частичному совпадению
        for alias, normalized in TEAM_ALIASES.items():
            if alias.lower() in name.lower() or name.lower() in alias.lower():
                return normalized
        
        # Поиск по списку команд
        for team in RPL_TEAMS_2026_27:
            if team.lower() in name.lower() or name.lower() in team.lower():
                return team
        
        return None

    def validate_match(self, data: Dict) -> Dict:
        """
        Валидация и нормализация данных матча
        
        Returns:
            Dict с гарантированными полями
        """
        # Нормализация команд
        home_team = self.normalize_team_name(data.get('home_team'))
        away_team = self.normalize_team_name(data.get('away_team'))
        
        # Пропускаем, если команды не валидны
        if not home_team or not away_team:
            return None
        
        # Статус
        status = data.get('status', self.STATUS_SCHEDULED).upper()
        if status not in [self.STATUS_SCHEDULED, self.STATUS_LIVE, self.STATUS_FINISHED,
                          self.STATUS_POSTPONED, self.STATUS_CANCELLED]:
            status = self.STATUS_SCHEDULED
        
        # Рассчёт data_quality
        data_quality = self._calculate_quality(data)
        
        return {
            "home_team": home_team,
            "away_team": away_team,
            "date": data.get('date'),
            "round": data.get('round'),
            "season": data.get('season', '2026/27'),
            "status": status,
            "home_goals": data.get('home_goals'),
            "away_goals": data.get('away_goals'),
            "home_xg": data.get('home_xg'),
            "away_xg": data.get('away_xg'),
            "home_possession": data.get('home_possession'),
            "away_possession": data.get('away_possession'),
            "home_shots": data.get('home_shots'),
            "away_shots": data.get('away_shots'),
            "home_shots_on_target": data.get('home_shots_on_target'),
            "away_shots_on_target": data.get('away_shots_on_target'),
            "source": data.get('source', self.get_source_name()),
            "source_version": data.get('source_version', self.get_source_version()),
            "data_quality": data_quality,
            "match_uuid": data.get('match_uuid') or self._generate_uuid(data)
        }

    def _calculate_quality(self, data: Dict) -> float:
        """Рассчёт качества данных"""
        quality = 0.0
        
        # Есть счёт (0.3)
        if data.get('home_goals') is not None and data.get('away_goals') is not None:
            quality += 0.3
        
        # Есть дата (0.25)
        if data.get('date'):
            quality += 0.25
        
        # Есть тур (0.2)
        if data.get('round'):
            quality += 0.2
        
        # Есть xG (0.15)
        if data.get('home_xg') is not None or data.get('away_xg') is not None:
            quality += 0.15
        
        # Есть статистика (0.1)
        if data.get('home_possession') is not None:
            quality += 0.05
        if data.get('home_shots') is not None:
            quality += 0.05
        
        return round(quality, 2)

    def _generate_uuid(self, data: Dict) -> str:
        """Генерация UUID для матча"""
        key = f"{data.get('home_team', '')}_{data.get('away_team', '')}_{data.get('date', '')}_{data.get('round', '')}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    def _parse_score(self, score: str) -> tuple:
        """Парсинг счёта из строки"""
        if not score:
            return None, None
        try:
            if ':' in score:
                parts = score.split(':')
                return int(parts[0].strip()), int(parts[1].strip())
            elif '-' in score:
                parts = score.split('-')
                return int(parts[0].strip()), int(parts[1].strip())
        except:
            pass
        return None, None

    def _parse_goals(self, goals_str: str) -> tuple:
        """Парсинг голов из строки вида '15-8'"""
        if not goals_str:
            return 0, 0
        try:
            if '-' in goals_str:
                parts = goals_str.split('-')
                return int(parts[0].strip()), int(parts[1].strip())
        except:
            pass
        return 0, 0
