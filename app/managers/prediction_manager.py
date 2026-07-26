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
# NORMALIZE CORE RESPONSE
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



    return {


        "winner":

            decision.get(

                "winner"

            ),



        "winner_name":

            decision.get(

                "winner_name"

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

            raw.get(

                "simulation",

                {}

            ).get(

                "top_scores",

                []

            ),



        "btts":

            raw.get(

                "btts",

                0

            ),



        "over25":

            raw.get(

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
# SAVE MODEL PREDICTION
# =====================================================


def save_prediction(

    fixture,

    prediction

):


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(

        """

        INSERT INTO predictions

        (

        fixture_id,

        league,

        season,


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

        (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())


        ON CONFLICT(fixture_id)

        DO UPDATE SET


        winner_prediction =
        EXCLUDED.winner_prediction,


        expected_score =
        EXCLUDED.expected_score,


        confidence =
        EXCLUDED.confidence


        """,

        (

        fixture["id"],


        fixture.get(

            "league",

            "RPL"

        ),


        fixture.get(

            "season",

            "2026/27"

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



        FAJCore.VERSION


        )

        )



        conn.commit()



    except Exception as e:


        conn.rollback()


        logger.error(

            "Prediction save error: %s",

            e,

            exc_info=True

        )


        raise



    finally:


        conn.close()








# =====================================================
# CREATE ONE PREDICTION
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



    result = core.predict_match(

        home,

        away,

        fixture.get(

            "league",

            "RPL"

        )

    )



    prediction = normalize_prediction(

        result

    )



    save_prediction(

        fixture,

        prediction

    )



    return prediction







# =====================================================
# CREATE TOUR
# =====================================================


def create_tour_predictions(

    fixtures,

    core=None

):


    generated = 0


    errors = []



    for fixture in fixtures:


        try:


            create_prediction(

                fixture,

                core

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


        "generated":

            generated,


        "errors":

            errors

    }








# =====================================================
# GET PREDICTIONS
# =====================================================


def get_predictions(

    league=None,

    season=None

):


    conn = get_db()



    try:


        cur = conn.cursor()



        query = """

        SELECT *

        FROM predictions

        WHERE 1=1

        """



        params = []



        if league:


            query += """

            AND league=%s

            """


            params.append(

                league

            )



        if season:


            query += """

            AND season=%s

            """


            params.append(

                season

            )



        query += """

        ORDER BY fixture_id

        """



        cur.execute(

            query,

            tuple(params)

        )



        rows = cur.fetchall()



        result = []



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



            result.append(

                item

            )



        return result



    finally:


        conn.close()
