# =====================================================
# FAJ Platform v6.4
# app/services/tour_predictor.py
#
# Tournament / Round Predictor
# =====================================================


import logging


from app.database import get_connection

from app.core.faj_core import FAJCore

from app.journal import Journal



logger = logging.getLogger(__name__)



journal = Journal()

core = FAJCore()



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

            "Tour fixtures error: %s",

            e,

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



    results = []



    logger.info(

        "FAJ tour prediction started: %s matches",

        len(fixtures)

    )



    for fixture in fixtures:



        try:



            fixture_id = fixture["id"]



            home = fixture["home_team"]

            away = fixture["away_team"]



            logger.info(

                "Predicting: %s — %s",

                home,

                away

            )



            # =========================================
            # FAJ CORE
            # =========================================


            prediction = core.predict_match(

                home,

                away,

                league

            )



            if not prediction:


                continue



            # =========================================
            # META
            # =========================================


            prediction["fixture_id"] = fixture_id


            prediction["home_team"] = home

            prediction["away_team"] = away


            prediction["league"] = league

            prediction["season"] = season



            # =========================================
            # JOURNAL
            # =========================================


            journal.save(

                match=f"{home} — {away}",

                prediction=prediction,

                fixture_id=fixture_id

            )



            results.append(

                prediction

            )



        except Exception as e:



            logger.error(

                "Tour prediction error %s: %s",

                fixture,

                e,

                exc_info=True

            )




    logger.info(

        "FAJ tour prediction finished: %s",

        len(results)

    )



    return results
