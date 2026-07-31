#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Match Prediction Engine v6.9
Полноценный движок прогнозирования матчей

Использует:
- FAJ Team Power
- xG Engine
- Poisson Distribution
- Monte Carlo Simulation (10,000 итераций)
- Expert Layer (коррекция ±5%)
- Нормализация вероятностей
"""

import math
import random
from typing import Dict, Tuple, List
from collections import Counter


class FAJMatchEngine:
    """Главный движок прогнозирования матчей FAJ"""
    
    def __init__(self):
        self.league_mean_xg = 1.35
        self.home_advantage = 1.12
        self.simulation_count = 10000
        self.expert_weight = 0.15
        self.model_weight = 0.85
        
        # Веса для FAJ Power
        self.weights = {
            "attack": 0.18,
            "defense": 0.18,
            "control": 0.15,
            "efficiency": 0.12,
            "mentality": 0.10,
            "tempo": 0.05,
            "press": 0.05,
            "transition": 0.05,
            "tactical": 0.05,
            "coach": 0.04,
            "form": 0.03
        }
    
    def calculate_team_power(self, passport: Dict) -> float:
        """
        Расчёт FAJ Team Power по формуле:
        Attack*0.18 + Defense*0.18 + Control*0.15 + Efficiency*0.12 +
        Mentality*0.10 + Tempo*0.05 + Press*0.05 + Transition*0.05 +
        Tactical*0.05 + Coach*0.04 + Form*0.03
        """
        power = 0
        for key, weight in self.weights.items():
            value = passport.get(key, 50)
            try:
                power += float(value) * weight
            except (TypeError, ValueError):
                power += 50 * weight
        return round(power, 2)
    
    def calculate_xg(self, home_passport: Dict, away_passport: Dict) -> Tuple[float, float]:
        """
        Расчёт xG для матча
        xG_home = LEAGUE_MEAN_XG * (Attack_home/Defense_away) * Form_home * Home_modifier
        """
        home_attack = float(home_passport.get("attack", 50)) / 100
        away_defense = float(away_passport.get("defense", 50)) / 100
        home_form = float(home_passport.get("form", 50)) / 100
        
        away_attack = float(away_passport.get("attack", 50)) / 100
        home_defense = float(home_passport.get("defense", 50)) / 100
        away_form = float(away_passport.get("form", 50)) / 100
        
        xg_home = self.league_mean_xg * (home_attack / max(away_defense, 0.01)) * (0.5 + 0.5 * home_form) * self.home_advantage
        xg_away = self.league_mean_xg * (away_attack / max(home_defense, 0.01)) * (0.5 + 0.5 * away_form)
        
        # Ограничение
        xg_home = max(0.10, min(4.00, xg_home))
        xg_away = max(0.10, min(4.00, xg_away))
        
        return round(xg_home, 2), round(xg_away, 2)
    
    def poisson_probability(self, goals: int, xg: float) -> float:
        """Вероятность количества голов по распределению Пуассона"""
        if xg == 0:
            return 1.0 if goals == 0 else 0.0
        try:
            from math import exp, factorial
            return (exp(-xg) * (xg ** goals)) / factorial(goals)
        except:
            return 0.0
    
    def calculate_probabilities(self, xg_home: float, xg_away: float) -> Dict:
        """
        Расчёт вероятностей через Poisson Score Matrix
        """
        max_goals = 7
        score_matrix = {}
        
        # Строим матрицу вероятностей всех счетов
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                prob = self.poisson_probability(i, xg_home) * self.poisson_probability(j, xg_away)
                if prob > 0.0001:
                    score_matrix[f"{i}:{j}"] = prob
        
        # Рассчитываем исходы
        p1 = sum(prob for score, prob in score_matrix.items() 
                if int(score.split(':')[0]) > int(score.split(':')[1]))
        px = sum(prob for score, prob in score_matrix.items() 
                if int(score.split(':')[0]) == int(score.split(':')[1]))
        p2 = sum(prob for score, prob in score_matrix.items() 
                if int(score.split(':')[0]) < int(score.split(':')[1]))
        
        return {
            "P1": p1,
            "PX": px,
            "P2": p2,
            "score_matrix": score_matrix
        }
    
    def monte_carlo_simulation(self, xg_home: float, xg_away: float) -> Dict:
        """
        Monte Carlo симуляция для уточнения вероятностей
        """
        results = []
        
        for _ in range(self.simulation_count):
            home_goals = self.poisson_sample(xg_home)
            away_goals = self.poisson_sample(xg_away)
            results.append((home_goals, away_goals))
        
        # Подсчёт исходов
        home_wins = sum(1 for h, a in results if h > a)
        draws = sum(1 for h, a in results if h == a)
        away_wins = sum(1 for h, a in results if h < a)
        
        # Топ-5 счетов
        score_counter = Counter(results)
        top_scores = score_counter.most_common(5)
        
        return {
            "P1": home_wins / self.simulation_count,
            "PX": draws / self.simulation_count,
            "P2": away_wins / self.simulation_count,
            "top_scores": [{"score": f"{h}:{a}", "prob": round(count / self.simulation_count * 100, 1)} 
                          for (h, a), count in top_scores]
        }
    
    def poisson_sample(self, xg: float) -> int:
        """Генерация случайного количества голов по распределению Пуассона"""
        if xg <= 0:
            return 0
        L = math.exp(-xg)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1
    
    def calculate_btts(self, xg_home: float, xg_away: float) -> float:
        """Вероятность того, что обе команды забьют"""
        p_home_zero = self.poisson_probability(0, xg_home)
        p_away_zero = self.poisson_probability(0, xg_away)
        return 1 - p_home_zero - p_away_zero + (p_home_zero * p_away_zero)
    
    def calculate_over25(self, xg_home: float, xg_away: float) -> float:
        """Вероятность того, что тотал матча больше 2.5"""
        prob_under25 = 0
        for i in range(3):
            for j in range(3):
                if i + j <= 2:
                    prob_under25 += self.poisson_probability(i, xg_home) * self.poisson_probability(j, xg_away)
        return 1 - prob_under25
    
    def calculate_confidence(self, p1: float, px: float, p2: float) -> int:
        """Расчёт уверенности модели"""
        max_prob = max(p1, px, p2)
        confidence = 50 + max_prob * 40
        return round(min(confidence, 95))
    
    def apply_expert_layer(self, model_probs: Dict, expert_probs: Dict) -> Dict:
        """
        Применение экспертного слоя
        Модель * 0.85 + Эксперт * 0.15
        """
        final = {
            "P1": model_probs["P1"] * self.model_weight + expert_probs.get("P1", 0) * self.expert_weight,
            "PX": model_probs["PX"] * self.model_weight + expert_probs.get("PX", 0) * self.expert_weight,
            "P2": model_probs["P2"] * self.model_weight + expert_probs.get("P2", 0) * self.expert_weight
        }
        
        # Нормализация
        total = final["P1"] + final["PX"] + final["P2"]
        if total > 0:
            final["P1"] = final["P1"] / total
            final["PX"] = final["PX"] / total
            final["P2"] = final["P2"] / total
        
        return final
    
    def calculate_risk(self, p1: float, px: float, p2: float, xg_diff: float, form_diff: float) -> str:
        """Расчёт уровня риска матча"""
        risk_score = abs(p1 - p2) * 50 + abs(xg_diff) * 20 + abs(form_diff) * 10
        
        if risk_score < 20:
            return "Низкий"
        elif risk_score < 40:
            return "Средний"
        else:
            return "Высокий"
    
    def predict_match(self, home_passport: Dict, away_passport: Dict, expert_probs: Dict = None) -> Dict:
        """
        Главный метод прогнозирования матча
        
        Args:
            home_passport: Паспорт домашней команды
            away_passport: Паспорт гостевой команды
            expert_probs: Экспертные вероятности (опционально)
        
        Returns:
            Dict с полным прогнозом
        """
        # 1. FAJ Power
        home_power = self.calculate_team_power(home_passport)
        away_power = self.calculate_team_power(away_passport)
        
        # 2. xG
        xg_home, xg_away = self.calculate_xg(home_passport, away_passport)
        
        # 3. Monte Carlo
        mc_results = self.monte_carlo_simulation(xg_home, xg_away)
        
        model_probs = {
            "P1": mc_results["P1"],
            "PX": mc_results["PX"],
            "P2": mc_results["P2"]
        }
        
        # 4. Expert Layer
        if expert_probs:
            final_probs = self.apply_expert_layer(model_probs, expert_probs)
        else:
            final_probs = model_probs
        
        # 5. Дополнительные показатели
        btts = self.calculate_btts(xg_home, xg_away) * 100
        over25 = self.calculate_over25(xg_home, xg_away) * 100
        confidence = self.calculate_confidence(final_probs["P1"], final_probs["PX"], final_probs["P2"])
        
        # 6. Риск
        form_diff = abs(float(home_passport.get("form", 50)) - float(away_passport.get("form", 50))) / 100
        xg_diff = abs(xg_home - xg_away)
        risk = self.calculate_risk(final_probs["P1"], final_probs["PX"], final_probs["P2"], xg_diff, form_diff)
        
        # 7. Результат
        return {
            "home_power": home_power,
            "away_power": away_power,
            "xg_home": xg_home,
            "xg_away": xg_away,
            "home_win": round(final_probs["P1"] * 100, 1),
            "draw": round(final_probs["PX"] * 100, 1),
            "away_win": round(final_probs["P2"] * 100, 1),
            "top_scores": mc_results["top_scores"],
            "btts": round(btts, 1),
            "over25": round(over25, 1),
            "confidence": confidence,
            "risk": risk,
            "model_probabilities": {k: round(v * 100, 1) for k, v in model_probs.items()},
            "final_probabilities": {k: round(v * 100, 1) for k, v in final_probs.items()}
        }


# =====================================================
# ТЕСТИРОВАНИЕ
# =====================================================

if __name__ == "__main__":
    engine = FAJMatchEngine()
    
    # Тестовые паспорта (для примера)
    home = {"attack": 82, "defense": 80, "control": 80, "efficiency": 81, "mentality": 78,
            "tempo": 80, "press": 76, "transition": 74, "tactical": 76, "coach": 78, "form": 82}
    away = {"attack": 70, "defense": 74, "control": 72, "efficiency": 69, "mentality": 70,
            "tempo": 72, "press": 68, "transition": 62, "tactical": 70, "coach": 68, "form": 70}
    
    result = engine.predict_match(home, away)
    
    print("=" * 50)
    print("FAJ Match Prediction Engine v6.9 - Тест")
    print("=" * 50)
    print(f"xG: {result['xg_home']} - {result['xg_away']}")
    print(f"Вероятности: П1 {result['home_win']}% | X {result['draw']}% | П2 {result['away_win']}%")
    print(f"BTTS: {result['btts']}%")
    print(f"Тотал > 2.5: {result['over25']}%")
    print(f"Уверенность: {result['confidence']}%")
    print(f"Риск: {result['risk']}")
    print("\nТоп счета:")
    for score in result['top_scores'][:3]:
        print(f"  {score['score']} - {score['prob']}%")
