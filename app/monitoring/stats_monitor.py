# =====================================================
# FAJ Platform v6.2
# Match Statistics Monitor
# =====================================================

import logging
from datetime import datetime

from app.database import get_db

logger = logging.getLogger(__name__)


# =====================================================
# SAVE MATCH STATISTICS
# =====================================================

def save_match_statistics(stats: dict):

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO team_match_stats
            (
                fixture_id,

                league,

                season,

                round,

                home_team,

                away_team,

                home_score,

                away_score,

                xg_home,

                xg_away,

                shots_home,

                shots_away,

                shots_on_target_home,

                shots_on_target_away,

                possession_home,

                possession_away,

                corners_home,

                corners_away,

                yellow_home,

                yellow_away,

                red_home,

                red_away,

                created
            )

            VALUES
            (
                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?
            )
            """,
            (
                stats.get("fixture_id"),

                stats.get("league"),

                stats.get("season"),

                stats.get("round"),

                stats.get("home_team"),

                stats.get("away_team"),

                stats.get("home_score"),

                stats.get("away_score"),

                stats.get("xg_home"),

                stats.get("xg_away"),

                stats.get("shots_home"),

                stats.get("shots_away"),

                stats.get("shots_on_target_home"),

                stats.get("shots_on_target_away"),

                stats.get("possession_home"),

                stats.get("possession_away"),

                stats.get("corners_home"),

                stats.get("corners_away"),

                stats.get("yellow_home"),

                stats.get("yellow_away"),

                stats.get("red_home"),

                stats.get("red_away"),

                datetime.now().isoformat()
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
# LOAD NOT FINISHED FIXTURES
# =====================================================

def get_finished_matches():

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *

            FROM fixtures

            WHERE
                status='finished'
            """
        ).fetchall()

        return [dict(r) for r in rows]

    finally:

        conn.close()


# =====================================================
# UPDATE MATCH STATISTICS
# =====================================================

def update_statistics():

    fixtures = get_finished_matches()

    report = {

        "processed": 0,

        "saved": 0,

        "errors": []
    }

    for fixture in fixtures:

        report["processed"] += 1

        # -------------------------------------------------
        # Пока данные-заглушка.
        #
        # Следующим этапом сюда подключаются:
        #
        # Soccer365
        # Flashscore
        # NB-Bet
        # API Football
        # -------------------------------------------------

        stats = {

            "fixture_id":
                fixture.get("id"),

            "league":
                fixture.get("league"),

            "season":
                fixture.get("season"),

            "round":
                fixture.get("round"),

            "home_team":
                fixture.get("home_team"),

            "away_team":
                fixture.get("away_team"),

            "home_score": None,

            "away_score": None,

            "xg_home": None,

            "xg_away": None,

            "shots_home": None,

            "shots_away": None,

            "shots_on_target_home": None,

            "shots_on_target_away": None,

            "possession_home": None,

            "possession_away": None,

            "corners_home": None,

            "corners_away": None,

            "yellow_home": None,

            "yellow_away": None,

            "red_home": None,

            "red_away": None

        }

        ok = save_match_statistics(stats)

        if ok:

            report["saved"] += 1

        else:

            report["errors"].append(

                fixture.get("id")

            )

    logger.info(report)

    return report
