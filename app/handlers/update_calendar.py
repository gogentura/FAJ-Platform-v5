# =====================================================
# FAJ Platform v6.1
# app/handlers/update_calendar.py
#
# RPL Calendar Update Handler
# =====================================================


from aiogram.types import Message


from app.monitoring.calendar_monitor import (
    sync_rpl_calendar
)




# =====================================================
# UPDATE CALENDAR COMMAND
# =====================================================


async def cmd_update_calendar(
    message: Message
):


    await message.answer(

        """
🔄 FAJ запускает синхронизацию календаря РПЛ...

Источник:

🌐 Sport-Express

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



        added = result.get(
            "added",
            0
        )


        updated = result.get(
            "updated",
            0
        )


        unchanged = result.get(
            "unchanged",
            0
        )


        errors = result.get(
            "errors",
            []
        )




        text = f"""

✅ Календарь обновлён


🏆 Лига:
{result.get("league","RPL")}


📅 Сезон:
{result.get("season","2026/27")}


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


                if isinstance(
                    error,
                    dict
                ):


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
