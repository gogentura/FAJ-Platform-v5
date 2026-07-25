# =====================================================
# FAJ Platform v6.5
# app/services/tour_predictor.py
# =====================================================

import logging

from app.database import get_db
from app.services.prediction_pipeline import PredictionPipeline

logger = logging.getLogger(__name__)


# =====================================================
# GET TOUR FIXTURES
# =====================================================

def get_tour_fixtures(
    league="RPL",
    season="2026/27"
):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT *

            FROM fixtures

            WHERE league=%s
              AND season=%s
              AND status='scheduled'
              AND prediction_created = FALSE

            ORDER BY match_date,
                     match_time
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

        logger.exception(e)

        conn.close()

        return []


# =====================================================
# SAVE FLAG
# =====================================================

def mark_prediction_created(fixture_id):

    conn = get_db()

    try:

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE fixtures

            SET prediction_created = TRUE

            WHERE id=%s
            """,
            (fixture_id,)
        )

        conn.commit()

        cur.close()
        conn.close()

    except Exception:

        logger.exception("mark_prediction_created")

        conn.close()


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

    logger.info(
        "Fixtures found: %s",
        len(fixtures)
    )

    pipeline = PredictionPipeline()

    results = []

    for fixture in fixtures:

        try:

            prediction = pipeline.predict_fixture(
                fixture
            )

            if prediction:

                results.append(prediction)

                mark_prediction_created(
                    fixture["id"]
                )

        except Exception:

            logger.exception(
                "Prediction error"
            )

    logger.info(
        "Predictions created: %s",
        len(results)
    )

    return results
