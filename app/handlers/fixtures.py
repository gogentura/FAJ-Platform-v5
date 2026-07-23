# =====================================================
# FAJ Platform v5.2
# Fixtures Handler
# =====================================================


from aiogram import types

from app.loaders.fixtures_loader import get_upcoming_fixtures
from app.handlers.keyboard import get_main_keyboard



# =====================================================
# SHOW FIXTURES
# =====================================================


async def cmd_fixtures(
    message: types.Message
):


    fixtures = get_upcoming_fixtures(
        league="RPL",
        limit=10
    )



    if not fixtures:

        await message.answer(
            """
📅 Календарь пуст

Матчи ещё не загружены.

Сначала загрузите календарь РПЛ.
""",
            reply_markup=get_main_keyboard()
        )

        return



    text = """
📅 *Ближайшие матчи РПЛ*

──────────────
"""



    for match in fixtures:


        text += (
            f"⚽ {match['home_team']} — "
            f"{match['away_team']}\n"
            f"📆 {match['match_date']}\n"
            f"🏆 Тур: {match['round']}\n"
        )


        if match.get(
            "prediction_created"
        ):

            text += "📊 Прогноз создан\n"


        else:

            text += "⏳ Прогноз не создан\n"


        text += "──────────────\n"



    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
