# =====================================================
# FAJ Platform v6.9.6
# app/services/tour_predictor.py
#
# Tournament Prediction Service
#
# Fixtures
#       |
#       v
# Team Passport Resolver
#       |
#       v
# Prediction Pipeline
#       |
#       v
# Prediction Manager
#       |
#       v
# PostgreSQL predictions
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
# TEAM NAME NORMALIZER
# =====================================================


def normalize_team_name(
    name
):

    if not name:
        return ""


    name = str(name).lower().strip()


    replacements = {

        "фк ": "",
        "фк.": "",

        "футбольный клуб ": "",

        "москва": "",
        "м": "м",

        "ростов-на-дону":
        "ростов",

        "динамо махачкала":
        "динамо мх",

        "динамо москва":
        "динамо м",

        "локомотив москва":
        "локомотив",

        "краснодар фк":
        "краснодар",

        "зенит санкт-петербург":
        "зенит",

        "спартак москва":
        "спартак",

    }


    for old, new in replacements.items():

        name = name.replace(
            old,
            new
        )


    return (
        name
        .replace(
            " ",
            ""
        )
    )




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
            "FAJ fixtures loaded: %s",
            len(fixtures)
        )


        return fixtures



    except Exception as e:


        logger.error(
            "Fixture loading error: %s",
            e,
            exc_info=True
        )


        return []





# =====================================================
# PASSPORT CHECK
# =====================================================


def passport_exists(
    team_name
):

    try:

        conn = get_db()

        cur = conn.cursor()



        cur.execute(
            """
            SELECT *

            FROM passports
            """
        )


        rows = cur.fetchall()


        conn.close()



        target = normalize_team_name(
            team_name
        )


        for row in rows:


            try:

                passport_team = row["team_name"]

            except:

                passport_team = row[0]



            if normalize_team_name(
                passport_team
            ) == target:

                return True



        logger.warning(
            "PASSPORT NOT FOUND: %s",
            team_name
        )


        return False



    except Exception as e:


        logger.error(
            "Passport check error: %s",
            e,
            exc_info=True
        )


        return False





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



    if not passport_exists(home):

        logger.warning(
            "MATCH SKIPPED WITHOUT PASSPORT: %s - %s",
            home,
            away
        )

        return None



    if not passport_exists(away):

        logger.warning(
            "MATCH SKIPPED WITHOUT PASSPORT: %s - %s",
            home,
            away
        )

        return None



    try:


        prediction = predict_match_pipeline(

            home,

            away,

            fixture.get(
                "league",
                "RPL"
            ),

            fixture.get(
                "season",
                "2026/27"
            )

        )



        if not prediction:

            return None



        return enrich_prediction(
            prediction,
            fixture
        )



    except Exception as e:


        logger.error(
            "Prediction error %s - %s : %s",
            home,
            away,
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
        "FAJ TOUR START"
    )


    clear_predictions()



    fixtures = get_tour_fixtures(
        league,
        season
    )



    if not fixtures:


        logger.warning(
            "NO FIXTURES"
        )


        return []



    results=[]


    skipped=[]



    for fixture in fixtures:


        prediction = predict_fixture(
            fixture
        )


        if not prediction:


            skipped.append(

                f"{fixture.get('home_team')} - {fixture.get('away_team')}"

            )

            continue



        if save_prediction(

            fixture,

            prediction

        ):


            results.append(
                prediction
            )



    logger.info(
        "FAJ TOUR FINISHED: %s predictions",
        len(results)
    )



    if skipped:

        logger.warning(
            "MATCHES WITHOUT PREDICTIONS: %s",
            skipped
        )


    return results



# =====================================================
# END
# =====================================================
