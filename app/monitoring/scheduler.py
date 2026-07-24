# =====================================================
# FAJ Platform v6.2
# Monitoring Scheduler
# =====================================================

import logging
from datetime import datetime

from app.monitoring.calendar_monitor import sync_calendar
from app.monitoring.results_monitor import update_results
from app.monitoring.stats_monitor import update_statistics
from app.monitoring.passport_monitor import update_all_passports

logger = logging.getLogger(__name__)


# =====================================================
# FULL PIPELINE
# =====================================================

def run_scheduler():

    logger.info("=======================================")
    logger.info("FAJ Monitoring Scheduler started")
    logger.info("=======================================")

    started = datetime.now()

    report = {}

    try:

        # -----------------------------------------
        # 1. Calendar
        # -----------------------------------------

        logger.info("STEP 1 :: Calendar")

        report["calendar"] = sync_calendar(
            league="RPL",
            season="2026/27"
        )

        # -----------------------------------------
        # 2. Results
        # -----------------------------------------

        logger.info("STEP 2 :: Results")

        report["results"] = update_results()

        # -----------------------------------------
        # 3. Statistics
        # -----------------------------------------

        logger.info("STEP 3 :: Statistics")

        report["statistics"] = update_statistics()

        # -----------------------------------------
        # 4. Passports
        # -----------------------------------------

        logger.info("STEP 4 :: Passports")

        report["passports"] = update_all_passports()

        # -----------------------------------------
        # Prediction Manager
        # подключим позже
        # -----------------------------------------

        report["predictions"] = "waiting"

    except Exception as e:

        logger.exception(e)

        report["error"] = str(e)

    finished = datetime.now()

    report["started"] = started.isoformat()

    report["finished"] = finished.isoformat()

    report["duration"] = str(
        finished - started
    )

    logger.info(report)

    return report


# =====================================================
# MANUAL RUN
# =====================================================

if __name__ == "__main__":

    run_scheduler()
