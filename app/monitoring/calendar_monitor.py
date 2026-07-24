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
    # SAVE FIXTURE
    # =================================================

    def save_fixture(self, fixture):

        cur = self.conn.cursor()


        cur.execute(
            """
            INSERT INTO fixtures
            (
                league,
                season,
                match_date,
                match_time,
                home_team,
                away_team,
                status,
                source
            )

            VALUES
            (
                %(league)s,
                %(season)s,
                %(date)s,
                %(time)s,
                %(home_team)s,
                %(away_team)s,
                %(status)s,
                'soccer365'
            )

            """,
            fixture
        )


        self.conn.commit()



    # =================================================
    # CHECK EXIST
    # =================================================

    def get_fixture(self, fixture):

        cur = self.conn.cursor()


        cur.execute(
            """
            SELECT
                id,
                match_time,
                status

            FROM fixtures

            WHERE
                league=%s
                AND season=%s
                AND match_date=%s
                AND home_team=%s
                AND away_team=%s

            LIMIT 1
            """,
            (
                fixture["league"],
                fixture["season"],
                fixture["date"],
                fixture["home_team"],
                fixture["away_team"]
            )
        )


        return cur.fetchone()



    # =================================================
    # UPDATE
    # =================================================

    def update(self):


        fixtures = self.manager.get_calendar()


        result = {

            "league": "RPL",
            "season": "2026/27",
            "added": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": []

        }



        for fixture in fixtures:


            try:


                row = self.get_fixture(
                    fixture
                )


                if row is None:


                    self.save_fixture(
                        fixture
                    )


                    result["added"] += 1



                else:


                    db_time = row["match_time"]

                    db_status = row["status"]



                    if (
                        db_time != fixture["time"]
                        or
                        db_status != fixture["status"]
                    ):


                        cur = self.conn.cursor()


                        cur.execute(
                            """
                            UPDATE fixtures

                            SET

                                match_time=%s,
                                status=%s,
                                updated=NOW()

                            WHERE id=%s

                            """,
                            (
                                fixture["time"],
                                fixture["status"],
                                row["id"]
                            )
                        )


                        self.conn.commit()


                        result["updated"] += 1



                    else:


                        result["unchanged"] += 1



            except Exception as e:


                logger.exception(e)


                result["errors"].append(

                    {
                        "match":
                        f"{fixture.get('home_team')} - {fixture.get('away_team')}",

                        "error":
                        repr(e)
                    }

                )



        return result





# =====================================================
# PUBLIC FUNCTION
# =====================================================


def sync_rpl_calendar():


    monitor = CalendarMonitor()


    return monitor.update()
