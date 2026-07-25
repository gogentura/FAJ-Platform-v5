# =====================================================
# FAJ Platform v6.5
# app/services/tour_predictor.py
# =====================================================

import logging

from app.database import get_connection
from app.services.prediction_pipeline import PredictionPipeline

logger = logging.getLogger(__name__)

pipeline = PredictionPipeline()


# =====================================================
# FIXTURES
# =====================================================

def get_tour_matches(
    league="RPL",
    season="2026/27"
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *

        FROM fixtures

        WHERE league=%s
          AND season=%s
          AND status='scheduled'

        ORDER BY match_date
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


# =====================================================
# MAIN
# =====================================================

def predict_tour(
    league="RPL",
    season="2026/27"
):

    fixtures = get_tour_matches(
        league,
        season
    )

    logger.info(
        "Fixtures found: %s",
        len(fixtures)
    )

    results = []

    for fixture in fixtures:

        try:

            prediction = pipeline.predict_fixture(
                fixture
            )

            if prediction:

                results.append(
                    prediction
                )

        except Exception as e:

            logger.exception(e)

    logger.info(
        "Predictions generated: %s",
        len(results)
    )

    return results
