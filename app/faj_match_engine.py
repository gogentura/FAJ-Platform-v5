#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Match Prediction Engine
"""

import math
import random
from typing import Dict, Tuple, List
from collections import Counter


class FAJMatchEngine:
    
    def __init__(self):
        self.league_mean_xg = 1.35
        self.home_advantage = 1.12
        self.simulation_count = 10000
        
        self.weights = {
            "attack": 0.18,
            "defense": 0.18,
            "control": 0.15,
            "efficiency": 0.12,
            "mentality": 0.10,
            "tempo": 0.05,
            "press": 0.05,
            "transition": 0.05,
            "flexibility": 0.05,
            "coach": 0.04,
            "form": 0.03
        }
    
    def calculate_team_power(self, passport: Dict) -> float:
        power = 0
        for key, weight in self.weights.items():
            value = passport.get(key, 50)
            try:
                power += float(value) * weight
            except:
                power += 50 * weight
        return round(power, 2)
    
    def calculate_xg(self, home_passport: Dict, away_passport: Dict) -> Tuple[float, float]:
        home_attack = float(home_passport.get("attack", 50)) / 100
        away_defense = float(away_passport.get("defense", 50)) / 100
        home_form = float(home_passport.get("form", 50)) / 100
        away_attack = float(away_passport.get("attack", 50)) / 100
        home_defense = float(home_passport.get("defense", 50)) / 100
        away_form = float(away_passport.get("form", 50)) / 100
        
        xg_home = self.league_mean_xg * (home_attack / max(away_defense, 0.01)) * (0.5 + 0.5 * home_form) * self.home_advantage
        xg_away = self.league_mean_xg * (away_attack / max(home_defense, 0.01)) * (0.5 + 0.5 * away_form)
        
        xg_home = max(0.10, min(4.00, xg_home))
        xg_away = max(0.10, min(4.00, xg_away))
        
        return round(xg_home, 2), round(xg_away, 2)
    
    def poisson_sample(self, xg: float) -> int:
        if xg <= 0:
            return 0
        L = math.exp(-xg)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1
    
    def monte_carlo_simulation(self, xg_home: float, xg_away: float) -> Dict:
        results = []
        for _ in range(self.simulation_count):
            results.append((self.poisson_sample(xg_home), self.poisson_sample(xg_away)))
        
        home_wins = sum(1 for h, a in results if h > a)
        draws = sum(1 for h, a in results if h == a)
        away_wins = sum(1 for h, a in results if h < a)
        
        score_counter = Counter(results)
        top_scores = score_counter.most_common(5)
        
        return {
            "P1": home_wins / self.simulation_count,
            "PX": draws / self.simulation_count,
            "P2": away_wins / self.simulation_count,
            "top_scores": [{"score": f"{h}:{a}", "prob": round(count / self.simulation_count * 100, 1)} 
                          for (h, a), count in top_scores]
        }
    
    def calculate_btts(self, xg_home: float, xg_away: float) -> float:
        from math import exp
        p_home_zero = exp(-xg_home)
        p_away_zero = exp(-xg_away)
        return 1 - p_home_zero - p_away_zero + (p_home_zero * p_away_zero)
    
    def calculate_over25(self, xg_home: float, xg_away: float) -> float:
        from math import exp
        prob_under25 = 0
        for i in range(3):
            for j in range(3):
                if i + j <= 2:
                    prob_under25 += (exp(-xg_home) * (xg_home ** i)) / (i ** 0.5 if i == 0 else 1) * \
                                   (exp(-xg_away) * (xg_away ** j)) / (j ** 0.5 if j == 0 else 1)
        return 1 - prob_under25
    
    def calculate_confidence(self, p1: float, px: float, p2: float) -> int:
        max_prob = max(p1, px, p2)
        confidence = 50 + max_prob * 40
        return round(min(confidence, 95))
    
    def calculate_risk(self, p1: float, px: float, p2: float, xg_diff: float, form_diff: float) -> str:
        risk_score = abs(p1 - p2) * 50 + abs(xg_diff) * 20 + abs(form_diff) * 10
        if risk_score < 20:
            return "Низкий"
        elif risk_score < 40:
            return "Средний"
        else:
            return "Высокий"
    
    def predict_match(self, home_passport: Dict, away_passport: Dict) -> Dict:
        home_power = self.calculate_team_power(home_passport)
        away_power = self.calculate_team_power(away_passport)
        
        xg_home, xg_away = self.calculate_xg(home_passport, away_passport)
        
        mc_results = self.monte_carlo_simulation(xg_home, xg_away)
        
        btts = self.calculate_btts(xg_home, xg_away) * 100
        over25 = self.calculate_over25(xg_home, xg_away) * 100
        confidence = self.calculate_confidence(mc_results["P1"], mc_results["PX"], mc_results["P2"])
        
        form_diff = abs(float(home_passport.get("form", 50)) - float(away_passport.get("form", 50))) / 100
        xg_diff = abs(xg_home - xg_away)
        risk = self.calculate_risk(mc_results["P1"], mc_results["PX"], mc_results["P2"], xg_diff, form_diff)
        
        return {
            "home_power": home_power,
            "away_power": away_power,
            "xg_home": xg_home,
            "xg_away": xg_away,
            "home_win": round(mc_results["P1"] * 100, 1),
            "draw": round(mc_results["PX"] * 100, 1),
            "away_win": round(mc_results["P2"] * 100, 1),
            "top_scores": mc_results["top_scores"],
            "btts": round(btts, 1),
            "over25": round(over25, 1),
            "confidence": confidence,
            "risk": risk
        }
