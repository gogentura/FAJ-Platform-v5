# =====================================================
# FAJ Platform v6.2
# Passport Monitor
# =====================================================

import logging
from datetime import datetime

from app.database import get_db

logger = logging.getLogger(__name__)


# =====================================================
# LOAD TEAMS
# =====================================================

def get_all_teams():

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *
            FROM team_passports
            ORDER BY team_name
            """
        ).fetchall()

        return [dict(r) for r in rows]

    finally:

        conn.close()


# =====================================================
# LOAD LAST MATCHES
# =====================================================

def load_recent_matches(
    team_name,
    limit=5
):

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT *

            FROM fixtures

            WHERE
            home_team=?
            OR away_team=?

            ORDER BY match_date DESC

            LIMIT ?
            """,
            (
                team_name,
                team_name,
                limit
            )
        ).fetchall()

        return [dict(r) for r in rows]

    finally:

        conn.close()


# =====================================================
# UPDATE ONE PASSPORT
# =====================================================

def update_passport(
    passport
):

    team = passport["team_name"]

    logger.info(
        f"Updating passport: {team}"
    )

    matches = load_recent_matches(team)

    if len(matches) == 0:

        return {
            "team": team,
            "status": "no_matches"
        }

    # ---------------------------------------
    # Пока только фиксируем дату обновления.
    #
    # Далее сюда будем постепенно добавлять:
    #
    # attack
    # defence
    # control
    # form
    # tempo
    # injuries
    # transfers
    # fatigue
    # ---------------------------------------

    conn = get_db()

    try:

        conn.execute(
            """
            UPDATE team_passports

            SET

            updated=?

            WHERE team_name=?
            """,
            (
                datetime.now().isoformat(),
                team
            )
        )

        conn.commit()

    finally:

        conn.close()

    return {

        "team": team,

        "status": "updated",

        "matches": len(matches)

    }


# =====================================================
# UPDATE ALL PASSPORTS
# =====================================================

def update_all_passports():

    passports = get_all_teams()

    report = []

    for passport in passports:

        report.append(

            update_passport(
                passport
            )

        )

    logger.info(

        f"Updated {len(report)} passports"

    )

    return report
