# =====================================================
# FAJ Platform v6.0
# Fixtures Diagnostic
# =====================================================


from app.database import get_db



def check_fixtures():


    conn = get_db()


    rows = conn.execute(
        """
        SELECT
            id,
            league,
            season,
            round,
            date,
            home_team,
            away_team

        FROM fixtures

        WHERE league = 'RPL'

        AND season = '2026/27'

        ORDER BY id
        """
    ).fetchall()



    print("\n========== FAJ FIXTURES ==========\n")



    for row in rows:

        print(
            f"{row['id']} | "
            f"Тур {row['round']} | "
            f"{row['date']} | "
            f"{row['home_team']} - {row['away_team']}"
        )



    print(
        "\nВсего матчей:",
        len(rows)
    )


    conn.close()




if __name__ == "__main__":

    check_fixtures()
