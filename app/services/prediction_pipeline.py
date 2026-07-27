# =====================================================
# FAJ Platform v6.9.3
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
#
# Flow:
#
# Fixture
#    ↓
# FAJCore
#    ↓
# xG Engine
#    ↓
# Confidence Calibration Layer
#    ↓
# Prediction Manager
#
# Compatible:
# - FAJCore v6.8+
# - confidence_engine v6.9.3
# - debug_prediction
# - generate_predictions
# - PostgreSQL
# =====================================================
import logging
from datetime import datetime
from app.core.faj_core import FAJCore
from app.core.confidence_engine import (
    calculate_confidence
)

logger = logging.getLogger(__name__)

# =====================================================
# SAFE FLOAT
# =====================================================
def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default

# =====================================================
# CLEAN DATA
# =====================================================
def clean_prediction(data):
    """
    Converts numpy/dataclass values
    into safe Python objects
    """
    if data is None:
        return {}
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = clean_prediction(value)
            elif isinstance(value, list):
                result[key] = [
                    clean_prediction(item)
                    for item in value
                ]
            else:
                try:
                    result[key] = value.item()
                except Exception:
                    result[key] = value
        return result
    if isinstance(data, list):
        return [
            clean_prediction(item)
            for item in data
        ]
    return data

# =====================================================
# EXTRACT CORE DATA
# =====================================================
def extract_block(raw, key):
    value = raw.get(key, {})
    if isinstance(value, dict):
        return value
    return {}

