# =====================================================
# FAJ Platform v6.5
# app/managers/prediction_manager.py
#
# Prediction Manager
# PostgreSQL version
# =====================================================


import logging
import ast
from datetime import datetime

import numpy as np

from app.database import get_db

from app.core.faj_core import FAJCore


logger = logging.getLogger(__name__)


MODEL_VERSION = "FAJ v6.5"



# =====================================================
# CLEAN NUMPY
# =====================================================


def clean_value(value):

    if isinstance(value, np.generic):
        return value.item()

    return value



def clean_prediction(data):

    if data is None:
        return {}

    result = {}

    for key, value in data.items():

        if isinstance(value, dict):

            result[key] = clean_prediction(value)


        elif isinstance(value, list):

            result[key] = [

                clean_prediction(v)
                if isinstance(v, dict)
                else clean_value(v)

                for v in value

            ]


        else:

            result[key] = clean_value(value)


    return result




# =====================================================
# NORMALIZE CORE RESULT
# =====================================================


def normalize_prediction(raw):

    raw = clean_prediction(raw)


    decision = raw.get(
        "decision",
        {}
    )


    xg = raw.get(
        "xg",
        {}
    ).get(
        "predicted",
        {}
    )


    simulation = raw.get(
        "simulation",
        {}
    )


    return {


        "winner":

            decision.get(
                "winner_name",
                decision.get(
                    "winner",
                    ""
                )
            ),



        "home_probability":

            float(
                decision.get(
                    "home_probability",
                    decision.get(
                        "home_prob",
                        0
                    )
                )
            ),



        "draw_probability":

            float(
                decision.get(
                    "draw_probability",
                    decision.get(
                        "draw_prob",
                        0
                    )
                )
            ),



        "away_probability":

            float(
                decision.get(
                    "away_probability",
                    decision.get(
                        "away_prob",
                        0
                    )
                )
            ),



        "winner_probability":

            float(
                decision.get(
                    "winner_probability",
                    0
                )
            ),



        "xg_home":

            float(
                xg.get(
                    "home",
                    0
                )
            ),



        "xg_away":

            float(
                xg.get(
                    "away",
                    0
                )
            ),



        "expected_score":

            decision.get(
                "expected_score",
                ""
            ),



        "top_scores":

            simulation.get(
                "top_scores",
                []
            ),



        "btts":

            float(
                raw.get(
                    "btts",
                    0
                )
            ),



        "over25":

            float(
                raw.get(
                    "over25",
                    0
                )
            ),



        "confidence":

            float(
                decision.get(
                    "confidence",
                    0
                )
            )

    }




# =====================================================
# CREATE SINGLE PREDICTION
# =====================================================


def create_prediction(

    fixture,

    core=None

):


    if core is None:

        core = FAJCore()



    home = fixture.get(
        "home_team"
    )


    away = fixture.get(
        "away_team"
    )


    league = fixture.get(
        "league",
        "RPL"
    )



    logger.info(

        f"Create prediction {home}-{away}"

    )



    raw = core.predict_match(

        home,

        away,

        league

    )



    if not raw:

        raise Exception(
            "FAJCore returned empty result"
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
# SAVE PREDICTION
# =====================================================


def save_prediction(

    fixture,

    prediction

):


    conn = get_db()


    cur = conn.cursor()



    try:


        cur.execute(

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

            %s,%s,%s,%s,

            %s,%s,

            %s,

            %s,%s,%s,

            %s,%s,

            %s,

            %s,

            %s,%s,

            %s,

            %s,

            %s

        )


        ON CONFLICT (fixture_id)

        DO UPDATE SET


            winner_prediction =
                EXCLUDED.winner_prediction,


            expected_score =
                EXCLUDED.expected_score,


            confidence =
                EXCLUDED.confidence,


            model_version =
                EXCLUDED.model_version

        """,

        (

            fixture.get("id"),

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
                    "top_scores",
                    []
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


            MODEL_VERSION,


            datetime.now()

        )


        )


        conn.commit()



    except Exception:


        conn.rollback()

        logger.exception(
            "Save prediction error"
        )

        raise



    finally:


        cur.close()

        conn.close()




# =====================================================
# CREATE TOUR
# =====================================================


def create_tour_predictions(

    fixtures,

    core=None

):


    result = {


        "generated":

            0,


        "errors":

            []

    }



    for fixture in fixtures:


        try:


            create_prediction(

                fixture,

                core

            )


            result["generated"] += 1



        except Exception as e:


            result["errors"].append(

                {

                    "match":

                    f"{fixture.get('home_team')} - {fixture.get('away_team')}",


                    "error":

                    str(e)

                }

            )



    return result




# =====================================================
# GET PREDICTIONS
# =====================================================


def get_predictions(

    league=None,

    season=None,

    round_number=None

):


    conn = get_db()

    cur = conn.cursor()



    query = """

    SELECT

        p.*,

        f.match_date


    FROM predictions p


    LEFT JOIN fixtures f

        ON p.fixture_id = f.id


    WHERE 1=1

    """



    params = []



    if league:


        query += """

        AND p.league=%s

        """


        params.append(
            league
        )



    if season:


        query += """

        AND p.season=%s

        """


        params.append(
            season
        )



    if round_number:


        query += """

        AND p.round=%s

        """


        params.append(
            round_number
        )



    query += """

    ORDER BY

        f.match_date ASC

    """



    cur.execute(

        query,

        tuple(params)

    )



    rows = cur.fetchall()



    predictions = []



    for row in rows:


        item = dict(row)



        try:


            item["top_scores"] = ast.literal_eval(

                item.get(
                    "top_scores",
                    "[]"
                )

            )


        except Exception:


            item["top_scores"] = []



        predictions.append(
            item
        )



    cur.close()

    conn.close()



    return predictions




# =====================================================
# COUNT
# =====================================================


def count_predictions():


    conn = get_db()

    cur = conn.cursor()


    cur.execute(

        """

        SELECT COUNT(*)

        FROM predictions

        """

    )


    count = cur.fetchone()[0]


    cur.close()

    conn.close()


    return count




# =====================================================
# CLEAR
# =====================================================


def clear_predictions():


    conn = get_db()

    cur = conn.cursor()


    cur.execute(

        """

        DELETE FROM predictions

        """

    )


    conn.commit()


    cur.close()

    conn.close()
