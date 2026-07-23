from app.database import get_db


# =====================================================
# ACCURACY ENGINE FAJ v5.1
# =====================================================


class AccuracyEngine:


    # =================================================
    # NORMALIZE TEAM
    # =================================================

    def normalize_team(self, name):

        if not name:
            return ""

        return (
            name
            .lower()
            .strip()
        )



    # =================================================
    # CHECK WINNER
    # =================================================

    def check_winner(
        self,
        prediction,
        actual
    ):

        if not prediction or not actual:
            return False


        prediction = self.normalize_team(
            prediction
        )

        actual = self.normalize_team(
            actual
        )


        return prediction == actual



    # =================================================
    # CHECK SCORE
    # =================================================

    def check_score(
        self,
        predicted,
        actual
    ):

        if not predicted or not actual:
            return False


        return (
            predicted.strip()
            ==
            actual.strip()
        )



    # =================================================
    # UPDATE JOURNAL
    # =================================================

    def evaluate_match(
        self,
        match
    ):


        conn = get_db()



        # Получаем последний прогноз

        prediction_row = conn.execute(
        """
        SELECT *
        FROM journal

        WHERE match = ?

        ORDER BY id DESC

        LIMIT 1
        """,
        (
            match,
        )
        ).fetchone()



        if not prediction_row:

            conn.close()

            return {

                "error":
                "Прогноз не найден"

            }



        # Получаем факт

        result_row = conn.execute(
        """
        SELECT *
        FROM match_results

        WHERE match = ?

        ORDER BY id DESC

        LIMIT 1
        """,
        (
            match,
        )
        ).fetchone()



        if not result_row:

            conn.close()

            return {

                "error":
                "Результат не найден"

            }



        prediction = dict(
            prediction_row
        )


        result = dict(
            result_row
        )



        # Проверка исхода

        outcome_hit = self.check_winner(
            prediction.get(
                "winner"
            ),
            result.get(
                "winner"
            )
        )



        # Проверка счёта

        score_hit = self.check_score(
            prediction.get(
                "expected_score"
            ),
            result.get(
                "score"
            )
        )



        accuracy = []



        if outcome_hit:

            accuracy.append(
                "OUTCOME"
            )


        if score_hit:

            accuracy.append(
                "SCORE"
            )



        if not accuracy:

            accuracy.append(
                "MISS"
            )



        accuracy_text = ",".join(
            accuracy
        )



        # Обновляем журнал

        conn.execute(
        """
        UPDATE journal

        SET

            actual_score = ?,

            actual_winner = ?,

            accuracy = ?

        WHERE id = ?

        """,
        (

            result.get(
                "score",
                ""
            ),

            result.get(
                "winner",
                ""
            ),

            accuracy_text,

            prediction.get(
                "id"
            )

        )
        )



        conn.commit()

        conn.close()



        return {

            "match":
            match,


            "actual_score":
            result.get(
                "score"
            ),


            "actual_winner":
            result.get(
                "winner"
            ),


            "outcome_hit":
            outcome_hit,


            "score_hit":
            score_hit,


            "accuracy":
            accuracy_text

        }



    # =================================================
    # GLOBAL STATS
    # =================================================

    def get_statistics(
        self
    ):


        conn = get_db()



        rows = conn.execute(
        """
        SELECT accuracy

        FROM journal

        WHERE accuracy IS NOT NULL

        """
        ).fetchall()



        conn.close()



        total = len(rows)


        outcome = 0

        score = 0



        for row in rows:


            value = row["accuracy"] or ""


            if "OUTCOME" in value:

                outcome += 1


            if "SCORE" in value:

                score += 1



        return {

            "matches":
            total,


            "outcome_accuracy":
            round(
                outcome / total * 100,
                1
            )
            if total
            else 0,


            "score_accuracy":
            round(
                score / total * 100,
                1
            )
            if total
            else 0

        }
