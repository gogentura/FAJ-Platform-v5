# =====================================================
# FAJ Platform v6.5
# app/services/prediction_pipeline.py
# =====================================================

import logging

from app.core.faj_core import FAJCore
from app.passport_manager import (
    load_passport,
    get_team_by_alias
)
from app.core.risk_engine import risk_engine
from app.utils.explainer import explain_prediction


logger = logging.getLogger(__name__)

core = FAJCore()


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
# LOAD PASSPORT
# =====================================================

def get_passport(team):

    try:

        real_team = get_team_by_alias(team)

        if real_team:
            team = real_team

        passport = load_passport(team)

        return passport or {}

    except Exception as e:

        logger.error(
            f"Passport error {team}: {e}"
        )

        return {}


# =====================================================
# FAJ RATING
# =====================================================

def calculate_rating(passport):

    if not passport:
        return 0

    if passport.get("faj_rating"):

        return round(
            safe_float(
                passport["faj_rating"]
            ),
            1
        )

    rating = (

        safe_float(passport.get("attack")) * 0.25 +

        safe_float(passport.get("defense")) * 0.25 +

        safe_float(passport.get("control")) * 0.20 +

        safe_float(passport.get("form")) * 0.20 +

        safe_float(passport.get("efficiency")) * 0.10

    )

    return round(rating, 1)


# =====================================================
# MAIN PIPELINE
# =====================================================

def predict_match_pipeline(

    home_team,
    away_team,
    league="RPL",
    season="2026/27"

):

    try:

        logger.info(
            f"FAJ pipeline start: {home_team} - {away_team}"
        )

        result = core.predict_match(

            home_team,
            away_team,
            league

        )

        if not result:
            return None

        xg = result.get("xg", {})
        predicted = xg.get("predicted", {})

        xg_home = safe_float(predicted.get("home"))
        xg_away = safe_float(predicted.get("away"))

        decision = result.get("decision", {})

        home_passport = get_passport(home_team)
        away_passport = get_passport(away_team)

        home_rating = calculate_rating(home_passport)
        away_rating = calculate_rating(away_passport)

        confidence = safe_float(
            decision.get("confidence", 0)
        )

        winner_probability = safe_float(
            decision.get("winner_probability", 0)
        )

        risk = risk_engine.analyze(

            confidence,
            home_rating,
            away_rating,
            winner_probability,
            xg_home,
            xg_away

        )

        factors = explain_prediction(

            home_passport,
            away_passport,
            xg_home,
            xg_away,
            league

        )

        prediction = {

            "home_team": home_team,
            "away_team": away_team,

            "league": league,
            "season": season,

            "xg_home": xg_home,
            "xg_away": xg_away,

            "winner": decision.get(
                "winner_name",
                decision.get("winner", "нет")
            ),

            "expected_score": decision.get(
                "expected_score",
                ""
            ),

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

            "winner_probability": winner_probability,

            "top_scores": result.get(
                "simulation",
                {}
            ).get(
                "top_scores",
                []
            ),

            "btts": result.get(
                "btts",
                0
            ),

            "over25": result.get(
                "over25",
                0
            ),

            "home_rating": home_rating,
            "away_rating": away_rating,

            "confidence": confidence,

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
                ""
            ),

            "factors": factors

        }

        logger.info(
            f"FAJ pipeline finished: {home_team} - {away_team}"
        )

        return prediction

    except Exception as e:

        logger.error(
            f"Pipeline error {home_team}-{away_team}: {e}",
            exc_info=True
        )

        return None


# =====================================================
# PREDICTION PIPELINE CLASS
# =====================================================

class PredictionPipeline:

    def __init__(self):

        logger.info(
            "PredictionPipeline initialized"
        )

    def predict_fixture(self, fixture):

        try:

            return predict_match_pipeline(

                home_team=fixture["home_team"],

                away_team=fixture["away_team"],

                league=fixture.get(
                    "league",
                    "RPL"
                ),

                season=fixture.get(
                    "season",
                    "2026/27"
                )

            )

        except Exception as e:

            logger.exception(e)

            return None
