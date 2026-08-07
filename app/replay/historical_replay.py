#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Historical Replay v1.0 — минимальная машина времени для FAJ

Цель: взять JSON тура → прогнать через Prediction Manager → сравнить с фактом
Никаких избыточных слоёв.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from app.database import FAJDatabase
from app.core.prediction_manager import get_prediction_manager
from app.engines.source_adapters.soccerland_adapter import SoccerlandAdapter

logger = logging.getLogger(__name__)


class HistoricalReplay:
    """
    Historical Replay v1.0 — минимальная версия
    """

    def __init__(self, db=None):
        self.db = db or FAJDatabase()
        self.data_dir = Path("data/historical")
        self.predictions_dir = Path("data/predictions")
        self.training_dir = Path("data/training")
        self.replay_dir = Path("data/replay")
        
        for dir_path in [self.data_dir, self.predictions_dir, self.training_dir, self.replay_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        self.adapter = SoccerlandAdapter()
        self.pm = get_prediction_manager()
        self.current_tour = 0

    def _load_tour_data(self, tour: int) -> Dict:
        """Загружает данные тура из JSON"""
        file_path = self.data_dir / f"rpl_2026_27_tour{tour}.json"
        if not file_path.exists():
            logger.warning(f"⚠️ Файл не найден: {file_path}")
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки: {e}")
            return None

    def _prepare_matches_for_prediction(self, tour_data: Dict) -> List[Dict]:
        """Подготавливает матчи для прогноза (без результатов)"""
        matches = []
        for match in tour_data.get('matches', []):
            matches.append({
                "home_team": match.get('home_team'),
                "away_team": match.get('away_team'),
                "date": match.get('date'),
                "round": tour_data.get('tour'),
                "season": tour_data.get('season', '2026/27'),
                "season_id": tour_data.get('season_id', 1)
            })
        return matches

    def _get_results(self, tour_data: Dict) -> List[Dict]:
        """Извлекает реальные результаты из данных тура"""
        results = []
        for match in tour_data.get('matches', []):
            if match.get('home_goals') is not None and match.get('away_goals') is not None:
                results.append({
                    "home_team": match.get('home_team'),
                    "away_team": match.get('away_team'),
                    "home_goals": match.get('home_goals'),
                    "away_goals": match.get('away_goals'),
                    "home_xg": match.get('home_xg'),
                    "away_xg": match.get('away_xg'),
                    "status": "FINISHED"
                })
        return results

    def _run_predictions(self, matches: List[Dict]) -> List[Dict]:
        """Запускает прогнозы для всех матчей с диагностикой паспортов"""
        predictions = []
        
        for match in matches:
            try:
                home_team = match.get('home_team')
                away_team = match.get('away_team')
                
                if not home_team or not away_team:
                    continue
                
                # ============================================================
                # ДИАГНОСТИКА ПАСПОРТОВ
                # ============================================================
                logger.info(f"🔍 Проверка паспортов: {home_team} vs {away_team}")
                
                try:
                    home_passport = self.pm.passport_manager.get_current_passport_by_name(home_team)
                    away_passport = self.pm.passport_manager.get_current_passport_by_name(away_team)
                    
                    if home_passport:
                        home_base = home_passport.get("BASE", {})
                        home_rating = home_passport.get("faj_rating", "N/A")
                        logger.info(
                            f"   ✅ {home_team} паспорт найден: "
                            f"rating={home_rating}, "
                            f"attack={home_base.get('attack', 'N/A')}, "
                            f"defense={home_base.get('defense', 'N/A')}, "
                            f"control={home_base.get('control', 'N/A')}"
                        )
                    else:
                        logger.error(f"   ❌ {home_team}: паспорт НЕ НАЙДЕН")
                    
                    if away_passport:
                        away_base = away_passport.get("BASE", {})
                        away_rating = away_passport.get("faj_rating", "N/A")
                        logger.info(
                            f"   ✅ {away_team} паспорт найден: "
                            f"rating={away_rating}, "
                            f"attack={away_base.get('attack', 'N/A')}, "
                            f"defense={away_base.get('defense', 'N/A')}, "
                            f"control={away_base.get('control', 'N/A')}"
                        )
                    else:
                        logger.error(f"   ❌ {away_team}: паспорт НЕ НАЙДЕН")
                        
                except Exception as e:
                    logger.error(f"   ❌ Ошибка проверки паспортов: {e}")
                
                # ============================================================
                # ПРОГНОЗ
                # ============================================================
                result = self.pm.predict(
                    home_team=home_team,
                    away_team=away_team,
                    league="RPL"
                )
                
                if hasattr(result, "__dict__"):
                    result = result.__dict__
                
                # ============================================================
                # ДИАГНОСТИКА РЕЗУЛЬТАТА
                # ============================================================
                xg = result.get("xg", {})
                logger.info(
                    f"   📊 {home_team} vs {away_team} → "
                    f"xG {xg.get('home', 0):.2f} : {xg.get('away', 0):.2f}, "
                    f"score={result.get('score', 'N/A')}, "
                    f"confidence={result.get('confidence', {}).get('overall', 0):.3f}"
                )
                
                predictions.append({
                    "home_team": home_team,
                    "away_team": away_team,
                    "round": match.get('round'),
                    "date": match.get('date'),
                    "prediction": result,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"❌ Ошибка прогноза для {match.get('home_team')} vs {match.get('away_team')}: {e}")
        
        return predictions

    def _compare_predictions(self, predictions: List[Dict], results: List[Dict]) -> List[Dict]:
        """Сравнивает прогнозы с реальными результатами"""
        comparison = []
        
        for pred in predictions:
            home_team = pred.get('home_team')
            away_team = pred.get('away_team')
            
            actual = None
            for r in results:
                if r.get('home_team') == home_team and r.get('away_team') == away_team:
                    actual = r
                    break
            
            if not actual:
                continue
            
            pred_data = pred.get('prediction', {})
            
            actual_home = actual.get('home_goals', 0)
            actual_away = actual.get('away_goals', 0)
            actual_score = f"{actual_home}:{actual_away}"
            
            pred_home = pred_data.get('xg', {}).get('home', 0)
            pred_away = pred_data.get('xg', {}).get('away', 0)
            pred_home_int = round(pred_home)
            pred_away_int = round(pred_away)
            predicted_score = f"{pred_home_int}:{pred_away_int}"
            
            pred_home_prob = pred_data.get('probability', {}).get('home', 0)
            pred_draw_prob = pred_data.get('probability', {}).get('draw', 0)
            pred_away_prob = pred_data.get('probability', {}).get('away', 0)
            
            if actual_home > actual_away:
                actual_result = "home"
            elif actual_home == actual_away:
                actual_result = "draw"
            else:
                actual_result = "away"
            
            if pred_home_prob > pred_draw_prob and pred_home_prob > pred_away_prob:
                pred_result = "home"
            elif pred_draw_prob > pred_home_prob and pred_draw_prob > pred_away_prob:
                pred_result = "draw"
            else:
                pred_result = "away"
            
            score_correct = predicted_score == actual_score
            result_correct = pred_result == actual_result
            
            pred_btts = pred_data.get('btts', 0)
            actual_btts = 1 if (actual_home > 0 and actual_away > 0) else 0
            btts_correct = 1 if (pred_btts >= 0.5 and actual_btts == 1) or (pred_btts < 0.5 and actual_btts == 0) else 0
            
            pred_over25 = pred_data.get('over_2_5', 0)
            actual_total = actual_home + actual_away
            actual_over25 = 1 if actual_total > 2.5 else 0
            over25_correct = 1 if (pred_over25 >= 0.5 and actual_over25 == 1) or (pred_over25 < 0.5 and actual_over25 == 0) else 0
            
            home_xg_actual = actual.get('home_xg')
            away_xg_actual = actual.get('away_xg')
            if home_xg_actual is not None and away_xg_actual is not None:
                xg_error = abs(pred_home - home_xg_actual) + abs(pred_away - away_xg_actual)
            else:
                xg_error = None
            
            comparison.append({
                "home_team": home_team,
                "away_team": away_team,
                "predicted_score": predicted_score,
                "actual_score": actual_score,
                "score_correct": score_correct,
                "predicted_result": pred_result,
                "actual_result": actual_result,
                "result_correct": result_correct,
                "xg_home_pred": round(pred_home, 2),
                "xg_away_pred": round(pred_away, 2),
                "xg_home_actual": home_xg_actual,
                "xg_away_actual": away_xg_actual,
                "xg_error": round(xg_error, 2) if xg_error is not None else None,
                "btts_correct": btts_correct,
                "over25_correct": over25_correct,
                "confidence": pred_data.get('confidence', {}).get('overall', 0),
                "risk": pred_data.get('risk', {}).get('score', 0)
            })
        
        return comparison

    def _save_predictions(self, predictions: List[Dict], tour: int):
        """Сохраняет прогнозы в JSON"""
        file_path = self.predictions_dir / f"tour{tour}_predictions.json"
        data = {
            "tour": tour,
            "timestamp": datetime.now().isoformat(),
            "predictions": predictions
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Прогнозы сохранены: {file_path}")

    def _save_comparison(self, comparison: List[Dict], tour: int):
        """Сохраняет сравнение в JSON"""
        file_path = self.training_dir / f"comparison_tour{tour}.json"
        data = {
            "tour": tour,
            "timestamp": datetime.now().isoformat(),
            "comparison": comparison
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Сравнение сохранено: {file_path}")

    def run_tour(self, tour: int) -> Dict:
        """Полный цикл одного тура"""
        logger.info(f"🔄 Запуск Historical Replay для тура {tour}")

        tour_data = self._load_tour_data(tour)
        if not tour_data:
            return {"status": "error", "message": f"Тур {tour} не найден"}

        matches = self._prepare_matches_for_prediction(tour_data)
        logger.info(f"📡 Загружено {len(matches)} матчей")

        logger.info("🔮 Запуск Prediction Engine...")
        predictions = self._run_predictions(matches)
        self._save_predictions(predictions, tour)

        results = self._get_results(tour_data)
        logger.info("⚖️ Сравнение прогнозов с фактом...")
        comparison = self._compare_predictions(predictions, results)
        self._save_comparison(comparison, tour)

        total = len(comparison)
        if total == 0:
            return {"status": "error", "message": "Нет данных для сравнения"}

        result_correct = sum(1 for c in comparison if c['result_correct'])
        score_correct = sum(1 for c in comparison if c['score_correct'])
        btts_correct = sum(1 for c in comparison if c['btts_correct'])
        over25_correct = sum(1 for c in comparison if c['over25_correct'])
        
        xg_values = [c['xg_error'] for c in comparison if c['xg_error'] is not None]
        total_xg_error = sum(xg_values)
        xg_error_count = len(xg_values)
        avg_xg_error = total_xg_error / xg_error_count if xg_error_count > 0 else None

        result_accuracy = result_correct / total * 100
        score_accuracy = score_correct / total * 100
        btts_accuracy = btts_correct / total * 100
        over25_accuracy = over25_correct / total * 100

        logger.info("=" * 50)
        logger.info(f"📊 РЕЗУЛЬТАТЫ ТУРА {tour}")
        logger.info(f"📊 Всего матчей: {total}")
        logger.info(f"🎯 Точность исходов: {result_accuracy:.1f}% ({result_correct}/{total})")
        logger.info(f"🎯 Точность счёта: {score_accuracy:.1f}% ({score_correct}/{total})")
        logger.info(f"⚽ Точность BTTS: {btts_accuracy:.1f}%")
        logger.info(f"📈 Точность ТБ 2.5: {over25_accuracy:.1f}%")
        if avg_xg_error is not None:
            logger.info(f"📊 Средняя ошибка xG: {avg_xg_error:.2f}")
        else:
            logger.info("📊 xG данные отсутствуют")
        logger.info("=" * 50)

        return {
            "tour": tour,
            "status": "success",
            "total_matches": total,
            "result_accuracy": round(result_accuracy, 1),
            "score_accuracy": round(score_accuracy, 1),
            "btts_accuracy": round(btts_accuracy, 1),
            "over25_accuracy": round(over25_accuracy, 1),
            "avg_xg_error": round(avg_xg_error, 2) if avg_xg_error is not None else None,
            "comparison": comparison
        }


if __name__ == "__main__":
    replay = HistoricalReplay()
    result = replay.run_tour(1)
    if result.get("status") == "success":
        print(f"✅ Тур 1 завершён!")
        print(f"   Точность исходов: {result['result_accuracy']}%")
        print(f"   Точность счёта: {result['score_accuracy']}%")
