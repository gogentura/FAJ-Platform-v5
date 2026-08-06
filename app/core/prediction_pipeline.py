#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Pipeline v1.9

РОЛЬ:
    Математический двигатель FAJ.
    Только расчёт. Никакой БД.

ВХОД:
    home_passport: Dict — паспорт хозяев (уже загружен)
    away_passport: Dict — паспорт гостей (уже загружен)
    home_rating: float — рейтинг хозяев
    away_rating: float — рейтинг гостей
    home_team: str — название хозяев (для вывода)
    away_team: str — название гостей (для вывода)
    league: str — лига (для журнала, по умолчанию "RPL")

ПРОЦЕСС:
    1. XG Model
    2. Poisson Model
    3. Monte Carlo
    4. Calibration
    5. Confidence
    6. Risk

ВЫХОД:
    {
        "status": "success",
        "prediction_id": str,
        "score": str,
        "score_probability": float,
        "xg": {"home": float, "away": float},
        "probability": {"home": float, "draw": float, "away": float},
        "btts": float,
        "over_2_5": float,
        "confidence": {"overall": float, "level": str},
        "risk": {"score": float, "level": str},
        "model_agreement": {"score": float, "level": str},
        "version": str,
        "processing_time_ms": float
    }
=====================================================
"""

import time
import logging
import hashlib
import uuid
from typing import Dict, Any

from app.config import config
from app.core.calibration_engine import CalibrationEngine
from app.core.confidence_engine import ConfidenceEngine
from app.core.risk_engine import RiskEngine

from app.models.xg_model import XGModel
from app.models.poisson_model import FAJPoissonModel
from app.models.monte_carlo_model import MonteCarloModel

logger = logging.getLogger(__name__)


class PredictionPipeline:
    """
    Prediction Pipeline v1.9
    Математический двигатель FAJ
    """

    VERSION = config.PIPELINE_VERSION

    def __init__(self):
        self.version = self.VERSION

        self.xg_model = XGModel()
        self.poisson_model = FAJPoissonModel(max_goals=config.MAX_GOALS)
        self.monte_carlo_model = MonteCarloModel()

        self.calibration_engine = CalibrationEngine()
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()

        logger.info(f"Prediction Pipeline v{self.VERSION} initialized")

    def run(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float,
        away_rating: float,
        home_team: str = "",
        away_team: str = "",
        league: str = "RPL"
    ) -> Dict[str, Any]:
        """
        Запуск вычислительного конвейера
        """
        start_time = time.perf_counter()
        prediction_id = str(uuid.uuid4())[:8]

        try:
            # =========================================================
            # 1. XG MODEL
            # =========================================================
            xg_result = self.xg_model.calculate(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating
            )

            home_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("home_xg", config.XG_LEAGUE_MEAN)))
            away_xg = max(config.XG_MIN, min(config.XG_MAX, xg_result.get("away_xg", config.XG_LEAGUE_MEAN)))

            # =========================================================
            # 2. POISSON MODEL
            # =========================================================
            poisson_result = self.poisson_model.calculate(home_xg, away_xg, include_matrix=False)
            probs = poisson_result.get("result_probability", {})

            # =========================================================
            # 3. MONTE CARLO
            # =========================================================
            seed = self._build_seed(home_team, away_team, home_rating, away_rating, home_xg, away_xg)
            mc_result = self.monte_carlo_model.simulate(
                home_xg, away_xg,
                iterations=config.MONTE_CARLO_ITERATIONS,
                seed=seed if config.MONTE_CARLO_REPRODUCIBLE else None
            )

            # =========================================================
            # 4. MODEL AGREEMENT
            # =========================================================
            agreement_score = self._calculate_model_agreement(poisson_result, mc_result)
            model_agreement = {
                "score": round(agreement_score, 3),
                "level": self._agreement_level(agreement_score)
            }

            # =========================================================
            # 5. RAW PREDICTION
            # =========================================================
            raw_prediction = {
                "match": {
                    "home": home_team,
                    "away": away_team,
                    "league": league
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
                "over_2_5": poisson_result.get("over_2_5", 0)
            }

            # =========================================================
            # 6. CALIBRATION
            # =========================================================
            calibrated = self.calibration_engine.adjust(raw_prediction)

            # Нормализация вероятностей (сумма должна быть 1.0)
            home_prob = calibrated.get("home", probs.get("home", 0.33))
            draw_prob = calibrated.get("draw", probs.get("draw", 0.33))
            away_prob = calibrated.get("away", probs.get("away", 0.33))

            total = home_prob + draw_prob + away_prob
            if total > 0:
                home_prob /= total
                draw_prob /= total
                away_prob /= total

            # =========================================================
            # 7. CONFIDENCE
            # =========================================================
            confidence_result = self.confidence_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated={"home": home_prob, "draw": draw_prob, "away": away_prob}
            )

            # =========================================================
            # 8. RISK
            # =========================================================
            risk_result = self.risk_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated={"home": home_prob, "draw": draw_prob, "away": away_prob},
                confidence=confidence_result
            )

            # =========================================================
            # 9. РЕЗУЛЬТАТ
            # =========================================================
            score = poisson_result.get("most_likely_score", "0:0")
            score_prob = poisson_result.get("score_probability", 0)

            return {
                "status": "success",
                "prediction_id": prediction_id,
                "score": score,
                "score_probability": round(score_prob, 3),
                "xg": {
                    "home": round(home_xg, 3),
                    "away": round(away_xg, 3)
                },
                "probability": {
                    "home": round(home_prob, 3),
                    "draw": round(draw_prob, 3),
                    "away": round(away_prob, 3)
                },
                "btts": round(poisson_result.get("btts_probability", 0), 3),
                "over_2_5": round(poisson_result.get("over_2_5", 0), 3),
                "confidence": {
                    "overall": round(confidence_result.get("overall", 0), 3),
                    "level": confidence_result.get("level", "MEDIUM")
                },
                "risk": {
                    "score": risk_result.get("score", 0),
                    "level": risk_result.get("level", "MEDIUM")
                },
                "model_agreement": model_agreement,
                "version": self.VERSION,
                "processing_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
            }

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _build_seed(self, home: str, away: str, home_rating: float, away_rating: float, home_xg: float, away_xg: float) -> int:
        key = f"{home}_{away}_{self.VERSION}_{home_rating:.1f}_{away_rating:.1f}_{home_xg:.2f}_{away_xg:.2f}_{config.SEASON_START}"
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def _calculate_model_agreement(self, poisson_result: Dict, mc_result: Dict) -> float:
        p = poisson_result.get("result_probability", {})
        m = mc_result
        diff = (
            abs(p.get("home", config.DEFAULT_HOME_PROB) - m.get("home_win", config.DEFAULT_HOME_PROB)) +
            abs(p.get("draw", config.DEFAULT_DRAW_PROB) - m.get("draw", config.DEFAULT_DRAW_PROB)) +
            abs(p.get("away", config.DEFAULT_AWAY_PROB) - m.get("away_win", config.DEFAULT_AWAY_PROB))
        )
        return round(1 - diff / 3, 4)

    def _agreement_level(self, value: float) -> str:
        if value >= 0.85:
            return "HIGH"
        elif value >= 0.65:
            return "MEDIUM"
        else:
            return "LOW"


# ============================================================
# SINGLETON
# ============================================================

_pipeline_instance: PredictionPipeline = None


def get_prediction_pipeline() -> PredictionPipeline:
    """Синглтон для PredictionPipeline"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = PredictionPipeline()
    return _pipeline_instance
