#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.1
Prediction Pipeline v2.0
=====================================================

РОЛЬ:
    Чистый математический двигатель FAJ.

ЦЕПОЧКА:

    Team Passport
        ↓
    XG Model
        ↓
    Poisson
        ↓
    Monte Carlo
        ↓
    Model Agreement
        ↓
    Calibration
        ↓
    Confidence
        ↓
    Risk
        ↓
    Final Prediction

ВАЖНО:
    Pipeline НЕ работает с БД.
    Pipeline НЕ загружает календарь.
    Pipeline НЕ изменяет БД.

    Работа с БД находится в PredictionManager.
"""

import time
import logging
import hashlib
import uuid
import math

from typing import Dict, Any, List

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
    FAJ Prediction Pipeline v2.0.

    Чистый расчёт без обращения к БД.
    """

    VERSION = "2.0"

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
        league: str = "RPL"
    ) -> Dict[str, Any]:

        start_time = time.perf_counter()

        prediction_id = str(
            uuid.uuid4()
        )[:8]

        try:

            # ====================================================
            # INPUT VALIDATION
            # ====================================================

            self._validate_input(
                home_passport,
                away_passport,
                home_rating,
                away_rating
            )

            logger.info(
                "🚀 PIPELINE START | "
                "%s vs %s | "
                "home_rating=%.2f | away_rating=%.2f",
                home_team,
                away_team,
                float(home_rating),
                float(away_rating)
            )

            logger.info(
                "HOME PASSPORT | attack=%s defense=%s "
                "control=%s goalkeeper=%s form=%s",
                home_passport.get("attack"),
                home_passport.get("defense"),
                home_passport.get("control"),
                home_passport.get("goalkeeper"),
                home_passport.get("form")
            )

            logger.info(
                "AWAY PASSPORT | attack=%s defense=%s "
                "control=%s goalkeeper=%s form=%s",
                away_passport.get("attack"),
                away_passport.get("defense"),
                away_passport.get("control"),
                away_passport.get("goalkeeper"),
                away_passport.get("form")
            )

            # ====================================================
            # 1. XG
            # ====================================================

            xg_result = self.xg_model.calculate(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating
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

            home_xg = float(
                xg_result["home_xg"]
            )

            away_xg = float(
                xg_result["away_xg"]
            )

            home_xg = max(
                config.XG_MIN,
                min(config.XG_MAX, home_xg)
            )

            away_xg = max(
                config.XG_MIN,
                min(config.XG_MAX, away_xg)
            )

            logger.info(
                "✅ XG RESULT | "
                "%s vs %s | "
                "home=%.3f away=%.3f",
                home_team,
                away_team,
                home_xg,
                away_xg
            )

            # ====================================================
            # 2. XG DIAGNOSTICS
            # ====================================================

            components = xg_result.get(
                "components",
                {}
            )

            diagnostic = {

                "raw_xg_home": round(
                    float(xg_result.get(
                        "home_xg",
                        home_xg
                    )),
                    3
                ),

                "raw_xg_away": round(
                    float(xg_result.get(
                        "away_xg",
                        away_xg
                    )),
                    3
                ),

                "home_attack_factor":
                    components.get(
                        "home_attack_factor",
                        1.0
                    ),

                "away_attack_factor":
                    components.get(
                        "away_attack_factor",
                        1.0
                    ),

                "home_defense_factor":
                    components.get(
                        "home_defense_factor",
                        1.0
                    ),

                "away_defense_factor":
                    components.get(
                        "away_defense_factor",
                        1.0
                    ),

                "home_keeper_factor":
                    components.get(
                        "home_keeper_factor",
                        1.0
                    ),

                "away_keeper_factor":
                    components.get(
                        "away_keeper_factor",
                        1.0
                    ),

                "home_control_factor":
                    components.get(
                        "home_control_factor",
                        1.0
                    ),

                "away_control_factor":
                    components.get(
                        "away_control_factor",
                        1.0
                    ),

                "home_advantage":
                    components.get(
                        "home_advantage",
                        config.HOME_ADVANTAGE
                    ),

                "home_form":
                    components.get(
                        "home_form_factor",
                        1.0
                    ),

                "away_form":
                    components.get(
                        "away_form_factor",
                        1.0
                    ),

                "home_rating": round(
                    float(home_rating),
                    2
                ),

                "away_rating": round(
                    float(away_rating),
                    2
                ),

                "rating_used_for_xg":
                    components.get(
                        "rating_used_for_xg",
                        False
                    )
            }

            # ====================================================
            # 3. POISSON
            # ====================================================

            poisson_result = (
                self.poisson_model.calculate(
                    home_xg,
                    away_xg,
                    include_matrix=True
                )
            )

            if not isinstance(
                poisson_result,
                dict
            ):

                raise ValueError(
                    "Poisson Model returned invalid result"
                )

            if poisson_result.get(
                "status"
            ) == "error":

                raise ValueError(
                    "Poisson calculation failed: "
                    f"{poisson_result.get('message', 'unknown error')}"
                )

            probabilities = poisson_result.get(
                "result_probability",
                {}
            )

            # ====================================================
            # 4. MONTE CARLO
            # ====================================================

            seed = self._build_seed(
                home_team,
                away_team,
                home_rating,
                away_rating,
                home_xg,
                away_xg
            )

            mc_result = (
                self.monte_carlo_model.simulate(
                    home_xg,
                    away_xg,
                    iterations=config.MONTE_CARLO_ITERATIONS,
                    seed=(
                        seed
                        if config.MONTE_CARLO_REPRODUCIBLE
                        else None
                    )
                )
            )

            if not isinstance(
                mc_result,
                dict
            ):

                raise ValueError(
                    "Monte Carlo returned invalid result"
                )

            # ====================================================
            # 5. MODEL AGREEMENT
            # ====================================================

            agreement_score = (
                self._calculate_model_agreement(
                    poisson_result,
                    mc_result
                )
            )

            model_agreement = {

                "score": round(
                    agreement_score,
                    3
                ),

                "level":
                    self._agreement_level(
                        agreement_score
                    )
            }

            # ====================================================
            # 6. RAW PREDICTION
            # ====================================================

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

                    "home":
                        probabilities.get(
                            "home",
                            config.DEFAULT_HOME_PROB
                        ),

                    "draw":
                        probabilities.get(
                            "draw",
                            config.DEFAULT_DRAW_PROB
                        ),

                    "away":
                        probabilities.get(
                            "away",
                            config.DEFAULT_AWAY_PROB
                        )
                },

                "score_prediction": {

                    "faj_score":
                        poisson_result.get(
                            "most_likely_score",
                            "0:0"
                        ),

                    "probability":
                        poisson_result.get(
                            "score_probability",
                            0
                        )
                },

                "btts":
                    poisson_result.get(
                        "btts_probability",
                        0
                    ),

                "over_2_5":
                    poisson_result.get(
                        "over_2_5",
                        0
                    )
            }

            # ====================================================
            # 7. CALIBRATION
            # ====================================================

            calibrated = (
                self.calibration_engine.adjust(
                    raw_prediction
                )
            )

            home_prob = float(
                calibrated.get(
                    "home",
                    probabilities.get(
                        "home",
                        0.33
                    )
                )
            )

            draw_prob = float(
                calibrated.get(
                    "draw",
                    probabilities.get(
                        "draw",
                        0.33
                    )
                )
            )

            away_prob = float(
                calibrated.get(
                    "away",
                    probabilities.get(
                        "away",
                        0.33
                    )
                )
            )

            total = (
                home_prob
                + draw_prob
                + away_prob
            )

            if total > 0:

                home_prob /= total
                draw_prob /= total
                away_prob /= total

            # ====================================================
            # 8. CONFIDENCE
            # ====================================================

            confidence_result = (
                self.confidence_engine.calculate(
                    raw_prediction=raw_prediction,
                    calibrated={
                        "home": home_prob,
                        "draw": draw_prob,
                        "away": away_prob
                    }
                )
            )

            # ====================================================
            # 9. RISK
            # ====================================================

            risk_result = (
                self.risk_engine.calculate(
                    raw_prediction=raw_prediction,
                    calibrated={
                        "home": home_prob,
                        "draw": draw_prob,
                        "away": away_prob
                    },
                    confidence=confidence_result
                )
            )

            # ====================================================
            # 10. EXTENDED METRICS
            # ====================================================

            extended = (
                self._calculate_extended_metrics(
                    home_xg=home_xg,
                    away_xg=away_xg,
                    poisson_top_scores=
                        poisson_result.get(
                            "top_scores",
                            []
                        ),
                    score_matrix=
                        poisson_result.get(
                            "score_matrix",
                            {}
                        )
                )
            )

            # ====================================================
            # 11. FINAL RESULT
            # ====================================================

            score = poisson_result.get(
                "most_likely_score",
                "0:0"
            )

            score_probability = float(
                poisson_result.get(
                    "score_probability",
                    0
                )
            )

            processing_time = round(
                (
                    time.perf_counter()
                    - start_time
                ) * 1000,
                2
            )

            result = {

                "status": "success",

                "prediction_id":
                    prediction_id,

                "match": {
                    "home": home_team,
                    "away": away_team,
                    "league": league
                },

                "score": score,

                "score_probability":
                    round(
                        score_probability,
                        4
                    ),

                "xg": {
                    "home": round(
                        home_xg,
                        4
                    ),
                    "away": round(
                        away_xg,
                        4
                    )
                },

                "probability": {
                    "home": round(
                        home_prob,
                        4
                    ),
                    "draw": round(
                        draw_prob,
                        4
                    ),
                    "away": round(
                        away_prob,
                        4
                    )
                },

                "btts": round(
                    float(
                        poisson_result.get(
                            "btts_probability",
                            0
                        )
                    ),
                    4
                ),

                "over_2_5": round(
                    float(
                        poisson_result.get(
                            "over_2_5",
                            0
                        )
                    ),
                    4
                ),

                "confidence": {

                    "overall": round(
                        float(
                            confidence_result.get(
                                "overall",
                                0
                            )
                        ),
                        4
                    ),

                    "level":
                        confidence_result.get(
                            "level",
                            "MEDIUM"
                        )
                },

                "risk": {

                    "score":
                        risk_result.get(
                            "score",
                            0
                        ),

                    "level":
                        risk_result.get(
                            "level",
                            "MEDIUM"
                        )
                },

                "model_agreement":
                    model_agreement,

                "extended":
                    extended,

                "diagnostic":
                    diagnostic,

                "version":
                    self.VERSION,

                "processing_time_ms":
                    processing_time
            }

            logger.info(
                "✅ PIPELINE SUCCESS | "
                "%s vs %s | "
                "score=%s | xG=%.2f:%.2f | "
                "P=%.3f/%.3f/%.3f | "
                "confidence=%.3f | risk=%s",
                home_team,
                away_team,
                score,
                home_xg,
                away_xg,
                home_prob,
                draw_prob,
                away_prob,
                confidence_result.get(
                    "overall",
                    0
                ),
                risk_result.get(
                    "level",
                    "MEDIUM"
                )
            )

            return result

        except Exception as e:

            logger.exception(
                "❌ PIPELINE ERROR | %s vs %s",
                home_team,
                away_team
            )

            return {

                "status": "error",

                "message": str(e),

                "prediction_id":
                    prediction_id,

                "version":
                    self.VERSION,

                "processing_time_ms":
                    round(
                        (
                            time.perf_counter()
                            - start_time
                        ) * 1000,
                        2
                    )
            }

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_input(
        self,
        home_passport: Dict[str, Any],
        away_passport: Dict[str, Any],
        home_rating: float,
        away_rating: float
    ) -> None:

        if not isinstance(
            home_passport,
            dict
        ):

            raise ValueError(
                "Home passport must be dict"
            )

        if not isinstance(
            away_passport,
            dict
        ):

            raise ValueError(
                "Away passport must be dict"
            )

        for name, passport in (
            ("home", home_passport),
            ("away", away_passport)
        ):

            required = [
                "attack",
                "defense",
                "control",
                "goalkeeper"
            ]

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

            float(home_rating)
            float(away_rating)

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                "Team ratings must be numeric"
            )

    # ============================================================
    # SEED
    # ============================================================

    def _build_seed(
        self,
        home: str,
        away: str,
        home_rating: float,
        away_rating: float,
        home_xg: float,
        away_xg: float
    ) -> int:

        key = (
            f"{home}_{away}_"
            f"{self.VERSION}_"
            f"{home_rating:.1f}_"
            f"{away_rating:.1f}_"
            f"{home_xg:.2f}_"
            f"{away_xg:.2f}_"
            f"{config.SEASON_START}"
        )

        return int(
            hashlib.md5(
                key.encode()
            ).hexdigest()[:8],
            16
        )

    # ============================================================
    # AGREEMENT
    # ============================================================

    def _calculate_model_agreement(
        self,
        poisson_result: Dict,
        mc_result: Dict
    ) -> float:

        p = poisson_result.get(
            "result_probability",
            {}
        )

        m = mc_result or {}

        diff = (

            abs(
                p.get(
                    "home",
                    config.DEFAULT_HOME_PROB
                )
                -
                m.get(
                    "home_win",
                    config.DEFAULT_HOME_PROB
                )
            )

            +

            abs(
                p.get(
                    "draw",
                    config.DEFAULT_DRAW_PROB
                )
                -
                m.get(
                    "draw",
                    config.DEFAULT_DRAW_PROB
                )
            )

            +

            abs(
                p.get(
                    "away",
                    config.DEFAULT_AWAY_PROB
                )
                -
                m.get(
                    "away_win",
                    config.DEFAULT_AWAY_PROB
                )
            )
        )

        return max(
            0.0,
            min(
                1.0,
                round(
                    1 - diff / 3,
                    4
                )
            )
        )

    def _agreement_level(
        self,
        value: float
    ) -> str:

        if value >= 0.85:
            return "HIGH"

        if value >= 0.65:
            return "MEDIUM"

        return "LOW"

    # ============================================================
    # EXTENDED METRICS
    # ============================================================

    def _calculate_extended_metrics(
        self,
        home_xg: float,
        away_xg: float,
        poisson_top_scores: List[Dict[str, Any]],
        score_matrix: Dict[str, float]
    ) -> Dict[str, Any]:

        top_scores = []

        # --------------------------------------------------------
        # TOP SCORES
        # --------------------------------------------------------

        for i, score_data in enumerate(
            poisson_top_scores[:5]
        ):

            try:

                score_str = str(
                    score_data.get(
                        "score",
                        "0:0"
                    )
                )

                probability = float(
                    score_data.get(
                        "probability",
                        0
                    )
                )

                if ":" in score_str:

                    home, away = (
                        score_str.split(
                            ":",
                            1
                        )
                    )

                elif "-" in score_str:

                    home, away = (
                        score_str.split(
                            "-",
                            1
                        )
                    )

                else:

                    continue

                top_scores.append(
                    {
                        "rank": i + 1,
                        "home": int(home),
                        "away": int(away),
                        "probability":
                            round(
                                probability,
                                4
                            ),
                        "prob_percent":
                            f"{probability * 100:.2f}%"
                    }
                )

            except (
                ValueError,
                TypeError,
                AttributeError
            ) as e:

                logger.warning(
                    "Cannot parse top score %s: %s",
                    score_data,
                    e
                )

        # --------------------------------------------------------
        # DISTRIBUTION
        # --------------------------------------------------------

        distributions = []

        if score_matrix:

            for score_str, probability in (
                score_matrix.items()
            ):

                try:

                    if ":" in score_str:

                        home, away = (
                            score_str.split(
                                ":",
                                1
                            )
                        )

                    elif "-" in score_str:

                        home, away = (
                            score_str.split(
                                "-",
                                1
                            )
                        )

                    else:

                        continue

                    distributions.append(
                        {
                            "home": int(home),
                            "away": int(away),
                            "probability":
                                round(
                                    float(
                                        probability
                                    ),
                                    6
                                )
                        }
                    )

                except (
                    ValueError,
                    TypeError,
                    AttributeError
                ):

                    continue

        # --------------------------------------------------------
        # BTTS / TOTALS
        # --------------------------------------------------------

        btts_prob = 0.0
        over_25 = 0.0
        over_35 = 0.0

        if score_matrix:

            for score_str, probability in (
                score_matrix.items()
            ):

                try:

                    if ":" in score_str:

                        home, away = (
                            score_str.split(
                                ":",
                                1
                            )
                        )

                    elif "-" in score_str:

                        home, away = (
                            score_str.split(
                                "-",
                                1
                            )
                        )

                    else:

                        continue

                    home = int(home)
                    away = int(away)
                    probability = float(
                        probability
                    )

                    if home > 0 and away > 0:
                        btts_prob += probability

                    total_goals = (
                        home + away
                    )

                    if total_goals >= 3:
                        over_25 += probability

                    if total_goals >= 4:
                        over_35 += probability

                except (
                    ValueError,
                    TypeError,
                    AttributeError
                ):

                    continue

        # --------------------------------------------------------
        # SAFETY FALLBACK
        # --------------------------------------------------------

        else:

            # Независимые Poisson-потоки.

            btts_prob = (
                1
                - math.exp(-home_xg)
            ) * (
                1
                - math.exp(-away_xg)
            )

            total_xg = (
                home_xg + away_xg
            )

            # P(total > 2)
            poisson_zero_to_two = (
                math.exp(-total_xg)
                * (
                    1
                    + total_xg
                    + total_xg ** 2 / 2
                )
            )

            over_25 = (
                1
                - poisson_zero_to_two
            )

            # P(total > 3)
            poisson_zero_to_three = (
                math.exp(-total_xg)
                * (
                    1
                    + total_xg
                    + total_xg ** 2 / 2
                    + total_xg ** 3 / 6
                )
            )

            over_35 = (
                1
                - poisson_zero_to_three
            )

        btts_prob = max(
            0.0,
            min(
                1.0,
                btts_prob
            )
        )

        over_25 = max(
            0.0,
            min(
                1.0,
                over_25
            )
        )

        over_35 = max(
            0.0,
            min(
                1.0,
                over_35
            )
        )

        # --------------------------------------------------------
        # MOST LIKELY SCORE
        # --------------------------------------------------------

        if top_scores:

            most_likely = {
                "home":
                    top_scores[0]["home"],
                "away":
                    top_scores[0]["away"],
                "prob":
                    top_scores[0]["probability"]
            }

        else:

            most_likely = {
                "home": 0,
                "away": 0,
                "prob": 0.0
            }

        return {

            "top_scores":
                top_scores,

            "most_likely_score":
                most_likely,

            "distributions":
                distributions,

            "btts": {

                "yes":
                    round(
                        btts_prob,
                        4
                    ),

                "no":
                    round(
                        1 - btts_prob,
                        4
                    )
            },

            "total": {

                "over_2_5":
                    round(
                        over_25,
                        4
                    ),

                "under_2_5":
                    round(
                        1 - over_25,
                        4
                    ),

                "over_3_5":
                    round(
                        over_35,
                        4
                    ),

                "under_3_5":
                    round(
                        1 - over_35,
                        4
                    )
            }
        }


# ============================================================
# SINGLETON
# ============================================================

_pipeline_instance = None


def get_prediction_pipeline() -> PredictionPipeline:

    global _pipeline_instance

    if _pipeline_instance is None:

        _pipeline_instance = (
            PredictionPipeline()
        )

    return _pipeline_instance