# =====================================================
# PIPELINE CLASS
# =====================================================
class PredictionPipeline:
    VERSION = "6.9.3"

    def __init__(self, core=None):
        self.core = core or FAJCore()

    # =================================================
    # MAIN ENTRY
    # =================================================
    def predict_match_pipeline(
        self,
        home_team,
        away_team,
        league="RPL",
        season="2026/27"
    ):
        started = datetime.now()
        try:
            raw = self.core.predict_match(
                home_team,
                away_team,
                league
            )
            raw = clean_prediction(raw)
            result = self.normalize(raw, league)
            result.update(
                {
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": league,
                    "season": season,
                    "pipeline_version": self.VERSION,
                    "processing_time": str(
                        datetime.now() - started
                    )
                }
            )
            return result
        except Exception as e:
            logger.error(
                "FAJ pipeline error: %s",
                e,
                exc_info=True
            )
            raise

    # =================================================
    # NORMALIZE START
    # =================================================
    def normalize(self, raw, league="RPL"):
        raw = clean_prediction(raw)
        decision = extract_block(raw, "decision")
        if not decision:
            decision = raw
        simulation = extract_block(raw, "simulation")
        xg_block = extract_block(raw, "xg")
        return self.normalize_core(
            raw,
            decision,
            simulation,
            xg_block,
            league
        )

    # =================================================
    # CORE NORMALIZATION
    # =================================================
    def normalize_core(
        self,
        raw,
        decision,
        simulation,
        xg_block,
        league
    ):
        # =============================================
        # XG EXTRACTION
        # =============================================
        predicted_xg = xg_block.get("predicted", {})
        xg_home = safe_float(
            predicted_xg.get("home", raw.get("xg_home", 0))
        )
        xg_away = safe_float(
            predicted_xg.get("away", raw.get("xg_away", 0))
        )

        # =============================================
        # FAJ RATINGS
        # =============================================
        home_rating = safe_float(
            decision.get("home_rating", raw.get("home_rating", 0))
        )
        away_rating = safe_float(
            decision.get("away_rating", raw.get("away_rating", 0))
        )

        # =============================================
        # WINNER
        # =============================================
        winner = decision.get("winner", raw.get("winner", "-"))
        if winner is None:
            winner = "-"
        winner_name = decision.get("winner_name", "-")
        if winner_name == "-":
            if winner == "home":
                winner_name = "Хозяева"
            elif winner == "away":
                winner_name = "Гости"
            elif winner == "draw":
                winner_name = "Ничья"

        # =============================================
        # SCORE
        # =============================================
        expected_score = decision.get(
            "expected_score",
            raw.get("expected_score", "-")
        )
        if not expected_score:
            top_scores = simulation.get("top_scores", [])
            if top_scores:
                expected_score = top_scores[0].get("score", "-")
            else:
                expected_score = "-"

        # =============================================
        # MONTE CARLO PROBABILITIES
        # =============================================
        home_probability = safe_float(
            decision.get(
                "home_probability",
                simulation.get("home_win_prob", 0) * 100
            )
        )
        draw_probability = safe_float(
            decision.get(
                "draw_probability",
                simulation.get("draw_prob", 0) * 100
            )
        )
        away_probability = safe_float(
            decision.get(
                "away_probability",
                simulation.get("away_win_prob", 0) * 100
            )
        )

        # =============================================
        # CONFIDENCE CALIBRATION LAYER
        # =============================================
        confidence_data = calculate_confidence(
            xg_home=xg_home,
            xg_away=xg_away,
            rating_home=home_rating,
            rating_away=away_rating,
            quality_home=1,
            quality_away=1,
            season_phase="start",
            home_advantage=True
        )
        confidence = confidence_data.get("confidence", 0)
        risk = confidence_data.get("risk", "Высокий")
        category = confidence_data.get("category", "C")

        # =============================================
        # FACTORS
        # =============================================
        factors = self.generate_factors(
            xg_home,
            xg_away,
            home_rating,
            away_rating
        )

        # =============================================
        # FINAL OBJECT
        # =============================================
        result = {
            "winner": winner,
            "winner_name": winner_name,
            "expected_score": expected_score,
            "xg_home": round(xg_home, 2),
            "xg_away": round(xg_away, 2),
            "home_rating": round(home_rating, 1),
            "away_rating": round(away_rating, 1),
            "home_probability": round(home_probability, 1),
            "draw_probability": round(draw_probability, 1),
            "away_probability": round(away_probability, 1),
            "confidence": confidence,
            "risk": risk,
            "category": category,
            "grade": category,  # compatibility with old handlers
            "season_phase": "start",
            "data_quality": {"home": 100, "away": 100},
            "passport_quality": {"home": 1, "away": 1},
            "factors": factors
        }
        return result

    # =================================================
    # RISK FALLBACK
    # =================================================
    def calculate_risk(self, confidence):
        confidence = safe_float(confidence)
        if confidence >= 70:
            return "Низкий"
        elif confidence >= 50:
            return "Средний"
        elif confidence >= 35:
            return "Высокий"
        return "Очень высокий"

    # =================================================
    # CATEGORY FALLBACK
    # =================================================
    def calculate_category(self, confidence):
        confidence = safe_float(confidence)
        if confidence >= 70:
            return "A"
        elif confidence >= 55:
            return "B"
        elif confidence >= 40:
            return "C"
        return "D"

    # =================================================
    # FACTORS ENGINE
    # =================================================
    def generate_factors(
        self,
        home_xg,
        away_xg,
        home_rating,
        away_rating
    ):
        factors = []
        # Attack
        if home_xg > away_xg:
            factors.append("🏹 Преимущество хозяев в атаке")
        elif away_xg > home_xg:
            factors.append("🏹 Преимущество гостей в атаке")

        # Defence / stability
        if home_rating > away_rating:
            factors.append("🛡 Более стабильная оборона хозяев")
        elif away_rating > home_rating:
            factors.append("🛡 Более стабильная оборона гостей")

        # xG advantage
        xg_diff = abs(home_xg - away_xg)
        if xg_diff >= 0.35:
            if home_xg > away_xg:
                factors.append(f"📈 xG преимущество хозяев ({home_xg:.2f})")
            else:
                factors.append(f"📈 xG преимущество гостей ({away_xg:.2f})")

        factors.append("🏆 Турнир: RPL")
        return factors


# =====================================================
# PUBLIC FUNCTION API
# =====================================================
def predict_match_pipeline(
    home_team,
    away_team,
    league="RPL",
    season="2026/27",
    core=None
):
    """
    Public adapter.
    Used by:
    - debug_prediction.py
    - handlers
    - external API
    """
    try:
        pipeline = PredictionPipeline(core=core)
        return pipeline.predict_match_pipeline(
            home_team,
            away_team,
            league,
            season
        )
    except Exception as e:
        logger.error(
            "Public pipeline error: %s",
            e,
            exc_info=True
        )
        return {
            "winner": "-",
            "winner_name": "-",
            "expected_score": "-",
            "xg_home": 0,
            "xg_away": 0,
            "home_rating": 0,
            "away_rating": 0,
            "confidence": 0,
            "risk": "Очень высокий",
            "category": "D",
            "grade": "D",
            "factors": []
        }


# =====================================================
# EXPORTS
# =====================================================
__all__ = [
    "PredictionPipeline",
    "predict_match_pipeline"
]
