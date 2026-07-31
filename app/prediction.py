#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Prediction Engine v10.0
"""

import math
from typing import Dict
from scipy.stats import poisson
from app.learning_db import LearningDB


class FAJPrediction:
    def __init__(self):
        self.learning_db = LearningDB()
        self.base_xg = 1.35
        self.home_advantage = 1.12
    
    def get_team_passport(self, team_name: str) -> Dict:
        return self.learning_db.get_team_passport(team_name)
    
    def calculate_xg(self, home_team: str, away_team: str) -> Dict:
        home_data = self.get_team_passport(home_team)
        away_data = self.get_team_passport(away_team)
        
        if not home_data or not away_data:
            return {'home_xg': 1.35, 'away_xg': 1.35}
        
        home_attack = float(home_data.get('attack', 50)) / 100
        home_defense = float(home_data.get('defense', 50)) / 100
        home_form = float(home_data.get('form', 50)) / 100
        
        away_attack = float(away_data.get('attack', 50)) / 100
        away_defense = float(away_data.get('defense', 50)) / 100
        away_form = float(away_data.get('form', 50)) / 100
        
        home_xg = self.base_xg * (0.5 + 0.5 * home_attack) * (1.5 - 0.5 * away_defense) * (0.5 + 0.5 * home_form) * self.home_advantage
        away_xg = self.base_xg * (0.5 + 0.5 * away_attack) * (1.5 - 0.5 * home_defense) * (0.5 + 0.5 * away_form)
        
        return {'home_xg': round(home_xg, 2), 'away_xg': round(away_xg, 2)}
    
    def poisson_probabilities(self, home_xg: float, away_xg: float) -> Dict:
        scores = {}
        for i in range(6):
            for j in range(6):
                prob = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
                scores[f"{i}:{j}"] = prob
        
        total = sum(scores.values())
        if total > 0:
            for k in scores:
                scores[k] = scores[k] / total * 100
        
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        top_scores = [{'score': s[0], 'prob': round(s[1], 2)} for s in sorted_scores]
        
        p1 = sum(v for k, v in scores.items() if int(k.split(':')[0]) > int(k.split(':')[1]))
        pX = sum(v for k, v in scores.items() if int(k.split(':')[0]) == int(k.split(':')[1]))
        p2 = sum(v for k, v in scores.items() if int(k.split(':')[0]) < int(k.split(':')[1]))
        
        return {'P1': round(p1, 1), 'X': round(pX, 1), 'P2': round(p2, 1), 'top_scores': top_scores}
    
    def calculate_confidence(self, home_xg: float, away_xg: float) -> int:
        xg_diff = abs(home_xg - away_xg)
        xg_score = min(xg_diff / 1.5 * 100, 100)
        probs = self.poisson_probabilities(home_xg, away_xg)
        uncertainty = 100 - max(probs['P1'], probs['X'], probs['P2'])
        confidence = xg_score * 0.5 + uncertainty * 0.5
        return round(min(max(confidence, 0), 100))
    
    def predict_match(self, home_team: str, away_team: str) -> Dict:
        try:
            xg = self.calculate_xg(home_team, away_team)
            probs = self.poisson_probabilities(xg['home_xg'], xg['away_xg'])
            confidence = self.calculate_confidence(xg['home_xg'], xg['away_xg'])
            
            # Тотал > 2.5
            total_over25 = 0
            for i in range(6):
                for j in range(6):
                    if i + j > 2.5:
                        total_over25 += poisson.pmf(i, xg['home_xg']) * poisson.pmf(j, xg['away_xg'])
            total_over25 = round(total_over25 * 100, 1)
            
            # Обе забьют
            btts = 1 - math.exp(-xg['home_xg']) - math.exp(-xg['away_xg']) + math.exp(-(xg['home_xg'] + xg['away_xg']))
            btts = round(btts * 100, 1)
            
            # Лучшая ставка
            max_prob = max(probs['P1'], probs['X'], probs['P2'])
            if max_prob == probs['P1']:
                best_bet = f"Победа {home_team}"
            elif max_prob == probs['X']:
                best_bet = "Ничья"
            else:
                best_bet = f"Победа {away_team}"
            
            return {
                'version': '10.0',
                'home_team': home_team,
                'away_team': away_team,
                'xg': xg,
                'probability': {'P1': probs['P1'], 'X': probs['X'], 'P2': probs['P2']},
                'top_scores': probs['top_scores'],
                'confidence': confidence,
                'total_over25': total_over25,
                'btts': btts,
                'best_bet': best_bet,
                'explanation': f"Анализ матча {home_team} vs {away_team}. xG: {xg['home_xg']} - {xg['away_xg']}. Уверенность: {confidence}%."
            }
        except Exception as e:
            return {'error': str(e)}
