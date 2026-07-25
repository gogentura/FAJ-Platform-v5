# =====================================================
# FAJ Platform v6.4.1
# app/services/prediction_pipeline.py
#
# Unified Prediction Pipeline
#
# FAJCore
# + Risk Engine
# + Expert Layer
# + Journal preparation
# =====================================================


import logging


from app.core.faj_core import FAJCore

from app.core.risk_engine import risk_engine

from app.passport_manager import (
    load_passport,
    get_team_by_alias
)


logger = logging.getLogger(__name__)



core = FAJCore()



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


        if isinstance(value, dict):

            return default


        return float(value)


    except Exception:

        return default




# =====================================================
# LOAD PASSPORT
# =====================================================


def get_passport(team):


    real_team = get_team_by_alias(team)


    if real_team:

        team = real_team



    passport = load_passport(

        team

    )


    return passport or {}




# =====================================================
# FAJ RATING
# =====================================================


def calculate_rating(

    passport

):


    if not passport:

        return 0



    if passport.get(

        "faj_rating"

    ):

        return round(

            safe_float(

                passport["faj_rating"]

            ),

            1

        )



    rating = (

        safe_float(

            passport.get("attack"),

        )

        * 0.25


        +

        safe_float(

            passport.get("defense")

        )

        * 0.25


        +

        safe_float(

            passport.get("control")

        )

        * 0.20


        +

        safe_float(

            passport.get("form")

        )

        * 0.20


        +

        safe_float(

            passport.get("efficiency")

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


def predict_match_pipeline(

    home_team,

    away_team,

    league="RPL",

    season="2026/27"

):


    try:


        # -----------------------------------------
        # CORE
        # -----------------------------------------


        result = core.predict_match(

            home_team,

            away_team,

            league

        )



        if not result:

            raise Exception(

                "FAJ Core returned empty"

            )




        decision = result.get(

            "decision",

            {}

        )



        xg = result.get(

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




        # -----------------------------------------
        # RATINGS
        # -----------------------------------------


        home_passport = get_passport(

            home_team

        )


        away_passport = get_passport(

            away_team

        )



        home_rating = calculate_rating(

            home_passport

        )


        away_rating = calculate_rating(

            away_passport

        )




        # -----------------------------------------
        # RISK ENGINE
        # -----------------------------------------


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



        risk = risk_engine.analyze(

            confidence,

            home_rating,

            away_rating,

            winner_probability,

            xg_home,

            xg_away

        )





        # -----------------------------------------
        # FINAL OBJECT
        # -----------------------------------------


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

                        "-"

                    )

                ),



            "expected_score":

                decision.get(

                    "expected_score",

                    "-"

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

                result.get(

                    "simulation",

                    {}

                ).get(

                    "top_scores",

                    []

                ),



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



            "home_rating":

                home_rating,



            "away_rating":

                away_rating,



            "confidence":

                confidence,



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



            "model_version":

                core.version

        }




        return prediction




    except Exception as e:



        logger.error(

            "Prediction pipeline error: %s",

            e,

            exc_info=True

        )


        return None
