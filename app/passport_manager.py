#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Passport Manager
"""

from typing import Dict, Optional
from app.database import FAJDatabase


class PassportManager:
    
    def __init__(self):
        self.db = FAJDatabase()
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
    
    def get_passport(self, team_name: str) -> Optional[Dict]:
        return self.db.get_passport(team_name)
    
    def get_all_passports(self) -> Dict:
        return self.db.get_all_passports()
    
    def update_after_match(self, home_team: str, away_team: str,
                           home_goals: int, away_goals: int,
                           xg_home: float, xg_away: float) -> Dict:
        home_passport = self.get_passport(home_team)
        away_passport = self.get_passport(away_team)
        
        if not home_passport or not away_passport:
            return {"error": "Паспорт одной из команд не найден"}
        
        home_passport["form"] = self._update_form(home_passport.get("form", 50), home_goals, away_goals)
        away_passport["form"] = self._update_form(away_passport.get("form", 50), away_goals, home_goals)
        
        home_passport["attack"] = self._update_attack(home_passport.get("attack", 50), home_goals, xg_home)
        away_passport["attack"] = self._update_attack(away_passport.get("attack", 50), away_goals, xg_away)
        
        home_passport["defense"] = self._update_defense(home_passport.get("defense", 50), away_goals, xg_away)
        away_passport["defense"] = self._update_defense(away_passport.get("defense", 50), home_goals, xg_home)
        
        home_passport["faj_rating"] = self._calculate_rating(home_passport)
        away_passport["faj_rating"] = self._calculate_rating(away_passport)
        
        self.db.update_passport(home_team, home_passport)
        self.db.update_passport(away_team, away_passport)
        
        return {
            "home": home_passport,
            "away": away_passport
        }
    
    def _update_form(self, current_form: float, goals_for: int, goals_against: int) -> int:
        if goals_for > goals_against:
            delta = 3
        elif goals_for == goals_against:
            delta = 1
        else:
            delta = -1
        new_form = current_form + delta * 2
        return max(30, min(100, int(new_form)))
    
    def _update_attack(self, current_attack: float, goals: int, xg: float) -> int:
        if goals > xg:
            delta = 2
        elif goals >= xg - 0.5:
            delta = 1
        else:
            delta = -1
        new_attack = current_attack + delta * 1.5
        return max(30, min(100, int(new_attack)))
    
    def _update_defense(self, current_defense: float, goals_conceded: int, xg_conceded: float) -> int:
        if goals_conceded < xg_conceded:
            delta = 2
        elif goals_conceded <= xg_conceded + 0.5:
            delta = 1
        else:
            delta = -1
        new_defense = current_defense + delta * 1.5
        return max(30, min(100, int(new_defense)))
    
    def _calculate_rating(self, passport: Dict) -> float:
        rating = 0
        for key, weight in self.weights.items():
            value = passport.get(key, 50)
            try:
                rating += float(value) * weight
            except:
                rating += 50 * weight
        return round(rating, 2)
