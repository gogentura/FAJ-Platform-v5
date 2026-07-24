# =====================================================
# FAJ Platform v6.0
# Expert Manager
# Personal Expert Predictions Storage
# =====================================================


from datetime import datetime

from app.database import get_db



# =====================================================
# SAVE EXPERT PREDICTION
# =====================================================


def save_expert_prediction(
    fixture,
    score_prediction,
    winner_prediction,
    confidence,
    comment="",
    expert_name="Главный аналитик"
):


    conn = get_db()


    try:


        conn.execute(
        """
        INSERT INTO expert_predictions
        (

            fixture_id,

            league,

            season,

            round,

            home_team,

            away_team,

            winner_prediction,

            score_prediction,

            confidence,

            expert_name,

            comment,

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

            winner_prediction,

            score_prediction,

            confidence,

            expert_name,

            comment,

            datetime.now().isoformat()

        )

        )


        conn.commit()



    except Exception as e:


        conn.rollback()


        print(
            "EXPERT PREDICTION SAVE ERROR:",
            e
        )


        raise e



    finally:


        conn.close()



    return {

        "status": "saved",

        "match":
            f"{fixture.get('home_team')} - {fixture.get('away_team')}",

        "score":
            score_prediction

    }




# =====================================================
# GET EXPERT PREDICTIONS
# =====================================================


def get_expert_predictions(
    league=None,
    season=None,
    round_number=None
):


    conn = get_db()



    query = """

    SELECT *

    FROM expert_predictions

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
# COUNT EXPERT PREDICTIONS
# =====================================================


def count_expert_predictions():


    conn = get_db()



    row = conn.execute(

        """

        SELECT COUNT(*) AS cnt

        FROM expert_predictions

        """

    ).fetchone()



    conn.close()



    return row["cnt"] if row else 0




# =====================================================
# UPDATE EXPERT RESULT
# =====================================================


def update_expert_result(
    prediction_id,
    actual_score,
    actual_winner,
    accuracy
):


    conn = get_db()


    try:


        conn.execute(
        """

        UPDATE expert_predictions

        SET

        actual_score = ?,

        actual_winner = ?,

        accuracy = ?

        WHERE id = ?

        """,

        (

            actual_score,

            actual_winner,

            accuracy,

            prediction_id

        )

        )


        conn.commit()



    except Exception as e:


        conn.rollback()

        raise e



    finally:

        conn.close()
