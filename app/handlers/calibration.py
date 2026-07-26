# =====================================================
# FAJ Platform v6.6
# app/handlers/calibration.py
#
# FAJ Calibration Monitor
# PostgreSQL compatible
# =====================================================


from aiogram.types import Message

from app.database import get_connection





async def cmd_calibration(
    message: Message
):

    try:

        conn = get_connection()

        cur = conn.cursor()



        # =========================================
        # COUNT
        # =========================================

        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM calibration_log
            """
        )


        row = cur.fetchone()


        total = 0


        if row:

            if isinstance(row, dict):

                total = row.get(
                    "cnt",
                    0
                )

            else:

                total = row[0]





        # =========================================
        # LAST ERRORS
        # =========================================

        cur.execute(
            """
            SELECT
                faj_score,
                fact_score,
                faj_winner,
                fact_winner,
                error_type

            FROM calibration_log

            ORDER BY created DESC

            LIMIT 5
            """
        )


        rows = cur.fetchall()



        conn.close()





        text = f"""
🧠 FAJ Calibration Layer


📊 Проверено прогнозов:

{total}


━━━━━━━━━━━━━━
"""



        if rows:



            for r in rows:


                if isinstance(
                    r,
                    dict
                ):

                    faj_score = r.get(
                        "faj_score",
                        "-"
                    )

                    fact_score = r.get(
                        "fact_score",
                        "-"
                    )

                    faj_winner = r.get(
                        "faj_winner",
                        "-"
                    )

                    fact_winner = r.get(
                        "fact_winner",
                        "-"
                    )

                    error_type = r.get(
                        "error_type",
                        "-"
                    )


                else:

                    faj_score = r[0]
                    fact_score = r[1]
                    faj_winner = r[2]
                    fact_winner = r[3]
                    error_type = r[4]



                text += f"""

⚽ Матч

FAJ:
{faj_score}

Факт:
{fact_score}


🏆 FAJ:
{faj_winner}

🏆 Факт:
{fact_winner}


⚠️ Ошибка:
{error_type}


────────────
"""



        else:


            text += """

Пока нет данных.


После завершения матчей:

🔄 Обновить результаты

↓

🧠 Calibration Layer

↓

📈 FAJ Core обучение
"""





        await message.answer(
            text
        )




    except Exception as e:


        await message.answer(

            f"""
❌ Ошибка Calibration


Тип:

{type(e).__name__}


Ошибка:

{e}
"""

        )
