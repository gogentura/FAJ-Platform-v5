# =====================================================
# FAJ Platform v6.2
# app/monitoring/results_monitor.py
#
# Match Results Monitor
#
# Source:
#   Soccer365
#
# DB:
#   PostgreSQL fixtures
# =====================================================


import logging
import re


from app.monitoring.sources.soccer365 import (
    Soccer365Source
)


from app.database import (
    get_connection
)



logger = logging.getLogger(__name__)



# =====================================================
# RESULTS MONITOR
# =====================================================


class ResultsMonitor:



    def __init__(self):

        self.source = Soccer365Source()



    # =================================================
    # LOAD RESULTS
    # =================================================

    def get_results(self):


        html = self.source.get_html()


        if not html:

            return []



        results = []



        # ------------------------------------------------
        # Ищем завершённые матчи
        #
        # пример Soccer365:
        #
        # Акрон - Ротор (0-1)
        #
        # ------------------------------------------------


        pattern = re.compile(

            r"(.+?)\s-\s(.+?)\s"
            r"\((\d+)-(\d+)\)"

        )



        matches = pattern.findall(
            html
        )



        for match in matches:


            home = (
                match[0]
                .strip()
            )


            away = (
                match[1]
                .strip()
            )


            home_score = int(
                match[2]
            )


            away_score = int(
                match[3]
            )



            results.append(

                {

                    "home_team":
                    self.source.normalize_team(
                        home
                    ),


                    "away_team":
                    self.source.normalize_team(
                        away
                    ),


                    "home_score":
                    home_score,


                    "away_score":
                    away_score,


                    "status":
                    "finished"

                }

            )



        logger.info(

            f"Results found: {len(results)}"

        )



        return results



    # =================================================
    # UPDATE DATABASE
    # =================================================

    def update_results(self):


        results = self.get_results()


        if not results:

            return {

                "updated": 0,

                "errors": [
                    "No results found"
                ]

            }



        conn = get_connection()


        cur = conn.cursor()



        updated = 0

        errors = []



        for item in results:


            try:


                if item["home_score"] > item["away_score"]:

                    result = "home_win"


                elif item["home_score"] < item["away_score"]:

                    result = "away_win"


                else:

                    result = "draw"



                cur.execute(

                    """
                    UPDATE fixtures

                    SET

                    status=%s,

                    home_score=%s,

                    away_score=%s,

                    result=%s,

                    updated=NOW()


                    WHERE

                    league=%s

                    AND home_team=%s

                    AND away_team=%s

                    """,

                    (

                        "finished",

                        item["home_score"],

                        item["away_score"],

                        result,

                        "RPL",

                        item["home_team"],

                        item["away_team"]

                    )

                )



                if cur.rowcount > 0:

                    updated += 1



            except Exception as e:


                logger.exception(e)


                errors.append(

                    str(e)

                )



        conn.commit()

        conn.close()



        return {


            "updated":

            updated,


            "errors":

            errors

        }



# =====================================================
# PUBLIC FUNCTION
# =====================================================


def sync_results():


    monitor = ResultsMonitor()


    return monitor.update_results()
