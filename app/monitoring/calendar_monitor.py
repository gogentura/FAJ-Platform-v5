# =====================================================
# FAJ Platform v6.3
# Calendar Monitor
# =====================================================

import logging

from app.database import get_connection
from app.monitoring.source_manager import SourceManager

logger = logging.getLogger(__name__)


class CalendarMonitor:

    def __init__(self):

        self.conn = get_connection()

        self.manager = SourceManager()

    # =================================================
    # UPSERT FIXTURE
    # =================================================

    def save_fixture(self, fixture):

        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO fixtures (

                league,
                season,

                match_date,
                match_time,

                home_team,
                away_team,

                status

            )

            VALUES (

                %(league)s,
                %(season)s,

                %(date)s,
                %(time)s,

                %(home_team)s,
                %(away_team)s,

                %(status)s

            )

            ON CONFLICT
            (
                league,
                season,
                match_date,
                home_team,
                away_team
            )

            DO UPDATE SET

                match_time = EXCLUDED.match_time,
                status = EXCLUDED.status;
            """,
            fixture
        )

        self.conn.commit()

    # =================================================
    # UPDATE CALENDAR
    # =================================================

    def update(self):

        fixtures = self.manager.get_calendar()

        added = 0
        updated = 0
        unchanged = 0

        errors = []

        cur = self.conn.cursor()

        for fixture in fixtures:

            try:

                cur.execute(
                    """
                    SELECT id, match_time, status

                    FROM fixtures

                    WHERE

                        league=%s
                        AND season=%s
                        AND match_date=%s
                        AND home_team=%s
                        AND away_team=%s
                    """,
                    (
                        fixture["league"],
                        fixture["season"],
                        fixture["date"],
                        fixture["home_team"],
                        fixture["away_team"],
                    )
                )

                row = cur.fetchone()

                if row is None:

                    self.save_fixture(fixture)

                    added += 1

                else:

                    db_time = row[1]
                    db_status = row[2]

                    if (
                        db_time != fixture["time"]
                        or
                        db_status != fixture["status"]
                    ):

                        self.save_fixture(fixture)

                        updated += 1

                    else:

                        unchanged += 1

            except Exception as e:

                logger.exception(e)

                errors.append(str(e))

        return {

            "league": "RPL",

            "season": "2026/27",

            "added": added,

            "updated": updated,

            "unchanged": unchanged,

            "errors": errors

        }


# =====================================================
# PUBLIC
# =====================================================

def sync_rpl_calendar():

    monitor = CalendarMonitor()

    return monitor.update()
