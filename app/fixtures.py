# =====================================================
# FAJ Platform v5.2
# Fixtures Manager
# Управление календарём матчей
# =====================================================


from datetime import datetime

from app.database import get_db



# =====================================================
# SAVE FIXTURE
# =====================================================


def save_fixture(
    league: str,
    season: str,
    round_number: int,
    match_date: str,
    home_team: str,
    away_team: str
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
        ?
    )


    ON CONFLICT DO NOTHING

    """,

    (

        league,

        season,

        round_number,

        match_date,

        home_team,

        away_team,

        "scheduled",

        False,

        datetime.now().isoformat()

    )

    )


    conn.commit()

    conn.close()



# =====================================================
# GET NEXT MATCHES
# =====================================================


def get_next_matches(
    league="RPL",
    limit=10
):

    conn = get_db()


    rows = conn.execute(
    """
    SELECT *

    FROM fixtures

    WHERE league = ?

    AND status = 'scheduled'

    ORDER BY match_date

    LIMIT ?

    """,

    (
        league,

        limit
    )

    ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# GET ROUND
# =====================================================


def get_round_matches(
    league,
    round_number
):


    conn = get_db()


    rows = conn.execute(
    """
    SELECT *

    FROM fixtures

    WHERE league = ?

    AND round = ?

    ORDER BY match_date

    """,

    (

        league,

        round_number

    )

    ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# GET TEAM CALENDAR
# =====================================================


def get_team_calendar(
    team,
    limit=20
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

    ORDER BY match_date

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
# MARK PREDICTED
# =====================================================


def mark_predicted(
    home_team,
    away_team
):


    conn = get_db()


    conn.execute(
    """
    UPDATE fixtures

    SET

    status = ?,

    prediction_created = ?

    WHERE

    home_team = ?

    AND

    away_team = ?

    """,

    (

        "predicted",

        True,

        home_team,

        away_team

    )

    )


    conn.commit()

    conn.close()



# =====================================================
# FINISH FIXTURE
# =====================================================


def finish_fixture(
    home_team,
    away_team,
    score
):


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



    conn = get_db()



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
# DELETE SEASON
# =====================================================


def clear_season(
    league,
    season
):


    conn = get_db()


    conn.execute(
    """
    DELETE FROM fixtures

    WHERE league = ?

    AND season = ?

    """,

    (

        league,

        season

    )

    )


    conn.commit()

    conn.close()



# =====================================================
# COUNT FIXTURES
# =====================================================


def count_fixtures(
    league="RPL"
):


    conn = get_db()


    row = conn.execute(
    """
    SELECT COUNT(*) AS cnt

    FROM fixtures

    WHERE league = ?

    """,

    (
        league,
    )

    ).fetchone()



    conn.close()



    return row["cnt"] if row else 0
