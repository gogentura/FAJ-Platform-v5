# =====================================================
# FAJ Platform v6.4
# app/services/tour_predictor.py
#
# Tour Predictor
# Works with FAJCore + PostgreSQL
# =====================================================


import logging
from datetime import datetime


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

                'pending'

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

            "FAJ fixtures found: %s",

            len(rows)

        )


        return rows



    except Exception as e:


        logger.error(

            f"Fixtures loading error: {e}",

            exc_info=True

        )


        return []





# =====================================================
# PREDICT ONE MATCH
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



    if not result:

        return None



    decision = result.get(

        "decision",

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

            fixture.get(

                "season",

                "2026/27"

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

            ),



        "xg_home":

            result["xg"]["predicted"]["home"],



        "xg_away":

            result["xg"]["predicted"]["away"],



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



        "top_scores":

            result.get(

                "simulation",

                {}

            ).get(

                "top_scores",

                []

            )

    }



    return prediction





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


            prediction = predict_fixture(

                fixture,

                league

            )



            if not prediction:

                continue



            # сохраняем в журнал


            journal.save(

                match=

                f"{prediction['home_team']} — {prediction['away_team']}",


                fixture_id=

                prediction["fixture_id"],


                prediction=

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

        "FAJ tour predictions created: %s",

        len(results)

    )


    return results
