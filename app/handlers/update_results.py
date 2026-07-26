# =====================================================
# FAJ Platform v6.6
# app/handlers/update_results.py
#
# Match Results Update Handler
#
# PostgreSQL Compatible
# =====================================================


import logging


from aiogram.types import Message


from app.monitoring.results_monitor import (
    sync_results
)


from app.services.result_analyzer import (
    analyze_finished_matches
)


from app.keyboards.admin import (
    admin_keyboard
)



logger = logging.getLogger(__name__)





# =====================================================
# UPDATE RESULTS BUTTON
# =====================================================


async def cmd_update_results(

    message: Message

):


    await message.answer(

        """
🔄 FAJ обновляет результаты матчей...


Источник:

🌐 Soccer365


Проверяем:

• завершённые матчи
• счета
• победителей
• статус fixtures
• сравнение FAJ прогнозов с фактом

⏳ Выполняется...
""",

        reply_markup=admin_keyboard()

    )



    try:



        # =============================================
        # STEP 1
        # SYNC RESULTS
        # =============================================


        sync_result = sync_results()



        if sync_result is None:

            sync_result = {}



        updated = sync_result.get(

            "updated",

            0

        )



        sync_errors = sync_result.get(

            "errors",

            []

        )





        # =============================================
        # STEP 2
        # CALIBRATION ANALYSIS
        # =============================================


        analyzed = analyze_finished_matches()



        if analyzed is None:

            analyzed = 0






        # =============================================
        # RESPONSE
        # =============================================


        text = (

            "🏆 *FAJ Results Update*\n\n"

            "━━━━━━━━━━━━━━\n\n"

            f"🔄 Обновлено матчей: {updated}\n\n"

            f"🧠 Проверено прогнозов: {analyzed}\n\n"

            "━━━━━━━━━━━━━━\n\n"

            "FAJ Learning Layer:\n\n"

            "✅ факт матча получен\n"

            "✅ прогноз сравнен\n"

            "✅ ошибки записаны\n"

            "✅ Calibration Log обновлён\n\n"

        )




        if sync_errors:


            text += (

                "⚠️ Ошибки синхронизации:\n\n"

            )


            for error in sync_errors[:10]:


                text += (

                    f"❌ {error}\n"

                )



        else:


            text += (

                "✅ Ошибок синхронизации нет\n\n"

                "FAJ готов к анализу:\n\n"

                "📊 точность модели\n"

                "🎯 ошибки счёта\n"

                "🧠 ошибки победителя\n"

                "📈 калибровка FAJ Core"

            )





        await message.answer(

            text,

            parse_mode="Markdown",

            reply_markup=admin_keyboard()

        )





    except Exception as e:



        logger.exception(

            "FAJ update results failed"

        )



        await message.answer(

            f"""
❌ Ошибка обновления результатов FAJ


Тип:

{type(e).__name__}


Ошибка:

{str(e)}
""",

            reply_markup=admin_keyboard()

        )
