# =====================================================
# FAJ Platform v6.5
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
# =====================================================


import logging


from app.core.faj_core import FAJCore


from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


from app.core.risk_engine import (
    risk_engine
)


from app.utils.explainer import (
    explain_prediction
)



logger = logging.getLogger(__name__)




# =====================================================
# SAFE FLOAT
# =====================================================


def safe_float(
    value,
    default=0
):

    try:

        if value is None:
            return default


        return float(value)


    except Exception:

        return default





# =====================================================
# PIPELINE CLASS
# =====================================================


class PredictionPipeline:


    VERSION = "6.5"



    def __init__(self):


        self.core = FAJCore()



# =====================================================
# PASSPORT
# =====================================================


    def get_passport(

        self,

        team

    ):


        try:


            real_team = get_team_by_alias(

                team

            )


            if real_team:

                team = real_team



            passport = load_passport(

                team

            )


            return passport or {}



        except Exception as e:


            logger.error(

                f"Passport error {team}: {e}"

            )


            return {}





# =====================================================
# FAJ RATING
# =====================================================


    def calculate_rating(

        self,

        passport

    ):


        if not passport:

            return 0



        if passport.get(
            "faj_rating"
        ):


            return round(

                safe_float(

                    passport.get(
                        "faj_rating"
                    )

                ),

                1

            )



        rating = (


            safe_float(

                passport.get(
                    "attack"
                )

            )
            * 0.25



            +


            safe_float(

                passport.get(
                    "defense"
                )

            )
            * 0.25



            +


            safe_float(

                passport.get(
                    "control"
                )

            )
            * 0.20



            +


            safe_float(

                passport.get(
                    "form"
                )

            )
            * 0.20



            +


            safe_float(

                passport.get(
                    "efficiency"
                )

            )
            * 0.10


        )


        return round(

            rating,

            1

        )





# =====================================================
# MAIN PIPELINE
# =====================================================


    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL",

        season="2026/27"

    ):


        try:


            logger.info(

                f"Pipeline start {home_team}-{away_team}"

            )



            # ---------------------------------
            # CORE
            # ---------------------------------


            core_result = self.core.predict_match(

                home_team,

                away_team,

                league

            )



            if not core_result:


                raise Exception(

                    "FAJ Core empty response"

                )





            # ---------------------------------
            # XG
            # ---------------------------------


            xg = core_result.get(

                "xg",

                {}

            ).get(

                "predicted",

                {}

            )



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





            # ---------------------------------
            # PASSPORTS
            # ---------------------------------


            home_passport = self.get_passport(

                home_team

            )


            away_passport = self.get_passport(

                away_team

            )



            home_rating = self.calculate_rating(

                home_passport

            )


            away_rating = self.calculate_rating(

                away_passport

            )





            # ---------------------------------
            # DECISION
            # ---------------------------------


            decision = core_result.get(

                "decision",

                {}

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

                    0

                )

            )





            # ---------------------------------
            # RISK
            # ---------------------------------


            risk = risk_engine.analyze(

                confidence,

                home_rating,

                away_rating,

                winner_probability,

                xg_home,

                xg_away

            )





            # ---------------------------------
            # FACTORS
            # ---------------------------------


            factors = explain_prediction(

                home_passport,

                away_passport,

                xg_home,

                xg_away,

                league

            )





            # ---------------------------------
            # FINAL OBJECT
            # ---------------------------------


            prediction = {


                "home_team":

                    home_team,


                "away_team":

                    away_team,


                "league":

                    league,


                "season":

                    season,



                "winner":

                    decision.get(

                        "winner_name",

                        decision.get(

                            "winner",

                            ""

                        )

                    ),



                "expected_score":

                    decision.get(

                        "expected_score",

                        ""

                    ),



                "home_probability":

                    decision.get(

                        "home_probability",

                        0

                    ),



                "draw_probability":

                    decision.get(

                        "draw_probability",

                        0

                    ),



                "away_probability":

                    decision.get(

                        "away_probability",

                        0

                    ),



                "xg_home":

                    xg_home,


                "xg_away":

                    xg_away,



                "top_scores":

                    core_result.get(

                        "simulation",

                        {}

                    ).get(

                        "top_scores",

                        []

                    ),



                "btts":

                    core_result.get(

                        "btts",

                        0

                    ),



                "over25":

                    core_result.get(

                        "over25",

                        0

                    ),



                "confidence":

                    confidence,



                "home_rating":

                    home_rating,



                "away_rating":

                    away_rating,



                "risk":

                    risk.get(

                        "risk",

                        "Средний"

                    ),



                "grade":

                    risk.get(

                        "grade",

                        "C"

                    ),



                "grade_name":

                    risk.get(

                        "grade_name",

                        ""

                    ),



                "factors":

                    factors

            }




            logger.info(

                f"Pipeline finished {home_team}-{away_team}"

            )



            return prediction



        except Exception as e:


            logger.error(

                f"Pipeline error {home_team}-{away_team}: {e}",

                exc_info=True

            )


            return None





# =====================================================
# GLOBAL INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()


# =====================================================
# LEGACY COMPATIBILITY
# FAJ v6.5
#
# Для старых импортов:
# from app.services.prediction_pipeline import predict_match_pipeline
# =====================================================
def predict_match_pipeline(
    home_team,
    away_team,
    league="RPL",
    season="2026/27"
):
    return prediction_pipeline.predict_match(
        home_team,
        away_team,
        league,
        season
    )
