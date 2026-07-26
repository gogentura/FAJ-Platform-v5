# =====================================================
# FAJ Platform v6.8
# app/services/prediction_pipeline.py
#
# Unified Prediction Pipeline
#
# Handler
#    ↓
# PredictionPipeline
#    ↓
# FAJCore
#    ↓
# Team Passport / xG / Monte Carlo
# =====================================================


import logging


from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)





# =====================================================
# GLOBAL CORE
# =====================================================


_core_instance = None



def get_core():

    global _core_instance


    if _core_instance is None:

        _core_instance = FAJCore()


    return _core_instance







# =====================================================
# NORMALIZE CORE OUTPUT
# =====================================================


def normalize_core_result(

    result,

    home_team,

    away_team

):


    if not result:

        return None



    decision = result.get(

        "decision",

        {}

    )



    xg_block = result.get(

        "xg",

        {}

    )


    predicted_xg = xg_block.get(

        "predicted",

        {}

    )



    simulation = result.get(

        "simulation",

        {}

    )



    return {


        # teams

        "home_team":
            home_team,


        "away_team":
            away_team,



        # xG

        "xg": {

            "predicted": {

                "home":
                    round(
                        float(
                            predicted_xg.get(
                                "home",
                                0
                            )
                        ),
                        2
                    ),


                "away":
                    round(
                        float(
                            predicted_xg.get(
                                "away",
                                0
                            )
                        ),
                        2
                    )

            }

        },



        "xg_home":
            round(
                float(
                    predicted_xg.get(
                        "home",
                        0
                    )
                ),
                2
            ),


        "xg_away":
            round(
                float(
                    predicted_xg.get(
                        "away",
                        0
                    )
                ),
                2
            ),




        # decision

        "decision": {


            "winner":
                decision.get(
                    "winner"
                ),


            "winner_name":
                decision.get(
                    "winner_name"
                ),


            "expected_score":
                decision.get(
                    "expected_score",
                    "-"
                ),


            "confidence":
                decision.get(
                    "confidence",
                    0
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
                )

        },



        # simulation

        "simulation":

            simulation,



        # ratings

        "home_rating":

            result.get(
                "home_rating",
                0
            ),


        "away_rating":

            result.get(
                "away_rating",
                0
            ),



        # markets

        "btts":

            result.get(
                "btts",
                0
            ),


        "over25":

            result.get(
                "over25",
                0
            ),


        "under25":

            result.get(
                "under25",
                0
            ),



        # meta

        "phase":

            result.get(
                "phase",
                "start"
            ),



        "data_quality": {


            "home":

                result.get(
                    "data_quality",
                    {}
                ).get(
                    "home",
                    100
                ),


            "away":

                result.get(
                    "data_quality",
                    {}
                ).get(
                    "away",
                    100
                )

        }



    }







# =====================================================
# PIPELINE CLASS
# =====================================================


class PredictionPipeline:



    def __init__(self):

        self.core = get_core()





    # -------------------------------------------------
    # MAIN MATCH PREDICTION
    # -------------------------------------------------


    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL",

        season="2026/27"

    ):


        try:


            raw = self.core.predict_match(

                home_team,

                away_team,

                league

            )



            normalized = normalize_core_result(

                raw,

                home_team,

                away_team

            )



            if normalized:

                normalized["league"] = league

                normalized["season"] = season



            return normalized



        except Exception as e:


            logger.error(

                "Prediction pipeline error: %s",

                e,

                exc_info=True

            )


            return None








# =====================================================
# GLOBAL INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()







# =====================================================
# LEGACY SUPPORT
#
# Для старых файлов FAJ v6.5
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







# =====================================================
# SHORT FUNCTION API
# =====================================================


def predict_match(

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
