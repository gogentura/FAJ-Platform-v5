# =====================================================
# FAJ Platform v6.1
# Update Calendar Handler
# =====================================================


from aiogram import types


from app.monitoring.calendar_monitor import (
    update_rpl_calendar
)


from app.keyboards.admin import (
    admin_keyboard
)



# =====================================================
# UPDATE RPL CALENDAR
# =====================================================


async def cmd_update_calendar(
    message: types.Message
):


    try:


        await message.answer(
            """
🔄 FAJ обновляет календарь...


Источник:
🏆 РПЛ


Проверка:
📅 календарь
⚽ матчи
🔍 изменения
"""
        )



        report = update_rpl_calendar()



        text = f"""
✅ Календарь обновлён


🏆 Лига:
{report.get('league')}


📅 Сезон:
{report.get('season')}


➕ Добавлено:
{report.get('added')}


🔄 Обновлено:
{report.get('updated')}


✔️ Без изменений:
{report.get('unchanged')}
"""



        changes = report.get(
            "changes",
            []
        )



        if changes:


            text += """

━━━━━━━━━━━━━━

⚠️ Изменения:

"""

            for item in changes:


                text += (

                    f"\n⚽ {item.get('match')}\n"

                )


                for change in item.get(
                    "changes",
                    []
                ):


                    text += (

                        f"• {change.get('field')}: "

                        f"{change.get('old')} → "

                        f"{change.get('new')}\n"

                    )



        else:


            text += """

━━━━━━━━━━━━━━

✅ Изменений не найдено

Календарь FAJ актуален.
"""



        await message.answer(

            text,

            reply_markup=admin_keyboard()

        )



    except Exception as e:


        await message.answer(

            f"""
❌ Ошибка обновления календаря


Тип:
{type(e).__name__}


Ошибка:
{str(e)}
""",

            reply_markup=admin_keyboard()

        )
