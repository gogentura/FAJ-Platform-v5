# =====================================================
# FAJ Platform v6.3.2
# app/journal.py
#
# FAJ Prediction Journal
# =====================================================


import json
import logging


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


        try:


            # -----------------------------------------
            # FIXTURE REQUIRED
            # -----------------------------------------

            if fixture_id is None:


                logger.warning(

                    "Journal save skipped: fixture_id отсутствует"

                )


                return



            conn = get_connection()

            cur = conn.cursor()



            home = prediction.get(
                "home_team",
                ""
            )


            away = prediction.get(
                "away_team",
                ""
            )


            league = prediction.get(
                "league",
                "RPL"
            )



            cur.execute(

                """

                INSERT INTO journal
                (

                    fixture_id,

                    home_team,
                    away_team,
                    league,


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


                    home_rating,
                    away_rating,


                    confidence,


                    risk,


                    grade,
                    grade_name,


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



                ON CONFLICT (fixture_id)

                DO UPDATE SET



                    winner =
                    EXCLUDED.winner,


                    winner_probability =
                    EXCLUDED.winner_probability,


                    home_probability =
                    EXCLUDED.home_probability,


                    draw_probability =
                    EXCLUDED.draw_probability,


                    away_probability =
                    EXCLUDED.away_probability,


                    xg_home =
                    EXCLUDED.xg_home,


                    xg_away =
                    EXCLUDED.xg_away,


                    expected_score =
                    EXCLUDED.expected_score,


                    top_scores =
                    EXCLUDED.top_scores,


                    btts =
                    EXCLUDED.btts,


                    over25 =
                    EXCLUDED.over25,


                    home_rating =
                    EXCLUDED.home_rating,


                    away_rating =
                    EXCLUDED.away_rating,


                    confidence =
                    EXCLUDED.confidence,


                    risk =
                    EXCLUDED.risk,


                    grade =
                    EXCLUDED.grade,


                    grade_name =
                    EXCLUDED.grade_name


                """,


                (

                    fixture_id,


                    home,

                    away,

                    league,



                    prediction.get(
                        "winner",
                        ""
                    ),



                    prediction.get(
                        "winner_probability",
                        0
                    ),



                    prediction.get(
                        "home_probability",
                        0
                    ),


                    prediction.get(
                        "draw_probability",
                        0
                    ),


                    prediction.get(
                        "away_probability",
                        0
                    ),



                    prediction.get(
                        "xg_home",
                        0
                    ),


                    prediction.get(
                        "xg_away",
                        0
                    ),



                    prediction.get(
                        "expected_score",
                        ""
                    ),



                    json.dumps(

                        prediction.get(
                            "top_scores",
                            []
                        ),

                        ensure_ascii=False

                    ),



                    prediction.get(
                        "btts",
                        0
                    ),


                    prediction.get(
                        "over25",
                        0
                    ),



                    prediction.get(
                        "home_rating",
                        0
                    ),


                    prediction.get(
                        "away_rating",
                        0
                    ),



                    prediction.get(
                        "confidence",
                        0
                    ),



                    prediction.get(
                        "risk",
                        "Средний"
                    ),



                    prediction.get(
                        "grade",
                        "C"
                    ),


                    prediction.get(
                        "grade_name",
                        "Высокий риск"
                    )

                )

            )



            conn.commit()



            cur.close()

            conn.close()



            logger.info(

                f"Journal saved: {home} — {away}"

            )



        except Exception as e:



            logger.error(

                f"Journal save error: {e}",

                exc_info=True

            )



    # =================================================
    # GET LAST PREDICTIONS
    # =================================================


    def get_last_predictions(

        self,

        limit=10

    ):


        try:


            conn = get_connection()

            cur = conn.cursor()



            cur.execute(

                """

                SELECT

                    *

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

            conn.close()



            return rows



        except Exception as e:



            logger.error(

                f"Journal read error: {e}",

                exc_info=True

            )


            return []



    # =================================================
    # FIND BY FIXTURE
    # =================================================


    def get_by_fixture(

        self,

        fixture_id

    ):


        try:


            conn = get_connection()

            cur = conn.cursor()



            cur.execute(

                """

                SELECT *

                FROM journal

                WHERE fixture_id=%s

                """,

                (
                    fixture_id,
                )

            )



            row = cur.fetchone()



            cur.close()

            conn.close()



            return row



        except Exception as e:



            logger.error(

                f"Journal fixture search error: {e}",

                exc_info=True

            )


            return None
