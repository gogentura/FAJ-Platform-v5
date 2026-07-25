# =====================================================
# FAJ Platform v6.4
# app/services/result_analyzer.py
#
# FAJ Result Analyzer
#
# Prediction vs Actual Result
# =====================================================


import logging


from app.database import get_connection


logger = logging.getLogger(__name__)



# =====================================================
# SCORE PARSER
# =====================================================


def parse_score(score):

    try:

        if not score:

            return None, None


        parts = (
            str(score)
            .replace(" ", "")
            .split("-")
        )


        if len(parts) != 2:

            return None, None


        return (

            int(parts[0]),

            int(parts[1])

        )


    except Exception:

        return None, None



# =====================================================
# WINNER FROM SCORE
# =====================================================


def get_winner_from_score(

    home_score,

    away_score

):


    if home_score > away_score:

        return "home"


    elif away_score > home_score:

        return "away"


    else:

        return "draw"



# =====================================================
# ANALYZE SINGLE RESULT
# =====================================================


def analyze_result(

    fixture_id,

    actual_score

):


    try:


        conn = get_connection()

        cur = conn.cursor()



        # -----------------------------------------
        # FIND JOURNAL PREDICTION
        # -----------------------------------------

        cur.execute(

            """

            SELECT *

            FROM journal

            WHERE fixture_id=%s

            LIMIT 1

            """,

            (
                fixture_id,
            )

        )


        prediction = cur.fetchone()



        if not prediction:


            logger.warning(

                f"No prediction found for fixture {fixture_id}"

            )


            conn.close()

            return False



        # -----------------------------------------
        # SCORES
        # -----------------------------------------


        actual_home, actual_away = parse_score(

            actual_score

        )


        predicted_home, predicted_away = parse_score(

            prediction.get(
                "expected_score"
            )

        )



        if actual_home is None:

            conn.close()

            return False



        # -----------------------------------------
        # WINNER CHECK
        # -----------------------------------------


        actual_winner = get_winner_from_score(

            actual_home,

            actual_away

        )


        predicted_winner = prediction.get(

            "winner"

        )



        winner_correct = (

            actual_winner == predicted_winner

        )



        # -----------------------------------------
        # EXACT SCORE
        # -----------------------------------------


        score_exact = (

            actual_home == predicted_home

            and

            actual_away == predicted_away

        )



        # -----------------------------------------
        # ACCURACY
        # -----------------------------------------


        accuracy = 0



        if winner_correct:

            accuracy += 70


        if score_exact:

            accuracy += 30



        # -----------------------------------------
        # UPDATE JOURNAL
        # -----------------------------------------


        cur.execute(

            """

            UPDATE journal

            SET

                actual_score=%s,

                actual_winner=%s,

                winner_correct=%s,

                score_exact=%s,

                accuracy=%s


            WHERE fixture_id=%s

            """,

            (

                actual_score,

                actual_winner,

                winner_correct,

                score_exact,

                accuracy,

                fixture_id

            )

        )



        conn.commit()


        cur.close()

        conn.close()



        logger.info(

            f"Result analyzed: fixture {fixture_id}"

        )


        return True



    except Exception as e:


        logger.error(

            f"Result analyze error: {e}",

            exc_info=True

        )


        return False



# =====================================================
# ANALYZE FINISHED FIXTURES
# =====================================================


def analyze_finished_matches():

    """
    Анализ всех завершённых матчей,
    где есть прогноз FAJ
    """

    updated = 0


    try:


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """

            SELECT

                fixture_id,

                actual_score


            FROM fixtures


            WHERE status='finished'

            AND actual_score IS NOT NULL


            """

        )


        fixtures = cur.fetchall()



        cur.close()

        conn.close()



        for fixture in fixtures:


            result = analyze_result(

                fixture["fixture_id"],

                fixture["actual_score"]

            )


            if result:

                updated += 1



        logger.info(

            f"Finished matches analyzed: {updated}"

        )


        return updated



    except Exception as e:


        logger.error(

            f"Finished matches analysis error: {e}",

            exc_info=True

        )


        return 0
