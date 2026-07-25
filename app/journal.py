# =====================================================
# FAJ Platform v6.3.2
# app/journal.py
# =====================================================

import json
import logging

from app.database import get_connection


logger = logging.getLogger(__name__)


class Journal:


    def save(

        self,

        match,

        prediction,

        fixture_id=None

    ):


        try:

            conn = get_connection()

            cur = conn.cursor()


            home = prediction.get(
                "home_team"
            )

            away = prediction.get(
                "away_team"
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
                grade_name

                )

                VALUES

                (

                %s,

                %s,%s,%s,

                %s,

                %s,

                %s,%s,%s,

                %s,%s,

                %s,

                %s,

                %s,%s,

                %s,%s,

                %s,

                %s,

                %s,%s

                )


                ON CONFLICT (fixture_id)

                DO UPDATE SET


                winner = EXCLUDED.winner,

                winner_probability =
                EXCLUDED.winner_probability,

                xg_home =
                EXCLUDED.xg_home,

                xg_away =
                EXCLUDED.xg_away,

                expected_score =
                EXCLUDED.expected_score,

                confidence =
                EXCLUDED.confidence,

                risk =
                EXCLUDED.risk,

                grade =
                EXCLUDED.grade


                """,

                (

                fixture_id,

                home,
                away,
                league,

                prediction.get(
                    "winner"
                ),

                prediction.get(
                    "winner_probability"
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


                json.dumps(

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
                    "home_rating"
                ),

                prediction.get(
                    "away_rating"
                ),


                prediction.get(
                    "confidence"
                ),

                prediction.get(
                    "risk"
                ),


                prediction.get(
                    "grade"
                ),

                prediction.get(
                    "grade_name"
                )

                )

            )


            conn.commit()

            conn.close()


        except Exception as e:


            logger.error(

                "Journal save error: %s",

                e,

                exc_info=True

            )
