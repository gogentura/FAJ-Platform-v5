# =====================================================
# FAJ Platform v6.8
# app/services/tour_predictor.py
#
# Tournament Predictor Service
# =====================================================


import logging


from app.database import get_db


from app.services.prediction_pipeline import (
    prediction_pipeline
)


from app.managers.prediction_manager import (
    save_prediction
)



logger = logging.getLogger(__name__)





# =====================================================
# LOAD FIXTURES
# =====================================================


def get_tour_fixtures(

    league="RPL",

    season="2026/27"

):


    try:


        conn=get_db()

        cur=conn.cursor()



        cur.execute(

"""
SELECT *

FROM fixtures

WHERE league=%s

AND season=%s

AND status='scheduled'

ORDER BY match_date, match_time

""",

(
league,
season
)

)


        rows=cur.fetchall()



        conn.close()



        fixtures=[]



        for row in rows:


            fixtures.append(
                dict(row)
            )



        logger.info(

            "FAJ fixtures loaded: %s",

            len(fixtures)

        )



        return fixtures



    except Exception as e:


        logger.error(

            "Fixture load error %s",

            e,

            exc_info=True

        )


        return []








# =====================================================
# NORMALIZE CORE
# =====================================================


def enrich_prediction(

    prediction,

    fixture

):


    if not prediction:

        return None



    decision=prediction.get(

        "decision",

        {}

    )



    # переносим поля наверх

    prediction["winner"]=decision.get(

        "winner"

    )


    prediction["winner_name"]=decision.get(

        "winner_name"

    )



    prediction["expected_score"]=decision.get(

        "expected_score",

        "-"

    )



    prediction["confidence"]=decision.get(

        "confidence",

        0

    )



    prediction["home_rating"]=decision.get(

        "home_rating",

        0

    )


    prediction["away_rating"]=decision.get(

        "away_rating",

        0

    )



    # новые поля v6.8


    prediction["risk"]=decision.get(

        "risk",

        prediction.get(
            "risk",
            "Средний"
        )

    )


    prediction["grade"]=decision.get(

        "grade",

        prediction.get(
            "grade",
            "C"
        )

    )



    prediction["factors"]=decision.get(

        "factors",

        prediction.get(
            "factors",
            []
        )

    )



    prediction["season_phase"]=prediction.get(

        "season_phase",

        "start"

    )



    prediction["passport_quality"]=prediction.get(

        "passport_quality",

        {

        "home":0,

        "away":0

        }

    )



    prediction["fixture_id"]=fixture.get(

        "id"

    )



    prediction["match_date"]=fixture.get(

        "match_date"

    )



    prediction["round"]=fixture.get(

        "round"

    )



    return prediction







# =====================================================
# SINGLE MATCH
# =====================================================


def predict_fixture(

    fixture

):


    try:


        home=fixture.get(

            "home_team"

        )


        away=fixture.get(

            "away_team"

        )


        league=fixture.get(

            "league",

            "RPL"

        )


        season=fixture.get(

            "season",

            "2026/27"

        )



        result=prediction_pipeline.predict_match(

            home,

            away,

            league,

            season

        )



        if not result:


            logger.warning(

                "Empty prediction %s-%s",

                home,

                away

            )


            return None



        return enrich_prediction(

            result,

            fixture

        )



    except Exception as e:


        logger.error(

            "Prediction failed %s-%s : %s",

            fixture.get("home_team"),

            fixture.get("away_team"),

            e,

            exc_info=True

        )


        return None







# =====================================================
# TOUR GENERATION
# =====================================================


def predict_tour(

    league="RPL",

    season="2026/27"

):


    fixtures=get_tour_fixtures(

        league,

        season

    )



    if not fixtures:


        logger.warning(

            "No fixtures found"

        )


        return []



    results=[]



    logger.info(

        "FAJ tour started %s matches",

        len(fixtures)

    )



    for fixture in fixtures:



        prediction=predict_fixture(

            fixture

        )



        if prediction is None:

            continue



        try:


            save_prediction(

                fixture,

                prediction

            )


        except Exception as e:


            logger.error(

                "Save failed %s",

                e

            )



        results.append(

            prediction

        )



    logger.info(

        "FAJ tour completed %s",

        len(results)

    )



    return results
