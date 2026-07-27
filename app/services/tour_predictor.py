# =====================================================
# FAJ Platform v6.9.6
# app/services/tour_predictor.py
#
# Tournament Prediction Service
#
# Fixtures
#      ↓
# Passport Loader
#      ↓
# FAJ Prediction Pipeline
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
# TEAM ALIASES
# =====================================================

TEAM_ALIASES = {

    "Ростов": [
        "Ростов",
        "ФК Ростов",
        "Ростов ФК"
    ],

    "Динамо М": [
        "Динамо М",
        "Динамо Москва",
        "Динамо"
    ],

    "Динамо Мх": [
        "Динамо Мх",
        "Динамо Махачкала",
        "Динамо Мах."
    ],

    "Краснодар": [
        "Краснодар",
        "ФК Краснодар"
    ],

    "Зенит": [
        "Зенит",
        "Зенит СПб"
    ],

    "Спартак": [
        "Спартак",
        "Спартак Москва"
    ],

    "ЦСКА": [
        "ЦСКА",
        "ЦСКА Москва"
    ],

}





# =====================================================
# FIXTURES
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
            "FAJ FIXTURES FOUND: %s",
            len(fixtures)
        )


        return fixtures



    except Exception as e:


        logger.error(
            "Fixtures error: %s",
            e,
            exc_info=True
        )


        return []







# =====================================================
# PASSPORT FINDER
# =====================================================


def get_team_passport(
        team_name
):

    try:


        conn = get_db()
        cur = conn.cursor()



        names = [

            team_name

        ]



        if team_name in TEAM_ALIASES:

            names.extend(
                TEAM_ALIASES[team_name]
            )



        columns = [

            "team_name",
            "name",
            "team",
            "club_name",
            "club"

        ]




        for name in names:



            for column in columns:



                try:


                    query = f"""

                    SELECT *

                    FROM passports

                    WHERE {column}=%s

                    LIMIT 1

                    """



                    cur.execute(

                        query,

                        (
                            name,
                        )

                    )



                    row = cur.fetchone()



                    if row:


                        conn.close()



                        try:

                            passport = dict(row)

                        except:

                            passport = row



                        logger.info(

                            "PASSPORT FOUND: %s via %s",

                            name,

                            column

                        )



                        return passport



                except Exception:

                    continue




        conn.close()



        logger.warning(

            "PASSPORT NOT FOUND: %s",

            team_name

        )


        return None




    except Exception as e:


        logger.error(

            "Passport error %s: %s",

            team_name,

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
# MATCH
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

            "FAJ MATCH: %s - %s",

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

                "MATCH SKIPPED WITHOUT PASSPORT: %s - %s",

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

                "PIPELINE EMPTY: %s - %s",

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

            "Prediction error: %s",

            e,

            exc_info=True

        )


        return None







# =====================================================
# TOUR
# =====================================================


def predict_tour(

        league="RPL",

        season="2026/27"

):


    logger.info(
        "FAJ TOUR START"
    )



    try:

        clear_predictions()


    except Exception as e:


        logger.warning(

            "Clear skipped: %s",

            e

        )




    fixtures = get_tour_fixtures(

        league,

        season

    )



    if not fixtures:


        logger.warning(

            "NO FIXTURES FOUND"

        )


        return []




    results=[]

    missing=[]





    for fixture in fixtures:



        prediction = predict_fixture(

            fixture

        )



        if not prediction:


            missing.append(

                f"{fixture.get('home_team')} - {fixture.get('away_team')}"

            )


            continue




        saved = save_prediction(

            fixture,

            prediction

        )



        if saved:


            results.append(

                prediction

            )





    if missing:


        logger.warning(

            "MATCHES WITHOUT PREDICTIONS: %s",

            missing

        )




    logger.info(

        "FAJ TOUR FINISHED: %s predictions",

        len(results)

    )



    return results




# =====================================================
# END
# =====================================================
