# =====================================================
# FAJ Debug Fixtures
# =====================================================

from app.database import get_db


def debug_fixtures():


    conn=get_db()

    cur=conn.cursor()


    print("\n=== TOTAL FIXTURES ===")


    cur.execute(
        """
        SELECT COUNT(*)
        FROM fixtures
        """
    )


    print(
        cur.fetchone()
    )



    print("\n=== STATUS ===")


    cur.execute(
        """
        SELECT status, COUNT(*)
        FROM fixtures
        GROUP BY status
        """
    )


    for row in cur.fetchall():

        print(row)



    print("\n=== SEASON ===")


    cur.execute(
        """
        SELECT season, COUNT(*)
        FROM fixtures
        GROUP BY season
        """
    )


    for row in cur.fetchall():

        print(row)



    print("\n=== RPL UPCOMING ===")


    cur.execute(
        """
        SELECT
        home_team,
        away_team,
        status,
        season

        FROM fixtures

        WHERE league='RPL'

        LIMIT 20
        """
    )


    for row in cur.fetchall():

        print(row)



    cur.close()

    conn.close()



if __name__=="__main__":

    debug_fixtures()
