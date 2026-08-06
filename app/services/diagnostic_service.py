#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Diagnostic Service

Централизованная диагностика всех компонентов.
История хранится в БД.
=====================================================
"""

import json
import time
import math
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.database import FAJDatabase
from app.passports.passport_manager import get_passport_manager
from app.core.prediction_pipeline import PredictionPipeline
from app.prediction.prediction_manager import get_prediction_manager
from app.config import config


class DiagnosticService:
    """
    Diagnostic Service v1.0
    """

    VERSION = "1.0"

    def __init__(self):
        self._cached_result: Optional[Dict[str, Any]] = None
        self.db = FAJDatabase()
        self.weights = config.DIAGNOSTIC_WEIGHTS

    # ============================================================
    # PUBLIC API
    # ============================================================

    def run_all(self, save_history: bool = True) -> Dict[str, Any]:
        self._cached_result = None
        results = []
        start_time = time.time()

        results.append(self._check_database())
        results.append(self._check_passports())
        results.append(self._check_pipeline())
        results.append(self._check_prediction())
        results.append(self._check_learning())

        elapsed = time.time() - start_time

        result = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "checks": results,
            "summary": self._get_summary(results)
        }

        self._cached_result = result

        if save_history:
            self._save_history(result)

        return result

    def get_cached_result(self) -> Optional[Dict[str, Any]]:
        return self._cached_result

    def check_database(self) -> Dict[str, Any]:
        return self._check_database()

    def check_passports(self) -> Dict[str, Any]:
        return self._check_passports()

    def check_pipeline(self) -> Dict[str, Any]:
        return self._check_pipeline()

    def check_prediction(self) -> Dict[str, Any]:
        return self._check_prediction()

    def check_learning(self) -> Dict[str, Any]:
        return self._check_learning()

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.db.get_diagnostics(limit)

    def get_health_score(self) -> Dict[str, Any]:
        if self._cached_result:
            result = self._cached_result
        else:
            result = self.run_all(save_history=False)

        summary = result.get("summary", {})
        passed = summary.get("passed", 0)
        total = summary.get("total", 1)

        total_weight = 0
        weighted_passed = 0

        for check in result.get("checks", []):
            name = check.get("name", "Unknown")
            status = check.get("status", "fail")
            severity = check.get("severity", "minor")

            weight = self.weights.get(name, 1)

            total_weight += weight
            if status == "pass":
                weighted_passed += weight
            elif status == "warn":
                weighted_passed += weight * 0.5

        weighted_score = round(weighted_passed / total_weight * 100, 1) if total_weight > 0 else 0

        return {
            "score": weighted_score,
            "raw_score": round(passed / total * 100, 1) if total > 0 else 0,
            "passed": passed,
            "total": total,
            "status": "healthy" if passed == total else "degraded",
            "timestamp": result.get("timestamp")
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _check_database(self) -> Dict[str, Any]:
        start = time.time()
        try:
            db = FAJDatabase()
            status = db.get_status()

            return {
                "name": "Database",
                "status": "pass",
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "tables": len(status.get("tables", {})),
                    "schema": status.get("schema_version", "N/A"),
                    "status": status.get("status", "UNKNOWN")
                }
            }
        except Exception as e:
            return {
                "name": "Database",
                "status": "fail",
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _check_passports(self) -> Dict[str, Any]:
        start = time.time()
        try:
            pm = get_passport_manager()
            teams = self.db.get_teams()
            team_names = [team["name"] for team in teams] if teams else ["Зенит", "Спартак"]

            found = 0
            ratings = []
            missing = []
            old_passports = []

            for team in team_names:
                passport = pm.get_current_passport_by_name(team)
                if passport:
                    found += 1
                    rating = pm.calculate_rating(passport)
                    ratings.append(rating)

                    # Проверка свежести
                    if "created_at" in passport:
                        try:
                            created = datetime.fromisoformat(passport["created_at"])
                            if (datetime.now() - created).days > 14:
                                old_passports.append(team)
                        except:
                            pass
                else:
                    missing.append(team)

            avg_rating = sum(ratings) / len(ratings) if ratings else 0

            status = "pass" if found == len(team_names) else "warn"

            return {
                "name": "Passports",
                "status": status,
                "severity": "major",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "found": found,
                    "total": len(team_names),
                    "avg_rating": round(avg_rating, 1),
                    "missing": missing[:5],
                    "old_passports": old_passports[:5] if old_passports else None
                }
            }
        except Exception as e:
            return {
                "name": "Passports",
                "status": "fail",
                "severity": "major",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _check_pipeline(self) -> Dict[str, Any]:
        start = time.time()
        try:
            pm = get_passport_manager()
            pipeline = PredictionPipeline()

            home_passport = pm.get_current_passport_by_name("Зенит")
            away_passport = pm.get_current_passport_by_name("Спартак")

            if not home_passport or not away_passport:
                return {
                    "name": "Pipeline",
                    "status": "fail",
                    "severity": "critical",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": "Паспорт не найден"
                }

            home_rating = pm.calculate_rating(home_passport)
            away_rating = pm.calculate_rating(away_passport)

            # Проверка NaN
            if math.isnan(home_rating) or math.isnan(away_rating):
                return {
                    "name": "Pipeline",
                    "status": "fail",
                    "severity": "critical",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": "Rating содержит NaN"
                }

            result = pipeline.run(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating,
                home_team="Зенит",
                away_team="Спартак"
            )

            if result.get("status") == "error":
                return {
                    "name": "Pipeline",
                    "status": "fail",
                    "severity": "critical",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": result.get("message")
                }

            probs = result.get("probability", {})
            total_prob = probs.get("home", 0) + probs.get("draw", 0) + probs.get("away", 0)

            home_xg = result.get("xg", {}).get("home", 0)
            away_xg = result.get("xg", {}).get("away", 0)

            confidence = result.get("confidence", {})
            overall = confidence.get("overall", 0)

            issues = []

            if not (0.99 <= total_prob <= 1.01):
                issues.append(f"Сумма вероятностей = {total_prob:.3f}")
            if not (0.1 <= home_xg <= 4.0):
                issues.append(f"xG хозяев = {home_xg:.2f}")
            if not (0.1 <= away_xg <= 4.0):
                issues.append(f"xG гостей = {away_xg:.2f}")
            if not (0 <= overall <= 1):
                issues.append(f"Confidence = {overall:.2f}")
            if not (0 <= home_rating <= 100):
                issues.append(f"Rating хозяев = {home_rating:.1f}")
            if not (0 <= away_rating <= 100):
                issues.append(f"Rating гостей = {away_rating:.1f}")

            status = "pass" if not issues else "warn"

            return {
                "name": "Pipeline",
                "status": status,
                "severity": "major",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "score": result.get("score", "N/A"),
                    "confidence": round(overall * 100, 1),
                    "issues": issues if issues else None
                }
            }
        except Exception as e:
            return {
                "name": "Pipeline",
                "status": "fail",
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _check_prediction(self) -> Dict[str, Any]:
        start = time.time()
        try:
            pm = get_prediction_manager()

            result = pm.predict("Зенит", "Спартак", "RPL")

            if result.get("status") == "error":
                return {
                    "name": "Prediction",
                    "status": "fail",
                    "severity": "critical",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": result.get("message")
                }

            prediction = result.get("prediction", {}) or result

            # Проверка сохранения
            prediction_id = prediction.get("prediction_id", "")
            saved = False

            if prediction_id and config.SAVE_TO_GOLD_DATASET:
                saved = self.db.prediction_exists(prediction_id)

            status = "pass"
            if config.SAVE_TO_GOLD_DATASET:
                status = "pass" if saved else "warn"

            return {
                "name": "Prediction",
                "status": status,
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "score": prediction.get("score", "N/A"),
                    "confidence": round(prediction.get("confidence", {}).get("overall", 0) * 100, 1),
                    "saved_to_db": saved
                }
            }
        except Exception as e:
            return {
                "name": "Prediction",
                "status": "fail",
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _check_learning(self) -> Dict[str, Any]:
        start = time.time()
        try:
            from app.learning.learning_engine import get_learning_engine

            engine = get_learning_engine()
            status = engine.get_learning_status()

            return {
                "name": "Learning",
                "status": "pass",
                "severity": "minor",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "gold_dataset": status.get("gold_dataset", 0),
                    "learning_records": status.get("learning_records", 0),
                    "critical_errors": status.get("critical_errors", 0)
                }
            }
        except ImportError:
            return {
                "name": "Learning",
                "status": "warn",
                "severity": "minor",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {"message": "Learning Engine not installed"}
            }
        except Exception as e:
            return {
                "name": "Learning",
                "status": "warn",
                "severity": "minor",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _get_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        passed = sum(1 for r in results if r.get("status") == "pass")
        warned = sum(1 for r in results if r.get("status") == "warn")
        failed = sum(1 for r in results if r.get("status") == "fail")
        total = len(results)
        critical_fail = sum(1 for r in results if r.get("status") == "fail" and r.get("severity") == "critical")

        return {
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "total": total,
            "critical_fail": critical_fail,
            "status": "healthy" if failed == 0 else "degraded"
        }

    def _save_history(self, result: Dict[str, Any]):
        try:
            summary = result.get("summary", {})
            details_json = json.dumps(result.get("checks", []), ensure_ascii=False, default=str)

            self.db.save_diagnostic({
                "timestamp": result.get("timestamp"),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "passed": summary.get("passed", 0),
                "warned": summary.get("warned", 0),
                "failed": summary.get("failed", 0),
                "total": summary.get("total", 0),
                "critical_fail": summary.get("critical_fail", 0),
                "status": summary.get("status", "unknown"),
                "details_json": details_json
            })

        except Exception as e:
            print(f"Save history error: {e}")


# ============================================================
# SINGLETON
# ============================================================

_default_service: Optional[DiagnosticService] = None


def get_diagnostic_service() -> DiagnosticService:
    global _default_service
    if _default_service is None:
        _default_service = DiagnosticService()
    return _default_service
