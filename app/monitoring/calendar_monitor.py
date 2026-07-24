# =====================================================
# FAJ Platform v6.2
# app/monitoring/calendar_monitor.py
#
# Calendar Synchronization Layer
#
# Source:
#   Soccer365
#
# DB:
#   PostgreSQL fixtures
# =====================================================

import logging


from app.monitoring.sources.soccer365 import (
    Soccer365Source
)


from app.database import (
    Database
)


logger = logging.getLogger(__name__)


# =====================================================
# MONITOR
# =====================================================


class CalendarMonitor:


    def __init__(self):

        self.source = Soccer365Source()

        self.db = Database()



    # =================================================
    # MAIN SYNC
    # =================================================

    async def sync_calendar(

        self,

        league="RPL",

        season="2026/27"

    ):


        logger.info(
            "FAJ Calendar sync started"
        )


        fixtures = (
            self.source
            .parse_calendar()
        )



        if not fixtures:


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



        for fixture in fixtures:


            try:


                result = (
                    await self.save_fixture(
                        fixture
                    )
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

                league=fixture["league"],

                season=fixture["season"],

                home_team=fixture["home_team"],

                away_team=fixture["away_team"]

            )

        )



        # ---------------------------------------------
        # NEW MATCH
        # ---------------------------------------------

        if not existing:



            self.db.insert_fixture(

                fixture

            )


            logger.info(

                f"Added fixture: "
                f"{fixture['home_team']} - "
                f"{fixture['away_team']}"

            )


            return "added"



        # ---------------------------------------------
        # UPDATE
        # ---------------------------------------------

        changed = False



        compare_fields = [


            "date",

            "time",

            "status"

        ]



        for field in compare_fields:


            if existing.get(field) != fixture.get(field):

                changed = True



        if changed:



            self.db.update_fixture(

                existing["id"],

                fixture

            )


            logger.info(

                f"Updated fixture: "
                f"{fixture['home_team']} - "
                f"{fixture['away_team']}"

            )


            return "updated"



        return "same"



# =====================================================
# PUBLIC FUNCTIONS
# =====================================================


async def sync_rpl_calendar():


    monitor = CalendarMonitor()


    return await monitor.sync_calendar(

        league="RPL",

        season="2026/27"

    )



async def update_rpl_calendar():


    return await sync_rpl_calendar()
