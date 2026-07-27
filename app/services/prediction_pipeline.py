# =====================================================
# FAJ Platform v6.9.2
# app/services/prediction_pipeline.py
#
# Universal Prediction Pipeline
#
# Совместим с:
#  • FAJ Core v6.8+
#  • debug_prediction
#  • prediction_manager
#  • tour_predictor
# =====================================================
import logging
import numpy as np
from app.core.faj_core import FAJCore

logger = logging.getLogger(__name__)

# =====================================================
# CLEAN NUMPY
# =====================================================
def clean_numpy(value):
    if isinstance(value, np.generic):
        return value.item()
    return value

def clean_dict(data):
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if isinstance(v, dict):
                result[k] = clean_dict(v)
            elif isinstance(v, list):
                result[k] = [
                    clean_dict(x) if isinstance(x, dict)
                    else clean_numpy(x)
                    for x in v
                ]
            else:
                result[k] = clean_numpy(v)
        return result
    return data

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
# PIPELINE
# =====================================================
class PredictionPipeline:
    VERSION = "6.9.2"

    def __init__(self, core=None):
        if isinstance(core, FAJCore):
            self.core = core
        else:
            self.core = FAJCore()

    # ==============================================
    # MAIN
    # ==============================================
    def run(
        self,
        home_team,
        away_team,
        league="RPL"
    ):
        raw = self.core.predict_match(
            home_team,
            away_team,
            league
        )
        raw = clean_dict(raw)
        return self.normalize(raw)

    # ==============================================
    # NORMALIZE
    # ==============================================
    def normalize(self, raw):
        decision = raw.get("decision", {})
        simulation = raw.get("simulation", {})
        xg = raw.get(
            "xg",
            {}
        ).get(
            "predicted",
            {}
        )

        winner = decision.get("winner", "-")
        winner_name = decision.get("winner_name", "-")
        expected_score = decision.get("expected_score", "-")
        if expected_score == "-":
            scores = simulation.get(
                "top_scores",
                []
            )
            if scores:
                expected_score = scores[0].get(
                    "score",
                    "-"
                )

        home_rating = safe_float(
            decision.get(
                "home_rating",
                raw.get(
                    "home_rating",
                    0
                )
            )
        )
        away_rating = safe_float(
            decision.get(
                "away_rating",
                raw.get(
                    "away_rating",
                    0
                )
            )
        )
        confidence = safe_float(
            decision.get(
                "confidence",
                raw.get(
                    "confidence",
                    0
                )
            )
        )

        return {
            "winner": winner,
            "winner_name": winner_name,
            "expected_score": expected_score,
            "home_probability": safe_float(
                decision.get(
                    "home_probability",
                    simulation.get(
                        "home_win_prob",
                        0
                    ) * 100
                )
            ),
            "draw_probability": safe_float(
                decision.get(
                    "draw_probability",
                    simulation.get(
                        "draw_prob",
                        0
                    ) * 100
                )
            ),
            "away_probability": safe_float(
                decision.get(
                    "away_probability",
                    simulation.get(
                        "away_win_prob",
                        0
                    ) * 100
                )
            ),
            "xg_home": round(
                safe_float(
                    xg.get("home", 0)
                ),
                2
            ),
            "xg_away": round(
                safe_float(
                    xg.get("away", 0)
                ),
                2
            ),
            "home_rating": round(
                home_rating,
                1
            ),
            "away_rating": round(
                away_rating,
                1
            ),
            "confidence": round(
                confidence,
                1
            ),
            "top_scores": simulation.get(
                "top_scores",
                []
            ),
            "btts": raw.get(
                "btts",
                0
            ),
            "over25": raw.get(
                "over25",
                0
            ),
            "under25": raw.get(
                "under25",
                0
            ),
            "over15": raw.get(
                "over15",
                0
            ),
            "over35": raw.get(
                "over35",
                0
            ),
            # =====================================
            # NEW v6.9
            # =====================================
            "risk": self.calculate_risk(
                confidence
            ),
            "grade": self.calculate_grade(
                confidence
            ),
            "category": self.calculate_grade(
                confidence
            ),
            "season_phase": raw.get(
                "season_phase",
                "start"
            ),
            "passport_quality": raw.get(
                "passport_quality",
                {
                    "home": 100,
                    "away": 100
                }
            ),
            "factors": self.generate_factors(
                winner,
                home_rating,
                away_rating,
                safe_float(xg.get("home", 0)),
                safe_float(xg.get("away", 0))
            )
        }

    # ==============================================
    # RISK
    # ==============================================
    def calculate_risk(self, confidence):
        confidence = safe_float(confidence)
        if confidence >= 70:
            return "Низкий"
        elif confidence >= 50:
            return "Средний"
        return "Высокий"

    # ==============================================
    # CATEGORY
    # ==============================================
    def calculate_grade(self, confidence):
        confidence = safe_float(confidence)
        if confidence >= 80:
            return "A"
        elif confidence >= 65:
            return "B"
        return "C"

    # ==============================================
    # FACTORS
    # ==============================================
    def generate_factors(
        self,
        winner,
        home_rating,
        away_rating,
        home_xg,
        away_xg
    ):
        factors = []
        if winner == "home":
            factors.append(
                "🏹 Преимущество хозяев в атаке"
            )
        elif winner == "away":
            factors.append(
                "🏹 Преимущество гостей в атаке"
            )
        if home_rating > away_rating:
            factors.append(
                "🛡 Более стабильная оборона хозяев"
            )
        elif away_rating > home_rating:
            factors.append(
                "🛡 Более стабильная оборона гостей"
            )
        if abs(home_xg - away_xg) >= 0.35:
            if home_xg > away_xg:
                factors.append(
                    f"📈 xG преимущество хозяев ({home_xg:.2f})"
                )
            else:
                factors.append(
                    f"📈 xG преимущество гостей ({away_xg:.2f})"
                )
        factors.append(
            "🏆 Турнир: RPL"
        )
        return factors


# =====================================================
# PUBLIC API
# =====================================================
def predict_match_pipeline(
    home_team,
    away_team,
    league="RPL",
    core=None
):
    """
    Главная точка входа для всего проекта.
    Используется:
    - debug_prediction.py
    - tour_predictor.py
    - prediction_manager.py
    """
    try:
        pipeline = PredictionPipeline(core)
        return pipeline.run(
            home_team=home_team,
            away_team=away_team,
            league=league
        )
    except Exception as e:
        logger.exception(
            "Prediction pipeline failed"
        )
        return {
            "winner": "-",
            "winner_name": "-",
            "expected_score": "-",
            "home_probability": 0,
            "draw_probability": 0,
            "away_probability": 0,
            "xg_home": 0,
            "xg_away": 0,
            "home_rating": 0,
            "away_rating": 0,
            "confidence": 0,
            "risk": "Высокий",
            "grade": "C",
            "category": "C",
            "season_phase": "start",
            "passport_quality": {
                "home": 0,
                "away": 0
            },
            "top_scores": [],
            "btts": 0,
            "over15": 0,
            "over25": 0,
            "under25": 0,
            "over35": 0,
            "factors": []
        }

# =====================================================
# ALIAS
# (совместимость со старым кодом)
# =====================================================
prediction_pipeline = PredictionPipeline()

__all__ = [
    "PredictionPipeline",
    "predict_match_pipeline",
    "prediction_pipeline"
]
