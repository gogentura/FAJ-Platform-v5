# =====================================================
# FAJ Platform v6.9
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
#
# Adapter:
# Fixture
#   ↓
# FAJCore
#   ↓
# Prediction Manager
#
# Compatible:
# - FAJCore v6.8
# - generate_tour
# - debug_prediction
# - PostgreSQL
# =====================================================
import logging
from datetime import datetime
from app.core.faj_core import FAJCore

logger = logging.getLogger(__name__)

# =====================================================
# SAFE VALUE
# =====================================================
def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default

# =====================================================
# CLEAN RESPONSE
# =====================================================
def clean_prediction(data):
    """
    Приводит ответ FAJ Core к безопасному виду
    """
    if not data:
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
                except AttributeError:
                    result[key] = value
        return result
    if isinstance(data, list):
        return [
            clean_prediction(item)
            for item in data
        ]
    return data

# =====================================================
# EXTRACT DECISION
# =====================================================
def extract_decision(raw):
    """
    Совместимость двух форматов:
    Старый FAJ Core:
    {
        decision:{
            winner,
            expected_score
        }
    }
    Новый FAJ Core:
    {
        winner,
        expected_score
    }
    """
    decision = raw.get(
        "decision",
        {}
    )
    if not decision:
        decision = raw
    return decision

# =====================================================
# PIPELINE CLASS
# =====================================================
class PredictionPipeline:
    VERSION = "6.9"

    def __init__(
        self,
        core=None
    ):
        self.core = core or FAJCore()

    # =================================================
    # MAIN PIPELINE
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
            raw = clean_prediction(
                raw
            )
            prediction = self.normalize(
                raw
            )
            prediction["home_team"] = home_team
            prediction["away_team"] = away_team
            prediction["league"] = league
            prediction["season"] = season
            prediction["pipeline_version"] = self.VERSION
            prediction["processing_time"] = str(
                datetime.now() - started
            )
            return prediction
        except Exception as e:
            logger.error(
                "FAJ pipeline error: %s",
                e,
                exc_info=True
            )
            raise

    # =====================================================
    # NORMALIZE CORE RESPONSE
    # =====================================================
    def normalize(
        self,
        raw
    ):
        raw = clean_prediction(
            raw
        )
        decision = extract_decision(
            raw
        )
        simulation = raw.get(
            "simulation",
            {}
        )
        xg_block = raw.get(
            "xg",
            {}
        )
        xg_pred = xg_block.get(
            "predicted",
            {}
        )
        # ---------------------------------------------
        # WINNER
        # ---------------------------------------------
        winner = decision.get(
            "winner"
        )
        winner_name = decision.get(
            "winner_name"
        )
        if not winner:
            winner = "-"
        if not winner_name:
            if winner == "home":
                winner_name = "Хозяева"
            elif winner == "away":
                winner_name = "Гости"
            elif winner == "draw":
                winner_name = "Ничья"
            else:
                winner_name = "-"
        # ---------------------------------------------
        # SCORE
        # ---------------------------------------------
        expected_score = decision.get(
            "expected_score",
            ""
        )
        if not expected_score:
            scores = simulation.get(
                "top_scores",
                []
            )
            if scores:
                expected_score = scores[0].get(
                    "score",
                    "-"
                )
            else:
                expected_score = "-"
        # ---------------------------------------------
        # XG
        # ---------------------------------------------
        xg_home = safe_float(
            xg_pred.get(
                "home",
                raw.get(
                    "xg_home",
                    0
                )
            )
        )
        xg_away = safe_float(
            xg_pred.get(
                "away",
                raw.get(
                    "xg_away",
                    0
                )
            )
        )
        # ---------------------------------------------
        # RATINGS
        # ---------------------------------------------
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
        # ---------------------------------------------
        # PROBABILITIES
        # ---------------------------------------------
        home_probability = safe_float(
            decision.get(
                "home_probability",
                simulation.get(
                    "home_win_prob",
                    0
                ) * 100
            )
        )
        draw_probability = safe_float(
            decision.get(
                "draw_probability",
                simulation.get(
                    "draw_prob",
                    0
                ) * 100
            )
        )
        away_probability = safe_float(
            decision.get(
                "away_probability",
                simulation.get(
                    "away_win_prob",
                    0
                ) * 100
            )
        )
        # ---------------------------------------------
        # CONFIDENCE
        # ---------------------------------------------
        confidence = safe_float(
            decision.get(
                "confidence",
                raw.get(
                    "confidence",
                    0
                )
            )
        )
        # ---------------------------------------------
        # RISK
        # ---------------------------------------------
        risk = self.calculate_risk(
            confidence
        )
        # ---------------------------------------------
        # CATEGORY
        # ---------------------------------------------
        category = self.calculate_category(
            confidence
        )
        # ---------------------------------------------
        # FACTORS
        # ---------------------------------------------
        factors = self.generate_factors(
            xg_home,
            xg_away,
            home_rating,
            away_rating,
            winner
        )
        return {
            "winner":
                winner,
            "winner_name":
                winner_name,
            "home_probability":
                round(home_probability,1),
            "draw_probability":
                round(draw_probability,1),
            "away_probability":
                round(away_probability,1),
            "xg_home":
                round(xg_home,2),
            "xg_away":
                round(xg_away,2),
            "expected_score":
                expected_score,
            "top_scores":
                simulation.get(
                    "top_scores",
                    []
                ),
            "confidence":
                round(confidence,1),
            "risk":
                risk,
            "category":
                category,
            "home_rating":
                round(home_rating,1),
            "away_rating":
                round(away_rating,1),
            "factors":
                factors,
            "season_phase":
                "start",
            "data_quality":
                {
                    "home":100,
                    "away":100
                }
        }

    # =====================================================
    # RISK CALCULATION
    # =====================================================
    def calculate_risk(
        self,
        confidence
    ):
        confidence = float(
            confidence or 0
        )
        if confidence >= 70:
            return "Низкий"
        elif confidence >= 50:
            return "Средний"
        else:
            return "Высокий"

    # =====================================================
    # CATEGORY
    # =====================================================
    def calculate_category(
        self,
        confidence
    ):
        confidence = float(
            confidence or 0
        )
        if confidence >= 80:
            return "A"
        elif confidence >= 65:
            return "B"
        else:
            return "C"

    # =====================================================
    # FACTORS
    # =====================================================
    def generate_factors(
        self,
        home_xg,
        away_xg,
        home_rating,
        away_rating,
        winner
    ):
        factors = []
        if home_xg > away_xg:
            factors.append(
                "🏹 Преимущество хозяев в атаке"
            )
        elif away_xg > home_xg:
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
        if abs(home_xg-away_xg) > 0.35:
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
# PUBLIC PIPELINE API
# =====================================================
def predict_match_pipeline(
    home_team,
    away_team,
    league="RPL",
    core=None
):
    try:
        if core is None:
            core = FAJCore()
        raw = core.predict_match(
            home_team,
            away_team,
            league
        )
        pipeline = PredictionPipeline()
        result = pipeline.normalize(
            raw
        )
        return result
    except Exception as e:
        logger.error(
            "FAJ pipeline error: %s",
            e,
            exc_info=True
        )
        return {
            "winner":"-",
            "winner_name":"-",
            "expected_score":"-",
            "xg_home":0,
            "xg_away":0,
            "home_rating":0,
            "away_rating":0,
            "confidence":0,
            "risk":"-",
            "category":"-",
            "factors":[]
        }
