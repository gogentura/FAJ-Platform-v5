# =====================================================
# FAJ Platform v6.2
# Prediction Scheduler
# =====================================================

import logging

from app.database import get_db

from app.managers.prediction_manager import (
    create_tour_predictions
)

logger = logging.getLogger(__name__)


# =====================================================
# LOAD NEXT ROUND
# =====================================================

def load_next_round():

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT MIN(round) AS rnd

            FROM fixtures

            WHERE
                status='scheduled'
            """
        ).fetchone()

        if row is None:

            return None

        if row["rnd"] is None:

            return None

        round_number = row["rnd"]

        rows = conn.execute(
            """
            SELECT *

            FROM fixtures

            WHERE

                status='scheduled'

                AND round=?

            ORDER BY match_date
            """,
            (
                round_number,
            )
        ).fetchall()

        return [

            dict(r)

            for r in rows

        ]

    finally:

        conn.close()


# =====================================================
# GENERATE
# =====================================================

def run_prediction_scheduler(core=None):

    fixtures = load_next_round()

    if fixtures is None:

        return {

            "status": "no_round"

        }

    report = create_tour_predictions(

        fixtures,

        core

    )

    logger.info(report)

    return report
