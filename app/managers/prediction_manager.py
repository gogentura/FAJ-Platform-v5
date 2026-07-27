# =====================================================
# FAJ Platform v6.9.2
# app/managers/prediction_manager.py
#
# Prediction Manager
#
# PredictionPipeline
#        |
#        v
# PredictionManager
#        |
#        v
# PostgreSQL
#
# =====================================================


import json
import logging
from datetime import datetime


from app.database import get_db


logger = logging.getLogger(__name__)





# =====================================================
# HELPERS
# =====================================================


def safe_float(
    value,
    default=0
):

    try:

        if value is None:
            return default

        return float(value)

    except:

        return default





def safe_json(
    value
):

    try:

        return json.dumps(
            value,
            ensure_ascii=False
        )

    except:

        return "{}"





# =====================================================
# CLEAR OLD PREDICTIONS
# =====================================================


def clear_predictions():

    """
    Удаляет старые прогнозы перед новым туром
    FAJ v6.9.2
    """

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
            "FAJ old predictions cleared"
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
# NORMALIZE
# =====================================================


def normalize_prediction(
    fixture,
    prediction
):


    if not prediction:

        return {}



    return {


        "fixture_id":
            fixture.get("id"),


        "home_team":
            fixture.get(
                "home_team",
                "-"
            ),


        "away_team":
            fixture.get(
                "away_team",
                "-"
            ),


        "league":
            fixture.get(
                "league",
                "RPL"
            ),


        "season":
            fixture.get(
                "season",
                "2026/27"
            ),



        "winner":
            prediction.get(
                "winner",
                "-"
            ),



        "expected_score":
            prediction.get(
                "expected_score",
                "-"
            ),



        "xg_home":
            safe_float(
                prediction.get(
                    "xg_home"
                )
            ),


        "xg_away":
            safe_float(
                prediction.get(
                    "xg_away"
                )
            ),



        "home_rating":
            safe_float(
                prediction.get(
                    "home_rating"
                )
            ),


        "away_rating":
            safe_float(
                prediction.get(
                    "away_rating"
                )
            ),




        "home_probability":
            safe_float(
                prediction.get(
                    "home_probability"
                )
            ) / 100,



        "draw_probability":
            safe_float(
                prediction.get(
                    "draw_probability"
                )
            ) / 100,



        "away_probability":
            safe_float(
                prediction.get(
                    "away_probability"
                )
            ) / 100,



        "confidence":
            safe_float(
                prediction.get(
                    "confidence"
                )
            ),



        "risk":
            prediction.get(
                "risk",
                "-"
            ),



        "category":
            prediction.get(
                "category",
                prediction.get(
                    "grade",
                    "C"
                )
            ),



        "factors":
            safe_json(
                prediction.get(
                    "factors",
                    []
                )
            ),



        "season_phase":
            prediction.get(
                "season_phase",
                "start"
            ),



        "passport_quality":
            safe_json(
                prediction.get(
                    "data_quality",
                    {}
                )
            ),



        "model_version":
            "6.9.2",



        "created_at":
            datetime.now()

    }






# =====================================================
# SAVE SINGLE
# =====================================================


def save_prediction(
    fixture,
    prediction
):


    try:


        data = normalize_prediction(
            fixture,
            prediction
        )


        if not data:

            return False



        conn = get_db()
        cur = conn.cursor()



        cur.execute(
            """
            INSERT INTO predictions
            (
                fixture_id,

                home_team,
                away_team,

                league,
                season,

                winner,
                expected_score,

                xg_home,
                xg_away,

                home_rating,
                away_rating,

                home_probability,
                draw_probability,
                away_probability,

                confidence,

                risk,
                category,

                factors,

                season_phase,

                passport_quality,

                model_version,

                created_at
            )


            VALUES

            (
                %s,%s,%s,%s,%s,
                %s,%s,
                %s,%s,
                %s,%s,
                %s,%s,%s,
                %s,
                %s,%s,
                %s,
                %s,
                %s,
                %s,
                %s
            )

            """,

            (
                data["fixture_id"],

                data["home_team"],
                data["away_team"],

                data["league"],
                data["season"],

                data["winner"],
                data["expected_score"],

                data["xg_home"],
                data["xg_away"],

                data["home_rating"],
                data["away_rating"],

                data["home_probability"],
                data["draw_probability"],
                data["away_probability"],

                data["confidence"],

                data["risk"],
                data["category"],

                data["factors"],

                data["season_phase"],

                data["passport_quality"],

                data["model_version"],

                data["created_at"]
            )

        )


        conn.commit()
        conn.close()



        logger.info(
            "Prediction saved %s - %s",
            data["home_team"],
            data["away_team"]
        )


        return True



    except Exception as e:


        logger.error(
            "Save prediction error: %s",
            e,
            exc_info=True
        )


        return False







# =====================================================
# SAVE TOUR
# =====================================================


def save_predictions_batch(
    fixtures,
    predictions
):


    # очистка старого тура

    clear_predictions()



    saved = 0



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
        "FAJ TOUR SAVED %s/%s",
        saved,
        len(predictions)
    )


    return saved






# =====================================================
# READ
# =====================================================


def get_predictions(
    limit=50
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



        return [
            dict(row)
            for row in rows
        ]



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

    return get_predictions(
        limit
    )





# =====================================================
# SINGLE
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
            "get_prediction_by_id error: %s",
            e,
            exc_info=True
        )


        return None
