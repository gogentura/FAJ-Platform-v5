#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
=====================================================
FAJ Platform v12.0
Prediction Pipeline v1.9

РОЛЬ:
    Математический двигатель FAJ.
    Только расчёт. Никакой БД.
=====================================================
"""

import time
import logging
import hashlib
import uuid
import math
from typing import Dict, Any, List, Tuple

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
            # 1. XG MODEL INPUT DIAGNOSTIC
            # =========================================================
            logger.info(
                "🔬 XG PIPELINE INPUT | "
                "%s vs %s | home_rating=%.2f | away_rating=%.2f",
                home_team,
                away_team,
                float(home_rating),
                float(away_rating)
            )

            # ---------------------------------------------------------
            # Home passport structure
            # ---------------------------------------------------------
            if isinstance(home_passport, dict):
                logger.info(
                    "🔬 XG PIPELINE INPUT HOME | "
                    "FLAT | attack=%s | defense=%s | "
                    "control=%s | goalkeeper=%s | form=%s",
                    home_passport.get("attack"),
                    home_passport.get("defense"),
                    home_passport.get("control"),
                    home_passport.get("goalkeeper"),
                    home_passport.get("form")
                )
                logger.info(
                    "🔬 XG PIPELINE HOME KEYS | %s",
                    list(home_passport.keys())
                )
            else:
                logger.error(
                    "❌ XG PIPELINE HOME PASSPORT INVALID | type=%s",
                    type(home_passport).__name__
                )

            # ---------------------------------------------------------
            # Away passport structure
            # ---------------------------------------------------------
            if isinstance(away_passport, dict):
                logger.info(
                    "🔬 XG PIPELINE INPUT AWAY | "
                    "FLAT | attack=%s | defense=%s | "
                    "control=%s | goalkeeper=%s | form=%s",
                    away_passport.get("attack"),
                    away_passport.get("defense"),
                    away_passport.get("control"),
                    away_passport.get("goalkeeper"),
                    away_passport.get("form")
                )
                logger.info(
                    "🔬 XG PIPELINE AWAY KEYS | %s",
                    list(away_passport.keys())
                )
            else:
                logger.error(
                    "❌ XG PIPELINE AWAY PASSPORT INVALID | type=%s",
                    type(away_passport).__name__
                )

            # =========================================================
            # 2. XG MODEL (С ПРОВЕРКОЙ РЕЗУЛЬТАТА)
            # =========================================================
            xg_result = self.xg_model.calculate(
                home_passport=home_passport,
                away_passport=away_passport,
                home_rating=home_rating,
                away_rating=away_rating
            )

            # =========================================================
            # XG RESULT VALIDATION
            # =========================================================
            if not isinstance(xg_result, dict):
                raise ValueError(
                    f"XG Model returned invalid result: {type(xg_result)}"
                )

            if xg_result.get("status") != "success":
                raise ValueError(
                    f"XG Model calculation failed: "
                    f"{xg_result.get('message', 'unknown error')}"
                )

            if "home_xg" not in xg_result:
                raise ValueError("XG Model result missing home_xg")

            if "away_xg" not in xg_result:
                raise ValueError("XG Model result missing away_xg")

            home_xg = float(xg_result["home_xg"])
            away_xg = float(xg_result["away_xg"])

            # =========================================================
            # XG RANGE
            # =========================================================
            home_xg = max(config.XG_MIN, min(config.XG_MAX, home_xg))
            away_xg = max(config.XG_MIN, min(config.XG_MAX, away_xg))

            logger.info(
                "XG PIPELINE RESULT | "
                "%s vs %s | home_xg=%.3f | away_xg=%.3f",
                home_team,
                away_team,
                home_xg,
                away_xg
            )

            # =========================================================
            # 3. ПОЛУЧАЕМ КОМПОНЕНТЫ ДЛЯ ДИАГНОСТИКИ
            # =========================================================
            components = xg_result.get("components", {})

            diagnostic = {
                "raw_xg_home": round(xg_result.get("home_xg", home_xg), 3),
                "raw_xg_away": round(xg_result.get("away_xg", away_xg), 3),

                "home_attack_factor": components.get("home_attack_factor", 1.0),
                "away_attack_factor": components.get("away_attack_factor", 1.0),

                "home_defense_factor": components.get("home_defense_factor", 1.0),
                "away_defense_factor": components.get("away_defense_factor", 1.0),

                "home_keeper_factor": components.get("home_keeper_factor", 1.0),
                "away_keeper_factor": components.get("away_keeper_factor", 1.0),

                "home_control_factor": components.get("home_control_factor", 1.0),
                "away_control_factor": components.get("away_control_factor", 1.0),

                "home_advantage": components.get("home_advantage", config.HOME_ADVANTAGE),

                "home_form": components.get("home_form_factor", 1.0),
                "away_form": components.get("away_form_factor", 1.0),

                "home_rating": round(home_rating, 1),
                "away_rating": round(away_rating, 1),

                "rating_used_for_xg": False  # FAJ Rating не участвует в xG
            }

            # =========================================================
            # 4. POISSON MODEL (С include_matrix=True ДЛЯ TOP_SCORES)
            # =========================================================
            poisson_result = self.poisson_model.calculate(
                home_xg,
                away_xg,
                include_matrix=True
            )

            if poisson_result.get("status") == "error":
                raise ValueError(
                    f"Poisson calculation failed: "
                    f"{poisson_result.get('message', 'unknown error')}"
                )

            probs = poisson_result.get("result_probability", {})

            # =========================================================
            # 5. MONTE CARLO
            # =========================================================
            seed = self._build_seed(
                home_team,
                away_team,
                home_rating,
                away_rating,
                home_xg,
                away_xg
            )

            mc_result = self.monte_carlo_model.simulate(
                home_xg,
                away_xg,
                iterations=config.MONTE_CARLO_ITERATIONS,
                seed=seed if config.MONTE_CARLO_REPRODUCIBLE else None
            )

            # =========================================================
            # 6. MODEL AGREEMENT
            # =========================================================
            agreement_score = self._calculate_model_agreement(poisson_result, mc_result)

            model_agreement = {
                "score": round(agreement_score, 3),
                "level": self._agreement_level(agreement_score)
            }

            # =========================================================
            # 7. RAW PREDICTION
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
            # 8. CALIBRATION
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
            # 9. CONFIDENCE
            # =========================================================
            confidence_result = self.confidence_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated={"home": home_prob, "draw": draw_prob, "away": away_prob}
            )

            # =========================================================
            # 10. RISK
            # =========================================================
            risk_result = self.risk_engine.calculate(
                raw_prediction=raw_prediction,
                calibrated={"home": home_prob, "draw": draw_prob, "away": away_prob},
                confidence=confidence_result
            )

            # =========================================================
            # 11. РАСШИРЕННЫЕ МЕТРИКИ
            # =========================================================
            extended = self._calculate_extended_metrics(
                home_xg=home_xg,
                away_xg=away_xg,
                poisson_top_scores=poisson_result.get("top_scores", []),
                score_matrix=poisson_result.get("score_matrix", {})
            )

            # =========================================================
            # 12. РЕЗУЛЬТАТ
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
                "extended": extended,
                "diagnostic": diagnostic,
                "version": self.VERSION,
                "processing_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
            }

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "prediction_id": prediction_id
            }

    # ============================================================
    # PRIVATE METHODS
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
            f"{home}_{away}_{self.VERSION}_"
            f"{home_rating:.1f}_{away_rating:.1f}_"
            f"{home_xg:.2f}_{away_xg:.2f}_"
            f"{config.SEASON_START}"
        )
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def _calculate_model_agreement(
        self,
        poisson_result: Dict,
        mc_result: Dict
    ) -> float:
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
    # _calculate_extended_metrics (С ДИАГНОСТИКОЙ И FALLBACK)
    # ============================================================

    def _calculate_extended_metrics(
        self,
        home_xg: float,
        away_xg: float,
        poisson_top_scores: List[Dict[str, Any]],
        score_matrix: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Расчёт расширенных метрик для UI.
        """
        # =========================================================
        # ДИАГНОСТИКА ВХОДНЫХ ДАННЫХ
        # =========================================================
        logger.info("🔬 EXTENDED METRICS INPUT:")
        logger.info("  home_xg=%.3f, away_xg=%.3f", home_xg, away_xg)
        logger.info("  poisson_top_scores: %s", poisson_top_scores[:3] if poisson_top_scores else "EMPTY")
        
        if score_matrix:
            keys = list(score_matrix.keys())[:5]
            items = list(score_matrix.items())[:3]
            logger.info("  score_matrix keys (first 5): %s", keys)
            logger.info("  score_matrix items (first 3): %s", items)
        else:
            logger.info("  score_matrix: EMPTY")

        # =========================================================
        # ТОП-5 СЧЕТОВ
        # =========================================================
        top_scores = []

        # Вариант 1: из poisson_top_scores
        if poisson_top_scores:
            top_scores = poisson_top_scores[:5]
            logger.info("  ✅ Using poisson_top_scores: %s", top_scores)

        # Вариант 2: из score_matrix (если top_scores пустой)
        elif score_matrix:
            logger.info("  ⚠️ poisson_top_scores empty, building from score_matrix")
            sorted_scores = sorted(score_matrix.items(), key=lambda x: x[1], reverse=True)
            for i, (score_str, prob) in enumerate(sorted_scores[:5]):
                try:
                    if ':' in score_str:
                        home, away = score_str.split(':')
                    elif '-' in score_str:
                        home, away = score_str.split('-')
                    else:
                        continue
                    top_scores.append({
                        'rank': i + 1,
                        'home': int(home),
                        'away': int(away),
                        'probability': round(prob, 4),
                        'prob_percent': f"{prob * 100:.2f}%"
                    })
                except (ValueError, AttributeError) as e:
                    logger.warning("  Failed to parse score: %s, error: %s", score_str, e)
                    continue
            logger.info("  ✅ Built top_scores from score_matrix: %s", top_scores)

        # Вариант 3: fallback из xG
        else:
            logger.warning("  ❌ No top_scores and no score_matrix, using fallback")
            top_scores = self._get_fallback_top_scores(home_xg, away_xg)
            logger.info("  ✅ Built fallback top_scores: %s", top_scores)

        # =========================================================
        # BTTS (Обе забьют) — из score_matrix
        # =========================================================
        btts_prob = 0.0
        if score_matrix:
            for score_str, prob in score_matrix.items():
                try:
                    if ':' in score_str:
                        home, away = score_str.split(':')
                    elif '-' in score_str:
                        home, away = score_str.split('-')
                    else:
                        continue
                    if int(home) > 0 and int(away) > 0:
                        btts_prob += prob
                except (ValueError, AttributeError):
                    continue
        else:
            # Fallback: approximative BTTS из xG
            btts_prob = (1 - math.exp(-home_xg * 0.5)) * (1 - math.exp(-away_xg * 0.5))

        btts_prob = min(btts_prob, 1.0)

        # =========================================================
        # ТОТАЛЫ — из score_matrix
        # =========================================================
        over_25 = 0.0
        over_35 = 0.0

        if score_matrix:
            for score_str, prob in score_matrix.items():
                try:
                    if ':' in score_str:
                        home, away = score_str.split(':')
                    elif '-' in score_str:
                        home, away = score_str.split('-')
                    else:
                        continue
                    total = int(home) + int(away)
                    if total > 2.5:
                        over_25 += prob
                    if total > 3.5:
                        over_35 += prob
                except (ValueError, AttributeError):
                    continue
        else:
            # Fallback: approximative totals из xG
            # Poisson approximation for over 2.5
            home_goals_prob = 1 - math.exp(-home_xg) * (1 + home_xg + home_xg**2/2)
            away_goals_prob = 1 - math.exp(-away_xg) * (1 + away_xg + away_xg**2/2)
            over_25 = home_goals_prob + away_goals_prob - home_goals_prob * away_goals_prob

        over_25 = min(over_25, 1.0)
        over_35 = min(over_35, 1.0)

        # =========================================================
        # САМЫЙ ВЕРОЯТНЫЙ СЧЁТ
        # =========================================================
        most_likely = {'home': 0, 'away': 0, 'prob': 0}

        if top_scores and isinstance(top_scores[0], dict):
            # Формат из poisson_top_scores: {"score": "0:1", "probability": 0.139}
            if 'score' in top_scores[0]:
                try:
                    score_str = top_scores[0]['score']
                    if ':' in score_str:
                        home, away = score_str.split(':')
                    elif '-' in score_str:
                        home, away = score_str.split('-')
                    else:
                        home, away = '0', '0'
                    most_likely = {
                        'home': int(home),
                        'away': int(away),
                        'prob': top_scores[0].get('probability', 0)
                    }
                except (ValueError, AttributeError, KeyError):
                    pass
            # Формат из нашего построения: {"home": 0, "away": 1, "probability": 0.139}
            elif 'home' in top_scores[0] and 'away' in top_scores[0]:
                most_likely = {
                    'home': top_scores[0].get('home', 0),
                    'away': top_scores[0].get('away', 0),
                    'prob': top_scores[0].get('probability', 0)
                }

        return {
            "top_scores": top_scores,
            "most_likely_score": {
                "home": most_likely.get('home', 0),
                "away": most_likely.get('away', 0),
                "prob": most_likely.get('prob', 0)
            },
            "btts": {
                "yes": round(btts_prob, 4),
                "no": round(1 - btts_prob, 4)
            },
            "total": {
                "over_2_5": round(over_25, 4),
                "under_2_5": round(1 - over_25, 4),
                "over_3_5": round(over_35, 4),
                "under_3_5": round(1 - over_35, 4)
            }
        }

    def _get_fallback_top_scores(
        self,
        home_xg: float,
        away_xg: float,
        max_goals: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fallback расчёт топ-счетов на основе xG.
        Используется только если Poisson модель не вернула данные.
        """
        def poisson_prob(lam: float, k: int) -> float:
            if lam <= 0:
                return 1.0 if k == 0 else 0.0
            return math.exp(-lam) * (lam ** k) / math.factorial(k)

        scores = []
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = poisson_prob(home_xg, home_goals) * poisson_prob(away_xg, away_goals)
                scores.append({
                    'home': home_goals,
                    'away': away_goals,
                    'probability': prob
                })

        scores.sort(key=lambda x: x['probability'], reverse=True)

        top_scores = []
        for i, score in enumerate(scores[:5]):
            if score['probability'] < 0.001:
                break
            top_scores.append({
                'rank': i + 1,
                'home': score['home'],
                'away': score['away'],
                'probability': round(score['probability'], 4),
                'prob_percent': f"{score['probability'] * 100:.2f}%"
            })

        return top_scores


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
