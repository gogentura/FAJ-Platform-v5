# =====================================================
# FAJ Platform v7.0.1
# app/services/prediction_pipeline.py
#
# Unified Prediction Pipeline
# Compatible with FAJ Core v7
# =====================================================
import logging
from app.core.faj_core import FAJCore
from app.core.risk_engine import risk_engine

logger = logging.getLogger(__name__)
MODEL_VERSION = "FAJ Platform v7.0.1"

# =====================================================
# CORE
# =====================================================
faj_core = FAJCore()

# =====================================================
# SAFE FLOAT
# =====================================================
def safe_float(value):
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0

# =====================================================
# MAIN PIPELINE
# =====================================================
def predict_match_pipeline(
    fixture,
    home_passport=None,
    away_passport=None
):
    """
    Unified Prediction Pipeline
    fixture = dict from fixtures table
    home_passport / away_passport
    оставлены только ради совместимости
    """
    try:
        home_team = fixture.get("home_team")
        away_team = fixture.get("away_team")
        league = fixture.get("league", "RPL")
        logger.info(
            "Prediction: %s - %s",
            home_team,
            away_team
        )
        # ==========================================
        # FAJ CORE
        # ==========================================
        prediction = faj_core.predict_match(
            home_team,
            away_team,
            league
        )
        if prediction is None:
            logger.warning(
                "Prediction is empty."
            )
            return None
        # ==========================================
        # DECISION
        # ==========================================
        decision = prediction.get(
            "decision",
            {}
        )
        xg = prediction.get(
            "xg",
            {}
        )
        predicted = xg.get(
            "predicted",
            {}
        )
        xg_home = safe_float(
            predicted.get(
                "home",
                0
            )
        )
        xg_away = safe_float(
            predicted.get(
                "away",
                0
            )
        )
        confidence = safe_float(
            decision.get(
                "confidence",
                0
            )
        )
        winner_probability = safe_float(
            decision.get(
                "winner_probability",
                confidence
            )
        )
        home_rating = safe_float(
            prediction.get(
                "home_rating",
                0
            )
        )
        away_rating = safe_float(
            prediction.get(
                "away_rating",
                0
            )
        )
        # ==========================================
        # RISK ENGINE
        # ==========================================
        try:
            risk = risk_engine.analyze(
                confidence=confidence,
                home_rating=home_rating,
                away_rating=away_rating,
                winner_probability=winner_probability,
                xg_home=xg_home,
                xg_away=xg_away
            )
        except Exception as e:
            logger.warning(
                "Risk Engine skipped: %s",
                e
            )
            risk = {
                "risk": "Не определён",
                "grade": "C",
                "grade_name": "Высокий риск"
            }
        # ==========================================
        # FINAL RESULT
        # ==========================================
        result = prediction.copy()
        result.update({
            "winner": decision.get(
                "winner"
            ),
            "winner_name": decision.get(
                "winner_name"
            ),
            "winner_probability": winner_probability,
            "home_probability": decision.get(
                "home_probability",
                0
            ),
            "draw_probability": decision.get(
                "draw_probability",
                0
            ),
            "away_probability": decision.get(
                "away_probability",
                0
            ),
            "expected_score": decision.get(
                "expected_score"
            ),
            "confidence": confidence,
            "home_rating": home_rating,
            "away_rating": away_rating,
            "xg_home": xg_home,
            "xg_away": xg_away,
            "model_version": MODEL_VERSION,
            "risk": risk.get(
                "risk",
                "Средний"
            ),
            "grade": risk.get(
                "grade",
                "C"
            ),
            "grade_name": risk.get(
                "grade_name",
                "Высокий риск"
            )
        })
        logger.info(
            "Prediction completed."
        )
        return result
    except Exception as e:
        logger.exception(
            "Prediction Pipeline error: %s",
            e
        )
        return None

# =====================================================
# COMPATIBILITY
# =====================================================
def predict_match(
    fixture,
    home_passport=None,
    away_passport=None
):
    return predict_match_pipeline(
        fixture,
        home_passport,
        away_passport
    )

# =====================================================
# CLASS
# =====================================================
class PredictionPipeline:
    def predict_match(
        self,
        fixture,
        home_passport=None,
        away_passport=None
    ):
        return predict_match_pipeline(
            fixture,
            home_passport,
            away_passport
        )

prediction_pipeline = PredictionPipeline()

# =====================================================
# END
# =====================================================
