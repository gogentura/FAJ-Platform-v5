#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Prediction Engine v10.0
Интеграция с Learning DB и скорректированными весами
"""

import math
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.stats import poisson
from app.learning_db import LearningDB


class FAJPrediction:
    """Главный движок прогнозирования FAJ с самообучением"""
    
    def __init__(self):
        self.learning_db = LearningDB()
        self.weights = self.learning_db.get_current_weights()
        self.base_xg = 1.35
        self.home_advantage = 1.12
        
    def get_team_passport(self, team_name: str) -> Dict:
        """Получить паспорт команды из Learning DB"""
        return self.learning_db.get_team_passport(team_name)
    
    def calculate_faj_rating(self, team_data: Dict) -> float:
        """Расчет FAJ Rating по формуле"""
        if not team_data:
            return 50.0
        
        rating = 0
        for key, weight in self.weights.items():
            value = team_data.get(key, 50)
            try:
                rating += float(value) * weight
            except (TypeError, ValueError):
                rating += 50 * weight
        return round(rating, 1)
    
    def calculate_xg(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Расчет xG для матча"""
        home_data = self.get_team_passport(home_team)
        away_data = self.get_team_passport(away_team)
        
        if not home_data or not away_data:
            # Если данных нет, используем средние значения
            return {'home_xg': 1.35, 'away_xg': 1.35}
        
        # Параметры команд
        home_attack = float(home_data.get('attack', 50)) / 100
        home_defense = float(home_data.get('defense', 50)) / 100
        home_form = float(home_data.get('form', 50)) / 100
        home_control = float(home_data.get('control', 50)) / 100
        
        away_attack = float(away_data.get('attack', 50)) / 100
        away_defense = float(away_data.get('defense', 50)) / 100
        away_form = float(away_data.get('form', 50)) / 100
        away_control = float(away_data.get('control', 50)) / 100
        
        # Расчет xG по формуле с учетом весов
        home_xg = (
            self.base_xg *
            (0.5 + 0.5 * home_attack) *
            (1.5 - 0.5 * away_defense) *
            (0.5 + 0.5 * home_form) *
            (0.5 + 0.5 * home_control) *
            self.home_advantage
        )
        
        away_xg = (
            self.base_xg *
            (0.5 + 0.5 * away_attack) *
            (1.5 - 0.5 * home_defense) *
            (0.5 + 0.5 * away_form) *
            (0.5 + 0.5 * away_control)
        )
        
        return {
            'home_xg': round(home_xg, 2),
            'away_xg': round(away_xg, 2)
        }
    
    def poisson_probabilities(self, home_xg: float, away_xg: float) -> Dict:
        """Расчет вероятностей с помощью распределения Пуассона"""
        scores = {}
        
        # Топ-10 наиболее вероятных счетов
        for i in range(6):
            for j in range(6):
                prob = poisson.pmf(i, home_xg) * poisson.pmf(j, away_xg)
                score = f"{i}:{j}"
                scores[score] = prob
        
        total_prob = sum(scores.values())
        if total_prob > 0:
            for score in scores:
                scores[score] = scores[score] / total_prob * 100
        
        # Сортируем и берем топ-5
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_scores = [{'score': s[0], 'prob': round(s[1], 2)} for s in sorted_scores[:5]]
        
        # Рассчитываем вероятности исходов
        p1 = sum(prob for score, prob in scores.items() 
                if int(score.split(':')[0]) > int(score.split(':')[1]))
        pX = sum(prob for score, prob in scores.items() 
                if int(score.split(':')[0]) == int(score.split(':')[1]))
        p2 = sum(prob for score, prob in scores.items() 
                if int(score.split(':')[0]) < int(score.split(':')[1]))
        
        return {
            'P1': round(p1, 1),
            'X': round(pX, 1),
            'P2': round(p2, 1),
            'top_scores': top_scores
        }
    
    def calculate_confidence(self, home_xg: float, away_xg: float, 
                            home_data: Dict, away_data: Dict) -> int:
        """Расчет Confidence Index"""
        # Разница xG
        xg_diff = abs(home_xg - away_xg)
        xg_score = min(xg_diff / 1.5 * 100, 100)
        
        # Разница рейтингов
        home_rating = self.calculate_faj_rating(home_data) if home_data else 50
        away_rating = self.calculate_faj_rating(away_data) if away_data else 50
        rating_diff = abs(home_rating - away_rating)
        rating_score = min(rating_diff / 20 * 100, 100)
        
        # Форма
        home_form = float(home_data.get('form', 50)) / 100 if home_data else 0.5
        away_form = float(away_data.get('form', 50)) / 100 if away_data else 0.5
        form_score = abs(home_form - away_form) * 100
        
        # Неопределенность
        probs = self.poisson_probabilities(home_xg, away_xg)
        uncertainty = 100 - max(probs['P1'], probs['X'], probs['P2'])
        
        # Итоговый Confidence
        confidence = (
            xg_score * 0.30 +
            rating_score * 0.25 +
            form_score * 0.15 +
            uncertainty * 0.30
        )
        
        return round(min(max(confidence, 0), 100))
    
    def predict_match(self, home_team: str, away_team: str) -> Dict:
        """Главный метод прогнозирования"""
        try:
            # 1. Расчет xG
            xg = self.calculate_xg(home_team, away_team)
            
            # 2. Poisson вероятности
            probs = self.poisson_probabilities(xg['home_xg'], xg['away_xg'])
            
            # 3. Confidence
            home_data = self.get_team_passport(home_team)
            away_data = self.get_team_passport(away_team)
            confidence = self.calculate_confidence(
                xg['home_xg'], xg['away_xg'],
                home_data, away_data
            )
            
            # 4. Тотал > 2.5
            total_over25 = sum(
                prob for score, prob in {
                    f"{i}:{j}": poisson.pmf(i, xg['home_xg']) * poisson.pmf(j, xg['away_xg'])
                    for i in range(6) for j in range(6)
                }.items()
                if int(score.split(':')[0]) + int(score.split(':')[1]) > 2.5
            )
            total_over25 = round(total_over25 * 100, 1)
            
            # 5. Обе забьют (BTTS)
            btts_prob = 1 - math.exp(-xg['home_xg']) - math.exp(-xg['away_xg']) + math.exp(-(xg['home_xg'] + xg['away_xg']))
            btts_prob = round(btts_prob * 100, 1)
            
            # 6. Лучшая ставка
            max_prob = max(probs['P1'], probs['X'], probs['P2'])
            if max_prob == probs['P1']:
                best_bet = f"Победа {home_team}"
            elif max_prob == probs['X']:
                best_bet = "Ничья"
            else:
                best_bet = f"Победа {away_team}"
            
            result = {
                'version': '10.0',
                'home_team': home_team,
                'away_team': away_team,
                'xg': xg,
                'probability': probs,
                'top_scores': probs['top_scores'],
                'confidence': confidence,
                'total_over25': total_over25,
                'btts': btts_prob,
                'best_bet': best_bet,
                'explanation': self.generate_explanation(
                    home_team, away_team, xg, probs, confidence,
                    home_data, away_data
                )
            }
            
            return result
            
        except Exception as e:
            return {'error': str(e)}
    
    def generate_explanation(self, home: str, away: str, xg: Dict, 
                             probs: Dict, confidence: int,
                             home_data: Dict, away_data: Dict) -> str:
        """Генерация объяснения прогноза"""
        home_rating = self.calculate_faj_rating(home_data) if home_data else 50
        away_rating = self.calculate_faj_rating(away_data) if away_data else 50
        
        explanation = f"""
        Анализ матча {home} vs {away}:
        
        1. Сила команд:
           - {home}: FAJ Rating {home_rating}
           - {away}: FAJ Rating {away_rating}
           - Разница: {abs(home_rating - away_rating)} баллов
        
        2. Ожидаемые голы (xG):
           - {home}: {xg['home_xg']}
           - {away}: {xg['away_xg']}
        
        3. Вероятности:
           - Победа {home}: {probs['P1']}%
           - Ничья: {probs['X']}%
           - Победа {away}: {probs['P2']}%
        
        4. Уверенность модели: {confidence}%
        
        5. Ключевые факторы:
           - {'Домашнее преимущество' if xg['home_xg'] > xg['away_xg'] else 'Гостевой фактор'}
           - {'Более сильный состав' if home_rating > away_rating else 'Более слабый состав'}
        """
        
        return explanation.strip()
    
    def compare_with_actual(self, match: str, faj_pred: str, expert_pred: str, actual: str) -> Dict:
        """Сравнение прогноза с фактическим результатом"""
        return self.learning_db.compare_prediction(match, faj_pred, expert_pred, actual)


# Для тестирования
if __name__ == "__main__":
    engine = FAJPrediction()
    
    print("=" * 50)
    print("FAJ Prediction Engine v10.0 - Тест")
    print("=" * 50)
    
    # Тестовый прогноз
    result = engine.predict_match("Зенит", "Спартак")
    
    print(f"\n🏟 Зенит vs Спартак")
    print(f"📊 xG: {result['xg']['home_xg']} - {result['xg']['away_xg']}")
    print(f"📈 Вероятности: П1 {result['probability']['P1']}% | X {result['probability']['X']}% | П2 {result['probability']['P2']}%")
    print(f"🎯 Лучшая ставка: {result['best_bet']}")
    print(f"📊 Уверенность: {result['confidence']}%")
    print(f"⚽ Тотал > 2.5: {result['total_over25']}%")
    print(f"🤝 Обе забьют: {result['btts']}%")
    
    print("\n✅ Тест завершен успешно!")
