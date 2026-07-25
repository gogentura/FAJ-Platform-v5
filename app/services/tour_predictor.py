# =====================================================
# FAJ Platform v6.4.1
# app/services/tour_predictor.py
#
# Tour Predictor Service
# =====================================================


import logging


from app.database import get_connection

from app.core.faj_core import FAJCore

from app.journal import Journal



logger = logging.getLogger(__name__)


core = FAJCore()

journal = Journal()



# =====================================================
# GET TOUR FIXTURES
# =====================================================


def get_tour_fixtures(

    league="RPL",

    season="2026/27"

):


    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """

            SELECT *

            FROM fixtures


            WHERE league=%s

            AND season=%s


            AND (

                status IS NULL

                OR LOWER(status)
                IN (

                'scheduled',

                'pending',

                'not_started',

                'ns'

                )

            )


            ORDER BY date


            """,

            (

                league,

                season

            )

        )



        rows = cur.fetchall()



        cur.close()

        conn.close()



        logger.info(

            "FAJ fixtures found: %s",

            len(rows)

        )



        return rows



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


def predict_single_fixture(

    fixture

):


    home = fixture["home_team"]

    away = fixture["away_team"]



    result = core.predict_match(

        home,

        away,

        fixture.get(

            "league",

            "RPL"

        )

    )



    result["fixture_id"] = fixture["id"]

    result["home_team"] = home

    result["away_team"] = away

    result["season"] = fixture.get(

        "season",

        "2026/27"

    )



    return result




# =====================================================
# SAVE TO JOURNAL
# =====================================================


def save_prediction(

    fixture,

    prediction

):


    try:


        journal.save(

            match=

            f"{fixture['home_team']} — {fixture['away_team']}",

            fixture_id=

            fixture["id"],

            prediction=prediction

        )


    except Exception as e:


        logger.error(

            "Journal save error: %s",

            e

        )




# =====================================================
# MAIN TOUR PREDICTOR
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

            "No fixtures for prediction"

        )


        return []



    predictions = []



    for fixture in fixtures:


        try:


            prediction = predict_single_fixture(

                fixture

            )



            save_prediction(

                fixture,

                prediction

            )



            predictions.append(

                prediction

            )



        except Exception as e:


            logger.error(

                "Prediction error %s: %s",

                fixture,

                e,

                exc_info=True

            )



    logger.info(

        "Tour predictions created: %s",

        len(predictions)

    )



    return predictions
