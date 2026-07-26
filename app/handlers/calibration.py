# =====================================================
# FAJ Platform v6.6
# app/handlers/calibration.py
#
# FAJ Calibration Telegram Handler
# =====================================================


import logging


from aiogram import types


from app.core.expert_engine import (
    analyze_match
)


from app.database import get_db


from app.keyboards.main import (
    main_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# GET FINISHED MATCHES
# =====================================================


def get_finished_matches():


    conn = get_db()


    try:


        cur = conn.cursor()



        cur.execute(

        """

        SELECT

        id,

        home_team,

        away_team,

        result


        FROM fixtures


        WHERE status='finished'


        ORDER BY id DESC


        LIMIT 20


        """

        )



        rows = cur.fetchall()



        return [

            dict(row)

            for row in rows

        ]



    finally:


        conn.close()






# =====================================================
# CALIBRATION REPORT
# =====================================================


async def cmd_calibration(

    message: types.Message

):


    try:


        matches = get_finished_matches()



        if not matches:


            await message.answer(

                """
🧠 FAJ Calibration

Нет завершённых матчей для анализа.

После окончания матчей:

FAJ сравнит:

• прогноз модели
• прогноз эксперта
• фактический результат

и создаст отчёт обучения.
""",

                reply_markup=main_keyboard()

            )


            return






        analyzed = 0


        expert_better = 0


        faj_better = 0


        errors = []





        for match in matches:


            try:


                result = analyze_match(

                    match["id"]

                )



                if result:


                    analyzed += 1



                    if result.get(

                        "expert_better"

                    ):


                        expert_better += 1


                    else:


                        faj_better += 1



                    errors.append(

                        result.get(

                            "error_type",

                            ""

                        )

                    )



            except Exception as e:


                logger.error(

                    "Calibration match error: %s",

                    e,

                    exc_info=True

                )








        text = (

            "🧠 *FAJ CALIBRATION REPORT*\n\n"

            "━━━━━━━━━━━━━━\n\n"

            f"📊 Проанализировано матчей: {analyzed}\n\n"

            f"👤 Эксперт лучше: {expert_better}\n"

            f"🤖 FAJ ближе: {faj_better}\n\n"

        )



        if errors:


            text += (

                "Ошибки модели:\n\n"

            )


            unique = set(errors)


            for error in unique:


                text += (

                    f"• {error}\n"

                )



        text += (

            "\n━━━━━━━━━━━━━━\n\n"

            "FAJ Learning Engine готов собирать данные.\n\n"

            "Следующий этап:\n"

            "📈 Калибровка FAJ Core\n"

            "⚖️ Настройка разницы классов команд\n"

        )





        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=main_keyboard()

        )




    except Exception as e:


        await message.answer(

            f"""
❌ Ошибка FAJ Calibration


Тип:

{type(e).__name__}


Ошибка:

{e}
""",

            reply_markup=main_keyboard()

        )
