# =====================================================
# FAJ Platform v6.7
# app/services/tour_predictor.py
#
# Tour Predictor
#
# Pipeline Based
# Calibration Ready
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
# SAFE ROW
# =====================================================


def row_to_dict(row, cursor):


    if isinstance(row, dict):

        return row


    try:

        return dict(

            zip(

                [
                    col.name
                    for col in cursor.description
                ],

                row

            )

        )


    except Exception:


        return {}






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

            ORDER BY

            COALESCE(match_date,date),

            COALESCE(match_time,time)

            """,

            (

                league,

                season

            )

        )



        rows=cur.fetchall()



        fixtures=[]


        for row in rows:


            item=row_to_dict(

                row,

                cur

            )


            if item:

                fixtures.append(item)



        cur.close()

        conn.close()



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
# SINGLE FIXTURE
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



        if not home or not away:


            return None



        prediction = prediction_pipeline.predict_match(

            home,

            away,

            fixture.get(
                "league",
                "RPL"
            ),

            fixture.get(
                "season",
                "2026/27"
            )

        )



        if prediction is None:


            logger.warning(

                "Pipeline returned None %s-%s",

                home,

                away

            )


            return None




        prediction.update(

            {

                "fixture_id":
                fixture.get(
                    "id"
                ),


                "round":
                fixture.get(
                    "round"
                ),


                "match_date":
                fixture.get(
                    "match_date",
                    fixture.get(
                        "date"
                    )
                )

            }

        )



        return prediction




    except Exception as e:


        logger.error(

            "Prediction fixture error %s",

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



        return True



    except Exception as e:


        logger.error(

            "Save prediction error %s",

            e,

            exc_info=True

        )


        return False







# =====================================================
# TOUR
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

            "No fixtures"

        )


        return []




    results=[]



    logger.info(

        "FAJ tour started %s",

        len(fixtures)

    )




    for fixture in fixtures:


        prediction=predict_fixture(

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

        "FAJ tour finished %s",

        len(results)

    )


    return results
