# =====================================================
# GET PREDICTIONS
# =====================================================

def get_predictions(
    league=None,
    season=None,
    round_number=None
):

    conn = get_db()

    try:

        query = """
        SELECT

            p.*,

            f.match_date,

            f.home_team,

            f.away_team

        FROM predictions p

        LEFT JOIN fixtures f

            ON p.fixture_id = f.id

        WHERE 1=1
        """

        params = []


        if league:

            query += """

            AND p.league = ?

            """

            params.append(
                league
            )


        if season:

            query += """

            AND p.season = ?

            """

            params.append(
                season
            )


        if round_number:

            query += """

            AND p.round = ?

            """

            params.append(
                round_number
            )


        query += """

        ORDER BY

            p.round ASC,

            f.match_date ASC,

            f.home_team ASC

        """


        rows = conn.execute(

            query,

            tuple(params)

        ).fetchall()


        return [

            dict(row)

            for row in rows

        ]


    finally:

        conn.close()
