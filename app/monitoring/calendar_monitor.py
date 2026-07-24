# =====================================================
# FAJ Platform v6.2
# app/monitoring/calendar_monitor.py
#
# Calendar synchronization layer
# Source:
#   Soccer365
#
# Logic:
#   INSERT new fixtures
#   UPDATE changed fixtures
#   KEEP history
# =====================================================

import logging
from datetime import datetime

from app.monitoring.sources.soccer365 import (
    Soccer365Source
)

from app.database import Database


logger = logging.getLogger(__name__)


class CalendarMonitor:


    def __init__(self):

        self.source = Soccer365Source()

        self.db = Database()



    # =================================================
    # SYNC CALENDAR
    # =================================================

    async def sync_calendar(
        self,
        league="RPL",
        season="2026/27"
    ):


        logger.info(
            "Starting calendar sync..."
        )


        fixtures = (
            self.source
            .parse_calendar()
        )


        if not fixtures:

            logger.warning(
                "Parser returned empty calendar"
            )

            return {

                "added": 0,

                "updated": 0,

                "same": 0,

                "errors": [

                    "Parser returned empty calendar"

                ]

            }



        added = 0

        updated = 0

        same = 0

        errors = []



        for match in fixtures:


            try:


                result = await self.save_fixture(
                    match
                )


                if result == "added":

                    added += 1


                elif result == "updated":

                    updated += 1


                else:

                    same += 1



            except Exception as e:


                logger.exception(e)


                errors.append(

                    str(e)

                )



        logger.info(

            f"""
Calendar sync finished

Added:
{added}

Updated:
{updated}

Same:
{same}
"""

        )



        return {

            "added": added,

            "updated": updated,

            "same": same,

            "errors": errors

        }



    # =================================================
    # SAVE FIXTURE
    # =================================================

    async def save_fixture(
        self,
        fixture
    ):


        existing = (
            self.db.get_fixture(
                league="RPL",
                season=fixture["season"],
                home_team=fixture["home_team"],
                away_team=fixture["away_team"]
            )
        )



        if not existing:


            self.db.insert_fixture(

                {

                    "league":
                    fixture["league"],


                    "season":
                    fixture["season"],


                    "date":
                    fixture["date"],


                    "time":
                    fixture["time"],


                    "home_team":
                    fixture["home_team"],


                    "away_team":
                    fixture["away_team"],


                    "status":
                    fixture["status"]

                }

            )


            return "added"



        changed = False



        fields = [

            "date",

            "time",

            "status"

        ]



        for field in fields:


            if (

                existing.get(field)

                !=

                fixture.get(field)

            ):

                changed = True



        if changed:


            self.db.update_fixture(

                existing["id"],

                {

                    "date":
                    fixture["date"],


                    "time":
                    fixture["time"],


                    "status":
                    fixture["status"]

                }

            )


            return "updated"



        return "same"



# =====================================================
# SERVICE FUNCTION
# =====================================================


async def update_rpl_calendar():


    monitor = CalendarMonitor()


    return await monitor.sync_calendar()
