#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Pipeline v1.2

РОЛЬ:
    Главный оркестратор FAJ.
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
from app.core.rating_engine import RatingEngine
from app.core.agreement_engine import AgreementEngine
from app.core.prediction_builder import PredictionBuilder
from app.services.prediction_repository import PredictionRepository
from app.passports.passport_manager import get_team_passport

from app.models.xg_model import XGModel
from app.models.poisson_model import FAJPoissonModel
from app.models.monte_carlo_model import MonteCarloModel

from app.core.calibration_engine import CalibrationEngine
from app.core.confidence_engine import ConfidenceEngine
from app.core.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class PredictionPipeline:
    VERSION = config.PIPELINE_VERSION

    def __init__(self, save_enabled: bool = True, db_connection=None):
        self.version = self.VERSION

        self.xg_model = XGModel()
        self.poisson_model = FAJPoissonModel(max_goals=config.MAX_GOALS)
        self.monte_carlo_model = MonteCarloModel()

        self.rating_engine = RatingEngine()
        self.agreement_engine = AgreementEngine()
        self.builder = PredictionBuilder()
        self.repository = PredictionRepository(db_connection=db_connection, save_enabled=save_enabled)

        self.calibration_engine = CalibrationEngine()
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()

        self._pipeline_steps = []
        self._last_step_time = None

        logger.info(f"Prediction Pipeline v{self.VERSION} initialized")

    def run(
        self,
        home_team: str,
        away_team: str,
        league: str = "RPL",
        context: Optional[MatchContext] = None
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        self._pipeline_steps = []
        self._last_step_time = start_time

        validation_error = self._validate_input(home_team, away_team, league)
        if validation_error:
            return {"status": "error", "message": validation_error}

        self._add_step("input_validated")

        try:
            prediction_id = str(uuid.uuid4())
            self._add_step("prediction_id_generated")

            home_passport = get_team_passport(home_team)
            away_passport = get_team_passport(away_team)

            if not home_passport or not away_passport:
                missing = [t for t, p in ((home_team, home_passport), (away_team, away_passport)) if not p]
                return {"status": "error", "message": f"Паспорт не найден: {', '.join(missing)}"}

            self._add_step("passport_loaded")

            home_rating = self.rating_engine.calculate(home_passport)
            away_rating = self.rating_engine.calculate(away_passport)
            self._add_step("rating_calculated")

            xg_result = self.xg_model.calculate(home_passport, away_passport, home_rating, away_rating)
            home_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("home_xg", config.XG_LEAGUE_MEAN)))
            away_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("away_xg", config.XG_LEAGUE_MEAN)))
            self._add_step("xg_completed")

            poisson_result = self.poisson_model.calculate(home_xg, away_xg, include_matrix=False)
            self._add_step("poisson_completed")

            seed = self._build_seed(home_team, away_team, league)
            mc_result = self.monte_carlo_model.simulate(
                home_xg, away_xg,
                iterations=config.MONTE_CARLO_ITERATIONS,
                seed=seed if config.MONTE_CARLO_REPRODUCIBLE else None
            )
            self._add_step("mc_completed")

            model_agreement = self.agreement_engine.calculate(poisson_result, mc_result)
            self._add_step("agreement_calculated")

            probs = poisson_result.get("result_probability", {})
            raw_prediction = {
                "match": {"home": home_team, "away": away_team, "league": league},
                "rating": {"home": home_rating, "away": away_rating},
                "xg": {"home": home_xg, "away": away_xg},
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
                "context": context.to_dict() if context and hasattr(context, "to_dict") else None
            }
            self._add_step("raw_prediction_built")

            calibrated = self.calibration_engine.adjust(raw_prediction)
            self._add_step("calibration_completed")

            confidence_result = self.confidence_engine.calculate(raw_prediction, calibrated, context)
            self._add_step("confidence_completed")

            risk_result = self.risk_engine.calculate(raw_prediction, calibrated, confidence_result, context)
            self._add_step("risk_completed")

            result = self.builder.build(
                prediction_id=prediction_id,
                raw_prediction=raw_prediction,
                calibrated=calibrated,
                confidence=confidence_result,
                risk=risk_result,
                model_agreement=model_agreement,
                pipeline_version=self.VERSION,
                platform_version=config.PLATFORM_VERSION,
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
                stages=self._pipeline_steps
            )

            self._add_step("pipeline_completed")
            result["metadata"]["stages"] = self._pipeline_steps

            if config.SAVE_TO_GOLD_DATASET:
                self.repository.save(result)

            return result

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _add_step(self, step: str) -> None:
        current_time = time.perf_counter()
        duration_ms = 0
        if self._last_step_time is not None:
            duration_ms = round((current_time - self._last_step_time) * 1000, 2)
        self._pipeline_steps.append({"step": step, "duration_ms": duration_ms})
        self._last_step_time = current_time

    def _validate_input(self, home: str, away: str, league: str) -> Optional[str]:
        if not home:
            return "Не указана команда хозяев"
        if not away:
            return "Не указана команда гостей"
        if home.lower() == away.lower():
            return "Команды не могут быть одинаковыми"
        if not league:
            return "Не указана лига"
        return None

    def _build_seed(self, home: str, away: str, league: str) -> int:
        key = f"{home}_{away}_{league}_{self.VERSION}"
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def status(self) -> Dict[str, Any]:
        return {
            "pipeline": "Prediction Pipeline",
            "version": self.VERSION,
            "status": "READY",
            "models": {
                "xg": self.xg_model.VERSION,
                "poisson": self.poisson_model.VERSION,
                "monte_carlo": self.monte_carlo_model.VERSION
            }
        }
