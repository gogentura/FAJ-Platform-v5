# =====================================================
# FAJ Platform v5.2
# Universal Fixtures Loader
# =====================================================


from datetime import datetime

from app.database import get_db



# =====================================================
# NORMALIZE TEAM NAME
# =====================================================

def normalize_team(team):

    if not team:
        return ""

    return (
        team
        .strip()
    )



# =====================================================
# SAVE SINGLE FIXTURE
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


    try:

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

            normalize_team(home_team),

            normalize_team(away_team),

            "scheduled",

            False,

            datetime.now().isoformat()

        )

        )


        conn.commit()


    except Exception as e:

        conn.rollback()

        print(
            "FIXTURE SAVE ERROR:",
            e
        )

        raise e


    finally:

        conn.close()



# =====================================================
# BULK LOAD FIXTURES
# =====================================================

def load_fixtures(
    league: str,
    season: str,
    fixtures: list
):


    """
    Универсальная загрузка календаря


    Формат:

    fixtures = [

        {
            "round":1,
            "date":"2026-07-19",
            "home":"Зенит",
            "away":"Спартак"
        }

    ]

    """


    loaded = 0

    errors = []



    for fixture in fixtures:


        try:


            save_fixture(

                league,

                season,

                fixture.get(
                    "round",
                    0
                ),

                fixture.get(
                    "date",
                    ""
                ),

                fixture.get(
                    "home",
                    ""
                ),

                fixture.get(
                    "away",
                    ""
                )

            )


            loaded += 1



        except Exception as e:


            errors.append(
                {
                    "fixture": fixture,
                    "error": str(e)
                }
            )



    return {

        "league": league,

        "season": season,

        "loaded": loaded,

        "errors": errors

    }



# =====================================================
# GET FIXTURES
# =====================================================

def get_fixtures(
    league=None,
    season=None
):


    conn = get_db()


    query = """
    SELECT *

    FROM fixtures

    WHERE 1=1

    """

    params = []



    if league:

        query += """
        AND league = ?
        """

        params.append(
            league
        )



    if season:

        query += """
        AND season = ?
        """

        params.append(
            season
        )



    query += """

    ORDER BY match_date

    """



    rows = conn.execute(
        query,
        tuple(params)
    ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# GET UPCOMING FIXTURES
# =====================================================

def get_upcoming_fixtures(
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
# MARK FIXTURE PREDICTED
# =====================================================

def mark_prediction_created(
    home_team,
    away_team
):


    conn = get_db()


    conn.execute(
    """
    UPDATE fixtures

    SET

    prediction_created = ?

    WHERE

    home_team = ?

    AND away_team = ?

    """,

    (

        True,

        home_team,

        away_team

    )

    )


    conn.commit()

    conn.close()



# =====================================================
# COUNT FIXTURES
# =====================================================

def count_fixtures(
    league=None
):


    conn = get_db()


    if league:


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


    else:


        row = conn.execute(
        """
        SELECT COUNT(*) AS cnt

        FROM fixtures

        """

        ).fetchone()



    conn.close()



    return row["cnt"] if row else 0
