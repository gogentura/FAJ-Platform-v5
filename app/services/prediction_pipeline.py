# =====================================================
# FAJ Platform v6.9.1
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
#
# Fixture
#   ↓
# FAJCore
#   ↓
# Prediction Output
#
# Compatible:
# - FAJCore v6.8+
# - debug_prediction
# - generate_tour
# - prediction_manager
# - PostgreSQL
# =====================================================

import logging
from datetime import datetime

from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)


# =====================================================
# SAFE CONVERTER
# =====================================================

def safe_float(value, default=0):

    try:

        if value is None:
            return default

        return float(value)

    except Exception:

        return default



# =====================================================
# CLEAN NUMPY / JSON
# =====================================================

def clean_prediction(data):

    if data is None:
        return {}

    if isinstance(data, dict):

        result = {}

        for key, value in data.items():

            if isinstance(value, dict):

                result[key] = clean_prediction(value)

            elif isinstance(value, list):

                result[key] = [
                    clean_prediction(v)
                    if isinstance(v, dict)
                    else v
                    for v in value
                ]

            else:

                try:
                    result[key] = value.item()

                except Exception:

                    result[key] = value


        return result


    return data



# =====================================================
# EXTRACT DECISION
# =====================================================

def extract_decision(raw):

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


    VERSION = "6.9.1"



    def __init__(self, core=None):

        self.core = core or FAJCore()



    # =================================================
    # MAIN
    # =================================================

    def run(
        self,
        home_team,
        away_team,
        league="RPL",
        season="2026/27"
    ):


        started = datetime.now()


        raw = self.core.predict_match(
            home_team,
            away_team,
            league
        )


        result = self.normalize(
            raw
        )


        result.update({

            "home_team":
                home_team,

            "away_team":
                away_team,

            "league":
                league,

            "season":
                season,

            "pipeline_version":
                self.VERSION,

            "processing_time":
                str(
                    datetime.now()-started
                )

        })


        return result





    # =================================================
    # NORMALIZE
    # =================================================

    def normalize(self, raw):


        raw = clean_prediction(raw)


        decision = extract_decision(raw)


        simulation = raw.get(
            "simulation",
            {}
        )


        xg = raw.get(
            "xg",
            {}
        ).get(
            "predicted",
            {}
        )


        # -----------------------------
        # winner
        # -----------------------------

        winner = decision.get(
            "winner"
        )


        winner_name = decision.get(
            "winner_name"
        )


        if not winner:

            home = simulation.get(
                "home_win_prob",
                0
            )

            draw = simulation.get(
                "draw_prob",
                0
            )

            away = simulation.get(
                "away_win_prob",
                0
            )


            if home >= draw and home >= away:

                winner="home"
                winner_name="Хозяева"


            elif away >= home and away >= draw:

                winner="away"
                winner_name="Гости"


            else:

                winner="draw"
                winner_name="Ничья"




        # -----------------------------
        # score
        # -----------------------------

        score = decision.get(
            "expected_score"
        )


        if not score:

            top = simulation.get(
                "top_scores",
                []
            )


            if top:

                score = top[0].get(
                    "score"
                )

            else:

                score="-"




        # -----------------------------
        # xG
        # -----------------------------

        xg_home = safe_float(
            xg.get(
                "home"
            )
        )


        xg_away = safe_float(
            xg.get(
                "away"
            )
        )



        # -----------------------------
        # ratings
        # -----------------------------

        home_rating = safe_float(
            decision.get(
                "home_rating",
                raw.get(
                    "home_rating"
                )
            )
        )


        away_rating = safe_float(
            decision.get(
                "away_rating",
                raw.get(
                    "away_rating"
                )
            )
        )



        # -----------------------------
        # confidence
        # -----------------------------

        confidence = safe_float(
            decision.get(
                "confidence",
                raw.get(
                    "confidence"
                )
            )
        )



        # -----------------------------
        # probabilities
        # -----------------------------

        home_prob = safe_float(
            decision.get(
                "home_probability",
                simulation.get(
                    "home_win_prob",
                    0
                )*100
            )
        )


        draw_prob = safe_float(
            decision.get(
                "draw_probability",
                simulation.get(
                    "draw_prob",
                    0
                )*100
            )
        )


        away_prob = safe_float(
            decision.get(
                "away_probability",
                simulation.get(
                    "away_win_prob",
                    0
                )*100
            )
        )



        return {


            "winner":
                winner,


            "winner_name":
                winner_name,


            "expected_score":
                score,


            "xg_home":
                round(xg_home,2),


            "xg_away":
                round(xg_away,2),


            "home_probability":
                round(home_prob,1),


            "draw_probability":
                round(draw_prob,1),


            "away_probability":
                round(away_prob,1),


            "home_rating":
                round(home_rating,1),


            "away_rating":
                round(away_rating,1),


            "confidence":
                round(confidence,1),


            "risk":
                self.calculate_risk(
                    confidence
                ),


            "category":
                self.calculate_category(
                    confidence
                ),


            "factors":
                self.generate_factors(
                    xg_home,
                    xg_away,
                    home_rating,
                    away_rating
                ),


            "season_phase":
                "start",


            "data_quality":
                {
                    "home":
                        100,

                    "away":
                        100
                }


        }




    # =================================================
    # RISK
    # =================================================

    def calculate_risk(self, confidence):

        if confidence >= 65:
            return "Низкий"

        if confidence >= 45:
            return "Средний"

        return "Высокий"



    # =================================================
    # CATEGORY
    # =================================================

    def calculate_category(self, confidence):

        if confidence >= 80:
            return "A"

        if confidence >= 60:
            return "B"

        return "C"



    # =================================================
    # FACTORS
    # =================================================

    def generate_factors(
        self,
        home_xg,
        away_xg,
        home_rating,
        away_rating
    ):


        factors=[]


        if home_xg > away_xg:

            factors.append(
                "🏹 Преимущество хозяев в атаке"
            )

        elif away_xg > home_xg:

            factors.append(
                "🏹 Преимущество гостей в атаке"
            )


        if abs(home_xg-away_xg)>0.3:

            if home_xg>away_xg:

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
# PUBLIC FUNCTIONS
# =====================================================


def predict_match_pipeline(
    home_team,
    away_team,
    league="RPL",
    core=None
):


    pipeline = PredictionPipeline(
        core
    )


    return pipeline.run(
        home_team,
        away_team,
        league
    )





# =====================================================
# BACKWARD COMPATIBILITY
# =====================================================


def prediction_pipeline(
    fixture,
    core=None
):


    return predict_match_pipeline(

        fixture.get(
            "home_team"
        ),

        fixture.get(
            "away_team"
        ),

        fixture.get(
            "league",
            "RPL"
        ),

        core

    )
