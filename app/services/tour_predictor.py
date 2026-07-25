# =====================================================
# FAJ Platform v6.4
# app/services/tour_predictor.py
#
# Tournament Predictor
# =====================================================

import logging

from app.database import get_connection

from app.services.prediction_pipeline import (
    PredictionPipeline
)


from app.journal import Journal


logger = logging.getLogger(__name__)


pipeline = PredictionPipeline()

journal = Journal()


# =====================================================
# GET FIXTURES
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

            AND status='scheduled'

            ORDER BY kickoff_time


            """,

            (

                league,
                season

            )

        )


        rows = cur.fetchall()


        cur.close()
        conn.close()


        return rows



    except Exception as e:


        logger.error(

            f"Fixtures loading error: {e}",

            exc_info=True

        )


        return []



# =====================================================
# PREDICT TOUR
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

            "No scheduled fixtures found"

        )

        return []



    results = []



    logger.info(

        f"FAJ tour started: {len(fixtures)} matches"

    )



    for fixture in fixtures:


        try:


            fixture_id = fixture["id"]


            home = fixture["home_team"]

            away = fixture["away_team"]



            prediction = pipeline.predict(

                home,

                away,

                league

            )



            if not prediction:


                continue



            prediction.update(

                {

                    "fixture_id":

                        fixture_id,


                    "home_team":

                        home,


                    "away_team":

                        away,


                    "league":

                        league,


                    "season":

                        season

                }

            )



            # сохраняем журнал


            journal.save(

                fixture,

                prediction,

                fixture_id

            )



            results.append(

                prediction

            )



            logger.info(

                f"Prediction saved: {home}-{away}"

            )



        except Exception as e:


            logger.error(

                f"Tour prediction error {fixture}: {e}",

                exc_info=True

            )



    logger.info(

        f"FAJ tour finished: {len(results)} predictions"

    )


    return results
