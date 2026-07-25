# =====================================================
# FAJ Platform v6.3.4
# app/services/result_analyzer.py
#
# FAJ Result Analyzer
#
# Сравнение прогноза с фактом
# =====================================================


import logging


from app.database import get_connection



logger = logging.getLogger(__name__)



# =====================================================
# HELPERS
# =====================================================


def normalize_team(team):

    if not team:

        return ""


    return (

        team
        .lower()
        .strip()

    )



def get_winner_from_score(

    home_score,

    away_score,

    home_team,

    away_team

):


    if home_score > away_score:

        return home_team


    if away_score > home_score:

        return away_team


    return "draw"



def parse_score(score):

    try:

        if not score:

            return None, None


        parts = score.split("-")


        return (

            int(parts[0]),

            int(parts[1])

        )


    except Exception:

        return None, None



# =====================================================
# RESULT ANALYZER
# =====================================================


class ResultAnalyzer:



    # =================================================
    # GET FINISHED FIXTURES
    # =================================================


    def get_finished_matches(

        self,

        league="RPL"

    ):


        conn = get_connection()

        cur = conn.cursor()



        cur.execute(

            """

            SELECT *

            FROM fixtures

            WHERE league=%s

            AND status IN

            (

                'finished',

                'FINISHED',

                'completed'

            )

            ORDER BY date DESC


            """,

            (

                league,

            )

        )


        rows = cur.fetchall()



        cur.close()

        conn.close()



        return rows



    # =================================================
    # GET PREDICTION
    # =================================================


    def get_prediction(

        self,

        fixture_id

    ):


        conn = get_connection()

        cur = conn.cursor()



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


        row = cur.fetchone()



        cur.close()

        conn.close()



        return row



    # =================================================
    # UPDATE JOURNAL RESULT
    # =================================================


    def update_journal(

        self,

        fixture_id,

        data

    ):


        conn = get_connection()

        cur = conn.cursor()



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

                data["actual_score"],

                data["actual_winner"],

                data["winner_correct"],

                data["score_exact"],

                data["accuracy"],

                fixture_id

            )

        )



        conn.commit()



        cur.close()

        conn.close()



    # =================================================
    # ANALYZE ONE MATCH
    # =================================================


    def analyze_match(

        self,

        fixture

    ):


        fixture_id = fixture.get(

            "id"

        )


        prediction = self.get_prediction(

            fixture_id

        )



        if not prediction:


            logger.warning(

                f"No prediction for fixture {fixture_id}"

            )


            return None



        home = fixture.get(

            "home_team"

        )


        away = fixture.get(

            "away_team"

        )



        home_score = fixture.get(

            "home_score",

            0

        )


        away_score = fixture.get(

            "away_score",

            0

        )



        actual_score = (

            f"{home_score}-{away_score}"

        )



        actual_winner = get_winner_from_score(

            home_score,

            away_score,

            home,

            away

        )



        predicted_winner = prediction.get(

            "winner"

        )



        winner_correct = False



        if predicted_winner:

            if normalize_team(predicted_winner) == normalize_team(actual_winner):

                winner_correct = True



        predicted_score = prediction.get(

            "expected_score"

        )



        score_exact = (

            predicted_score == actual_score

        )



        accuracy = 0



        if winner_correct:

            accuracy += 0.7



        if score_exact:

            accuracy += 0.3



        result = {


            "actual_score":

                actual_score,


            "actual_winner":

                actual_winner,


            "winner_correct":

                winner_correct,


            "score_exact":

                score_exact,


            "accuracy":

                round(

                    accuracy,

                    2

                )

        }



        self.update_journal(

            fixture_id,

            result

        )



        return result



    # =================================================
    # ANALYZE ALL
    # =================================================


    def analyze_all(

        self,

        league="RPL"

    ):


        fixtures = self.get_finished_matches(

            league

        )


        analyzed = 0

        skipped = 0



        for fixture in fixtures:


            result = self.analyze_match(

                fixture

            )


            if result:

                analyzed += 1

            else:

                skipped += 1



        return {


            "league":

                league,


            "analyzed":

                analyzed,


            "skipped":

                skipped

        }



# =====================================================
# SERVICE FUNCTION
# =====================================================


def analyze_results(

    league="RPL"

):


    analyzer = ResultAnalyzer()


    return analyzer.analyze_all(

        league

    )



# =====================================================
# COMPATIBILITY OLD HANDLERS
# =====================================================


def analyze_finished_matches(

    league="RPL"

):

    return analyze_results(

        league

    )
