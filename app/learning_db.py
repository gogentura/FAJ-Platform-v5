#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Learning Database v10.0
Самообучающаяся система для хранения и анализа прогнозов

Функции:
- Хранение паспортов команд
- Хранение прогнозов FAJ и экспертных
- Хранение фактических результатов
- Анализ ошибок
- Корректировка весов модели
- История обучения
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
        """Создание директории для данных"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def load_all(self) -> None:
        """Загрузка всех данных из файлов"""
        self.passports = self.load_json("passports_2026.json", self.get_default_passports())
        self.tour1_results = self.load_json("tour1_results.json", self.get_default_tour1())
        self.tour2_predictions = self.load_json("tour2_predictions.json", self.get_default_tour2())
        self.memory = self.load_json("learning_memory.json", [])
        self.weights_history = self.load_json("weights_history.json", self.get_default_weights())
        self.comparison_log = self.load_json("comparison_log.json", [])
    
    # ============================================================
    # БАЗОВЫЕ МЕТОДЫ РАБОТЫ С JSON
    # ============================================================
    
    def load_json(self, filename: str, default: Any) -> Any:
        """Загрузка JSON-файла"""
        path = os.path.join(self.data_dir, filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return default
        return default
    
    def save_json(self, filename: str, data: Any) -> None:
        """Сохранение JSON-файла"""
        path = os.path.join(self.data_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ============================================================
    # ДАННЫЕ ПО УМОЛЧАНИЮ (ДЛЯ ПЕРВОГО ЗАПУСКА)
    # ============================================================
    
    def get_default_passports(self) -> Dict:
        """Паспорта команд после 1-го тура (скорректированные)"""
        return {
            "Зенит": {
                "attack": 92, "defense": 82, "control": 85,
                "efficiency": 90, "mentality": 95, "tempo": 85,
                "press": 88, "transition": 82, "flexibility": 87,
                "coach": 92, "form": 92, "depth": 88,
                "home_rating": 95, "away_rating": 88
            },
            "Краснодар": {
                "attack": 92, "defense": 82, "control": 88,
                "efficiency": 90, "mentality": 88, "tempo": 85,
                "press": 85, "transition": 80, "flexibility": 87,
                "coach": 88, "form": 92, "depth": 84,
                "home_rating": 92, "away_rating": 86
            },
            "Спартак": {
                "attack": 88, "defense": 78, "control": 82,
                "efficiency": 85, "mentality": 75, "tempo": 86,
                "press": 84, "transition": 70, "flexibility": 78,
                "coach": 80, "form": 88, "depth": 78,
                "home_rating": 90, "away_rating": 82
            },
            "Локомотив": {
                "attack": 86, "defense": 84, "control": 83,
                "efficiency": 88, "mentality": 82, "tempo": 86,
                "press": 80, "transition": 78, "flexibility": 82,
                "coach": 85, "form": 87, "depth": 82,
                "home_rating": 88, "away_rating": 84
            },
            "ЦСКА": {
                "attack": 82, "defense": 80, "control": 80,
                "efficiency": 81, "mentality": 78, "tempo": 80,
                "press": 76, "transition": 74, "flexibility": 76,
                "coach": 78, "form": 82, "depth": 76,
                "home_rating": 85, "away_rating": 78
            },
            "Динамо М": {
                "attack": 78, "defense": 78, "control": 80,
                "efficiency": 80, "mentality": 76, "tempo": 82,
                "press": 76, "transition": 74, "flexibility": 78,
                "coach": 80, "form": 75, "depth": 76,
                "home_rating": 82, "away_rating": 76
            },
            "Ростов": {
                "attack": 78, "defense": 76, "control": 75,
                "efficiency": 77, "mentality": 80, "tempo": 76,
                "press": 74, "transition": 72, "flexibility": 74,
                "coach": 76, "form": 78, "depth": 72,
                "home_rating": 80, "away_rating": 74
            },
            "Рубин": {
                "attack": 76, "defense": 74, "control": 73,
                "efficiency": 75, "mentality": 78, "tempo": 74,
                "press": 72, "transition": 70, "flexibility": 72,
                "coach": 74, "form": 76, "depth": 70,
                "home_rating": 78, "away_rating": 72
            },
            "Ахмат": {
                "attack": 74, "defense": 72, "control": 70,
                "efficiency": 73, "mentality": 76, "tempo": 72,
                "press": 70, "transition": 68, "flexibility": 70,
                "coach": 72, "form": 74, "depth": 68,
                "home_rating": 76, "away_rating": 70
            },
            "Оренбург": {
                "attack": 72, "defense": 70, "control": 68,
                "efficiency": 71, "mentality": 74, "tempo": 70,
                "press": 68, "transition": 66, "flexibility": 68,
                "coach": 70, "form": 72, "depth": 66,
                "home_rating": 76, "away_rating": 68
            },
            "Крылья Советов": {
                "attack": 70, "defense": 74, "control": 72,
                "efficiency": 69, "mentality": 70, "tempo": 72,
                "press": 68, "transition": 62, "flexibility": 70,
                "coach": 68, "form": 70, "depth": 66,
                "home_rating": 72, "away_rating": 68
            },
            "Факел": {
                "attack": 68, "defense": 70, "control": 65,
                "efficiency": 67, "mentality": 72, "tempo": 68,
                "press": 66, "transition": 64, "flexibility": 66,
                "coach": 68, "form": 68, "depth": 64,
                "home_rating": 72, "away_rating": 64
            },
            "Балтика": {
                "attack": 62, "defense": 60, "control": 58,
                "efficiency": 61, "mentality": 64, "tempo": 60,
                "press": 58, "transition": 56, "flexibility": 58,
                "coach": 60, "form": 65, "depth": 56,
                "home_rating": 65, "away_rating": 58
            },
            "Динамо Мх": {
                "attack": 64, "defense": 62, "control": 60,
                "efficiency": 63, "mentality": 66, "tempo": 62,
                "press": 60, "transition": 58, "flexibility": 60,
                "coach": 62, "form": 65, "depth": 58,
                "home_rating": 66, "away_rating": 60
            },
            "Акрон": {
                "attack": 60, "defense": 55, "control": 56,
                "efficiency": 58, "mentality": 60, "tempo": 58,
                "press": 54, "transition": 50, "flexibility": 56,
                "coach": 58, "form": 45, "depth": 54,
                "home_rating": 62, "away_rating": 54
            },
            "Родина": {
                "attack": 65, "defense": 60, "control": 62,
                "efficiency": 64, "mentality": 62, "tempo": 60,
                "press": 58, "transition": 56, "flexibility": 60,
                "coach": 60, "form": 50, "depth": 58,
                "home_rating": 64, "away_rating": 58
            }
        }
    
    def get_default_tour1(self) -> Dict:
        """Результаты 1-го тура (факт + прогнозы)"""
        return {
            "ЦСКА-Балтика": {
                "faj": "1:1",
                "expert": "1:0",
                "actual": "2:1",
                "xg": {"home": 2.25, "away": 1.52}
            },
            "Динамо-Крылья": {
                "faj": "3:1",
                "expert": "2:0",
                "actual": "0:0",
                "xg": {"home": 1.85, "away": 0.65}
            },
            "Акрон-Зенит": {
                "faj": "0:2",
                "expert": "0:2",
                "actual": "0:5",
                "xg": {"home": 0.69, "away": 2.52}
            },
            "Факел-ДинМх": {
                "faj": "1:0",
                "expert": "1:0",
                "actual": "1:2",
                "xg": {"home": 1.16, "away": 0.85}
            },
            "Спартак-Родина": {
                "faj": "2:0",
                "expert": "2:0",
                "actual": "3:0",
                "xg": {"home": 2.50, "away": 0.55}
            },
            "Оренбург-Ростов": {
                "faj": "1:1",
                "expert": "1:1",
                "actual": "2:1",
                "xg": {"home": 0.82, "away": 0.69}
            },
            "Локомотив-Ахмат": {
                "faj": "2:1",
                "expert": "2:1",
                "actual": "1:1",
                "xg": {"home": 1.27, "away": 1.24}
            },
            "Рубин-Краснодар": {
                "faj": "1:1",
                "expert": "1:2",
                "actual": "1:3",
                "xg": {"home": 0.61, "away": 2.76}
            }
        }
    
    def get_default_tour2(self) -> Dict:
        """Прогнозы на 2-й тур (FAJ + Эксперт)"""
        return {
            "Родина-Ростов": {
                "faj": "0:1",
                "expert": "0:2",
                "xg": {"home": 0.82, "away": 1.34}
            },
            "Акрон-Рубин": {
                "faj": "0:1",
                "expert": "1:2",
                "xg": {"home": 0.41, "away": 1.18}
            },
            "ЦСКА-Крылья": {
                "faj": "1:0",
                "expert": "1:0",
                "xg": {"home": 1.37, "away": 0.85}
            },
            "ДинМх-Локомотив": {
                "faj": "0:1",
                "expert": "1:2",
                "xg": {"home": 0.61, "away": 1.57}
            },
            "Балтика-Динамо": {
                "faj": "0:1",
                "expert": "1:2",
                "xg": {"home": 0.52, "away": 1.25}
            },
            "Оренбург-Зенит": {
                "faj": "0:2",
                "expert": "0:2",
                "xg": {"home": 0.63, "away": 1.88}
            },
            "Краснодар-Факел": {
                "faj": "2:0",
                "expert": "3:0",
                "xg": {"home": 1.91, "away": 0.63}
            },
            "Ахмат-Спартак": {
                "faj": "0:1",
                "expert": "1:2",
                "xg": {"home": 0.68, "away": 1.36}
            }
        }
    
    def get_default_weights(self) -> List:
        """История весов модели"""
        return [
            {
                "version": "10.0",
                "timestamp": "2026-07-31T00:00:00",
                "weights": {
                    "attack": 0.18, "defense": 0.18, "control": 0.15,
                    "efficiency": 0.12, "mentality": 0.10, "tempo": 0.07,
                    "press": 0.05, "transition": 0.05, "flexibility": 0.05,
                    "coach": 0.05
                },
                "reason": "Initial weights before season"
            },
            {
                "version": "10.1",
                "timestamp": "2026-08-01T00:00:00",
                "weights": {
                    "attack": 0.19, "defense": 0.19, "control": 0.14,
                    "efficiency": 0.12, "mentality": 0.11, "tempo": 0.07,
                    "press": 0.05, "transition": 0.04, "flexibility": 0.05,
                    "coach": 0.04
                },
                "reason": "After Tour 1 correction"
            }
        ]
    
    # ============================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПАСПОРТАМИ
    # ============================================================
    
    def get_team_passport(self, team_name: str) -> Dict:
        """Получить паспорт команды"""
        return self.passports.get(team_name, {})
    
    def get_all_teams(self) -> List[str]:
        """Получить список всех команд"""
        return list(self.passports.keys())
    
    def update_team_passport(self, team_name: str, data: Dict) -> None:
        """Обновить паспорт команды"""
        if team_name in self.passports:
            self.passports[team_name].update(data)
        else:
            self.passports[team_name] = data
        self.save_json("passports_2026.json", self.passports)
    
    # ============================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПРОГНОЗАМИ
    # ============================================================
    
    def get_tour_predictions(self, tour: str = "tour2") -> Dict:
        """Получить прогнозы на тур"""
        if tour == "tour1":
            return self.tour1_results
        elif tour == "tour2":
            return self.tour2_predictions
        return {}
    
    def update_tour_predictions(self, tour: str, predictions: Dict) -> None:
        """Обновить прогнозы на тур"""
        if tour == "tour1":
            self.tour1_results = predictions
            self.save_json("tour1_results.json", self.tour1_results)
        elif tour == "tour2":
            self.tour2_predictions = predictions
            self.save_json("tour2_predictions.json", self.tour2_predictions)
    
    # ============================================================
    # МЕТОДЫ ДЛЯ САМООБУЧЕНИЯ
    # ============================================================
    
    def add_learning_record(self, record: Dict) -> None:
        """Добавить запись в память обучения"""
        record['timestamp'] = datetime.now().isoformat()
        self.memory.append(record)
        self.save_json("learning_memory.json", self.memory)
    
    def get_learning_stats(self) -> Dict:
        """Получить статистику обучения"""
        return {
            'total_records': len(self.memory),
            'teams_count': len(self.passports),
            'weights_updates': len(self.weights_history),
            'comparisons': len(self.comparison_log),
            'last_update': self.memory[-1]['timestamp'] if self.memory else None
        }
    
    def compare_prediction(self, match: str, faj_pred: str, expert_pred: str, actual: str) -> Dict:
        """
        Сравнение прогнозов и фиксация ошибок
        
        Args:
            match: Название матча (например, "ЦСКА-Балтика")
            faj_pred: Прогноз FAJ (например, "2:1")
            expert_pred: Экспертный прогноз (например, "1:0")
            actual: Фактический результат (например, "2:1")
        
        Returns:
            Dict с результатами сравнения
        """
        # Определяем исходы
        def get_outcome(score):
            if not score or score == "-":
                return None
            h, a = map(int, score.split(':'))
            if h > a:
                return "П1"
            elif h == a:
                return "X"
            else:
                return "П2"
        
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
        """Получить сводку сравнения прогнозов в виде DataFrame"""
        if not self.comparison_log:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.comparison_log)
        return df[['match', 'faj_pred', 'expert_pred', 'actual', 
                   'faj_correct', 'expert_correct', 'faj_score_correct', 'expert_score_correct']]
    
    # ============================================================
    # МЕТОДЫ ДЛЯ РАБОТЫ С ВЕСАМИ
    # ============================================================
    
    def get_current_weights(self) -> Dict:
        """Получить текущие веса модели"""
        if self.weights_history:
            return self.weights_history[-1]['weights']
        return self.get_default_weights()[0]['weights']
    
    def update_weights(self, new_weights: Dict, reason: str) -> None:
        """Обновить веса модели"""
        version = f"10.{len(self.weights_history)}"
        record = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'weights': new_weights,
            'reason': reason
        }
        self.weights_history.append(record)
        self.save_json("weights_history.json", self.weights_history)
    
    def get_weights_history_df(self) -> pd.DataFrame:
        """Получить историю весов в виде DataFrame"""
        if not self.weights_history:
            return pd.DataFrame()
        
        records = []
        for item in self.weights_history:
            record = {
                'version': item['version'],
                'timestamp': item['timestamp'],
                'reason': item['reason']
            }
            record.update(item['weights'])
            records.append(record)
        
        return pd.DataFrame(records)
    
    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================
    
    def get_match_pairs(self, tour: str = "tour2") -> List[tuple]:
        """Получить список пар команд для тура"""
        data = self.get_tour_predictions(tour)
        return [(k.split('-')[0], k.split('-')[1]) for k in data.keys()]
    
    def get_match_data(self, match: str, tour: str = "tour2") -> Dict:
        """Получить данные по матчу"""
        data = self.get_tour_predictions(tour)
        return data.get(match, {})
    
    def add_result(self, match: str, result: str, tour: str = "tour1") -> None:
        """Добавить/обновить результат матча"""
        data = self.get_tour_predictions(tour)
        if match in data:
            data[match]['actual'] = result
            self.update_tour_predictions(tour, data)
    
    def calculate_accuracy(self) -> Dict:
        """Рассчитать точность прогнозов"""
        if not self.comparison_log:
            return {"faj": 0, "expert": 0, "faj_score": 0, "expert_score": 0, "total": 0}
        
        total = len(self.comparison_log)
        faj_correct = sum(1 for r in self.comparison_log if r['faj_correct'])
        expert_correct = sum(1 for r in self.comparison_log if r['expert_correct'])
        faj_score_correct = sum(1 for r in self.comparison_log if r['faj_score_correct'])
        expert_score_correct = sum(1 for r in self.comparison_log if r['expert_score_correct'])
        
        return {
            "total": total,
            "faj": round(faj_correct / total * 100, 1) if total > 0 else 0,
            "expert": round(expert_correct / total * 100, 1) if total > 0 else 0,
            "faj_score": round(faj_score_correct / total * 100, 1) if total > 0 else 0,
            "expert_score": round(expert_score_correct / total * 100, 1) if total > 0 else 0
        }


# ============================================================
# ТЕСТИРОВАНИЕ (если запустить файл напрямую)
# ============================================================

if __name__ == "__main__":
    # Создаем экземпляр
    db = LearningDB()
    
    print("=" * 50)
    print("FAJ Learning Database v10.0 - Тест")
    print("=" * 50)
    
    print(f"\n📊 Команды в базе: {len(db.get_all_teams())}")
    print(f"📋 Записей в памяти: {len(db.memory)}")
    print(f"⚖️ Версия весов: {db.weights_history[-1]['version'] if db.weights_history else 'Нет'}")
    
    print("\n📈 Текущие веса:")
    for key, value in db.get_current_weights().items():
        print(f"  {key}: {value}")
    
    print("\n📊 Статистика сравнения:")
    stats = db.calculate_accuracy()
    print(f"  Всего матчей: {stats['total']}")
    print(f"  FAJ точность исходов: {stats['faj']}%")
    print(f"  Эксперт точность исходов: {stats['expert']}%")
    
    print("\n✅ Тест завершен успешно!")
