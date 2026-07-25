# =====================================================
# FAJ Platform v6.5
# app/services/tour_predictor.py
#
# Tournament / Round Predictor
#
# Uses:
# - Prediction Pipeline
# - FAJ Core
# - Journal
# - prediction_history
# =====================================================


import logging


from app.database import get_connection

from app.services.prediction_pipeline import (
    predict_match_pipeline
)


from app.journal import Journal



logger = logging.getLogger(__name__)



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

            AND status='scheduled'

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



        return rows



    except Exception as e:


        logger.error(

            f"Get fixtures error: {e}",

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

            f"Prediction history save error: {e}",

            exc_info=True

        )





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



    results = []



    logger.info(

        f"FAJ tour started. Matches: {len(fixtures)}"

    )



    for fixture in fixtures:


        try:


            fixture_id = fixture["id"]



            home = fixture["home_team"]


            away = fixture["away_team"]




            prediction = predict_match_pipeline(

                home_team=home,

                away_team=away,

                league=league,

                season=season

            )



            if not prediction:


                logger.warning(

                    f"No prediction: {home} - {away}"

                )

                continue




            prediction["fixture_id"] = fixture_id




            # -------------------------------
            # JOURNAL
            # -------------------------------


            journal.save(

                match=f"{home} — {away}",

                fixture_id=fixture_id,

                prediction=prediction

            )



            # -------------------------------
            # HISTORY
            # -------------------------------


            save_prediction_history(

                fixture_id,

                prediction

            )



            results.append(

                prediction

            )



            logger.info(

                f"Prediction saved: {home} - {away}"

            )



        except Exception as e:


            logger.error(

                f"Tour prediction error {fixture}: {e}",

                exc_info=True

            )




    logger.info(

        f"FAJ tour finished. Predictions: {len(results)}"

    )



    return results
