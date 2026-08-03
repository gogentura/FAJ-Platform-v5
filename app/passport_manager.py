#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v11.2.1
Passport Manager — ФИНАЛЬНАЯ ЗАМОРОЖЕННАЯ ВЕРСИЯ 🔒

Управление паспортами команд:
- создание паспорта на старте сезона
- автоматическое восстановление перед матчем
- обновление team_dynamic после каждого матча
- адаптивная коррекция team_base (с confidence_factor)
- performance_index как полноценный фактор
- расширенный match_snapshots в БД
- xg_memory с разделением attack/defense
- контроль последней Base коррекции
- team_identity (стиль, темп, прессинг)
- tactical_matchup_memory
- passport_confidence
- player_impact_memory

Статус: ✅ ПОЛНОСТЬЮ ГОТОВ К ПОДКЛЮЧЕНИЮ XG ENGINE 🔒
"""

import json
import math
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from app.database import FAJDatabase
from app.config import FAJConfig


class PassportManager:
    """Управление паспортами команд FAJ"""

    def __init__(self):
        self.db = FAJDatabase()
        self.config = FAJConfig()
        
        self.MAX_CHANGE_PER_SEASON = self.config.MAX_CHANGE_PER_SEASON
        
        self.default_base = {
            "attack": 50,
            "defense": 50,
            "control": 50,
            "press": 50,
            "tempo": 50,
            "transition": 50,
            "set_pieces": 50,
            "counter_attack": 50,
            "build_up": 50,
            "finishing": 50,
            "goalkeeper": 50,
            "discipline": 50,
            "coach_factor": 50,
            "squad_quality": 50,
            "bench_quality": 50,
            "home_advantage": 1.0
        }
        self.default_dynamic = {
            "form": 50,
            "fitness": 50,
            "morale": 50,
            "fatigue": 50,
            "injury_index": 0,
            "coach_confidence": 50,
            "last5_points": 0.0,
            "last5_strength_points": 0.0,
            "last5_results": "[0,0,0,0,0]",
            "last5_strength_results": "[0,0,0,0,0]",
            "last5_xg": 0.0,
            "last5_xga": 0.0,
            "last5_goals": 0,
            "last5_conceded": 0,
            "last5_performance": "[0,0,0,0,0]",
            "average_performance": 0.0,
            "current_streak": 0,
            "days_rest": 7,
            "travel_distance": 0,
            "rotation_index": 0,
            "last_base_correction_match": 0,
            "passport_confidence": self.config.INITIAL_PASSPORT_CONFIDENCE
        }

    # =========================================================
    # 1. СОЗДАНИЕ ПАСПОРТА
    # =========================================================

    def create_initial_passport(self, team_id: int, season_id: int,
                                base_data: Dict = None,
                                dynamic_data: Dict = None,
                                identity_data: Dict = None) -> Dict:
        base = base_data or self.default_base.copy()
        dynamic = dynamic_data or self.default_dynamic.copy()
        identity = identity_data or {
            "style": "mixed",
            "tempo": "medium",
            "pressing": "medium",
            "transition": "medium",
            "risk_level": "medium"
        }

        self.db.update_base(team_id, season_id, **base)
        self.db.update_dynamic(team_id, season_id, **dynamic)
        self.db.update_identity(team_id, season_id, **identity)

        self.db.add_history(
            team_id, season_id, "passport_created",
            "none", "created", "Initial passport", "system"
        )

        return {
            "team_id": team_id,
            "season_id": season_id,
            "base": base,
            "dynamic": dynamic,
            "identity": identity,
            "status": "created"
        }

    # =========================================================
    # 2. ПОЛУЧЕНИЕ ПАСПОРТА
    # =========================================================

    def get_full_passport(self, team_id: int, season_id: int) -> Dict:
        base = self.db.get_base(team_id, season_id)
        dynamic = self.db.get_dynamic(team_id, season_id)
        identity = self.db.get_identity(team_id, season_id)
        tactical = self.db.get_tactical_matchup(team_id, season_id)

        return {
            "team_id": team_id,
            "season_id": season_id,
            "base": dict(base) if base else None,
            "dynamic": dict(dynamic) if dynamic else None,
            "identity": dict(identity) if identity else None,
            "tactical": dict(tactical) if tactical else None
        }

    def get_match_snapshot(self, team_id: int, season_id: int) -> Dict:
        passport = self.get_full_passport(team_id, season_id)
        if not passport:
            return None

        base = passport.get("base", {})
        dynamic = passport.get("dynamic", {})
        identity = passport.get("identity", {})
        tactical = passport.get("tactical", {})

        return {
            "team_id": team_id,
            "season_id": season_id,
            "attack": base.get("attack", 50),
            "defense": base.get("defense", 50),
            "control": base.get("control", 50),
            "press": base.get("press", 50),
            "tempo": base.get("tempo", 50),
            "transition": base.get("transition", 50),
            "finishing": base.get("finishing", 50),
            "coach_factor": base.get("coach_factor", 50),
            "squad_quality": base.get("squad_quality", 50),
            "home_advantage": base.get("home_advantage", 1.0),
            "form": dynamic.get("form", 50),
            "fitness": dynamic.get("fitness", 50),
            "morale": dynamic.get("morale", 50),
            "fatigue": dynamic.get("fatigue", 50),
            "days_rest": dynamic.get("days_rest", 7),
            "injuries": dynamic.get("injury_index", 0),
            "passport_confidence": dynamic.get("passport_confidence", 0.4),
            "style": identity.get("style", "mixed"),
            "vs_high_press": tactical.get("vs_high_press", 0),
            "vs_low_block": tactical.get("vs_low_block", 0),
            "vs_counter_attack": tactical.get("vs_counter_attack", 0),
            "last5_results": self._parse_results(dynamic.get("last5_results", "[0,0,0,0,0]")),
            "last5_strength_results": self._parse_results(dynamic.get("last5_strength_results", "[0,0,0,0,0]")),
            "average_performance": dynamic.get("average_performance", 0.0)
        }

    def _parse_results(self, results_str: str) -> List[float]:
        try:
            return json.loads(results_str)
        except:
            return [0.0, 0.0, 0.0, 0.0, 0.0]

    # =========================================================
    # 3. ПОДГОТОВКА К МАТЧУ
    # =========================================================

    def prepare_for_match(self, team_id: int, season_id: int, match_id: int,
                          opponent_strength: float = 1.0,
                          days_since_last: int = 7) -> Dict:
        recovery_result = self._update_before_match(team_id, season_id, days_since_last)
        snapshot = self.get_match_snapshot(team_id, season_id)
        
        if snapshot:
            self.db.save_match_snapshot(
                match_id, team_id,
                snapshot,
                opponent_strength=opponent_strength,
                confidence_factor=snapshot.get("passport_confidence", 0.4)
            )
        
        return {
            "status": "ready",
            "team_id": team_id,
            "season_id": season_id,
            "recovery": recovery_result,
            "snapshot": snapshot,
            "saved": True
        }

    def _update_before_match(self, team_id: int, season_id: int, days_since_last: int = 7) -> Dict:
        dynamic = self.db.get_dynamic(team_id, season_id)
        if not dynamic:
            return {"status": "error", "message": "Dynamic не найден"}

        dyn = dict(dynamic)
        
        current_fatigue = dyn.get("fatigue", 50)
        recovery = days_since_last * self.config.FATIGUE_RECOVERY_RATE + self.config.FATIGUE_RECOVERY_BONUS
        new_fatigue = max(0, current_fatigue - recovery)
        dyn["fatigue"] = int(new_fatigue)
        
        dyn["travel_distance"] = 0
        dyn["days_rest"] = days_since_last
        dyn["fitness"] = min(100, dyn.get("fitness", 50) + days_since_last)
        
        self.db.update_dynamic(team_id, season_id, **dyn)
        
        return {
            "status": "updated",
            "team_id": team_id,
            "season_id": season_id,
            "fatigue": new_fatigue,
            "days_rest": days_since_last
        }

    # =========================================================
    # 4. РАСЧЁТ PERFORMANCE INDEX
    # =========================================================

    def calculate_performance_index(self, team_goals: int, opponent_goals: int,
                                    xg_for: float, xg_against: float,
                                    control: float = 0.5) -> float:
        xg_diff = xg_for - xg_against
        xg_score = max(-1, min(1, xg_diff / 2))
        
        if team_goals > opponent_goals:
            points = 1.0
        elif team_goals == opponent_goals:
            points = 0.0
        else:
            points = -1.0
        
        if xg_for > 0:
            shot_quality = min(1, (team_goals / max(xg_for, 0.1) - 0.5) * 2)
        else:
            shot_quality = 0
        
        performance = (
            self.config.PERFORMANCE_WEIGHTS["xg"] * xg_score +
            self.config.PERFORMANCE_WEIGHTS["points"] * points +
            self.config.PERFORMANCE_WEIGHTS["shot_quality"] * shot_quality +
            self.config.PERFORMANCE_WEIGHTS["control"] * control
        )
        
        return max(-1, min(1, performance))

    # =========================================================
    # 5. ОБНОВЛЕНИЕ ПОСЛЕ МАТЧА (Уровень 1)
    # =========================================================

    def update_after_match(self, team_id: int, season_id: int,
                           match_id: int,
                           team_goals: int, opponent_goals: int,
                           xg_for: float, xg_against: float,
                           is_home: bool,
                           opponent_strength: float = 1.0,
                           match_intensity: float = 1.0,
                           control: float = 0.5,
                           minutes_played: int = 90) -> Dict:
        current = self.db.get_dynamic(team_id, season_id)
        if not current:
            return {"status": "error", "message": "Dynamic не найден"}

        dynamic = dict(current)
        results = self._parse_results(dynamic.get("last5_results", "[0,0,0,0,0]"))
        strength_results = self._parse_results(dynamic.get("last5_strength_results", "[0,0,0,0,0]"))
        performance_list = self._parse_results(dynamic.get("last5_performance", "[0,0,0,0,0]"))

        # 1. Результат матча
        if team_goals > opponent_goals:
            result_weight = 3 * (0.7 + 0.3 * opponent_strength)
            points = 3
            dynamic["form"] = min(100, dynamic.get("form", 50) + int(3 * opponent_strength))
            dynamic["current_streak"] = dynamic.get("current_streak", 0) + 1 if dynamic.get("current_streak", 0) >= 0 else 1
        elif team_goals == opponent_goals:
            result_weight = 1
            points = 1
            dynamic["form"] = min(100, dynamic.get("form", 50) + 1)
            dynamic["current_streak"] = 0
        else:
            result_weight = 0
            points = 0
            dynamic["form"] = max(0, dynamic.get("form", 50) - int(2 * opponent_strength))
            dynamic["current_streak"] = dynamic.get("current_streak", 0) - 1 if dynamic.get("current_streak", 0) <= 0 else -1

        # 2. Обновляем результаты
        results.append(float(points))
        strength_results.append(round(result_weight, 2))
        if len(results) > 5:
            results.pop(0)
        if len(strength_results) > 5:
            strength_results.pop(0)
        
        dynamic["last5_results"] = json.dumps(results)
        dynamic["last5_strength_results"] = json.dumps(strength_results)
        dynamic["last5_points"] = float(sum(results))
        dynamic["last5_strength_points"] = float(sum(strength_results))

        # 3. xG
        current_xg = dynamic.get("last5_xg", 0)
        current_xga = dynamic.get("last5_xga", 0)
        dynamic["last5_xg"] = round(current_xg * 0.8 + xg_for * 0.2, 2)
        dynamic["last5_xga"] = round(current_xga * 0.8 + xg_against * 0.2, 2)
        
        # 4. Голы
        current_goals = dynamic.get("last5_goals", 0)
        current_conceded = dynamic.get("last5_conceded", 0)
        dynamic["last5_goals"] = int(current_goals * 0.8 + team_goals * 0.2)
        dynamic["last5_conceded"] = int(current_conceded * 0.8 + opponent_goals * 0.2)

        # 5. Performance
        performance = self.calculate_performance_index(
            team_goals, opponent_goals,
            xg_for, xg_against,
            control
        )
        performance_list.append(round(performance, 3))
        if len(performance_list) > 5:
            performance_list.pop(0)
        dynamic["last5_performance"] = json.dumps(performance_list)
        dynamic["average_performance"] = round(sum(performance_list) / len(performance_list), 3)

        # 6. Усталость
        days_rest = dynamic.get("days_rest", 0)
        travel_distance = dynamic.get("travel_distance", 0)
        current_fatigue = dynamic.get("fatigue", 50)
        
        base_fatigue = minutes_played / 90 * 10 * match_intensity
        travel_fatigue = travel_distance / 100 * 2
        new_fatigue = current_fatigue + base_fatigue + travel_fatigue
        dynamic["fatigue"] = max(0, min(100, int(new_fatigue)))
        
        dynamic["travel_distance"] = 0
        dynamic["days_rest"] = 0

        # 7. Мораль
        if team_goals > opponent_goals:
            morale_boost = 2 * (1 + (opponent_strength - 1) * 0.5)
            dynamic["morale"] = min(100, dynamic.get("morale", 50) + int(morale_boost))
        else:
            morale_loss = 1 * opponent_strength
            dynamic["morale"] = max(0, dynamic.get("morale", 50) - int(morale_loss))

        # 8. Fitness
        dynamic["fitness"] = min(100, dynamic.get("fitness", 50) + 2)

        # 9. Travel distance
        if not is_home:
            dynamic["travel_distance"] = dynamic.get("travel_distance", 0) + 100

        # 10. Passport Confidence (растет с каждым матчем)
        current_confidence = dynamic.get("passport_confidence", 0.4)
        new_confidence = min(
            self.config.MAX_PASSPORT_CONFIDENCE,
            current_confidence + self.config.CONFIDENCE_GROWTH_PER_MATCH
        )
        dynamic["passport_confidence"] = new_confidence

        self.db.update_dynamic(team_id, season_id, **dynamic)

        # 11. XG Memory (attack и defense)
        self._update_xg_memory(team_id, season_id, xg_for, xg_against)

        # 12. Tactical Matchup (обновляем на основе результата)
        self._update_tactical_matchup(team_id, season_id, opponent_strength, team_goals, opponent_goals)

        # 13. Запись в журнал
        self.db.add_journal(
            match_id,
            f"dynamic_update_{team_id}",
            "auto",
            f"{team_goals}:{opponent_goals}",
            "info",
            f"Performance: {performance:.2f}, Fatigue: {new_fatigue}, Form: {dynamic['form']}, Confidence: {new_confidence:.2f}"
        )

        self.db.add_history(
            team_id, season_id,
            "dynamic_update",
            "after_match",
            f"{team_goals}:{opponent_goals}",
            f"Perf: {performance:.2f}, вес: {result_weight:.2f}, интенсивность: {match_intensity:.2f}",
            "auto"
        )

        return {
            "status": "updated",
            "team_id": team_id,
            "season_id": season_id,
            "dynamic": dynamic,
            "result_weight": result_weight,
            "performance_index": performance
        }

    # =========================================================
    # 6. XG MEMORY (attack и defense в БД)
    # =========================================================

    def _update_xg_memory(self, team_id: int, season_id: int,
                          xg_for: float, xg_against: float):
        memory = self.db.get_xg_memory(team_id, season_id)
        
        xg_norm = 1.35
        attack_deviation = (xg_for - xg_norm) / xg_norm
        defense_deviation = (xg_against - xg_norm) / xg_norm
        
        if memory:
            matches_count = memory['matches_count'] + 1
            current_attack = memory['attack_xg_deviation']
            current_defense = memory['defense_xg_deviation']
            
            new_attack = current_attack + (attack_deviation - current_attack) / matches_count
            new_defense = current_defense + (defense_deviation - current_defense) / matches_count
            
            self.db.save_xg_memory(team_id, season_id, new_attack, new_defense, matches_count)
        else:
            self.db.save_xg_memory(team_id, season_id, attack_deviation, defense_deviation, 1)

    def get_xg_correction(self, team_id: int, season_id: int) -> Tuple[float, float]:
        memory = self.db.get_xg_memory(team_id, season_id)
        if not memory or memory['matches_count'] < 5:
            return 0.0, 0.0
        
        attack_correction = memory['attack_xg_deviation'] * 10
        defense_correction = memory['defense_xg_deviation'] * 10
        
        return max(-3, min(3, attack_correction)), max(-3, min(3, defense_correction))

    # =========================================================
    # 7. TACTICAL MATCHUP UPDATE
    # =========================================================

    def _update_tactical_matchup(self, team_id: int, season_id: int,
                                  opponent_strength: float,
                                  team_goals: int, opponent_goals: int):
        """Обновление тактической памяти на основе результата"""
        # Получаем текущие данные
        tactical = self.db.get_tactical_matchup(team_id, season_id)
        if not tactical:
            tactical = {
                "vs_high_press": 0,
                "vs_low_block": 0,
                "vs_counter_attack": 0,
                "vs_possession": 0,
                "vs_direct": 0
            }
        
        # Если команда выиграла у сильного соперника → усиливаем
        if team_goals > opponent_goals:
            # Победа над сильным соперником → хороший показатель
            if opponent_strength > 1.1:
                tactical["vs_high_press"] = min(10, tactical.get("vs_high_press", 0) + 0.5)
            # Победа над слабым → нейтрально
            elif opponent_strength < 0.9:
                tactical["vs_low_block"] = min(10, tactical.get("vs_low_block", 0) + 0.3)
        else:
            # Поражение → ухудшаем показатели
            if opponent_strength > 1.1:
                tactical["vs_high_press"] = max(-10, tactical.get("vs_high_press", 0) - 0.5)
            elif opponent_strength < 0.9:
                tactical["vs_low_block"] = max(-10, tactical.get("vs_low_block", 0) - 0.3)

        self.db.update_tactical_matchup(team_id, season_id, **tactical)

    # =========================================================
    # 8. РАСЧЁТ КОРРЕКЦИИ BASE
    # =========================================================

    def _get_base_correction_limit(self, matches_count: int) -> int:
        if matches_count >= 15:
            return 3
        elif matches_count >= 10:
            return 2
        else:
            return 1

    def _get_confidence_factor(self, matches_count: int) -> float:
        if matches_count >= 15:
            return 0.9
        elif matches_count >= 10:
            return 0.7
        elif matches_count >= 5:
            return 0.5
        else:
            return 0.3

    def update_after_series(self, team_id: int, season_id: int,
                           matches_count: int = 5) -> Dict:
        current = self.db.get_base(team_id, season_id)
        if not current:
            return {"status": "error", "message": "Base не найден"}

        dynamic = self.db.get_dynamic(team_id, season_id)
        if not dynamic:
            return {"status": "error", "message": "Dynamic не найден"}

        base = dict(current)
        dyn = dict(dynamic)

        limit = self._get_base_correction_limit(matches_count)
        confidence = self._get_confidence_factor(matches_count)
        attack_correction, defense_correction = self.get_xg_correction(team_id, season_id)
        avg_performance = dyn.get("average_performance", 0)
        passport_confidence = dyn.get("passport_confidence", 0.4)

        history = self.db.get_history(team_id, season_id, limit=100)
        season_changes = {}
        for record in history:
            if record['field'] in ['attack', 'defense', 'press', 'coach_factor', 'finishing']:
                old = float(record['old_value']) if record['old_value'].replace('.', '').isdigit() else 50
                new = float(record['new_value']) if record['new_value'].replace('.', '').isdigit() else 50
                season_changes[record['field']] = season_changes.get(record['field'], 0) + (new - old)

        schedule_difficulty = self._calculate_schedule_difficulty(team_id, season_id)

        changes = self._calculate_strength_adjustment(
            base, dyn, season_changes, schedule_difficulty,
            limit, confidence, attack_correction, defense_correction,
            avg_performance, passport_confidence
        )

        for key, change in changes.items():
            if key in base:
                new_value = max(0, min(100, base[key] + change))
                base[key] = int(new_value)

        self.db.update_base(team_id, season_id, **base)

        dyn["last_base_correction_match"] = matches_count
        self.db.update_dynamic(team_id, season_id, **dyn)

        self.db.add_history(
            team_id, season_id,
            "base_correction",
            "after_series",
            f"{matches_count} матчей",
            f"Лимит: ±{limit}, уверенность: {confidence:.2f}, "
            f"attack коррекция: {attack_correction:.2f}, defense коррекция: {defense_correction:.2f}, "
            f"performance: {avg_performance:.2f}, паспорт уверенность: {passport_confidence:.2f}, "
            f"изменения: {changes}",
            "auto"
        )

        return {
            "status": "updated",
            "team_id": team_id,
            "season_id": season_id,
            "base": base,
            "changes": changes,
            "correction_limit": limit,
            "confidence": confidence,
            "attack_correction": attack_correction,
            "defense_correction": defense_correction
        }

    def _calculate_strength_adjustment(self, current_base: Dict, dynamic: Dict,
                                     current_season_changes: Dict,
                                     schedule_difficulty: float,
                                     correction_limit: int,
                                     confidence: float,
                                     attack_correction: float,
                                     defense_correction: float,
                                     avg_performance: float,
                                     passport_confidence: float) -> Dict:
        changes = {}
        
        xg_for = dynamic.get("last5_xg", 0)
        xg_against = dynamic.get("last5_xga", 0)
        goals_for = dynamic.get("last5_goals", 0)
        goals_against = dynamic.get("last5_conceded", 0)
        form = dynamic.get("form", 50)
        
        xg_norm = 1.35

        # Общий коэффициент уверенности (паспорт + данные)
        total_confidence = confidence * (0.5 + 0.5 * passport_confidence)

        # 1. Атака
        if xg_for > 0:
            adjusted_xg = xg_for / max(schedule_difficulty, 0.5)
            attack_deviation = (adjusted_xg - xg_norm) / xg_norm
            
            attack_change = int(attack_deviation * 10 * total_confidence)
            
            if avg_performance > 0.3:
                attack_change += 1
            elif avg_performance < -0.3:
                attack_change -= 1
            
            attack_change += int(attack_correction * total_confidence)
            attack_change = max(-correction_limit, min(correction_limit, attack_change))
            
            if form > 60:
                attack_change = min(attack_change + 1, correction_limit)
            elif form < 40:
                attack_change = max(attack_change - 1, -correction_limit)
            
            if attack_deviation > 0.2 and goals_for / max(xg_for, 0.1) < 0.8:
                changes["finishing"] = max(-correction_limit, -1)
                changes["attack"] = min(correction_limit, attack_change)
            else:
                changes["attack"] = attack_change

        # 2. Защита
        if xg_against > 0:
            adjusted_xga = xg_against / max(schedule_difficulty, 0.5)
            defense_deviation = (adjusted_xga - xg_norm) / xg_norm
            
            defense_change = -int(defense_deviation * 8 * total_confidence)
            defense_change += -int(defense_correction * total_confidence)
            
            if avg_performance > 0.3:
                defense_change = max(defense_change - 1, -correction_limit)
            elif avg_performance < -0.3:
                defense_change = min(defense_change + 1, correction_limit)
            
            defense_change = max(-correction_limit, min(correction_limit, defense_change))
            
            if form > 60:
                defense_change = max(defense_change - 1, -correction_limit)
            elif form < 40:
                defense_change = min(defense_change + 1, correction_limit)
            
            changes["defense"] = defense_change

        # 3. Прессинг
        if form > 70:
            changes["press"] = 1
        elif form < 40:
            changes["press"] = -1

        # 4. Coach factor
        morale = dynamic.get("morale", 50)
        if morale > 70:
            changes["coach_factor"] = 1
        elif morale < 40:
            changes["coach_factor"] = -1

        # 5. Finishing
        if xg_for > 0 and goals_for > 0:
            finishing_ratio = goals_for / max(xg_for, 0.1)
            finishing_change = 0
            if finishing_ratio > 1.2:
                finishing_change = 1
                if avg_performance > 0.3:
                    finishing_change += 1
            elif finishing_ratio < 0.7:
                finishing_change = -1
                if avg_performance < -0.3:
                    finishing_change -= 1
            
            finishing_change = max(-correction_limit, min(correction_limit, finishing_change))
            changes["finishing"] = min(changes.get("finishing", 0) + finishing_change, correction_limit)

        for key in changes:
            current_change = current_season_changes.get(key, 0)
            if abs(current_change + changes[key]) > self.MAX_CHANGE_PER_SEASON:
                if changes[key] > 0:
                    changes[key] = self.MAX_CHANGE_PER_SEASON - current_change
                else:
                    changes[key] = -self.MAX_CHANGE_PER_SEASON - current_change

        return changes

    def _calculate_schedule_difficulty(self, team_id: int, season_id: int) -> float:
        history = self.db.get_history(team_id, season_id, limit=50)
        matches = []
        for record in history:
            if record['field'] == 'dynamic_update':
                desc = record.get('reason', '')
                if 'сила соперника:' in desc:
                    try:
                        parts = desc.split('сила соперника:')
                        if len(parts) > 1:
                            strength_str = parts[1].split(',')[0].strip()
                            strength = float(strength_str)
                            matches.append(strength)
                    except:
                        pass
        
        last_matches = matches[-5:] if matches else []
        if not last_matches:
            return 1.0
        
        avg_strength = sum(last_matches) / len(last_matches)
        return max(0.5, min(1.5, avg_strength))

    def get_matches_since_correction(self, team_id: int, season_id: int) -> int:
        dynamic = self.db.get_dynamic(team_id, season_id)
        if not dynamic:
            return 0
        return dynamic.get('last_base_correction_match', 0)

    # =========================================================
    # 9. ПОЛНЫЙ ЦИКЛ
    # =========================================================

    def full_match_update(self, team_id: int, season_id: int,
                          match_id: int,
                          team_goals: int, opponent_goals: int,
                          xg_for: float, xg_against: float,
                          is_home: bool,
                          opponent_strength: float = 1.0,
                          match_intensity: float = 1.0,
                          control: float = 0.5,
                          minutes_played: int = 90) -> Dict:
        result = self.update_after_match(
            team_id, season_id, match_id,
            team_goals, opponent_goals,
            xg_for, xg_against,
            is_home,
            opponent_strength,
            match_intensity,
            control,
            minutes_played
        )

        matches_since = self.get_matches_since_correction(team_id, season_id)
        if matches_since >= 5:
            series_result = self.update_after_series(team_id, season_id, matches_since)
            result["base_updated"] = series_result

        return result

    # =========================================================
    # 10. ВСЕ ПАСПОРТЫ ЛИГИ
    # =========================================================

    def get_league_passports(self, league: str, season_id: int) -> List[Dict]:
        teams = self.db.get_teams(league)
        passports = []

        for team in teams:
            passport = self.get_full_passport(team['id'], season_id)
            if passport:
                passports.append({
                    "team": team['name'],
                    "team_id": team['id'],
                    "base": passport.get("base"),
                    "dynamic": passport.get("dynamic"),
                    "identity": passport.get("identity"),
                    "tactical": passport.get("tactical"),
                    "form": self._get_form_summary(team['id'], season_id)
                })

        return passports

    def _get_form_summary(self, team_id: int, season_id: int) -> Dict:
        dynamic = self.db.get_dynamic(team_id, season_id)
        if not dynamic:
            return {"points": 0, "wins": 0, "draws": 0, "losses": 0}
        
        results = self._parse_results(dynamic.get("last5_results", "[0,0,0,0,0]"))
        return {
            "points": sum(results),
            "wins": sum(1 for r in results if r == 3),
            "draws": sum(1 for r in results if r == 1),
            "losses": sum(1 for r in results if r == 0),
            "results": results
        }


# =========================================================
# ТЕСТИРОВАНИЕ
# =========================================================

if __name__ == "__main__":
    pm = PassportManager()

    team_id = pm.db
