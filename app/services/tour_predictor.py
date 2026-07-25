# =====================================================
# FAJ Platform v6.4.1
# app/services/tour_predictor.py
#
# Tournament / Round Predictor Service
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


            AND LOWER(

                COALESCE(status,'')

            ) = 'scheduled'


            ORDER BY id


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

            "Tour fixtures loading error: %s",

            e,

            exc_info=True

        )


        return []




# =====================================================
# SAVE PREDICTION HISTORY
# =====================================================


def save_prediction_history(

    fixture_id,

    prediction

):


    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """

            INSERT INTO prediction_history

            (

                fixture_id,


                home_team,

                away_team,


                league,

                season,


                xg_home,

                xg_away,


                predicted_score,

                predicted_winner,


                home_probability,

                draw_probability,

                away_probability,


                home_rating,

                away_rating,


                confidence,


                risk,


                grade,


                created


            )


            VALUES

            (

                %s,


                %s,

                %s,


                %s,

                %s,


                %s,

                %s,


                %s,

                %s,


                %s,

                %s,

                %s,


                %s,

                %s,


                %s,


                %s,


                %s,


                NOW()

            )


            ON CONFLICT (fixture_id)

            DO UPDATE SET


                predicted_score =
                EXCLUDED.predicted_score,


                predicted_winner =
                EXCLUDED.predicted_winner,


                confidence =
                EXCLUDED.confidence,


                risk =
                EXCLUDED.risk,


                grade =
                EXCLUDED.grade


            """,

            (

                fixture_id,


                prediction.get(
                    "home_team",
                    ""
                ),


                prediction.get(
                    "away_team",
                    ""
                ),


                prediction.get(
                    "league",
                    "RPL"
                ),


                prediction.get(
                    "season",
                    "2026/27"
                ),


                prediction.get(
                    "xg_home",
                    0
                ),


                prediction.get(
                    "xg_away",
                    0
                ),


                prediction.get(
                    "expected_score",
                    ""
                ),


                prediction.get(
                    "winner",
                    ""
                ),


                prediction.get(
                    "home_probability",
                    0
                ),


                prediction.get(
                    "draw_probability",
                    0
                ),


                prediction.get(
                    "away_probability",
                    0
                ),


                prediction.get(
                    "home_rating",
                    0
                ),


                prediction.get(
                    "away_rating",
                    0
                ),


                prediction.get(
                    "confidence",
                    0
                ),


                prediction.get(
                    "risk",
                    "Средний"
                ),


                prediction.get(
                    "grade",
                    "C"
                )

            )

        )



        conn.commit()



        cur.close()

        conn.close()



    except Exception as e:


        logger.error(

            "Prediction history save error: %s",

            e,

            exc_info=True

        )




# =====================================================
# PREDICT ONE FIXTURE
# =====================================================


def predict_fixture(

    fixture,

    league="RPL"

):


    home = fixture["home_team"]

    away = fixture["away_team"]



    result = core.predict_match(

        home,

        away,

        league

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

            "No fixtures found for tour"

        )


        return []



    predictions = []



    logger.info(

        "FAJ tour prediction started: %s matches",

        len(fixtures)

    )



    for fixture in fixtures:


        try:


            prediction = predict_fixture(

                fixture,

                league

            )



            # Journal

            journal.save(

                match=

                f"{fixture['home_team']} — {fixture['away_team']}",


                fixture_id=

                fixture["id"],


                prediction=

                prediction

            )



            # Learning history

            save_prediction_history(

                fixture["id"],

                prediction

            )



            predictions.append(

                prediction

            )



            logger.info(

                "Prediction created: %s — %s",

                fixture["home_team"],

                fixture["away_team"]

            )



        except Exception as e:


            logger.error(

                "Fixture prediction error %s: %s",

                fixture,

                e,

                exc_info=True

            )



    logger.info(

        "FAJ tour finished: %s predictions",

        len(predictions)

    )



    return predictions
