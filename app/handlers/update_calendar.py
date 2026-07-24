# =====================================================
# FAJ Platform v6.3
# app/handlers/update_calendar.py
#
# RPL Calendar Update Handler
# =====================================================


from aiogram.types import Message


from app.monitoring.calendar_monitor import (
    sync_rpl_calendar
)



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


        result = sync_rpl_calendar()



        text = f"""
✅ Календарь обновлён


🏆 Лига:
{result.get("league", "RPL")}


📅 Сезон:
{result.get("season", "2026/27")}


━━━━━━━━━━━━━━


➕ Добавлено:
{result.get("added", 0)}


🔄 Обновлено:
{result.get("updated", 0)}


✔️ Без изменений:
{result.get("unchanged", 0)}

"""


        errors = result.get(
            "errors",
            []
        )


        if errors:


            text += """

━━━━━━━━━━━━━━

⚠️ Ошибки:

"""


            for error in errors[:10]:


                if isinstance(error, dict):

                    text += (
                        f"""
⚽ {error.get("match","")}

❌ {error.get("error","")}

"""
                    )

                else:

                    text += (
                        f"""
❌ {error}

"""
                    )


        else:


            text += """

━━━━━━━━━━━━━━

✅ Ошибок нет
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

{repr(e)}
"""
        )
