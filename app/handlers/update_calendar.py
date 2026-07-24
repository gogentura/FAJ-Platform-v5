# =====================================================
# FAJ Platform v6.3
# app/monitoring/calendar_monitor.py
#
# RPL Calendar Monitor
# Source:
#   Soccer365
# =====================================================


import logging


from app.database import get_db


from app.monitoring.sources.soccer365 import (
    Soccer365Source
)



logger = logging.getLogger(__name__)



# =====================================================
# SYNC RPL CALENDAR
# =====================================================


def sync_rpl_calendar():


    result = {

        "league": "RPL",

        "season": "2026/27",

        "added": 0,

        "updated": 0,

        "unchanged": 0,

        "errors": []

    }



    source = Soccer365Source()



    try:


        fixtures = source.parse_calendar()



    except Exception as e:


        result["errors"].append(

            {

                "source": "soccer365",

                "error": repr(e)

            }

        )


        return result



    if not fixtures:


        return result



    conn = None



    try:


        conn = get_db()

        cur = conn.cursor()



        for fixture in fixtures:



            try:



                # -------------------------------------
                # CHECK DUPLICATE
                # -------------------------------------


                cur.execute(

                    """
                    SELECT id,
                           match_date,
                           match_time,
                           status,
                           match_url
                    FROM fixtures
                    WHERE league=%s
                    AND season=%s
                    AND home_team=%s
                    AND away_team=%s
                    LIMIT 1
                    """,

                    (

                        fixture["league"],

                        fixture["season"],

                        fixture["home_team"],

                        fixture["away_team"]

                    )

                )



                existing = cur.fetchone()



                # -------------------------------------
                # INSERT
                # -------------------------------------


                if not existing:



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
                            source,
                            match_url
                        )

                        VALUES
                        (
                            %s,%s,%s,%s,%s,%s,%s,%s,%s
                        )

                        """,

                        (

                            fixture["league"],

                            fixture["season"],

                            fixture["date"],

                            fixture["time"],

                            fixture["home_team"],

                            fixture["away_team"],

                            fixture["status"],

                            "soccer365",

                            fixture.get(
                                "match_url"
                            )

                        )

                    )



                    result["added"] += 1



                # -------------------------------------
                # UPDATE
                # -------------------------------------


                else:



                    changed = False



                    if existing.get(
                        "match_url"
                    ) != fixture.get(
                        "match_url"
                    ):


                        changed = True



                    if existing.get(
                        "match_date"
                    ).isoformat() != fixture["date"]:


                        changed = True



                    if changed:



                        cur.execute(

                            """
                            UPDATE fixtures

                            SET

                            match_date=%s,

                            match_time=%s,

                            match_url=%s,

                            updated=NOW()

                            WHERE id=%s

                            """,

                            (

                                fixture["date"],

                                fixture["time"],

                                fixture.get(
                                    "match_url"
                                ),

                                existing["id"]

                            )

                        )



                        result["updated"] += 1



                    else:


                        result["unchanged"] += 1





            except Exception as e:



                result["errors"].append(

                    {

                        "match":

                        f"{fixture.get('home_team')} - {fixture.get('away_team')}",


                        "error":

                        repr(e)

                    }

                )



        conn.commit()



    except Exception as e:



        result["errors"].append(

            {

                "database":

                repr(e)

            }

        )


        if conn:

            conn.rollback()



    finally:


        if conn:

            conn.close()



    logger.info(

        f"RPL calendar sync: {result}"

    )



    return result
