#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Pipeline v1.5

РОЛЬ:
    Главный оркестратор FAJ.
    Управляет последовательностью расчёта прогноза.

PIPELINE:
    1. Input Validation
    2. Load Team Passport
    3. Load Tournament DNA
    4. Calculate FAJ Rating
    5. Calculate Team Strength
    6. XG Model
    7. Poisson Model
    8. Monte Carlo Simulation
    9. Probability Engine
    10. Calibration
    11. Confidence
    12. Risk
    13. Prediction Manager
    14. Streamlit Output

ИЗМЕНЕНИЯ v1.5:
    - Убран Tournament Factor из XG (передаётся как объект)
    - Passport Quality перенесён в Passport Manager
    - Добавлен model_input для обучения
    - Добавлен match_type (league, cup, ucl_group, ucl_playoff, friendly)
    - В model_input добавлен tournament_dna
    - Добавлен passport_status в metadata
=====================================================
"""

import time
import logging
import uuid
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime

from app.config import config
from app.core.match_context import MatchContext
from app.passports.passport_manager import get_team_passport, calculate_faj_rating

from app.models.xg_model import XGModel
from app.models.poisson_model import FAJPoissonModel
from app.models.monte_carlo_model import MonteCarloModel

from app.core.calibration_engine import CalibrationEngine
from app.core.confidence_engine import ConfidenceEngine
from app.core.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class PredictionPipeline:
    VERSION = config.PIPELINE_VERSION

    # Tournament DNA (только как объект, не влияет на xG)
    TOURNAMENT_DNA = {
        "RPL": {
            "goal_factor": 0.95,
            "tempo": 0.90,
            "physicality": 1.05
        },
        "EPL": {
            "goal_factor": 1.05,
            "tempo": 1.10,
            "physicality": 1.00
        },
        "La Liga": {
            "goal_factor": 1.00,
            "tempo": 0.95,
            "technical": 1.10
        },
        "UCL": {
            "goal_factor": 1.05,
            "tempo": 1.00,
            "experience": 1.10
        }
    }

    # Типы матчей
    MATCH_TYPES = ["league", "cup", "ucl_group", "ucl_playoff", "friendly"]

    def __init__(self):
        self.version = self.VERSION

        # Модели
        self.xg_model = XGModel()
        self.poisson_model = FAJPoissonModel(max_goals=config.MAX_GOALS)
        self.monte_carlo_model = MonteCarloModel()

        # Движки
        self.calibration_engine = CalibrationEngine()
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()

        # Диагностика
        self._pipeline_steps = []
        self._last_step_time = None

        logger.info(f"Prediction Pipeline v{self.VERSION} initialized")

    def run(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        match_type: str = "league",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        self._pipeline_steps = []
        self._last_step_time = start_time

        # =========================================================
        # 1. ВАЛИДАЦИЯ
        # =========================================================
        validation_error = self._validate_input(home_team, away_team, league, match_type)
        if validation_error:
            return {"status": "error", "message": validation_error}

        home_team_clean = home_team.strip()
        away_team_clean = away_team.strip()
        league_clean = league.strip() if league else "RPL"
        match_type_clean = match_type.strip() if match_type else "league"

        self._add_step("input_validated")

        try:
            # =========================================================
            # 2. PREDICTION ID
            # =========================================================
            prediction_id = str(uuid.uuid4())
            self._add_step("prediction_id_generated")

            # =========================================================
            # 3. LOAD TEAM PASSPORT
            # =========================================================
            home_passport = get_team_passport(home_team_clean)
            away_passport = get_team_passport(away_team_clean)

            passport_status = {
                "home": "loaded" if home_passport else "not_found",
                "away": "loaded" if away_passport else "not_found"
            }

            if not home_passport or not away_passport:
                missing = [t for t, p in ((home_team_clean, home_passport), (away_team_clean, away_passport)) if not p]
                return {"status": "error", "message": f"Паспорт не найден: {', '.join(missing)}"}

            self._add_step("passport_loaded")

            # =========================================================
            # 4. LOAD TOURNAMENT DNA
            # =========================================================
            tournament_dna = self.TOURNAMENT_DNA.get(league_clean, {})
            self._add_step("tournament_dna_loaded")

            # =========================================================
            # 5. FAJ RATING
            # =========================================================
            home_rating = calculate_faj_rating(home_passport)
            away_rating = calculate_faj_rating(away_passport)
            self._add_step("rating_calculated")

            # =========================================================
            # 6. XG MODEL (без умножения на tournament_factor)
            # =========================================================
            xg_result = self.xg_model.calculate(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating
            )

            home_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("home_xg", config.XG_LEAGUE_MEAN)))
            away_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("away_xg", config.XG_LEAGUE_MEAN)))

            self._add_step("xg_completed")

            # =========================================================
            # 7. POISSON MODEL
            # =========================================================
            poisson_result = self.poisson_model.calculate(home_xg, away_xg, include_matrix=False)
            self._add_step("poisson_completed")

            # =========================================================
            # 8. MONTE CARLO
            # =========================================================
            seed = self._build_seed(
                home_team_clean,
                away_team_clean,
                league_clean,
                home_rating,
                away_rating,
                home_xg,
                away_xg
            )
            mc_result = self.monte_carlo_model.simulate(
                home_xg, away_xg,
                iterations=config.MONTE_CARLO_ITERATIONS,
                seed=seed if config.MONTE_CARLO_REPRODUCIBLE else None
            )
            self._add_step("mc_completed")

            # =========================================================
            # 9. MODEL AGREEMENT
            # =========================================================
            agreement_score = self._calculate_model_agreement(poisson_result, mc_result)
            model_agreement = {
                "score": agreement_score,
                "level": self._agreement_level(agreement_score)
            }
            self._add_step("agreement_calculated")

            # =========================================================
            # 10. RAW PREDICTION
            # =========================================================
            probs = poisson_result.get("result_probability", {})
            raw_prediction = {
                "match": {
                    "home": home_team_clean,
                    "away": away_team_clean,
                    "league": league_clean,
                    "match_type": match_type_clean
                },
                "rating": {
                    "home": home_rating,
                    "away": away_rating
                },
                "xg": {
                    "home": home_xg,
                    "away": away_xg
                },
                "probability": {
                    "home": probs.get("home", config.DEFAULT_HOME_PROB),
                    "draw": probs.get("draw", config.DEFAULT_DRAW_PROB),
                    "away": probs.get("away", config.DEFAULT_AWAY_PROB)
                },
                "score_prediction": {
                    "faj_score": poisson_result.get("most_likely_score", "0:0"),
                    "probability": poisson_result.get("score_probability", 0)
                },
                "btts": poisson_result.get("btts_probability", 0),
                "over_2_5": poisson_result.get("over_2_5", 0),
                "tournament_dna": tournament_dna,
                "context": context.to_dict() if context and hasattr(context, "to_dict") else None
            }
            self._add_step("raw_prediction_built")

            # =========================================================
            # 11. CALIBRATION
            # =========================================================
            calibrated = self.calibration_engine.adjust(raw_prediction)
            self._add_step("calibration_completed")

            # =========================================================
            # 12. CONFIDENCE
            # =========================================================
            confidence_result = self.confidence_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated=calibrated,
                context=context
            )
            self._add_step("confidence_completed")

            # =========================================================
            # 13. RISK
            # =========================================================
            risk_result = self.risk_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated=calibrated,
                confidence=confidence_result,
                context=context
            )
            self._add_step("risk_completed")

            # =========================================================
            # 14. SUMMARY
            # =========================================================
            summary = {
                "home": home_team_clean,
                "away": away_team_clean,
                "score": poisson_result.get("most_likely_score", "0:0"),
                "home_win": probs.get("home", 0),
                "draw": probs.get("draw", 0),
                "away_win": probs.get("away", 0)
            }

            # =========================================================
            # 15. MODEL INPUT (для обучения) С tournament_dna
            # =========================================================
            model_input = {
                "home_rating": home_rating,
                "away_rating": away_rating,
                "home_xg": home_xg,
                "away_xg": away_xg,
                "league": league_clean,
                "match_type": match_type_clean,
                "tournament_dna": tournament_dna
            }

            # =========================================================
            # 16. RESULT
            # =========================================================
            result = {
                "prediction_id": prediction_id,
                "summary": summary,
                "raw_prediction": raw_prediction,
                "calibrated": calibrated,
                "confidence": confidence_result,
                "risk": risk_result,
                "model_agreement": model_agreement,
                "model_input": model_input,
                "metadata": {
                    "pipeline_version": self.VERSION,
                    "platform_version": config.PLATFORM_VERSION,
                    "passport_status": passport_status,
                    "season_phase": self._get_season_phase(),
                    "tournament_dna": tournament_dna,
                    "processing_time_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    "stages": self._pipeline_steps,
                    "timestamp": datetime.now().isoformat()
                }
            }

            self._add_step("pipeline_completed")
            result["metadata"]["stages"] = self._pipeline_steps

            return result

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _add_step(self, step: str) -> None:
        current_time = time.perf_counter()
        duration_ms = 0
        if self._last_step_time is not None:
            duration_ms = round((current_time - self._last_step_time) * 1000, 2)
        self._pipeline_steps.append({"step": step, "duration_ms": duration_ms})
        self._last_step_time = current_time

    def _validate_input(
        self,
        home: str,
        away: str,
        league: str,
        match_type: str
    ) -> Optional[str]:
        home = home.strip() if home else ""
        away = away.strip() if away else ""
        league = league.strip() if league else ""
        match_type = match_type.strip() if match_type else ""

        if not home:
            return "Не указана команда хозяев"
        if not away:
            return "Не указана команда гостей"
        if home.lower() == away.lower():
            return "Команды не могут быть одинаковыми"
        if not league:
            return "Не указана лига"
        if match_type and match_type not in self.MATCH_TYPES:
            return f"Некорректный тип матча: {match_type}. Доступные: {', '.join(self.MATCH_TYPES)}"
        return None

    def _build_seed(
        self,
        home: str,
        away: str,
        league: str,
        home_rating: float,
        away_rating: float,
        home_xg: float,
        away_xg: float
    ) -> int:
        key = (
            f"{home}_{away}_{league}_"
            f"{self.VERSION}_"
            f"{home_rating:.1f}_{away_rating:.1f}_"
            f"{home_xg:.2f}_{away_xg:.2f}_"
            f"{config.SEASON_START}"
        )
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def _get_season_phase(self) -> str:
        today = datetime.now()
        season_start = datetime.strptime(config.SEASON_START, "%Y-%m-%d")
        days = (today - season_start).days

        if days < 30:
            return "start"
        elif days < 90:
            return "early"
        elif days < 210:
            return "mid"
        else:
            return "end"

    def _calculate_model_agreement(
        self,
        poisson_result: Dict[str, Any],
        mc_result: Dict[str, Any]
    ) -> float:
        p = poisson_result.get("result_probability", {})
        m = mc_result

        diff = (
            abs(p.get("home", config.DEFAULT_HOME_PROB) - m.get("home_win", config.DEFAULT_HOME_PROB)) +
            abs(p.get("draw", config.DEFAULT_DRAW_PROB) - m.get("draw", config.DEFAULT_DRAW_PROB)) +
            abs(p.get("away", config.DEFAULT_AWAY_PROB) - m.get("away_win", config.DEFAULT_AWAY_PROB))
        )

        agreement = round(1 - diff / 3, 4)
        return max(0.0, min(1.0, agreement))

    def _agreement_level(self, value: float) -> str:
        if value >= 0.85:
            return "HIGH"
        elif value >= 0.65:
            return "MEDIUM"
        else:
            return "LOW"

    # ============================================================
    # STATUS
    # ============================================================

    def status(self) -> Dict[str, Any]:
        return {
            "pipeline": "Prediction Pipeline",
            "version": self.VERSION,
            "status": "READY",
            "tournaments": list(self.TOURNAMENT_DNA.keys()),
            "match_types": self.MATCH_TYPES,
            "models": {
                "xg": self.xg_model.VERSION,
                "poisson": self.poisson_model.VERSION,
                "monte_carlo": self.monte_carlo_model.VERSION
            },
            "modules": {
                "calibration": self.calibration_engine.VERSION,
                "confidence": self.confidence_engine.VERSION,
                "risk": self.risk_engine.VERSION
            }
        }
