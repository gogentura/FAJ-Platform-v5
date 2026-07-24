# =====================================================
# FAJ Platform v6.1
# app/handlers/debug_calendar.py
# =====================================================


from aiogram.types import Message

from app.monitoring.sources.sportexpress import (
    SportExpressSource
)

from app.monitoring.rpl_calendar_parser import (
    RPL_CALENDAR_URL
)



async def cmd_debug_calendar(
    message: Message
):

    source = SportExpressSource()


    html = source.get_page(
        RPL_CALENDAR_URL
    )


    if not html:

        await message.answer(
            """
❌ Sport-Express не отвечает

HTML не получен
"""
        )

        return



    length = len(html)


    preview = html[:500]


    await message.answer(

        f"""
🔍 FAJ Calendar Debug


🌐 URL:

{RPL_CALENDAR_URL}


📄 HTML размер:

{length} символов


Первые 500 символов:

{preview}
"""
    )
