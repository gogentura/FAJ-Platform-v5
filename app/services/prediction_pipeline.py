# =====================================================
# FAJ Platform v6.9.6
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
#
# Flow:
#
# Fixture
#    |
#    v
# FAJ Core
#    |
#    v
# xG Engine
#    |
#    v
# Monte Carlo
#    |
#    v
# Confidence
#    |
#    v
# Risk Engine
#    |
#    v
# Prediction
#
# =====================================================


import logging


from app.core.faj_core import FAJCore
from app.core.risk_engine import risk_engine


logger = logging.getLogger(__name__)


MODEL_VERSION = "FAJ v6.9.6"



# =====================================================
# CORE
# =====================================================

faj_core = FAJCore()



# =====================================================
# SAFE FLOAT
# =====================================================

def safe_float(value):

    try:
        return float(value)

    except Exception:
        return 0.0



# =====================================================
# MAIN PIPELINE
# =====================================================

def predict_match_pipeline(
        fixture,
        home_passport,
        away_passport
):

    try:

        home_team = fixture.get(
            "home_team",
            "-"
        )

        away_team = fixture.get(
            "away_team",
            "-"
        )


        logger.info(
            "FAJ prediction start: %s - %s",
            home_team,
            away_team
        )


        # =============================================
        # FAJ CORE
        # =============================================

        prediction = faj_core.predict_match(

            fixture,

            home_passport,

            away_passport

        )


        if not prediction:

            logger.warning(
                "FAJ Core returned empty prediction"
            )

            return None



        # =============================================
        # DATA
        # =============================================

        confidence = safe_float(
            prediction.get(
                "confidence",
                0
            )
        )


        xg_home = safe_float(
            prediction.get(
                "xg_home",
                0
            )
        )


        xg_away = safe_float(
            prediction.get(
                "xg_away",
                0
            )
        )


        home_rating = safe_float(

            home_passport.get(

                "faj_rating",

                home_passport.get(
                    "rating",
                    0
                )

            )

        )


        away_rating = safe_float(

            away_passport.get(

                "faj_rating",

                away_passport.get(
                    "rating",
                    0
                )

            )

        )



        winner_probability = safe_float(

            prediction.get(

                "winner_probability",

                confidence

            )

        )



        # =============================================
        # RISK ENGINE
        # =============================================

        try:

            risk = risk_engine.analyze(

                confidence,

                home_rating,

                away_rating,

                winner_probability,

                xg_home,

                xg_away

            )

        except Exception as e:

            logger.warning(
                "Risk engine skipped: %s",
                e
            )

            risk = {}



        # =============================================
        # ENRICH RESULT
        # =============================================

        prediction.update(

            {

                "model_version":
                    MODEL_VERSION,


                "risk":
                    risk.get(
                        "risk",
                        "Не определён"
                    ),


                "grade":
                    risk.get(
                        "grade",
                        "C"
                    ),


                "grade_name":
                    risk.get(
                        "grade_name",
                        "Высокий риск"
                    )

            }

        )


        logger.info(
            "FAJ prediction completed: %s - %s",
            home_team,
            away_team
        )


        return prediction



    except Exception as e:


        logger.exception(
            "FAJ pipeline error: %s",
            e
        )


        return None





# =====================================================
# COMPATIBILITY FUNCTION
# =====================================================

def predict_match(
        fixture,
        home_passport,
        away_passport
):

    return predict_match_pipeline(

        fixture,

        home_passport,

        away_passport

    )






# =====================================================
# COMPATIBILITY CLASS
# =====================================================

class PredictionPipeline:


    def predict_match(
            self,
            fixture,
            home_passport,
            away_passport
    ):

        return predict_match_pipeline(

            fixture,

            home_passport,

            away_passport

        )





# Старый импорт:
#
# from app.services.prediction_pipeline import prediction_pipeline
#
# работает.


prediction_pipeline = PredictionPipeline()



# =====================================================
# END
# =====================================================
