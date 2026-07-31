#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Learning Database v10.0
Самообучающаяся система для хранения и анализа прогнозов
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd


class LearningDB:
    """Самообучающаяся база данных FAJ"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.ensure_directories()
        self.load_all()
        
    def ensure_directories(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
    
    def load_all(self) -> None:
        self.passports = self.load_json("passports_2026.json", {})
        self.tour1_results = self.load_json("tour1_results.json", {})
        self.tour2_predictions = self.load_json("tour2_predictions.json", {})
        self.tour2_results = self.load_json("tour2_results.json", {})
        self.memory = self.load_json("learning_memory.json", [])
        self.weights_history = self.load_json("weights_history.json", [])
        self.comparison_log = self.load_json("comparison_log.json", [])
        self.config = self.load_json("config.json", self.get_default_config())
    
    def get_default_config(self) -> Dict:
        return {
            "version": "10.0",
            "base_xg": 1.35,
            "home_advantage": 1.12,
            "weights": {
                "attack": 0.19, "defense": 0.19, "control": 0.14,
                "efficiency": 0.12, "mentality": 0.11, "tempo": 0.07,
                "press": 0.05, "transition": 0.04, "flexibility": 0.05,
                "coach": 0.04
            }
        }
    
    def load_json(self, filename: str, default: Any) -> Any:
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return default
        return default
    
    def save_json(self, filename: str, data: Any) -> None:
        path = os.path.join(self.data_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_team_passport(self, team_name: str) -> Dict:
        return self.passports.get(team_name, {})
    
    def get_all_teams(self) -> List[str]:
        return list(self.passports.keys())
    
    def update_team_passport(self, team_name: str, data: Dict) -> None:
        if team_name in self.passports:
            self.passports[team_name].update(data)
        else:
            self.passports[team_name] = data
        self.save_json("passports_2026.json", self.passports)
    
    def get_tour_predictions(self, tour: str = "tour2") -> Dict:
        if tour == "tour1":
            return self.tour1_results
        elif tour == "tour2":
            return self.tour2_predictions
        return {}
    
    def update_tour_results(self, tour: str, results: Dict) -> None:
        if tour == "tour2":
            self.tour2_results = results
            self.save_json("tour2_results.json", self.tour2_results)
    
    def add_learning_record(self, record: Dict) -> None:
        record['timestamp'] = datetime.now().isoformat()
        self.memory.append(record)
        self.save_json("learning_memory.json", self.memory)
    
    def get_learning_stats(self) -> Dict:
        return {
            'total_records': len(self.memory),
            'teams_count': len(self.passports),
            'weights_updates': len(self.weights_history),
            'comparisons': len(self.comparison_log),
            'last_update': self.memory[-1]['timestamp'] if self.memory else None
        }
    
    def compare_prediction(self, match: str, faj_pred: str, expert_pred: str, actual: str) -> Dict:
        def get_outcome(score):
            if not score or score == "-":
                return None
            try:
                h, a = map(int, score.split(':'))
                if h > a:
                    return "П1"
                elif h == a:
                    return "X"
                else:
                    return "П2"
            except:
                return None
        
        faj_outcome = get_outcome(faj_pred)
        expert_outcome = get_outcome(expert_pred)
        actual_outcome = get_outcome(actual)
        
        faj_correct = faj_outcome == actual_outcome
        expert_correct = expert_outcome == actual_outcome
        faj_score_correct = faj_pred == actual
        expert_score_correct = expert_pred == actual
        
        record = {
            'match': match,
            'faj_pred': faj_pred,
            'expert_pred': expert_pred,
            'actual': actual,
            'faj_outcome': faj_outcome,
            'expert_outcome': expert_outcome,
            'actual_outcome': actual_outcome,
            'faj_correct': faj_correct,
            'expert_correct': expert_correct,
            'faj_score_correct': faj_score_correct,
            'expert_score_correct': expert_score_correct,
            'timestamp': datetime.now().isoformat()
        }
        
        self.comparison_log.append(record)
        self.save_json("comparison_log.json", self.comparison_log)
        self.add_learning_record(record)
        return record
    
    def get_comparison_summary(self) -> pd.DataFrame:
        if not self.comparison_log:
            return pd.DataFrame()
        df = pd.DataFrame(self.comparison_log)
        return df[['match', 'faj_pred', 'expert_pred', 'actual', 
                   'faj_correct', 'expert_correct', 'faj_score_correct', 'expert_score_correct']]
    
    def get_current_weights(self) -> Dict:
        if self.weights_history:
            return self.weights_history[-1]['weights']
        return self.config.get("weights", {})
    
    def update_weights(self, new_weights: Dict, reason: str) -> None:
        version = f"10.{len(self.weights_history)}"
        record = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'weights': new_weights,
            'reason': reason
        }
        self.weights_history.append(record)
        self.save_json("weights_history.json", self.weights_history)
        
        # Обновляем конфиг
        self.config["weights"] = new_weights
        self.save_json("config.json", self.config)
    
    def calculate_accuracy(self) -> Dict:
        if not self.comparison_log:
            return {"faj": 0, "expert": 0, "faj_score": 0, "expert_score": 0, "total": 0}
        
        total = len(self.comparison_log)
        faj_correct = sum(1 for r in self.comparison_log if r.get('faj_correct', False))
        expert_correct = sum(1 for r in self.comparison_log if r.get('expert_correct', False))
        faj_score_correct = sum(1 for r in self.comparison_log if r.get('faj_score_correct', False))
        expert_score_correct = sum(1 for r in self.comparison_log if r.get('expert_score_correct', False))
        
        return {
            "total": total,
            "faj": round(faj_correct / total * 100, 1) if total > 0 else 0,
            "expert": round(expert_correct / total * 100, 1) if total > 0 else 0,
            "faj_score": round(faj_score_correct / total * 100, 1) if total > 0 else 0,
            "expert_score": round(expert_score_correct / total * 100, 1) if total > 0 else 0
        }
    
    def get_weights_history_df(self) -> pd.DataFrame:
        if not self.weights_history:
            return pd.DataFrame()
        
        records = []
        for item in self.weights_history:
            record = {
                'version': item.get('version', ''),
                'timestamp': item.get('timestamp', ''),
                'reason': item.get('reason', '')
            }
            record.update(item.get('weights', {}))
            records.append(record)
        
        return pd.DataFrame(records)


if __name__ == "__main__":
    db = LearningDB()
    print("=" * 50)
    print("FAJ Learning Database v10.0 - Тест")
    print("=" * 50)
    print(f"\n📊 Команды в базе: {len(db.get_all_teams())}")
    print(f"📋 Записей в памяти: {len(db.memory)}")
    print(f"⚖️ Версия весов: {db.weights_history[-1]['version'] if db.weights_history else 'Нет'}")
    print("\n✅ Тест завершен успешно!")
