# =====================================================
# FAJ Platform v6.2
# app/handlers/update_calendar.py
#
# RPL Calendar Update Handler
# Source:
#   Soccer365
# =====================================================


from aiogram.types import Message


from app.monitoring.calendar_monitor import (
    sync_rpl_calendar
)



# =====================================================
# UPDATE CALENDAR
# =====================================================


async def cmd_update_calendar(
    message: Message
):


    await message.answer(

        """
🔄 FAJ запускает синхронизацию календаря РПЛ...


Источник:

🌐 Soccer365


Проверяем:

• туры
• даты матчей
• команды
• дубли
• изменения
        """

    )



    try:


        result = await sync_rpl_calendar()



        added = result.get(
            "added",
            0
        )


        updated = result.get(
            "updated",
            0
        )


        unchanged = result.get(
            "same",
            0
        )


        errors = result.get(
            "errors",
            []
        )



        text = f"""

✅ Календарь обновлён


🏆 Лига:
RPL


📅 Сезон:
2026/27


━━━━━━━━━━━━━━


➕ Добавлено:
{added}


🔄 Обновлено:
{updated}


✔️ Без изменений:
{unchanged}

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


Теперь можно:

🔍 Проверить календарь

или

🚀 Создать прогнозы тура

"""



        await message.answer(
            text
        )



    except Exception as e:


        await message.answer(

            f"""
❌ Ошибка обновления календаря


Тип:

{type(e).__name__}


Ошибка:

{str(e)}

"""

        )
