# =====================================================
# FAJ Platform v6.8
# app/services/prediction_pipeline.py
#
# Unified Prediction Pipeline
# =====================================================


import logging


from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)





# =====================================================
# CORE INSTANCE
# =====================================================


_core = None



def get_core():

    global _core


    if _core is None:

        _core = FAJCore()


    return _core







# =====================================================
# RISK ENGINE
# =====================================================


def calculate_risk(

    confidence

):


    try:

        confidence = float(confidence)


    except Exception:

        confidence = 0



    if confidence >= 70:

        return "Низкий"


    elif confidence >= 45:

        return "Средний"


    else:

        return "Высокий"







# =====================================================
# CATEGORY
# =====================================================


def calculate_category(

    confidence

):


    try:

        confidence = float(confidence)

    except:

        confidence = 0



    if confidence >= 70:

        return "A"


    elif confidence >= 50:

        return "B"


    else:

        return "C"







# =====================================================
# FACTORS
# =====================================================


def build_factors(

    result

):


    factors = []



    decision = result.get(

        "decision",

        {}

    )


    winner = decision.get(

        "winner"

    )


    xg = result.get(

        "xg",

        {}

    ).get(

        "predicted",

        {}

    )



    home_xg = xg.get(

        "home",

        0

    )


    away_xg = xg.get(

        "away",

        0

    )



    if winner == "home":

        factors.append(

            "🏹 Преимущество хозяев в атаке"

        )


    elif winner == "away":

        factors.append(

            "🏹 Преимущество гостей в атаке"

        )



    if home_xg > away_xg:

        factors.append(

            f"📈 xG преимущество хозяев ({home_xg})"

        )


    elif away_xg > home_xg:

        factors.append(

            f"📈 xG преимущество гостей ({away_xg})"

        )



    factors.append(

        "🏆 Турнир: RPL"

    )


    return factors







# =====================================================
# NORMALIZE
# =====================================================


def normalize_prediction(

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


    xg = result.get(

        "xg",

        {}

    ).get(

        "predicted",

        {}

    )



    confidence = decision.get(

        "confidence",

        0

    )



    normalized = {


        "home_team":

            home_team,


        "away_team":

            away_team,



        "winner":

            decision.get(

                "winner"

            ),



        "winner_name":

            decision.get(

                "winner_name",

                "-"

            ),



        "expected_score":

            decision.get(

                "expected_score",

                "-"

            ),




        "xg_home":

            round(

                float(

                    xg.get(

                        "home",

                        0

                    )

                ),

                2

            ),



        "xg_away":

            round(

                float(

                    xg.get(

                        "away",

                        0

                    )

                ),

                2

            ),




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




        "confidence":

            confidence,



        "risk":

            calculate_risk(

                confidence

            ),



        "category":

            calculate_category(

                confidence

            ),



        "factors":

            build_factors(

                result

            ),




        "simulation":

            result.get(

                "simulation",

                {}

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



        "under25":

            result.get(

                "under25",

                0

            ),




        "phase":

            "start",



        "data_quality":

            {

                "home":100,

                "away":100

            }

    }



    return normalized







# =====================================================
# PIPELINE CLASS
# =====================================================


class PredictionPipeline:



    def __init__(self):

        self.core = get_core()





    def predict_match(

        self,

        home_team,

        away_team,

        league="RPL",

        season="2026/27"

    ):


        try:


            result = self.core.predict_match(

                home_team,

                away_team,

                league

            )



            prediction = normalize_prediction(

                result,

                home_team,

                away_team

            )



            if prediction:


                prediction["league"] = league

                prediction["season"] = season



            return prediction



        except Exception as e:


            logger.exception(

                "FAJ pipeline error"

            )


            return None







# =====================================================
# GLOBAL INSTANCE
# =====================================================


prediction_pipeline = PredictionPipeline()







# =====================================================
# COMPATIBILITY API
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
