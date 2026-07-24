# =====================================================
# FAJ Platform v6.0
# FAJ Prediction Generator
# =====================================================


from datetime import datetime


from app.database import get_db


from app.core.faj_core import FAJCore


from app.managers.prediction_manager import (
    save_prediction
)



# =====================================================
# FIND TEAM PASSPORT
# =====================================================


def get_team_passport(team_name):


    conn = get_db()


    row = conn.execute(
        """
        SELECT *

        FROM passports

        WHERE team_name = ?

        """,

        (
            team_name,
        )

    ).fetchone()


    conn.close()



    if row:

        return dict(row)


    return None




# =====================================================
# GET UPCOMING FIXTURES
# =====================================================


def get_upcoming_fixtures(
    league="RPL",
    season="2026/27"
):


    conn = get_db()


    rows = conn.execute(
        """

        SELECT *

        FROM fixtures

        WHERE league = ?

        AND season = ?

        AND status = 'scheduled'

        ORDER BY match_date


        """,

        (

            league,

            season

        )

    ).fetchall()



    conn.close()



    return [

        dict(row)

        for row in rows

    ]




# =====================================================
# GENERATE SINGLE PREDICTION
# =====================================================


def generate_prediction(
    fixture
):


    home = fixture["home_team"]

    away = fixture["away_team"]



    home_passport = get_team_passport(
        home
    )


    away_passport = get_team_passport(
        away
    )



    if not home_passport:

        raise Exception(
            f"Паспорт не найден: {home}"
        )



    if not away_passport:

        raise Exception(
            f"Паспорт не найден: {away}"
        )



    core = FAJCore()



    result = core.predict(

        home_passport,

        away_passport

    )



    save_prediction(

        fixture,

        result

    )



    return result




# =====================================================
# GENERATE TOUR
# =====================================================


def generate_rpl_predictions():



    fixtures = get_upcoming_fixtures()



    generated = 0

    errors = []



    for fixture in fixtures:


        try:


            generate_prediction(
                fixture
            )


            generated += 1



        except Exception as e:


            errors.append(

                {

                    "match":
                    f"{fixture.get('home_team')} - {fixture.get('away_team')}",


                    "error":
                    str(e)

                }

            )



    return {


        "league":
        "RPL",


        "season":
        "2026/27",


        "generated":
        generated,


        "errors":
        errors,


        "created":
        datetime.now().isoformat()

    }
