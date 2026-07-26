# =====================================================
# FAJ Platform v6.9
# app/services/prediction_pipeline.py
#
# Unified FAJ Prediction Pipeline
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
# HELPERS
# =====================================================


def get_risk(confidence):

    try:

        confidence = float(confidence)

    except:

        confidence = 0



    if confidence >= 70:

        return "Низкий"


    if confidence >= 45:

        return "Средний"


    return "Высокий"







def get_category(confidence):

    try:

        confidence = float(confidence)

    except:

        confidence = 0



    if confidence >= 70:

        return "A"


    if confidence >= 50:

        return "B"


    return "C"







# =====================================================
# RESTORE DECISION
# =====================================================


def restore_decision(raw):


    decision = raw.get(

        "decision",

        {}

    )


    simulation = raw.get(

        "simulation",

        {}

    )



    # если Core decision потерян

    if not decision:


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



        if home >= away and home >= draw:


            winner = "home"

            winner_name = "Хозяева"



        elif away >= home and away >= draw:


            winner = "away"

            winner_name = "Гости"



        else:


            winner = "draw"

            winner_name = "Ничья"



        scores = simulation.get(

            "top_scores",

            []

        )


        score = "-"



        if scores:

            score = scores[0].get(

                "score",

                "-"

            )



        decision = {


            "winner":

                winner,


            "winner_name":

                winner_name,



            "expected_score":

                score,



            "winner_probability":

                max(

                    home,

                    draw,

                    away

                ) * 100

        }



    return decision







# =====================================================
# NORMALIZE
# =====================================================


def normalize_prediction(

    raw,

    home,

    away

):


    decision = restore_decision(

        raw

    )



    xg_block = raw.get(

        "xg",

        {}

    ).get(

        "predicted",

        {}

    )



    home_xg = float(

        xg_block.get(

            "home",

            0

        )

    )



    away_xg = float(

        xg_block.get(

            "away",

            0

        )

    )



    home_rating = raw.get(

        "home_rating",

        decision.get(

            "home_rating",

            0

        )

    )



    away_rating = raw.get(

        "away_rating",

        decision.get(

            "away_rating",

            0

        )

    )



    confidence = raw.get(

        "confidence",

        decision.get(

            "confidence",

            0

        )

    )



    factors = []



    winner = decision.get(

        "winner"

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

            f"📈 xG преимущество хозяев ({round(home_xg,2)})"

        )


    elif away_xg > home_xg:


        factors.append(

            f"📈 xG преимущество гостей ({round(away_xg,2)})"

        )



    factors.append(

        "🏆 Турнир: RPL"

    )





    return {


        "home_team":

            home,


        "away_team":

            away,



        "winner":

            decision.get(

                "winner",

                "-"

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

                home_xg,

                2

            ),



        "xg_away":

            round(

                away_xg,

                2

            ),



        "home_rating":

            round(

                float(home_rating),

                1

            ),



        "away_rating":

            round(

                float(away_rating),

                1

            ),



        "confidence":

            round(

                float(confidence),

                1

            ),



        "risk":

            get_risk(

                confidence

            ),



        "category":

            get_category(

                confidence

            ),



        "factors":

            factors,



        "simulation":

            raw.get(

                "simulation",

                {}

            ),



        "top_scores":

            raw.get(

                "simulation",

                {}

            ).get(

                "top_scores",

                []

            ),



        "btts":

            raw.get(

                "btts",

                0

            ),



        "over25":

            raw.get(

                "over25",

                0

            ),



        "under25":

            raw.get(

                "under25",

                0

            ),



        "phase":

            "start",



        "data_quality":

            {

                "home":

                    100,


                "away":

                    100

            }

    }







# =====================================================
# PIPELINE CLASS
# =====================================================


class PredictionPipeline:



    def __init__(self):

        self.core = get_core()



    def predict_match(

        self,

        home,

        away,

        league="RPL",

        season="2026/27"

    ):


        try:


            raw = self.core.predict_match(

                home,

                away,

                league

            )



            if not raw:


                logger.warning(

                    "Empty Core response"

                )


                return None



            prediction = normalize_prediction(

                raw,

                home,

                away

            )



            prediction["league"] = league

            prediction["season"] = season



            return prediction



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
# COMPATIBILITY FUNCTIONS
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
