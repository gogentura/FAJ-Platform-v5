# =====================================================
# FAJ Platform v6.4
# app/services/tour_predictor.py
#
# FAJ Tournament Predictor Service
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



        # Диагностика

        cur.execute(

            """

            SELECT

                id,

                home_team,

                away_team,

                league,

                season,

                status

            FROM fixtures


            WHERE league=%s

            AND season=%s


            ORDER BY date NULLS LAST


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

            f"Tour fixtures error: {e}",

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


        logger.warning(

            f"History save skipped: {e}"

        )




# =====================================================
# NORMALIZE CORE RESULT
# =====================================================


def normalize_prediction(

    result,

    home,

    away,

    league,

    season

):


    xg = result.get(

        "xg",

        {}

    ).get(

        "predicted",

        {}

    )



    decision = result.get(

        "decision",

        {}

    )



    simulation = result.get(

        "simulation",

        {}

    )



    return {


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



        "confidence":

            decision.get(

                "confidence",

                0

            ),



        "top_scores":

            simulation.get(

                "top_scores",

                []

            )

    }




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

            "FAJ: no fixtures"

        )


        return []



    predictions = []



    logger.info(

        "FAJ tour start: %s matches",

        len(fixtures)

    )



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



            prediction = normalize_prediction(

                result,

                home,

                away,

                league,

                season

            )



            prediction["fixture_id"] = fixture_id



            # Journal

            journal.save(

                match=f"{home} — {away}",

                fixture_id=fixture_id,

                prediction=prediction

            )



            # History

            save_prediction_history(

                fixture_id,

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

        "FAJ tour finished: %s",

        len(predictions)

    )



    return predictions
