# =====================================================
# FAJ Platform v6.4
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
# GET TOUR FIXTURES
# =====================================================


def get_tour_fixtures(

    league="RPL",

    season="2026/27"

):

    try:


        conn = get_connection()

        cur = conn.cursor()



        # Берём все матчи лиги,
        # кроме завершённых

        cur.execute(

            """

            SELECT *

            FROM fixtures

            WHERE league=%s

            AND status NOT IN (

                'finished',

                'completed',

                'played'

            )

            ORDER BY kickoff_time


            """,

            (

                league,

            )

        )



        rows = cur.fetchall()



        logger.info(

            f"FAJ fixtures found: {len(rows)}"

        )



        if rows:


            for row in rows[:3]:

                logger.info(

                    f"Fixture sample: {row}"

                )



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

            "No fixtures for prediction"

        )


        return []



    results = []



    logger.info(

        f"FAJ tour prediction started: {len(fixtures)} matches"

    )



    for fixture in fixtures:


        try:


            fixture_id = fixture["id"]


            home = fixture["home_team"]

            away = fixture["away_team"]



            logger.info(

                f"Predicting: {home} - {away}"

            )



            result = core.predict_match(

                home,

                away,

                league

            )



            if not result:

                continue



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



            prediction = {


                "fixture_id":

                    fixture_id,


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
                        ""
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



                "risk":

                    decision.get(
                        "risk",
                        "Средний"
                    ),



                "grade":

                    decision.get(
                        "grade",
                        "C"
                    )

            }



            # сохраняем журнал

            journal.save(

                fixture,

                prediction,

                fixture_id

            )



            # сохраняем историю

            save_prediction_history(

                fixture_id,

                prediction

            )



            results.append(

                prediction

            )



        except Exception as e:


            logger.error(

                f"Prediction error {fixture}: {e}",

                exc_info=True

            )



    logger.info(

        f"FAJ tour finished: {len(results)} predictions"

    )



    return results
