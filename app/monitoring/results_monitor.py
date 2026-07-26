# =====================================================
# FAJ Platform v6.6
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
# SAFE INT
# =====================================================

def safe_int(value):

    try:
        return int(value)

    except Exception:
        return None





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


        try:


            html = self.source.get_html()



            if not html:


                logger.warning(
                    "Soccer365 returned empty html"
                )


                return []



            logger.info(
                f"Soccer365 html length: {len(html)}"
            )



            results = []



            # =================================================
            # VARIANT 1
            # Акрон - Зенит (0-5)
            # =================================================


            patterns = [


                r"(.+?)\s-\s(.+?)\s\((\d+)-(\d+)\)",


                r"(.+?)\s-\s(.+?)\s\((\d+):(\d+)\)",


                r"(.+?)\s+(\d+)\s*:\s*(\d+)\s+(.+?)"


            ]



            for pattern in patterns:


                matches = re.findall(

                    pattern,

                    html,

                    re.MULTILINE

                )



                if matches:


                    logger.info(

                        f"Soccer365 matches found: {len(matches)}"

                    )


                    for m in matches:



                        try:



                            if len(m) == 4:


                                home = m[0].strip()

                                away = m[1].strip()

                                home_score = safe_int(
                                    m[2]
                                )

                                away_score = safe_int(
                                    m[3]
                                )



                            else:


                                home = m[0].strip()

                                home_score = safe_int(
                                    m[1]
                                )

                                away_score = safe_int(
                                    m[2]
                                )

                                away = m[3].strip()



                            if (

                                home_score is None

                                or

                                away_score is None

                            ):

                                continue





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



                        except Exception as e:


                            logger.warning(

                                f"Parse error: {e}"

                            )



                    break





            logger.info(

                f"Final results parsed: {len(results)}"

            )



            return results



        except Exception as e:



            logger.exception(

                f"Get results error: {e}"

            )


            return []







    # =================================================
    # UPDATE DATABASE
    # =================================================


    def update_results(self):


        results = self.get_results()



        if not results:


            return {


                "updated": 0,


                "errors": [

                    "Soccer365 results not found"

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


                    AND

                        status != 'finished'


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
