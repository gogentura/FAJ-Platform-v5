# =====================================================
# FAJ Platform v6.0
# FAJ Prediction Generator
# Tournament Prediction Builder
# =====================================================


from datetime import datetime


from app.database import get_db


from app.managers.prediction_manager import (
    create_prediction
)



# =====================================================
# GET UPCOMING FIXTURES
# =====================================================


def get_upcoming_fixtures(
    league="RPL",
    season="2026/27"
):


    conn = get_db()


    try:


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



        return [

            dict(row)

            for row in rows

        ]



    finally:


        conn.close()




# =====================================================
# GENERATE SINGLE MATCH
# =====================================================


def generate_match_prediction(
    fixture
):


    result = create_prediction(

        fixture

    )


    return result




# =====================================================
# GENERATE ALL TOUR PREDICTIONS
# =====================================================


def generate_rpl_predictions():


    fixtures = get_upcoming_fixtures(

        league="RPL",

        season="2026/27"

    )



    generated = 0


    errors = []



    predictions = []



    for fixture in fixtures:


        try:



            result = generate_match_prediction(

                fixture

            )



            predictions.append(

                {

                    "match":

                    f"{fixture.get('home_team')} - {fixture.get('away_team')}",


                    "prediction":

                    result

                }

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


        "predictions":

        predictions,


        "created":

        datetime.now().isoformat()

    }




# =====================================================
# GENERATE SELECTED ROUND
# =====================================================


def generate_round_predictions(
    round_number
):


    conn = get_db()



    try:


        rows = conn.execute(
        """

        SELECT *

        FROM fixtures

        WHERE league = ?

        AND season = ?

        AND round = ?

        AND status = 'scheduled'


        """,

        (

            "RPL",

            "2026/27",

            round_number

        )

        ).fetchall()



        fixtures = [

            dict(row)

            for row in rows

        ]



    finally:


        conn.close()



    results = []



    for fixture in fixtures:


        try:


            prediction = create_prediction(

                fixture

            )


            results.append(

                {

                    "fixture":

                    fixture,


                    "prediction":

                    prediction

                }

            )



        except Exception as e:


            results.append(

                {

                    "fixture":

                    fixture,


                    "error":

                    str(e)

                }

            )



    return results




# =====================================================
# TEST
# =====================================================


if __name__ == "__main__":


    result = generate_rpl_predictions()



    print(
        "========== FAJ GENERATOR =========="
    )


    print(
        result
    )
