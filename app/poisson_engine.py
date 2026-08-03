#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Poisson Engine — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ 🔒

Переводит xG в вероятности исходов с помощью распределения Пуассона

Pipeline:
1. Получение xG (из XG Engine или напрямую)
2. Расчёт вероятности каждого счёта: P(home_goals) × P(away_goals)
3. Нормализация матрицы (сумма = 100%)
4. Суммирование вероятностей:
   - П1: home_goals > away_goals
   - X: home_goals == away_goals
   - П2: home_goals < away_goals
5. Топ-5 точных счетов
6. Тоталы (over25, over35)
7. Обе забьют (btts)
8. Handicap (home/away: -1, 0, +1)
9. Confidence (новая формула)
10. Сохранение в БД (predictions + prediction_scores + prediction_distributions + prediction_markets)

Статус: 🔒 ЗАМОРОЖЕН
"""

import math
from typing import Dict, List, Tuple, Optional
from app.database import FAJDatabase
from app.config import FAJConfig


class PoissonEngine:
    """Расчёт вероятностей через распределение Пуассона"""

    def __init__(self):
        self.db = FAJDatabase()
        self.config = FAJConfig()
        
        self.max_goals = self.config.MAX_GOALS
        self.simulation_count = self.config.SIMULATION_COUNT

    # =========================================================
    # 1. ФУНКЦИЯ ПУАССОНА
    # =========================================================

    def _poisson_probability(self, goals: int, xg: float) -> float:
        """
        Вероятность количества голов по распределению Пуассона
        
        P(k) = (e^(-λ) × λ^k) / k!
        """
        if xg <= 0:
            return 1.0 if goals == 0 else 0.0
        
        try:
            return (math.exp(-xg) * (xg ** goals)) / math.factorial(goals)
        except:
            return 0.0

    # =========================================================
    # 2. РАСЧЁТ HANDICAP (home + away)
    # =========================================================

    def _handicap_probability(self, distribution: Dict) -> Dict:
        """
        Handicap probabilities for both teams
        
        Returns:
            {
                "home_-1": float,   # Победа хозяев с разницей 2+
                "home_0": float,    # Победа хозяев с разницей 1+
                "home_plus1": float,# Хозяева не проигрывают (>= -1)
                "away_-1": float,   # Победа гостей с разницей 2+
                "away_0": float,    # Победа гостей с разницей 1+
                "away_plus1": float # Гости не проигрывают (>= -1)
            }
        """
        result = {
            "home_-1": 0.0,
            "home_0": 0.0,
            "home_plus1": 0.0,
            "away_-1": 0.0,
            "away_0": 0.0,
            "away_plus1": 0.0
        }
        
        for score, prob in distribution.items():
            h, a = map(int, score.split(':'))
            diff = h - a
            
            # Home handicap
            if diff >= 2:
                result["home_-1"] += prob
            if diff >= 1:
                result["home_0"] += prob
            if diff >= -1:
                result["home_plus1"] += prob
            
            # Away handicap
            if diff <= -2:
                result["away_-1"] += prob
            if diff <= -1:
                result["away_0"] += prob
            if diff <= 1:
                result["away_plus1"] += prob
        
        return {
            k: round(v * 100, 1)
            for k, v in result.items()
        }

    # =========================================================
    # 3. РАСЧЁТ ВЕРОЯТНОСТЕЙ
    # =========================================================

    def calculate_probabilities(self, xg_home: float, xg_away: float) -> Dict:
        """
        Полный расчёт вероятностей на основе xG
        
        Returns:
            Dict: {
                "home_win": float,
                "draw": float,
                "away_win": float,
                "top_scores": List[{"score": str, "probability": float}],
                "over25": float,
                "over35": float,
                "btts": float,
                "handicap": Dict[str, float],
                "distribution": Dict[str, float]
            }
        """
        # 1. Строим распределение всех счетов
        distribution = {}
        for home_goals in range(self.max_goals + 1):
            for away_goals in range(self.max_goals + 1):
                prob = (
                    self._poisson_probability(home_goals, xg_home) *
                    self._poisson_probability(away_goals, xg_away)
                )
                if prob > 0.0001:
                    distribution[f"{home_goals}:{away_goals}"] = prob

        # 2. Нормализация (сумма = 1.0)
        total_prob = sum(distribution.values())
        if total_prob > 0:
            for score in distribution:
                distribution[score] /= total_prob

        # 3. Суммируем исходы
        home_win = 0.0
        draw = 0.0
        away_win = 0.0
        
        for score, prob in distribution.items():
            h, a = map(int, score.split(':'))
            if h > a:
                home_win += prob
            elif h == a:
                draw += prob
            else:
                away_win += prob

        # 4. Нормализация исходов (на случай, если сумма ≠ 1)
        total = home_win + draw + away_win
        if total > 0:
            home_win /= total
            draw /= total
            away_win /= total

        # 5. Топ-5 точных счетов
        sorted_scores = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
        top_scores = [
            {"score": score, "probability": round(prob * 100, 2)}
            for score, prob in sorted_scores[:5]
        ]

        # 6. Тотал > 2.5
        over25 = sum(
            prob for score, prob in distribution.items()
            if sum(map(int, score.split(':'))) > 2.5
        )

        # 7. Тотал > 3.5
        over35 = sum(
            prob for score, prob in distribution.items()
            if sum(map(int, score.split(':'))) > 3.5
        )

        # 8. Обе забьют (BTTS)
        btts = sum(
            prob for score, prob in distribution.items()
            if all(g > 0 for g in map(int, score.split(':')))
        )

        # 9. Handicap (home + away)
        handicap = self._handicap_probability(distribution)

        return {
            "home_win": round(home_win * 100, 1),
            "draw": round(draw * 100, 1),
            "away_win": round(away_win * 100, 1),
            "top_scores": top_scores,
            "over25": round(over25 * 100, 1),
            "over35": round(over35 * 100, 1),
            "btts": round(btts * 100, 1),
            "handicap": handicap,
            "distribution": {k: round(v * 100, 2) for k, v in distribution.items()}
        }

    # =========================================================
    # 4. РАСЧЁТ CONFIDENCE
    # =========================================================

    def _calculate_confidence(self, home_win: float, draw: float, away_win: float,
                              xg_home: float, xg_away: float) -> int:
        """
        Расчёт уверенности прогноза
        
        Формула:
        confidence = 50 + abs(home_win - away_win) * 0.5 + abs(xg_home - xg_away) * 10
        """
        xg_diff = abs(xg_home - xg_away)
        prob_diff = abs(home_win - away_win)
        
        confidence = 50 + prob_diff * 0.5 + xg_diff * 10
        
        return int(min(95, max(0, confidence)))

    # =========================================================
    # 5. ПОЛНЫЙ ПРОГНОЗ МАТЧА
    # =========================================================

    def predict_match(self, match_id: int, xg_home: float, xg_away: float,
                      model_version: str = "v12.0",
                      algorithm: str = "poisson_v12") -> Dict:
        """
        Полный прогноз матча с сохранением в БД
        """
        # 1. Расчёт вероятностей
        probabilities = self.calculate_probabilities(xg_home, xg_away)
        
        # 2. Confidence
        confidence = self._calculate_confidence(
            probabilities["home_win"],
            probabilities["draw"],
            probabilities["away_win"],
            xg_home,
            xg_away
        )
        
        # 3. Сохранение в predictions
        prediction_id = self.db.save_prediction(
            match_id=match_id,
            model_version=model_version,
            algorithm=algorithm,
            home_win=probabilities["home_win"],
            draw=probabilities["draw"],
            away_win=probabilities["away_win"],
            over25=probabilities["over25"],
            over35=probabilities["over35"],
            btts=probabilities["btts"],
            confidence=confidence
        )
        
        # 4. Сохранение топ-счетов
        scores = [
            (s["score"], s["probability"])
            for s in probabilities["top_scores"]
        ]
        self.db.add_prediction_scores(prediction_id, scores)
        
        # 5. Сохранение полного распределения
        distribution = {
            tuple(map(int, k.split(':'))): v / 100
            for k, v in probabilities["distribution"].items()
        }
        self.db.add_prediction_distribution(prediction_id, distribution)
        
        # 6. Сохранение рынков (handicap home + away)
        for market, value in probabilities["handicap"].items():
            self.db.add_prediction_market(
                prediction_id=prediction_id,
                market=market,
                value=value
            )
        
        # 7. Сохранение остальных рынков
        markets = {
            "btts": probabilities["btts"],
            "over25": probabilities["over25"],
            "over35": probabilities["over35"]
        }
        for market, value in markets.items():
            self.db.add_prediction_market(
                prediction_id=prediction_id,
                market=market,
                value=value
            )
        
        return {
            "match_id": match_id,
            "xg_home": xg_home,
            "xg_away": xg_away,
            "probabilities": {
                "home_win": probabilities["home_win"],
                "draw": probabilities["draw"],
                "away_win": probabilities["away_win"]
            },
            "top_scores": probabilities["top_scores"],
            "over25": probabilities["over25"],
            "over35": probabilities["over35"],
            "btts": probabilities["btts"],
            "handicap": probabilities["handicap"],
            "confidence": confidence,
            "prediction_id": prediction_id,
            "model_version": model_version,
            "algorithm": algorithm
        }

    # =========================================================
    # 6. ПРОГНОЗ ПО ID МАТЧА (ИЗ БД)
    # =========================================================

    def predict_from_match_id(self, match_id: int) -> Dict:
        match_pred = self.db.get_match_prediction(match_id)
        if not match_pred:
            return {"error": f"Матч {match_id} не найден в match_predictions"}
        
        xg_home = match_pred.get("xg_home", 1.35)
        xg_away = match_pred.get("xg_away", 1.35)
        
        return self.predict_match(
            match_id,
            xg_home,
            xg_away,
            model_version=match_pred.get("model_version", "v12.0")
        )

    # =========================================================
    # 7. ПРОГНОЗ ПО НАЗВАНИЯМ КОМАНД
    # =========================================================

    def predict_by_names(self, home_name: str, away_name: str,
                         league: str = "RPL", season: int = 2026) -> Dict:
        from app.xg_engine import XGEngine
        xg_engine = XGEngine()
        
        xg_result = xg_engine.calculate_xg_by_names(
            home_name, away_name, league, season
        )
        
        if "error" in xg_result:
            return {"error": xg_result["error"]}
        
        return self.predict_match(
            xg_result["match_id"],
            xg_result["xg_home"],
            xg_result["xg_away"]
        )

    # =========================================================
    # 8. ПАКЕТНЫЙ РАСЧЁТ
    # =========================================================

    def predict_round(self, matches: list, season_id: int) -> list:
        from app.xg_engine import XGEngine
        xg_engine = XGEngine()
        
        xg_results = xg_engine.calculate_round_xg(matches, season_id)
        
        predictions = []
        for xg_result in xg_results:
            if "error" in xg_result:
                predictions.append({"error": xg_result["error"]})
                continue
            
            pred = self.predict_match(
                xg_result["match_id"],
                xg_result["xg_home"],
                xg_result["xg_away"]
            )
            predictions.append(pred)
        
        return predictions


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    engine = PoissonEngine()
    
    print("=" * 50)
    print("FAJ Poisson Engine v12.0 - Тест")
    print("=" * 50)
    
    print("\n📊 Тест: Расчёт (xG 1.85 - 1.15)")
    result = engine.calculate_probabilities(1.85, 1.15)
    
    print(f"  П1: {result['home_win']}%")
    print(f"  X: {result['draw']}%")
    print(f"  П2: {result['away_win']}%")
    print("\n  Handicap:")
    for k, v in result["handicap"].items():
        print(f"    {k}: {v}%")
    print("\n  Топ-3 счета:")
    for score in result["top_scores"][:3]:
        print(f"    {score['score']}: {score['probability']}%")
