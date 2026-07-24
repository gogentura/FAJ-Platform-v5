# =====================================================
# FAJ Platform v6.1
# Calendar Monitor
# Контроль и обновление календарей турниров
# =====================================================


from datetime import datetime


from app.database import get_db


from app.monitoring.rpl_calendar_parser import (
    parse_rpl_calendar
)



# =====================================================
# COMPARE FIXTURES
# =====================================================


def compare_fixture(
    db_fixture,
    new_fixture
):


    changed = False


    changes = []



    fields = [

        "round",

        "match_date",

        "home_team",

        "away_team"

    ]



    for field in fields:


        old = db_fixture.get(
            field
        )


        new_key = field



        if field == "match_date":

            new = new_fixture.get(
                "date"
            )


        elif field == "home_team":

            new = new_fixture.get(
                "home"
            )


        elif field == "away_team":

            new = new_fixture.get(
                "away"
            )


        else:

            new = new_fixture.get(
                field
            )



        if str(old) != str(new):


            changed = True


            changes.append(

                {
                    "field": field,
                    "old": old,
                    "new": new
                }

            )



    return changed, changes




# =====================================================
# FIND FIXTURE
# =====================================================


def find_existing_fixture(
    fixture
):


    conn = get_db()



    row = conn.execute(

        """

        SELECT *

        FROM fixtures

        WHERE league = ?

        AND season = ?

        AND (

            home_team = ?

            OR

            away_team = ?

        )

        """,

        (

            fixture.get(
                "league"
            ),

            fixture.get(
                "season"
            ),

            fixture.get(
                "home"
            ),

            fixture.get(
                "away"
            )

        )

    ).fetchone()



    conn.close()



    return dict(row) if row else None




# =====================================================
# INSERT NEW FIXTURE
# =====================================================


def insert_fixture(
    fixture
):


    conn = get_db()



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

        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?,
        ?

    )


    """,

    (

        fixture.get(
            "league"
        ),

        fixture.get(
            "season"
        ),

        fixture.get(
            "round"
        ),

        fixture.get(
            "date"
        ),

        fixture.get(
            "home"
        ),

        fixture.get(
            "away"
        ),

        "scheduled",

        "",

        "",

        False,

        datetime.now().isoformat()

    )

    )


    conn.commit()

    conn.close()




# =====================================================
# UPDATE FIXTURE
# =====================================================


def update_fixture(
    fixture_id,
    fixture
):


    conn = get_db()



    conn.execute(

    """

    UPDATE fixtures


    SET

        round = ?,

        match_date = ?,

        home_team = ?,

        away_team = ?


    WHERE id = ?

    """,

    (

        fixture.get(
            "round"
        ),

        fixture.get(
            "date"
        ),

        fixture.get(
            "home"
        ),

        fixture.get(
            "away"
        ),

        fixture_id

    )

    )



    conn.commit()

    conn.close()




# =====================================================
# MAIN MONITOR
# =====================================================


def update_rpl_calendar():


    report = {


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


        "changes":
        []

    }




    fixtures = parse_rpl_calendar()



    for item in fixtures:



        existing = find_existing_fixture(
            item
        )



        if not existing:


            insert_fixture(
                item
            )


            report["added"] += 1


            continue




        changed, changes = compare_fixture(

            existing,

            item

        )



        if changed:


            update_fixture(

                existing["id"],

                item

            )


            report["updated"] += 1



            report["changes"].append(

                {

                    "match":

                    (
                        f"{item.get('home')} - "
                        f"{item.get('away')}"
                    ),


                    "changes":

                    changes

                }

            )



        else:


            report["unchanged"] += 1




    return report




# =====================================================
# DEBUG
# =====================================================


if __name__ == "__main__":


    result = update_rpl_calendar()


    print(result)
