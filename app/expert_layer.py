#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.0
Expert Layer — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ 🔒

Корректирует математический прогноз на основе контекстных факторов:
- Coach Factor (тренерский опыт, влияние) — 15%
- Transfer Factor (трансферы) — 10%
- Injury Factor (травмы ключевых игроков) — 20%
- Motivation Factor (мотивация, дерби, еврокубки) — 20%
- Tournament DNA (турнирный контекст) — 15%
- Squad Stability (стабильность состава) — 10%
- Human Expert Input (ручная корректировка) — 10%

Принцип:
- Математика даёт базу (Poisson)
- Экспертный слой корректирует через FAJ Adjustment Score
- Коррекция ограничена ±15% на фактор
- Итоговый сдвиг ограничен ±8% (общий)
- Коррекция объяснима и журналируется

Статус: 🔒 ЗАМОРОЖЕН
"""

from typing import Dict, Optional, Tuple, List
from app.database import FAJDatabase
from app.config import FAJConfig
from app.passport_manager import PassportManager


class ExpertLayer:
    """Экспертный слой FAJ — корректировка прогнозов"""

    def __init__(self):
        self.db = FAJDatabase()
        self.config = FAJConfig()
        self.passport_manager = PassportManager()
        
        # Максимальное влияние экспертного слоя на фактор (±15%)
        self.MAX_EXPERT_ADJUSTMENT = 0.15
        
        # Максимальный итоговый сдвиг прогноза (±8%)
        self.MAX_FINAL_SHIFT = 0.08
        
        # Веса факторов
        self.COACH_WEIGHT = 0.15
        self.TRANSFER_WEIGHT = 0.10
        self.INJURY_WEIGHT = 0.20
        self.MOTIVATION_WEIGHT = 0.20
        self.TOURNAMENT_WEIGHT = 0.15
        self.STABILITY_WEIGHT = 0.10
        self.EXPERT_WEIGHT = 0.10

    # =========================================================
    # 1. ОГРАНИЧИТЕЛИ
    # =========================================================

    def _limit_adjustment(self, value: float) -> float:
        """
        Ограничивает экспертную корректировку ±15% на фактор
        """
        return max(1.0 - self.MAX_EXPERT_ADJUSTMENT, 
                   min(1.0 + self.MAX_EXPERT_ADJUSTMENT, value))

    def _limit_final_shift(self, old_value: float, new_value: float) -> float:
        """
        Ограничивает итоговый сдвиг прогноза ±8%
        """
        shift = new_value - old_value
        if abs(shift) > self.MAX_FINAL_SHIFT:
            if shift > 0:
                return old_value + self.MAX_FINAL_SHIFT
            else:
                return old_value - self.MAX_FINAL_SHIFT
        return new_value

    # =========================================================
    # 2. ФАКТОРЫ
    # =========================================================

    def _coach_factor(self, team_id: int, season_id: int) -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("base"):
            return 1.0
        
        coach = passport["base"].get("coach_factor", 50)
        factor = 0.9 + (coach / 100) * 0.2
        return max(0.9, min(1.1, factor))

    def _transfer_factor(self, team_id: int, season_id: int) -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("base"):
            return 1.0
        
        squad = passport["base"].get("squad_quality", 50)
        factor = 0.95 + (squad / 100) * 0.1
        return max(0.95, min(1.05, factor))

    def _injury_factor(self, team_id: int, season_id: int) -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("dynamic"):
            return 1.0
        
        injury = passport["dynamic"].get("injury_index", 0)
        factor = 1.0 - (injury / 100) * 0.15
        return max(0.85, min(1.0, factor))

    def _motivation_factor(self, team_id: int, season_id: int, match_context: str = "league") -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("dynamic"):
            motivation_index = 50
        else:
            motivation_index = passport["dynamic"].get("motivation_index", 50)
        
        context_map = {
            "friendly": 0.85,
            "league": 1.0,
            "cup": 1.05,
            "derby": 1.10,
            "europe": 1.08
        }
        base = context_map.get(match_context, 1.0)
        
        individual = 0.9 + (motivation_index / 100) * 0.2
        
        return base * individual

    def _tournament_factor(self, team_id: int, season_id: int, competition: str) -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("base"):
            international_exp = 50
        else:
            international_exp = passport["base"].get("international_experience", 50)
        
        tournament_map = {
            "RPL": 1.0,
            "EPL": 1.05,
            "LALIGA": 1.03,
            "UCL": 1.08,
            "CUP": 1.02,
            "FRIENDLY": 0.90
        }
        base = tournament_map.get(competition, 1.0)
        
        exp_factor = 0.9 + (international_exp / 100) * 0.2
        
        return base * exp_factor

    def _stability_factor(self, team_id: int, season_id: int) -> float:
        passport = self.passport_manager.get_full_passport(team_id, season_id)
        if not passport or not passport.get("base"):
            return 1.0
        
        bench = passport["base"].get("bench_quality", 50)
        rotation = passport["dynamic"].get("rotation_index", 0)
        
        bench_factor = 0.95 + (bench / 100) * 0.1
        rotation_factor = 1.0 - (rotation / 100) * 0.05
        
        factor = (bench_factor + rotation_factor) / 2
        return max(0.95, min(1.05, factor))

    def _human_expert_factor(self, expert_input: Dict) -> float:
        if not expert_input:
            return 1.0
        
        home_adj = expert_input.get("home_adj", 0) * self.EXPERT_WEIGHT
        return 1.0 + home_adj

    # =========================================================
    # 3. КОРРЕКТИРОВКА ПРОГНОЗА
    # =========================================================

    def apply_expert_correction(self, home_team_id: int, away_team_id: int,
                                season_id: int,
                                poisson_probs: Dict,
                                match_context: str = "league",
                                competition: str = "RPL",
                                expert_input: Dict = None,
                                expert_reasons: List[str] = None) -> Dict:
        # 1. Рассчитываем факторы
        coach_home = self._coach_factor(home_team_id, season_id)
        coach_away = self._coach_factor(away_team_id, season_id)
        
        transfer_home = self._transfer_factor(home_team_id, season_id)
        transfer_away = self._transfer_factor(away_team_id, season_id)
        
        injury_home = self._injury_factor(home_team_id, season_id)
        injury_away = self._injury_factor(away_team_id, season_id)
        
        motivation_home = self._motivation_factor(home_team_id, season_id, match_context)
        motivation_away = self._motivation_factor(away_team_id, season_id, match_context)
        
        tournament_home = self._tournament_factor(home_team_id, season_id, competition)
        tournament_away = self._tournament_factor(away_team_id, season_id, competition)
        
        stability_home = self._stability_factor(home_team_id, season_id)
        stability_away = self._stability_factor(away_team_id, season_id)
        
        # 2. Общая корректировка
        raw_home_adjustment = (
            (coach_home ** self.COACH_WEIGHT) *
            (transfer_home ** self.TRANSFER_WEIGHT) *
            (injury_home ** self.INJURY_WEIGHT) *
            (motivation_home ** self.MOTIVATION_WEIGHT) *
            (tournament_home ** self.TOURNAMENT_WEIGHT) *
            (stability_home ** self.STABILITY_WEIGHT)
        )
        home_adjustment = self._limit_adjustment(raw_home_adjustment)
        
        raw_away_adjustment = (
            (coach_away ** self.COACH_WEIGHT) *
            (transfer_away ** self.TRANSFER_WEIGHT) *
            (injury_away ** self.INJURY_WEIGHT) *
            (motivation_away ** self.MOTIVATION_WEIGHT) *
            (tournament_away ** self.TOURNAMENT_WEIGHT) *
            (stability_away ** self.STABILITY_WEIGHT)
        )
        away_adjustment = self._limit_adjustment(raw_away_adjustment)
        
        # 3. Экспертный ввод (с весом)
        if expert_input:
            home_expert_adj = expert_input.get("home_adj", 0) * self.EXPERT_WEIGHT
            away_expert_adj = expert_input.get("away_adj", 0) * self.EXPERT_WEIGHT
            
            home_adjustment = self._limit_adjustment(
                home_adjustment * (1.0 + home_expert_adj)
            )
            away_adjustment = self._limit_adjustment(
                away_adjustment * (1.0 + away_expert_adj)
            )
        
        # 4. Применяем корректировку
        home_score = poisson_probs["home_win"] * home_adjustment
        draw_score = poisson_probs["draw"]
        away_score = poisson_probs["away_win"] * away_adjustment
        
        # 5. Нормализация
        total = home_score + draw_score + away_score
        if total > 0:
            raw_home_win = home_score / total * 100
            raw_draw = draw_score / total * 100
            raw_away_win = away_score / total * 100
        else:
            raw_home_win = poisson_probs["home_win"]
            raw_draw = poisson_probs["draw"]
            raw_away_win = poisson_probs["away_win"]
        
        # 6. Применяем ограничение итогового сдвига (±8%)
        home_win = self._limit_final_shift(poisson_probs["home_win"], raw_home_win)
        draw = self._limit_final_shift(poisson_probs["draw"], raw_draw)
        away_win = self._limit_final_shift(poisson_probs["away_win"], raw_away_win)
        
        # 7. Финальная нормализация (после ограничения)
        total_final = home_win + draw + away_win
        if total_final > 0:
            home_win = round(home_win / total_final * 100, 1)
            draw = round(draw / total_final * 100, 1)
            away_win = round(away_win / total_final * 100, 1)
        else:
            home_win = poisson_probs["home_win"]
            draw = poisson_probs["draw"]
            away_win = poisson_probs["away_win"]
        
        # 8. Причины
        reasons = expert_reasons or []
        if home_adjustment > 1.02:
            reasons.append(f"Домашнее преимущество: +{round((home_adjustment-1)*100,1)}%")
        if away_adjustment > 1.02:
            reasons.append(f"Гостевое преимущество: +{round((away_adjustment-1)*100,1)}%")
        if injury_home < 0.95:
            reasons.append(f"Травмы хозяев: -{round((1-injury_home)*100,1)}%")
        if injury_away < 0.95:
            reasons.append(f"Травмы гостей: -{round((1-injury_away)*100,1)}%")
        if motivation_home > 1.05:
            reasons.append(f"Высокая мотивация хозяев")
        if motivation_away > 1.05:
            reasons.append(f"Высокая мотивация гостей")
        
        return {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "adjustments": {
                "coach": round((coach_home - 1) * 100, 1),
                "transfer": round((transfer_home - 1) * 100, 1),
                "injury": round((injury_home - 1) * 100, 1),
                "motivation": round((motivation_home - 1) * 100, 1),
                "tournament": round((tournament_home - 1) * 100, 1),
                "stability": round((stability_home - 1) * 100, 1),
                "expert": round(home_adjustment - 1 - (coach_home - 1) - (transfer_home - 1) - (injury_home - 1) - (motivation_home - 1) - (tournament_home - 1) - (stability_home - 1), 1) if expert_input else 0
            },
            "reasons": reasons[:5],
            "final_shift": {
                "home": round(home_win - poisson_probs["home_win"], 1),
                "draw": round(draw - poisson_probs["draw"], 1),
                "away": round(away_win - poisson_probs["away_win"], 1)
            }
        }

    # =========================================================
    # 4. ПОЛНЫЙ ПРОГНОЗ С ЭКСПЕРТНЫМ СЛОЕМ
    # =========================================================

    def predict_with_expert(self, match_id: int,
                           poisson_probs: Dict,
                           home_team_id: int = None,
                           away_team_id: int = None,
                           season_id: int = None,
                           match_context: str = "league",
                           competition: str = "RPL",
                           expert_input: Dict = None,
                           expert_reasons: List[str] = None) -> Dict:
        if not home_team_id or not away_team_id or not season_id:
            match = self.db.get_matches()
            for m in match:
                if m['id'] == match_id:
                    home_team_id = m['home_team_id']
                    away_team_id = m['away_team_id']
                    break
        
        if not home_team_id or not away_team_id:
            return {"error": "Не удалось определить команды матча"}
        
        if not season_id:
            match = self.db.get_matches()
            for m in match:
                if m['id'] == match_id:
                    round_id = m['round_id']
                    rounds = self.db.get_rounds()
                    for r in rounds:
                        if r['id'] == round_id:
                            season_id = r['season_id']
                            break
                    break
        
        result = self.apply_expert_correction(
            home_team_id, away_team_id,
            season_id,
            poisson_probs,
            match_context,
            competition,
            expert_input,
            expert_reasons
        )
        
        self.db.add_journal(
            match_id,
            f"FAJ_v12_poisson_{poisson_probs['home_win']}:{poisson_probs['draw']}:{poisson_probs['away_win']}",
            f"expert_{result['home_win']}:{result['draw']}:{result['away_win']}",
            "pending",
            "expert_layer",
            f"Reasons: {', '.join(result['reasons'])} | Adjustments: {result['adjustments']} | Final shift: {result['final_shift']}"
        )
        
        return result


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    expert = ExpertLayer()
    
    print("=" * 50)
    print("FAJ Expert Layer v12.0 - Тест")
    print("=" * 50)
    
    poisson = {
        "home_win": 52.0,
        "draw": 27.0,
        "away_win": 21.0
    }
    
    print("\n📊 Базовый прогноз (Poisson):")
    print(f"  П1: {poisson['home_win']}%")
    print(f"  X: {poisson['draw']}%")
    print(f"  П2: {poisson['away_win']}%")
    
    result = expert.apply_expert_correction(
        home_team_id=1,
        away_team_id=2,
        season_id=1,
        poisson_probs=poisson,
        match_context="derby",
        competition="RPL",
        expert_reasons=["Дерби", "Травма ключевого игрока хозяев"]
    )
    
    print("\n🧠 После экспертного слоя:")
    print(f"  П1: {result['home_win']}%")
    print(f"  X: {result['draw']}%")
    print(f"  П2: {result['away_win']}%")
    print(f"\n  Итоговый сдвиг:")
    for k, v in result['final_shift'].items():
        print(f"    {k}: {v}%")
    print(f"\n  Причины:")
    for r in result['reasons']:
        print(f"    - {r}")
    print(f"\n  Коррекции:")
    for k, v in result['adjustments'].items():
        print(f"    {k}: {v}%")
