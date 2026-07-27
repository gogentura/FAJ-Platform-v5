# =====================================================
# FAJ Platform v6.9.3
# app/services/tour_predictor.py
#
# Tournament Prediction Service
#
# Flow:
#
# Fixtures
#    ↓
# Prediction Pipeline
#    ↓
# Prediction Manager
#    ↓
# PostgreSQL
#    ↓
# Learning Layer
#
# Compatible:
# - prediction_pipeline v6.9.3
# - FAJCore v6.8+
# - generate_predictions.py
# - debug_prediction.py
# - PostgreSQL
# =====================================================


import logging


from app.database import get_db


from app.services.prediction_pipeline import (
    predict_match_pipeline
)


from app.managers.prediction_manager import (
    save_prediction,
    clear_predictions
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

        conn = get_db()

        cursor = conn.cursor()


        cursor.execute(
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


        rows = cursor.fetchall()


        conn.close()


        fixtures=[]


        for row in rows:

            try:

                fixtures.append(
                    dict(row)
                )

            except:

                fixtures.append(
                    row
                )


        logger.info(
            "FAJ fixtures loaded: %s",
            len(fixtures)
        )


        return fixtures



    except Exception as e:


        logger.error(
            "Fixture loading error: %s",
            e,
            exc_info=True
        )


        return []







# =====================================================
# NORMALIZE RESULT
# =====================================================


def enrich_prediction(

    prediction,

    fixture

):


    if not prediction:

        return None



    prediction["fixture_id"] = fixture.get(
        "id"
    )


    prediction["home_team"] = fixture.get(
        "home_team"
    )


    prediction["away_team"] = fixture.get(
        "away_team"
    )


    prediction["match_date"] = fixture.get(
        "match_date"
    )


    prediction["round"] = fixture.get(
        "round"
    )



    if "grade" not in prediction:

        prediction["grade"] = prediction.get(
            "category",
            "C"
        )



    if "passport_quality" not in prediction:

        prediction["passport_quality"] = {

            "home": 1,

            "away": 1

        }



    return prediction







# =====================================================
# SINGLE MATCH
# =====================================================


def predict_fixture(

    fixture

):


    try:


        home = fixture.get(
            "home_team"
        )


        away = fixture.get(
            "away_team"
        )


        league = fixture.get(
            "league",
            "RPL"
        )


        season = fixture.get(
            "season",
            "2026/27"
        )



        logger.info(
            "FAJ predicting %s - %s",
            home,
            away
        )



        prediction = predict_match_pipeline(

            home,

            away,

            league,

            season

        )



        if not prediction:


            logger.warning(
                "Empty prediction %s-%s",
                home,
                away
            )


            return None




        return enrich_prediction(

            prediction,

            fixture

        )



    except Exception as e:


        logger.error(
            "Prediction error: %s",
            e,
            exc_info=True
        )


        return None







# =====================================================
# GENERATE TOUR
# =====================================================


def predict_tour(

    league="RPL",

    season="2026/27"

):


    logger.info(
        "FAJ tour generation started"
    )



    # =============================================
    # REMOVE OLD PREDICTIONS
    # =============================================


    try:

        clear_predictions()


    except Exception as e:


        logger.error(
            "Prediction cleanup error: %s",
            e,
            exc_info=True
        )





    fixtures = get_tour_fixtures(

        league,

        season

    )



    if not fixtures:


        logger.warning(
            "No scheduled fixtures"
        )


        return []





    results=[]



    logger.info(
        "FAJ matches: %s",
        len(fixtures)
    )




    for fixture in fixtures:



        prediction = predict_fixture(

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
                "Prediction save error: %s",
                e,
                exc_info=True
            )




        results.append(

            prediction

        )




    logger.info(
        "FAJ tour completed: %s predictions",
        len(results)
    )



    return results
