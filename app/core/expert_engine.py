# =====================================================
# FAJ Platform v6.6
# app/core/expert_engine.py
#
# FAJ Expert Comparison Engine v1.0
#
# FAJ Model vs Expert vs Reality
# =====================================================


import logging


from app.database import get_db



logger = logging.getLogger(__name__)





# =====================================================
# SCORE NORMALIZE
# =====================================================


def normalize_score(score):

    if not score:

        return None


    return str(score).strip()






# =====================================================
# WINNER FROM SCORE
# =====================================================


def winner_from_score(score):


    if not score:

        return None



    try:

        home, away = score.split("-")

        home = int(home)

        away = int(away)



        if home > away:

            return "home"


        elif away > home:

            return "away"


        else:

            return "draw"



    except Exception:

        return None







# =====================================================
# SCORE ERROR
# =====================================================


def calculate_score_error(

    faj_score,

    fact_score

):


    if not faj_score or not fact_score:

        return 99



    try:


        f1, f2 = map(

            int,

            faj_score.split("-")

        )


        a1, a2 = map(

            int,

            fact_score.split("-")

        )



        return (

            abs(f1-a1)

            +

            abs(f2-a2)

        )



    except Exception:


        return 99






# =====================================================
# COMPARE PREDICTIONS
# =====================================================


def compare_predictions(

    faj_prediction,

    expert_prediction,

    fact_result

):


    result = {}



    faj_score = normalize_score(

        faj_prediction.get(

            "expected_score"

        )

    )


    expert_score = normalize_score(

        expert_prediction.get(

            "score"

        )

    )


    fact_score = normalize_score(

        fact_result.get(

            "result"

        )

    )





    faj_winner = winner_from_score(

        faj_score

    )


    expert_winner = winner_from_score(

        expert_score

    )


    fact_winner = winner_from_score(

        fact_score

    )





    errors = []





    # победитель FAJ


    if faj_winner != fact_winner:


        errors.append(

            "FAJ ошибка победителя"

        )





    # эксперт


    if expert_winner == fact_winner:


        expert_better = True


    else:


        expert_better = False






    # счёт


    score_error = calculate_score_error(

        faj_score,

        fact_score

    )



    if score_error > 2:


        errors.append(

            "Ошибка точного счёта"

        )





    if not errors:


        errors.append(

            "FAJ прогноз точный"

        )





    result = {


        "faj_score":

            faj_score,


        "expert_score":

            expert_score,


        "fact_score":

            fact_score,



        "faj_winner":

            faj_winner,


        "expert_winner":

            expert_winner,


        "fact_winner":

            fact_winner,



        "expert_better":

            expert_better,



        "error_type":

            "; ".join(errors)



    }



    return result







# =====================================================
# SAVE CALIBRATION
# =====================================================


def save_calibration(

    fixture_id,

    comparison

):


    conn = get_db()



    try:


        cur = conn.cursor()



        cur.execute(

        """

        INSERT INTO calibration_log

        (

        fixture_id,


        faj_score,

        fact_score,


        faj_winner,

        fact_winner,


        expert_score,

        expert_winner,


        error_type,


        conclusion,


        created


        )


        VALUES

        (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())

        """,

        (

        fixture_id,


        comparison.get(

            "faj_score"

        ),


        comparison.get(

            "fact_score"

        ),


        comparison.get(

            "faj_winner"

        ),


        comparison.get(

            "fact_winner"

        ),


        comparison.get(

            "expert_score"

        ),


        comparison.get(

            "expert_winner"

        ),


        comparison.get(

            "error_type"

        ),


        (

            "Эксперт лучше"

            if comparison.get(

                "expert_better"

            )

            else

            "FAJ ближе"

        )


        )

        )



        conn.commit()



    except Exception as e:


        conn.rollback()


        logger.error(

            "Calibration save error: %s",

            e,

            exc_info=True

        )


        raise



    finally:


        conn.close()







# =====================================================
# RUN SINGLE MATCH ANALYSIS
# =====================================================


def analyze_match(

    fixture_id

):


    conn = get_db()



    try:


        cur = conn.cursor()



        cur.execute(

        """

        SELECT *

        FROM predictions

        WHERE fixture_id=%s

        """,

        (

            fixture_id,

        )

        )


        faj = cur.fetchone()



        if not faj:

            return None



        faj = dict(faj)





        cur.execute(

        """

        SELECT *

        FROM expert_predictions

        WHERE match=%s

        """,

        (

            f"{faj['home_team']} - {faj['away_team']}",

        )

        )


        expert = cur.fetchone()



        if expert:

            expert = dict(expert)

        else:

            expert = {}






        cur.execute(

        """

        SELECT *

        FROM fixtures

        WHERE id=%s

        """,

        (

            fixture_id,

        )

        )


        fact = cur.fetchone()



        if not fact:

            return None



        fact = dict(fact)





        comparison = compare_predictions(

            faj,

            expert,

            fact

        )





        save_calibration(

            fixture_id,

            comparison

        )



        return comparison





    finally:


        conn.close()
