# =====================================================
# FAJ Platform v6.4.1
# app/services/tour_predictor.py
#
# Tour Prediction Service
# =====================================================


import logging


from app.database import get_connection

from app.core.faj_core import FAJCore

from app.journal import Journal



logger = logging.getLogger(__name__)



core = FAJCore()

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

            ORDER BY kickoff_time NULLS LAST

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

            f"Fixtures load error: {e}",

            exc_info=True

        )


        return []



# =====================================================
# SAVE HISTORY
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

                %s,%s,%s,%s,%s,

                %s,%s,

                %s,%s,

                %s,%s,%s,

                %s,%s,

                %s,%s,%s,

                NOW()

            )


            ON CONFLICT(fixture_id)

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
                    "home_team"
                ),


                prediction.get(
                    "away_team"
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
                    "-"
                ),


                prediction.get(
                    "winner",
                    "-"
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

            f"History save error: {e}",

            exc_info=True

        )



# =====================================================
# SINGLE FIXTURE PREDICT
# =====================================================


def predict_fixture(

    fixture,

    league="RPL",

    season="2026/27"

):


    home = fixture["home_team"]

    away = fixture["away_team"]



    result = core.predict_match(

        home,

        away,

        league

    )



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



    simulation = result.get(

        "simulation",

        {}

    )



    prediction = {



        "fixture_id":

            fixture["id"],



        "home_team":

            home,


        "away_team":

            away,


        "league":

            league,


        "season":

            season,



        "xg_home":

            xg.get(
                "home",
                0
            ),



        "xg_away":

            xg.get(
                "away",
                0
            ),



        "winner":

            decision.get(
                "winner_name",
                decision.get(
                    "winner",
                    "нет"
                )
            ),



        "expected_score":

            decision.get(
                "expected_score",
                "-"
            ),



        "home_probability":

            decision.get(
                "home_probability",
                0
            ),



        "draw_probability":

            decision.get(
                "draw_probability",
                0
            ),



        "away_probability":

            decision.get(
                "away_probability",
                0
            ),



        "confidence":

            decision.get(
                "confidence",
                0
            ),



        "top_scores":

            simulation.get(
                "top_scores",
                []
            ),



        "risk":

            decision.get(
                "risk",
                "Средний"
            ),



        "grade":

            decision.get(
                "grade",
                "C"
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
            )

    }


    return prediction



# =====================================================
# TOUR PREDICTOR
# =====================================================


def predict_tour(

    league="RPL",

    season="2026/27"

):


    fixtures = get_tour_fixtures(

        league,

        season

    )



    predictions = []



    logger.info(

        f"FAJ tour started: {len(fixtures)} fixtures"

    )



    for fixture in fixtures:


        try:


            prediction = predict_fixture(

                fixture,

                league,

                season

            )



            # сохраняем историю

            save_prediction_history(

                fixture["id"],

                prediction

            )



            # журнал

            journal.save(

                match=

                f"{fixture['home_team']} — {fixture['away_team']}",


                fixture_id=

                fixture["id"],


                prediction=

                prediction

            )



            predictions.append(

                prediction

            )



        except Exception as e:


            logger.error(

                f"Prediction error {fixture}: {e}",

                exc_info=True

            )



    logger.info(

        f"FAJ tour finished: {len(predictions)} predictions"

    )



    return predictions
