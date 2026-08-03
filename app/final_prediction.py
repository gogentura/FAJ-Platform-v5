#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Final Prediction Engine — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ 🔒

Объединяет все слои FAJ в единый прогноз:
1. XG Engine → xG_home, xG_away
2. Poisson Engine → вероятности, счета, рынки
3. Expert Layer → корректировка с объяснением
4. Final Assembly → прогноз, уверенность, объяснение
5. FAJ Confidence Engine → пересчёт уверенности
6. Final Score Ranking → пересчёт топ-счёта

Pipeline:
match_id
    ↓
XG Engine (xg_home, xg_away)
    ↓
Poisson Engine (probabilities, scores, markets)
    ↓
Expert Layer (adjusted probabilities, reasons, final_adjustments)
    ↓
Final Assembly
    ├── FAJ Confidence Engine
    ├── Final Score Ranking (с final_adjustments)
    ├── Prediction ID Generator
    └── Status Management
    ↓
FAJ Report

Статус: 🔒 ЗАМОРОЖЕН
Версия модели: FAJ v12.0
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, List
from app.xg_engine import XGEngine
from app.poisson_engine import PoissonEngine
from app.expert_layer import ExpertLayer
from app.database import FAJDatabase
from app.config import FAJConfig


class FinalPredictionEngine:
    """Главный оркестратор FAJ — сборка финального прогноза"""

    # Версия модели
    MODEL_VERSION = "12.0"

    def __init__(self):
        self.xg_engine = XGEngine()
        self.poisson_engine = PoissonEngine()
        self.expert_layer = ExpertLayer()
        self.db = FAJDatabase()
        self.config = FAJConfig()

    # =========================================================
    # 1. ГЕНЕРАТОР FAJ ID
    # =========================================================

    def _generate_prediction_id(self, match_id: int) -> str:
        year = datetime.now().year
        hash_part = uuid.uuid4().hex[:6].upper()
        return f"FAJ-{year}-{match_id}-{hash_part}"

    # =========================================================
    # 2. FAJ CONFIDENCE ENGINE
    # =========================================================

    def _calculate_faj_confidence(self, final_probs: Dict,
                                  xg_home: float, xg_away: float,
                                  poisson_probs: Dict) -> int:
        max_prob = max(final_probs.values())
        probability_score = max_prob
        
        xg_diff = abs(xg_home - xg_away)
        xg_score = min(xg_diff * 20, 100)
        
        agreement = 100 - (
            abs(final_probs["home_win"] - poisson_probs["home_win"]) +
            abs(final_probs["draw"] - poisson_probs["draw"]) +
            abs(final_probs["away_win"] - poisson_probs["away_win"])
        )
        
        confidence = (probability_score + xg_score + agreement) / 3
        return round(min(confidence, 95))

    # =========================================================
    # 3. FINAL SCORE RANKING
    # =========================================================

    def _adjust_scores(self, scores: List[Dict],
                       home_adjustment: float,
                       away_adjustment: float) -> List[Dict]:
        adjusted = []
        for score in scores:
            h, a = map(int, score["score"].split(":"))
            prob = score["probability"]
            
            adjusted_prob = prob * (home_adjustment ** h) * (away_adjustment ** a)
            
            adjusted.append({
                "score": score["score"],
                "probability": round(adjusted_prob, 2)
            })
        
        return sorted(adjusted, key=lambda x: x["probability"], reverse=True)

    # =========================================================
    # 4. ГЛАВНЫЙ МЕТОД — ПОЛНЫЙ ПРОГНОЗ
    # =========================================================

    def predict(self, match_id: int,
                match_context: str = "league",
                competition: str = "RPL",
                expert_input: Dict = None,
                expert_reasons: List[str] = None) -> Dict:
        # 1. XG ENGINE
        xg_result = self.xg_engine.calculate_xg_from_match_id(match_id)
        if "error" in xg_result:
            return {"error": xg_result["error"]}
        
        xg_home = xg_result["xg_home"]
        xg_away = xg_result["xg_away"]
        
        # 2. POISSON ENGINE
        poisson_result = self.poisson_engine.predict_match(
            match_id, xg_home, xg_away
        )
        if "error" in poisson_result:
            return {"error": poisson_result["error"]}
        
        poisson_probs = {
            "home_win": poisson_result["probabilities"]["home_win"],
            "draw": poisson_result["probabilities"]["draw"],
            "away_win": poisson_result["probabilities"]["away_win"]
        }
        
        # 3. EXPERT LAYER
        match = self.db.get_matches()
        home_team_id = None
        away_team_id = None
        season_id = None
        
        for m in match:
            if m['id'] == match_id:
                home_team_id = m['home_team_id']
                away_team_id = m['away_team_id']
                break
        
        if home_team_id and away_team_id:
            for m in match:
                if m['id'] == match_id:
                    round_id = m['round_id']
                    rounds = self.db.get_rounds()
                    for r in rounds:
                        if r['id'] == round_id:
                            season_id = r['season_id']
                            break
                    break
        
        if home_team_id and away_team_id and season_id:
            expert_result = self.expert_layer.apply_expert_correction(
                home_team_id, away_team_id, season_id,
                poisson_probs,
                match_context, competition,
                expert_input, expert_reasons
            )
        else:
            expert_result = {
                "home_win": poisson_probs["home_win"],
                "draw": poisson_probs["draw"],
                "away_win": poisson_probs["away_win"],
                "reasons": ["Экспертный слой не применён"],
                "adjustments": {},
                "final_home_adjustment": 1.0,
                "final_away_adjustment": 1.0
            }
        
        # 4. FINAL ASSEMBLY
        final_home = expert_result["home_win"]
        final_draw = expert_result["draw"]
        final_away = expert_result["away_win"]
        
        final_probs = {
            "home_win": final_home,
            "draw": final_draw,
            "away_win": final_away
        }
        
        # 5. FAJ CONFIDENCE ENGINE
        confidence = self._calculate_faj_confidence(
            final_probs, xg_home, xg_away, poisson_probs
        )
        
        # 6. FINAL SCORE RANKING (с final_adjustments из Expert Layer)
        home_adj = expert_result.get("final_home_adjustment", 1.0)
        away_adj = expert_result.get("final_away_adjustment", 1.0)
        
        adjusted_scores = self._adjust_scores(
            poisson_result["top_scores"],
            home_adj,
            away_adj
        )
        top_score = adjusted_scores[0]["score"] if adjusted_scores else "1:1"
        
        # 7. PREDICTION ID
        prediction_id = self._generate_prediction_id(match_id)
        
        # 8. MARKETS
        markets = {
            "home_win": final_home,
            "draw": final_draw,
            "away_win": final_away,
            "over25": poisson_result["over25"],
            "over35": poisson_result["over35"],
            "btts": poisson_result["btts"],
            "handicap": poisson_result.get("handicap", {})
        }
        
        # 9. STATUS
        status = "created"
        
        # 10. EXPLANATION (с переданным prediction_id)
        explanation = self._generate_explanation(
            match_id, prediction_id, xg_home, xg_away,
            poisson_probs, expert_result,
            final_home, final_draw, final_away,
            top_score, confidence
        )
        
        # 11. Формируем результат
        result = {
            "match_id": match_id,
            "prediction_id": prediction_id,
            "model_version": f"FAJ v{self.MODEL_VERSION}",
            "status": status,
            "xg": {
                "home": xg_home,
                "away": xg_away
            },
            "poisson": {
                "home_win": poisson_probs["home_win"],
                "draw": poisson_probs["draw"],
                "away_win": poisson_probs["away_win"]
            },
            "expert": {
                "home_win": expert_result["home_win"],
                "draw": expert_result["draw"],
                "away_win": expert_result["away_win"],
                "reasons": expert_result.get("reasons", []),
                "adjustments": expert_result.get("adjustments", {}),
                "final_home_adjustment": expert_result.get("final_home_adjustment", 1.0),
                "final_away_adjustment": expert_result.get("final_away_adjustment", 1.0)
            },
            "final": final_probs,
            "top_score": top_score,
            "adjusted_scores": adjusted_scores[:5],
            "markets": markets,
            "confidence": confidence,
            "explanation": explanation
        }
        
        # 12. Сохраняем в журнал
        self.db.add_journal(
            match_id,
            f"FAJ_{prediction_id}",
            "final",
            f"{final_home}:{final_draw}:{final_away}",
            "created",
            f"Confidence: {confidence}%, Top score: {top_score}, Model: FAJ v{self.MODEL_VERSION}"
        )
        
        return result

    # =========================================================
    # 5. ГЕНЕРАЦИЯ ОБЪЯСНЕНИЯ
    # =========================================================

    def _generate_explanation(self, match_id: int, prediction_id: str,
                              xg_home: float, xg_away: float,
                              poisson_probs: Dict,
                              expert_result: Dict,
                              final_home: float, final_draw: float, final_away: float,
                              top_score: str, confidence: int) -> str:
        # Определяем фаворита
        if final_home > final_draw and final_home > final_away:
            favorite = "хозяева"
        elif final_away > final_draw and final_away > final_home:
            favorite = "гости"
        else:
            favorite = "ничья"
        
        max_prob = max(final_home, final_draw, final_away)
        if max_prob >= 55:
            confidence_text = "высокая"
        elif max_prob >= 40:
            confidence_text = "средняя"
        else:
            confidence_text = "низкая"
        
        lines = [
            f"📊 Прогноз матча #{match_id}",
            f"🆔 ID: {prediction_id}",
            f"📌 Версия: FAJ v{self.MODEL_VERSION}",
            "",
            f"⚽ Ожидаемые голы (xG): {xg_home:.2f} : {xg_away:.2f}",
            "",
            f"📈 Вероятности FAJ:",
            f"  • Победа хозяев: {final_home}%",
            f"  • Ничья: {final_draw}%",
            f"  • Победа гостей: {final_away}%",
            "",
            f"🎯 Наиболее вероятный счёт: {top_score}",
            "",
            f"📊 Уверенность: {confidence_text} ({max_prob:.0f}%, FAJ CI: {confidence}%)",
            "",
            f"🔑 Ключевые факторы:"
        ]
        
        if expert_result.get("reasons"):
            for reason in expert_result["reasons"][:3]:
                lines.append(f"  • {reason}")
        
        if xg_home > xg_away:
            lines.append(f"  • Домашняя команда создаёт больше моментов")
        if abs(xg_home - xg_away) > 0.5:
            lines.append(f"  • Существенная разница в xG")
        
        return "\n".join(lines)

    # =========================================================
    # 6. ПРОГНОЗ ПО НАЗВАНИЯМ (ТЕСТ)
    # =========================================================

    def predict_by_names(self, home_name: str, away_name: str,
                         league: str = "RPL", season: int = 2026,
                         match_context: str = "league",
                         competition: str = "RPL") -> Dict:
        from app.xg_engine import XGEngine
        xg_engine = XGEngine()
        
        home_team_id = self.db.get_team_id(home_name, league)
        away_team_id = self.db.get_team_id(away_name, league)
        season_id = self.db.get_season_id(league, str(season))
        
        if not home_team_id or not away_team_id or not season_id:
            return {"error": "Команда или сезон не найдены"}
        
        match_id = self.db.add_match(
            round_id=1,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            competition=league
        )
        
        xg_result = xg_engine.calculate_xg(
            home_team_id, away_team_id,
            season_id, match_id
        )
        
        if "error" in xg_result:
            return {"error": xg_result["error"]}
        
        return self.predict(match_id, match_context, competition)


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    engine = FinalPredictionEngine()
    
    print("=" * 50)
    print("FAJ Final Prediction Engine v12.0 - Тест")
    print("=" * 50)
    
    result = engine.predict_by_names("Зенит", "Спартак", match_context="derby")
    
    if "error" in result:
        print(f"❌ Ошибка: {result['error']}")
    else:
        print(f"\n🏟 Зенит vs Спартак")
        print(f"🆔 {result['prediction_id']}")
        print(f"📌 Версия: {result['model_version']}")
        print(f"\n📊 XG: {result['xg']['home']} - {result['xg']['away']}")
        print(f"\n📈 Финальный прогноз:")
        print(f"  П1: {result['final']['home_win']}%")
        print(f"  X: {result['final']['draw']}%")
        print(f"  П2: {result['final']['away_win']}%")
        print(f"  Счёт: {result['top_score']}")
        print(f"  Уверенность: {result['confidence']}%")
        print(f"\n📋 Объяснение:")
        print(result['explanation'])
