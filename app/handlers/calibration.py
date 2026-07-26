# =====================================================
# FAJ Platform v6.6
# app/handlers/calibration.py
#
# FAJ Calibration Monitor
# =====================================================


from aiogram.types import Message

from app.database import get_connection





async def cmd_calibration(
    message: Message
):

    try:

        conn = get_connection()

        cur = conn.cursor()


        # Проверяем таблицу

        cur.execute(
            """
            SELECT COUNT(*)
            FROM calibration_log
            """
        )


        total = cur.fetchone()[0]



        # Последние ошибки

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


                text += f"""

⚽ Матч

FAJ:
{r[0]}

Факт:
{r[1]}


🏆 FAJ:
{r[2]}

🏆 Факт:
{r[3]}


⚠️ Ошибка:
{r[4]}


────────────
"""


        else:


            text += """

Пока ошибок нет.

После завершения матчей:

🔄 Обновить результаты

↓

🧠 Calibration

↓

FAJ Learning Layer
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


{e}
"""
        )
