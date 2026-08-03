#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
XG Engine — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ 🔒

Превращает паспорт команды в ожидаемые голы (xG)

Pipeline:
1. Получение снапшотов (home + away)
2. Расчёт факторов
   - Attack Factor (из паспорта)
   - Defense Factor (из паспорта соперника)
   - Home Advantage (из паспорта)
   - Form Factor
   - Fatigue Factor
   - Performance Factor
   - Tactical Matchup Factor
   - XG Memory Correction (из xg_memory)
   - Passport Confidence Factor
3. xG_home = League_Mean × Attack_home × Defense_away × Home_Adv × Form × Fatigue × Performance × Tactical × Memory × Confidence
4. xG_away = League_Mean × Attack_away × Defense_home × Form × Fatigue × Performance × Tactical × Memory × Confidence
5. Сохранение в match_predictions

Статус: 🔒 ЗАМОРОЖЕН
"""

from typing import Dict, Tuple, Optional
from app.passport_manager import PassportManager
from app.database import FAJDatabase
from app.config import FAJConfig


class XGEngine:
    """Расчёт ожидаемых голов (xG) на основе паспортов команд"""

    def __init__(self):
        self.passport_manager = PassportManager()
        self.db = FAJDatabase()
        self.config = FAJConfig()
        
        self.league_mean_xg = self.config.LEAGUE_MEAN_XG
        self.xg_min = self.config.XG_MIN
        self.xg_max = self.config.XG_MAX  # Исправлено: из config.py

    # =========================================================
    # 1. ОСНОВНЫЕ ФАКТОРЫ
    # =========================================================

    def _attack_factor(self, snapshot: Dict) -> float:
        """
        Фактор атаки (0.5 - 2.0)
        
        Учитывает:
        - attack (базовая атака)
        - finishing (реализация)
        """
        attack = snapshot.get("attack", 50)
        finishing = snapshot.get("finishing", 50)
        
        avg_attack = (attack + finishing) / 2
        factor = 0.5 + (avg_attack / 100) * 1.5
        return max(0.5, min(2.0, factor))

    def _defense_factor(self, snapshot: Dict) -> float:
        """
        Фактор защиты (0.5 - 2.0)
        
        Учитывает:
        - defense (базовая защита)
        - discipline (дисциплина)
        - goalkeeper (вратарь)
        """
        defense = snapshot.get("defense", 50)
        discipline = snapshot.get("discipline", 50)
        goalkeeper = snapshot.get("goalkeeper", 50)
        
        avg_defense = (defense + discipline + goalkeeper) / 3
        factor = 2.0 - (avg_defense / 100) * 1.5
        return max(0.5, min(2.0, factor))

    def _form_factor(self, snapshot: Dict) -> float:
        """
        Фактор формы (0.7 - 1.3)
        
        Учитывает:
        - form (текущая форма)
        """
        form = snapshot.get("form", 50)
        factor = 0.7 + (form / 100) * 0.6
        return max(0.7, min(1.3, factor))

    def _fatigue_factor(self, snapshot: Dict) -> float:
        """
        Фактор усталости (0.7 - 1.1)
        
        Учитывает:
        - fatigue (усталость)
        - fitness (физическая готовность)
        """
        fatigue = snapshot.get("fatigue", 50)
        fitness = snapshot.get("fitness", 50)
        
        avg_fatigue = (fatigue + (100 - fitness)) / 2
        factor = 1.1 - (avg_fatigue / 100) * 0.4
        return max(0.7, min(1.1, factor))

    def _performance_factor(self, snapshot: Dict) -> float:
        """
        Фактор производительности (0.8 - 1.2)
        
        Учитывает:
        - average_performance (накопленный индекс качества игры)
        """
        avg_performance = snapshot.get("average_performance", 0)
        factor = 1.0 + avg_performance * 0.2
        return max(0.8, min(1.2, factor))

    def _tactical_factor(self, snapshot: Dict, opponent_style: str = "mixed") -> float:
        """
        Тактический фактор (0.8 - 1.2)
        
        Учитывает исторические данные против стилей:
        - vs_high_press
        - vs_low_block
        - vs_counter_attack
        """
        vs_high_press = snapshot.get("vs_high_press", 0)
        vs_low_block = snapshot.get("vs_low_block", 0)
        vs_counter_attack = snapshot.get("vs_counter_attack", 0)
        
        def normalize(value: float) -> float:
            return 1.0 + (value / 10) * 0.2
        
        if opponent_style == "high_press":
            factor = normalize(vs_high_press)
        elif opponent_style == "low_block":
            factor = normalize(vs_low_block)
        elif opponent_style == "counter":
            factor = normalize(vs_counter_attack)
        else:
            factor = 1.0
        
        return max(0.8, min(1.2, factor))

    def _confidence_factor(self, snapshot: Dict) -> float:
        """
        Фактор уверенности в паспорте (0.8 - 1.0)
        
        Учитывает:
        - passport_confidence (накопленная уверенность)
        """
        confidence = snapshot.get("passport_confidence", 0.4)
        factor = 0.7 + confidence * 0.3
        return max(0.7, min(1.0, factor))

    def _home_advantage_factor(self, snapshot: Dict) -> float:
        """
        Домашний фактор из паспорта команды
        
        Учитывает:
        - home_advantage (индивидуальный коэффициент команды)
        """
        home_adv = snapshot.get("home_advantage", self.config.HOME_ADVANTAGE)
        return max(1.0, min(1.2, home_adv))

    # =========================================================
    # 2. XG MEMORY CORRECTION
    # =========================================================

    def _xg_memory_factor(self, team_id: int, season_id: int) -> Dict[str, float]:
        """
        XG Memory Correction из xg_memory
        
        Учитывает:
        - attack_xg_deviation (историческое отклонение атаки)
        - defense_xg_deviation (историческое отклонение защиты)
        """
        attack_corr, defense_corr = self.passport_manager.get_xg_correction(
            team_id, season_id
        )
        
        return {
            "attack": 1 + attack_corr / 100,
            "defense": 1 + defense_corr / 100
        }

    # =========================================================
    # 3. XG РАСЧЁТ
    # =========================================================

    def calculate_xg(self, home_team_id: int, away_team_id: int,
                     season_id: int, match_id: int,
                     opponent_home_style: str = "mixed",
                     opponent_away_style: str = "mixed") -> Dict:
        """
        Расчёт xG для матча
        
        Args:
            home_team_id: ID домашней команды
            away_team_id: ID гостевой команды
            season_id: ID сезона
            match_id: ID матча
            opponent_home_style: Стиль соперника для хозяев
            opponent_away_style: Стиль соперника для гостей
        
        Returns:
            Dict: {
                "xg_home": float,
                "xg_away": float,
                "factors": {
                    "home": {...},
                    "away": {...}
                }
            }
        """
        # 1. Получаем снапшоты
        home_snapshot = self.passport_manager.get_match_snapshot(home_team_id, season_id)
        away_snapshot = self.passport_manager.get_match_snapshot(away_team_id, season_id)
        
        if not home_snapshot or not away_snapshot:
            return {"error": "Не удалось получить снапшоты команд"}
        
        # 2. XG Memory Correction для обеих команд
        home_memory = self._xg_memory_factor(home_team_id, season_id)
        away_memory = self._xg_memory_factor(away_team_id, season_id)
        
        # 3. Расчёт факторов для хозяев
        home_factors = {
            "attack": self._attack_factor(home_snapshot),
            "defense": self._defense_factor(away_snapshot),
            "form": self._form_factor(home_snapshot),
            "fatigue": self._fatigue_factor(home_snapshot),
            "performance": self._performance_factor(home_snapshot),
            "tactical": self._tactical_factor(home_snapshot, opponent_away_style),
            "confidence": self._confidence_factor(home_snapshot),
            "home_advantage": self._home_advantage_factor(home_snapshot),
            "memory_attack": home_memory["attack"],
            "memory_defense": home_memory["defense"]
        }
        
        # 4. Расчёт факторов для гостей
        away_factors = {
            "attack": self._attack_factor(away_snapshot),
            "defense": self._defense_factor(home_snapshot),
            "form": self._form_factor(away_snapshot),
            "fatigue": self._fatigue_factor(away_snapshot),
            "performance": self._performance_factor(away_snapshot),
            "tactical": self._tactical_factor(away_snapshot, opponent_home_style),
            "confidence": self._confidence_factor(away_snapshot),
            "memory_attack": away_memory["attack"],
            "memory_defense": away_memory["defense"]
        }
        
        # 5. Расчёт xG хозяев
        xg_home = (
            self.league_mean_xg *
            home_factors["attack"] *
            home_factors["defense"] *
            home_factors["form"] *
            home_factors["fatigue"] *
            home_factors["performance"] *
            home_factors["tactical"] *
            home_factors["confidence"] *
            home_factors["home_advantage"] *
            home_factors["memory_attack"] *
            home_factors["memory_defense"]
        )
        
        # 6. Расчёт xG гостей
        xg_away = (
            self.league_mean_xg *
            away_factors["attack"] *
            away_factors["defense"] *
            away_factors["form"] *
            away_factors["fatigue"] *
            away_factors["performance"] *
            away_factors["tactical"] *
            away_factors["confidence"] *
            away_factors["memory_attack"] *
            away_factors["memory_defense"]
        )
        
        # 7. Ограничения
        xg_home = max(self.xg_min, min(self.xg_max, xg_home))
        xg_away = max(self.xg_min, min(self.xg_max, xg_away))
        
        # 8. Округление
        xg_home = round(xg_home, 2)
        xg_away = round(xg_away, 2)
        
        # 9. Сохранение в БД
        self.db.save_match_prediction(
            match_id,
            xg_home,
            xg_away,
            lambda_home=xg_home,
            lambda_away=xg_away,
            home_advantage=home_factors["home_advantage"],
            prediction_type="standard",
            model_version="v12.0"
        )
        
        return {
            "xg_home": xg_home,
            "xg_away": xg_away,
            "factors": {
                "home": home_factors,
                "away": away_factors,
                "home_memory": home_memory,
                "away_memory": away_memory
            },
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "match_id": match_id,
            "season_id": season_id
        }

    # =========================================================
    # 4. РАСЧЁТ XG ДЛЯ МАТЧА ПО НАЗВАНИЯМ
    # =========================================================

    def calculate_xg_by_names(self, home_name: str, away_name: str,
                              league: str = "RPL", season: int = 2026) -> Dict:
        """
        Расчёт xG по названиям команд (удобно для тестирования)
        """
        home_team_id = self.db.get_team_id(home_name, league)
        away_team_id = self.db.get_team_id(away_name, league)
        season_id = self.db.get_season_id(league, str(season))
        
        if not home_team_id or not away_team_id or not season_id:
            return {"error": f"Команда или сезон не найдены: {home_name} или {away_name}"}
        
        match_id = self.db.add_match(
            round_id=1,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            competition=league
        )
        
        return self.calculate_xg(
            home_team_id, away_team_id,
            season_id, match_id
        )

    # =========================================================
    # 5. ПАКЕТНЫЙ РАСЧЁТ ДЛЯ ТУРА
    # =========================================================

    def calculate_round_xg(self, matches: list, season_id: int) -> list:
        """
        Пакетный расчёт xG для всех матчей тура
        
        Args:
            matches: список словарей с ключами home_team_id, away_team_id, match_id
            season_id: ID сезона
        
        Returns:
            list: результаты расчёта для каждого матча
        """
        results = []
        for match in matches:
            result = self.calculate_xg(
                match["home_team_id"],
                match["away_team_id"],
                season_id,
                match["match_id"]
            )
            results.append(result)
        return results


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    engine = XGEngine()
    
    print("=" * 50)
    print("FAJ XG Engine v12.0 - Тест")
    print("=" * 50)
    
    result = engine.calculate_xg_by_names("Зенит", "Спартак")
    
    if "error" in result:
        print(f"❌ Ошибка: {result['error']}")
    else:
        print(f"\n🏟 Зенит vs Спартак")
        print(f"⚽ xG: {result['xg_home']} - {result['xg_away']}")
        print("\n📊 Факторы:")
        print("  Хозяева:")
        for key, value in result["factors"]["home"].items():
            print(f"    {key}: {value:.3f}")
        print("  Гости:")
        for key, value in result["factors"]["away"].items():
            print(f"    {key}: {value:.3f}")
        print("\n🧠 XG Memory:")
        print(f"  Хозяева: attack={result['factors']['home_memory']['attack']:.3f}, defense={result['factors']['home_memory']['defense']:.3f}")
        print(f"  Гости: attack={result['factors']['away_memory']['attack']:.3f}, defense={result['factors']['away_memory']['defense']:.3f}")
