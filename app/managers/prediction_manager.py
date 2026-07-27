# =====================================================
# FAJ Platform v6.9.6
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# Compatible:
# - prediction_pipeline v6.9.x
# - tour_predictor v6.9.x
# - Telegram Viewer v6.9.5
#
# =====================================================

import logging
import json

from datetime import datetime

from app.database import get_db


logger = logging.getLogger(__name__)


# =====================================================
# SAFE
# =====================================================

def safe_float(value):

    try:

        if value is None:
            return 0

        return float(value)

    except Exception:

        return 0



def safe_json(value):

    try:

        if value is None:
            return json.dumps({})

        if isinstance(value, str):
            return value

        return json.dumps(
            value,
            ensure_ascii=False
        )

    except Exception:

        return json.dumps({})



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
            "Clear predictions error: %s",
            e,
            exc_info=True
        )

        return False



# =====================================================
# SAVE ONE
# =====================================================

def save_prediction(
    fixture,
    prediction
):

    try:

        if not fixture:
            return False


        if not prediction:
            return False



        conn = get_db()
        cur = conn.cursor()



        # Основная совместимая запись
        cur.execute(
            """
            INSERT INTO predictions
            (
                fixture_id,

                home_team,
                away_team,

                winner,
                expected_score,

                xg_home,
                xg_away,

                confidence,

                model_version,

                created_at
            )

            VALUES
            (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s
            )
            """,

            (

                fixture.get(
                    "id"
                ),


                fixture.get(
                    "home_team",
                    "-"
                ),


                fixture.get(
                    "away_team",
                    "-"
                ),


                prediction.get(
                    "winner",
                    "-"
                ),


                prediction.get(
                    "expected_score",
                    prediction.get(
                        "score_prediction",
                        "-"
                    )
                ),


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


                safe_float(
                    prediction.get(
                        "confidence"
                    )
                ),


                "FAJ v6.9.6",


                datetime.now()

            )
        )


        conn.commit()
        conn.close()



        logger.info(
            "Prediction saved: %s - %s",
            fixture.get("home_team"),
            fixture.get("away_team")
        )


        return True



    except Exception as e:


        logger.error(
            "SAVE prediction error: %s",
            e,
            exc_info=True
        )


        return False



# =====================================================
# BATCH
# =====================================================

def save_predictions_batch(
    fixtures,
    predictions
):

    saved = 0


    if not fixtures or not predictions:

        return 0



    for fixture, prediction in zip(
        fixtures,
        predictions
    ):

        if save_prediction(
            fixture,
            prediction
        ):

            saved += 1



    logger.info(
        "Batch saved %s/%s",
        saved,
        len(predictions)
    )


    return saved



# =====================================================
# READ
# =====================================================

def get_predictions(
    limit=20
):

    try:

        conn = get_db()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT

                id,

                fixture_id,

                home_team,
                away_team,

                winner,
                expected_score,

                xg_home,
                xg_away,

                confidence,

                model_version,

                created_at


            FROM predictions

            ORDER BY created_at DESC

            LIMIT %s

            """,

            (
                limit,
            )
        )


        rows = cur.fetchall()


        conn.close()


        result = []


        for row in rows:

            try:

                result.append(
                    dict(row)
                )

            except:

                result.append(
                    row
                )


        logger.info(
            "Predictions loaded: %s",
            len(result)
        )


        return result



    except Exception as e:


        logger.error(
            "GET predictions error: %s",
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

        conn = get_db()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT *

            FROM predictions

            ORDER BY created_at DESC

            LIMIT %s
            """,

            (
                limit,
            )
        )


        rows = cur.fetchall()


        conn.close()


        return rows


    except Exception as e:


        logger.error(
            "History error: %s",
            e,
            exc_info=True
        )


        return []



# =====================================================
# ONE
# =====================================================

def get_prediction_by_id(
    prediction_id
):

    try:

        conn = get_db()
        cur = conn.cursor()


        cur.execute(
            """
            SELECT *

            FROM predictions

            WHERE id=%s

            LIMIT 1
            """,

            (
                prediction_id,
            )
        )


        row = cur.fetchone()


        conn.close()


        if row:

            return dict(row)


        return None


    except Exception as e:


        logger.error(
            "Prediction by id error: %s",
            e,
            exc_info=True
        )


        return None



# =====================================================
# DUPLICATES
# =====================================================

def delete_duplicate_predictions():

    try:

        conn = get_db()
        cur = conn.cursor()


        cur.execute(
            """
            DELETE FROM predictions p1

            USING predictions p2

            WHERE p1.id < p2.id

            AND p1.fixture_id=p2.fixture_id
            """
        )


        deleted = cur.rowcount


        conn.commit()
        conn.close()


        return deleted


    except Exception as e:


        logger.error(
            "Duplicate error: %s",
            e,
            exc_info=True
        )


        return 0



# =====================================================
# EXPORTS
# =====================================================

__all__ = [

    "clear_predictions",

    "save_prediction",

    "save_predictions_batch",

    "get_predictions",

    "get_prediction_history",

    "get_prediction_by_id",

    "delete_duplicate_predictions"

]
