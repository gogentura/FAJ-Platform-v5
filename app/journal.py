# =====================================================
# FAJ Platform v7.0.2
# app/journal.py
#
# Journal / Learning Memory Layer
#
# PostgreSQL ONLY
#
# Compatible:
# - FAJ Core
# - Prediction Pipeline
# - Calibration Engine
# =====================================================


import logging
import json

from app.database import get_connection


logger = logging.getLogger(__name__)




class Journal:


    # =================================================
    # SAVE PREDICTION
    # =================================================

    def save(
        self,
        match,
        prediction,
        fixture_id=None
    ):

        conn = None

        try:

            if fixture_id is None:

                logger.warning(
                    "Journal save skipped: fixture_id missing"
                )

                return False


            conn = get_connection()

            cur = conn.cursor()



            home_team = prediction.get(
                "home_team",
                match.get(
                    "home_team",
                    ""
                )
            )


            away_team = prediction.get(
                "away_team",
                match.get(
                    "away_team",
                    ""
                )
            )


            decision = prediction.get(
                "decision",
                {}
            )


            xg = prediction.get(
                "xg",
                {}
            ).get(
                "predicted",
                {}
            )


            model_version = prediction.get(
                "version",
                "FAJ"
            )



            cur.execute(
            """

            INSERT INTO journal
            (

                fixture_id,

                home_team,

                away_team,


                prediction,

                expected_score,


                winner,


                confidence,

                risk,

                grade,


                xg_home,

                xg_away,


                model_version,


                created

            )


            VALUES

            (

                %s,

                %s,

                %s,


                %s,

                %s,


                %s,


                %s,

                %s,

                %s,


                %s,

                %s,


                %s,


                NOW()

            )


            """,

            (

                fixture_id,


                home_team,

                away_team,


                json.dumps(
                    prediction,
                    ensure_ascii=False
                ),


                decision.get(
                    "expected_score",
                    ""
                ),


                decision.get(
                    "winner",
                    ""
                ),


                decision.get(
                    "confidence",
                    prediction.get(
                        "confidence",
                        0
                    )
                ),


                prediction.get(
                    "risk",
                    "Не определён"
                ),


                prediction.get(
                    "grade",
                    "C"
                ),


                xg.get(
                    "home",
                    0
                ),


                xg.get(
                    "away",
                    0
                ),


                model_version

            )

            )


            conn.commit()


            cur.close()


            logger.info(
                "Journal saved: %s - %s",
                home_team,
                away_team
            )


            return True



        except Exception as e:


            logger.exception(
                "Journal save error: %s",
                e
            )


            return False



        finally:

            if conn:

                conn.close()



    # =================================================
    # LAST PREDICTIONS
    # =================================================


    def get_last_predictions(
        self,
        limit=10
    ):


        conn = None


        try:

            conn = get_connection()

            cur = conn.cursor()


            cur.execute(
            """

            SELECT *

            FROM journal

            ORDER BY created DESC

            LIMIT %s

            """,

            (
                limit,
            )

            )


            rows = cur.fetchall()


            cur.close()


            return rows



        except Exception as e:


            logger.exception(
                "Journal read error: %s",
                e
            )


            return []



        finally:

            if conn:

                conn.close()



    # =================================================
    # GET BY FIXTURE
    # =================================================


    def get_by_fixture(
        self,
        fixture_id
    ):


        conn = None


        try:


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


            return row



        except Exception as e:


            logger.exception(
                "Journal fixture error: %s",
                e
            )


            return None



        finally:

            if conn:

                conn.close()





# =====================================================
# CLEAR
# =====================================================


def clear_journal():


    conn = None


    try:

        conn = get_connection()

        cur = conn.cursor()


        cur.execute(
            "DELETE FROM journal"
        )


        conn.commit()


        cur.close()


        logger.info(
            "Journal cleared"
        )


        return True



    except Exception as e:


        logger.exception(
            "Journal clear error: %s",
            e
        )


        return False



    finally:


        if conn:

            conn.close()
