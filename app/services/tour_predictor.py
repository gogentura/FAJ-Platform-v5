# =====================================================
# FAJ Platform v6.5
# app/services/tour_predictor.py
#
# Tournament / Round Predictor
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
# GET TOUR FIXTURES
# =====================================================


def get_tour_fixtures(

    league="RPL",

    season="2026/27"

):


    try:


        conn = get_db()

        cur = conn.cursor()



        cur.execute(

            """
            SELECT *

            FROM fixtures

            WHERE league = %s

            AND season = %s

            AND status = 'scheduled'

            ORDER BY match_date, match_time

            """,

            (

                league,

                season

            )

        )



        rows = cur.fetchall()



        cur.close()

        conn.close()



        fixtures = []



        for row in rows:


            try:

                fixtures.append(
                    dict(row)
                )


            except Exception:


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

            "Fixtures loading error: %s",

            e,

            exc_info=True

        )


        return []





# =====================================================
# PREDICT SINGLE MATCH
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




        prediction = prediction_pipeline.predict_match(

            home,

            away,

            league,

            season

        )



        if not prediction:


            logger.warning(

                "Empty prediction %s - %s",

                home,

                away

            )


            return None




        prediction["fixture_id"] = fixture.get(

            "id"

        )


        prediction["round"] = fixture.get(

            "round"

        )


        prediction["match_date"] = fixture.get(

            "match_date"

        )



        return prediction



    except Exception as e:


        logger.error(

            "Prediction error %s: %s",

            fixture,

            e,

            exc_info=True

        )


        return None





# =====================================================
# SAVE
# =====================================================


def save_tour_prediction(

    fixture,

    prediction

):


    try:


        save_prediction(

            fixture,

            prediction

        )



        logger.info(

            "Prediction saved %s - %s",

            fixture.get(
                "home_team"
            ),

            fixture.get(
                "away_team"
            )

        )



    except Exception as e:


        logger.error(

            "Prediction save error: %s",

            e,

            exc_info=True

        )





# =====================================================
# MAIN TOUR
# =====================================================


def predict_tour(

    league="RPL",

    season="2026/27"

):


    fixtures = get_tour_fixtures(

        league,

        season

    )



    if not fixtures:


        logger.warning(

            "No scheduled fixtures"

        )


        return []




    results = []



    logger.info(

        "FAJ tour prediction started: %s matches",

        len(fixtures)

    )




    for fixture in fixtures:


        prediction = predict_fixture(

            fixture

        )



        if not prediction:


            continue



        save_tour_prediction(

            fixture,

            prediction

        )



        results.append(

            prediction

        )




    logger.info(

        "FAJ tour prediction finished: %s",

        len(results)

    )



    return results
