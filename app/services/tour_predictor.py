# =====================================================
# FAJ Platform v6.5
# app/services/tour_predictor.py
#
# Tournament / Round Predictor
# FIXED VERSION
# =====================================================


import logging


from app.database import get_db


from app.services.prediction_pipeline import (
    prediction_pipeline
)


from app.managers.prediction_manager import (
    save_prediction
)



logger = logging.getLogger(__name__)





# =====================================================
# GET TOUR FIXTURES
# =====================================================


def get_tour_fixtures(

    league="RPL",

    season="2026/27"

):

    try:


        conn = get_db()

        cur = conn.cursor()



        cur.execute(

            """
            SELECT *

            FROM fixtures

            WHERE league = %s

            AND season = %s

            AND status = 'scheduled'

            ORDER BY match_date, match_time

            """,

            (
                league,
                season
            )

        )


        rows = cur.fetchall()



        cur.close()

        conn.close()



        fixtures = []



        for row in rows:


            try:

                fixtures.append(
                    dict(row)
                )

            except Exception:

                fixtures.append(
                    row
                )



        logger.info(

            "FAJ fixtures loaded: %s",

            len(fixtures)

        )



        return fixtures



    except Exception as e:


        logger.exception(

            "Fixtures loading failed"

        )


        return []







# =====================================================
# PREDICT SINGLE FIXTURE
# =====================================================


def predict_fixture(

    fixture

):


    home = fixture.get(
        "home_team"
    )


    away = fixture.get(
        "away_team"
    )


    league = fixture.get(
        "league",
        "RPL"
    )



    try:


        logger.info(

            "FAJ predicting fixture: %s - %s",

            home,

            away

        )



        # =============================================
        # FIX:
        # prediction_pipeline v6.5
        # принимает:
        #
        # home
        # away
        # league
        #
        # season НЕ передаем
        # =============================================


        prediction = prediction_pipeline.predict_match(

            home,

            away,

            league

        )



        if not prediction:


            logger.error(

                """
FAJ EMPTY PREDICTION

MATCH:
%s - %s

LEAGUE:
%s

FIXTURE:
%s

""",

                home,

                away,

                league,

                fixture

            )


            return None





        # =============================================
        # META DATA
        # =============================================


        prediction["fixture_id"] = fixture.get(
            "id"
        )


        prediction["round"] = fixture.get(
            "round"
        )


        prediction["match_date"] = fixture.get(
            "match_date"
        )


        prediction["match_time"] = fixture.get(
            "match_time"
        )


        prediction["season"] = fixture.get(
            "season",
            "2026/27"
        )


        return prediction





    except Exception as e:


        logger.exception(

            """
FAJ FIXTURE ERROR

%s - %s

ERROR:
%s

""",

            home,

            away,

            e

        )


        return None







# =====================================================
# SAVE TOUR PREDICTION
# =====================================================


def save_tour_prediction(

    fixture,

    prediction

):


    try:


        save_prediction(

            fixture,

            prediction

        )


        logger.info(

            "Prediction saved: %s - %s",

            fixture.get(
                "home_team"
            ),

            fixture.get(
                "away_team"
            )

        )


        return True



    except Exception as e:


        logger.exception(

            "Prediction save failed"

        )


        return False







# =====================================================
# MAIN TOUR GENERATOR
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

            """
NO FIXTURES

League:
%s

Season:
%s

""",

            league,

            season

        )


        return []





    results = []



    logger.info(

        "FAJ TOUR START %s matches",

        len(fixtures)

    )





    for fixture in fixtures:



        prediction = predict_fixture(

            fixture

        )



        if prediction is None:


            logger.error(

                "Skipped fixture: %s - %s",

                fixture.get(
                    "home_team"
                ),

                fixture.get(
                    "away_team"
                )

            )


            continue





        save_tour_prediction(

            fixture,

            prediction

        )



        results.append(

            prediction

        )





    logger.info(

        "FAJ TOUR FINISHED predictions=%s",

        len(results)

    )



    return results
