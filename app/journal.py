# =====================================================
# FAJ Platform v6.3
# app/journal.py
#
# PostgreSQL Journal Layer
# =====================================================

from datetime import datetime
import json

from app.database import get_db


# =====================================================
# CLEAN VALUES
# =====================================================

def clean_value(value):

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

        now = datetime.now()



        # =============================================
        # PARSE TEAMS
        # =============================================

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



        # =============================================
        # TEXT
        # =============================================

        prediction_text = (

            f"{prediction.get('winner_name','')} | "

            f"xG "

            f"{prediction.get('xg_home',0)}-"

            f"{prediction.get('xg_away',0)} | "

            f"{prediction.get('expected_score','')}"

        )



        # =============================================
        # INSERT
        # =============================================

        conn.execute(
        """

        INSERT INTO journal
        (

            date,

            match,

            home_team,

            away_team,


            prediction,

            winner,

            winner_prob,


            home_prob,

            draw_prob,

            away_prob,


            xg_home,

            xg_away,


            expected_score,

            top_scores,


            btts,

            over25,


            actual_score,

            actual_winner,


            confidence,


            model_version,

            data_version,


            accuracy,


            created


        )

        VALUES

        (

            %s,%s,%s,%s,%s,

            %s,%s,%s,%s,%s,

            %s,%s,%s,%s,%s,

            %s,%s,%s,%s,%s,

            %s,%s,%s,%s

        )

        """,

        (

            now,

            match,

            home_team,

            away_team,


            prediction_text,


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



            json.dumps(
                prediction.get(
                    "top_scores",
                    []
                ),
                ensure_ascii=False
            ),



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
                    "confidence",
                    0
                )
            ),



            "6.3",



            "2026.07",



            None,



            now

        )

        )



        conn.commit()

        conn.close()



    # =================================================
    # LAST PREDICTIONS
    # =================================================

    def get_all(
        self,
        limit=20
    ):

        conn = get_db()


        rows = conn.execute(
        """

        SELECT *

        FROM journal

        ORDER BY id DESC

        LIMIT %s

        """,

        (
            limit,
        )

        ).fetchall()



        conn.close()



        return [

            dict(row)

            for row in rows

        ]
