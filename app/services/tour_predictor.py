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

            f"Fixtures error: {e}",

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


            confidence,


            created

            )


            VALUES

            (

            %s,%s,%s,%s,%s,

            %s,%s,

            %s,%s,

            %s,

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
                "confidence",
                0
            )

            )

        )


        conn.commit()


        cur.close()

        conn.close()



    except Exception as e:


        logger.error(

            f"History error: {e}",

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

            "No scheduled fixtures"

        )


        return []



    results = []



    logger.info(

        f"FAJ predicting {len(fixtures)} matches"

    )



    for fixture in fixtures:


        try:



            fixture_id = fixture["id"]


            home = fixture["home_team"]

            away = fixture["away_team"]



            result = core.predict_match(

                home,

                away,

                league

            )



            if not result:

                continue



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

                    result["xg"]["predicted"]["home"],


                "xg_away":

                    result["xg"]["predicted"]["away"],


                "winner":

                    result["decision"]["winner_name"],


                "expected_score":

                    result["decision"]["expected_score"],


                "confidence":

                    result["decision"]["confidence"],


                "home_probability":

                    result["decision"]["home_probability"],


                "draw_probability":

                    result["decision"]["draw_probability"],


                "away_probability":

                    result["decision"]["away_probability"],


                "home_rating":

                    0,


                "away_rating":

                    0

            }



            # Journal


            journal.save(

                fixture,

                prediction,

                fixture_id

            )



            save_prediction_history(

                fixture_id,

                prediction

            )



            results.append(

                prediction

            )



        except Exception as e:



            logger.error(

                f"Match prediction error {fixture}: {e}",

                exc_info=True

            )



    return results
