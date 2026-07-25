# =====================================================
# FAJ Platform v6.4.1
# app/services/tour_predictor.py
#
# FAJ Tour Predictor
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

            AND status IN

            (

                'scheduled',
                'pending',
                'NS',
                'not_started'

            )

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

            "FAJ fixtures loaded: %s",

            len(rows)

        )


        return rows



    except Exception as e:


        logger.error(

            "Fixtures load error: %s",

            e,

            exc_info=True

        )


        return []





# =====================================================
# SAVE HISTORY
# =====================================================


def save_history(

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


            predicted_score,

            predicted_winner,


            home_probability,

            draw_probability,

            away_probability,


            xg_home,

            xg_away,


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

            %s,%s,%s,

            %s,%s,

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
            EXCLUDED.confidence


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
                "xg_home",
                0
            ),


            prediction.get(
                "xg_away",
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

            "History save error: %s",

            e,

            exc_info=True

        )





# =====================================================
# TOUR PREDICTION
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



    for fixture in fixtures:



        try:



            fixture_id = fixture["id"]


            home = fixture["home_team"]


            away = fixture["away_team"]



            logger.info(

                "Predicting %s - %s",

                home,

                away

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



                "expected_score":

                    decision.get(

                        "expected_score",

                        "-"

                    ),



                "winner":

                    decision.get(

                        "winner_name",

                        decision.get(

                            "winner",

                            "-"

                        )

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



                "xg_home":

                    result["xg"]["predicted"]["home"],



                "xg_away":

                    result["xg"]["predicted"]["away"],



                "home_rating":

                    result.get(

                        "home_rating",

                        0

                    ),



                "away_rating":

                    result.get(

                        "away_rating",

                        0

                    ),



                "confidence":

                    decision.get(

                        "confidence",

                        0

                    )

            }



            results.append(

                prediction

            )



            # журнал

            journal.save(

                match=f"{home} — {away}",

                fixture_id=fixture_id,

                prediction=prediction

            )



            save_history(

                fixture_id,

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

        "FAJ tour finished: %s predictions",

        len(results)

    )



    return results
