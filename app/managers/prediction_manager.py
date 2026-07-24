# =====================================================
# FAJ Platform v6.0
# Prediction Manager
# FAJ Model Predictions Storage
# =====================================================


from datetime import datetime


from app.database import get_db


from app.core.faj_core import FAJCore




# =====================================================
# CREATE SINGLE FAJ PREDICTION
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
    # RUN MODEL
    # =============================================

    prediction = core.predict(

        home_team,

        away_team

    )



    # =============================================
    # SAVE
    # =============================================


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

            home_team,

            away_team,

            prediction.get(
                "winner"
            ),

            prediction.get(
                "home_probability"
            ),

            prediction.get(
                "draw_probability"
            ),

            prediction.get(
                "away_probability"
            ),

            prediction.get(
                "xg_home"
            ),

            prediction.get(
                "xg_away"
            ),

            prediction.get(
                "expected_score"
            ),

            str(
                prediction.get(
                    "top_scores"
                )
            ),

            prediction.get(
                "btts"
            ),

            prediction.get(
                "over25"
            ),

            prediction.get(
                "confidence"
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


            result = create_prediction(

                fixture,

                core

            )


            results.append(

                {
                    "fixture": fixture,

                    "prediction": result

                }

            )


        except Exception as e:


            results.append(

                {
                    "fixture": fixture,

                    "error": str(e)

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



    conn.close()



    return [

        dict(row)

        for row in rows

    ]



# =====================================================
# COUNT FAJ PREDICTIONS
# =====================================================


def count_predictions():


    conn = get_db()



    row = conn.execute(

        """

        SELECT COUNT(*) AS cnt

        FROM predictions

        """

    ).fetchone()



    conn.close()



    return row["cnt"] if row else 0
