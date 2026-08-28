#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Prediction Pipeline v2.3
=====================================================

РОЛЬ:
    Чистый математический двигатель FAJ.

АРХИТЕКТУРНЫЕ ПРАВИЛА:
    - Pipeline НЕ работает с БД.
    - Pipeline НЕ загружает календарь.
    - Pipeline НЕ изменяет БД.
    - Prediction и Fact не смешиваются.
    - XG Prediction xG является pre-match величиной.
    - Poisson строит score matrix на основе FAJ xG.
    - Monte Carlo используется как независимый математический
      контроль и источник model agreement.
    - Calibration / Confidence / Risk работают после базового
      математического расчёта.

ИСПРАВЛЕНИЯ v2.3:
    1. Единый вызов XGModel через home_rating / away_rating.
    2. Единый league default = "РПЛ".
    3. form является обязательным полем паспорта.
    4. BTTS/O2.5/O3.5 рассчитываются из score_matrix.
    5. most_likely_score использует probability.
    6. ConfidenceEngine получает только согласованный контракт.
    7. RiskEngine получает context=None.
    8. Monte Carlo используется только для model agreement.
    9. Проверяется корректность результата Monte Carlo.
    10. Защита от NaN/Inf для xG и вероятностей.
    11. Вероятности 1X2 нормализуются единым способом.
    12. В результат сохраняются версии математических моделей.
    13. Pipeline остаётся полностью независимым от БД.
