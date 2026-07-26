# =====================================================
# FAJ Platform v6.6
# app/core/calibration_engine.py
#
# FAJ Calibration Engine v1.0
#
# Model vs Expert vs Reality
# =====================================================


import logging


from datetime import datetime


from app.database import get_db



logger = logging.getLogger(__name__)





# =====================================================
# RESULT NORMALIZE
# =====================================================


def normalize_score(
    home_score,
    away_score
):

    return f"{home_score}-{away_score}"





# =====================================================
# COMPARE WINNER
# =====================================================


def check_winner(
    predicted,
    actual
):


    if not predicted:

        return False


    if not actual:

        return False



    return predicted == actual







# =====================================================
# SCORE DIFFERENCE
# =====================================================


def score_error(
    predicted,
    actual
):


    if not predicted or not actual:

        return 99



    try:

        p = predicted.split("-")

        a = actual.split("-")



        return abs(
            int(p[0]) - int(a[0])
        ) + abs(
            int(p[1]) - int(a[1])
        )


    except:


        return 99






# =====================================================
# ERROR TYPE
# =====================================================


def detect_error(
    prediction,
    fact
):


    errors = []



    if not check_winner(

        prediction.get(
            "winner_prediction"
        ),

        fact.get(
            "winner"

        )

    ):


        errors.append(

            "Ошибка определения победителя"

        )





    if score_error(

        prediction.get(
            "expected_score"
        ),

        fact.get(
            "result"
        )

    ) > 2:


        errors.append(

            "Ошибка точного счёта"

        )





    xg_home = float(

        prediction.get(
            "xg_home",
            0
        )

    )


    xg_away = float(

        prediction.get(
            "xg_away",
            0
        )

    )



    if abs(
        xg_home - xg_away
    ) < 0.3:


        errors.append(

            "FAJ недооценил разницу команд"

        )



    if not errors:


        errors.append(

            "Прогноз точный"

        )



    return errors







# =====================================================
# CALIBRATE MATCH
# =====================================================


def calibrate_match(
    fixture_id
):


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(

        """

        SELECT

        p.*,

        f.result,

        f.winner


        FROM predictions p


        JOIN fixtures f

        ON p.fixture_id=f.id


        WHERE p.fixture_id=%s


        """,

        (

            fixture_id,

        )

        )



        row = cur.fetchone()



        if not row:


            return None



        data = dict(row)



        errors = detect_error(

            data,

            data

        )





        cur.execute(

        """

        INSERT INTO calibration_log

        (

        fixture_id,

        errors,

        created


        )


        VALUES

        (%s,%s,NOW())


        """,

        (

        fixture_id,

        str(errors)

        )

        )



        conn.commit()



        return {


            "fixture_id":

            fixture_id,


            "errors":

            errors


        }



    except Exception as e:


        conn.rollback()


        logger.error(

            "Calibration error: %s",

            e,

            exc_info=True

        )


        return None



    finally:


        conn.close()






# =====================================================
# CALIBRATE ALL FINISHED
# =====================================================


def calibrate_finished_matches():


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(

        """

        SELECT id

        FROM fixtures

        WHERE status='finished'

        """

        )


        matches = cur.fetchall()



        results = []



        for match in matches:


            result = calibrate_match(

                match["id"]

            )


            if result:

                results.append(

                    result

                )



        return results



    finally:


        conn.close()
