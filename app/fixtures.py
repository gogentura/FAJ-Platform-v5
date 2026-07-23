# app/fixtures.py

from datetime import datetime
from app.database import get_db



# =====================================================
# SAVE FIXTURE
# =====================================================

def save_fixture(
    league,
    round_number,
    date,
    home_team,
    away_team
):

    conn = get_db()


    conn.execute(
    """
    INSERT INTO fixtures
    (
        league,
        round,
        date,
        home_team,
        away_team,
        status,
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
        ?
    )


    ON CONFLICT DO NOTHING

    """,

    (
        league,
        round_number,
        date,
        home_team,
        away_team,
        "scheduled",
        datetime.now().isoformat()
    )

    )


    conn.commit()

    conn.close()



# =====================================================
# GET UPCOMING FIXTURES
# =====================================================

def get_upcoming_fixtures(
    league=None,
    limit=20
):

    conn = get_db()


    if league:


        rows = conn.execute(
        """
        SELECT *

        FROM fixtures

        WHERE league = ?

        AND status = 'scheduled'

        ORDER BY date

        LIMIT ?

        """,

        (
            league,
            limit
        )

        ).fetchall()


    else:


        rows = conn.execute(
        """
        SELECT *

        FROM fixtures

        WHERE status = 'scheduled'

        ORDER BY date

        LIMIT ?

        """,

        (
            limit,
        )

        ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# GET TEAM FIXTURES
# =====================================================

def get_team_fixtures(
    team,
    limit=10
):

    conn = get_db()


    rows = conn.execute(
    """
    SELECT *

    FROM fixtures

    WHERE

    home_team = ?

    OR

    away_team = ?

    ORDER BY date

    LIMIT ?

    """,

    (
        team,
        team,
        limit
    )

    ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# FINISH MATCH
# =====================================================

def finish_fixture(
    home_team,
    away_team,
    score
):


    conn = get_db()



    home_goals, away_goals = map(
        int,
        score.split(":")
    )



    if home_goals > away_goals:

        winner = home_team


    elif away_goals > home_goals:

        winner = away_team


    else:

        winner = "Ничья"




    conn.execute(
    """
    UPDATE fixtures

    SET

    status = ?,

    result = ?,

    winner = ?

    WHERE

    home_team = ?

    AND

    away_team = ?

    """,

    (

        "finished",

        score,

        winner,

        home_team,

        away_team

    )

    )



    conn.commit()

    conn.close()



# =====================================================
# DELETE OLD FIXTURES
# =====================================================

def clear_fixtures():

    conn = get_db()


    conn.execute(
    """
    DELETE FROM fixtures
    """
    )


    conn.commit()

    conn.close()
