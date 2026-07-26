# =====================================================
# FAJ Platform v7.0
# Results Monitor
#
# Soccer365 Results
# Database Sync
# Calibration Pipeline
# =====================================================


import logging


from app.data_sources.soccer365_results import (
    Soccer365Results
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

        self.source = Soccer365Results()



    # =================================================
    # LOAD RESULTS
    # =================================================

    def get_results(self):

        try:

            results = self.source.get_results()

            logger.info(

                f"Loaded results: {len(results)}"

            )

            return results


        except Exception as e:

            logger.exception(e)

            return []



    # =================================================
    # CALCULATE RESULT
    # =================================================

    @staticmethod
    def calculate_result(

        home_score,

        away_score

    ):

        if home_score > away_score:

            return "home_win"


        if home_score < away_score:

            return "away_win"


        return "draw"



    # =================================================
    # UPDATE DATABASE
    # =================================================

    def update_results(self):


        results = self.get_results()



        if not results:


            return {

                "updated": 0,

                "errors": [
                    "Soccer365 results empty"
                ]

            }



        conn = get_connection()

        cur = conn.cursor()



        updated = 0

        errors = []



        for match in results:


            try:


                result = self.calculate_result(

                    match["home_score"],

                    match["away_score"]

                )



                cur.execute(

                    """
                    UPDATE fixtures

                    SET

                        status = %s,

                        home_score = %s,

                        away_score = %s,

                        result = %s,

                        updated = NOW()


                    WHERE

                        league = %s

                    AND

                        home_team = %s

                    AND

                        away_team = %s

                    """,

                    (

                        "finished",

                        match["home_score"],

                        match["away_score"],

                        result,

                        "RPL",

                        match["home_team"],

                        match["away_team"]

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
