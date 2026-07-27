# =====================================================
# FAJ Platform v6.9.3
# app/managers/prediction_manager.py
# =====================================================

import logging
from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================

def safe_float(value):
    try:
        return float(value or 0)
    except:
        return 0



# =====================================================
# CLEAR
# =====================================================

def clear_predictions():

    try:

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM predictions
            """
        )

        conn.commit()
        conn.close()

        logger.info(
            "FAJ predictions cleared"
        )

        return True


    except Exception as e:

        logger.error(
            "Clear error: %s",
            e,
            exc_info=True
        )

        return False




# =====================================================
# SAVE
# =====================================================

def save_prediction(
    fixture,
    prediction
):

    try:

        if not fixture or not prediction:

            return False


        conn = get_db()
        cur = conn.cursor()


        winner = prediction.get(
            "winner",
            "-"
        )


        score = prediction.get(
            "expected_score",
            "-"
        )


        cur.execute(
            """
            INSERT INTO predictions
            (
                fixture_id,
                home_win,
                draw,
                away_win,
                xg_home,
                xg_away,
                score_prediction,
                confidence,
                model_version,
                created
            )

            VALUES
            (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s
            )
            """,

            (

                fixture.get("id"),

                safe_float(
                    prediction.get(
                        "home_probability"
                    )
                ) / 100,


                safe_float(
                    prediction.get(
                        "draw_probability"
                    )
                ) / 100,


                safe_float(
                    prediction.get(
                        "away_probability"
                    )
                ) / 100,


                safe_float(
                    prediction.get(
                        "xg_home"
                    )
                ),


                safe_float(
                    prediction.get(
                        "xg_away"
                    )
                ),


                f"{winner}|{score}",


                safe_float(
                    prediction.get(
                        "confidence"
                    )
                ),


                "FAJ v6.9.3",


                datetime.now()

            )
        )


        conn.commit()
        conn.close()


        return True



    except Exception as e:


        logger.error(
            "Save prediction error: %s",
            e,
            exc_info=True
        )

        return False




# =====================================================
# GET PREDICTIONS
# =====================================================

def get_predictions(
    limit=20
):


    try:

        conn=get_db()
        cur=conn.cursor()


        cur.execute(
            """
            SELECT
                p.*,
                f.home_team,
                f.away_team,
                f.league,
                f.season

            FROM predictions p

            LEFT JOIN fixtures f
            ON p.fixture_id=f.id


            ORDER BY p.created DESC

            LIMIT %s
            """,

            (
                limit,
            )

        )


        rows=cur.fetchall()


        conn.close()


        result=[]


        for row in rows:


            data=dict(row)


            score=data.get(
                "score_prediction",
                "-"
            )


            winner="-"


            expected="-"


            if "|" in score:

                parts=score.split("|")

                winner=parts[0]

                expected=parts[1]


            data["winner"]=winner

            data["expected_score"]=expected


            result.append(
                data
            )


        return result



    except Exception as e:


        logger.error(
            "get_predictions error: %s",
            e,
            exc_info=True
        )


        return []




# =====================================================
# HISTORY
# =====================================================

def get_prediction_history(
    limit=100
):

    try:

        conn=get_db()
        cur=conn.cursor()


        cur.execute(
            """
            SELECT *
            FROM predictions
            ORDER BY created DESC
            LIMIT %s
            """,

            (
                limit,
            )
        )


        rows=cur.fetchall()

        conn.close()

        return rows


    except Exception as e:

        logger.error(
            "History error: %s",
            e
        )

        return []




# =====================================================
# ONE
# =====================================================

def get_prediction_by_id(
    prediction_id
):

    try:

        conn=get_db()
        cur=conn.cursor()


        cur.execute(
            """
            SELECT *
            FROM predictions
            WHERE id=%s
            """,
            (
                prediction_id,
            )
        )


        row=cur.fetchone()

        conn.close()


        if row:
            return dict(row)


        return None


    except Exception as e:

        logger.error(
            "Prediction id error: %s",
            e
        )

        return None



# =====================================================
# EXPORT
# =====================================================

__all__=[
    "clear_predictions",
    "save_prediction",
    "get_predictions",
    "get_prediction_history",
    "get_prediction_by_id"
]
