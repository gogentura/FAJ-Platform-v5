# =====================================================
# FAJ Platform v6.2
# Debug Soccer365 Source
# =====================================================

from aiogram.types import Message

from app.monitoring.sources.soccer365 import (
    Soccer365Source
)


async def cmd_debug_soccer365(
    message: Message
):

    source = Soccer365Source()


    html = source.get_html()


    if not html:

        await message.answer(
            """
❌ Soccer365

HTML не получен
"""
        )

        return



    fixtures = source.parse_calendar()



    text = f"""
🔍 Soccer365 Debug


HTTP:
OK


HTML:
{len(html)} символов


Найдено объектов:
{len(fixtures)}


━━━━━━━━━━━━━━

Первые данные:

"""


    for item in fixtures[:20]:

        text += (
            "\n⚽ "
            +
            str(
                item
            )
        )


    await message.answer(
        text
    )
