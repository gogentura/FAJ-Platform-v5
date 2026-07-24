# =====================================================
# FAJ Platform v6.2
# app/handlers/update_results.py
#
# Match Results Update Handler
# =====================================================


import logging


from aiogram.types import Message


from app.monitoring.results_monitor import (
    sync_results
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

        """

    )



    try:



        result = sync_results()



        updated = result.get(

            "updated",

            0

        )



        errors = result.get(

            "errors",

            []

        )



        text = f"""

✅ Результаты обновлены


🏆 Лига:

RPL


━━━━━━━━━━━━━━


🔄 Обновлено матчей:

{updated}

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

🧠 подготовку прогнозов

📈 обновление формы команд

"""



        await message.answer(

            text

        )



    except Exception as e:


        logger.exception(e)



        await message.answer(

            f"""

❌ Ошибка обновления результатов


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )
