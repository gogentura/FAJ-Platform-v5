# =====================================================
# FAJ Platform v6.4
# app/handlers/update_results.py
#
# Match Results Update Handler
#
# Results Sync + Journal Analyzer
# =====================================================


import logging


from aiogram.types import Message


from app.monitoring.results_monitor import (
    sync_results
)


from app.services.result_analyzer import (
    analyze_finished_matches
)



logger = logging.getLogger(__name__)



# =====================================================
# UPDATE RESULTS COMMAND
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
• победителя
• статус fixtures
• сравнение прогнозов FAJ с фактом

        """

    )



    try:


        # =============================================
        # STEP 1
        # SYNC RESULTS
        # =============================================


        result = sync_results()



        updated = result.get(

            "updated",

            0

        )



        errors = result.get(

            "errors",

            []

        )



        # =============================================
        # STEP 2
        # ANALYZE RESULTS
        # =============================================


        analyzed = analyze_finished_matches()



        # =============================================
        # RESPONSE
        # =============================================


        text = f"""

✅ Результаты FAJ обновлены


🏆 Лига:

RPL


━━━━━━━━━━━━━━


🔄 Матчей обновлено:

{updated}


🧠 Прогнозов проверено:

{analyzed}


━━━━━━━━━━━━━━


FAJ Learning Layer:

✅ победитель сравнен

✅ точный счёт проверен

✅ журнал обновлён

"""



        if errors:


            text += """

━━━━━━━━━━━━━━

⚠️ Ошибки:

"""


            for error in errors[:10]:


                text += f"""

❌ {error}

"""



        else:


            text += """

━━━━━━━━━━━━━━

✅ Ошибок нет

FAJ продолжает:

📊 сбор статистики

🧠 анализ точности модели

📈 обновление качества прогнозов

"""



        await message.answer(

            text

        )



    except Exception as e:


        logger.exception(e)



        await message.answer(

            f"""

❌ Ошибка обновления результатов FAJ


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )
