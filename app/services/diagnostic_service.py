#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Diagnostic Service

Централизованная диагностика всех компонентов.
=====================================================
"""

import json
import time
import math
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

from app.database import FAJDatabase
from app.passports.passport_manager import get_passport_manager
from app.core.prediction_pipeline import PredictionPipeline
from app.prediction.prediction_manager import get_prediction_manager
from app.config import config

# psutil опционально
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class Check:
    """Регистрация проверки"""
    name: str
    func: Callable
    severity: str = "major"  # critical, major, minor, info


class DiagnosticService:
    """
    Diagnostic Service v1.0
    """

    VERSION = "1.0"

    # Состояния системы
    STATUS_LEVELS = {
        "healthy": {"icon": "🟢", "label": "Healthy", "score": 100},
        "warning": {"icon": "🟡", "label": "Warning", "score": 70},
        "degraded": {"icon": "🟠", "label": "Degraded", "score": 40},
        "critical": {"icon": "🔴", "label": "Critical", "score": 0}
    }

    # Штрафы для warn в зависимости от severity
    WARN_PENALTIES = {
        "critical": 0.3,
        "major": 0.6,
        "minor": 0.8,
        "info": 0.9
    }

    def __init__(self, deep_check: bool = False):
        self._cached_result: Optional[Dict[str, Any]] = None
        self.db = FAJDatabase()
        self.deep_check = deep_check
        self._save_counter = 0

        # Реестр проверок (веса берутся из config)
        self._checks: List[Check] = [
            Check("Database", self._check_database, "critical"),
            Check("Passports", self._check_passports, "major"),
            Check("Pipeline", self._check_pipeline, "major"),
            Check("Prediction", self._check_prediction, "critical"),
            Check("Learning", self._check_learning, "minor"),
            Check("Performance", self._check_performance, "minor"),
            Check("Versions", self._check_versions, "info"),
        ]

    # ============================================================
    # PUBLIC API
    # ============================================================

    def run_all(self, save_history: bool = True) -> Dict[str, Any]:
        self._cached_result = None
        results = []
        start_time = time.time()

        for check in self._checks:
            try:
                results.append(check.func())
            except Exception as e:
                results.append({
                    "name": check.name,
                    "status": "fail",
                    "severity": check.severity,
                    "duration_ms": 0,
                    "error": str(e)
                })

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

    def check_performance(self) -> Dict[str, Any]:
        return self._check_performance()

    def check_versions(self) -> Dict[str, Any]:
        return self._check_versions()

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.db.get_diagnostics(limit)

    def get_health_score(self) -> Dict[str, Any]:
        if self._cached_result:
            result = self._cached_result
        else:
            result = self.run_all(save_history=False)

        summary = result.get("summary", {})
        passed = summary.get("passed", 0)
        warned = summary.get("warned", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 1)

        total_weight = 0
        weighted_score = 0

        for check in result.get("checks", []):
            name = check.get("name", "Unknown")
            status = check.get("status", "fail")
            severity = check.get("severity", "minor")
            weight = config.DIAGNOSTIC_WEIGHTS.get(name, 1)

            total_weight += weight
            if status == "pass":
                weighted_score += weight * 1.0
            elif status == "warn":
                penalty = self.WARN_PENALTIES.get(severity, 0.6)
                weighted_score += weight * penalty
            elif status == "info":
                weighted_score += weight * 0.9
            # fail = 0

        final_score = round(weighted_score / total_weight * 100, 1) if total_weight > 0 else 0

        critical_fail = summary.get("critical_fail", 0)
        if critical_fail > 0:
            status = "critical"
        elif failed > 0:
            status = "degraded"
        elif warned > 0:
            status = "warning"
        else:
            status = "healthy"

        return {
            "score": final_score,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "total": total,
            "critical_fail": critical_fail,
            "status": status,
            "status_icon": self.STATUS_LEVELS.get(status, {}).get("icon", "⚪"),
            "status_label": self.STATUS_LEVELS.get(status, {}).get("label", "Unknown"),
            "timestamp": result.get("timestamp")
        }

    def export_json(self) -> str:
        """Экспорт отчёта в JSON"""
        result = self.run_all(save_history=False)
        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    def export_html(self) -> str:
        """Экспорт отчёта в HTML"""
        result = self.run_all(save_history=False)

        html = """
        <html>
        <head>
            <title>FAJ Diagnostic Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                .status { font-weight: bold; }
                .pass { color: green; }
                .warn { color: orange; }
                .fail { color: red; }
                .info { color: blue; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
            </style>
        </head>
        <body>
            <h1>FAJ Diagnostic Report</h1>
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>Status:</strong> <span class="status {status}">{status}</span></p>
            <p><strong>Elapsed:</strong> {elapsed}s</p>
            <h2>Checks</h2>
            <table>
                <tr>
                    <th>Component</th>
                    <th>Status</th>
                    <th>Severity</th>
                    <th>Duration (ms)</th>
                    <th>Details</th>
                </tr>
                {rows}
            </table>
        </body>
        </html>
        """

        rows = ""
        for check in result.get("checks", []):
            name = check.get("name", "Unknown")
            status = check.get("status", "unknown")
            severity = check.get("severity", "info")
            duration = check.get("duration_ms", 0)
            error = check.get("error", "")
            details = check.get("details", {})

            detail_str = ", ".join(f"{k}: {v}" for k, v in details.items() if v)
            if error:
                detail_str = f"ERROR: {error}"

            rows += f"""
                <tr>
                    <td>{name}</td>
                    <td class="{status}">{status}</td>
                    <td>{severity}</td>
                    <td>{duration:.1f}</td>
                    <td>{detail_str}</td>
                </tr>
            """

        return html.format(
            timestamp=result.get("timestamp", ""),
            status=result.get("summary", {}).get("status", "unknown"),
            elapsed=result.get("elapsed_seconds", 0),
            rows=rows
        )

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _check_database(self) -> Dict[str, Any]:
        start = time.time()
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Определяем тип БД
            db_type = "sqlite"
            try:
                cursor.execute("SELECT version()")
                db_type = "postgresql"
            except:
                pass

            # Получаем список таблиц
            if db_type == "sqlite":
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
            else:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
                tables = [row[0] for row in cursor.fetchall()]

            conn.close()

            status = self.db.get_status()

            # Проверка записи (только при deep_check)
            if self.deep_check:
                test_id = self.db.save_diagnostic({
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_seconds": 0,
                    "passed": 1,
                    "warned": 0,
                    "failed": 0,
                    "total": 1,
                    "critical_fail": 0,
                    "status": "test",
                    "details_json": "{}"
                })
                if test_id and test_id > 0:
                    conn = self.db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM diagnostic_history WHERE id = ?", (test_id,))
                    conn.commit()
                    conn.close()

            return {
                "name": "Database",
                "status": "pass",
                "severity": "critical",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "type": db_type,
                    "tables": len(tables),
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

            required_fields = ["attack", "defense", "control", "tempo", "coach", "form"]

            found = 0
            ratings = []
            missing = []
            incomplete = []
            old_passports = []

            for team in team_names:
                passport = pm.get_current_passport_by_name(team)
                if passport:
                    found += 1
                    rating = pm.calculate_rating(passport)
                    ratings.append(rating)

                    missing_fields = [f for f in required_fields if passport.get(f) is None]
                    if missing_fields:
                        incomplete.append(f"{team} ({', '.join(missing_fields)})")

                    if "updated_at" in passport:
                        try:
                            updated = datetime.fromisoformat(passport["updated_at"])
                            if (datetime.now() - updated).days > 14:
                                old_passports.append(team)
                        except:
                            pass
                else:
                    missing.append(team)

            avg_rating = sum(ratings) / len(ratings) if ratings else 0

            status = "pass"
            if missing:
                status = "warn"
            elif incomplete:
                status = "warn"
            elif old_passports:
                status = "warn"

            return {
                "name": "Passports",
                "status": status,
                "severity": "major",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "found": found,
                    "total": len(team_names),
                    "avg_rating": round(avg_rating, 1),
                    "missing": missing[:5] if missing else None,
                    "incomplete": incomplete[:3] if incomplete else None,
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

            test_matches = config.DIAGNOSTIC_TEST_MATCHES

            passed_matches = 0
            issues = []
            total_time = 0

            for home, away in test_matches:
                home_passport = pm.get_current_passport_by_name(home)
                away_passport = pm.get_current_passport_by_name(away)

                if not home_passport or not away_passport:
                    issues.append(f"{home}-{away}: паспорт не найден")
                    continue

                home_rating = pm.calculate_rating(home_passport)
                away_rating = pm.calculate_rating(away_passport)

                if math.isnan(home_rating) or math.isnan(away_rating):
                    issues.append(f"{home}-{away}: NaN в рейтинге")
                    continue

                match_start = time.time()
                result = pipeline.run(
                    home_passport=home_passport,
                    away_passport=away_passport,
                    home_rating=home_rating,
                    away_rating=away_rating,
                    home_team=home,
                    away_team=away
                )
                match_time = (time.time() - match_start) * 1000
                total_time += match_time

                if result.get("status") == "error":
                    issues.append(f"{home}-{away}: {result.get('message')}")
                    continue

                probs = result.get("probability", {})
                total_prob = probs.get("home", 0) + probs.get("draw", 0) + probs.get("away", 0)

                xg = result.get("xg", {})
                home_xg = xg.get("home", 0)
                away_xg = xg.get("away", 0)

                confidence = result.get("confidence", {})
                overall = confidence.get("overall", 0)

                errors = []
                if not (0.99 <= total_prob <= 1.01):
                    errors.append(f"сумма={total_prob:.3f}")
                if not (0.1 <= home_xg <= 4.0):
                    errors.append(f"xG_home={home_xg:.2f}")
                if not (0.1 <= away_xg <= 4.0):
                    errors.append(f"xG_away={away_xg:.2f}")
                if not (0 <= overall <= 1):
                    errors.append(f"confidence={overall:.2f}")
                if math.isnan(home_xg) or math.isnan(away_xg):
                    errors.append("NaN в xG")

                if errors:
                    issues.append(f"{home}-{away}: {', '.join(errors)}")
                else:
                    passed_matches += 1

            avg_time = total_time / len(test_matches) if test_matches else 0

            status = "pass"
            if passed_matches >= 2:
                status = "pass"
            elif passed_matches >= 1:
                status = "warn"
            else:
                status = "fail"

            if avg_time > 5000:
                status = "warn" if status == "pass" else status

            return {
                "name": "Pipeline",
                "status": status,
                "severity": "major",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "passed": passed_matches,
                    "total": len(test_matches),
                    "avg_time_ms": round(avg_time, 1),
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

            required_fields = ["score", "xg", "probability", "confidence"]
            missing = [f for f in required_fields if f not in prediction]

            if missing:
                return {
                    "name": "Prediction",
                    "status": "warn",
                    "severity": "critical",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": f"Отсутствуют поля: {', '.join(missing)}"
                }

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
                "status": "info",
                "severity": "info",
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

    def _check_performance(self) -> Dict[str, Any]:
        start = time.time()
        try:
            if not PSUTIL_AVAILABLE:
                return {
                    "name": "Performance",
                    "status": "info",
                    "severity": "info",
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "details": {"message": "psutil not installed"}
                }

            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=0.5)

            status = "pass"
            issues = []

            if mem.percent > 90:
                issues.append(f"RAM: {mem.percent}%")
                status = "warn"
            if cpu > 80:
                issues.append(f"CPU: {cpu}%")
                status = "warn"

            return {
                "name": "Performance",
                "status": status,
                "severity": "minor",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": {
                    "ram_percent": mem.percent,
                    "ram_available_gb": round(mem.available / (1024**3), 1),
                    "cpu_percent": cpu,
                    "issues": issues if issues else None
                }
            }
        except Exception as e:
            return {
                "name": "Performance",
                "status": "info",
                "severity": "info",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _check_versions(self) -> Dict[str, Any]:
        start = time.time()
        try:
            from app.config import config as cfg

            versions = {
                "platform": getattr(cfg, "PLATFORM_VERSION", "unknown"),
                "core": getattr(cfg, "CORE_VERSION", "unknown"),
                "pipeline": getattr(cfg, "PIPELINE_VERSION", "unknown"),
                "model": getattr(cfg, "MODEL_VERSION", "unknown"),
                "passport": getattr(cfg, "PASSPORT_VERSION", "unknown"),
                "schema": self.db.get_status().get("schema_version", "unknown")
            }

            return {
                "name": "Versions",
                "status": "pass",
                "severity": "info",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "details": versions
            }
        except Exception as e:
            return {
                "name": "Versions",
                "status": "info",
                "severity": "info",
                "duration_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)
            }

    def _get_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        passed = sum(1 for r in results if r.get("status") == "pass")
        warned = sum(1 for r in results if r.get("status") == "warn")
        failed = sum(1 for r in results if r.get("status") == "fail")
        info = sum(1 for r in results if r.get("status") == "info")
        total = len(results)
        critical_fail = sum(1 for r in results if r.get("status") == "fail" and r.get("severity") == "critical")

        return {
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "info": info,
            "total": total,
            "critical_fail": critical_fail,
            "status": "critical" if critical_fail > 0 else "degraded" if failed > 0 else "warning" if warned > 0 else "healthy"
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

            # Ограничиваем историю каждые 100 сохранений
            self._save_counter += 1
            if self._save_counter >= 100:
                self._save_counter = 0
                conn = self.db.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM diagnostic_history
                    WHERE id NOT IN (
                        SELECT id FROM diagnostic_history
                        ORDER BY id DESC
                        LIMIT 1000
                    )
                """)
                conn.commit()
                conn.close()

        except Exception as e:
            print(f"Save history error: {e}")


# ============================================================
# SINGLETON
# ============================================================

_default_service: Optional[DiagnosticService] = None


def get_diagnostic_service(deep_check: bool = False) -> DiagnosticService:
    global _default_service
    if _default_service is None:
        _default_service = DiagnosticService(deep_check)
    return _default_service
