#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Historical Replay v1.4 — машина времени для FAJ

Исправления v1.4:
1. Replay Context Injection — передача паспортов в Prediction Manager
2. Prediction Audit Trail — полный контекст прогноза
3. Исправление run_season — корректный подсчёт очков
4. Безопасное получение версий через getattr
5. Replay ID для каждого запуска
6. Расширенная блокировка Replay Guard
"""

import json
import logging
import hashlib
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from app.database import FAJDatabase
from app.core.prediction_manager import get_prediction_manager
from app.core.replay_guard import get_replay_guard
from app.engines.parser_engine import ParserEngine
from app.engines.source_adapters.soccerland_adapter import SoccerlandAdapter
from app.config import config

logger = logging.getLogger(__name__)


class HistoricalReplay:
    """
    Historical Replay v1.4 — машина времени для FAJ
    """

    def __init__(self, db: Optional[FAJDatabase] = None):
        self.db = db or FAJDatabase()
        self.data_dir = Path("data/historical")
        self.predictions_dir = Path("data/predictions")
        self.training_dir = Path("data/training")
        self.passports_dir = Path("data/passports")
        self.replay_dir = Path("data/replay")
        
        for dir_path in [self.data_dir, self.predictions_dir, self.training_dir, 
                         self.passports_dir, self.replay_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        self.parser = ParserEngine(db=self.db)
        self.adapter = SoccerlandAdapter()
        self.pm = get_prediction_manager()
        self.guard = get_replay_guard()
        
        self.current_tour = 0
        
        # Безопасное получение версий
        self.model_version = getattr(config, 'PLATFORM_VERSION', 'unknown')
        self.weights_version = getattr(config, 'CORE_VERSION', 'unknown')
        self.passport_version = getattr(config, 'PASSPORT_VERSION', 'unknown')
        
        # Генерация уникального ID запуска
        self.replay_id = f"RPL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # Контекст тура
        self._replay_context = {
            "tour": None,
            "passports": {},
            "cutoff_date": None,
            "replay_id": self.replay_id
        }

    # ============================================================
    # REPLAY CONTEXT INJECTION
    # ============================================================

    def _set_replay_context(self, tour: int, passports: Dict, cutoff_date: str = None):
        """Устанавливает контекст для Prediction Manager"""
        self._replay_context = {
            "tour": tour,
            "passports": passports,
            "cutoff_date": cutoff_date or datetime.now().isoformat(),
            "replay_id": self.replay_id
        }
        # Передаём контекст в Prediction Manager
        self.pm.set_replay_context(self._replay_context)
        logger.info(f"📝 Replay Context установлен для тура {tour} (ID: {self.replay_id})")

    def _clear_replay_context(self):
        """Очищает контекст после тура"""
        self._replay_context = {"tour": None, "passports": {}, "cutoff_date": None, "replay_id": self.replay_id}
        self.pm.clear_replay_context()
        logger.info("🧹 Replay Context очищен")

    # ============================================================
    # REPLAY LOCK (через Replay Guard)
    # ============================================================

    def _acquire_replay_lock(self, tour: int) -> bool:
        return self.guard.lock(tour, replay_id=self.replay_id)

    def _release_replay_lock(self):
        self.guard.unlock()

    # ============================================================
    # PASSPORT TIME MACHINE
    # ============================================================

    def _load_passport_for_replay(self, tour: int) -> Dict:
        """Загружает правильный снимок паспортов для тура"""
        if tour == 1:
            initial_path = self.passports_dir / "initial_snapshot.json"
            if initial_path.exists():
                try:
                    with open(initial_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    logger.info(f"📸 Загружен initial_snapshot")
                    return data.get('passports', {})
                except:
                    pass
            
            logger.info("📸 initial_snapshot не найден, создаю из текущих паспортов")
            snapshot = self._capture_full_passports()
            self._save_passport_snapshot(snapshot, 0, "initial")
            return snapshot
        
        previous_tour = tour - 1
        prev_path = self.passports_dir / f"snapshot_tour{previous_tour}_after.json"
        if prev_path.exists():
            try:
                with open(prev_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"📸 Загружен снимок после тура {previous_tour}")
                return data.get('passports', {})
            except:
                pass
        
        logger.warning(f"⚠️ Снимок после тура {previous_tour} не найден")
        return self._capture_full_passports()

    # ============================================================
    # ОСНОВНОЙ ЦИКЛ
    # ============================================================

    def run_tour(self, tour: int, league: str = "РПЛ") -> Dict:
        """Полный цикл одного тура"""
        self.current_tour = tour
        
        logger.info(f"🔄 Запуск Historical Replay для тура {tour} (ID: {self.replay_id})")

        results = {
            "replay_id": self.replay_id,
            "tour": tour,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "model_version": self.model_version,
            "weights_version": self.weights_version,
            "passport_version": self.passport_version,
            "matches_processed": 0,
            "predictions_saved": 0,
            "comparison_done": 0,
            "score_points": 0,
            "max_score_points": 0
        }

        try:
            # ============================================================
            # 1. БЛОКИРУЕМ ДОСТУП
            # ============================================================
            self._acquire_replay_lock(tour)

            # ============================================================
            # 2. Загружаем календарь
            # ============================================================
            logger.info(f"📡 Загрузка календаря тура {tour}...")
            fixtures = self._load_tour_fixtures(tour)
            
            if not fixtures:
                logger.warning(f"⚠️ Нет матчей для тура {tour}")
                results["status"] = "no_matches"
                self._release_replay_lock()
                return results

            # ============================================================
            # 3. Сохраняем календарь
            # ============================================================
            logger.info(f"💾 Сохранение {len(fixtures)} матчей...")
            saved = self._save_fixtures(fixtures)
            results["matches_processed"] = saved

            # ============================================================
            # 4. Загружаем исторический снимок паспортов
            # ============================================================
            logger.info("📸 Загрузка исторического снимка паспортов...")
            passport_snapshot = self._load_passport_for_replay(tour)
            cutoff_date = fixtures[0].get('date') if fixtures else None
            logger.info(f"   ✅ Загружено {len(passport_snapshot)} паспортов")

            # ============================================================
            # 5. УСТАНАВЛИВАЕМ КОНТЕКСТ В PREDICTION MANAGER
            # ============================================================
            self._set_replay_context(tour, passport_snapshot, cutoff_date)

            # ============================================================
            # 6. Делаем прогнозы
            # ============================================================
            logger.info("🔮 Запуск Prediction Engine...")
            predictions = self._run_predictions(fixtures)
            self._save_predictions(predictions, tour)
            results["predictions_saved"] = len(predictions)

            # ============================================================
            # 7. Очищаем контекст
            # ============================================================
            self._clear_replay_context()

            # ============================================================
            # 8. Снимаем блокировку
            # ============================================================
            self._release_replay_lock()

            # ============================================================
            # 9. Загружаем результаты
            # ============================================================
            logger.info("📊 Загрузка реальных результатов...")
            actual_results = self._load_tour_results(tour)
            self._update_matches_with_results(actual_results)

            # ============================================================
            # 10. Сравниваем прогнозы с фактом
            # ============================================================
            logger.info("⚖️ Сравнение прогнозов с фактом...")
            comparison = self._compare_predictions_improved(predictions, actual_results)
            self._save_comparison(comparison, tour)
            results["comparison_done"] = len(comparison)

            # ============================================================
            # 11. Считаем очки
            # ============================================================
            total_score_points = sum(c.get('score_points', 0) for c in comparison)
            max_score_points = len(comparison) * 3
            results["score_points"] = total_score_points
            results["max_score_points"] = max_score_points

            # ============================================================
            # 12. Обновляем модель через Learning Engine
            # ============================================================
            logger.info("🧠 Запуск Learning Engine...")
            learning_result = self._run_learning_engine(comparison, tour)
            self._save_replay_journal(tour, learning_result)

            # ============================================================
            # 13. Сохраняем снимок паспортов ПОСЛЕ тура
            # ============================================================
            logger.info("📸 Сохранение снимка паспортов после тура...")
            passport_snapshot = self._capture_full_passports()
            self._save_passport_snapshot(passport_snapshot, tour, "after")

            logger.info(f"✅ Тур {tour} завершён! (ID: {self.replay_id})")

        except Exception as e:
            logger.error(f"❌ Ошибка в туре {tour}: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            self._clear_replay_context()
            self._release_replay_lock()

        return results

    # ============================================================
    # ЗАГРУЗКА ДАННЫХ
    # ============================================================

    def _load_tour_fixtures(self, tour: int) -> List[Dict]:
        """Загрузка календаря тура из JSON"""
        file_path = self.data_dir / f"rpl_2026_27_tour{tour}.json"
        
        if not file_path.exists():
            logger.warning(f"⚠️ Файл не найден: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            fixtures = []
            for match in data.get('matches', []):
                fixture = {
                    "home_team": match.get('home_team'),
                    "away_team": match.get('away_team'),
                    "date": match.get('date'),
                    "round": tour,
                    "status": "SCHEDULED",
                    "season": data.get('season', '2026/27'),
                    "season_id": data.get('season_id', 1),
                    "source": "historical_replay",
                    "source_version": "1.4",
                    "data_cutoff": match.get('date'),
                    "visibility": "before_match",
                    "replay_id": self.replay_id
                }
                validated = self.adapter.validate_match(fixture)
                if validated:
                    fixtures.append(validated)
            
            return fixtures
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки календаря: {e}")
            return []

    def _load_tour_results(self, tour: int) -> List[Dict]:
        """Загрузка реальных результатов тура из JSON"""
        file_path = self.data_dir / f"rpl_2026_27_tour{tour}.json"
        
        if not file_path.exists():
            logger.warning(f"⚠️ Файл не найден: {file_path}")
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results = []
            for match in data.get('matches', []):
                if match.get('home_goals') is not None and match.get('away_goals') is not None:
                    result = {
                        "home_team": match.get('home_team'),
                        "away_team": match.get('away_team'),
                        "home_goals": match.get('home_goals'),
                        "away_goals": match.get('away_goals'),
                        "home_xg": match.get('home_xg'),
                        "away_xg": match.get('away_xg'),
                        "status": "FINISHED",
                        "round": tour,
                        "season": data.get('season', '2026/27'),
                        "season_id": data.get('season_id', 1),
                        "source": "historical_replay",
                        "source_version": "1.4",
                        "visibility": "after_match",
                        "replay_id": self.replay_id
                    }
                    results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки результатов: {e}")
            return []

    # ============================================================
    # СОХРАНЕНИЕ В БД
    # ============================================================

    def _save_fixtures(self, fixtures: List[Dict]) -> int:
        saved = 0
        for fixture in fixtures:
            try:
                match_id = self.db.upsert_match(fixture)
                if match_id:
                    saved += 1
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения: {e}")
        return saved

    def _update_matches_with_results(self, results: List[Dict]) -> int:
        updated = 0
        for result in results:
            try:
                match_id = self.db.upsert_match(result)
                if match_id:
                    updated += 1
            except Exception as e:
                logger.error(f"❌ Ошибка обновления: {e}")
        return updated

    # ============================================================
    # ПОЛНЫЙ СНИМОК ПАСПОРТОВ
    # ============================================================

    def _capture_full_passports(self) -> Dict:
        """Создание полного снимка паспортов через FAJDatabase"""
        try:
            teams = self.db.get_teams(league="РПЛ")
            passports = {}
            for team in teams:
                team_id = team['id']
                team_name = team['name']
                season_id = 1
                
                base = self.db.get_base(team_id, season_id)
                dynamic = self.db.get_dynamic(team_id, season_id)
                identity = self.db.get_identity(team_id, season_id)
                passport = self.db._get_team_passport(team_id, season_id)
                
                passports[team_name] = {
                    "base": dict(base) if base else {},
                    "dynamic": dict(dynamic) if dynamic else {},
                    "identity": dict(identity) if identity else {},
                    "passport": passport if passport else {}
                }
            return passports
        except Exception as e:
            logger.error(f"❌ Ошибка создания снимка: {e}")
            return {}

    def _save_passport_snapshot(self, snapshot: Dict, tour: int, stage: str):
        """Сохранение снимка паспортов"""
        file_path = self.passports_dir / f"snapshot_tour{tour}_{stage}.json"
        data = {
            "replay_id": self.replay_id,
            "tour": tour,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "model_version": self.model_version,
            "passports": snapshot
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Снимок паспортов сохранён: {file_path}")

    # ============================================================
    # ПРОГНОЗЫ
    # ============================================================

    def _run_predictions(self, fixtures: List[Dict]) -> List[Dict]:
        """Запуск прогнозов с контекстом"""
        predictions = []
        
        for fixture in fixtures:
            try:
                home_team = fixture.get('home_team')
                away_team = fixture.get('away_team')
                
                if not home_team or not away_team:
                    continue
                
                result = self.pm.predict(
                    home_team=home_team,
                    away_team=away_team,
                    league="RPL"
                )
                
                if hasattr(result, "__dict__"):
                    result = result.__dict__
                
                pred_uuid = hashlib.md5(
                    f"{home_team}_{away_team}_{self.current_tour}_{self.replay_id}_{datetime.now().isoformat()}".encode()
                ).hexdigest()[:16]
                
                predictions.append({
                    "prediction_id": pred_uuid,
                    "replay_id": self.replay_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "round": fixture.get('round'),
                    "date": fixture.get('date'),
                    "data_cutoff": fixture.get('data_cutoff'),
                    "visibility": fixture.get('visibility', 'before_match'),
                    "model_version": self.model_version,
                    "weights_version": self.weights_version,
                    "passport_version": self.passport_version,
                    "replay_context": {
                        "tour": self._replay_context.get('tour'),
                        "cutoff_date": self._replay_context.get('cutoff_date'),
                        "passports_count": len(self._replay_context.get('passports', {}))
                    },
                    "prediction": result,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"❌ Ошибка прогноза: {e}")
        
        return predictions

    # ============================================================
    # СРАВНЕНИЕ
    # ============================================================

    def _compare_predictions_improved(self, predictions: List[Dict], actual_results: List[Dict]) -> List[Dict]:
        """Улучшенное сравнение прогнозов с фактом"""
        comparison = []
        
        for pred in predictions:
            home_team = pred.get('home_team')
            away_team = pred.get('away_team')
            
            actual = None
            for r in actual_results:
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
            
            score_distance = abs(pred_home_int - actual_home) + abs(pred_away_int - actual_away)
            
            if score_distance == 0:
                score_grade = "EXACT"
                score_points = 3
            elif score_distance == 1:
                score_grade = "DIFFERENCE_1"
                score_points = 1
            else:
                score_grade = "MISS"
                score_points = 0
            
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
            
            pred_btts = pred_data.get('btts', 0)
            actual_btts = 1 if (actual_home > 0 and actual_away > 0) else 0
            
            pred_over25 = pred_data.get('over_2_5', 0)
            actual_total = actual_home + actual_away
            actual_over25 = 1 if actual_total > 2.5 else 0
            
            comparison.append({
                "prediction_id": pred.get('prediction_id'),
                "replay_id": pred.get('replay_id'),
                "home_team": home_team,
                "away_team": away_team,
                "predicted_score": predicted_score,
                "actual_score": actual_score,
                "score_distance": score_distance,
                "score_grade": score_grade,
                "score_points": score_points,
                "predicted_result": pred_result,
                "actual_result": actual_result,
                "result_correct": pred_result == actual_result,
                "xg_home_pred": pred_home,
                "xg_away_pred": pred_away,
                "xg_home_actual": actual.get('home_xg', 0),
                "xg_away_actual": actual.get('away_xg', 0),
                "xg_error": abs(pred_home - actual.get('home_xg', 0)) +
                            abs(pred_away - actual.get('away_xg', 0)),
                "btts_pred": pred_btts,
                "btts_actual": actual_btts,
                "btts_correct": 1 if (pred_btts >= 0.5 and actual_btts == 1) or (pred_btts < 0.5 and actual_btts == 0) else 0,
                "over25_pred": pred_over25,
                "over25_actual": actual_over25,
                "over25_correct": 1 if (pred_over25 >= 0.5 and actual_over25 == 1) or (pred_over25 < 0.5 and actual_over25 == 0) else 0,
                "confidence": pred_data.get('confidence', {}).get('overall', 0),
                "risk": pred_data.get('risk', {}).get('score', 0),
                "model_version": pred.get('model_version'),
                "weights_version": pred.get('weights_version'),
                "passport_version": pred.get('passport_version'),
                "replay_context": pred.get('replay_context')
            })
        
        return comparison

    # ============================================================
    # LEARNING ENGINE
    # ============================================================

    def _run_learning_engine(self, comparison: List[Dict], tour: int) -> Dict:
        """Запуск Learning Engine с корректным подсчётом очков"""
        if not comparison:
            return {"status": "no_data", "tour": tour}
        
        total_matches = len(comparison)
        correct_results = sum(1 for c in comparison if c['result_correct'])
        correct_btts = sum(1 for c in comparison if c['btts_correct'])
        correct_over25 = sum(1 for c in comparison if c['over25_correct'])
        
        total_score_points = sum(c.get('score_points', 0) for c in comparison)
        max_score_points = total_matches * 3
        
        result_accuracy = correct_results / total_matches * 100 if total_matches > 0 else 0
        score_accuracy = total_score_points / max_score_points * 100 if max_score_points > 0 else 0
        btts_accuracy = correct_btts / total_matches * 100 if total_matches > 0 else 0
        over25_accuracy = correct_over25 / total_matches * 100 if total_matches > 0 else 0
        
        total_xg_error = sum(c.get('xg_error', 0) for c in comparison)
        avg_xg_error = total_xg_error / total_matches if total_matches > 0 else 0
        
        exact_count = sum(1 for c in comparison if c.get('score_grade') == 'EXACT')
        diff1_count = sum(1 for c in comparison if c.get('score_grade') == 'DIFFERENCE_1')
        miss_count = sum(1 for c in comparison if c.get('score_grade') == 'MISS')
        
        logger.info(f"📊 Результаты тура {tour}:")
        logger.info(f"   🏆 Исходы: {correct_results}/{total_matches} ({result_accuracy:.1f}%)")
        logger.info(f"   🎯 Счета: {total_score_points}/{max_score_points} ({score_accuracy:.1f}%)")
        logger.info(f"   🎯 EXACT={exact_count}, DIFF_1={diff1_count}, MISS={miss_count}")
        logger.info(f"   ⚽ BTTS: {correct_btts}/{total_matches} ({btts_accuracy:.1f}%)")
        logger.info(f"   📈 Тотал: {correct_over25}/{total_matches} ({over25_accuracy:.1f}%)")
        logger.info(f"   📊 xG Error: {avg_xg_error:.2f}")
        
        return {
            "status": "success",
            "replay_id": self.replay_id,
            "tour": tour,
            "total_matches": total_matches,
            "result_accuracy": round(result_accuracy, 1),
            "score_accuracy": round(score_accuracy, 1),
            "score_points": total_score_points,
            "max_score_points": max_score_points,
            "btts_accuracy": round(btts_accuracy, 1),
            "over25_accuracy": round(over25_accuracy, 1),
            "avg_xg_error": round(avg_xg_error, 3),
            "score_distribution": {
                "exact": exact_count,
                "difference_1": diff1_count,
                "miss": miss_count
            },
            "learning_applied": False
        }

    # ============================================================
    # СОХРАНЕНИЕ
    # ============================================================

    def _save_predictions(self, predictions: List[Dict], tour: int):
        """Сохранение прогнозов в JSON"""
        file_path = self.predictions_dir / f"tour{tour}_predictions.json"
        data = {
            "replay_id": self.replay_id,
            "tour": tour,
            "timestamp": datetime.now().isoformat(),
            "replay_locked": self.guard.is_locked(),
            "model_version": self.model_version,
            "replay_context": {
                "tour": self._replay_context.get('tour'),
                "cutoff_date": self._replay_context.get('cutoff_date'),
                "replay_id": self.replay_id
            },
            "predictions": predictions
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Прогнозы сохранены: {file_path}")

    def _save_comparison(self, comparison: List[Dict], tour: int):
        """Сохранение сравнения в JSON"""
        file_path = self.training_dir / f"comparison_tour{tour}.json"
        data = {
            "replay_id": self.replay_id,
            "tour": tour,
            "timestamp": datetime.now().isoformat(),
            "model_version": self.model_version,
            "comparison": comparison
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Сравнение сохранено: {file_path}")

    def _save_replay_journal(self, tour: int, learning_result: Dict):
        """Сохранение журнала обучения"""
        file_path = self.replay_dir / "replay_log.json"
        
        existing = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except:
                pass
        
        entry = {
            "replay_id": self.replay_id,
            "tour": tour,
            "timestamp": datetime.now().isoformat(),
            "model_version": self.model_version,
            "learning": learning_result
        }
        existing.append(entry)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Журнал обучения сохранён: {file_path}")

    # ============================================================
    # УСИЛЕННЫЙ RUN_SEASON
    # ============================================================

    def run_season(self, tours: List[int]) -> Dict:
        """Запуск полного сезона с корректным подсчётом очков"""
        logger.info(f"🏆 Запуск полного сезона: {len(tours)} туров (ID: {self.replay_id})")
        
        results = {
            "replay_id": self.replay_id,
            "season": "2026/27",
            "league": "РПЛ",
            "model_version": self.model_version,
            "tours_count": len(tours),
            "tours": [],
            "total_matches": 0,
            "total_score_points": 0,
            "total_max_score_points": 0,
            "season_accuracy": {
                "result": 0,
                "score": 0,
                "btts": 0,
                "over25": 0
            },
            "score_distribution": {
                "exact": 0,
                "difference_1": 0,
                "miss": 0
            }
        }
        
        total_matches = 0
        total_result_correct = 0
        total_score_points = 0
        total_max_score_points = 0
        total_btts_correct = 0
        total_over25_correct = 0
        exact_total = 0
        diff1_total = 0
        miss_total = 0
        
        for tour in tours:
            result = self.run_tour(tour)
            results["tours"].append(result)
            
            if result.get("comparison_done", 0) > 0:
                total_matches += result["comparison_done"]
                total_score_points += result.get("score_points", 0)
                total_max_score_points += result.get("max_score_points", 0)
                
                # Собираем статистику из журнала
                journal_path = self.replay_dir / "replay_log.json"
                if journal_path.exists():
                    try:
                        with open(journal_path, 'r', encoding='utf-8') as f:
                            journal = json.load(f)
                        for entry in journal:
                            if entry.get('tour') == tour and entry.get('replay_id') == self.replay_id:
                                learning = entry.get('learning', {})
                                matches = learning.get('total_matches', 0)
                                if matches > 0:
                                    total_result_correct += (learning.get('result_accuracy', 0) * matches) / 100
                                    total_btts_correct += (learning.get('btts_accuracy', 0) * matches) / 100
                                    total_over25_correct += (learning.get('over25_accuracy', 0) * matches) / 100
                                    
                                    dist = learning.get('score_distribution', {})
                                    exact_total += dist.get('exact', 0)
                                    diff1_total += dist.get('difference_1', 0)
                                    miss_total += dist.get('miss', 0)
                                break
                    except:
                        pass
        
        results["total_matches"] = total_matches
        results["total_score_points"] = total_score_points
        results["total_max_score_points"] = total_max_score_points
        
        if total_matches > 0:
            results["season_accuracy"] = {
                "result": round(total_result_correct / total_matches, 1),
                "score": round(total_score_points / total_max_score_points * 100, 1) if total_max_score_points > 0 else 0,
                "btts": round(total_btts_correct / total_matches, 1),
                "over25": round(total_over25_correct / total_matches, 1)
            }
            results["score_distribution"] = {
                "exact": exact_total,
                "difference_1": diff1_total,
                "miss": miss_total
            }
        
        # Сохраняем отчёт
        report_path = self.replay_dir / f"season_report_{self.replay_id}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info("=" * 50)
        logger.info(f"🏆 FAJ SEASON REPORT (ID: {self.replay_id})")
        logger.info(f"📊 Всего матчей: {total_matches}")
        logger.info(f"🎯 Точность исходов: {results['season_accuracy']['result']:.1f}%")
        logger.info(f"🎯 Точность счёта: {results['season_accuracy']['score']:.1f}%")
        logger.info(f"⚽ Точность BTTS: {results['season_accuracy']['btts']:.1f}%")
        logger.info(f"📈 Точность тотала: {results['season_accuracy']['over25']:.1f}%")
        logger.info("=" * 50)
        
        return results


if __name__ == "__main__":
    replay = HistoricalReplay()
    print("🚀 FAJ Historical Replay v1.4")
    print("=" * 40)
    
    result = replay.run_tour(1)
    print(f"✅ Тур 1: {result['status']}")
    print(f"   Replay ID: {result.get('replay_id')}")
