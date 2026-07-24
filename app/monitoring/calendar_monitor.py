# =====================================================
# FAJ Platform v6.1
# app/monitoring/calendar_monitor.py
#
# Universal Calendar Monitor
# =====================================================


from datetime import datetime


from app.database import get_db


from app.monitoring.rpl_calendar_parser import (
    parse_rpl_calendar
)




# =====================================================
# SAVE FIXTURE
# =====================================================


def save_fixture(
    fixture
):


    conn = get_db()


    try:


        existing = conn.execute(

            """

            SELECT id

            FROM fixtures

            WHERE league = ?

            AND season = ?

            AND round = ?

            AND home_team = ?

            AND away_team = ?

            LIMIT 1

            """,

            (

                fixture["league"],

                fixture["season"],

                fixture["round"],

                fixture["home_team"],

                fixture["away_team"]

            )

        ).fetchone()



        if existing:


            conn.execute(

                """

                UPDATE fixtures

                SET

                match_date = ?,

                status = ?

                WHERE id = ?

                """,

                (

                    fixture.get(
                        "match_date",
                        ""
                    ),

                    fixture.get(
                        "status",
                        "scheduled"
                    ),

                    existing["id"]

                )

            )



            action = "updated"



        else:


            conn.execute(

                """

                INSERT INTO fixtures

                (

                    league,

                    season,

                    round,

                    match_date,

                    home_team,

                    away_team,

                    status,

                    result,

                    winner,

                    prediction_created,

                    created

                )


                VALUES

                (

                    ?,?,?,?,?,?,?,?,?,?,?

                )

                """,

                (

                    fixture["league"],

                    fixture["season"],

                    fixture["round"],

                    fixture.get(
                        "match_date",
                        ""
                    ),

                    fixture["home_team"],

                    fixture["away_team"],

                    fixture.get(
                        "status",
                        "scheduled"
                    ),

                    "",

                    "",

                    False,

                    datetime.now().isoformat()

                )

            )



            action = "added"




        conn.commit()



        return action



    except Exception as e:


        conn.rollback()

        raise e



    finally:


        conn.close()




# =====================================================
# SYNC RPL CALENDAR
# =====================================================


def sync_rpl_calendar():



    fixtures = parse_rpl_calendar()



    if not fixtures:


        return {


            "league":
                "RPL",


            "season":
                "2026/27",


            "added":
                0,


            "updated":
                0,


            "unchanged":
                0,


            "errors":

                [

                    "Parser returned empty calendar"

                ]

        }




    added = 0

    updated = 0

    errors = []




    for fixture in fixtures:



        try:



            result = save_fixture(

                fixture

            )



            if result == "added":


                added += 1



            elif result == "updated":


                updated += 1




        except Exception as e:



            errors.append(

                {

                    "match":

                    (
                        fixture.get(
                            "home_team"
                        )
                        +

                        " - "

                        +

                        fixture.get(
                            "away_team"
                        )
                    ),


                    "error":

                    str(e)

                }

            )





    return {


        "league":

            "RPL",


        "season":

            "2026/27",


        "added":

            added,


        "updated":

            updated,


        "unchanged":

            0,


        "errors":

            errors


    }




# =====================================================
# CLEAR RPL FIXTURES
# =====================================================


def clear_rpl_calendar():



    conn = get_db()



    try:


        result = conn.execute(

            """

            DELETE FROM fixtures

            WHERE league = ?

            AND season = ?

            """,

            (

                "RPL",

                "2026/27"

            )

        )



        deleted = result.rowcount



        conn.commit()



        return deleted



    except Exception as e:


        conn.rollback()

        raise e



    finally:


        conn.close()
