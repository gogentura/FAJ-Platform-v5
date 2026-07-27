# =====================================================
# FAJ Platform v6.9.6
# app/services/tour_predictor.py
#
# Tournament Prediction Service
#
# Fixtures
#      ↓
# Team Passports
#      ↓
# Prediction Pipeline
#      ↓
# Prediction Manager
#      ↓
# PostgreSQL
#
# =====================================================


import logging


from app.database import get_db


from app.services.prediction_pipeline import (
    predict_match_pipeline
)


from app.managers.prediction_manager import (
    save_prediction,
    clear_predictions
)


logger = logging.getLogger(__name__)





# =====================================================
# LOAD FIXTURES
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

            WHERE league=%s

            AND season=%s

            AND status='scheduled'

            ORDER BY match_date, match_time

            """,
            (
                league,
                season
            )
        )


        rows = cur.fetchall()


        conn.close()


        fixtures=[]


        for row in rows:

            try:

                fixtures.append(
                    dict(row)
                )

            except:

                fixtures.append(
                    row
                )


        logger.info(
            "Fixtures loaded: %s",
            len(fixtures)
        )


        return fixtures



    except Exception as e:


        logger.error(
            "Fixtures loading error: %s",
            e,
            exc_info=True
        )


        return []







# =====================================================
# LOAD TEAM PASSPORT
# =====================================================


def get_team_passport(
        team_name
):

    try:

        conn = get_db()
        cur = conn.cursor()


        cur.execute(

            """
            SELECT *

            FROM passports

            WHERE team_name=%s

            LIMIT 1

            """,

            (
                team_name,
            )

        )


        row = cur.fetchone()


        conn.close()



        if row:

            try:

                return dict(row)

            except:

                return row



        logger.warning(
            "Passport not found: %s",
            team_name
        )


        return None



    except Exception as e:


        logger.error(
            "Passport loading error: %s",
            e,
            exc_info=True
        )


        return None







# =====================================================
# ENRICH
# =====================================================


def enrich_prediction(
        prediction,
        fixture
):

    if not prediction:

        return None



    prediction["fixture_id"] = fixture.get(
        "id"
    )


    prediction["home_team"] = fixture.get(
        "home_team"
    )


    prediction["away_team"] = fixture.get(
        "away_team"
    )


    prediction["league"] = fixture.get(
        "league",
        "RPL"
    )


    prediction["season"] = fixture.get(
        "season",
        "2026/27"
    )


    return prediction







# =====================================================
# SINGLE MATCH
# =====================================================


def predict_fixture(
        fixture
):

    try:


        home = fixture.get(
            "home_team"
        )


        away = fixture.get(
            "away_team"
        )



        logger.info(
            "Predicting: %s - %s",
            home,
            away
        )



        home_passport = get_team_passport(
            home
        )


        away_passport = get_team_passport(
            away
        )



        if not home_passport or not away_passport:


            logger.warning(

                "Missing passport: %s - %s",

                home,

                away

            )


            return None




        prediction = predict_match_pipeline(

            fixture,

            home_passport,

            away_passport

        )



        if not prediction:


            logger.warning(

                "Pipeline returned empty: %s - %s",

                home,

                away

            )


            return None



        return enrich_prediction(

            prediction,

            fixture

        )




    except Exception as e:


        logger.error(

            "Prediction fixture error: %s",

            e,

            exc_info=True

        )


        return None







# =====================================================
# GENERATE TOUR
# =====================================================


def predict_tour(
        league="RPL",
        season="2026/27"
):


    logger.info(
        "FAJ tour generation started"
    )



    clear_predictions()



    fixtures = get_tour_fixtures(

        league,

        season

    )



    if not fixtures:


        logger.warning(
            "No fixtures found"
        )


        return []




    results=[]



    for fixture in fixtures:



        prediction = predict_fixture(

            fixture

        )



        if not prediction:

            continue



        saved = save_prediction(

            fixture,

            prediction

        )



        if saved:


            results.append(

                prediction

            )



    logger.info(

        "FAJ tour completed: %s",

        len(results)

    )



    return results





# =====================================================
# END
# =====================================================
