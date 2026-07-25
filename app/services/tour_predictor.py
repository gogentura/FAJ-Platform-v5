# =====================================================
# FAJ Platform v6.4
# app/services/tour_predictor.py
#
# Tournament / Round Predictor
# =====================================================

import logging
from datetime import datetime

from app.database import get_connection

from app.predict import predict_match

from app.journal import Journal


logger = logging.getLogger(__name__)


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


            home_probability,
            draw_probability,
            away_probability,


            home_rating,
            away_rating,


            confidence,

            risk,

            grade,


            created


            )


            VALUES

            (

            %s,

            %s,%s,

            %s,%s,

            %s,%s,

            %s,

            %s,


            %s,%s,%s,


            %s,%s,


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
                "Высокий"
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



            prediction = predict_match(

                home,

                away,

                league

            )


            if not prediction:

                continue



            prediction["fixture_id"] = fixture_id

            prediction["home_team"] = home
            prediction["away_team"] = away


            prediction["season"] = season



            # журнал

            journal.save(

                fixture,

                prediction,

                fixture_id

            )


            # история

            save_prediction_history(

                fixture_id,

                prediction

            )


            results.append(

                prediction

            )



        except Exception as e:


            logger.error(

                "Tour match error %s: %s",

                fixture,

                e,

                exc_info=True

            )



    logger.info(

        "FAJ tour prediction finished: %s",

        len(results)

    )


    return results
