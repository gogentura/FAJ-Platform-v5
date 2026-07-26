# =====================================================
# FAJ Platform v6.6
# app/handlers/calibration.py
#
# FAJ Calibration Handler
# PostgreSQL version
# =====================================================


import logging


from aiogram import types


from app.database import get_db


from app.keyboards.admin import (
    admin_keyboard
)


from app.core.expert_engine import (
    analyze_match
)



logger = logging.getLogger(__name__)





# =====================================================
# GET COMPLETED MATCHES
# =====================================================


def get_completed_matches():


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(
            """
            SELECT

                f.id,

                f.home_team,

                f.away_team,

                f.home_score,

                f.away_score,

                f.status,

                f.season,


                p.expected_score,

                p.winner_prediction,

                p.confidence


            FROM fixtures f


            LEFT JOIN predictions p

            ON p.fixture_id = f.id


            WHERE

                f.status = 'finished'

            AND

                f.home_score IS NOT NULL

            AND

                f.away_score IS NOT NULL


            ORDER BY f.id DESC


            LIMIT 50

            """
        )



        rows = cur.fetchall()



        return rows



    finally:

        conn.close()







# =====================================================
# SAVE CALIBRATION RESULT
# =====================================================


def save_calibration(

    fixture_id,

    faj_score,

    fact_score,

    faj_winner,

    fact_winner,

    error_type,

    confidence=0

):


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(

        """

        INSERT INTO calibration_log

        (

            fixture_id,

            faj_score,

            fact_score,

            faj_winner,

            fact_winner,

            error_type,

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

            NOW()

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



        conn.commit()



    except Exception as e:


        conn.rollback()


        logger.error(

            f"Calibration save error: {e}"

        )


        raise



    finally:


        conn.close()








# =====================================================
# CALIBRATION BUTTON
# =====================================================


async def cmd_calibration(

    message: types.Message

):


    try:



        matches = get_completed_matches()



        if not matches:


            await message.answer(

                """
🧠 FAJ Calibration


Нет завершённых матчей.


После обновления результатов:

🔄 Обновить результаты

FAJ сможет сравнить:

🤖 модель

👤 эксперт

🏟 факт

и обучить ядро.
""",

                reply_markup=admin_keyboard()

            )


            return






        total = 0

        errors_count = 0

        correct = 0





        text = (

            "🧠 *FAJ CALIBRATION REPORT*\n\n"

            "━━━━━━━━━━━━━━\n\n"

        )







        for match in matches:



            try:


                fixture_id = match["id"]



                home = match["home_team"]

                away = match["away_team"]



                fact_score = (

                    f"{match['home_score']}"

                    "-"

                    f"{match['away_score']}"

                )



                if match["home_score"] > match["away_score"]:

                    fact_winner = home


                elif match["away_score"] > match["home_score"]:

                    fact_winner = away


                else:

                    fact_winner = "Ничья"





                faj_score = match["expected_score"] or "-"



                faj_winner = match["winner_prediction"] or "-"





                error_type = "OK"



                if faj_winner != fact_winner:


                    error_type = (

                        "Ошибка победителя"

                    )

                    errors_count += 1


                else:


                    correct += 1






                save_calibration(

                    fixture_id,

                    faj_score,

                    fact_score,

                    faj_winner,

                    fact_winner,

                    error_type

                )



                total += 1




                text += (

                    f"⚽ {home} — {away}\n"

                    f"FAJ: {faj_score} ({faj_winner})\n"

                    f"Факт: {fact_score} ({fact_winner})\n"

                    f"📌 {error_type}\n\n"

                )




            except Exception as e:


                logger.error(

                    f"Calibration match error: {e}",

                    exc_info=True

                )








        text += (

            "━━━━━━━━━━━━━━\n\n"

            f"📊 Матчей: {total}\n"

            f"✅ Верных: {correct}\n"

            f"❌ Ошибок: {errors_count}\n\n"

            "FAJ Learning Engine обновляет данные.\n"

        )





        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=admin_keyboard()

        )




    except Exception as e:


        logger.error(

            f"Calibration handler error: {e}",

            exc_info=True

        )


        await message.answer(

            f"""
❌ Ошибка FAJ Calibration


Тип:

{type(e).__name__}


Ошибка:

{e}
""",

            reply_markup=admin_keyboard()

        )
