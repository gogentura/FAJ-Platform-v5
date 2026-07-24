# =====================================================
# FAJ Platform v6.0
# Prediction Manager
# FAJ Model Predictions Storage
# =====================================================


from datetime import datetime


from app.database import get_db


from app.core.faj_core import FAJCore




# =====================================================
# SAVE PREDICTION
# =====================================================


def save_prediction(
    fixture,
    prediction
):


    conn = get_db()



    try:


        conn.execute(
        """
        INSERT INTO predictions
        (

            fixture_id,

            league,

            season,

            round,

            home_team,

            away_team,

            winner_prediction,

            home_probability,

            draw_probability,

            away_probability,

            xg_home,

            xg_away,

            expected_score,

            top_scores,

            btts_probability,

            over25_probability,

            confidence,

            model_version,

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

            fixture.get("id"),

            fixture.get("league"),

            fixture.get("season"),

            fixture.get("round"),


            fixture.get("home_team"),

            fixture.get("away_team"),


            prediction.get("winner"),


            prediction.get(
                "home_probability",
                0
            ),


            prediction.get(
                "draw_probability",
                0
            ),


            prediction.get(
                "away_probability",
                0
            ),


            prediction.get(
                "xg_home",
                0
            ),


            prediction.get(
                "xg_away",
                0
            ),


            prediction.get(
                "expected_score",
                "-"
            ),


            str(
                prediction.get(
                    "top_scores",
                    []
                )
            ),


            prediction.get(
                "btts",
                0
            ),


            prediction.get(
                "over25",
                0
            ),


            prediction.get(
                "confidence",
                0
            ),


            "FAJ v6.0",


            datetime.now().isoformat()

        )

        )



        conn.commit()



    except Exception as e:


        conn.rollback()


        print(
            "PREDICTION SAVE ERROR:",
            e
        )


        raise e



    finally:


        conn.close()




# =====================================================
# CREATE SINGLE PREDICTION
# =====================================================


def create_prediction(
    fixture,
    core=None
):


    if core is None:


        core = FAJCore()



    home_team = fixture.get(
        "home_team"
    )


    away_team = fixture.get(
        "away_team"
    )



    # =============================================
    # RUN FAJ MODEL
    # =============================================


    prediction = core.predict(

        home_team,

        away_team

    )



    # =============================================
    # SAVE
    # =============================================


    save_prediction(

        fixture,

        prediction

    )



    return prediction




# =====================================================
# CREATE TOUR PREDICTIONS
# =====================================================


def create_tour_predictions(
    fixtures,
    core=None
):


    results = []



    for fixture in fixtures:


        try:


            prediction = create_prediction(

                fixture,

                core

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
# GET FAJ PREDICTIONS
# =====================================================


def get_predictions(
    league=None,
    season=None,
    round_number=None
):


    conn = get_db()



    try:


        query = """

        SELECT *

        FROM predictions

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



        if round_number:


            query += """

            AND round = ?

            """

            params.append(
                round_number
            )



        query += """

        ORDER BY created DESC

        """



        rows = conn.execute(

            query,

            tuple(params)

        ).fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:


        conn.close()




# =====================================================
# COUNT PREDICTIONS
# =====================================================


def count_predictions():


    conn = get_db()



    try:


        row = conn.execute(

            """

            SELECT COUNT(*) AS cnt

            FROM predictions

            """

        ).fetchone()



        return row["cnt"] if row else 0



    finally:


        conn.close()
