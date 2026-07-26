# =====================================================
# FAJ Platform v6.6
# app/services/prediction_pipeline.py
#
# FAJ Prediction Pipeline
#
# Core + Passport + Risk + Explain
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


    VERSION = "6.6"



    def __init__(self):

        self.core = FAJCore()





    # =================================================
    # PASSPORT
    # =================================================


    def get_passport(self, team):

        try:

            alias = get_team_by_alias(team)


            if alias:

                team = alias



            passport = load_passport(team)


            return passport or {}



        except Exception as e:


            logger.error(

                f"Passport error {team}: {e}"

            )


            return {}





    # =================================================
    # RATING
    # =================================================


    def calculate_rating(self, passport):

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

            safe_float(
                passport.get("attack")
            ) * 0.25


            +

            safe_float(
                passport.get("defense")
            ) * 0.25


            +

            safe_float(
                passport.get("control")
            ) * 0.20


            +

            safe_float(
                passport.get("form")
            ) * 0.20


            +

            safe_float(
                passport.get("efficiency")
            ) * 0.10

        )


        return round(rating,1)





    # =================================================
    # CORE CALL
    # =================================================


    def call_core(

        self,

        home_team,

        away_team,

        league

    ):


        if hasattr(

            self.core,

            "predict"

        ):


            return self.core.predict(

                home_team,

                away_team,

                league

            )



        if hasattr(

            self.core,

            "predict_match"

        ):


            return self.core.predict_match(

                home_team,

                away_team,

                league

            )



        raise Exception(

            "FAJCore has no prediction method"

        )





    # =================================================
    # MAIN PREDICTION
    # =================================================


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



            # CORE

            core_result = self.call_core(

                home_team,

                away_team,

                league

            )



            if not core_result:


                raise Exception(

                    "FAJ Core returned None"

                )



            if isinstance(core_result,dict):

                if core_result.get("error"):

                    raise Exception(

                        core_result["error"]

                    )





            # ===============================
            # XG
            # ===============================


            xg = (

                core_result

                .get("xg", {})

                .get("predicted", {})

            )



            xg_home = safe_float(

                xg.get("home")

            )


            xg_away = safe_float(

                xg.get("away")

            )





            # ===============================
            # PASSPORT
            # ===============================


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





            # ===============================
            # DECISION
            # ===============================


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





            # ===============================
            # RISK
            # ===============================


            risk = risk_engine.analyze(

                confidence,

                home_rating,

                away_rating,

                winner_probability,

                xg_home,

                xg_away

            )





            # ===============================
            # EXPLAIN
            # ===============================


            factors = explain_prediction(

                home_passport,

                away_passport,

                xg_home,

                xg_away,

                league

            )





            # ===============================
            # FINAL OBJECT
            # ===============================


            return {


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
                            "winner"
                        )
                    ),


                "expected_score":
                    decision.get(
                        "expected_score",
                        "-"
                    ),



                "home_probability":
                    safe_float(
                        decision.get(
                            "home_prob",
                            decision.get(
                                "home_probability",
                                0
                            )
                        )
                    ),



                "draw_probability":
                    safe_float(
                        decision.get(
                            "draw_prob",
                            decision.get(
                                "draw_probability",
                                0
                            )
                        )
                    ),



                "away_probability":
                    safe_float(
                        decision.get(
                            "away_prob",
                            decision.get(
                                "away_probability",
                                0
                            )
                        )
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
                    safe_float(
                        core_result.get(
                            "btts",
                            0
                        )
                    ),



                "over25":
                    safe_float(
                        core_result.get(
                            "over25",
                            0
                        )
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


                "factors":
                    factors

            }



        except Exception as e:


            logger.exception(

                f"Pipeline failed {home_team}-{away_team}"

            )


            return {


                "error":

                    str(e),


                "home_team":

                    home_team,


                "away_team":

                    away_team,


                "league":

                    league,


                "confidence":

                    0,


                "expected_score":

                    None

            }





# =====================================================
# GLOBAL INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()





# =====================================================
# LEGACY FUNCTION
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