"""

import hashlib
import logging
import math
import time
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
    FAJ Prediction Pipeline v2.3.
    """

    VERSION = "2.3"

    def __init__(self):
        self.version = self.VERSION

        self.xg_model = XGModel()
        self.poisson_model = FAJPoissonModel(
            max_goals=config.MAX_GOALS
        )
        self.monte_carlo_model = MonteCarloModel()

        self.calibration_engine = CalibrationEngine()
        self.confidence_engine = ConfidenceEngine()
        self.risk_engine = RiskEngine()

        logger.info(
            "Prediction Pipeline v%s initialized",
            self.VERSION
        )

    # ============================================================
    # MAIN
    # ============================================================

    def run(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float,
        away_rating: float,
        home_team: str = "",
        away_team: str = "",
        league: str = "РПЛ",
    ) -> Dict[str, Any]:

        start_time = time.perf_counter()
        prediction_id = str(uuid.uuid4())[:8]

        try:
            # ====================================================
            # 0. INPUT VALIDATION
            # ====================================================

            self._validate_input(
                home_passport,
                away_passport,
                home_rating,
                away_rating,
            )

            home_rating = float(home_rating)
            away_rating = float(away_rating)

            logger.info(
                "PIPELINE START | %s vs %s | "
                "home_rating=%.2f | away_rating=%.2f",
                home_team,
                away_team,
                home_rating,
                away_rating,
            )

            # ====================================================
            # 1. XG MODEL
            # ====================================================

            xg_result = self.xg_model.calculate(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating,
            )

            if not isinstance(xg_result, dict):
                raise ValueError(
                    "XG Model returned invalid result"
                )

            if xg_result.get("status") != "success":
                raise ValueError(
                    "XG Model calculation failed: "
                    f"{xg_result.get('message', 'unknown error')}"
                )

            if (
                "home_xg" not in xg_result
                or "away_xg" not in xg_result
            ):
                raise ValueError(
                    "XG Model result missing xG values"
                )

            home_xg = self._safe_float(
                xg_result["home_xg"],
                "home_xg",
            )
            away_xg = self._safe_float(
                xg_result["away_xg"],
                "away_xg",
            )

            home_xg = self._clamp_xg(home_xg)
            away_xg = self._clamp_xg(away_xg)

            logger.info(
                "XG RESULT | %s vs %s | "
                "home=%.4f | away=%.4f",
                home_team,
                away_team,
                home_xg,
                away_xg,
            )

            # ====================================================
            # 2. POISSON
            # ====================================================

            poisson_result = self.poisson_model.calculate(
                home_xg,
                away_xg,
                include_matrix=True,
            )

            if not isinstance(poisson_result, dict):
                raise ValueError(
                    "Poisson Model returned invalid result"
                )

            if poisson_result.get("status") == "error":
                raise ValueError(
                    "Poisson calculation failed: "
                    f"{poisson_result.get('message', 'unknown error')}"
                )

            probabilities = poisson_result.get(
                "result_probability",
                {},
            )

            if not isinstance(probabilities, dict):
                raise ValueError(
                    "Poisson result_probability must be dict"
                )

            poisson_probs = self._normalize_probabilities(
                probabilities
            )

            # ====================================================
            # 3. MONTE CARLO
            # ====================================================

            seed = self._build_seed(
                home_team,
                away_team,
                home_rating,
                away_rating,
                home_xg,
                away_xg,
            )

            mc_result = self.monte_carlo_model.simulate(
                home_xg,
                away_xg,
                iterations=config.MONTE_CARLO_ITERATIONS,
                seed=(
                    seed
                    if config.MONTE_CARLO_REPRODUCIBLE
                    else None
                ),
            )

            if not isinstance(mc_result, dict):
                raise ValueError(
                    "Monte Carlo returned invalid result"
                )

            if mc_result.get("status") == "error":
                raise ValueError(
                    "Monte Carlo calculation failed: "
                    f"{mc_result.get('message', 'unknown error')}"
                )

            # ====================================================
            # 4. MODEL AGREEMENT
            # ====================================================

            agreement_score = self._calculate_model_agreement(
                poisson_result,
                mc_result,
            )

            model_agreement = {
                "score": round(agreement_score, 4),
                "level": self._agreement_level(
                    agreement_score
                ),
            }

            # ====================================================
            # 5. EXTENDED METRICS
            # ====================================================

            score_matrix = poisson_result.get(
                "score_matrix",
                {},
            )

            extended = self._calculate_extended_metrics(
                home_xg=home_xg,
                away_xg=away_xg,
                poisson_top_scores=poisson_result.get(
                    "top_scores",
                    [],
                ),
                score_matrix=score_matrix,
            )

            btts_prob = float(
                extended
                .get("btts", {})
                .get("yes", 0.0)
            )

            over_25 = float(
                extended
                .get("total", {})
                .get("over_2_5", 0.0)
            )

            # ====================================================
            # 6. RAW PREDICTION
            # ====================================================

            most_likely_score = self._normalize_score(
                poisson_result.get(
                    "most_likely_score",
                    "0:0",
                )
            )

            score_probability = self._safe_probability(
                poisson_result.get(
                    "score_probability",
                    0.0,
                )
            )

            raw_prediction = {
                "match": {
                    "home": home_team,
                    "away": away_team,
                    "league": league,
                },
                "xg": {
                    "home": home_xg,
                    "away": away_xg,
                },
                "probability": poisson_probs,
                "score_prediction": {
                    "faj_score": most_likely_score,
                    "probability": score_probability,
                },
                "btts": btts_prob,
                "over_2_5": over_25,
            }

            # ====================================================
            # 7. CALIBRATION
            # ====================================================

            calibrated = self.calibration_engine.adjust(
                raw_prediction
            )

            if not isinstance(calibrated, dict):
                calibrated = {}

            calibrated_probs = self._normalize_probabilities(
                {
                    "home": calibrated.get(
                        "home",
                        poisson_probs["home"],
                    ),
                    "draw": calibrated.get(
                        "draw",
                        poisson_probs["draw"],
                    ),
                    "away": calibrated.get(
                        "away",
                        poisson_probs["away"],
                    ),
                }
            )

            # ====================================================
            # 8. CONFIDENCE
            # ====================================================

            confidence_result = (
                self.confidence_engine.calculate(
                    raw_prediction=raw_prediction,
                    calibrated=calibrated_probs,
                    context=None,
                )
            )

            if not isinstance(confidence_result, dict):
                confidence_result = {
                    "overall": 0.0,
                    "level": "LOW",
                }

            confidence_value = self._safe_probability(
                confidence_result.get(
                    "overall",
                    0.0,
                )
            )

            confidence_level = confidence_result.get(
                "level",
                "MEDIUM",
            )

            # ====================================================
            # 9. RISK
            # ====================================================

            risk_result = self.risk_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated=calibrated_probs,
                confidence=confidence_result,
                context=None,
            )

            if not isinstance(risk_result, dict):
                risk_result = {
                    "score": 0.0,
                    "level": "MEDIUM",
                }

            risk_score = risk_result.get(
                "score",
                0.0,
            )

            try:
                risk_score = float(risk_score)
            except (TypeError, ValueError):
                risk_score = 0.0

            # ====================================================
            # 10. MODEL VERSIONS
            # ====================================================

            model_versions = {
                "pipeline": self.VERSION,
                "xg_model": getattr(
                    self.xg_model,
                    "VERSION",
                    getattr(
                        self.xg_model,
                        "version",
                        "unknown",
                    ),
                ),
                "poisson_model": getattr(
                    self.poisson_model,
                    "VERSION",
                    getattr(
                        self.poisson_model,
                        "version",
                        "unknown",
                    ),
                ),
                "monte_carlo_model": getattr(
                    self.monte_carlo_model,
                    "VERSION",
                    getattr(
                        self.monte_carlo_model,
                        "version",
                        "unknown",
                    ),
                ),
            }

            # ====================================================
            # 11. FINAL RESULT
            # ====================================================

            processing_time = round(
                (
                    time.perf_counter()
                    - start_time
                ) * 1000,
                2,
            )

            result = {
                "status": "success",
                "prediction_id": prediction_id,

                "match": {
                    "home": home_team,
                    "away": away_team,
                    "league": league,
                },

                "score": most_likely_score,
                "score_probability": round(
                    score_probability,
                    4,
                ),

                "xg": {
                    "home": round(home_xg, 4),
                    "away": round(away_xg, 4),
                },

                "probability": {
                    "home": round(
                        calibrated_probs["home"],
                        4,
                    ),
                    "draw": round(
                        calibrated_probs["draw"],
                        4,
                    ),
                    "away": round(
                        calibrated_probs["away"],
                        4,
                    ),
                },

                "btts": round(
                    btts_prob,
                    4,
                ),

                "over_2_5": round(
                    over_25,
                    4,
                ),

                "confidence": {
                    "overall": round(
                        confidence_value,
                        4,
                    ),
                    "level": confidence_level,
                },

                "risk": {
                    "score": round(
                        risk_score,
                        4,
                    ),
                    "level": risk_result.get(
                        "level",
                        "MEDIUM",
                    ),
                },

                "model_agreement": model_agreement,

                "extended": extended,

                "model_versions": model_versions,

                "version": self.VERSION,

                "processing_time_ms": processing_time,
            }

            logger.info(
                "PIPELINE SUCCESS | %s vs %s | "
                "score=%s | xG=%.2f:%.2f | "
                "P=%.3f/%.3f/%.3f | "
                "confidence=%.3f | risk=%s",
                home_team,
                away_team,
                most_likely_score,
                home_xg,
                away_xg,
                calibrated_probs["home"],
                calibrated_probs["draw"],
                calibrated_probs["away"],
                confidence_value,
                risk_result.get(
                    "level",
                    "MEDIUM",
                ),
            )

            return result

        except Exception as e:
            logger.exception(
                "PIPELINE ERROR | %s vs %s",
                home_team,
                away_team,
            )

            return {
                "status": "error",
                "message": str(e),
                "prediction_id": prediction_id,
                "version": self.VERSION,
                "processing_time_ms": round(
                    (
                        time.perf_counter()
                        - start_time
                    ) * 1000,
                    2,
                ),
            }

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_input(
        self,
        home_passport,
        away_passport,
        home_rating,
        away_rating,
    ):
        if not isinstance(home_passport, dict):
            raise ValueError(
                "Home passport must be dict"
            )

        if not isinstance(away_passport, dict):
            raise ValueError(
                "Away passport must be dict"
            )

        required = [
            "attack",
            "defense",
            "control",
            "goalkeeper",
            "form",
        ]

        for name, passport in (
            ("home", home_passport),
            ("away", away_passport),
        ):
            missing = [
                field
                for field in required
                if (
                    field not in passport
                    or passport.get(field) is None
                )
            ]

            if missing:
                raise ValueError(
                    f"{name} passport missing: "
                    f"{', '.join(missing)}"
                )

        try:
            home_rating = float(home_rating)
            away_rating = float(away_rating)
        except (TypeError, ValueError):
            raise ValueError(
                "Team ratings must be numeric"
            )

        if not math.isfinite(home_rating):
            raise ValueError(
                "Home rating must be finite"
            )

        if not math.isfinite(away_rating):
            raise ValueError(
                "Away rating must be finite"
            )

    # ============================================================
    # SAFE NUMBERS
    # ============================================================

    def _safe_float(
        self,
        value,
        field_name: str,
    ) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be numeric"
            )

        if not math.isfinite(value):
            raise ValueError(
                f"{field_name} must be finite"
            )

        return value

    def _safe_probability(self, value) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0

        if not math.isfinite(value):
            return 0.0

        return max(
            0.0,
            min(1.0, value),
        )

    def _clamp_xg(self, value: float) -> float:
        return max(
            float(config.XG_MIN),
            min(
                float(config.XG_MAX),
                value,
            ),
        )

    # ============================================================
    # PROBABILITY NORMALIZATION
    # ============================================================

    def _normalize_probabilities(
        self,
        probabilities: Dict[str, Any],
    ) -> Dict[str, float]:

        defaults = {
            "home": float(
                config.DEFAULT_HOME_PROB
            ),
            "draw": float(
                config.DEFAULT_DRAW_PROB
            ),
            "away": float(
                config.DEFAULT_AWAY_PROB
            ),
        }

        values = {}

        for key in ("home", "draw", "away"):
            try:
                value = float(
                    probabilities.get(
                        key,
                        defaults[key],
                    )
                )
            except (TypeError, ValueError):
                value = defaults[key]

            if not math.isfinite(value):
                value = defaults[key]

            values[key] = max(
                0.0,
                min(1.0, value),
            )

        total = (
            values["home"]
            + values["draw"]
            + values["away"]
        )

        if total <= 0:
            values = {
                "home": 1 / 3,
                "draw": 1 / 3,
                "away": 1 / 3,
            }
        else:
            values = {
                key: value / total
                for key, value in values.items()
            }

        return values

    # ============================================================
    # SEED
    # ============================================================

    def _build_seed(
        self,
        home,
        away,
        home_rating,
        away_rating,
        home_xg,
        away_xg,
    ) -> int:

        key = (
            f"{home}_"
            f"{away}_"
            f"{self.VERSION}_"
            f"{home_rating:.4f}_"
            f"{away_rating:.4f}_"
            f"{home_xg:.4f}_"
            f"{away_xg:.4f}_"
            f"{config.SEASON_START}"
        )

        return int(
            hashlib.md5(
                key.encode("utf-8")
            ).hexdigest()[:8],
            16,
        )

    # ============================================================
    # MODEL AGREEMENT
    # ============================================================

    def _calculate_model_agreement(
        self,
        poisson_result,
        mc_result,
    ) -> float:

        p = poisson_result.get(
            "result_probability",
            {},
        )

        m = mc_result or {}

        poisson_probs = self._normalize_probabilities(
            p
        )

        mc_probs = self._normalize_probabilities(
            {
                "home": m.get(
                    "home_win",
                    config.DEFAULT_HOME_PROB,
                ),
                "draw": m.get(
                    "draw",
                    config.DEFAULT_DRAW_PROB,
                ),
                "away": m.get(
                    "away_win",
                    config.DEFAULT_AWAY_PROB,
                ),
            }
        )

        distance = (
            abs(
                poisson_probs["home"]
                - mc_probs["home"]
            )
            + abs(
                poisson_probs["draw"]
                - mc_probs["draw"]
            )
            + abs(
                poisson_probs["away"]
                - mc_probs["away"]
            )
        ) / 3

        agreement = 1.0 - distance

        return max(
            0.0,
            min(
                1.0,
                round(
                    agreement,
                    4,
                ),
            ),
        )

    def _agreement_level(
        self,
        value: float,
    ) -> str:

        if value >= 0.85:
            return "HIGH"

        if value >= 0.65:
            return "MEDIUM"

        return "LOW"

    # ============================================================
    # SCORE NORMALIZATION
    # ============================================================

    def _normalize_score(self, score) -> str:

        if isinstance(score, dict):
            home = score.get("home", 0)
            away = score.get("away", 0)

            try:
                return f"{int(home)}:{int(away)}"
            except (TypeError, ValueError):
                return "0:0"

        score = str(score)

        if ":" in score:
            home, away = score.split(":", 1)
        elif "-" in score:
            home, away = score.split("-", 1)
        else:
            return "0:0"

        try:
            return f"{int(home)}:{int(away)}"
        except (TypeError, ValueError):
            return "0:0"

    # ============================================================
    # EXTENDED METRICS
    # ============================================================

    def _calculate_extended_metrics(
        self,
        home_xg,
        away_xg,
        poisson_top_scores,
        score_matrix,
    ):

        top_scores = []

        if isinstance(
            poisson_top_scores,
            list,
        ):
            for i, score_data in enumerate(
                poisson_top_scores[:5]
            ):
                try:
                    if not isinstance(
                        score_data,
                        dict,
                    ):
                        continue

                    score_str = str(
                        score_data.get(
                            "score",
                            "0:0",
                        )
                    )

                    probability = (
                        self._safe_probability(
                            score_data.get(
                                "probability",
                                0.0,
                            )
                        )
                    )

                    if ":" in score_str:
                        home, away = score_str.split(
                            ":",
                            1,
                        )
                    elif "-" in score_str:
                        home, away = score_str.split(
                            "-",
                            1,
                        )
                    else:
                        continue

                    top_scores.append(
                        {
                            "rank": i + 1,
                            "home": int(home),
                            "away": int(away),
                            "probability": round(
                                probability,
                                4,
                            ),
                            "prob_percent": (
                                f"{probability * 100:.2f}%"
                            ),
                        }
                    )

                except (
                    ValueError,
                    TypeError,
                    AttributeError,
                ) as e:

                    logger.warning(
                        "Cannot parse top score %s: %s",
                        score_data,
                        e,
                    )

        distributions = []

        if isinstance(
            score_matrix,
            dict,
        ):
            for score_str, probability in (
                score_matrix.items()
            ):
                try:
                    if ":" in str(score_str):
                        home, away = str(
                            score_str
                        ).split(":", 1)

                    elif "-" in str(score_str):
                        home, away = str(
                            score_str
                        ).split("-", 1)

                    else:
                        continue

                    distributions.append(
                        {
                            "home": int(home),
                            "away": int(away),
                            "probability": round(
                                self._safe_probability(
                                    probability
                                ),
                                6,
                            ),
                        }
                    )

                except (
                    ValueError,
                    TypeError,
                    AttributeError,
                ):
                    continue

        btts_prob = 0.0
        over_25 = 0.0
        over_35 = 0.0

        if isinstance(
            score_matrix,
            dict,
        ) and score_matrix:

            for score_str, probability in (
                score_matrix.items()
            ):
                try:
                    score_str = str(score_str)

                    if ":" in score_str:
                        home, away = score_str.split(
                            ":",
                            1,
                        )
                    elif "-" in score_str:
                        home, away = score_str.split(
                            "-",
                            1,
                        )
                    else:
                        continue

                    home = int(home)
                    away = int(away)

                    probability = (
                        self._safe_probability(
                            probability
                        )
                    )

                    if home > 0 and away > 0:
                        btts_prob += probability

                    total_goals = home + away

                    if total_goals >= 3:
                        over_25 += probability

                    if total_goals >= 4:
                        over_35 += probability

                except (
                    ValueError,
                    TypeError,
                    AttributeError,
                ):
                    continue

        else:
            # Fallback только математический.
            # Никаких внешних/фактических данных здесь нет.

            btts_prob = (
                1.0 - math.exp(-home_xg)
            ) * (
                1.0 - math.exp(-away_xg)
            )

            total_xg = home_xg + away_xg

            poisson_0_2 = (
                math.exp(-total_xg)
                * (
                    1
                    + total_xg
                    + total_xg ** 2 / 2
                )
            )

            over_25 = 1.0 - poisson_0_2

            poisson_0_3 = (
                math.exp(-total_xg)
                * (
                    1
                    + total_xg
                    + total_xg ** 2 / 2
                    + total_xg ** 3 / 6
                )
            )

            over_35 = 1.0 - poisson_0_3

        btts_prob = self._safe_probability(
            btts_prob
        )

        over_25 = self._safe_probability(
            over_25
        )

        over_35 = self._safe_probability(
            over_35
        )

        if top_scores:
            most_likely = {
                "home": top_scores[0]["home"],
                "away": top_scores[0]["away"],
                "probability": top_scores[0][
                    "probability"
                ],
            }
        else:
            most_likely = {
                "home": 0,
                "away": 0,
                "probability": 0.0,
            }

        return {
            "top_scores": top_scores,

            "most_likely_score": most_likely,

            "distributions": distributions,

            "btts": {
                "yes": round(
                    btts_prob,
                    4,
                ),
                "no": round(
                    1.0 - btts_prob,
                    4,
                ),
            },

            "total": {
                "over_2_5": round(
                    over_25,
                    4,
                ),
                "under_2_5": round(
                    1.0 - over_25,
                    4,
                ),
                "over_3_5": round(
                    over_35,
                    4,
                ),
                "under_3_5": round(
                    1.0 - over_35,
                    4,
                ),
            },
        }


# ============================================================
# SINGLETON
# ============================================================

_pipeline_instance = None


def get_prediction_pipeline() -> PredictionPipeline:
    global _pipeline_instance

    if _pipeline_instance is None:
        _pipeline_instance = PredictionPipeline()

    return _pipeline_instance
