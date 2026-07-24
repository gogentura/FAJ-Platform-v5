# =====================================================
# FAJ Platform v6.0
# Prediction Manager
# FAJ Model Predictions Storage
# =====================================================


from datetime import datetime


from app.database import get_db


from app.core.faj_core import FAJCore




# =====================================================
# ADAPTER FAJ CORE RESPONSE
# =====================================================


def normalize_prediction(
    raw_prediction
):


    if not raw_prediction:

        return {}



    decision = raw_prediction.get(
        "decision",
        {}
    )



    predicted_xg = (
        raw_prediction
        .get("xg", {})
        .get("predicted", {})
    )



    return {


        "winner":
        decision.get(
            "winner"
        ),



        "home_probability":
        decision.get(
            "home_prob",
            0
        ),



        "draw_probability":
        decision.get(
            "draw_prob",
            0
        ),



        "away_probability":
        decision.get(
            "away_prob",
            0
        ),



        "xg_home":
        predicted_xg.get(
            "home",
            0
        ),



        "xg_away":
        predicted_xg.get(
            "away",
            0
        ),



        "expected_score":
        decision.get(
            "expected_score"
        ),



        "top_scores":
        raw_prediction.get(
            "top_scores",
            []
        ),



        "btts":
        raw_prediction.get(
            "btts",
            0
        ),



        "over25":
        raw_prediction.get(
            "over25",
            0
        ),



        "confidence":
        decision.get(
            "confidence",
            0
        )


    }




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


            fixture.get(
                "id"
            ),


            fixture.get(
                "league",
                "RPL"
            ),


            fixture.get(
                "season",
                "2026/27"
            ),


            fixture.get(
                "round"
            ),



            fixture.get(
                "home_team"
            ),


            fixture.get(
                "away_team"
            ),



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

        raise e



    finally:


        conn.close()




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
    # CALL MODEL
    # =============================================


    if hasattr(
        core,
        "predict"
    ):


        raw = core.predict(

            home_team,

            away_team,

            fixture.get(
                "league",
                "RPL"
            )

        )


    else:


        raw = core.predict_match(

            home_team,

            away_team,

            fixture.get(
                "league",
                "RPL"
            )

        )



    # =============================================
    # ERROR CHECK
    # =============================================


    if "error" in raw:


        raise Exception(
            raw["error"]
        )



    prediction = normalize_prediction(
        raw
    )



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



    errors = []



    for fixture in fixtures:


        try:


            prediction = create_prediction(

                fixture,

                core

            )



            results.append(

                prediction

            )



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


        "generated":

        len(results),



        "errors":

        errors,


        "league":

        "RPL",



        "season":

        "2026/27"



    }




# =====================================================
# GET PREDICTIONS
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

            AND league=?

            """


            params.append(
                league
            )



        if season:


            query += """

            AND season=?

            """


            params.append(
                season
            )



        if round_number:


            query += """

            AND round=?

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
# COUNT
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
