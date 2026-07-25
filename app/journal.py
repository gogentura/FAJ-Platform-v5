# =====================================================
# FAJ Platform v6.3.1
# app/journal.py
#
# PostgreSQL Journal Layer
# =====================================================


from datetime import datetime
import json
import logging


from app.database import get_db



logger = logging.getLogger(__name__)



# =====================================================
# CLEAN VALUES
# =====================================================

def clean_value(value):

    if value is None:

        return None


    if hasattr(value, "item"):

        return value.item()


    return value



# =====================================================
# JOURNAL
# =====================================================


class Journal:



    # =================================================
    # SAVE PREDICTION
    # =================================================


    def save(

        self,

        match: str,

        prediction: dict,

        actual: dict = None

    ):



        conn = get_db()



        try:



            now = datetime.now()



            # =========================================
            # PARSE TEAMS
            # =========================================


            parts = (

                match

                .replace("-", "—")

                .split("—")

            )



            home_team = (

                parts[0].strip()

                if len(parts) > 0

                else ""

            )



            away_team = (

                parts[1].strip()

                if len(parts) > 1

                else ""

            )



            # =========================================
            # JSON
            # =========================================


            top_scores = json.dumps(

                prediction.get(

                    "top_scores",

                    []

                ),

                ensure_ascii=False

            )



            # =========================================
            # INSERT
            # =========================================


            conn.execute(

            """

            INSERT INTO journal

            (

                league,

                home_team,

                away_team,


                winner,

                winner_probability,


                home_probability,

                draw_probability,

                away_probability,


                xg_home,

                xg_away,


                expected_score,

                top_scores,


                btts,

                over25,


                confidence,


                home_rating,

                away_rating,


                risk,

                grade,


                model_version,

                data_version,


                actual_score,

                actual_winner,


                accuracy,


                created


            )


            VALUES

            (

                %s,%s,%s,

                %s,%s,

                %s,%s,%s,

                %s,%s,

                %s,%s,

                %s,%s,

                %s,

                %s,%s,

                %s,%s,

                %s,%s,

                %s,%s,

                %s,

                %s

            )


            """,


            (



                prediction.get(

                    "league",

                    "RPL"

                ),



                home_team,

                away_team,



                prediction.get(

                    "winner",

                    ""

                ),



                clean_value(

                    prediction.get(

                        "winner_probability",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "home_probability",

                        prediction.get(

                            "home_prob",

                            0

                        )

                    )

                ),



                clean_value(

                    prediction.get(

                        "draw_probability",

                        prediction.get(

                            "draw_prob",

                            0

                        )

                    )

                ),



                clean_value(

                    prediction.get(

                        "away_probability",

                        prediction.get(

                            "away_prob",

                            0

                        )

                    )

                ),



                clean_value(

                    prediction.get(

                        "xg_home",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "xg_away",

                        0

                    )

                ),



                prediction.get(

                    "expected_score",

                    ""

                ),



                top_scores,



                clean_value(

                    prediction.get(

                        "btts",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "over25",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "confidence",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "home_rating",

                        0

                    )

                ),



                clean_value(

                    prediction.get(

                        "away_rating",

                        0

                    )

                ),



                prediction.get(

                    "risk",

                    "Средний"

                ),



                prediction.get(

                    "grade",

                    "B"

                ),



                "6.3.1",



                "2026.07",



                actual.get(

                    "score",

                    ""

                )

                if actual

                else "",



                actual.get(

                    "winner",

                    ""

                )

                if actual

                else "",



                clean_value(

                    prediction.get(

                        "accuracy",

                        None

                    )

                ),



                now


            )

            )



            conn.commit()



        except Exception as e:


            conn.rollback()


            logger.error(

                f"Journal save error: {e}"

            )


            raise



        finally:


            conn.close()



    # =================================================
    # GET ALL
    # =================================================


    def get_all(

        self,

        limit=20

    ):



        conn = get_db()



        try:


            cursor = conn.execute(

            """

            SELECT *

            FROM journal

            ORDER BY id DESC

            LIMIT %s

            """,

            (

                limit,

            )

            )



            rows = cursor.fetchall()



            return [

                dict(row)

                for row in rows

            ]



        finally:


            conn.close()
