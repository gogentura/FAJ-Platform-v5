# =====================================================
# FAJ Platform v6.2
# Results Monitor
# =====================================================

import logging
from datetime import datetime

from app.database import get_db

logger = logging.getLogger(__name__)


# =====================================================
# LOAD SCHEDULED MATCHES
# =====================================================

def get_scheduled_matches():

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *

            FROM fixtures

            WHERE status='scheduled'

            ORDER BY match_date
            """
        ).fetchall()

        return [dict(r) for r in rows]

    finally:

        conn.close()


# =====================================================
# SAVE RESULT
# =====================================================

def update_fixture_result(
    fixture_id,
    home_score,
    away_score
):

    conn = get_db()

    try:

        if home_score > away_score:

            winner = "home"

        elif away_score > home_score:

            winner = "away"

        else:

            winner = "draw"

        conn.execute(
            """
            UPDATE fixtures

            SET

                status=?,

                result=?,

                winner=?,

                updated=?

            WHERE id=?
            """,

            (
                "finished",

                f"{home_score}:{away_score}",

                winner,

                datetime.now().isoformat(),

                fixture_id
            )
        )

        conn.commit()

        return True

    except Exception as e:

        conn.rollback()

        logger.exception(e)

        return False

    finally:

        conn.close()


# =====================================================
# FETCH RESULT
# =====================================================

def fetch_result_from_sources(
    fixture
):

    """
    Пока заглушка.

    Позже сюда подключаются:

    Soccer365

    Flashscore

    API Football
    """

    return None


# =====================================================
# UPDATE RESULTS
# =====================================================

def update_results():

    fixtures = get_scheduled_matches()

    report = {

        "checked": 0,

        "updated": 0,

        "errors": []

    }

    for fixture in fixtures:

        report["checked"] += 1

        result = fetch_result_from_sources(
            fixture
        )

        if result is None:

            continue

        ok = update_fixture_result(

            fixture["id"],

            result["home_score"],

            result["away_score"]

        )

        if ok:

            report["updated"] += 1

        else:

            report["errors"].append(

                fixture["id"]

            )

    logger.info(report)

    return report
