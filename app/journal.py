from datetime import datetime

from app.database import get_db


# =====================================================
# CLEAN NUMPY VALUES
# =====================================================

def clean_value(value):

    if hasattr(value, "item"):
        return value.item()

    return value



# =====================================================
# JOURNAL
# =====================================================

class Journal:


    def save(
        self,
        match: str,
        prediction: dict,
        actual: dict = None
    ):

        conn = get_db()

        now = datetime.now().isoformat()



        # =============================================
        # SAFE MATCH PARSE
        # =============================================

        parts = (
            match
            .replace("-", "—")
            .split("—")
        )


        home_team = parts[0].strip()


        away_team = (
            parts[1].strip()
            if len(parts) > 1
            else ""
        )



        # =============================================
        # HUMAN READABLE PREDICTION
        # =============================================

        prediction_text = (
            f"{prediction.get('winner', '')} | "
            f"xG "
            f"{prediction.get('xg_home', 0)}-"
            f"{prediction.get('xg_away', 0)} | "
            f"{prediction.get('expected_score', '')}"
        )



        conn.execute(
        """
        INSERT INTO journal (

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


        VALUES (

            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?

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
                    "home_prob",
                    0
                )
            ),



            clean_value(
                prediction.get(
                    "draw_prob",
                    0
                )
            ),



            clean_value(
                prediction.get(
                    "away_prob",
                    0
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



            str(
                prediction.get(
                    "top_scores",
                    []
                )
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
            if actual else "",



            actual.get(
                "winner",
                ""
            )
            if actual else "",



            clean_value(
                prediction.get(
                    "confidence",
                    0
                )
            ),



            "5.2",



            datetime.now().strftime(
                "%Y-%m-%d"
            ),



            "pending",



            now

        )

        )


        conn.commit()

        conn.close()



    # =================================================
    # GET LAST PREDICTIONS
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

        LIMIT ?

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
