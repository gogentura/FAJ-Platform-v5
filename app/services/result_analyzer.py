# =====================================================
# FAJ Platform v6.6
# app/services/result_analyzer.py
#
# FAJ Result Analyzer
#
# Сравнение:
# FAJ прогноз
# Факт матча
# Calibration Log
# =====================================================


import logging


from app.database import get_connection



logger = logging.getLogger(__name__)





# =====================================================
# WINNER DETECTOR
# =====================================================


def detect_winner(
    home_score,
    away_score,
    home_team,
    away_team
):


    if home_score > away_score:

        return home_team


    elif away_score > home_score:

        return away_team


    else:

        return "Ничья"







# =====================================================
# ANALYZE FINISHED MATCHES
# =====================================================


def analyze_finished_matches():


    conn = get_connection()


    analyzed = 0



    try:


        cur = conn.cursor()



        # Берём матчи,
        # где есть факт и прогноз


        cur.execute(

        """

        SELECT


            f.id,

            f.home_team,

            f.away_team,

            f.home_score,

            f.away_score,


            p.expected_score,

            p.winner_prediction


        FROM fixtures f


        LEFT JOIN predictions p


        ON p.fixture_id = f.id


        WHERE


            f.status = %s


        AND

            f.home_score IS NOT NULL


        AND

            f.away_score IS NOT NULL


        AND

            p.id IS NOT NULL


        ORDER BY

            f.match_date DESC


        """,

        (

            "finished",

        )

        )




        matches = cur.fetchall()





        for match in matches:


            fixture_id = match[0]


            home = match[1]

            away = match[2]


            home_score = match[3]

            away_score = match[4]


            faj_score = match[5]

            faj_winner = match[6]





            fact_score = (

                f"{home_score}-{away_score}"

            )


            fact_winner = detect_winner(

                home_score,

                away_score,

                home,

                away

            )



            error_type = "OK"



            if faj_score != fact_score:


                error_type = "Ошибка счёта"




            if faj_winner != fact_winner:


                if error_type == "OK":

                    error_type = "Ошибка победителя"

                else:

                    error_type += "+ победитель"







            # сохраняем ошибку


            cur.execute(

            """

            INSERT INTO calibration_log

            (

                fixture_id,

                faj_score,

                fact_score,

                faj_winner,

                fact_winner,

                error_type

            )


            VALUES

            (

                %s,

                %s,

                %s,

                %s,

                %s,

                %s

            )


            """,

            (

                fixture_id,

                faj_score,

                fact_score,

                faj_winner,

                fact_winner,

                error_type

            )

            )



            analyzed += 1






        conn.commit()



        logger.info(

            f"FAJ analyzed matches: {analyzed}"

        )



        return analyzed





    except Exception as e:


        conn.rollback()


        logger.exception(

            f"Result analyzer error: {e}"

        )


        raise



    finally:


        conn.close()
